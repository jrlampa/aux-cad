"""
test_unifilar_diagrama.py - Testes unitários para busca de dispositivos KMZ,
determinação de blocos ('chaves_' e 'REL') e construção do esquema gráfico unifilar 2.5D.
"""

import os
import json
import pytest
from pathlib import Path
from unifilar.dispositivos_kmz_finder import (
    normalizar_chave_dispositivo,
    extrair_apenas_digitos,
    buscar_dispositivo_kmz,
    latlon_to_utm,
    CAMINHO_PADRAO_KMZ,
    CACHE_FILE,
)
from unifilar.unifilar_diagrama_builder import (
    determinar_bloco_protecao,
    construir_esquema_unifilar,
    gerar_dicionario_esquema,
)
from unifilar.unifilar_manager import processar_ponto


class TestDispositivosKmzFinder:
    """Testes para o buscador de dispositivos KMZ e conversão geográfica."""

    def test_normalizar_chave_dispositivo(self):
        assert normalizar_chave_dispositivo("CF636018") == "CF636018"
        assert normalizar_chave_dispositivo("CHAVE FUSÍVEL CF-636018") == "CHAVEFUSVELCF636018"
        assert normalizar_chave_dispositivo("REL-9923") == "REL9923"
        assert normalizar_chave_dispositivo("SG-59356") == "SG59356"
        assert normalizar_chave_dispositivo("") == ""

    def test_extrair_apenas_digitos(self):
        assert extrair_apenas_digitos("CF636018") == "636018"
        assert extrair_apenas_digitos("REL-9923") == "9923"
        assert extrair_apenas_digitos("ABC") == ""
        assert extrair_apenas_digitos("") == ""

    def test_latlon_to_utm(self):
        # Ponto real no Rio de Janeiro (Fuso 23S)
        lat = -22.9068
        lon = -43.1729
        x, y = latlon_to_utm(lat, lon, zone=23, northern_hemisphere=False)
        assert 680000 < x < 700000
        assert 7460000 < y < 7470000

        # Hemisfério Norte
        xn, yn = latlon_to_utm(22.9068, -43.1729, zone=23, northern_hemisphere=True)
        assert 680000 < xn < 700000
        assert yn > 0

    def test_ler_dispositivos_de_kmz_com_arquivo_valido(self, tmp_path):
        import zipfile
        from unifilar.dispositivos_kmz_finder import ler_dispositivos_de_kmz

        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>CF-998877</name>
      <Point>
        <coordinates>-43.1729,-22.9068,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>REL-112233</name>
      <Point>
        <coordinates>-43.1800,-22.9100,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
        kmz_path = tmp_path / "teste_dispositivos.kmz"
        with zipfile.ZipFile(kmz_path, "w") as z:
            z.writestr("doc.kml", kml_content)

        res = ler_dispositivos_de_kmz(str(kmz_path))
        assert "CF998877" in res
        assert "REL112233" in res
        assert res["CF998877"]["lat"] == -22.9068
        assert res["CF998877"]["lon"] == -43.1729
        assert "NUM_998877" in res

        # Arquivo inexistente
        assert ler_dispositivos_de_kmz("caminho_inexistente.kmz") == {}

    def test_buscar_dispositivo_existente(self):
        if os.path.exists(CACHE_FILE) or os.path.exists(CAMINHO_PADRAO_KMZ):
            res = buscar_dispositivo_kmz("CF636018", fuso_utm=23)
            assert res is not None
            assert res["encontrado"] is True
            assert "636018" in res["nome_original"]
            assert res["utm_x"] > 0
            assert res["utm_y"] > 0
            assert res["fuso"] == 23

    def test_buscar_dispositivo_inexistente(self):
        res = buscar_dispositivo_kmz("CODIGO_INEXISTENTE_99999999")
        assert res is None


class TestUnifilarDiagramaBuilder:
    """Testes para o construtor geométrico 2.5D do diagrama unifilar."""

    def test_determinar_bloco_protecao(self):
        assert determinar_bloco_protecao("RELIGADOR", "REL 9923") == "REL."
        assert determinar_bloco_protecao("REL", "AL-01") == "REL."
        assert determinar_bloco_protecao("CHAVE FUSIVEL", "CF636018") == "chaves_"
        assert determinar_bloco_protecao("SECCIONADORA", "SG-100") == "chaves_"
        assert determinar_bloco_protecao("CHAVE_FACA_FUSIVEL", "") == "chaves_"
        assert determinar_bloco_protecao("DESCONHECIDO", "") == "chaves_"

    def test_construir_esquema_unifilar(self):
        esquema = construir_esquema_unifilar(
            subestacao="NILOPOLIS",
            alimentador="01",
            protecao_rotulo="CF636018",
            protecao_tipo="CHAVE_FUSIVEL",
            ponto_alvo="N760355",
            clientes_a=0,
            clientes_b=12,
            kva=45.0,
            pt_base=(100.0, 200.0),
            escala_h=2.5,
        )

        assert len(esquema.linhas) >= 3
        assert len(esquema.textos) >= 6
        assert len(esquema.blocos) >= 2

        # Verifica bloco da proteção
        blk_prot = next((b for b in esquema.blocos if b.nome_bloco == "chaves_"), None)
        assert blk_prot is not None
        assert blk_prot.nome_bloco == "chaves_"

        # Verifica bloco do ponto
        blk_pto = next((b for b in esquema.blocos if b.nome_bloco == "PONTO"), None)
        assert blk_pto is not None
        assert blk_pto.nome_bloco == "PONTO"

        # Dicionário serializável
        d = gerar_dicionario_esquema(esquema)
        assert "linhas" in d
        assert "textos" in d
        assert "blocos" in d


class TestUnifilarManagerIntegration:
    """Testes de integração com o unifilar_manager."""

    def test_processar_ponto_com_resumo_manual(self, tmp_path):
        resumo = "Saida do Alimentador - NIL01 > Chave Fusivel - CF636018 Clientes Grupo A: 0 Clientes Grupo B: 15 - KVA: 75 > Poste - N760355"
        out_json = str(tmp_path / "saida_unifilar.json")

        resultado = processar_ponto(
            ponto="N760355",
            resumo_manual=resumo,
            arquivo_saida=out_json,
        )

        assert resultado["sucesso"] is True
        assert resultado["subestacao"] == "NIL"
        assert resultado["alimentador"] == "01"
        assert resultado["bloco_protecao"] == "chaves_"
        assert "esquema_grafico" in resultado
        assert os.path.exists(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            dados_salvos = json.load(f)
            assert dados_salvos["sucesso"] is True
            assert dados_salvos["subestacao"] == "NIL"
            assert dados_salvos["bloco_protecao"] == "chaves_"

    def test_dispositivos_kmz_finder_edge_cases(self, tmp_path):
        from unifilar.dispositivos_kmz_finder import DispositivosKmzIndex
        # Teste com código vazio
        assert buscar_dispositivo_kmz("") is None
        assert buscar_dispositivo_kmz(None) is None

        # Teste com pasta_kmz customizada e cache isolado
        pasta_vazia = tmp_path / "kmz_vazia"
        pasta_vazia.mkdir()
        cache_isolado = str(tmp_path / "cache_vazio.json")
        idx = DispositivosKmzIndex(pasta_kmz=str(pasta_vazia), cache_file=cache_isolado)
        idx.carregar_indice(forcar_reindex=True)
        assert len(idx.dados) == 0
        assert idx.buscar("QUALQUER") is None

        # Teste com busca por prefixo e dígitos
        if os.path.exists(CACHE_FILE):
            res_num = buscar_dispositivo_kmz("636018")
            assert res_num is not None
            assert res_num["encontrado"] is True

    def test_cli_dispositivos_kmz_finder(self):
        import subprocess
        # Teste de execução CLI do localizador KMZ com --json
        cmd = [
            "python",
            "unifilar/dispositivos_kmz_finder.py",
            "--codigo",
            "CF636018",
            "--json"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "encontrado" in proc.stdout
        dados = json.loads(proc.stdout)
        assert dados.get("encontrado") is True

        # Teste de execução CLI sem --json (formato texto amigável)
        cmd_txt = [
            "python",
            "unifilar/dispositivos_kmz_finder.py",
            "--codigo",
            "CF636018"
        ]
        proc_txt = subprocess.run(cmd_txt, capture_output=True, text=True, check=True)
        assert "Dispositivo encontrado" in proc_txt.stdout

        # Teste de execução CLI com dispositivo inexistente
        cmd_inex = [
            "python",
            "unifilar/dispositivos_kmz_finder.py",
            "--codigo",
            "INEXISTENTE_XYZ_999"
        ]
        proc_inex = subprocess.run(cmd_inex, capture_output=True, text=True, check=True)
        assert "não encontrado" in proc_inex.stdout

    def test_buscar_dispositivo_kmz_com_pasta_custom(self, tmp_path):
        # Chama a função de conveniência passando pasta_kmz
        res = buscar_dispositivo_kmz("CF123", pasta_kmz=str(tmp_path))
        assert res is None

    def test_cli_unifilar_manager(self, tmp_path):
        import subprocess
        out_f = str(tmp_path / "cli_unifilar.json")
        resumo = "Saida do Alimentador - NIL01 > Chave Fusivel - CF636018 Clientes Grupo A: 0 Clientes Grupo B: 15 - KVA: 75 > Poste - N760355"
        cmd = [
            "python",
            "unifilar/unifilar_manager.py",
            "--resumo",
            resumo,
            "--ponto",
            "N760355",
            "--out",
            out_f
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert os.path.exists(out_f)
        with open(out_f, "r", encoding="utf-8") as f:
            d = json.load(f)
            assert d["sucesso"] is True
            assert d["bloco_protecao"] == "chaves_"
            assert d["alimentador"] == "01"


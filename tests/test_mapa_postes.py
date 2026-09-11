"""
Testes Unitários para o Módulo de Estúdio Web de Postes & Cargas (mapa_postes/mapa_servidor.py).
"""

import os
import tempfile
import zipfile
import pytest

from mapa_postes.mapa_servidor import (
    PosteStudio,
    EstadoProjeto,
    gerar_lisp_postes_studio,
    exportar_kmz_studio
)


def test_estado_projeto_persist_e_restore():
    """Testa salvar e recarregar os postes em JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "mapa_teste.json")
        estado = EstadoProjeto(json_file)

        p1 = PosteStudio(
            id="p_1",
            numero="01",
            lat=-22.9000,
            lon=-43.1700,
            x_utm=687000.0,
            y_utm=7466000.0,
            tipo_poste="11/M",
            estrutura_mt="N1",
            estrutura_bt="S1",
            clientes_mono=3,
            clientes_bi=1,
            clientes_tri=1,
            cargas_especiais=[{"descricao": "Bomba 15CV", "potencia_kw": 11.0, "tipo": "Trifásica"}]
        )
        estado.postes[p1.id] = p1
        estado.salvar()

        assert os.path.exists(json_file)

        # Novo estado carregando do mesmo arquivo
        novo_estado = EstadoProjeto(json_file)
        assert len(novo_estado.postes) == 1
        carregado = novo_estado.postes["p_1"]
        assert carregado.numero == "01"
        assert carregado.clientes_mono == 3
        assert carregado.clientes_bi == 1
        assert carregado.clientes_tri == 1
        assert len(carregado.cargas_especiais) == 1
        assert carregado.cargas_especiais[0]["potencia_kw"] == 11.0


def test_gerar_lisp_postes_studio_com_clientes_e_cargas():
    """Testa a geração de código AutoLISP incluindo blocos e anotações enriquecidas."""
    p = PosteStudio(
        id="p_2",
        numero="02",
        lat=-22.9068,
        lon=-43.1729,
        x_utm=687483.0,
        y_utm=7465384.0,
        tipo_poste="11/400",
        estrutura_mt="N3b",
        estrutura_bt="F2-D2",
        equipamentos=["IP", "DAE"],
        clientes_mono=2,
        clientes_bi=0,
        clientes_tri=1,
        cargas_especiais=[{"descricao": "Oficina Mecânica", "potencia_kw": 15.0}]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_lsp = os.path.join(tmpdir, "mapa_postes_exec.lsp")
        gerar_lisp_postes_studio([p], out_lsp)

        assert os.path.exists(out_lsp)
        with open(out_lsp, "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Blocos padronizados
        assert '"POSTE_"' in conteudo
        assert '"PONTO"' in conteudo
        assert '"02"' in conteudo

        # Textos e Estruturas
        assert '"11/400"' in conteudo
        assert '"N3b"' in conteudo
        assert '"F2-D2"' in conteudo
        assert '"IP"' in conteudo
        assert '"DAE"' in conteudo

        # Anotação de Clientes e Cargas
        assert 'CLI: 2M/1T/OFIC 16.3kVA' in conteudo or 'CLI: 2M/1T' in conteudo
        assert 'CARGA TRI: OFICINA MECÂNICA 16.3kVA (15kW)' in conteudo
        assert 'POSTES_CARGAS' in conteudo


def test_gerar_lisp_postes_studio_com_multi_estruturas_e_trafo_bloco_t():
    """Valida que múltiplas estruturas MT/BT e o bloco T de transformador são gerados no LISP."""
    p = PosteStudio(
        id="p_trafo",
        numero="01",
        lat=-22.9068,
        lon=-43.1729,
        x_utm=556984.25,
        y_utm=7502486.19,
        tipo_poste="11/600",
        estrutura_mt="N3b",
        estrutura_bt="S2",
        estruturas_mt=["N3b", "CE1"],
        estruturas_bt=["S1", "S2"],
        equipamentos=["IP", "TRAFO 45kVA"],
        tem_trafo=True,
        potencia_trafo="45kVA"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_lsp = os.path.join(tmpdir, "mapa_postes_trafo.lsp")
        gerar_lisp_postes_studio([p], out_lsp)

        assert os.path.exists(out_lsp)
        with open(out_lsp, "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Verifica bloco POSTE_, bloco PONTO e bloco T do Trafo
        assert '"POSTE_"' in conteudo
        assert '"PONTO"' in conteudo
        assert '"T"' in conteudo  # Bloco específico de Trafo

        # Multi-estruturas geradas nas descrições
        assert '"N3b"' in conteudo
        assert '"CE1"' in conteudo
        assert '"S1"' in conteudo
        assert '"S2"' in conteudo
        assert '"TRAFO 45kVA"' in conteudo


def test_conversao_potencia_trifasica_fp92():
    """Testa a conversão bidirecional entre kW e kVA com FP = 0.92."""
    from mapa_postes.mapa_servidor import converter_potencia_trifasica

    # 1. Informado kW -> calcula kVA
    kw, kva = converter_potencia_trifasica(kw=15.0, fp=0.92)
    assert kw == 15.0
    assert kva == 16.30  # 15 / 0.92 = 16.304 -> 16.3

    # 2. Informado kVA -> calcula kW
    kw2, kva2 = converter_potencia_trifasica(kva=45.0, fp=0.92)
    assert kva2 == 45.0
    assert kw2 == 41.40  # 45 * 0.92 = 41.4

    # 3. Informado 30 kW -> calcula kVA
    kw3, kva3 = converter_potencia_trifasica(kw=30.0, fp=0.92)
    assert kw3 == 30.0
    assert kva3 == 32.61  # 30 / 0.92 = 32.608 -> 32.61


def test_exportar_kmz_studio_comprimido():
    """Testa a geração de arquivo KMZ válido para Google Earth."""
    p = PosteStudio(
        id="p_3",
        numero="03",
        lat=-23.0190,
        lon=-44.1636,
        x_utm=585698.0,
        y_utm=7454125.0,
        tipo_poste="11/M",
        estrutura_mt="N1",
        estrutura_bt="S1",
        clientes_mono=1
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_kmz = os.path.join(tmpdir, "rede_studio.kmz")
        exportar_kmz_studio([p], out_kmz)

        assert os.path.exists(out_kmz)
        with zipfile.ZipFile(out_kmz, "r") as z:
            assert "doc.kml" in z.namelist()
            kml_text = z.open("doc.kml").read().decode("utf-8")
            assert "<name>03</name>" in kml_text
            assert "11/M" in kml_text
            assert "1 Mono" in kml_text


def test_mapa_handler_api_rotas_http():
    """Testa as requisições HTTP da API REST do servidor."""
    import http.client
    import threading
    from mapa_postes.mapa_servidor import criar_servidor

    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "db.json")
        web_dir = os.path.join(tmpdir, "web")
        os.makedirs(web_dir, exist_ok=True)
        with open(os.path.join(web_dir, "index.html"), "w") as f:
            f.write("<h1>Mapa Studio</h1>")

        estado = EstadoProjeto(json_file)
        server = criar_servidor(porta=8799, estado=estado, web_dir=web_dir)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", 8799, timeout=5)

            # 1. GET / (serve index.html)
            conn.request("GET", "/")
            res = conn.getresponse()
            assert res.status == 200
            corpo = res.read().decode("utf-8")
            assert "Mapa Studio" in corpo

            # 2. POST /api/postes (atualiza lista)
            dados_postes = {
                "postes": [
                    {
                        "id": "p_http_1",
                        "numero": "01",
                        "lat": -22.9068,
                        "lon": -43.1729,
                        "tipo_poste": "11/M",
                        "estrutura_mt": "N1",
                        "estrutura_bt": "S1",
                        "clientes_mono": 2,
                        "clientes_bi": 1,
                        "clientes_tri": 0
                    }
                ]
            }
            import json
            payload = json.dumps(dados_postes)
            conn.request("POST", "/api/postes", payload, {"Content-Type": "application/json"})
            res = conn.getresponse()
            assert res.status == 200
            res_data = json.loads(res.read().decode("utf-8"))
            assert res_data["ok"] is True
            assert res_data["total"] == 1

            # 3. GET /api/postes (lê lista)
            conn.request("GET", "/api/postes")
            res = conn.getresponse()
            assert res.status == 200
            lista_postes = json.loads(res.read().decode("utf-8"))
            assert len(lista_postes) == 1
            assert lista_postes[0]["numero"] == "01"

            # 4. POST /api/enviar-cad
            conn.request("POST", "/api/enviar-cad", "{}")
            res = conn.getresponse()
            assert res.status == 200
            res_cad = json.loads(res.read().decode("utf-8"))
            assert res_cad["ok"] is True
            assert "mapa_postes_exec.lsp" in res_cad["script_lsp"]

            # 5. POST /api/exportar-kmz
            conn.request("POST", "/api/exportar-kmz", "{}")
            res = conn.getresponse()
            assert res.status == 200
            res_kmz = json.loads(res.read().decode("utf-8"))
            assert res_kmz["ok"] is True
            assert "postes_rede_campo.kmz" in res_kmz["caminho_kmz"]

            # 6. POST /api/converter-coordenadas (UTM -> Lat/Lon)
            conv_utm_payload = json.dumps({"tipo": "utm", "x": 585786.0, "y": 7454079.0, "fuso": 23})
            conn.request("POST", "/api/converter-coordenadas", conv_utm_payload, {"Content-Type": "application/json"})
            res = conn.getresponse()
            assert res.status == 200
            res_conv = json.loads(res.read().decode("utf-8"))
            assert res_conv["ok"] is True
            assert -24 < res_conv["lat"] < -22
            assert -45 < res_conv["lon"] < -43

            # 7. POST /api/converter-coordenadas (Lat/Lon -> UTM)
            conv_ll_payload = json.dumps({"tipo": "latlon", "lat": -22.9068, "lon": -43.1729, "fuso": 23})
            conn.request("POST", "/api/converter-coordenadas", conv_ll_payload, {"Content-Type": "application/json"})
            res = conn.getresponse()
            assert res.status == 200
            res_conv2 = json.loads(res.read().decode("utf-8"))
            assert res_conv2["ok"] is True
            assert 687000 < res_conv2["x_utm"] < 688000

            # 8. POST /api/converter-potencia (kW -> kVA com FP 0.92)
            conv_pot_payload = json.dumps({"kw": 15.0, "fp": 0.92})
            conn.request("POST", "/api/converter-potencia", conv_pot_payload, {"Content-Type": "application/json"})
            res = conn.getresponse()
            assert res.status == 200
            res_pot = json.loads(res.read().decode("utf-8"))
            assert res_pot["ok"] is True
            assert res_pot["kva"] == 16.30

            conn.close()

        finally:
            server.shutdown()
            server.server_close()


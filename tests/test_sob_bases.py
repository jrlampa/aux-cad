# -*- coding: utf-8 -*-
"""
test_sob_bases.py - Suíte de Testes para Mapeamento de Bases e Nomenclatura {BASE}_{SOB}_DESENHO.dwg.
Valida o padrão dinâmico de nomenclatura DWG substituindo BASE e SOB conforme
especificado pelas regras do repositório FABAO da Enel Rio.
"""

from pathlib import Path
import pytest

from sob.sob_bases import (
    normalizar_sigla_base,
    gerar_nome_dwg_sob,
    carregar_bases_fabao,
    TABELA_BASES_PADRAO,
    TABELA_CECO_BASE,
)
from sob.sob_core import derivar_caminhos_sob


class TestNormalizacaoBases:
    """Testa a conversão robusta de nomes de bases e CECOs para siglas de 2 letras."""

    def test_siglas_diretas(self):
        assert normalizar_sigla_base("PE") == "PE"
        assert normalizar_sigla_base("cf") == "CF"
        assert normalizar_sigla_base("AN") == "AN"
        assert normalizar_sigla_base("re") == "RE"
        assert normalizar_sigla_base("NI") == "NI"
        assert normalizar_sigla_base("MA") == "MA"
        assert normalizar_sigla_base("SG") == "SG"
        assert normalizar_sigla_base("TE") == "TE"

    def test_nomes_completos(self):
        assert normalizar_sigla_base("Petrópolis") == "PE"
        assert normalizar_sigla_base("PETROPOLIS") == "PE"
        assert normalizar_sigla_base("Cabo Frio") == "CF"
        assert normalizar_sigla_base("Angra dos Reis") == "AN"
        assert normalizar_sigla_base("Resende") == "RE"
        assert normalizar_sigla_base("Niterói") == "NI"
        assert normalizar_sigla_base("Magé") == "MA"
        assert normalizar_sigla_base("São Gonçalo") == "SG"
        assert normalizar_sigla_base("Teresópolis") == "TE"
        assert normalizar_sigla_base("Campos dos Goytacazes") == "CA"
        assert normalizar_sigla_base("Macaé") == "MC"
        assert normalizar_sigla_base("Itaperuna") == "IT"

    def test_ceco_numerico(self):
        assert normalizar_sigla_base("1670") == "PE"  # Petrópolis
        assert normalizar_sigla_base("1550") == "AN"  # Angra
        assert normalizar_sigla_base("1560") == "RE"  # Resende
        assert normalizar_sigla_base("1610") == "NI"  # Niterói
        assert normalizar_sigla_base("1650") == "MA"  # Magé
        assert normalizar_sigla_base("1660") == "SG"  # São Gonçalo
        assert normalizar_sigla_base("1680") == "TE"  # Teresópolis

    def test_padrao_fallback(self):
        # Quando nulo ou vazio, deve retornar 'PE' como padrão seguro
        assert normalizar_sigla_base(None) == "PE"
        assert normalizar_sigla_base("") == "PE"
        assert normalizar_sigla_base("   ") == "PE"


class TestGeradorNomeDwgSob:
    """Valida a formação canônica de {BASE}_{SOB}_DESENHO.dwg."""

    def test_padrao_obrigatorio_desenho(self):
        nome = gerar_nome_dwg_sob("PE", "A057350816")
        assert nome == "PE_A057350816_DESENHO.dwg"
        assert nome.endswith("_DESENHO.dwg")

    def test_limpeza_de_prefixo_sob_redundante(self):
        nome = gerar_nome_dwg_sob("PE", "SOB_A057350816")
        assert nome == "PE_A057350816_DESENHO.dwg"

    def test_outras_bases(self):
        assert gerar_nome_dwg_sob("CF", "A053749939") == "CF_A053749939_DESENHO.dwg"
        assert gerar_nome_dwg_sob("Angra", "A057350816") == "AN_A057350816_DESENHO.dwg"
        assert gerar_nome_dwg_sob("1670", "A057350816") == "PE_A057350816_DESENHO.dwg"

    def test_fallback_sem_base(self):
        assert gerar_nome_dwg_sob(None, "A057350816") == "PE_A057350816_DESENHO.dwg"


class TestDerivacaoCaminhosComBase:
    """Valida a integração da sigla da base com derivar_caminhos_sob."""

    def test_derivar_caminhos_com_base_customizada(self, tmp_path):
        dest = tmp_path / "DESTINO"
        dest.mkdir()

        caminhos = derivar_caminhos_sob("A057350816", dest, base="PE")
        assert caminhos["BASE_SIGLA"] == "PE"
        assert caminhos["NOME_BASE_DWG"] == "PE_A057350816_DESENHO.dwg"
        assert caminhos["BASE_DWG"].name == "PE_A057350816_DESENHO.dwg"

    def test_derivar_caminhos_com_cabo_frio(self, tmp_path):
        dest = tmp_path / "DESTINO"
        dest.mkdir()

        caminhos = derivar_caminhos_sob("A053749939", dest, base="CF")
        assert caminhos["BASE_SIGLA"] == "CF"
        assert caminhos["NOME_BASE_DWG"] == "CF_A053749939_DESENHO.dwg"
        assert caminhos["BASE_DWG"].name == "CF_A053749939_DESENHO.dwg"

    def test_derivar_caminhos_padrao_pe(self, tmp_path):
        dest = tmp_path / "DESTINO"
        dest.mkdir()

        caminhos = derivar_caminhos_sob("A057350816", dest)
        assert caminhos["BASE_SIGLA"] == "PE"
        assert caminhos["NOME_BASE_DWG"] == "PE_A057350816_DESENHO.dwg"


class TestCarregadorFabao:
    """Valida leitura e resiliência ao carregar dados do FABAO."""

    def test_carregar_bases_existentes_ou_fallback(self):
        mapa = carregar_bases_fabao()
        assert isinstance(mapa, dict)
        assert "PETRÓPOLIS" in mapa
        assert mapa["PETRÓPOLIS"] == "PE"
        assert "CABO FRIO" in mapa
        assert mapa["CABO FRIO"] == "CF"

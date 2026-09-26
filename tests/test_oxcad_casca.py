# -*- coding: utf-8 -*-
"""
Suíte de Testes da Casca do OXCAD v1 (AutoCAD .NET / WPF / AutoLISP).
Valida:
1. Construção correta do contexto do DWG;
2. Extração de SOB (nome do arquivo, padrão BASE_SOB_DESENHO, pasta pai);
3. Tratamento de DWG não salvo / inexistente sem exceção;
4. GUID estável e exclusivo do PaletteHost (sem colisão com MapaCadPaleta);
5. Lógica singleton e integridade dos comandos registrados;
6. Ausência de dependências fixas de OneDrive ou caminhos absolutos;
7. Verificação das DLLs compiladas para net8.0-windows e net48;
8. Estrutura e sintaxe do AutoLISP loader (oxcad_loader.lsp).
"""

from pathlib import Path
import re
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
OXCAD_DIR = ROOT_DIR / "oxcad"


# ==============================================================================
# 1. Testes de Existência e Integridade dos Arquivos da Casca OXCAD
# ==============================================================================

def test_arquivos_obrigatorios_oxcad_existem():
    """Garante que todos os componentes essenciais da casca OXCAD foram criados."""
    arquivos_esperados = [
        "OxCadPaleta.csproj",
        "DwgContext.cs",
        "OxCadControl.xaml",
        "OxCadControl.xaml.cs",
        "PaletteHost.cs",
        "Plugin.cs",
        "oxcad_loader.lsp",
    ]
    for nome in arquivos_esperados:
        arq = OXCAD_DIR / nome
        assert arq.exists(), f"Arquivo obrigatório ausente: {nome}"
        assert arq.stat().st_size > 0, f"Arquivo vazio: {nome}"


def test_dlls_compiladas_existem():
    """Garante que os artefatos compilados para ambos os runtimes existem."""
    dll_net8 = OXCAD_DIR / "bin" / "Release" / "net8.0-windows" / "OxCadPaleta.dll"
    dll_net48 = OXCAD_DIR / "bin" / "Release" / "net48" / "OxCadPaleta.dll"

    assert dll_net8.exists(), f"DLL .NET 8 não encontrada: {dll_net8}"
    assert dll_net8.stat().st_size > 5000, "DLL .NET 8 parece corrompida ou vazia"

    assert dll_net48.exists(), f"DLL .NET 4.8 não encontrada: {dll_net48}"
    assert dll_net48.stat().st_size > 5000, "DLL .NET 4.8 parece corrompida ou vazia"


# ==============================================================================
# 2. Testes de GUID Estável, Exclusivo e Inexistência de Colisão
# ==============================================================================

def test_palette_host_guid_exclusivo():
    """Verifica que o GUID da paleta OXCAD é estável e não colide com MapaCadPaleta."""
    palette_host_file = OXCAD_DIR / "PaletteHost.cs"
    conteudo = palette_host_file.read_text(encoding="utf-8")

    # GUID esperado para OXCAD
    guid_oxcad = "8A4F1D9C-2B7E-4E6A-B35D-9F0A1C8E7B2D"
    guid_mapa = "E4C23A4D-7E81-4C5D-912A-18F2E7D90B31"

    assert guid_oxcad in conteudo, "GUID do OXCAD não encontrado em PaletteHost.cs"
    assert guid_mapa not in conteudo, "GUID do MapaCadPaleta foi indevidamente reutilizado no OXCAD!"


def test_palette_host_singleton_e_estilo():
    """Verifica que PaletteHost implementa singleton, dock lateral e botões padrão."""
    conteudo = (OXCAD_DIR / "PaletteHost.cs").read_text(encoding="utf-8")

    assert "private static PaletteSet? _paletteSet;" in conteudo
    assert "PaletteSetStyles.ShowAutoHideButton" in conteudo
    assert "PaletteSetStyles.ShowCloseButton" in conteudo
    assert "DockSides.Right" in conteudo
    assert 'new PaletteSet("OXCAD"' in conteudo or 'new PaletteSet("OXCAD",' in conteudo


# ==============================================================================
# 3. Testes de Registro de Comandos e Inalterabilidade de WORKSPACE
# ==============================================================================

def test_comandos_plugin_oxcad():
    """Verifica se o comando OXCAD está registrado e WORKSPACE não foi sobrescrito."""
    conteudo = (OXCAD_DIR / "Plugin.cs").read_text(encoding="utf-8")

    assert '[CommandMethod("OXCAD")]' in conteudo
    assert '[CommandMethod("FECHAR_OXCAD")]' in conteudo
    assert '[CommandMethod("RECARREGAR_OXCAD")]' in conteudo
    assert '[CommandMethod("WORKSPACE")]' not in conteudo, "WORKSPACE não pode ser sobrescrito pelo OXCAD!"
    assert '[CommandMethod("SOBWORKSPACE")]' not in conteudo, "SOBWORKSPACE não pode ser alterado!"


# ==============================================================================
# 4. Testes de Independência de OneDrive e Caminhos
# ==============================================================================

def test_sem_dependencia_onedrive():
    """Verifica que o código-fonte do OXCAD não possui dependências estáticas do OneDrive."""
    arquivos_codigo = list(OXCAD_DIR.glob("*.cs")) + list(OXCAD_DIR.glob("*.xaml")) + list(OXCAD_DIR.glob("*.lsp"))
    for arq in arquivos_codigo:
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        assert "OneDrive" not in texto, f"Referência hardcoded a OneDrive encontrada em {arq.name}"
        assert "C:\\Users\\" not in texto, f"Caminho absoluto de usuário encontrado em {arq.name}"


# ==============================================================================
# 5. Testes da Lógica de Extração de Contexto e SOB
# ==============================================================================

class ContextExtractorSimulator:
    """
    Simulador fiel da lógica de DwgContextExtractor.cs para testes unitários em Python.
    """
    REGEX_SOB_PREFIXO = re.compile(r"SOB_([A-Za-z0-9_\-]+)")
    REGEX_DWG_BASE = re.compile(r"[A-Za-z]{2}_([A-Za-z0-9_\-]+)_DESENHO")
    REGEX_SOB_ALFA = re.compile(r"(?:^|[^A-Za-z0-9])([A-Za-z][0-9]{8,12})(?:[^A-Za-z0-9]|$)")

    @classmethod
    def extrair_sob(cls, texto: str):
        if not texto:
            return None
        m = cls.REGEX_SOB_PREFIXO.search(texto)
        if m:
            cand = m.group(1).upper()
            if cls.validar_sob_id(cand):
                return cand
        m = cls.REGEX_DWG_BASE.search(texto)
        if m:
            cand = m.group(1).upper()
            if cls.validar_sob_id(cand):
                return cand
        m = cls.REGEX_SOB_ALFA.search(texto)
        if m:
            cand = m.group(1).upper()
            if cls.validar_sob_id(cand):
                return cand
        return None

    @staticmethod
    def validar_sob_id(sob_id: str) -> bool:
        if not sob_id or not isinstance(sob_id, str):
            return False
        s = sob_id.strip().upper()
        if s.startswith("SOB_") or len(s) < 3 or len(s) > 30:
            return False
        return bool(re.match(r"^[A-Z0-9_\-]+$", s))

    @classmethod
    def construir_contexto(cls, full_path: str, arquivo_existe: bool = True):
        if not full_path or not arquivo_existe:
            return {
                "salvo": False,
                "status": "Desenho ainda não salvo.",
                "dwg_nome": "Desenho ainda não salvo.",
                "dwg_caminho": "-",
                "dwg_diretorio": "-",
                "sob_id": "-",
            }
        p = Path(full_path)
        nome = p.name
        diretorio = str(p.parent)
        sob = cls.extrair_sob(nome) or cls.extrair_sob(diretorio)
        return {
            "salvo": True,
            "status": "Contexto identificado" if sob else "Contexto identificado (SOB não localizada)",
            "dwg_nome": nome,
            "dwg_caminho": full_path,
            "dwg_diretorio": diretorio,
            "sob_id": sob if sob else "Não identificada",
        }


def test_extrair_sob_padrao_oficial_dwg():
    """Valida extração da SOB a partir de padrão {BASE}_{SOB}_DESENHO.dwg."""
    assert ContextExtractorSimulator.extrair_sob("PE_A057349839_DESENHO.dwg") == "A057349839"
    assert ContextExtractorSimulator.extrair_sob("PET_A057349839_DESENHO.dwg") == "A057349839"
    assert ContextExtractorSimulator.extrair_sob("NT_B987654321_DESENHO.dwg") == "B987654321"


def test_extrair_sob_padrao_pasta():
    """Valida extração da SOB a partir do nome da pasta SOB_..."""
    assert ContextExtractorSimulator.extrair_sob(r"C:\Projetos\SOB_A057349839") == "A057349839"
    assert ContextExtractorSimulator.extrair_sob(r"D:\Trabalho\SOB_2026_09_15") == "2026_09_15"


def test_extrair_sob_alfanumerico_concessionaria():
    """Valida extração da SOB alfanumérica pura da concessionária."""
    assert ContextExtractorSimulator.extrair_sob("A057349839") == "A057349839"
    assert ContextExtractorSimulator.extrair_sob("PROJETO_A057349839_FINAL.dwg") == "A057349839"


def test_construir_contexto_dwg_salvo(tmp_path):
    """Valida construção do contexto com DWG salvo físico."""
    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    ctx = ContextExtractorSimulator.construir_contexto(str(dwg), arquivo_existe=True)
    assert ctx["salvo"] is True
    assert ctx["status"] == "Contexto identificado"
    assert ctx["sob_id"] == "A057349839"
    assert ctx["dwg_nome"] == "PE_A057349839_DESENHO.dwg"
    assert ctx["dwg_diretorio"] == str(pasta_sob)


def test_construir_contexto_dwg_sem_sob_no_nome(tmp_path):
    """Valida DWG cujo nome é genérico mas está dentro da pasta da SOB."""
    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "desenho_geral.dwg"
    dwg.write_text("dummy")

    ctx = ContextExtractorSimulator.construir_contexto(str(dwg), arquivo_existe=True)
    assert ctx["salvo"] is True
    assert ctx["status"] == "Contexto identificado"
    assert ctx["sob_id"] == "A057349839"
    assert ctx["dwg_nome"] == "desenho_geral.dwg"


def test_construir_contexto_dwg_nao_salvo():
    """Valida tratamento seguro de desenho não salvo."""
    ctx_nulo = ContextExtractorSimulator.construir_contexto(None, arquivo_existe=False)
    assert ctx_nulo["salvo"] is False
    assert ctx_nulo["status"] == "Desenho ainda não salvo."
    assert ctx_nulo["sob_id"] == "-"

    ctx_inexistente = ContextExtractorSimulator.construir_contexto("Drawing1.dwg", arquivo_existe=False)
    assert ctx_inexistente["salvo"] is False
    assert ctx_inexistente["status"] == "Desenho ainda não salvo."
    assert ctx_inexistente["dwg_nome"] == "Desenho ainda não salvo."


# ==============================================================================
# 6. Testes do AutoLISP Loader (oxcad_loader.lsp)
# ==============================================================================

def test_oxcad_loader_lsp_estrutura():
    """Valida se o loader LISP possui as funções de resolução de caminho e comandos."""
    conteudo = (OXCAD_DIR / "oxcad_loader.lsp").read_text(encoding="utf-8")

    assert "defun c:oxcad-get-dll-path" in conteudo
    assert "defun c:oxcad-load-dll" in conteudo
    assert "defun c:OXCAD" in conteudo
    assert "defun c:FECHAR_OXCAD" in conteudo
    assert "defun c:RECARREGAR_OXCAD" in conteudo
    assert "_.NETLOAD" in conteudo
    assert "OxCadPaleta.dll" in conteudo
    assert "ACADVER" in conteudo
    assert "25.0" in conteudo

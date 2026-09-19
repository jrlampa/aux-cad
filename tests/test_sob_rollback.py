# -*- coding: utf-8 -*-
"""
Testes Unitários do Módulo de Rollback Seguro da Fase B (Seção 18).
Valida o desfazimento atômico e seguro exclusivamente dos recursos criados,
proteção contra destruição de dados preexistentes e proteção absoluta de BASE_TEMPLATE.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from sob.sob_rollback import RollbackContext, RecursoRastreado
from sob.sob_manager import SobOrchestrator
from sob.sob_core import (
    criar_estrutura_sob,
    copiar_arquivo_base,
)
from sob.sob_sharepoint import SobDownloadIncompleteError


@pytest.fixture
def ambiente_teste(tmp_path):
    """
    Cria um ambiente temporário limpo com template de teste.
    """
    dest_root = tmp_path / "Projetos"
    dest_root.mkdir()
    template = tmp_path / "prancha.dwg"
    template.write_bytes(b"AC1032" + b"\x00" * 200)

    sob_id = "A057349839"
    sob_name = f"SOB_{sob_id}"
    sob_root = dest_root / sob_name
    croqui_dir = sob_root / "CROQUI"
    base_dwg = sob_root / "BASE_SOB_DESENHO.dwg"

    return {
        "dest_root": dest_root,
        "template": template,
        "sob_id": sob_id,
        "sob_name": sob_name,
        "sob_root": sob_root,
        "croqui_dir": croqui_dir,
        "base_dwg": base_dwg,
    }


def test_rollback_nao_necessario_sem_alteracoes(ambiente_teste):
    """
    Seção 18.13: Se a falha ocorrer antes de qualquer alteração física,
    o estado deverá ser ROLLBACK_NÃO_NECESSÁRIO.
    """
    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=ambiente_teste["dest_root"],
        sob_root=ambiente_teste["sob_root"],
        croqui_dir=ambiente_teste["croqui_dir"],
        base_dwg=ambiente_teste["base_dwg"],
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_A12",
        motivo_falha="Falha de autenticação na Fase A",
    )

    assert relatorio["resultado_do_rollback"] == "ROLLBACK_NÃO_NECESSÁRIO"
    assert relatorio["rollback_iniciado"] is False
    assert len(relatorio["recursos_removidos"]) == 0
    assert ambiente_teste["template"].exists()


def test_rollback_concluido_apos_criacao_pastas(ambiente_teste):
    """
    Seção 18.4 & 18.5: Se SOB_ROOT e CROQUI_DIR foram criados e a falha ocorrer em seguida,
    ambos devem ser removidos em ordem inversa e resultar em ROLLBACK_CONCLUÍDO.
    """
    dest_root = ambiente_teste["dest_root"]
    sob_name = ambiente_teste["sob_name"]

    sob_root, croqui_dir = criar_estrutura_sob(dest_root, sob_name)
    assert sob_root.exists()
    assert croqui_dir.exists()

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=dest_root,
        sob_root=sob_root,
        croqui_dir=croqui_dir,
        base_dwg=ambiente_teste["base_dwg"],
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()
    ctx.registrar_criacao("SOB_ROOT", sob_root, tipo="dir")
    ctx.registrar_criacao("CROQUI_DIR", croqui_dir, tipo="dir")

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_B03",
        motivo_falha="Falha no início do download",
    )

    assert relatorio["resultado_do_rollback"] == "ROLLBACK_CONCLUÍDO"
    assert not croqui_dir.exists()
    assert not sob_root.exists()
    assert str(croqui_dir) in relatorio["recursos_removidos"]
    assert str(sob_root) in relatorio["recursos_removidos"]
    assert ambiente_teste["dest_root"].exists()


def test_rollback_concluido_download_parcial(ambiente_teste):
    """
    Seção 18.5 & 18.9: Arquivos baixados devem ser rastreados e removidos individualmente.
    """
    dest_root = ambiente_teste["dest_root"]
    sob_name = ambiente_teste["sob_name"]
    sob_root, croqui_dir = criar_estrutura_sob(dest_root, sob_name)

    # Simula arquivos baixados durante a execução
    arq1 = croqui_dir / "croqui1.dwg"
    arq1.write_bytes(b"conteudo 1")
    arq2 = croqui_dir / "documento.pdf"
    arq2.write_bytes(b"conteudo 2")

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=dest_root,
        sob_root=sob_root,
        croqui_dir=croqui_dir,
        base_dwg=ambiente_teste["base_dwg"],
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()
    ctx.registrar_criacao("SOB_ROOT", sob_root, tipo="dir")
    ctx.registrar_criacao("CROQUI_DIR", croqui_dir, tipo="dir")
    ctx.registrar_download_arquivo(arq1)
    ctx.registrar_download_arquivo(arq2)

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_B04",
        motivo_falha="Download corrompido ou incompleto",
    )

    assert relatorio["resultado_do_rollback"] == "ROLLBACK_CONCLUÍDO"
    assert not arq1.exists()
    assert not arq2.exists()
    assert not croqui_dir.exists()
    assert not sob_root.exists()


def test_protecao_conteudo_preexistente(ambiente_teste):
    """
    Seção 18.6: Se CROQUI_DIR continha um arquivo preexistente, ele NUNCA deve ser removido,
    e as pastas pai não devem ser excluídas, gerando ROLLBACK_PARCIAL.
    """
    dest_root = ambiente_teste["dest_root"]
    sob_name = ambiente_teste["sob_name"]
    sob_root, croqui_dir = criar_estrutura_sob(dest_root, sob_name)

    # Arquivo preexistente
    arq_antigo = croqui_dir / "referencia_preexistente.dwg"
    arq_antigo.write_bytes(b"dados que o usuario ja tinha colocado")

    # Arquivo novo baixado pela execução
    arq_novo = croqui_dir / "novo_croqui.dwg"
    arq_novo.write_bytes(b"dados novos")

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=dest_root,
        sob_root=sob_root,
        croqui_dir=croqui_dir,
        base_dwg=ambiente_teste["base_dwg"],
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()
    ctx.registrar_criacao("SOB_ROOT", sob_root, tipo="dir")
    ctx.registrar_criacao("CROQUI_DIR", croqui_dir, tipo="dir")
    # Apenas o arquivo novo foi registrado como criado
    ctx.registrar_download_arquivo(arq_novo)

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_B04",
        motivo_falha="Erro durante download",
    )

    # O arquivo novo foi removido
    assert not arq_novo.exists()
    # O arquivo preexistente FOI PRESERVADO
    assert arq_antigo.exists()
    # As pastas foram mantidas por conter conteúdo preservado
    assert croqui_dir.exists()
    assert sob_root.exists()
    assert relatorio["resultado_do_rollback"] == "ROLLBACK_CONCLUÍDO"
    assert str(croqui_dir) in relatorio["recursos_preservados"]
    assert str(sob_root) in relatorio["recursos_preservados"]


def test_protecao_absoluta_base_template(ambiente_teste):
    """
    Seção 18.8: O arquivo BASE_TEMPLATE tem proteção absoluta e nunca pode ser excluído.
    """
    template = ambiente_teste["template"]
    hash_original = template.read_bytes()

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=ambiente_teste["dest_root"],
        sob_root=ambiente_teste["sob_root"],
        croqui_dir=ambiente_teste["croqui_dir"],
        base_dwg=ambiente_teste["base_dwg"],
        base_template=template,
    )
    ctx.inicializar_fase_b()

    # Tenta registrar maliciosamente BASE_TEMPLATE como criado
    ctx.registrar_criacao("BASE_DWG", template, tipo="file")

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_B06",
        motivo_falha="Falha crítica simulada",
    )

    # Template continua intacto
    assert template.exists()
    assert template.read_bytes() == hash_original
    assert str(template) in relatorio["recursos_preservados"]


def test_ordem_inversa_execucao(ambiente_teste):
    """
    Seção 18.10: Valida a sequência de desfazimento em ordem inversa:
    BASE_DWG -> arquivos baixados -> CROQUI_DIR -> SOB_ROOT.
    """
    dest_root = ambiente_teste["dest_root"]
    sob_name = ambiente_teste["sob_name"]
    sob_root, croqui_dir = criar_estrutura_sob(dest_root, sob_name)

    arq_baixado = croqui_dir / "croqui.dwg"
    arq_baixado.write_bytes(b"dados")

    base_dwg = copiar_arquivo_base(
        ambiente_teste["template"],
        sob_root,
        nome_destino="BASE_SOB_DESENHO.dwg",
    )

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=dest_root,
        sob_root=sob_root,
        croqui_dir=croqui_dir,
        base_dwg=base_dwg,
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()
    ctx.registrar_criacao("SOB_ROOT", sob_root, tipo="dir")
    ctx.registrar_criacao("CROQUI_DIR", croqui_dir, tipo="dir")
    ctx.registrar_download_arquivo(arq_baixado)
    ctx.registrar_criacao("BASE_DWG", base_dwg, tipo="file")

    ordem_remocoes = []
    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        ordem_remocoes.append(self.name)
        original_unlink(self, *args, **kwargs)

    original_rmdir = Path.rmdir

    def mock_rmdir(self, *args, **kwargs):
        ordem_remocoes.append(self.name)
        original_rmdir(self, *args, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(Path, "unlink", mock_unlink), mock.patch.object(Path, "rmdir", mock_rmdir):
        relatorio = ctx.executar_rollback(
            etapa_falha="ETAPA_B10",
            motivo_falha="Falha ao validar abertura no AutoCAD",
        )

    assert relatorio["resultado_do_rollback"] == "ROLLBACK_CONCLUÍDO"
    # Ordem esperada: BASE_SOB_DESENHO.dwg -> croqui.dwg -> CROQUI -> SOB_A057349839
    assert ordem_remocoes == ["BASE_SOB_DESENHO.dwg", "croqui.dwg", "CROQUI", "SOB_A057349839"]


def test_recurso_remanescente_em_uso(ambiente_teste):
    """
    Seção 18.11 & 18.12: Se o BASE_DWG estiver em uso ou não puder ser fechado,
    ele deve ser registrado em recursos_remanescentes com orientações claras.
    """
    dest_root = ambiente_teste["dest_root"]
    sob_name = ambiente_teste["sob_name"]
    sob_root, croqui_dir = criar_estrutura_sob(dest_root, sob_name)

    base_dwg = copiar_arquivo_base(
        ambiente_teste["template"],
        sob_root,
        nome_destino="BASE_SOB_DESENHO.dwg",
    )

    ctx = RollbackContext(
        sob_id=ambiente_teste["sob_id"],
        destination_root=dest_root,
        sob_root=sob_root,
        croqui_dir=croqui_dir,
        base_dwg=base_dwg,
        base_template=ambiente_teste["template"],
    )
    ctx.inicializar_fase_b()
    ctx.registrar_criacao("SOB_ROOT", sob_root, tipo="dir")
    ctx.registrar_criacao("CROQUI_DIR", croqui_dir, tipo="dir")
    ctx.registrar_criacao("BASE_DWG", base_dwg, tipo="file")
    ctx.marcar_dwg_aberto()

    # Callback simula falha ao tentar fechar no AutoCAD
    def callback_fechador(caminho):
        return False

    relatorio = ctx.executar_rollback(
        etapa_falha="ETAPA_B10",
        motivo_falha="Desenho travado pelo AutoCAD",
        fechador_cad_callback=callback_fechador,
    )

    assert relatorio["resultado_do_rollback"] == "ROLLBACK_PARCIAL"
    assert len(relatorio["recursos_remanescentes"]) > 0
    rem = relatorio["recursos_remanescentes"][0]
    assert rem["caminho"] == str(base_dwg)
    assert "em uso" in rem["motivo"].lower()
    assert "fechar" in rem["acao_necessaria"].lower()
    # Como BASE_DWG não foi removido, SOB_ROOT não deve ter sido removido
    assert sob_root.exists()


def test_orchestrator_rollback_integrado_falha_download(ambiente_teste):
    """
    Integração completa: SobOrchestrator dispara rollback automático ao falhar na Fase B.
    """
    dest_root = ambiente_teste["dest_root"]
    template = ambiente_teste["template"]

    # Mock do cliente do SharePoint que falha na validação de download
    mock_client = MagicMock()
    mock_client.autenticar.return_value = True
    mock_client.localizar_pasta_sob.return_value = {"nome": "SOB_A057349839", "elemento": MagicMock()}
    mock_client.validar_conteudo_disponivel.return_value = True

    # Simula download de arquivo mas validação falha
    def mock_baixar(pasta_info, destino):
        arq = destino / "teste.dwg"
        arq.write_bytes(b"conteudo")
        return [arq]

    mock_client.baixar_croqui.side_effect = mock_baixar
    mock_client.validar_download.side_effect = SobDownloadIncompleteError("[FALHA] Download parcial corrompido.")

    orc = SobOrchestrator(
        origem_base=template,
        sharepoint_client=mock_client,
    )

    resultado = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=True,
        abrir_cad=False,
    )

    assert resultado["status"] == "BLOQUEADO"
    assert resultado["sucesso"] is False
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"
    assert resultado["rollback_info"] is not None
    # Verifica que as pastas temporárias foram limpas
    sob_root = dest_root / "SOB_A057349839"
    assert not sob_root.exists()
    assert template.exists()

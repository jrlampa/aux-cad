# -*- coding: utf-8 -*-
"""
Testes Unitários de Idempotência e Repetição Segura da Operação SOB (Seção 19).
Cobre os cenários IDEMP-01 a IDEMP-07 definidos na Seção 19.19.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from sob.sob_idempotencia import (
    gerar_run_id,
    gravar_manifesto_execucao,
    ler_manifesto_execucao,
    classificar_sob_root,
    verificar_arquivo_download_idempotente,
)
from sob.sob_manager import SobOrchestrator
from sob.sob_core import (
    criar_estrutura_sob,
    copiar_arquivo_base,
    calcular_hash_arquivo,
)
from sob.sob_sharepoint import SobDownloadIncompleteError


@pytest.fixture
def ambiente_idemp(tmp_path):
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


def test_idemp_01_executar_duas_vezes_sob_nova(ambiente_idemp):
    """
    IDEMP-01: Primeira execução conclui com sucesso.
    Segunda execução bloqueia com [INFO] A SOB já possui uma execução concluída neste destino.
    Sem recriar, sem sobrescrever e sem duplicar pastas (Seção 19.7 e 19.19).
    """
    dest_root = ambiente_idemp["dest_root"]
    template = ambiente_idemp["template"]

    orc = SobOrchestrator(origem_base=template)

    # 1ª Execução
    res1 = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=False,
        abrir_cad=False,
    )
    assert res1["sucesso"] is True
    assert res1["status"] == "CONCLUÍDO"
    dwg_path = Path(res1["BASE_DWG"])
    assert dwg_path.exists()
    hash_dwg_original = calcular_hash_arquivo(dwg_path)

    # 2ª Execução idêntica
    res2 = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=False,
        abrir_cad=False,
    )

    # Deve bloquear com status de informação segura
    assert res2["status"] == "BLOQUEADO"
    assert "já possui uma execução concluída" in res2["mensagem"]
    assert res2["etapa"] == "SOB_CONCLUIDA_EXISTENTE"
    # O arquivo original NÃO pode ter sido alterado
    assert dwg_path.exists()
    assert calcular_hash_arquivo(dwg_path) == hash_dwg_original
    # Não pode ter criado pastas secundárias como SOB_A057349839_1
    assert not (dest_root / "SOB_A057349839_1").exists()


def test_idemp_02_falha_seguida_de_rollback_completo(ambiente_idemp):
    """
    IDEMP-02: Execução que falha e executa ROLLBACK_CONCLUÍDO remove a pasta da SOB.
    A execução subsequente é tratada como nova execução limpa (Seção 19.8).
    """
    dest_root = ambiente_idemp["dest_root"]
    template = ambiente_idemp["template"]

    mock_client = MagicMock()
    mock_client.autenticar.return_value = True
    mock_client.localizar_pasta_sob.return_value = {"nome": "SOB_A057349839", "elemento": MagicMock()}
    mock_client.validar_conteudo_disponivel.return_value = True
    # Download falha na primeira tentativa
    mock_client.baixar_croqui.return_value = []
    mock_client.validar_download.side_effect = SobDownloadIncompleteError("[FALHA] Download corrompido.")

    orc = SobOrchestrator(origem_base=template, sharepoint_client=mock_client)

    # 1ª Execução falha e faz rollback completo
    res1 = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=True,
        abrir_cad=False,
    )
    assert res1["status"] == "BLOQUEADO"
    assert res1["rollback"] == "ROLLBACK_CONCLUÍDO"
    sob_root = dest_root / "SOB_A057349839"
    assert not sob_root.exists()

    # 2ª Execução agora com download bem-sucedido
    mock_client.validar_download.side_effect = None
    mock_client.validar_download.return_value = True

    res2 = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=True,
        abrir_cad=False,
    )
    assert res2["status"] == "CONCLUÍDO"
    assert sob_root.exists()


def test_idemp_03_falha_seguida_de_rollback_parcial(ambiente_idemp):
    """
    IDEMP-03: Se a execução anterior terminou em ROLLBACK_PARCIAL e a pasta restou,
    a nova execução deve ser bloqueada como incompleta (Seção 19.9).
    """
    dest_root = ambiente_idemp["dest_root"]
    template = ambiente_idemp["template"]
    sob_name = ambiente_idemp["sob_name"]
    sob_root = dest_root / sob_name
    sob_root.mkdir()

    # Simula estado de falha anterior registrado com ROLLBACK_PARCIAL
    gravar_manifesto_execucao(
        sob_root,
        {
            "run_id": gerar_run_id(),
            "sob_id": "A057349839",
            "status": "BLOQUEADO",
            "rollback": "ROLLBACK_PARCIAL",
            "motivo_falha": "Arquivo em uso",
        },
    )

    orc = SobOrchestrator(origem_base=template)

    res = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=False,
        abrir_cad=False,
    )

    assert res["status"] == "BLOQUEADO"
    assert "execução anterior em estado incompleto" in res["mensagem"]


def test_idemp_04_base_dwg_existente_sem_validacao(ambiente_idemp):
    """
    IDEMP-04: Se SOB_ROOT já existe com arquivo ou conteúdo desconhecido sem validação,
    o sistema bloqueia a criação e impede sobrescrita (Seção 19.12).
    """
    dest_root = ambiente_idemp["dest_root"]
    template = ambiente_idemp["template"]
    sob_root = dest_root / ambiente_idemp["sob_name"]
    sob_root.mkdir()
    arquivo_desconhecido = sob_root / "BASE_SOB_DESENHO.dwg"
    arquivo_desconhecido.write_bytes(b"conteudo estranho sem manifesto")

    orc = SobOrchestrator(origem_base=template)

    res = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=False,
        abrir_cad=False,
    )

    assert res["status"] == "BLOQUEADO"
    assert "A pasta da SOB já existe" in res["mensagem"]
    # Garante que não sobrescreveu o arquivo desconhecido
    assert arquivo_desconhecido.read_bytes() == b"conteudo estranho sem manifesto"


def test_idemp_05_download_existente_identico(tmp_path):
    """
    IDEMP-05: Se um arquivo de download já existe localmente e é idêntico,
    ele é reconhecido e reutilizado sem sobrescrever (Seção 19.11).
    """
    pasta = tmp_path / "CROQUI"
    pasta.mkdir()
    arq = pasta / "desenho.dwg"
    conteudo = b"AC1032conteudoidentico"
    arq.write_bytes(conteudo)

    import hashlib
    hash_esperado = hashlib.sha256(conteudo).hexdigest()

    resultado = verificar_arquivo_download_idempotente(
        arquivo_local=arq,
        tamanho_esperado=len(conteudo),
        hash_esperado=hash_esperado,
    )

    assert resultado == "IDENTICO"


def test_idemp_06_download_existente_divergente(tmp_path):
    """
    IDEMP-06: Se um arquivo já existe localmente mas com conteúdo divergente,
    o conflito é detectado para impedir sobrescrita acidental (Seção 19.11).
    """
    pasta = tmp_path / "CROQUI"
    pasta.mkdir()
    arq = pasta / "desenho.dwg"
    arq.write_bytes(b"conteudo local diferente")

    resultado = verificar_arquivo_download_idempotente(
        arquivo_local=arq,
        tamanho_esperado=9999,  # tamanho diferente
    )

    assert resultado == "DIVERGENTE"


def test_idemp_07_encerramento_inesperado(ambiente_idemp):
    """
    IDEMP-07: Simula encerramento inesperado durante a Fase B (ex: manifesto em EM_EXECUCAO).
    A repetição subsequente identifica o estado incompleto e bloqueia (Seção 19.10).
    """
    dest_root = ambiente_idemp["dest_root"]
    template = ambiente_idemp["template"]
    sob_root = dest_root / ambiente_idemp["sob_name"]
    sob_root.mkdir()

    # Manifesto gravado mas nunca finalizado como CONCLUÍDO
    gravar_manifesto_execucao(
        sob_root,
        {
            "run_id": gerar_run_id(),
            "sob_id": "A057349839",
            "status": "EM_EXECUCAO",
            "etapa": "DOWNLOAD_VALIDADO",
        },
    )

    orc = SobOrchestrator(origem_base=template)

    res = orc.executar(
        sob_raw="A057349839",
        destino_dir=dest_root,
        baixar_croqui_sp=False,
        abrir_cad=False,
    )

    assert res["status"] == "BLOQUEADO"
    assert "execução anterior em estado incompleto" in res["mensagem"]

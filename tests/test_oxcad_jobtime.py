# -*- coding: utf-8 -*-
"""
Suíte de testes para OXCAD 0.5.1 — Validação Operacional e Hardening do Controle de Tempo.
Cobre exaustivamente:
- Caso A: Pausa normal e congelamento durante a pausa
- Caso B: Retomada e acúmulo estrito dos intervalos produtivos
- Caso C: Conclusão e congelamento definitivo
- Caso D: Encerramento do AutoCAD / Queda de processo sem acúmulo de tempo fantasma (Requisito Crítico)
- Caso E: Robustez contra corrupção e arquivos inválidos
- Caso F: Duplo clique, concorrência e idempotência estrita de todas as ações
- Integração CLI com passagem de --acad-pid
- Integração ponta a ponta com o ciclo de vida do comando SOB (SobOrchestrator)
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from workspace.workspace_time import (
    TimeState,
    OxCadTimeEntry,
    formatar_segundos_para_hhmmss,
    formatar_iso_para_exibicao_local,
    obter_caminho_time_json,
    carregar_tempo_projeto,
    salvar_tempo_projeto,
    inicializar_tempo_projeto,
    iniciar_ou_retomar_tempo,
    pausar_tempo,
    concluir_tempo,
    reabrir_tempo,
    tratar_interrupcao_se_necessario,
    atualizar_heartbeat_tempo,
    processo_esta_ativo,
)
from workspace.workspace_context_cli import (
    extrair_contexto_operacional,
    executar_acao_operacional,
)
from sob_manager import SobOrchestrator
from sob_sharepoint import SharePointClient


def test_formatacao_segundos_para_hhmmss():
    assert formatar_segundos_para_hhmmss(0) == "00:00:00"
    assert formatar_segundos_para_hhmmss(59) == "00:00:59"
    assert formatar_segundos_para_hhmmss(60) == "00:01:00"
    assert formatar_segundos_para_hhmmss(3665) == "01:01:05"
    assert formatar_segundos_para_hhmmss(7200.4) == "02:00:00"
    assert formatar_segundos_para_hhmmss(-10) == "00:00:00"


def test_formatacao_iso_local():
    assert formatar_iso_para_exibicao_local(None) == "-"
    assert formatar_iso_para_exibicao_local("invalido") == "-"
    val = formatar_iso_para_exibicao_local("2026-09-26T14:32:00Z")
    assert "/" in val and ":" in val


def test_criacao_inicial_e_caminho(tmp_path: Path):
    sob_dir = tmp_path / "SOB_TESTE"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("dummy", encoding="utf-8")

    caminho = obter_caminho_time_json(sob_dir)
    assert caminho == sob_dir / ".oxcad" / "time.json"
    assert not caminho.exists()

    entry = inicializar_tempo_projeto(sob_dir, dwg_path=str(dwg))
    assert entry.estado == TimeState.NAO_INICIADO
    assert entry.sob_id == "SOB_TESTE"
    assert entry.dwg_path == str(dwg)
    assert entry.tempo_acumulado_segundos == 0.0
    assert caminho.exists()

    # Re-inicializar sem sobrescrever
    entry2 = inicializar_tempo_projeto(sob_dir, dwg_path=str(dwg), sobrescrever=False)
    assert entry2.sob_id == entry.sob_id


# =========================================================================
# BATERIA DE TESTES RIGOROSOS — CASOS A, B, C, D, E, F (Seção 6 do Prompt)
# =========================================================================

def test_caso_a_pausa_normal(tmp_path: Path):
    """
    Caso A — Pausa normal:
    Iniciar -> passagem de tempo -> Pausar -> passagem de tempo -> consultar.
    O período pausado não pode entrar no acumulado.
    """
    sob_dir = tmp_path / "SOB_CASO_A"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)  # 30m trabalhados
    t2 = t1 + timedelta(hours=2)    # 2h pausado

    # Iniciar às 10:00
    entry = iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())
    assert entry.estado == TimeState.EM_EXECUCAO

    # Pausar às 10:30 (trabalhou 30 min = 1800s)
    entry_pausado = pausar_tempo(sob_dir, timestamp_iso=t1.isoformat())
    assert entry_pausado.estado == TimeState.PAUSADO
    assert entry_pausado.tempo_acumulado_segundos == 1800.0

    # Consultar 2 horas depois (12:30): acumulado DEVE permanecer rigorosamente 1800s
    entry_consulta = carregar_tempo_projeto(sob_dir)
    assert entry_consulta.estado == TimeState.PAUSADO
    assert entry_consulta.calcular_tempo_total_segundos(agora_dt=t2) == 1800.0
    assert entry_consulta.obter_tempo_formatado(agora_dt=t2) == "00:30:00"


def test_caso_b_retomada(tmp_path: Path):
    """
    Caso B — Retomada:
    Iniciar -> Pausar -> passagem de tempo -> Retomar -> passagem de tempo.
    Somente os intervalos de execução entram no acumulado.
    """
    sob_dir = tmp_path / "SOB_CASO_B"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=20)  # Pausa aos 20m
    t2 = t1 + timedelta(minutes=40)  # Retoma 40m depois
    t3 = t2 + timedelta(minutes=25)  # Trabalha mais 25m e consulta

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())
    pausar_tempo(sob_dir, timestamp_iso=t1.isoformat())  # 20 min acumulados
    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t2.isoformat())

    entry = carregar_tempo_projeto(sob_dir)
    # Total esperado: 20m + 25m = 45m (2700s). Os 40m de pausa NÃO entram!
    total_seg = entry.calcular_tempo_total_segundos(agora_dt=t3)
    assert total_seg == 2700.0
    assert entry.obter_tempo_formatado(agora_dt=t3) == "00:45:00"


def test_caso_c_conclusao_congelada(tmp_path: Path):
    """
    Caso C — Conclusão:
    Depois de Concluir, o tempo deve ficar congelado.
    Consultas em qualquer data futura não podem acrescentar tempo.
    """
    sob_dir = tmp_path / "SOB_CASO_C"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=47, seconds=23)  # 00:47:23
    t_futuro = t1 + timedelta(days=10)           # 10 dias depois

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())
    entry_fim = concluir_tempo(sob_dir, timestamp_iso=t1.isoformat())

    assert entry_fim.estado == TimeState.CONCLUIDO
    assert entry_fim.tempo_acumulado_segundos == pytest.approx(2843.0, 0.1)
    assert entry_fim.obter_tempo_formatado() == "00:47:23"

    # Consultar 10 dias depois: permanece rigorosamente congelado
    assert entry_fim.calcular_tempo_total_segundos(agora_dt=t_futuro) == pytest.approx(2843.0, 0.1)
    assert entry_fim.obter_tempo_formatado(agora_dt=t_futuro) == "00:47:23"


def test_caso_d_encerramento_autocad_e_sessao_interrompida(tmp_path: Path):
    """
    Caso D — Encerramento do AutoCAD (Requisito Crítico das Seções 3, 4 e 5):
    14:00 Iniciar com PID 1000
    14:45 AutoCAD fechado (última atividade em 14:45)
    16:30 AutoCAD reaberto com PID 2000
    O sistema NÃO pode registrar 02:30:00!
    Deve detectar 'Sessão interrompida' e registrar exatamente 00:45:00.
    """
    sob_dir = tmp_path / "SOB_CASO_D"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("dwg", encoding="utf-8")

    t_inicio = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    t_fechou = datetime(2026, 9, 26, 14, 45, 0, tzinfo=timezone.utc)
    t_reabriu = datetime(2026, 9, 26, 16, 30, 0, tzinfo=timezone.utc)

    # 1. Inicia sessão no AutoCAD 1 (PID 1000)
    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t_inicio.isoformat(), pid=1000)

    # 2. Sessão trabalha até 14:45 (simula último heartbeat/atividade gravada antes de fechar)
    atualizar_heartbeat_tempo(sob_dir, pid=1000, timestamp_custom=t_fechou.isoformat())

    # 3. AutoCAD fechou. Reabre às 16:30 com PID 2000
    # O contexto do DWG é extraído pelo novo AutoCAD
    ctx = extrair_contexto_operacional(str(dwg), acad_pid=2000)
    tempo_info = ctx["tempo"]

    # Validações fundamentais:
    # A) O estado deve ser detectado como 'Interrompido'
    assert tempo_info["estado"] == TimeState.INTERROMPIDO.value
    # B) O tempo trabalhado DEVE ser exatamente 45 minutos (2700s) e NÃO 2h30min (9000s)!
    assert tempo_info["tempo_total_segundos"] == 2700.0
    assert tempo_info["tempo_formatado"] == "00:45:00"

    # 4. Usuário opta por Retomar o trabalho às 16:30 no novo AutoCAD
    res_retomar = iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t_reabriu.isoformat(), pid=2000)
    assert res_retomar.estado == TimeState.EM_EXECUCAO

    # 5. Após trabalhar mais 15 minutos (até 16:45), o tempo total deve ser 45m + 15m = 60m (01:00:00)
    t_trabalho2 = t_reabriu + timedelta(minutes=15)
    entry_atual = carregar_tempo_projeto(sob_dir)
    assert entry_atual.calcular_tempo_total_segundos(agora_dt=t_trabalho2) == 3600.0
    assert entry_atual.obter_tempo_formatado(agora_dt=t_trabalho2) == "01:00:00"


def test_caso_e_arquivo_corrompido_e_resiliencia(tmp_path: Path):
    """
    Caso E — Arquivo corrompido:
    Não destrói silenciosamente o histórico e recupera com segurança.
    """
    sob_dir = tmp_path / "SOB_CASO_E"
    sob_dir.mkdir()
    oxcad_dir = sob_dir / ".oxcad"
    oxcad_dir.mkdir()
    time_file = oxcad_dir / "time.json"
    time_file.write_text("{{{ INVALID JSON CORRUPTED", encoding="utf-8")

    # carregar com fallback não explode e fornece entrada segura
    entry = carregar_tempo_projeto(sob_dir, fallback_se_invalido=True)
    assert entry is not None
    assert entry.estado == TimeState.NAO_INICIADO
    assert entry.sob_id == "SOB_CASO_E"

    # Salvar nova entrada recupera o arquivo atomicamente
    entry.tempo_acumulado_segundos = 100.0
    assert salvar_tempo_projeto(sob_dir, entry) is True
    assert json.loads(time_file.read_text(encoding="utf-8"))["tempo_acumulado_segundos"] == 100.0


def test_caso_f_duplo_clique_e_idempotencia_estrita(tmp_path: Path):
    """
    Caso F — Duplo clique e Idempotência:
    - Pausar -> Pausar (sem duplicar sessões, sem alterar tempo)
    - Retomar -> Retomar (sem zerar sessão, sem duplicar)
    - Concluir -> Concluir (sem alterar data de encerramento)
    - Reabrir em projeto não concluído (sem efeito adverso)
    """
    sob_dir = tmp_path / "SOB_CASO_F"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=10)

    # Iniciar
    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())

    # Duplo clique em Pausar às 09:10
    e1 = pausar_tempo(sob_dir, timestamp_iso=t1.isoformat())
    e2 = pausar_tempo(sob_dir, timestamp_iso=t1.isoformat())
    assert e1.tempo_acumulado_segundos == 600.0
    assert e2.tempo_acumulado_segundos == 600.0
    assert len(e2.sessoes) == 1  # NÃO gerou sessão fantasma vazia!

    # Duplo clique em Retomar às 09:10
    e3 = iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t1.isoformat())
    e4 = iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t1.isoformat())
    assert e3.tempo_acumulado_segundos == 600.0
    assert e4.tempo_acumulado_segundos == 600.0
    assert e4.estado == TimeState.EM_EXECUCAO

    # Duplo clique em Concluir
    t2 = t1 + timedelta(minutes=5)
    e5 = concluir_tempo(sob_dir, timestamp_iso=t2.isoformat())
    e6 = concluir_tempo(sob_dir, timestamp_iso=t2.isoformat())
    assert e5.estado == TimeState.CONCLUIDO
    assert e6.estado == TimeState.CONCLUIDO
    assert e5.data_hora_fim == e6.data_hora_fim
    assert e6.tempo_acumulado_segundos == 900.0

    # Chamar reabrir em projeto já reaberto/pausado
    e7 = reabrir_tempo(sob_dir)
    assert e7.estado == TimeState.PAUSADO
    e8 = reabrir_tempo(sob_dir)
    assert e8.estado == TimeState.PAUSADO


def test_relogio_retrocedido_delta_negativo(tmp_path: Path):
    """Garante que saltos para trás no relógio do Windows não causem tempo negativo."""
    sob_dir = tmp_path / "SOB_TIMEWARP"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    t_passado = t0 - timedelta(hours=1)

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())
    entry = pausar_tempo(sob_dir, timestamp_iso=t_passado.isoformat())
    assert entry.tempo_acumulado_segundos == 0.0
    assert entry.estado == TimeState.PAUSADO


def test_integracao_cli_tempo(tmp_path: Path, simulated_host_protocol):
    """Valida extração e ações operacionais de tempo via workspace_context_cli.py com acad-pid."""
    sob_dir = tmp_path / "SOB_CLI_01"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("cad", encoding="utf-8")
    sob_id = "A057349839"
    (sob_dir / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id, "status": "CONCLUÍDO", "base_dwg": str(dwg)
        }), encoding="utf-8",
    )

    def acao_tempo(nome: str):
        return executar_acao_operacional(
            nome, dwg_path=str(dwg), acad_pid=5555,
            sob_id_esperada=sob_id,
            host_context=simulated_host_protocol(dwg, sob_id),
        )

    # 1. Extrair contexto
    ctx = extrair_contexto_operacional(str(dwg))
    assert ctx["tempo"] is not None
    assert ctx["tempo"]["estado"] == TimeState.NAO_INICIADO.value
    assert ctx["tempo"]["tempo_formatado"] == "00:00:00"

    # 2. Executar ação de início via CLI com acad_pid
    res_inicio = acao_tempo("tempo_iniciar")
    assert res_inicio["sucesso"] is True
    assert res_inicio["estado"] == TimeState.EM_EXECUCAO.value

    # 3. Executar ação de heartbeat
    res_hb = acao_tempo("tempo_heartbeat")
    assert res_hb["sucesso"] is True

    # 4. Executar ação de pausa
    res_pausa = acao_tempo("tempo_pausar")
    assert res_pausa["sucesso"] is True
    assert res_pausa["estado"] == TimeState.PAUSADO.value

    # 5. Executar retomada
    res_retomar = acao_tempo("tempo_retomar")
    assert res_retomar["sucesso"] is True
    assert res_retomar["estado"] == TimeState.EM_EXECUCAO.value

    # 6. Executar conclusão
    res_fim = acao_tempo("tempo_concluir")
    assert res_fim["sucesso"] is True
    assert res_fim["estado"] == TimeState.CONCLUIDO.value

    # 7. Executar reabertura
    res_reabrir = acao_tempo("tempo_reabrir")
    assert res_reabrir["sucesso"] is True
    assert res_reabrir["estado"] == TimeState.PAUSADO.value


def test_integracao_sob_manager_inicializa_tempo(tmp_path: Path):
    """
    Valida que ao finalizar a preparação de uma SOB via SobOrchestrator,
    o arquivo .oxcad/time.json é gerado com estado EmExecucao e tempo zerado.
    """
    fake_dwg = tmp_path / "modelos" / "prancha.dwg"
    fake_dwg.parent.mkdir(parents=True, exist_ok=True)
    fake_dwg.write_bytes(b"AC1032" + (b"\x00" * 200) + b"MODELO_BASE_OFICIAL")

    destino = tmp_path / "projetos"
    destino.mkdir()

    mock_client = MagicMock(spec=SharePointClient)
    mock_client.autenticar.return_value = True
    mock_client.localizar_pasta_sob.return_value = {"nome": "SOB_A057349839", "elemento": MagicMock()}

    def simular_download(pasta_info, croqui_dir):
        arq = croqui_dir / "croqui_campo.pdf"
        arq.write_bytes(b"%PDF-1.4 croqui de teste")
        return [arq]

    mock_client.baixar_croqui.side_effect = simular_download
    mock_client.validar_download.return_value = True

    orquestrador = SobOrchestrator(
        origem_base=fake_dwg,
        sharepoint_client=mock_client,
    )

    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(destino),
        baixar_croqui_sp=True,
        abrir_cad=False,
    )

    assert resultado["sucesso"] is True

    # Verificar existência da pasta SOB criada
    pasta_sob = destino / "SOB_A057349839"
    assert pasta_sob.exists()

    # Verificar criação automática do arquivo .oxcad/time.json
    time_file = pasta_sob / ".oxcad" / "time.json"
    assert time_file.exists()

    entry = carregar_tempo_projeto(pasta_sob)
    assert entry is not None
    assert entry.estado == TimeState.EM_EXECUCAO
    assert entry.data_hora_inicio is not None
    assert entry.tempo_acumulado_segundos == 0.0
    assert entry.dwg_path is not None
    assert Path(entry.dwg_path).exists()


def test_processo_esta_ativo_robustez():
    """Valida determinismo e ausência de efeitos colaterais em processo_esta_ativo."""
    import os
    # PIDs inválidos ou nulos
    assert processo_esta_ativo(None) is False
    assert processo_esta_ativo(0) is False
    assert processo_esta_ativo(-1) is False
    assert processo_esta_ativo(-99999) is False

    # Processo atual garantidamente ativo
    meu_pid = os.getpid()
    assert processo_esta_ativo(meu_pid) is True

    # PID inexistente no SO
    assert processo_esta_ativo(99999999) is False


def test_colisao_pid_reutilizado_com_token_sessao(tmp_path: Path):
    """
    Cenário Crítico de PID Reutilizado pelo Windows (Seções 3 e 14 do Prompt):
    Processo A abre com PID 1000 e Token A.
    AutoCAD A é fechado às 10:20 (último heartbeat às 10:20).
    O kernel do Windows reutiliza o PID 1000 para outro processo / novo AutoCAD B!
    Novo AutoCAD B abre o DWG às 11:30 com PID 1000 e Token B.
    O sistema DEVE detectar a interrupção devido ao token diferente,
    mesmo que o PID seja idêntico (1000 == 1000).
    """
    sob_dir = tmp_path / "SOB_PID_REUSE"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("cad", encoding="utf-8")

    t0 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    t_hb = datetime(2026, 9, 26, 10, 20, 0, tzinfo=timezone.utc)
    t_novo = datetime(2026, 9, 26, 11, 30, 0, tzinfo=timezone.utc)

    # 1. AutoCAD A inicia sessão com PID 1000 e Token A
    iniciar_ou_retomar_tempo(
        sob_dir,
        timestamp_iso=t0.isoformat(),
        pid=1000,
        token_sessao="1000_SESSAO_AUTOCAD_A",
    )

    # 2. Heartbeat às 10:20
    atualizar_heartbeat_tempo(
        sob_dir,
        pid=1000,
        token_sessao="1000_SESSAO_AUTOCAD_A",
        timestamp_custom=t_hb.isoformat(),
    )

    # 3. AutoCAD A encerrou. Novo AutoCAD B inicia e coincidentemente recebe PID 1000
    # mas possui seu próprio token de sessão
    ctx = extrair_contexto_operacional(
        str(dwg),
        acad_pid=1000,
        acad_token="1000_SESSAO_AUTOCAD_B",
    )
    tempo_info = ctx["tempo"]

    # Deve detectar Interrompido e contabilizar estritamente os 20m (1200s),
    # descartando o período com AutoCAD fechado (10:20 às 11:30)
    assert tempo_info["estado"] == TimeState.INTERROMPIDO.value
    assert tempo_info["tempo_total_segundos"] == 1200.0
    assert tempo_info["tempo_formatado"] == "00:20:00"


def test_longo_periodo_e_ausencia_inchaco_json(tmp_path: Path):
    """
    Cenário de Longo Período (Seção 9):
    Centenas de heartbeats não podem inflar o time.json nem duplicar sessões.
    """
    sob_dir = tmp_path / "SOB_LONGO_PERIODO"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 8, 0, 0, tzinfo=timezone.utc)
    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat(), pid=1234, token_sessao="TOK_1234")

    # Primeiro heartbeat grava ultima_atividade
    t_hb1 = t0 + timedelta(minutes=1)
    atualizar_heartbeat_tempo(
        sob_dir,
        pid=1234,
        token_sessao="TOK_1234",
        timestamp_custom=t_hb1.isoformat(),
    )
    time_file = obter_caminho_time_json(sob_dir)
    tam_apos_hb1 = time_file.stat().st_size

    # Simula mais 119 heartbeats (totalizando 2 horas de trabalho a cada 60s)
    for m in range(2, 121):
        t_tick = t0 + timedelta(minutes=m)
        atualizar_heartbeat_tempo(
            sob_dir,
            pid=1234,
            token_sessao="TOK_1234",
            timestamp_custom=t_tick.isoformat(),
        )

    entry = carregar_tempo_projeto(sob_dir)
    # A lista de sessões concluídas NÃO pode conter entradas criadas por heartbeat
    assert len(entry.sessoes) == 0

    # O tamanho do arquivo NÃO pode crescer indefinidamente entre o 1º e o 120º heartbeat
    tam_final = time_file.stat().st_size
    assert abs(tam_final - tam_apos_hb1) <= 10

    # Ao consultar 4 horas depois (12:00)
    t_fim = t0 + timedelta(hours=4)
    assert entry.calcular_tempo_total_segundos(agora_dt=t_fim) == 14400.0
    assert entry.obter_tempo_formatado(agora_dt=t_fim) == "04:00:00"


def test_heartbeat_apos_pausa_ou_conclusao_e_ignorado(tmp_path: Path):
    """Heartbeat só pode atuar em EmExecucao; é sumariamente ignorado em Pausado ou Concluido."""
    sob_dir = tmp_path / "SOB_HB_IGNORADO"
    sob_dir.mkdir()

    t0 = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)
    t_hb = t1 + timedelta(minutes=10)

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat())
    pausar_tempo(sob_dir, timestamp_iso=t1.isoformat())

    # Heartbeat enviado quando o projeto já está Pausado
    entry_hb = atualizar_heartbeat_tempo(sob_dir, pid=999, timestamp_custom=t_hb.isoformat())
    assert entry_hb.estado == TimeState.PAUSADO
    assert entry_hb.tempo_acumulado_segundos == 1800.0
    assert entry_hb.pid_processo is None

    # Concluir
    entry_fim = concluir_tempo(sob_dir, timestamp_iso=t_hb.isoformat())
    assert entry_fim.estado == TimeState.CONCLUIDO

    # Heartbeat em projeto já Concluido
    entry_hb2 = atualizar_heartbeat_tempo(sob_dir, pid=999, timestamp_custom=(t_hb + timedelta(hours=1)).isoformat())
    assert entry_hb2.estado == TimeState.CONCLUIDO
    assert entry_hb2.tempo_acumulado_segundos == 1800.0


def test_pausa_fechamento_reabertura_mantem_pausado(tmp_path: Path):
    """
    Cenário Pausado + Fechamento (Seção 11):
    14:00 iniciar
    14:30 pausar
    14:40 fechar AutoCAD
    16:00 abrir AutoCAD com novo PID
    O estado deve continuar semanticamente Pausado, NÃO Interrompido.
    """
    sob_dir = tmp_path / "SOB_PAUSA_FECHAMENTO"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("cad", encoding="utf-8")

    t0 = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    t_pausa = datetime(2026, 9, 26, 14, 30, 0, tzinfo=timezone.utc)

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat(), pid=1000)
    pausar_tempo(sob_dir, timestamp_iso=t_pausa.isoformat())

    # Novo AutoCAD abre às 16:00 com PID 3000
    ctx = extrair_contexto_operacional(str(dwg), acad_pid=3000, acad_token="TOK_3000")
    tempo_info = ctx["tempo"]

    assert tempo_info["estado"] == TimeState.PAUSADO.value
    assert tempo_info["tempo_total_segundos"] == 1800.0
    assert tempo_info["tempo_formatado"] == "00:30:00"


def test_concluido_fechamento_reabertura_congelado(tmp_path: Path):
    """
    Cenário Concluído (Seção 12):
    14:00 iniciar
    15:00 concluir
    18:00 abrir novamente com novo PID
    Tempo deve permanecer congelado e estado Concluído.
    """
    sob_dir = tmp_path / "SOB_CONCLUIDO_FECHAMENTO"
    sob_dir.mkdir()
    dwg = sob_dir / "desenho.dwg"
    dwg.write_text("cad", encoding="utf-8")

    t0 = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    t_fim = datetime(2026, 9, 26, 15, 0, 0, tzinfo=timezone.utc)

    iniciar_ou_retomar_tempo(sob_dir, timestamp_iso=t0.isoformat(), pid=1000)
    concluir_tempo(sob_dir, timestamp_iso=t_fim.isoformat())

    # Reabrir AutoCAD horas depois
    ctx = extrair_contexto_operacional(str(dwg), acad_pid=4000, acad_token="TOK_4000")
    tempo_info = ctx["tempo"]

    assert tempo_info["estado"] == TimeState.CONCLUIDO.value
    assert tempo_info["tempo_total_segundos"] == 3600.0
    assert tempo_info["tempo_formatado"] == "01:00:00"


def test_timezone_utc_explicito_em_todos_os_campos(tmp_path: Path):
    """
    Auditoria de Timezone (Seção 20):
    Garante que todos os timestamps gerados e persistidos possuem timezone explícito (+00:00 ou Z).
    """
    sob_dir = tmp_path / "SOB_TIMEZONE"
    sob_dir.mkdir()

    entry = iniciar_ou_retomar_tempo(sob_dir)
    assert entry.data_hora_inicio is not None
    assert "+" in entry.data_hora_inicio or "Z" in entry.data_hora_inicio
    assert "+" in entry.ultima_atualizacao or "Z" in entry.ultima_atualizacao

    entry_pausa = pausar_tempo(sob_dir)
    assert "+" in entry_pausa.ultima_atualizacao or "Z" in entry_pausa.ultima_atualizacao
    if entry_pausa.sessoes:
        s0 = entry_pausa.sessoes[0]
        assert "+" in s0["inicio"] or "Z" in s0["inicio"]
        assert "+" in s0["fim"] or "Z" in s0["fim"]


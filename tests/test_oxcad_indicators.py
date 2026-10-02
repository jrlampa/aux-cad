# -*- coding: utf-8 -*-
"""
Suíte de testes automatizados para o P2.1 — Indicadores de Gestão (OXCAD).
Cobre exaustivamente os 18 cenários contratuais obrigatórios com dados sintéticos:
1. log vazio;
2. uma execução concluída;
3. execução com múltiplas transições;
4. execução falha;
5. execução cancelada;
6. múltiplas ações;
7. cálculo de média/mediana/p95;
8. linha JSON inválida;
9. arquivo ausente;
10. filtro por SOB;
11. SOB divergente;
12. pending.json ausente;
13. delivery ausente;
14. time.json ausente;
15. dados incompletos;
16. isolamento entre duas SOBs;
17. ausência de histórico não inferida como zero;
18. resultado determinístico.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from workspace.workspace_indicators import consultar_indicadores, IndicadoresAnalyzer


def _escrever_jsonl(path: Path, records: list):
    linhas = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


# 1. Log vazio
def test_01_log_vazio(tmp_path: Path):
    log_file = tmp_path / "empty.jsonl"
    log_file.write_text("", encoding="utf-8")

    res = consultar_indicadores(log_file=log_file)
    assert res["schema"] == 1
    assert res["execucoes"]["status"] == "SEM_DADOS"
    assert res["execucoes"]["total_execucoes"] == 0
    assert res["execucoes"]["taxa_conclusao_pct"] is None
    assert res["execucoes"]["duracao_ms"]["media_ms"] is None


# 2. Uma execução concluída
def test_02_uma_execucao_concluida(tmp_path: Path):
    log_file = tmp_path / "single.jsonl"
    _escrever_jsonl(log_file, [
        {
            "execution_id": "exec-1",
            "action": "cqt",
            "execution_state": "Concluido",
            "duration_ms": 1250.0,
            "sob_id": "A057526153",
            "timestamp": "2026-10-02T10:00:00Z"
        }
    ])

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["status"] == "OK"
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["concluidas"] == 1
    assert res["execucoes"]["falhas"] == 0
    assert res["execucoes"]["taxa_conclusao_pct"] == 100.0
    assert res["execucoes"]["duracao_ms"]["media_ms"] == 1250.0
    assert res["execucoes"]["distribuicao_por_acao"]["cqt"] == 1


# 3. Execução com múltiplas transições (Iniciado -> Executando -> Concluido)
def test_03_execucao_multiplas_transicoes(tmp_path: Path):
    log_file = tmp_path / "transitions.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "exec-multi", "action": "orcamento", "execution_state": "Iniciado", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "exec-multi", "action": "orcamento", "execution_state": "Executando", "timestamp": "2026-10-02T10:00:01Z"},
        {"execution_id": "exec-multi", "action": "orcamento", "execution_state": "Concluido", "duration_ms": 2500.0, "timestamp": "2026-10-02T10:00:02Z"}
    ])

    res = consultar_indicadores(log_file=log_file)
    # Deve contabilizar EXATAMENTE 1 execução, sem inflar o volume por eventos repetidos
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["concluidas"] == 1
    assert res["execucoes"]["taxa_conclusao_pct"] == 100.0
    assert res["execucoes"]["duracao_ms"]["media_ms"] == 2500.0


# 4. Execução falha
def test_04_execucao_falha(tmp_path: Path):
    log_file = tmp_path / "failed.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "exec-fail", "action": "sob", "execution_state": "Iniciado", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "exec-fail", "action": "sob", "execution_state": "Falhou", "error": "ARTIFACT_NOT_VERIFIED", "duration_ms": 800.0, "timestamp": "2026-10-02T10:00:01Z"}
    ])

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["concluidas"] == 0
    assert res["execucoes"]["falhas"] == 1
    assert res["execucoes"]["taxa_conclusao_pct"] == 0.0
    assert res["execucoes"]["falhas_por_tipo"]["ARTIFACT_NOT_VERIFIED"] == 1


# 5. Execução cancelada
def test_05_execucao_cancelada(tmp_path: Path):
    log_file = tmp_path / "canceled.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "exec-canc", "action": "prancha", "execution_state": "Cancelado", "duration_ms": 300.0, "timestamp": "2026-10-02T10:00:00Z"}
    ])

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["concluidas"] == 0
    assert res["execucoes"]["canceladas"] == 1
    assert res["execucoes"]["taxa_conclusao_pct"] == 0.0


# 6. Múltiplas ações
def test_06_multiplas_acoes(tmp_path: Path):
    log_file = tmp_path / "multiple_actions.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "action": "cqt", "execution_state": "Concluido", "duration_ms": 100.0},
        {"execution_id": "e2", "action": "cqt", "execution_state": "Concluido", "duration_ms": 150.0},
        {"execution_id": "e3", "action": "orcamento", "execution_state": "Concluido", "duration_ms": 300.0},
        {"execution_id": "e4", "action": "ambiental", "execution_state": "Falhou", "error": "MISSING_DOCX", "duration_ms": 500.0},
    ])

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 4
    assert res["execucoes"]["concluidas"] == 3
    assert res["execucoes"]["falhas"] == 1
    assert res["execucoes"]["taxa_conclusao_pct"] == 75.0
    dist = res["execucoes"]["distribuicao_por_acao"]
    assert dist == {"ambiental": 1, "cqt": 2, "orcamento": 1}


# 7. Cálculo de média/mediana/p95
def test_07_calculo_media_mediana_p95(tmp_path: Path):
    log_file = tmp_path / "stats.jsonl"
    # Conjunto de durações: 100, 200, 300, 400, 500, 1000
    # Total = 2500, Média = 416.67, Mediana = 350.0, P95 com interpolação = 875.0
    duracoes = [100.0, 200.0, 300.0, 400.0, 500.0, 1000.0]
    records = [
        {"execution_id": f"e-{i}", "action": "cqt", "execution_state": "Concluido", "duration_ms": d}
        for i, d in enumerate(duracoes)
    ]
    _escrever_jsonl(log_file, records)

    res = consultar_indicadores(log_file=log_file)
    dur = res["execucoes"]["duracao_ms"]
    assert dur["amostras"] == 6
    assert dur["total_ms"] == 2500.0
    assert dur["media_ms"] == 416.67
    assert dur["mediana_ms"] == 350.0
    assert dur["p95_ms"] == 875.0


# 8. Linha JSON inválida
def test_08_linha_json_invalida(tmp_path: Path):
    log_file = tmp_path / "corrupt.jsonl"
    conteudo = (
        '{"execution_id": "ok-1", "action": "cqt", "execution_state": "Concluido", "duration_ms": 100.0}\n'
        'LINHA CORROMPIDA INVALIDA NAO-JSON { [ \n'
        '{"execution_id": "ok-2", "action": "orcamento", "execution_state": "Concluido", "duration_ms": 200.0}\n'
    )
    log_file.write_text(conteudo, encoding="utf-8")

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 2
    assert res["qualidade_dados"]["linhas_totais_log"] == 3
    assert res["qualidade_dados"]["linhas_validas_log"] == 2
    assert res["qualidade_dados"]["linhas_invalidas_log"] == 1


# 9. Arquivo ausente
def test_09_arquivo_ausente(tmp_path: Path):
    non_existent = tmp_path / "nao_existe.jsonl"
    res = consultar_indicadores(log_file=non_existent)
    assert res["execucoes"]["status"] == "NÃO DISPONÍVEL"
    assert res["execucoes"]["motivo"] == "ARQUIVO_LOG_NAO_ENCONTRADO"
    assert str(non_existent) in res["qualidade_dados"]["arquivos_ausentes"]


# 10. Filtro por SOB
def test_10_filtro_por_sob(tmp_path: Path):
    log_file = tmp_path / "multi_sob.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "eA1", "sob_id": "A057526153", "action": "cqt", "execution_state": "Concluido"},
        {"execution_id": "eA2", "sob_id": "A057526153", "action": "orcamento", "execution_state": "Concluido"},
        {"execution_id": "eB1", "sob_id": "B999888777", "action": "cqt", "execution_state": "Concluido"},
    ])

    res_a = consultar_indicadores(log_file=log_file, sob_id="A057526153")
    assert res_a["execucoes"]["total_execucoes"] == 2
    assert res_a["escopo"]["sob_id"] == "A057526153"

    res_b = consultar_indicadores(log_file=log_file, sob_id="B999888777")
    assert res_b["execucoes"]["total_execucoes"] == 1
    assert res_b["escopo"]["sob_id"] == "B999888777"


# 11. SOB divergente
def test_11_sob_divergente(tmp_path: Path):
    project_dir = tmp_path / "SOB_A057526153"
    project_dir.mkdir()
    manifesto = project_dir / ".sob_state.json"
    manifesto.write_text(json.dumps({"sob_id": "A057526153", "status": "CONCLUÍDO"}), encoding="utf-8")

    # Passa sob_id incompatível com o manifesto existente
    res = consultar_indicadores(project_root=project_dir, sob_id="B999999999")
    assert res["escopo"]["status_identidade"] == "IDENTITY_UNVERIFIABLE"
    assert res["escopo"]["motivo_recusa"] == "SOB_ID_MISMATCH"
    assert res["pendencias"]["status"] == "NÃO DISPONÍVEL"


# 12. pending.json ausente
def test_12_pending_json_ausente(tmp_path: Path):
    project_dir = tmp_path / "SOB_TESTE"
    project_dir.mkdir()

    res = consultar_indicadores(project_root=project_dir)
    assert res["pendencias"]["status"] == "NÃO DISPONÍVEL"
    assert res["pendencias"]["motivo"] == "ARQUIVO_PENDING_NAO_ENCONTRADO"
    # Não mascarar ausência como zero
    assert res["pendencias"]["total"] is None
    assert res["pendencias"]["taxa_resolucao_pct"] is None


# 13. delivery ausente
def test_13_delivery_ausente(tmp_path: Path):
    project_dir = tmp_path / "SOB_TESTE"
    project_dir.mkdir()

    res = consultar_indicadores(project_root=project_dir)
    assert res["entregas"]["status"] == "NÃO DISPONÍVEL"
    assert res["entregas"]["motivo"] == "DIRETORIO_DELIVERIES_NAO_ENCONTRADO"
    assert res["entregas"]["total_pacotes"] is None


# 14. time.json ausente
def test_14_time_json_ausente(tmp_path: Path):
    project_dir = tmp_path / "SOB_TESTE"
    project_dir.mkdir()

    res = consultar_indicadores(project_root=project_dir)
    assert res["tempo_operacional"]["status"] == "NÃO DISPONÍVEL"
    assert res["tempo_operacional"]["motivo"] == "ARQUIVO_TIME_NAO_ENCONTRADO"
    assert res["tempo_operacional"]["tempo_acumulado_segundos"] is None


# 15. Dados incompletos (eventos sem duration_ms ou sem state)
def test_15_dados_incompletos(tmp_path: Path):
    log_file = tmp_path / "incomplete.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "inc-1", "action": "cqt", "execution_state": "Iniciado"},
        {"execution_id": "inc-2", "action": "cqt", "execution_state": "Concluido"},  # sem duration_ms
        {"execution_id": "inc-3", "action": "cqt", "execution_state": "Concluido", "duration_ms": 500.0},
    ])

    res = consultar_indicadores(log_file=log_file)
    dur = res["execucoes"]["duracao_ms"]
    assert dur["amostras"] == 1
    assert dur["media_ms"] == 500.0


# 16. Isolamento entre duas SOBs
def test_16_isolamento_entre_duas_sobs(tmp_path: Path):
    # Projeto A
    dir_a = tmp_path / "SOB_A"
    (dir_a / ".oxcad").mkdir(parents=True)
    pending_a = dir_a / ".oxcad" / "pending.json"
    pending_a.write_text(json.dumps({
        "schema": 1, "sob_id": "A057111111",
        "items": [
            {"id": "p1", "status": "RESOLVIDA", "severity": "ALTA"},
            {"id": "p2", "status": "ABERTA", "severity": "MEDIA"},
        ]
    }), encoding="utf-8")

    # Projeto B
    dir_b = tmp_path / "SOB_B"
    (dir_b / ".oxcad").mkdir(parents=True)
    pending_b = dir_b / ".oxcad" / "pending.json"
    pending_b.write_text(json.dumps({
        "schema": 1, "sob_id": "B057222222",
        "items": [
            {"id": "p3", "status": "ABERTA", "severity": "CRITICA"},
        ]
    }), encoding="utf-8")

    res_a = consultar_indicadores(project_root=dir_a, sob_id="A057111111")
    assert res_a["pendencias"]["total"] == 2
    assert res_a["pendencias"]["resolvidas"] == 1
    assert res_a["pendencias"]["abertas"] == 1
    assert res_a["pendencias"]["por_severidade"]["ALTA"] == 1
    assert res_a["pendencias"]["por_severidade"]["CRITICA"] == 0

    res_b = consultar_indicadores(project_root=dir_b, sob_id="B057222222")
    assert res_b["pendencias"]["total"] == 1
    assert res_b["pendencias"]["resolvidas"] == 0
    assert res_b["pendencias"]["abertas"] == 1
    assert res_b["pendencias"]["por_severidade"]["ALTA"] == 0
    assert res_b["pendencias"]["por_severidade"]["CRITICA"] == 1


# 17. Ausência de histórico não inferida como zero
def test_17_ausencia_historico_nao_inferida_como_zero(tmp_path: Path):
    log_file = tmp_path / "no_history.jsonl"
    log_file.write_text("", encoding="utf-8")

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["taxa_conclusao_pct"] is None
    assert res["execucoes"]["duracao_ms"]["media_ms"] is None
    assert res["execucoes"]["duracao_ms"]["mediana_ms"] is None
    assert res["execucoes"]["duracao_ms"]["p95_ms"] is None


# 18. Resultado determinístico
def test_18_resultado_deterministico(tmp_path: Path):
    log_file = tmp_path / "det.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "action": "cqt", "execution_state": "Concluido", "duration_ms": 100.0, "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "e2", "action": "orcamento", "execution_state": "Falhou", "error": "ERR_1", "duration_ms": 200.0, "timestamp": "2026-10-02T10:01:00Z"},
    ])

    res1 = consultar_indicadores(log_file=log_file)
    res2 = consultar_indicadores(log_file=log_file)

    # Ignora apenas o timestamp de geração
    res1_copy = {k: v for k, v in res1.items() if k != "gerado_em"}
    res2_copy = {k: v for k, v in res2.items() if k != "gerado_em"}

    assert res1_copy == res2_copy

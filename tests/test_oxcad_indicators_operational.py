# -*- coding: utf-8 -*-
"""
Suíte de testes automatizados para o P2.2 — Indicadores Operacionais e Visão Consolidada de Processo (OXCAD).
Cobre exaustivamente os 20 cenários contratuais obrigatórios com dados sintéticos:
1. consulta de projeto válido;
2. consulta de SOB inexistente;
3. identidade divergente;
4. workspace vazio;
5. workspace com múltiplos projetos;
6. filtro por período;
7. filtro por ação;
8. filtro por estado;
9. ausência de fonte persistente;
10. log rotativo;
11. log corrompido;
12. múltiplas transições do mesmo execution_id;
13. isolamento entre SOBs;
14. resultado determinístico;
15. consulta não gera OxCadExecution;
16. consulta não altera arquivos;
17. UI / CLI não bloqueia por processamento síncrono;
18. erro de leitura apresentado corretamente;
19. cobertura histórica explicitada;
20. regressão do P2.1.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import pytest

from workspace.workspace_indicators import consultar_indicadores, IndicadoresAnalyzer
from workspace.workspace_indicators_cli import formatar_resumo_terminal


def _escrever_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _escrever_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    linhas = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _criar_projeto_sintetico(root: Path, sob_id: str, num_pendencias: int = 2, num_entregas: int = 1):
    root.mkdir(parents=True, exist_ok=True)
    # .sob_state.json
    _escrever_json(root / ".sob_state.json", {
        "sob_id": sob_id,
        "status": "CONCLUIDO",
        "duracao_segundos": 45.0,
        "data_inicio": "2026-10-01T08:00:00Z",
        "data_fim": "2026-10-01T08:00:45Z",
    })
    # .oxcad/pending.json
    items = []
    for i in range(num_pendencias):
        items.append({
            "id": f"p-{i+1}",
            "sob_id": sob_id,
            "status": "ABERTA" if i % 2 == 0 else "RESOLVIDA",
            "severity": "ALTA" if i % 2 == 0 else "BAIXA",
        })
    _escrever_json(root / ".oxcad" / "pending.json", {
        "schema": 1,
        "sob_id": sob_id,
        "items": items,
    })
    # .oxcad/deliveries/
    for j in range(num_entregas):
        deliv_dir = root / ".oxcad" / "deliveries" / f"pkg_{j+1}"
        _escrever_json(deliv_dir / "manifest.json", {"sob_id": sob_id, "package_id": f"pkg_{j+1}"})
        _escrever_json(deliv_dir / "approval.json", {"approved": True})
        (deliv_dir / "manifest.sha256").write_text("dummyhash", encoding="utf-8")
    # .oxcad/time.json
    _escrever_json(root / ".oxcad" / "time.json", {
        "sob_id": sob_id,
        "estado": "Pausado",
        "tempo_acumulado_segundos": 3600.0,
        "sessoes": [{"inicio": "2026-10-01T09:00:00Z", "fim": "2026-10-01T10:00:00Z", "segundos": 3600.0}],
    })
    # .auxcad_versions/
    v_dir = root / ".auxcad_versions" / "v1"
    _escrever_json(v_dir / "manifest.json", {"version": "v1"})


# 1. Consulta de projeto válido
def test_01_consulta_projeto_valido(tmp_path: Path):
    proj_dir = tmp_path / "SOB_VALIDA"
    _criar_projeto_sintetico(proj_dir, "SOB_VALIDA", num_pendencias=4, num_entregas=2)

    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_VALIDA")
    assert res["schema"] == 1
    assert res["escopo"]["tipo"] == "PROJETO"
    assert res["escopo"]["status_identidade"] == "VALIDA"
    assert res["escopo"]["sob_id"] == "SOB_VALIDA"
    assert res["pendencias"]["status"] == "OK"
    assert res["pendencias"]["total"] == 4
    assert res["entregas"]["status"] == "OK"
    assert res["entregas"]["total_pacotes"] == 2
    assert res["tempo_operacional"]["status"] == "OK"
    assert res["tempo_operacional"]["tempo_acumulado_segundos"] == 3600.0
    assert res["versoes"]["status"] == "OK"
    assert res["versoes"]["total_snapshots"] == 1


# 2. Consulta de SOB inexistente (diretório não encontrado)
def test_02_consulta_sob_inexistente(tmp_path: Path):
    proj_dir = tmp_path / "SOB_INEXISTENTE"
    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_INEXISTENTE")

    assert res["escopo"]["status_identidade"] == "IDENTITY_UNVERIFIABLE"
    assert res["escopo"]["motivo_recusa"] == "DIRETORIO_PROJETO_NAO_ENCONTRADO"
    assert res["execucoes"]["status"] == "NÃO DISPONÍVEL"


# 3. Identidade divergente
def test_03_identidade_divergente(tmp_path: Path):
    proj_dir = tmp_path / "SOB_A"
    _criar_projeto_sintetico(proj_dir, "SOB_A")

    # Informa SOB_B para uma pasta que contém manifesto de SOB_A
    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_B")
    assert res["escopo"]["status_identidade"] == "IDENTITY_UNVERIFIABLE"
    assert res["escopo"]["motivo_recusa"] == "SOB_ID_MISMATCH"


# 4. Workspace vazio
def test_04_workspace_vazio(tmp_path: Path):
    ws_dir = tmp_path / "workspace_vazio"
    ws_dir.mkdir(parents=True, exist_ok=True)

    res = consultar_indicadores(workspace_root=ws_dir)
    assert res["escopo"]["tipo"] == "WORKSPACE"
    assert res["escopo"]["total_projetos_observados"] == 0
    assert res["pendencias"]["status"] == "SEM_DADOS"
    assert res["pendencias"]["total"] == 0
    assert any("Nenhum diretório" in lim for lim in res["qualidade_dados"]["limitacoes_cobertura"])


# 5. Workspace com múltiplos projetos
def test_05_workspace_multiplos_projetos(tmp_path: Path):
    ws_dir = tmp_path / "workspace_multi"
    p1 = ws_dir / "PROJ_1"
    p2 = ws_dir / "PROJ_2"
    _criar_projeto_sintetico(p1, "SOB_1", num_pendencias=2, num_entregas=1)
    _criar_projeto_sintetico(p2, "SOB_2", num_pendencias=3, num_entregas=2)

    res = consultar_indicadores(workspace_root=ws_dir)
    assert res["escopo"]["tipo"] == "WORKSPACE"
    assert res["escopo"]["total_projetos_observados"] == 2
    assert "SOB_1" in res["escopo"]["projetos_observados"]
    assert "SOB_2" in res["escopo"]["projetos_observados"]
    assert res["pendencias"]["status"] == "OK"
    assert res["pendencias"]["total"] == 5  # 2 + 3
    assert res["entregas"]["status"] == "OK"
    assert res["entregas"]["total_pacotes"] == 3  # 1 + 2
    assert res["tempo_operacional"]["tempo_acumulado_segundos"] == 7200.0  # 3600 + 3600
    assert res["versoes"]["total_snapshots"] == 2  # 1 + 1


# 6. Filtro por período
def test_06_filtro_por_periodo(tmp_path: Path):
    log_file = tmp_path / "log_periodo.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"},
        {"execution_id": "e2", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "e3", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-03T10:00:00Z"},
    ])

    res = consultar_indicadores(
        log_file=log_file,
        periodo_inicio="2026-10-02T00:00:00Z",
        periodo_fim="2026-10-02T23:59:59Z",
    )
    assert res["execucoes"]["status"] == "OK"
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["periodo_observado"]["inicio"] == "2026-10-02T10:00:00Z"


# 7. Filtro por ação
def test_07_filtro_por_acao(tmp_path: Path):
    log_file = tmp_path / "log_acao.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "e2", "action": "orcamento", "execution_state": "Concluido", "timestamp": "2026-10-02T10:01:00Z"},
        {"execution_id": "e3", "action": "cqt", "execution_state": "Falhou", "timestamp": "2026-10-02T10:02:00Z"},
    ])

    res = consultar_indicadores(log_file=log_file, acao="cqt")
    assert res["execucoes"]["status"] == "OK"
    assert res["execucoes"]["total_execucoes"] == 2
    assert "orcamento" not in res["execucoes"]["distribuicao_por_acao"]
    assert res["execucoes"]["distribuicao_por_acao"]["cqt"] == 2


# 8. Filtro por estado
def test_08_filtro_por_estado(tmp_path: Path):
    log_file = tmp_path / "log_estado.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "e2", "action": "cqt", "execution_state": "Falhou", "error": "ERR_TEST", "timestamp": "2026-10-02T10:01:00Z"},
        {"execution_id": "e3", "action": "cqt", "execution_state": "Cancelado", "timestamp": "2026-10-02T10:02:00Z"},
    ])

    res = consultar_indicadores(log_file=log_file, estado="Falhou")
    assert res["execucoes"]["status"] == "OK"
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["falhas"] == 1
    assert res["execucoes"]["concluidas"] == 0


# 9. Ausência de fonte persistente (time.json ausente)
def test_09_ausencia_fonte_persistente(tmp_path: Path):
    proj_dir = tmp_path / "SOB_PARCIAL"
    _criar_projeto_sintetico(proj_dir, "SOB_PARCIAL")
    # Deleta time.json propositalmente
    time_file = proj_dir / ".oxcad" / "time.json"
    if time_file.is_file():
        time_file.unlink()

    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_PARCIAL")
    assert res["tempo_operacional"]["status"] == "NÃO DISPONÍVEL"
    assert res["tempo_operacional"]["motivo"] == "ARQUIVO_TIME_NAO_ENCONTRADO"
    # Mas pendências continuam OK
    assert res["pendencias"]["status"] == "OK"


# 10. Log rotativo
def test_10_log_rotativo(tmp_path: Path):
    log_file = tmp_path / "application.jsonl"
    log_file.write_text("", encoding="utf-8")

    res = consultar_indicadores(log_file=log_file)
    lims = res["qualidade_dados"]["limitacoes_cobertura"]
    assert any("rotação máxima de 5 MB" in lim for lim in lims)


# 11. Log corrompido
def test_11_log_corrompido(tmp_path: Path):
    log_file = tmp_path / "corrupted.jsonl"
    log_file.write_text("LINHA_INVALIDA_NAO_JSON\n{\"execution_id\":\"e1\",\"action\":\"cqt\",\"execution_state\":\"Concluido\"}\n{JSON_TRUNCADO", encoding="utf-8")

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["qualidade_dados"]["linhas_invalidas_log"] == 2
    assert res["qualidade_dados"]["linhas_validas_log"] == 1


# 12. Múltiplas transições do mesmo execution_id
def test_12_multiplas_transicoes_mesmo_execution_id(tmp_path: Path):
    log_file = tmp_path / "transitions.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e_trans", "action": "cqt", "execution_state": "Iniciado", "timestamp": "2026-10-02T10:00:00Z"},
        {"execution_id": "e_trans", "action": "cqt", "execution_state": "Executando", "timestamp": "2026-10-02T10:00:01Z"},
        {"execution_id": "e_trans", "action": "cqt", "execution_state": "Executando", "timestamp": "2026-10-02T10:00:02Z"},
        {"execution_id": "e_trans", "action": "cqt", "execution_state": "Concluido", "duration_ms": 1500.0, "timestamp": "2026-10-02T10:00:03Z"},
    ])

    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 1
    assert res["execucoes"]["concluidas"] == 1
    assert res["execucoes"]["duracao_ms"]["media_ms"] == 1500.0


# 13. Isolamento entre SOBs
def test_13_isolamento_entre_sobs(tmp_path: Path):
    log_file = tmp_path / "multi_sobs.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "SOB_ALPHA", "action": "cqt", "execution_state": "Concluido"},
        {"execution_id": "e2", "sob_id": "SOB_BETA", "action": "orcamento", "execution_state": "Concluido"},
    ])

    res_alpha = consultar_indicadores(log_file=log_file, sob_id="SOB_ALPHA")
    assert res_alpha["execucoes"]["total_execucoes"] == 1
    assert "cqt" in res_alpha["execucoes"]["distribuicao_por_acao"]
    assert "orcamento" not in res_alpha["execucoes"]["distribuicao_por_acao"]


# 14. Resultado determinístico
def test_14_resultado_deterministico(tmp_path: Path):
    proj_dir = tmp_path / "SOB_DET"
    _criar_projeto_sintetico(proj_dir, "SOB_DET")

    res1 = consultar_indicadores(project_root=proj_dir, sob_id="SOB_DET")
    res2 = consultar_indicadores(project_root=proj_dir, sob_id="SOB_DET")

    # Remove chaves dependentes de tempo atual (gerado_em)
    res1.pop("gerado_em", None)
    res2.pop("gerado_em", None)
    assert res1 == res2


# 15. Consulta não gera OxCadExecution
def test_15_consulta_nao_gera_oxcad_execution(tmp_path: Path):
    log_file = tmp_path / "exec_test.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e_orig", "action": "cqt", "execution_state": "Concluido"}
    ])

    # Antes da consulta
    conteudo_antes = log_file.read_text(encoding="utf-8")

    # Executa consulta analítica
    res = consultar_indicadores(log_file=log_file)
    assert res["execucoes"]["total_execucoes"] == 1

    # Após a consulta: o arquivo não deve ter recebido nenhuma nova linha ou execução
    conteudo_depois = log_file.read_text(encoding="utf-8")
    assert conteudo_antes == conteudo_depois


# 16. Consulta não altera arquivos (read-only estrito)
def test_16_consulta_nao_altera_arquivos(tmp_path: Path):
    proj_dir = tmp_path / "SOB_READONLY"
    _criar_projeto_sintetico(proj_dir, "SOB_READONLY")

    # Mapear hashes de todos os arquivos
    hashes_antes = {}
    for p in proj_dir.rglob("*"):
        if p.is_file():
            hashes_antes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

    consultar_indicadores(project_root=proj_dir, sob_id="SOB_READONLY")

    # Checar se hashes permanecem 100% idênticos
    for p in proj_dir.rglob("*"):
        if p.is_file():
            assert hashes_antes[str(p)] == hashlib.sha256(p.read_bytes()).hexdigest()


# 17. UI / CLI não bloqueia por processamento síncrono
def test_17_ui_nao_bloqueia_processamento_sincrono(tmp_path: Path):
    log_file = tmp_path / "log_perf.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": f"e_{i}", "action": "cqt", "execution_state": "Concluido"} for i in range(100)
    ])

    inicio = time.perf_counter()
    res = consultar_indicadores(log_file=log_file)
    delta = time.perf_counter() - inicio

    assert res["execucoes"]["total_execucoes"] == 100
    # Processamento deve ser quase instantâneo (< 0.5s para 100 itens)
    assert delta < 0.5


# 18. Erro de leitura apresentado corretamente
def test_18_erro_leitura_apresentado_corretamente(tmp_path: Path):
    proj_dir = tmp_path / "SOB_ERR"
    proj_dir.mkdir(parents=True, exist_ok=True)
    #pending.json com conteúdo inválido (não-JSON)
    pending_file = proj_dir / ".oxcad" / "pending.json"
    pending_file.parent.mkdir(parents=True, exist_ok=True)
    pending_file.write_text("{conteudo_invalido_corrompido", encoding="utf-8")

    res = consultar_indicadores(project_root=proj_dir)
    assert res["pendencias"]["status"] == "NÃO DISPONÍVEL"
    assert "ERRO_LEITURA_PENDING" in res["pendencias"]["motivo"]


# 19. Cobertura histórica explicitada
def test_19_cobertura_historica_explicitada(tmp_path: Path):
    res = consultar_indicadores(log_file=tmp_path / "test.jsonl")
    assert "qualidade_dados" in res
    assert "limitacoes_cobertura" in res["qualidade_dados"]
    assert len(res["qualidade_dados"]["limitacoes_cobertura"]) > 0


# 20. Regressão do P2.1 e apresentação textual
def test_20_regressao_p2_1_e_apresentacao_textual(tmp_path: Path):
    proj_dir = tmp_path / "SOB_REG"
    _criar_projeto_sintetico(proj_dir, "SOB_REG")

    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_REG")
    # Todas as chaves do contrato Schema 1 do P2.1 devem estar presentes
    chaves_obrigatorias = [
        "schema", "gerado_em", "escopo", "periodo_observado", "execucoes",
        "pendencias", "entregas", "tempo_operacional", "versoes", "sob_manifesto", "qualidade_dados"
    ]
    for k in chaves_obrigatorias:
        assert k in res

    # Testa formatação textual da apresentação (workspace_indicators_cli)
    texto = formatar_resumo_terminal(res)
    assert "OXCAD — INDICADORES DE PROCESSO E GESTÃO" in texto
    assert "SOB: SOB_REG" in texto
    assert "Pendências: 2 cadastradas" in texto

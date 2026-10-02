# -*- coding: utf-8 -*-
"""
Suíte de testes automatizados para o P2.3 — Qualidade, Histórico e Comparabilidade dos Indicadores.
Cobre exaustivamente os 20 cenários contratuais obrigatórios com dados sintéticos:
1. cobertura completa;
2. cobertura parcial;
3. log limitado por rotação;
4. fonte ausente;
5. fonte corrompida;
6. fonte persistente válida;
7. proveniência correta;
8. período observado;
9. registros descartados;
10. motivo de descarte;
11. comparação válida;
12. comparação inválida por cobertura;
13. comparação inválida por identidade;
14. comparação com fonte ausente;
15. filtro preservado na comparação;
16. determinismo;
17. consulta continua read-only;
18. consulta não cria execução;
19. CLI preserva compatibilidade;
20. UI continua não bloqueante.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from workspace.workspace_indicators import consultar_indicadores, IndicadoresAnalyzer
from workspace.workspace_indicator_quality import (
    COBERTURA_COMPLETA,
    COBERTURA_FONTE_INDISPONIVEL,
    COBERTURA_IDENTIDADE_NAO_VERIFICAVEL,
    COBERTURA_LIMITADA_POR_ROTACAO,
    COBERTURA_PARCIAL,
    COBERTURA_SEM_DADOS,
    PROVENIENCIA_FONTES,
    comparar_indicadores,
)


def _escrever_jsonl(path: Path, records: list):
    linhas = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _criar_projeto_completo(base_dir: Path, sob_id: str = "A057526153") -> Path:
    proj_dir = base_dir / sob_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    # .sob_state.json
    sob_state = {
        "sob_id": sob_id,
        "status": "CONCLUÍDO",
        "duracao_segundos": 15.0,
        "data_inicio": "2026-10-01T10:00:00Z",
        "data_fim": "2026-10-01T10:00:15Z",
    }
    (proj_dir / ".sob_state.json").write_text(json.dumps(sob_state), encoding="utf-8")

    # .oxcad/pending.json
    oxcad_dir = proj_dir / ".oxcad"
    oxcad_dir.mkdir(exist_ok=True)
    pending = {
        "schema": 1,
        "sob_id": sob_id,
        "items": [
            {"id": "p1", "status": "ABERTA", "severity": "ALTA"},
            {"id": "p2", "status": "RESOLVIDA", "severity": "MEDIA"},
        ],
    }
    (oxcad_dir / "pending.json").write_text(json.dumps(pending), encoding="utf-8")

    # .oxcad/deliveries/
    deliv_dir = oxcad_dir / "deliveries" / "pkg_01"
    deliv_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"sob_id": sob_id, "package_id": "pkg_01"}
    (deliv_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (deliv_dir / "manifest.sha256").write_text("dummyhash", encoding="utf-8")
    (deliv_dir / "approval.json").write_text(json.dumps({"approved": True}), encoding="utf-8")

    # .oxcad/time.json
    time_data = {
        "sob_id": sob_id,
        "estado": "Finalizado",
        "tempo_acumulado_segundos": 3600.0,
        "sessoes": [{"inicio": "2026-10-01T10:00:00Z", "fim": "2026-10-01T11:00:00Z"}],
    }
    (oxcad_dir / "time.json").write_text(json.dumps(time_data), encoding="utf-8")

    # .auxcad_versions/
    vers_dir = proj_dir / ".auxcad_versions" / "snap_1"
    vers_dir.mkdir(parents=True, exist_ok=True)
    (vers_dir / "manifest.json").write_text(json.dumps({"version": 1}), encoding="utf-8")

    return proj_dir


# 1. Cobertura completa
def test_01_cobertura_completa(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {
            "execution_id": "exec-1",
            "action": "cqt",
            "execution_state": "Concluido",
            "sob_id": "A057526153",
            "timestamp": "2026-10-01T10:05:00Z",
            "duration_ms": 1000.0,
        }
    ])

    res = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)
    assert res["qualidade_dados"]["cobertura"] == COBERTURA_COMPLETA
    assert res["execucoes"]["status"] == "OK"
    assert res["pendencias"]["status"] == "OK"
    assert res["entregas"]["status"] == "OK"
    assert res["tempo_operacional"]["status"] == "OK"


# 2. Cobertura parcial
def test_02_cobertura_parcial(tmp_path: Path):
    proj_dir = tmp_path / "SOB_PARCIAL"
    proj_dir.mkdir()
    (proj_dir / ".sob_state.json").write_text(json.dumps({"sob_id": "SOB_PARCIAL"}), encoding="utf-8")
    # sem pasta .oxcad (fontes duráveis ausentes)
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {
            "execution_id": "exec-1",
            "action": "cqt",
            "execution_state": "Concluido",
            "sob_id": "SOB_PARCIAL",
            "timestamp": "2026-10-01T10:05:00Z",
        }
    ])

    res = consultar_indicadores(project_root=proj_dir, sob_id="SOB_PARCIAL", log_file=log_file)
    assert res["qualidade_dados"]["cobertura"] == COBERTURA_PARCIAL
    assert ".oxcad/pending.json" in res["qualidade_dados"]["fontes_ausentes"]


# 3. Log limitado por rotação
def test_03_log_limitado_por_rotacao(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {
            "execution_id": "exec-1",
            "action": "cqt",
            "execution_state": "Concluido",
            "sob_id": "A057526153",
            "timestamp": "2026-10-01T12:00:00Z",
        }
    ])

    # Solicitar período inicial anterior ao primeiro timestamp disponível no log
    res = consultar_indicadores(
        project_root=proj_dir,
        sob_id="A057526153",
        log_file=log_file,
        periodo_inicio="2026-09-01T00:00:00Z",
    )
    assert res["qualidade_dados"]["cobertura"] == COBERTURA_LIMITADA_POR_ROTACAO


# 4. Fonte ausente
def test_04_fonte_ausente(tmp_path: Path):
    log_inexistente = tmp_path / "nao_existe.jsonl"
    res = consultar_indicadores(log_file=log_inexistente)
    assert res["qualidade_dados"]["cobertura"] == COBERTURA_FONTE_INDISPONIVEL
    assert str(log_inexistente) in res["qualidade_dados"]["fontes_ausentes"]


# 5. Fonte corrompida
def test_05_fonte_corrompida(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "corrupt.jsonl"
    log_file.write_text("linha-invalida-sem-json\n{\"execution_id\": \"exec-1\", \"sob_id\": \"A057526153\", \"execution_state\": \"Concluido\", \"timestamp\": \"2026-10-01T10:00:00Z\"}\n", encoding="utf-8")

    res = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)
    assert res["qualidade_dados"]["linhas_invalidas_log"] == 1
    assert res["qualidade_dados"]["descartes_por_motivo"]["LINHA_CORROMPIDA"] == 1
    assert res["qualidade_dados"]["cobertura"] == COBERTURA_PARCIAL


# 6. Fonte persistente válida
def test_06_fonte_persistente_valida(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    res = consultar_indicadores(project_root=proj_dir, sob_id="A057526153")
    assert res["pendencias"]["status"] == "OK"
    assert res["pendencias"]["total"] == 2
    assert res["entregas"]["status"] == "OK"
    assert res["entregas"]["total_pacotes"] == 1
    assert res["tempo_operacional"]["tempo_acumulado_segundos"] == 3600.0


# 7. Proveniência correta
def test_07_proveniencia_correta(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"}
    ])

    res = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)
    assert res["proveniencia"] == PROVENIENCIA_FONTES
    assert res["execucoes"]["proveniencia"] == "logs/application.jsonl"
    assert res["pendencias"]["proveniencia"] == ".oxcad/pending.json"
    assert res["entregas"]["proveniencia"] == ".oxcad/deliveries/"
    assert res["tempo_operacional"]["proveniencia"] == ".oxcad/time.json"
    assert res["versoes"]["proveniencia"] == ".auxcad_versions/"
    assert res["sob_manifesto"]["proveniencia"] == ".sob_state.json"


# 8. Período observado
def test_08_periodo_observado(tmp_path: Path):
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "SOB1", "timestamp": "2026-10-01T10:00:00Z", "execution_state": "Concluido"},
        {"execution_id": "e2", "sob_id": "SOB1", "timestamp": "2026-10-03T10:00:00Z", "execution_state": "Concluido"},
    ])

    res = consultar_indicadores(sob_id="SOB1", log_file=log_file)
    per = res["periodo_observado"]
    assert per["inicio"] == "2026-10-01T10:00:00Z"
    assert per["fim"] == "2026-10-03T10:00:00Z"
    assert per["duracao_dias"] == 2.0


# 9. Registros descartados
def test_09_registros_descartados(tmp_path: Path):
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "SOB1", "action": "cqt", "timestamp": "2026-10-01T10:00:00Z", "execution_state": "Concluido"},
        {"execution_id": "e2", "sob_id": "SOB1", "action": "orcamento", "timestamp": "2026-10-01T11:00:00Z", "execution_state": "Concluido"},
    ])

    # Filtro por ação cqt deve aceitar 1 e descartar 1
    res = consultar_indicadores(sob_id="SOB1", log_file=log_file, acao="cqt")
    qual = res["qualidade_dados"]
    assert qual["registros_considerados"] == 1
    assert qual["registros_descartados"] >= 1
    assert qual["descartes_por_motivo"]["FILTRO_ACAO"] == 1


# 10. Motivo de descarte
def test_10_motivo_de_descarte(tmp_path: Path):
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "SOB1", "timestamp": "2026-09-01T10:00:00Z", "execution_state": "Concluido"}, # Fora do período
        {"execution_id": "e2", "sob_id": "SOB2", "timestamp": "2026-10-01T10:00:00Z", "execution_state": "Concluido"}, # SOB diferente
        {"no_exec_id": "teste"},                                                                                          # Sem execution_id
    ])

    res = consultar_indicadores(
        sob_id="SOB1",
        log_file=log_file,
        periodo_inicio="2026-10-01T00:00:00Z",
    )
    descartes = res["qualidade_dados"]["descartes_por_motivo"]
    assert descartes["FILTRO_PERIODO"] >= 1
    assert descartes["FILTRO_SOB"] >= 1
    assert descartes["SEM_EXECUTION_ID"] >= 1


# 11. Comparação válida
def test_11_comparacao_valida(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "action": "cqt", "execution_state": "Concluido", "duration_ms": 1000.0, "timestamp": "2026-10-01T10:00:00Z"},
        {"execution_id": "e2", "sob_id": "A057526153", "action": "cqt", "execution_state": "Concluido", "duration_ms": 2000.0, "timestamp": "2026-10-02T10:00:00Z"},
    ])

    res = consultar_indicadores(
        project_root=proj_dir,
        sob_id="A057526153",
        log_file=log_file,
        periodo_inicio="2026-10-01T00:00:00Z",
        periodo_fim="2026-10-01T23:59:59Z",
        comparar_inicio="2026-10-02T00:00:00Z",
        comparar_fim="2026-10-02T23:59:59Z",
    )

    assert "comparacao" in res
    comp = res["comparacao"]
    assert comp["status"] == "VALIDA"
    assert comp["comparavel"] is True
    assert comp["motivo"] is None
    deltas = comp["deltas"]
    assert "total_execucoes" in deltas
    assert deltas["total_execucoes"]["base"] == 1
    assert deltas["total_execucoes"]["comparado"] == 1
    assert deltas["total_execucoes"]["delta_absoluto"] == 0.0


# 12. Comparação inválida por cobertura
def test_12_comparacao_invalida_por_cobertura(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "timestamp": "2026-10-01T10:00:00Z", "execution_state": "Concluido"}
    ])

    # Período comparado ultrapassa o log para trás (LIMITADA_POR_ROTACAO)
    res = consultar_indicadores(
        project_root=proj_dir,
        sob_id="A057526153",
        log_file=log_file,
        periodo_inicio="2026-10-01T00:00:00Z",
        periodo_fim="2026-10-01T23:59:59Z",
        comparar_inicio="2026-08-01T00:00:00Z",
        comparar_fim="2026-08-31T23:59:59Z",
    )

    comp = res.get("comparacao", {})
    assert comp["status"] == "NAO_DETERMINADA"
    assert comp["comparavel"] is False
    assert comp["motivo"] == "LIMITADA_POR_ROTACAO"


# 13. Comparação inválida por identidade
def test_13_comparacao_invalida_por_identidade(tmp_path: Path):
    rel1 = {
        "escopo": {"tipo": "PROJETO", "sob_id": "SOB_A", "status_identidade": "VALIDA"},
        "qualidade_dados": {"cobertura": "COMPLETA", "fontes_utilizadas": ["logs/application.jsonl"]},
    }
    rel2 = {
        "escopo": {"tipo": "PROJETO", "sob_id": "SOB_B", "status_identidade": "VALIDA"},
        "qualidade_dados": {"cobertura": "COMPLETA", "fontes_utilizadas": ["logs/application.jsonl"]},
    }

    comp = comparar_indicadores(rel1, rel2)
    assert comp["status"] == "NAO_DETERMINADA"
    assert comp["comparavel"] is False
    assert comp["motivo"] == "ESCOPO_OU_IDENTIDADE_DIVERGENTE"


# 14. Comparação com fonte ausente
def test_14_comparacao_com_fonte_ausente(tmp_path: Path):
    rel1 = {
        "escopo": {"tipo": "PROJETO", "sob_id": "SOB_A", "status_identidade": "VALIDA"},
        "qualidade_dados": {"cobertura": "FONTE_INDISPONIVEL", "fontes_utilizadas": []},
    }
    rel2 = {
        "escopo": {"tipo": "PROJETO", "sob_id": "SOB_A", "status_identidade": "VALIDA"},
        "qualidade_dados": {"cobertura": "COMPLETA", "fontes_utilizadas": ["logs/application.jsonl"]},
    }

    comp = comparar_indicadores(rel1, rel2)
    assert comp["status"] == "NAO_DETERMINADA"
    assert comp["comparavel"] is False
    assert comp["motivo"] == "FONTE_INDISPONIVEL"


# 15. Filtro preservado na comparação
def test_15_filtro_preservado_na_comparacao(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"},
        {"execution_id": "e2", "sob_id": "A057526153", "action": "orcamento", "execution_state": "Concluido", "timestamp": "2026-10-01T11:00:00Z"},
        {"execution_id": "e3", "sob_id": "A057526153", "action": "cqt", "execution_state": "Concluido", "timestamp": "2026-10-02T10:00:00Z"},
    ])

    res = consultar_indicadores(
        project_root=proj_dir,
        sob_id="A057526153",
        log_file=log_file,
        acao="cqt",
        periodo_inicio="2026-10-01T00:00:00Z",
        periodo_fim="2026-10-01T23:59:59Z",
        comparar_inicio="2026-10-02T00:00:00Z",
        comparar_fim="2026-10-02T23:59:59Z",
    )

    deltas = res["comparacao"]["deltas"]
    assert deltas["total_execucoes"]["base"] == 1
    assert deltas["total_execucoes"]["comparado"] == 1


# 16. Determinismo
def test_16_determinismo(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"}
    ])

    res1 = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)
    res2 = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)

    # Remover timestamp gerado_em
    res1.pop("gerado_em")
    res2.pop("gerado_em")
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)


# 17. Consulta continua read-only
def test_17_consulta_continua_read_only(tmp_path: Path):
    proj_dir = _criar_projeto_completo(tmp_path, "A057526153")
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"}
    ])

    def calc_hashes():
        h = {}
        for p in proj_dir.rglob("*"):
            if p.is_file():
                h[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        h[str(log_file)] = hashlib.sha256(log_file.read_bytes()).hexdigest()
        return h

    hashes_antes = calc_hashes()
    _ = consultar_indicadores(project_root=proj_dir, sob_id="A057526153", log_file=log_file)
    hashes_depois = calc_hashes()

    assert hashes_antes == hashes_depois


# 18. Consulta não cria execução
def test_18_consulta_nao_cria_execucao(tmp_path: Path):
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"}
    ])
    linhas_antes = log_file.read_text(encoding="utf-8").strip().splitlines()

    _ = consultar_indicadores(sob_id="A057526153", log_file=log_file)
    linhas_depois = log_file.read_text(encoding="utf-8").strip().splitlines()

    assert len(linhas_antes) == len(linhas_depois)


# 19. CLI preserva compatibilidade
def test_19_cli_preserva_compatibilidade(tmp_path: Path):
    log_file = tmp_path / "app.jsonl"
    _escrever_jsonl(log_file, [
        {"execution_id": "e1", "sob_id": "A057526153", "execution_state": "Concluido", "timestamp": "2026-10-01T10:00:00Z"}
    ])

    cli_script = Path(__file__).resolve().parent.parent / "workspace" / "workspace_indicators_cli.py"

    # 1. Formato JSON com novos parâmetros de comparação
    cmd = [
        sys.executable,
        str(cli_script),
        "--sob", "A057526153",
        "--log-file", str(log_file),
        "--start-date", "2026-10-01T00:00:00Z",
        "--end-date", "2026-10-01T23:59:59Z",
        "--compare-start", "2026-10-02T00:00:00Z",
        "--compare-end", "2026-10-02T23:59:59Z",
        "--format", "json",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.returncode == 0
    saida = json.loads(proc.stdout)
    assert saida["schema"] == 1
    assert "comparacao" in saida

    # 2. Formato text/summary
    cmd_text = [
        sys.executable,
        str(cli_script),
        "--sob", "A057526153",
        "--log-file", str(log_file),
        "--format", "summary",
    ]
    proc_text = subprocess.run(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc_text.returncode == 0
    assert "OXCAD — INDICADORES DE PROCESSO E GESTÃO" in proc_text.stdout
    assert "Cobertura Histórica:" in proc_text.stdout


# 20. UI continua não bloqueante
def test_20_ui_continua_nao_bloqueante():
    service_path = Path(__file__).resolve().parent.parent / "oxcad" / "WorkspaceService.cs"
    conteudo = service_path.read_text(encoding="utf-8")

    assert "public static async Task<string> ConsultarIndicadoresJsonAsync" in conteudo
    assert "return await Task.Run(" in conteudo
    assert "OxCadExecutionRegistry.Start" not in conteudo.split("ConsultarIndicadoresJsonAsync")[1].split("public static")[0]

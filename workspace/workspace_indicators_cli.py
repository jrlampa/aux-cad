# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Camada de Consulta e Apresentação de Indicadores (P2.2).
Responsabilidade única: Interface CLI e formatador de apresentação para consulta
operacional de indicadores de processo e gestão (SOB / Workspace).

Diretrizes:
- Totalmente read-only, desacoplado do ciclo de execução operacional OxCadExecution;
- Suporte a saídas JSON estruturado (consumo por APIs/WPF) e resumo textual legível;
- Explicitação de limitações temporais e observabilidade dos logs rotativos;
- Zero ranking individual, zero avaliação de desempenho pessoal.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Import defensivo do motor analítico
try:
    from workspace.workspace_indicators import consultar_indicadores
except ImportError:
    from workspace_indicators import consultar_indicadores


def formatar_resumo_terminal(dados: Dict[str, Any]) -> str:
    """Gera uma apresentação textual amigável e concisa dos indicadores."""
    linhas = []
    escopo = dados.get("escopo", {})
    tipo = escopo.get("tipo", "PROJETO")
    sob_id = escopo.get("sob_id") or "-"
    status_id = escopo.get("status_identidade", "NÃO VERIFICADO")

    linhas.append("=" * 64)
    linhas.append(f" OXCAD — INDICADORES DE PROCESSO E GESTÃO (P2.2)")
    linhas.append("=" * 64)
    linhas.append(f" Escopo: {tipo} | SOB: {sob_id} | Identidade: {status_id}")

    if escopo.get("total_projetos_observados", 0) > 1:
        linhas.append(f" Projetos no Workspace: {escopo.get('total_projetos_observados')}")

    periodo = dados.get("periodo_observado", {})
    p_ini = periodo.get("inicio") or "N/D"
    p_fim = periodo.get("fim") or "N/D"
    linhas.append(f" Período Observado: {p_ini} até {p_fim}")
    linhas.append("-" * 64)

    # Execuções
    execs = dados.get("execucoes", {})
    st_exec = execs.get("status", "N/D")
    if st_exec == "OK":
        tot = execs.get("total_execucoes", 0)
        conc = execs.get("concluidas", 0)
        falhas = execs.get("falhas", 0)
        canc = execs.get("canceladas", 0)
        taxa = execs.get("taxa_conclusao_pct")
        taxa_str = f"{taxa:.1f}%" if taxa is not None else "N/D"
        dur = execs.get("duracao_ms", {})
        p95 = dur.get("p95_ms")
        p95_str = f"{p95 / 1000.0:.2f}s" if p95 is not None else "N/D"
        med = dur.get("mediana_ms")
        med_str = f"{med / 1000.0:.2f}s" if med is not None else "N/D"

        linhas.append(f" Execuções Totais: {tot} | Concluídas: {conc} ({taxa_str})")
        linhas.append(f" Falhas: {falhas} | Canceladas: {canc} | Duração Mediana: {med_str} | P95: {p95_str}")
        dist = execs.get("distribuicao_por_acao") or {}
        if dist:
            dist_str = ", ".join([f"{k}: {v}" for k, v in dist.items()])
            linhas.append(f" Distribuição por Ação: {dist_str}")
    elif st_exec == "SEM_DADOS":
        linhas.append(" Execuções: Nenhuma execução registrada para o filtro informado.")
    else:
        linhas.append(f" Execuções: NÃO DISPONÍVEL ({execs.get('motivo', 'Desconhecido')})")

    linhas.append("-" * 64)

    # Pendências
    pends = dados.get("pendencias", {})
    st_pend = pends.get("status", "N/D")
    if st_pend == "OK":
        tot_p = pends.get("total", 0)
        ab_p = pends.get("abertas", 0)
        res_p = pends.get("resolvidas", 0)
        tx_p = pends.get("taxa_resolucao_pct")
        tx_p_str = f"{tx_p:.1f}%" if tx_p is not None else "N/D"
        linhas.append(f" Pendências: {tot_p} cadastradas | Abertas: {ab_p} | Resolvidas: {res_p} ({tx_p_str})")
    elif st_pend == "SEM_DADOS":
        linhas.append(" Pendências: Nenhuma pendência registrada.")
    else:
        linhas.append(f" Pendências: NÃO DISPONÍVEL ({pends.get('motivo', 'N/D')})")

    # Entregas
    deliv = dados.get("entregas", {})
    st_del = deliv.get("status", "N/D")
    if st_del == "OK":
        tot_d = deliv.get("total_pacotes", 0)
        apr_d = deliv.get("aprovados", 0)
        rev_d = deliv.get("revogados", 0)
        pend_d = deliv.get("pendentes_aprovacao", 0)
        linhas.append(f" Entregas: {tot_d} pacotes | Aprovados: {apr_d} | Revogados: {rev_d} | Pendentes: {pend_d}")
    elif st_del == "SEM_DADOS":
        linhas.append(" Entregas: Nenhum pacote de entrega registrado.")
    else:
        linhas.append(f" Entregas: NÃO DISPONÍVEL ({deliv.get('motivo', 'N/D')})")

    # Tempo Operacional
    tempo = dados.get("tempo_operacional", {})
    st_tmp = tempo.get("status", "N/D")
    if st_tmp == "OK":
        fmt = tempo.get("tempo_acumulado_formatado", "00:00:00")
        sess = tempo.get("total_sessoes", 0)
        linhas.append(f" Tempo Operacional: {fmt} acumulado ({sess} sessões)")

    linhas.append("-" * 64)

    # Qualidade e Limitações
    qualidade = dados.get("qualidade_dados", {})
    limitacoes = qualidade.get("limitacoes_cobertura", [])
    if limitacoes:
        linhas.append(" Limitações de Cobertura Observadas:")
        for lim in limitacoes:
            linhas.append(f"  • {lim}")

    linhas.append("=" * 64)
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description="OXCAD — Camada de Apresentação e Consulta de Indicadores (P2.2)")
    parser.add_argument("--project-root", type=str, default=None, help="Caminho raiz da SOB/projeto")
    parser.add_argument("--sob", type=str, default=None, help="Identificador oficial da SOB")
    parser.add_argument("--workspace-root", type=str, default=None, help="Caminho raiz do workspace para consolidação")
    parser.add_argument("--action", type=str, default=None, help="Filtro por ação (ex: cqt, orcamento, sob)")
    parser.add_argument("--state", type=str, default=None, help="Filtro por estado final (ex: Concluido, Falhou)")
    parser.add_argument("--start-date", type=str, default=None, help="Data/hora inicial ISO (ex: 2026-10-01T00:00:00Z)")
    parser.add_argument("--end-date", type=str, default=None, help="Data/hora final ISO (ex: 2026-10-02T23:59:59Z)")
    parser.add_argument("--log-file", type=str, default=None, help="Caminho do log application.jsonl")
    parser.add_argument("--format", choices=["json", "text", "summary"], default="json", help="Formato de saída")
    parser.add_argument("--pretty", action="store_true", help="Formatar JSON com indentação")

    args = parser.parse_args()

    log_path = args.log_file
    if not log_path:
        default_log = Path(__file__).resolve().parent.parent / "logs" / "application.jsonl"
        if default_log.is_file():
            log_path = default_log

    resultado = consultar_indicadores(
        project_root=args.project_root,
        sob_id=args.sob,
        workspace_root=args.workspace_root,
        acao=args.action,
        estado=args.state,
        periodo_inicio=args.start_date,
        periodo_fim=args.end_date,
        log_file=log_path,
    )

    if args.format in ["text", "summary"]:
        print(formatar_resumo_terminal(resultado))
    else:
        if args.pretty:
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(resultado, ensure_ascii=False))

    sys.exit(0)


if __name__ == "__main__":
    main()

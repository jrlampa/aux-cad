# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Leitura Defensiva de Fontes Persistentes de Indicadores (P2.1 / P2.2 / P2.3).
Responsabilidade única: Leitura read-only, resiliente e auditável de artefatos duráveis
(.oxcad/pending.json, .oxcad/deliveries/, .oxcad/time.json, .auxcad_versions/, .sob_state.json).

Diretrizes:
- Totalmente read-only: nenhuma escrita em disco, nenhuma alteração de arquivos;
- Zero dados mockados: consumo exclusivo de dados existentes em disco;
- Tolerância a falhas e corrupções parciais com anotação em collector de qualidade;
- Ausência de banco de dados ou caches persistentes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from workspace.workspace_indicator_quality import PROVENIENCIA_FONTES, QualityMetricsCollector
except ImportError:
    from workspace_indicator_quality import PROVENIENCIA_FONTES, QualityMetricsCollector


def formatar_segundos_hhmmss(segundos: Optional[Union[int, float]]) -> Optional[str]:
    if segundos is None:
        return None
    seg = max(0, int(round(segundos)))
    return f"{seg // 3600:02d}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"


def bloco_nao_disponivel(motivo: str, campos: Dict[str, Any], proveniencia: Optional[str] = None) -> Dict[str, Any]:
    res = {"status": "NÃO DISPONÍVEL", "motivo": motivo}
    if proveniencia:
        res["proveniencia"] = proveniencia
    res.update(campos)
    return res


def processar_pending(root: Path, sob_resolvida: Optional[str], collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Lê defensivamente o store autoritativo de pendências (.oxcad/pending.json)."""
    store_file = root / ".oxcad" / "pending.json"
    if not store_file.is_file():
        collector.registrar_fonte_ausente(".oxcad/pending.json")
        return bloco_nao_disponivel("ARQUIVO_PENDING_NAO_ENCONTRADO", {
            "total": None, "abertas": None, "em_andamento": None,
            "resolvidas": None, "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None,
        }, proveniencia=PROVENIENCIA_FONTES["pendencias"])

    try:
        data = json.loads(store_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("items"), list):
            collector.registrar_fonte_invalida(".oxcad/pending.json")
            return bloco_nao_disponivel("ARQUIVO_PENDING_INVALIDO", {
                "total": None, "abertas": None, "em_andamento": None,
                "resolvidas": None, "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None,
            }, proveniencia=PROVENIENCIA_FONTES["pendencias"])

        store_sob = str(data.get("sob_id", "")).strip().upper() if data.get("sob_id") else None
        if sob_resolvida and store_sob and store_sob != sob_resolvida:
            return bloco_nao_disponivel("SOB_ID_MISMATCH", {
                "total": None, "abertas": None, "em_andamento": None,
                "resolvidas": None, "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None,
            }, proveniencia=PROVENIENCIA_FONTES["pendencias"])

        collector.registrar_fonte_utilizada(".oxcad/pending.json")
        items = data["items"]
        total = len(items)
        abertas, em_andamento, resolvidas, descartadas = 0, 0, 0, 0
        por_severidade = {"BAIXA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0}

        for item in items:
            if not isinstance(item, dict):
                continue
            st = item.get("status")
            if st == "ABERTA":
                abertas += 1
            elif st == "EM_ANDAMENTO":
                em_andamento += 1
            elif st == "RESOLVIDA":
                resolvidas += 1
            elif st == "DESCARTADA":
                descartadas += 1

            sev = str(item.get("severity", "")).upper()
            if sev in por_severidade:
                por_severidade[sev] += 1

        ativas_e_resolvidas = abertas + em_andamento + resolvidas
        taxa = round((resolvidas / ativas_e_resolvidas * 100.0), 2) if ativas_e_resolvidas > 0 else None

        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES["pendencias"],
            "total": total,
            "abertas": abertas,
            "em_andamento": em_andamento,
            "resolvidas": resolvidas,
            "descartadas": descartadas,
            "taxa_resolucao_pct": taxa,
            "por_severidade": por_severidade,
        }
    except Exception as ex:
        collector.registrar_fonte_invalida(".oxcad/pending.json")
        return bloco_nao_disponivel(f"ERRO_LEITURA_PENDING: {ex}", {
            "total": None, "abertas": None, "em_andamento": None,
            "resolvidas": None, "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None,
        }, proveniencia=PROVENIENCIA_FONTES["pendencias"])


def processar_deliveries(root: Path, sob_resolvida: Optional[str], collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Lê defensivamente o store de pacotes de entrega (.oxcad/deliveries/)."""
    store_dir = root / ".oxcad" / "deliveries"
    if not store_dir.is_dir():
        collector.registrar_fonte_ausente(".oxcad/deliveries/")
        return bloco_nao_disponivel("DIRETORIO_DELIVERIES_NAO_ENCONTRADO", {
            "total_pacotes": None, "aprovados": None, "revogados": None, "pendentes_aprovacao": None, "integridade": None,
        }, proveniencia=PROVENIENCIA_FONTES["entregas"])

    try:
        total_pacotes, aprovados, revogados, pendentes = 0, 0, 0, 0
        confirmados, divergentes, invalidos = 0, 0, 0

        for entry in store_dir.iterdir():
            if not entry.is_dir():
                continue
            manifest_file = entry / "manifest.json"
            if not manifest_file.is_file():
                continue

            try:
                man_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                man_sob = str(man_data.get("sob_id", "")).strip().upper() if man_data.get("sob_id") else None
                if sob_resolvida and man_sob and man_sob != sob_resolvida:
                    continue
            except Exception:
                invalidos += 1
                continue

            total_pacotes += 1
            appr_file = entry / "approval.json"
            if appr_file.is_file():
                try:
                    appr_data = json.loads(appr_file.read_text(encoding="utf-8"))
                    if appr_data.get("approved") is True:
                        aprovados += 1
                    elif appr_data.get("approved") is False:
                        revogados += 1
                    else:
                        pendentes += 1
                except Exception:
                    invalidos += 1
            else:
                pendentes += 1

            if (entry / "manifest.sha256").is_file():
                confirmados += 1
            else:
                divergentes += 1

        collector.registrar_fonte_utilizada(".oxcad/deliveries/")
        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES["entregas"],
            "total_pacotes": total_pacotes,
            "aprovados": aprovados,
            "revogados": revogados,
            "pendentes_aprovacao": pendentes,
            "integridade": {
                "confirmados": confirmados,
                "divergentes": divergentes,
                "invalidos": invalidos,
            },
        }
    except Exception as ex:
        collector.registrar_fonte_invalida(".oxcad/deliveries/")
        return bloco_nao_disponivel(f"ERRO_LEITURA_DELIVERIES: {ex}", {
            "total_pacotes": None, "aprovados": None, "revogados": None, "pendentes_aprovacao": None, "integridade": None,
        }, proveniencia=PROVENIENCIA_FONTES["entregas"])


def processar_time(root: Path, sob_resolvida: Optional[str], collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Lê defensivamente o apontamento operacional de tempo (.oxcad/time.json)."""
    time_file = root / ".oxcad" / "time.json"
    if not time_file.is_file():
        collector.registrar_fonte_ausente(".oxcad/time.json")
        return bloco_nao_disponivel("ARQUIVO_TIME_NAO_ENCONTRADO", {
            "estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None,
        }, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"])

    try:
        data = json.loads(time_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            collector.registrar_fonte_invalida(".oxcad/time.json")
            return bloco_nao_disponivel("ARQUIVO_TIME_INVALIDO", {
                "estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None,
            }, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"])

        store_sob = str(data.get("sob_id", "")).strip().upper() if data.get("sob_id") else None
        if sob_resolvida and store_sob and store_sob != sob_resolvida:
            return bloco_nao_disponivel("SOB_ID_MISMATCH", {
                "estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None,
            }, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"])

        collector.registrar_fonte_utilizada(".oxcad/time.json")
        acumulado = data.get("tempo_acumulado_segundos")
        sessoes = data.get("sessoes")
        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES["tempo_operacional"],
            "estado": data.get("estado"),
            "tempo_acumulado_segundos": acumulado,
            "tempo_acumulado_formatado": formatar_segundos_hhmmss(acumulado),
            "total_sessoes": len(sessoes) if isinstance(sessoes, list) else 0,
        }
    except Exception as ex:
        collector.registrar_fonte_invalida(".oxcad/time.json")
        return bloco_nao_disponivel(f"ERRO_LEITURA_TIME: {ex}", {
            "estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None,
        }, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"])


def processar_versoes(root: Path, collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Conta snapshots de versão disponíveis em .auxcad_versions/."""
    vers_dir = root / ".auxcad_versions"
    if not vers_dir.is_dir():
        return {"status": "OK", "total_snapshots": 0, "proveniencia": PROVENIENCIA_FONTES["versoes"]}
    try:
        snapshots = [d for d in vers_dir.iterdir() if d.is_dir() and (d / "manifest.json").is_file()]
        collector.registrar_fonte_utilizada(".auxcad_versions/")
        return {"status": "OK", "total_snapshots": len(snapshots), "proveniencia": PROVENIENCIA_FONTES["versoes"]}
    except Exception as ex:
        collector.registrar_fonte_invalida(".auxcad_versions/")
        return bloco_nao_disponivel(f"ERRO_LEITURA_VERSOES: {ex}", {"total_snapshots": None}, proveniencia=PROVENIENCIA_FONTES["versoes"])


def processar_sob_state(root: Path, sob_resolvida: Optional[str], collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Lê defensivamente o manifesto de preparação de projeto (.sob_state.json)."""
    state_file = root / ".sob_state.json"
    if not state_file.is_file():
        collector.registrar_fonte_ausente(".sob_state.json")
        return bloco_nao_disponivel("MANIFESTO_SOB_NAO_ENCONTRADO", {
            "sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None,
        }, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"])

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            collector.registrar_fonte_invalida(".sob_state.json")
            return bloco_nao_disponivel("MANIFESTO_SOB_INVALIDO", {
                "sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None,
            }, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"])

        sob_id = str(data.get("sob_id", "")).strip().upper() if data.get("sob_id") else None
        if sob_resolvida and sob_id and sob_id != sob_resolvida:
            return bloco_nao_disponivel("SOB_ID_MISMATCH", {
                "sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None,
            }, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"])

        collector.registrar_fonte_utilizada(".sob_state.json")
        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES["sob_manifesto"],
            "sob_id": sob_id,
            "estado_preparacao": data.get("status"),
            "duracao_segundos": data.get("duracao_segundos"),
            "data_inicio": data.get("data_inicio"),
            "data_fim": data.get("data_fim"),
        }
    except Exception as ex:
        collector.registrar_fonte_invalida(".sob_state.json")
        return bloco_nao_disponivel(f"ERRO_LEITURA_MANIFESTO_SOB: {ex}", {
            "sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None,
        }, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"])


def processar_reviews(root: Path, sob_resolvida: Optional[str], collector: QualityMetricsCollector) -> Dict[str, Any]:
    """Lê defensivamente o store autoritativo de revisões técnicas (.oxcad/reviews.json)."""
    store_file = root / ".oxcad" / "reviews.json"
    if not store_file.is_file():
        return bloco_nao_disponivel("ARQUIVO_REVIEWS_NAO_ENCONTRADO", {
            "total_revisoes": None, "iniciadas": None, "aprovadas": None,
            "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None,
            "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None,
        }, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))

    try:
        data = json.loads(store_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("reviews"), list):
            collector.registrar_fonte_invalida(".oxcad/reviews.json")
            return bloco_nao_disponivel("ARQUIVO_REVIEWS_INVALIDO", {
                "total_revisoes": None, "iniciadas": None, "aprovadas": None,
                "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None,
                "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None,
            }, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))

        store_sob = str(data.get("sob_id", "")).strip().upper() if data.get("sob_id") else None
        if sob_resolvida and store_sob and store_sob != sob_resolvida:
            return bloco_nao_disponivel("SOB_ID_MISMATCH", {
                "total_revisoes": None, "iniciadas": None, "aprovadas": None,
                "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None,
                "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None,
            }, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))

        reviews = data["reviews"]
        collector.registrar_fonte_utilizada(".oxcad/reviews.json")

        iniciadas = sum(1 for r in reviews if r.get("status") in {"DRAFT", "IN_REVIEW"})
        aprovadas = sum(1 for r in reviews if r.get("status") == "APPROVED")
        alteracoes = sum(1 for r in reviews if r.get("status") == "CHANGES_REQUIRED")
        rejeitadas = sum(1 for r in reviews if r.get("status") == "REJECTED")
        canceladas = sum(1 for r in reviews if r.get("status") == "CANCELLED")
        substituidas = sum(1 for r in reviews if r.get("status") == "SUPERSEDED")

        findings_count = 0
        por_severidade = {"info": 0, "minor": 0, "major": 0, "critical": 0}
        entregas_count = 0

        for r in reviews:
            if r.get("delivery"):
                entregas_count += 1
            for f in r.get("findings", []):
                findings_count += 1
                sev = str(f.get("severity", "")).lower()
                if sev in por_severidade:
                    por_severidade[sev] += 1

        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"),
            "total_revisoes": len(reviews),
            "iniciadas": iniciadas,
            "aprovadas": aprovadas,
            "alteracoes_solicitadas": alteracoes,
            "rejeitadas": rejeitadas,
            "canceladas": canceladas,
            "substituidas": substituidas,
            "findings_total": findings_count,
            "findings_por_severidade": por_severidade,
            "entregas_vinculadas": entregas_count,
        }
    except Exception as ex:
        collector.registrar_fonte_invalida(".oxcad/reviews.json")
        return bloco_nao_disponivel(f"ERRO_LEITURA_REVIEWS: {ex}", {
            "total_revisoes": None, "iniciadas": None, "aprovadas": None,
            "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None,
            "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None,
        }, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))


def processar_workspace_consolidado(
    workspace_root: Optional[Path],
    collector: QualityMetricsCollector
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], List[str]]:
    """Consolida indicadores persistidos de múltiplos projetos sob workspace_root."""
    projetos_encontrados: List[Path] = []
    if workspace_root and workspace_root.is_dir():
        for item in workspace_root.iterdir():
            if item.is_dir() and ((item / ".sob_state.json").is_file() or (item / ".oxcad").is_dir()):
                projetos_encontrados.append(item)

    total_projetos = len(projetos_encontrados)
    sobs_observadas: List[str] = []

    if total_projetos == 0:
        collector.registrar_limitacao(
            "Nenhum diretório com manifesto de SOB (.sob_state.json) ou dados (.oxcad) localizado no workspace especificado."
        )
        vazio_pend = {
            "status": "SEM_DADOS", "proveniencia": PROVENIENCIA_FONTES["pendencias"], "total": 0, "abertas": 0, "em_andamento": 0,
            "resolvidas": 0, "descartadas": 0, "taxa_resolucao_pct": None,
            "por_severidade": {"BAIXA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0},
        }
        vazio_deliv = {
            "status": "SEM_DADOS", "proveniencia": PROVENIENCIA_FONTES["entregas"], "total_pacotes": 0, "aprovados": 0, "revogados": 0,
            "pendentes_aprovacao": 0, "integridade": {"confirmados": 0, "divergentes": 0, "invalidos": 0},
        }
        vazio_time = {
            "status": "SEM_DADOS", "proveniencia": PROVENIENCIA_FONTES["tempo_operacional"], "estado": None, "tempo_acumulado_segundos": 0.0,
            "tempo_acumulado_formatado": "00:00:00", "total_sessoes": 0,
        }
        vazio_vers = {"status": "SEM_DADOS", "proveniencia": PROVENIENCIA_FONTES["versoes"], "total_snapshots": 0}
        vazio_manifesto = {
            "status": "SEM_DADOS", "proveniencia": PROVENIENCIA_FONTES["sob_manifesto"], "total_projetos": 0, "sobs": [],
        }
        return vazio_pend, vazio_deliv, vazio_time, vazio_vers, vazio_manifesto, []

    tot_pend, abertas, em_andamento, resolvidas, descartadas = 0, 0, 0, 0, 0
    por_severidade = {"BAIXA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0}
    tot_pacotes, aprovados, revogados, pendentes = 0, 0, 0, 0
    confirmados, divergentes, invalidos = 0, 0, 0
    tempo_total_seg = 0.0
    tot_sessoes = 0
    tot_snapshots = 0

    for p_dir in projetos_encontrados:
        sob_nome = p_dir.name
        manifesto = p_dir / ".sob_state.json"
        if manifesto.is_file():
            try:
                c = json.loads(manifesto.read_text(encoding="utf-8"))
                sob_raw = c.get("sob_id")
                if sob_raw:
                    sob_nome = str(sob_raw).strip().upper()
            except Exception:
                pass
        sobs_observadas.append(sob_nome)

        p_pend = processar_pending(p_dir, None, collector)
        if p_pend.get("status") == "OK":
            tot_pend += p_pend.get("total") or 0
            abertas += p_pend.get("abertas") or 0
            em_andamento += p_pend.get("em_andamento") or 0
            resolvidas += p_pend.get("resolvidas") or 0
            descartadas += p_pend.get("descartadas") or 0
            for k, v in (p_pend.get("por_severidade") or {}).items():
                por_severidade[k] = por_severidade.get(k, 0) + v

        p_del = processar_deliveries(p_dir, None, collector)
        if p_del.get("status") == "OK":
            tot_pacotes += p_del.get("total_pacotes") or 0
            aprovados += p_del.get("aprovados") or 0
            revogados += p_del.get("revogados") or 0
            pendentes += p_del.get("pendentes_aprovacao") or 0
            integ = p_del.get("integridade") or {}
            confirmados += integ.get("confirmados", 0)
            divergentes += integ.get("divergentes", 0)
            invalidos += integ.get("invalidos", 0)

        p_time = processar_time(p_dir, None, collector)
        if p_time.get("status") == "OK":
            tempo_total_seg += float(p_time.get("tempo_acumulado_segundos") or 0.0)
            tot_sessoes += int(p_time.get("total_sessoes") or 0)

        p_vers = processar_versoes(p_dir, collector)
        if p_vers.get("status") == "OK":
            tot_snapshots += int(p_vers.get("total_snapshots") or 0)

    ativas_res = abertas + em_andamento + resolvidas
    taxa_pend = round((resolvidas / ativas_res * 100.0), 2) if ativas_res > 0 else None

    res_pend = {
        "status": "OK", "proveniencia": PROVENIENCIA_FONTES["pendencias"], "total": tot_pend, "abertas": abertas,
        "em_andamento": em_andamento, "resolvidas": resolvidas, "descartadas": descartadas, "taxa_resolucao_pct": taxa_pend,
        "por_severidade": por_severidade,
    }
    res_deliv = {
        "status": "OK", "proveniencia": PROVENIENCIA_FONTES["entregas"], "total_pacotes": tot_pacotes, "aprovados": aprovados,
        "revogados": revogados, "pendentes_aprovacao": pendentes,
        "integridade": {"confirmados": confirmados, "divergentes": divergentes, "invalidos": invalidos},
    }
    res_time = {
        "status": "OK", "proveniencia": PROVENIENCIA_FONTES["tempo_operacional"], "estado": "Consolidado",
        "tempo_acumulado_segundos": round(tempo_total_seg, 2),
        "tempo_acumulado_formatado": formatar_segundos_hhmmss(tempo_total_seg), "total_sessoes": tot_sessoes,
    }
    res_vers = {"status": "OK", "proveniencia": PROVENIENCIA_FONTES["versoes"], "total_snapshots": tot_snapshots}
    res_manifesto = {
        "status": "OK", "proveniencia": PROVENIENCIA_FONTES["sob_manifesto"], "total_projetos": total_projetos,
        "sobs": sorted(sobs_observadas),
    }

    return res_pend, res_deliv, res_time, res_vers, res_manifesto, sorted(sobs_observadas)

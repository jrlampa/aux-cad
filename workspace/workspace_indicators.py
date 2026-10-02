# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Indicadores de Gestão e Processo (P2.1 / P2.2 / P2.3).
Responsabilidade única: Motor analítico, determinístico, read-only e auditável
para agregação e cálculo de métricas de gestão a partir de dados já persistidos
(logs de execução, cadastros de pendências, entregas, tempo e manifestos de SOB).

Diretrizes obrigatórias:
- Zero efeitos colaterais: nenhuma escrita em disco, nenhuma alteração de estado;
- Zero inferência de histórico inexistente: dados ausentes reportados como NÃO DISPONÍVEL;
- Reconstrução obrigatória por execution_id para evitar inflação por transições múltiplas;
- Isolamento estrito de identidade por SOB;
- Tolerância a falhas na leitura linha a linha de logs (linhas corrompidas contabilizadas);
- Independência de serviços ou bancos de dados externos (apenas biblioteca padrão Python);
- Filtros analíticos: SOB, período temporal, ação e estado final da execução;
- Consolidação de workspace com múltiplos projetos ou workspace vazio;
- Classificação estrita de cobertura histórica e rastreamento de proveniência (P2.3);
- Comparabilidade metodológica entre períodos sem banco de dados (P2.3);
- Ausência de ranking de pessoas, produtividade individual ou atribuição individual.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from workspace.workspace_indicator_quality import (
        COBERTURA_COMPLETA,
        COBERTURA_FONTE_INDISPONIVEL,
        COBERTURA_IDENTIDADE_NAO_VERIFICAVEL,
        COBERTURA_LIMITADA_POR_ROTACAO,
        COBERTURA_PARCIAL,
        COBERTURA_SEM_DADOS,
        PROVENIENCIA_FONTES,
        QualityMetricsCollector,
        classificar_cobertura_historica,
        comparar_indicadores,
    )
    from workspace.workspace_indicator_stores import (
        bloco_nao_disponivel,
        formatar_segundos_hhmmss,
        processar_deliveries,
        processar_pending,
        processar_reviews,
        processar_sob_state,
        processar_time,
        processar_versoes,
        processar_workspace_consolidado,
    )
except ImportError:
    from workspace_indicator_quality import (
        COBERTURA_COMPLETA,
        COBERTURA_FONTE_INDISPONIVEL,
        COBERTURA_IDENTIDADE_NAO_VERIFICAVEL,
        COBERTURA_LIMITADA_POR_ROTACAO,
        COBERTURA_PARCIAL,
        COBERTURA_SEM_DADOS,
        PROVENIENCIA_FONTES,
        QualityMetricsCollector,
        classificar_cobertura_historica,
        comparar_indicadores,
    )
    from workspace_indicator_stores import (
        bloco_nao_disponivel,
        formatar_segundos_hhmmss,
        processar_deliveries,
        processar_pending,
        processar_reviews,
        processar_sob_state,
        processar_time,
        processar_versoes,
        processar_workspace_consolidado,
    )


# Versão oficial do schema do contrato
SCHEMA_VERSION = 1

# Padrão para validação básica de SOB_ID
_SOB_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]+$")


def _agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(timestamp_val: Optional[Union[str, datetime]]) -> Optional[datetime]:
    if not timestamp_val:
        return None
    if isinstance(timestamp_val, datetime):
        return timestamp_val if timestamp_val.tzinfo else timestamp_val.replace(tzinfo=timezone.utc)
    if not isinstance(timestamp_val, str):
        return None
    try:
        ts = timestamp_val.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalizar_sob_id(sob_id: Optional[str]) -> Optional[str]:
    if not sob_id or not isinstance(sob_id, str):
        return None
    candidato = sob_id.strip().upper()
    if not candidato or not _SOB_ID_REGEX.match(candidato):
        return None
    return candidato


def _calcular_estatisticas_duracao(valores_ms: List[float]) -> Dict[str, Optional[float]]:
    """Calcula deterministamente total, média, mediana e P95."""
    if not valores_ms:
        return {
            "total_ms": None,
            "media_ms": None,
            "mediana_ms": None,
            "p95_ms": None,
            "amostras": 0,
        }

    amostras = len(valores_ms)
    total = sum(valores_ms)
    media = total / amostras
    ordenados = sorted(valores_ms)

    if amostras % 2 == 1:
        mediana = ordenados[amostras // 2]
    else:
        mediana = (ordenados[amostras // 2 - 1] + ordenados[amostras // 2]) / 2.0

    if amostras == 1:
        p95 = ordenados[0]
    else:
        k = (amostras - 1) * 0.95
        f = math.floor(k)
        c = math.ceil(k)
        p95 = ordenados[int(k)] if f == c else ordenados[int(f)] * (c - k) + ordenados[int(c)] * (k - f)

    return {
        "total_ms": round(total, 2),
        "media_ms": round(media, 2),
        "mediana_ms": round(mediana, 2),
        "p95_ms": round(p95, 2),
        "amostras": amostras,
    }


@dataclass
class _ExecutionAggregate:
    execution_id: str
    sob_id: Optional[str] = None
    action: Optional[str] = None
    estado_final: str = "Iniciado"
    estados_vistos: List[str] = field(default_factory=list)
    duracao_ms: Optional[float] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    primeiro_timestamp: Optional[str] = None
    ultimo_timestamp: Optional[str] = None


class IndicadoresAnalyzer:
    """
    Analisador puramente read-only que extrai e agrega indicadores de gestão
    respeitando os limites de autoridade entre dados duráveis e logs rotativos.
    """

    def __init__(
        self,
        log_file: Optional[Union[str, Path]] = None,
        errors_file: Optional[Union[str, Path]] = None,
        project_root: Optional[Union[str, Path]] = None,
        sob_id: Optional[str] = None,
        periodo_inicio: Optional[Union[datetime, str]] = None,
        periodo_fim: Optional[Union[datetime, str]] = None,
        acao_filtro: Optional[str] = None,
        estado_filtro: Optional[str] = None,
        workspace_root: Optional[Union[str, Path]] = None,
    ):
        self.log_file = Path(log_file).resolve() if log_file else None
        self.errors_file = Path(errors_file).resolve() if errors_file else None
        self.project_root = Path(project_root).resolve() if project_root else None
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.sob_id_esperada = _normalizar_sob_id(sob_id) if sob_id else None
        self.periodo_inicio = _parse_iso(periodo_inicio)
        self.periodo_fim = _parse_iso(periodo_fim)
        self.acao_filtro = acao_filtro.strip().lower() if acao_filtro else None
        self.estado_filtro = estado_filtro.strip().lower() if estado_filtro else None

        self.collector = QualityMetricsCollector()

    @property
    def linhas_totais(self) -> int:
        return self.collector.linhas_totais

    @property
    def linhas_validas(self) -> int:
        return self.collector.linhas_validas

    @property
    def linhas_invalidas(self) -> int:
        return self.collector.linhas_invalidas

    @property
    def arquivos_ausentes(self) -> List[str]:
        return self.collector.fontes_ausentes

    @property
    def limitacoes_cobertura(self) -> List[str]:
        return self.collector.limitacoes_cobertura

    def gerar_relatorio(self) -> Dict[str, Any]:
        """Executa a análise completa e retorna o dicionário estruturado sob o schema 1."""
        status_identidade, sob_resolvida, motivo_identidade = self._verificar_identidade()

        if status_identidade == "IDENTITY_UNVERIFIABLE":
            return self._montar_resposta_identidade_inverificavel(motivo_identidade)

        execucoes_agg, periodo_obs = self._processar_logs_execucao(sob_resolvida)

        projetos_observados: List[str] = []
        tem_fontes_duraveis_ok = False
        tem_fontes_duraveis_ausentes = False

        if self.project_root:
            dados_pending = processar_pending(self.project_root, sob_resolvida, self.collector)
            dados_deliveries = processar_deliveries(self.project_root, sob_resolvida, self.collector)
            dados_time = processar_time(self.project_root, sob_resolvida, self.collector)
            dados_versoes = processar_versoes(self.project_root, self.collector)
            dados_sob_state = processar_sob_state(self.project_root, sob_resolvida, self.collector)
            dados_reviews = processar_reviews(self.project_root, sob_resolvida, self.collector)

            if sob_resolvida:
                projetos_observados.append(sob_resolvida)

            blocos_status_base = [
                dados_pending.get("status"),
                dados_deliveries.get("status"),
                dados_time.get("status"),
                dados_versoes.get("status"),
                dados_sob_state.get("status"),
            ]
            tem_fontes_duraveis_ok = any(st == "OK" for st in blocos_status_base) or dados_reviews.get("status") == "OK"
            tem_fontes_duraveis_ausentes = any(st == "NÃO DISPONÍVEL" for st in blocos_status_base)

        elif self.workspace_root:
            (
                dados_pending,
                dados_deliveries,
                dados_time,
                dados_versoes,
                dados_sob_state,
                projetos_observados,
            ) = processar_workspace_consolidado(self.workspace_root, self.collector)
            dados_reviews = bloco_nao_disponivel("CONSOLIDACAO_NAO_SUPORTADA", {"total_revisoes": None, "iniciadas": None, "aprovadas": None, "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None, "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None}, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))

            tem_fontes_duraveis_ok = len(projetos_observados) > 0
            tem_fontes_duraveis_ausentes = len(projetos_observados) == 0

        else:
            dados_pending = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"total": None, "abertas": None, "em_andamento": None, "resolvidas": None, "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None}, proveniencia=PROVENIENCIA_FONTES["pendencias"])
            dados_deliveries = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"total_pacotes": None, "aprovados": None, "revogados": None, "pendentes_aprovacao": None, "integridade": None}, proveniencia=PROVENIENCIA_FONTES["entregas"])
            dados_time = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None}, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"])
            dados_versoes = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"total_snapshots": None}, proveniencia=PROVENIENCIA_FONTES["versoes"])
            dados_sob_state = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None}, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"])
            dados_reviews = bloco_nao_disponivel("PROJETO_NAO_INFORMADO", {"total_revisoes": None, "iniciadas": None, "aprovadas": None, "alteracoes_solicitadas": None, "rejeitadas": None, "canceladas": None, "substituidas": None, "findings_total": None, "findings_por_severidade": None, "entregas_vinculadas": None}, proveniencia=PROVENIENCIA_FONTES.get("revisoes", ".oxcad/reviews.json"))

        if self.log_file:
            self.collector.registrar_limitacao(
                "Logs em 'application.jsonl' possuem rotação máxima de 5 MB; execuções anteriores ao log rotativo ativo não constam nesta amostra."
            )
        if not self.project_root and not self.workspace_root:
            self.collector.registrar_limitacao(
                "Consulta sem pasta de projeto ('project_root'): pendências, entregas e tempo durável dependem do diretório do projeto."
            )

        tipo_escopo = "PROJETO" if (self.project_root or sob_resolvida) else "WORKSPACE"
        total_exec = execucoes_agg.get("total_execucoes") or 0

        cobertura = classificar_cobertura_historica(
            status_identidade=status_identidade,
            collector=self.collector,
            total_execucoes=total_exec,
            tem_fontes_duraveis_ok=tem_fontes_duraveis_ok,
            tem_fontes_duraveis_ausentes=tem_fontes_duraveis_ausentes,
            log_presente=(self.log_file is not None and self.log_file.is_file()),
        )

        return {
            "schema": SCHEMA_VERSION,
            "gerado_em": _agora_utc_iso(),
            "escopo": {
                "tipo": tipo_escopo,
                "sob_id": sob_resolvida,
                "project_root": str(self.project_root) if self.project_root else None,
                "workspace_root": str(self.workspace_root) if self.workspace_root else None,
                "status_identidade": status_identidade,
                "total_projetos_observados": len(projetos_observados),
                "projetos_observados": projetos_observados,
            },
            "periodo_observado": periodo_obs,
            "proveniencia": PROVENIENCIA_FONTES,
            "execucoes": execucoes_agg,
            "pendencias": dados_pending,
            "entregas": dados_deliveries,
            "tempo_operacional": dados_time,
            "versoes": dados_versoes,
            "sob_manifesto": dados_sob_state,
            "revisoes": dados_reviews,
            "qualidade_dados": {
                "cobertura": cobertura,
                "inicio_observado": periodo_obs.get("inicio"),
                "fim_observado": periodo_obs.get("fim"),
                "fontes_utilizadas": self.collector.fontes_utilizadas,
                "fontes_ausentes": self.collector.fontes_ausentes,
                "fontes_invalidas": self.collector.fontes_invalidas,
                "registros_considerados": self.collector.registros_considerados,
                "registros_descartados": self.collector.total_descartes,
                "descartes_por_motivo": self.collector.descartes_por_motivo,
                "linhas_totais_log": self.collector.linhas_totais,
                "linhas_validas_log": self.collector.linhas_validas,
                "linhas_invalidas_log": self.collector.linhas_invalidas,
                "arquivos_ausentes": self.collector.fontes_ausentes,
                "limitacoes_cobertura": self.collector.limitacoes_cobertura,
                "proveniencia": PROVENIENCIA_FONTES,
            },
        }

    def _verificar_identidade(self) -> Tuple[str, Optional[str], Optional[str]]:
        """Verifica a coerência da SOB informada contra o project_root e manifesto existente."""
        if self.project_root:
            if not self.project_root.is_dir():
                self.collector.registrar_fonte_ausente(str(self.project_root))
                return "IDENTITY_UNVERIFIABLE", None, "DIRETORIO_PROJETO_NAO_ENCONTRADO"

            manifesto = self.project_root / ".sob_state.json"
            if manifesto.is_file():
                try:
                    conteudo = json.loads(manifesto.read_text(encoding="utf-8"))
                    sob_man = _normalizar_sob_id(conteudo.get("sob_id"))
                    if self.sob_id_esperada and sob_man and self.sob_id_esperada != sob_man:
                        return "IDENTITY_UNVERIFIABLE", None, "SOB_ID_MISMATCH"
                    return "VALIDA", (self.sob_id_esperada or sob_man), None
                except Exception:
                    self.collector.registrar_fonte_invalida(str(manifesto))

        if self.sob_id_esperada:
            return "VALIDA", self.sob_id_esperada, None

        return "VALIDA", None, None

    def _montar_resposta_identidade_inverificavel(self, motivo: Optional[str]) -> Dict[str, Any]:
        recusa = motivo or "IDENTIDADE_CONFLITANTE_OU_INVALIDA"
        return {
            "schema": SCHEMA_VERSION,
            "gerado_em": _agora_utc_iso(),
            "escopo": {
                "tipo": "PROJETO" if self.project_root else "WORKSPACE",
                "sob_id": self.sob_id_esperada,
                "project_root": str(self.project_root) if self.project_root else None,
                "workspace_root": str(self.workspace_root) if self.workspace_root else None,
                "status_identidade": "IDENTITY_UNVERIFIABLE",
                "motivo_recusa": recusa,
                "total_projetos_observados": 0,
                "projetos_observados": [],
            },
            "periodo_observado": {"inicio": None, "fim": None, "duracao_dias": None},
            "proveniencia": PROVENIENCIA_FONTES,
            "execucoes": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {
                "total_execucoes": None, "concluidas": None, "falhas": None, "canceladas": None,
                "em_andamento": None, "taxa_conclusao_pct": None, "duracao_ms": None,
                "distribuicao_por_acao": None, "falhas_por_tipo": None,
            }, proveniencia=PROVENIENCIA_FONTES["execucoes"]),
            "pendencias": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {
                "total": None, "abertas": None, "em_andamento": None, "resolvidas": None,
                "descartadas": None, "taxa_resolucao_pct": None, "por_severidade": None,
            }, proveniencia=PROVENIENCIA_FONTES["pendencias"]),
            "entregas": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {
                "total_pacotes": None, "aprovados": None, "revogados": None,
                "pendentes_aprovacao": None, "integridade": None,
            }, proveniencia=PROVENIENCIA_FONTES["entregas"]),
            "tempo_operacional": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {
                "estado": None, "tempo_acumulado_segundos": None, "tempo_acumulado_formatado": None, "total_sessoes": None,
            }, proveniencia=PROVENIENCIA_FONTES["tempo_operacional"]),
            "versoes": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {"total_snapshots": None}, proveniencia=PROVENIENCIA_FONTES["versoes"]),
            "sob_manifesto": bloco_nao_disponivel("IDENTITY_UNVERIFIABLE", {
                "sob_id": None, "estado_preparacao": None, "duracao_segundos": None, "data_inicio": None, "data_fim": None,
            }, proveniencia=PROVENIENCIA_FONTES["sob_manifesto"]),
            "qualidade_dados": {
                "cobertura": COBERTURA_IDENTIDADE_NAO_VERIFICAVEL,
                "inicio_observado": None,
                "fim_observado": None,
                "fontes_utilizadas": self.collector.fontes_utilizadas,
                "fontes_ausentes": self.collector.fontes_ausentes,
                "fontes_invalidas": self.collector.fontes_invalidas,
                "registros_considerados": 0,
                "registros_descartados": 0,
                "descartes_por_motivo": self.collector.descartes_por_motivo,
                "linhas_totais_log": self.collector.linhas_totais,
                "linhas_validas_log": self.collector.linhas_validas,
                "linhas_invalidas_log": self.collector.linhas_invalidas,
                "arquivos_ausentes": self.collector.fontes_ausentes,
                "limitacoes_cobertura": ["Agregação recusada: identidade de projeto inverificável."],
                "proveniencia": PROVENIENCIA_FONTES,
            },
        }

    def _processar_logs_execucao(self, sob_filtro: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Lê e reconstrói as execuções por execution_id com filtros de SOB, período, ação e estado."""
        vazio_ret = bloco_nao_disponivel("ARQUIVO_LOG_NAO_ENCONTRADO", {
            "total_execucoes": None, "concluidas": None, "falhas": None, "canceladas": None,
            "em_andamento": None, "taxa_conclusao_pct": None, "duracao_ms": None,
            "distribuicao_por_acao": None, "falhas_por_tipo": None,
        }, proveniencia=PROVENIENCIA_FONTES["execucoes"]), {"inicio": None, "fim": None, "duracao_dias": None}

        if not self.log_file or not self.log_file.is_file():
            if self.log_file:
                self.collector.registrar_fonte_ausente(str(self.log_file))
            return vazio_ret

        try:
            sz = self.log_file.stat().st_size
            if sz >= 5 * 1024 * 1024:
                self.collector.log_rotacionado_detectado = True
        except OSError:
            pass

        self.collector.registrar_fonte_utilizada("logs/application.jsonl")

        execucoes_map: Dict[str, _ExecutionAggregate] = {}
        primeiro_ts_arquivo: Optional[datetime] = None
        primeiro_ts_global: Optional[datetime] = None
        ultimo_ts_global: Optional[datetime] = None

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    self.collector.linhas_totais += 1
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        record = json.loads(raw)
                        self.collector.linhas_validas += 1
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        self.collector.linhas_invalidas += 1
                        self.collector.registrar_descarte("LINHA_CORROMPIDA")
                        continue

                    if not isinstance(record, dict):
                        self.collector.linhas_invalidas += 1
                        self.collector.registrar_descarte("LINHA_CORROMPIDA")
                        continue

                    exec_id = record.get("execution_id")
                    if not exec_id or not isinstance(exec_id, str):
                        self.collector.registrar_descarte("SEM_EXECUTION_ID")
                        continue

                    ts_str = record.get("timestamp")
                    dt_evento = _parse_iso(ts_str)

                    if dt_evento:
                        if primeiro_ts_arquivo is None or dt_evento < primeiro_ts_arquivo:
                            primeiro_ts_arquivo = dt_evento

                    # Filtragem de período
                    if dt_evento:
                        if self.periodo_inicio and dt_evento < self.periodo_inicio:
                            self.collector.registrar_descarte("FILTRO_PERIODO")
                            continue
                        if self.periodo_fim and dt_evento > self.periodo_fim:
                            self.collector.registrar_descarte("FILTRO_PERIODO")
                            continue
                        if primeiro_ts_global is None or dt_evento < primeiro_ts_global:
                            primeiro_ts_global = dt_evento
                        if ultimo_ts_global is None or dt_evento > ultimo_ts_global:
                            ultimo_ts_global = dt_evento

                    # Filtragem por SOB
                    record_sob = _normalizar_sob_id(record.get("sob_id"))
                    if sob_filtro and record_sob and record_sob != sob_filtro:
                        self.collector.registrar_descarte("FILTRO_SOB")
                        continue

                    # Reconstrução da execução
                    if exec_id not in execucoes_map:
                        execucoes_map[exec_id] = _ExecutionAggregate(
                            execution_id=exec_id,
                            sob_id=record_sob,
                            action=record.get("action"),
                            primeiro_timestamp=ts_str,
                        )

                    agg = execucoes_map[exec_id]
                    if not agg.sob_id and record_sob:
                        agg.sob_id = record_sob
                    if not agg.action and record.get("action"):
                        agg.action = record.get("action")
                    if not agg.started_at and record.get("started_at"):
                        agg.started_at = record.get("started_at")
                    if record.get("finished_at"):
                        agg.finished_at = record.get("finished_at")
                    agg.ultimo_timestamp = ts_str or agg.ultimo_timestamp

                    dur = record.get("duration_ms")
                    if dur is not None:
                        try:
                            agg.duracao_ms = float(dur)
                        except (ValueError, TypeError):
                            pass

                    err = record.get("error")
                    if err:
                        agg.error = str(err)

                    state_raw = str(record.get("execution_state") or record.get("result") or "").strip()
                    if state_raw:
                        agg.estados_vistos.append(state_raw)
                        st_norm = state_raw.lower()
                        if st_norm in {"concluido", "concluído", "sucesso"}:
                            agg.estado_final = "Concluido"
                        elif st_norm in {"falhou", "erro", "falha"}:
                            agg.estado_final = "Falhou"
                        elif st_norm in {"cancelado"}:
                            agg.estado_final = "Cancelado"
                        elif st_norm in {"executando"}:
                            if agg.estado_final not in {"Concluido", "Falhou", "Cancelado"}:
                                agg.estado_final = "Executando"

        except OSError as ex:
            self.collector.registrar_fonte_invalida(str(self.log_file))
            self.collector.registrar_limitacao(f"Erro de E/S ao ler log {self.log_file.name}: {ex}")
            return bloco_nao_disponivel(f"ERRO_LEITURA_LOG: {ex}", {
                "total_execucoes": None, "concluidas": None, "falhas": None, "canceladas": None,
                "em_andamento": None, "taxa_conclusao_pct": None, "duracao_ms": None,
                "distribuicao_por_acao": None, "falhas_por_tipo": None,
            }, proveniencia=PROVENIENCIA_FONTES["execucoes"]), {"inicio": None, "fim": None, "duracao_dias": None}

        if sob_filtro:
            novos = {}
            for eid, a in execucoes_map.items():
                if a.sob_id == sob_filtro:
                    novos[eid] = a
                else:
                    self.collector.registrar_descarte("FILTRO_SOB")
            execucoes_map = novos

        if self.acao_filtro:
            novos = {}
            for eid, a in execucoes_map.items():
                if a.action and a.action.lower() == self.acao_filtro:
                    novos[eid] = a
                else:
                    self.collector.registrar_descarte("FILTRO_ACAO")
            execucoes_map = novos

        if self.estado_filtro:
            novos = {}
            for eid, a in execucoes_map.items():
                if a.estado_final.lower() == self.estado_filtro:
                    novos[eid] = a
                else:
                    self.collector.registrar_descarte("FILTRO_ESTADO")
            execucoes_map = novos

        if self.periodo_inicio and primeiro_ts_arquivo and self.periodo_inicio.date() < primeiro_ts_arquivo.date():
            self.collector.solicitou_periodo_anterior_ao_log = True
            self.collector.registrar_limitacao(
                "Período inicial solicitado é anterior ao evento mais antigo do log rotativo disponível."
            )

        self.collector.registros_considerados = len(execucoes_map)
        total_execucoes = len(execucoes_map)
        duracao_dias = (
            round((ultimo_ts_global - primeiro_ts_global).total_seconds() / 86400.0, 2)
            if (primeiro_ts_global and ultimo_ts_global) else None
        )
        periodo_res = {
            "inicio": primeiro_ts_global.isoformat().replace("+00:00", "Z") if primeiro_ts_global else None,
            "fim": ultimo_ts_global.isoformat().replace("+00:00", "Z") if ultimo_ts_global else None,
            "duracao_dias": duracao_dias,
        }

        if total_execucoes == 0:
            return {
                "status": "SEM_DADOS",
                "proveniencia": PROVENIENCIA_FONTES["execucoes"],
                "total_execucoes": 0,
                "concluidas": 0,
                "falhas": 0,
                "canceladas": 0,
                "em_andamento": 0,
                "taxa_conclusao_pct": None,
                "duracao_ms": _calcular_estatisticas_duracao([]),
                "distribuicao_por_acao": {},
                "falhas_por_tipo": {},
            }, periodo_res

        concluidas = 0
        falhas = 0
        canceladas = 0
        em_andamento = 0
        duracoes_validas: List[float] = []
        dist_acoes: Dict[str, int] = {}
        falhas_tipo: Dict[str, int] = {}

        for agg in execucoes_map.values():
            if agg.estado_final == "Concluido":
                concluidas += 1
            elif agg.estado_final == "Falhou":
                falhas += 1
                tipo_err = agg.error or "ERRO_NAO_ESPECIFICADO"
                falhas_tipo[tipo_err] = falhas_tipo.get(tipo_err, 0) + 1
            elif agg.estado_final == "Cancelado":
                canceladas += 1
            else:
                em_andamento += 1

            if agg.duracao_ms is not None and agg.duracao_ms >= 0:
                duracoes_validas.append(agg.duracao_ms)

            act = agg.action or "desconhecida"
            dist_acoes[act] = dist_acoes.get(act, 0) + 1

        finalizadas = concluidas + falhas + canceladas
        taxa_conclusao = round((concluidas / finalizadas * 100.0), 2) if finalizadas > 0 else None

        return {
            "status": "OK",
            "proveniencia": PROVENIENCIA_FONTES["execucoes"],
            "total_execucoes": total_execucoes,
            "concluidas": concluidas,
            "falhas": falhas,
            "canceladas": canceladas,
            "em_andamento": em_andamento,
            "taxa_conclusao_pct": taxa_conclusao,
            "duracao_ms": _calcular_estatisticas_duracao(duracoes_validas),
            "distribuicao_por_acao": dict(sorted(dist_acoes.items())),
            "falhas_por_tipo": dict(sorted(falhas_tipo.items())),
        }, periodo_res


def consultar_indicadores(
    project_root: Optional[Union[str, Path]] = None,
    sob_id: Optional[str] = None,
    log_file: Optional[Union[str, Path]] = None,
    periodo_inicio: Optional[Union[datetime, str]] = None,
    periodo_fim: Optional[Union[datetime, str]] = None,
    acao: Optional[str] = None,
    estado: Optional[str] = None,
    workspace_root: Optional[Union[str, Path]] = None,
    comparar_inicio: Optional[Union[datetime, str]] = None,
    comparar_fim: Optional[Union[datetime, str]] = None,
) -> Dict[str, Any]:
    """
    Função pública de entrada read-only do motor analítico OXCAD (P2.1 / P2.2 / P2.3).
    Suporta enriquecimento de qualidade, rastreamento de proveniência e comparação de períodos.
    """
    analyzer = IndicadoresAnalyzer(
        log_file=log_file,
        project_root=project_root,
        sob_id=sob_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        acao_filtro=acao,
        estado_filtro=estado,
        workspace_root=workspace_root,
    )
    relatorio_base = analyzer.gerar_relatorio()

    if comparar_inicio or comparar_fim:
        analyzer_comp = IndicadoresAnalyzer(
            log_file=log_file,
            project_root=project_root,
            sob_id=sob_id,
            periodo_inicio=comparar_inicio,
            periodo_fim=comparar_fim,
            acao_filtro=acao,
            estado_filtro=estado,
            workspace_root=workspace_root,
        )
        relatorio_comp = analyzer_comp.gerar_relatorio()
        relatorio_base["comparacao"] = comparar_indicadores(relatorio_base, relatorio_comp)

    return relatorio_base


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="OXCAD — Indicadores de Gestão e Processo (P2.1 / P2.2 / P2.3)")
    parser.add_argument("--project-root", type=str, default=None, help="Caminho raiz da SOB/projeto")
    parser.add_argument("--sob", type=str, default=None, help="Identificador oficial da SOB")
    parser.add_argument("--workspace-root", type=str, default=None, help="Caminho raiz do workspace")
    parser.add_argument("--action", type=str, default=None, help="Filtrar por ação (ex: cqt, orcamento, sob)")
    parser.add_argument("--state", type=str, default=None, help="Filtrar por estado (ex: Concluido, Falhou)")
    parser.add_argument("--start-date", type=str, default=None, help="Data/hora inicial ISO")
    parser.add_argument("--end-date", type=str, default=None, help="Data/hora final ISO")
    parser.add_argument("--compare-start", type=str, default=None, help="Data inicial ISO para comparação")
    parser.add_argument("--compare-end", type=str, default=None, help="Data final ISO para comparação")
    parser.add_argument("--log-file", type=str, default=None, help="Caminho do arquivo application.jsonl")
    parser.add_argument("--pretty", action="store_true", help="Formatar saída JSON")

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
        comparar_inicio=args.compare_start,
        comparar_fim=args.compare_end,
        log_file=log_path,
    )

    if args.pretty:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)

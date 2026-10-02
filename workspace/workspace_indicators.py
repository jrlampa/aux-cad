# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Indicadores de Gestão (P2.1).
Responsabilidade única: Motor analítico, determinístico, read-only e auditável
para agregação e cálculo de métricas de gestão a partir de dados já persistidos
(logs de execução, cadastros de pendências, entregas, tempo e manifestos de SOB).

Diretrizes obrigatórias:
- Zero efeitos colaterais: nenhuma escrita em disco, nenhuma alteração de estado;
- Zero inferência de histórico inexistente: dados ausentes reportados como NÃO DISPONÍVEL;
- Reconstrução obrigatória por execution_id para evitar inflação por transições múltiplas;
- Isolamento estrito de identidade por SOB;
- Tolerância a falhas na leitura linha a linha de logs (linhas corrompidas contabilizadas);
- Independência de serviços ou bancos de dados externos (apenas biblioteca padrão Python).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union


# Versão oficial do schema do contrato
SCHEMA_VERSION = 1

# Padrão para validação básica de SOB_ID
_SOB_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]+$")


def _agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(timestamp_str: Optional[str]) -> Optional[datetime]:
    if not timestamp_str or not isinstance(timestamp_str, str):
        return None
    try:
        ts = timestamp_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _normalizar_sob_id(sob_id: Optional[str]) -> Optional[str]:
    if not sob_id or not isinstance(sob_id, str):
        return None
    candidato = sob_id.strip().upper()
    if not candidato:
        return None
    if not _SOB_ID_REGEX.match(candidato):
        return None
    return candidato


def _calcular_estatisticas_duracao(valores_ms: List[float]) -> Dict[str, Optional[float]]:
    """
    Calcula deterministamente total, média, mediana e percentil 95 (P95).
    Retorna None para métricas quando não houver amostras válidas.
    """
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

    # Mediana determinística
    if amostras % 2 == 1:
        mediana = ordenados[amostras // 2]
    else:
        mediana = (ordenados[amostras // 2 - 1] + ordenados[amostras // 2]) / 2.0

    # Percentil 95 determinístico com interpolação linear
    if amostras == 1:
        p95 = ordenados[0]
    else:
        k = (amostras - 1) * 0.95
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            p95 = ordenados[int(k)]
        else:
            p95 = ordenados[int(f)] * (c - k) + ordenados[int(c)] * (k - f)

    return {
        "total_ms": round(total, 2),
        "media_ms": round(media, 2),
        "mediana_ms": round(mediana, 2),
        "p95_ms": round(p95, 2),
        "amostras": amostras,
    }


def _formatar_segundos_hhmmss(segundos: Optional[Union[int, float]]) -> Optional[str]:
    if segundos is None:
        return None
    seg = max(0, int(round(segundos)))
    horas = seg // 3600
    resto = seg % 3600
    minutos = resto // 60
    s = resto % 60
    return f"{horas:02d}:{minutos:02d}:{s:02d}"


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
        periodo_inicio: Optional[datetime] = None,
        periodo_fim: Optional[datetime] = None,
    ):
        self.log_file = Path(log_file).resolve() if log_file else None
        self.errors_file = Path(errors_file).resolve() if errors_file else None
        self.project_root = Path(project_root).resolve() if project_root else None
        self.sob_id_esperada = _normalizar_sob_id(sob_id) if sob_id else None
        self.periodo_inicio = periodo_inicio
        self.periodo_fim = periodo_fim

        self.linhas_totais = 0
        self.linhas_validas = 0
        self.linhas_invalidas = 0
        self.arquivos_ausentes: List[str] = []
        self.limitacoes_cobertura: List[str] = []

    def gerar_relatorio(self) -> Dict[str, Any]:
        """
        Executa a análise completa e retorna o dicionário estruturado sob o schema 1.
        """
        # 1. Validar e resolver identidade de escopo
        status_identidade, sob_resolvida, motivo_identidade = self._verificar_identidade()

        # 2. Se a identidade for inverificável em contexto de projeto, interromper agregação
        if status_identidade == "IDENTITY_UNVERIFIABLE":
            return self._montar_resposta_identidade_inverificavel(motivo_identidade)

        # 3. Processar eventos de execução do log rotativo
        execucoes_agg, periodo_obs = self._processar_logs_execucao(sob_resolvida)

        # 4. Processar fontes duráveis do projeto (se project_root estiver definido)
        dados_pending = self._processar_pending(sob_resolvida)
        dados_deliveries = self._processar_deliveries(sob_resolvida)
        dados_time = self._processar_time(sob_resolvida)
        dados_versoes = self._processar_versoes()
        dados_sob_state = self._processar_sob_state(sob_resolvida)

        # 5. Adicionar limitações estruturais de cobertura
        if self.log_file:
            self.limitacoes_cobertura.append(
                "Logs em 'application.jsonl' possuem rotação máxima de 5 MB; execuções anteriores ao log rotativo ativo não constam nesta amostra."
            )
        if not self.project_root:
            self.limitacoes_cobertura.append(
                "Consulta sem pasta de projeto ('project_root'): pendências, entregas e tempo durável dependem do diretório do projeto."
            )

        # 6. Consolidar contrato final
        return {
            "schema": SCHEMA_VERSION,
            "gerado_em": _agora_utc_iso(),
            "escopo": {
                "tipo": "PROJETO" if (self.project_root or sob_resolvida) else "WORKSPACE",
                "sob_id": sob_resolvida,
                "project_root": str(self.project_root) if self.project_root else None,
                "status_identidade": status_identidade,
            },
            "periodo_observado": periodo_obs,
            "execucoes": execucoes_agg,
            "pendencias": dados_pending,
            "entregas": dados_deliveries,
            "tempo_operacional": dados_time,
            "versoes": dados_versoes,
            "sob_manifesto": dados_sob_state,
            "qualidade_dados": {
                "linhas_totais_log": self.linhas_totais,
                "linhas_validas_log": self.linhas_validas,
                "linhas_invalidas_log": self.linhas_invalidas,
                "arquivos_ausentes": self.arquivos_ausentes,
                "limitacoes_cobertura": self.limitacoes_cobertura,
            },
        }

    def _verificar_identidade(self) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Verifica a coerência da SOB informada contra o project_root e manifesto existente.
        Retorna (status_identidade, sob_resolvida, motivo_falha).
        """
        if self.project_root:
            if not self.project_root.is_dir():
                self.arquivos_ausentes.append(str(self.project_root))
                return "IDENTITY_UNVERIFIABLE", None, "DIRETORIO_PROJETO_NAO_ENCONTRADO"

            # Tenta ler .sob_state.json para verificar identidade autoritativa
            manifesto = self.project_root / ".sob_state.json"
            if manifesto.is_file():
                try:
                    conteudo = json.loads(manifesto.read_text(encoding="utf-8"))
                    sob_man = _normalizar_sob_id(conteudo.get("sob_id"))
                    if self.sob_id_esperada and sob_man and self.sob_id_esperada != sob_man:
                        return "IDENTITY_UNVERIFIABLE", None, "SOB_ID_MISMATCH"
                    return "VALIDA", (self.sob_id_esperada or sob_man), None
                except Exception:
                    pass

        if self.sob_id_esperada:
            return "VALIDA", self.sob_id_esperada, None

        if self.project_root:
            return "VALIDA", None, None

        return "VALIDA", None, None

    def _montar_resposta_identidade_inverificavel(self, motivo: Optional[str]) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "gerado_em": _agora_utc_iso(),
            "escopo": {
                "tipo": "PROJETO" if self.project_root else "WORKSPACE",
                "sob_id": self.sob_id_esperada,
                "project_root": str(self.project_root) if self.project_root else None,
                "status_identidade": "IDENTITY_UNVERIFIABLE",
                "motivo_recusa": motivo or "IDENTIDADE_CONFLITANTE_OU_INVALIDA",
            },
            "periodo_observado": {"inicio": None, "fim": None, "duracao_dias": None},
            "execucoes": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "total_execucoes": None,
                "concluidas": None,
                "falhas": None,
                "canceladas": None,
                "em_andamento": None,
                "taxa_conclusao_pct": None,
                "duracao_ms": None,
                "distribuicao_por_acao": None,
                "falhas_por_tipo": None,
            },
            "pendencias": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "total": None,
                "abertas": None,
                "em_andamento": None,
                "resolvidas": None,
                "descartadas": None,
                "taxa_resolucao_pct": None,
                "por_severidade": None,
            },
            "entregas": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "total_pacotes": None,
                "aprovados": None,
                "revogados": None,
                "pendentes_aprovacao": None,
                "integridade": None,
            },
            "tempo_operacional": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "estado": None,
                "tempo_acumulado_segundos": None,
                "tempo_acumulado_formatado": None,
                "total_sessoes": None,
            },
            "versoes": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "total_snapshots": None,
            },
            "sob_manifesto": {
                "status": "NÃO DISPONÍVEL",
                "motivo": "IDENTITY_UNVERIFIABLE",
                "sob_id": None,
                "estado_preparacao": None,
                "duracao_segundos": None,
                "data_inicio": None,
                "data_fim": None,
            },
            "qualidade_dados": {
                "linhas_totais_log": self.linhas_totais,
                "linhas_validas_log": self.linhas_validas,
                "linhas_invalidas_log": self.linhas_invalidas,
                "arquivos_ausentes": self.arquivos_ausentes,
                "limitacoes_cobertura": ["Agregação recusada: identidade de projeto inverificável."],
            },
        }

    def _processar_logs_execucao(self, sob_filtro: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Lê e reconstrói as execuções por execution_id a partir do arquivo de log JSONL.
        """
        if not self.log_file or not self.log_file.is_file():
            if self.log_file:
                self.arquivos_ausentes.append(str(self.log_file))
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "ARQUIVO_LOG_NAO_ENCONTRADO",
                "total_execucoes": None,
                "concluidas": None,
                "falhas": None,
                "canceladas": None,
                "em_andamento": None,
                "taxa_conclusao_pct": None,
                "duracao_ms": None,
                "distribuicao_por_acao": None,
                "falhas_por_tipo": None,
            }, {"inicio": None, "fim": None, "duracao_dias": None}

        execucoes_map: Dict[str, _ExecutionAggregate] = {}
        primeiro_ts_global: Optional[datetime] = None
        ultimo_ts_global: Optional[datetime] = None

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    self.linhas_totais += 1
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        record = json.loads(raw)
                        self.linhas_validas += 1
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        self.linhas_invalidas += 1
                        continue

                    if not isinstance(record, dict):
                        self.linhas_invalidas += 1
                        continue

                    exec_id = record.get("execution_id")
                    if not exec_id or not isinstance(exec_id, str):
                        # Eventos de log que não pertencem a uma execução com ID são ignorados na agregação de execuções
                        continue

                    ts_str = record.get("timestamp")
                    dt_evento = _parse_iso(ts_str)

                    # Filtragem de período global
                    if dt_evento:
                        if self.periodo_inicio and dt_evento < self.periodo_inicio:
                            continue
                        if self.periodo_fim and dt_evento > self.periodo_fim:
                            continue

                        if primeiro_ts_global is None or dt_evento < primeiro_ts_global:
                            primeiro_ts_global = dt_evento
                        if ultimo_ts_global is None or dt_evento > ultimo_ts_global:
                            ultimo_ts_global = dt_evento

                    # Filtragem por SOB
                    record_sob = _normalizar_sob_id(record.get("sob_id"))
                    if sob_filtro and record_sob and record_sob != sob_filtro:
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

                    # Atualiza último timestamp
                    agg.ultimo_timestamp = ts_str or agg.ultimo_timestamp

                    # Duração
                    dur = record.get("duration_ms")
                    if dur is not None:
                        try:
                            agg.duracao_ms = float(dur)
                        except (ValueError, TypeError):
                            pass

                    # Erro
                    err = record.get("error")
                    if err:
                        agg.error = str(err)

                    # Transição de estado
                    state_raw = str(record.get("execution_state") or record.get("result") or "").strip()
                    if state_raw:
                        agg.estados_vistos.append(state_raw)
                        # Normalizar nomes
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
            self.limitacoes_cobertura.append(f"Erro de E/S ao ler log {self.log_file.name}: {ex}")
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_LOG: {ex}",
                "total_execucoes": None,
                "concluidas": None,
                "falhas": None,
                "canceladas": None,
                "em_andamento": None,
                "taxa_conclusao_pct": None,
                "duracao_ms": None,
                "distribuicao_por_acao": None,
                "falhas_por_tipo": None,
            }, {"inicio": None, "fim": None, "duracao_dias": None}

        # Se filtro de SOB estava ativo, descartar execuções que acabaram vinculadas a outra SOB
        if sob_filtro:
            execucoes_map = {
                eid: agg for eid, agg in execucoes_map.items()
                if agg.sob_id == sob_filtro
            }

        total_execucoes = len(execucoes_map)
        if total_execucoes == 0:
            return {
                "status": "SEM_DADOS",
                "total_execucoes": 0,
                "concluidas": 0,
                "falhas": 0,
                "canceladas": 0,
                "em_andamento": 0,
                "taxa_conclusao_pct": None,
                "duracao_ms": _calcular_estatisticas_duracao([]),
                "distribuicao_por_acao": {},
                "falhas_por_tipo": {},
            }, {
                "inicio": primeiro_ts_global.isoformat().replace("+00:00", "Z") if primeiro_ts_global else None,
                "fim": ultimo_ts_global.isoformat().replace("+00:00", "Z") if ultimo_ts_global else None,
                "duracao_dias": round((ultimo_ts_global - primeiro_ts_global).total_seconds() / 86400.0, 2)
                if (primeiro_ts_global and ultimo_ts_global) else None,
            }

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

        periodo_res = {
            "inicio": primeiro_ts_global.isoformat().replace("+00:00", "Z") if primeiro_ts_global else None,
            "fim": ultimo_ts_global.isoformat().replace("+00:00", "Z") if ultimo_ts_global else None,
            "duracao_dias": round((ultimo_ts_global - primeiro_ts_global).total_seconds() / 86400.0, 2)
            if (primeiro_ts_global and ultimo_ts_global) else None,
        }

        return {
            "status": "OK",
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

    def _processar_pending(self, sob_resolvida: Optional[str]) -> Dict[str, Any]:
        """
        Lê defensivamente o store autoritativo de pendências (.oxcad/pending.json).
        """
        if not self.project_root:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "PROJETO_NAO_INFORMADO",
                "total": None,
                "abertas": None,
                "em_andamento": None,
                "resolvidas": None,
                "descartadas": None,
                "taxa_resolucao_pct": None,
                "por_severidade": None,
            }

        store_file = self.project_root / ".oxcad" / "pending.json"
        if not store_file.is_file():
            self.arquivos_ausentes.append(str(store_file))
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "ARQUIVO_PENDING_NAO_ENCONTRADO",
                "total": None,
                "abertas": None,
                "em_andamento": None,
                "resolvidas": None,
                "descartadas": None,
                "taxa_resolucao_pct": None,
                "por_severidade": None,
            }

        try:
            data = json.loads(store_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("items"), list):
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "ARQUIVO_PENDING_INVALIDO",
                    "total": None,
                    "abertas": None,
                    "em_andamento": None,
                    "resolvidas": None,
                    "descartadas": None,
                    "taxa_resolucao_pct": None,
                    "por_severidade": None,
                }

            # Verificar se pertence à SOB consultada
            store_sob = _normalizar_sob_id(data.get("sob_id"))
            if sob_resolvida and store_sob and store_sob != sob_resolvida:
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "SOB_ID_MISMATCH",
                    "total": None,
                    "abertas": None,
                    "em_andamento": None,
                    "resolvidas": None,
                    "descartadas": None,
                    "taxa_resolucao_pct": None,
                    "por_severidade": None,
                }

            items = data["items"]
            total = len(items)
            abertas = 0
            em_andamento = 0
            resolvidas = 0
            descartadas = 0
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
            taxa_resolucao = round((resolvidas / ativas_e_resolvidas * 100.0), 2) if ativas_e_resolvidas > 0 else None

            return {
                "status": "OK",
                "total": total,
                "abertas": abertas,
                "em_andamento": em_andamento,
                "resolvidas": resolvidas,
                "descartadas": descartadas,
                "taxa_resolucao_pct": taxa_resolucao,
                "por_severidade": por_severidade,
            }
        except Exception as ex:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_PENDING: {ex}",
                "total": None,
                "abertas": None,
                "em_andamento": None,
                "resolvidas": None,
                "descartadas": None,
                "taxa_resolucao_pct": None,
                "por_severidade": None,
            }

    def _processar_deliveries(self, sob_resolvida: Optional[str]) -> Dict[str, Any]:
        """
        Lê defensivamente o store de pacotes de entrega (.oxcad/deliveries/).
        """
        if not self.project_root:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "PROJETO_NAO_INFORMADO",
                "total_pacotes": None,
                "aprovados": None,
                "revogados": None,
                "pendentes_aprovacao": None,
                "integridade": None,
            }

        store_dir = self.project_root / ".oxcad" / "deliveries"
        if not store_dir.is_dir():
            self.arquivos_ausentes.append(str(store_dir))
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "DIRETORIO_DELIVERIES_NAO_ENCONTRADO",
                "total_pacotes": None,
                "aprovados": None,
                "revogados": None,
                "pendentes_aprovacao": None,
                "integridade": None,
            }

        try:
            total_pacotes = 0
            aprovados = 0
            revogados = 0
            pendentes_aprovacao = 0
            confirmados = 0
            divergentes = 0
            invalidos = 0

            for entry in store_dir.iterdir():
                if not entry.is_dir():
                    continue
                manifest_file = entry / "manifest.json"
                if not manifest_file.is_file():
                    continue

                try:
                    man_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    man_sob = _normalizar_sob_id(man_data.get("sob_id"))
                    if sob_resolvida and man_sob and man_sob != sob_resolvida:
                        continue
                except Exception:
                    invalidos += 1
                    continue

                total_pacotes += 1

                # Inspecionar approval.json
                appr_file = entry / "approval.json"
                if appr_file.is_file():
                    try:
                        appr_data = json.loads(appr_file.read_text(encoding="utf-8"))
                        if appr_data.get("approved") is True:
                            aprovados += 1
                        elif appr_data.get("approved") is False:
                            revogados += 1
                        else:
                            pendentes_aprovacao += 1
                    except Exception:
                        invalidos += 1
                else:
                    pendentes_aprovacao += 1

                # Integridade do checksum
                sha_file = entry / "manifest.sha256"
                if sha_file.is_file():
                    confirmados += 1
                else:
                    divergentes += 1

            return {
                "status": "OK",
                "total_pacotes": total_pacotes,
                "aprovados": aprovados,
                "revogados": revogados,
                "pendentes_aprovacao": pendentes_aprovacao,
                "integridade": {
                    "confirmados": confirmados,
                    "divergentes": divergentes,
                    "invalidos": invalidos,
                },
            }
        except Exception as ex:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_DELIVERIES: {ex}",
                "total_pacotes": None,
                "aprovados": None,
                "revogados": None,
                "pendentes_aprovacao": None,
                "integridade": None,
            }

    def _processar_time(self, sob_resolvida: Optional[str]) -> Dict[str, Any]:
        """
        Lê defensivamente o apontamento operacional de tempo (.oxcad/time.json).
        """
        if not self.project_root:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "PROJETO_NAO_INFORMADO",
                "estado": None,
                "tempo_acumulado_segundos": None,
                "tempo_acumulado_formatado": None,
                "total_sessoes": None,
            }

        time_file = self.project_root / ".oxcad" / "time.json"
        if not time_file.is_file():
            self.arquivos_ausentes.append(str(time_file))
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "ARQUIVO_TIME_NAO_ENCONTRADO",
                "estado": None,
                "tempo_acumulado_segundos": None,
                "tempo_acumulado_formatado": None,
                "total_sessoes": None,
            }

        try:
            data = json.loads(time_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "ARQUIVO_TIME_INVALIDO",
                    "estado": None,
                    "tempo_acumulado_segundos": None,
                    "tempo_acumulado_formatado": None,
                    "total_sessoes": None,
                }

            store_sob = _normalizar_sob_id(data.get("sob_id"))
            if sob_resolvida and store_sob and store_sob != sob_resolvida:
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "SOB_ID_MISMATCH",
                    "estado": None,
                    "tempo_acumulado_segundos": None,
                    "tempo_acumulado_formatado": None,
                    "total_sessoes": None,
                }

            acumulado = data.get("tempo_acumulado_segundos")
            estado = data.get("estado")
            sessoes = data.get("sessoes")
            total_sessoes = len(sessoes) if isinstance(sessoes, list) else 0

            return {
                "status": "OK",
                "estado": estado,
                "tempo_acumulado_segundos": acumulado,
                "tempo_acumulado_formatado": _formatar_segundos_hhmmss(acumulado),
                "total_sessoes": total_sessoes,
            }
        except Exception as ex:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_TIME: {ex}",
                "estado": None,
                "tempo_acumulado_segundos": None,
                "tempo_acumulado_formatado": None,
                "total_sessoes": None,
            }

    def _processar_versoes(self) -> Dict[str, Any]:
        """
        Conta snapshots de versão disponíveis em .auxcad_versions/.
        """
        if not self.project_root:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "PROJETO_NAO_INFORMADO",
                "total_snapshots": None,
            }

        vers_dir = self.project_root / ".auxcad_versions"
        if not vers_dir.is_dir():
            return {"status": "OK", "total_snapshots": 0}

        try:
            snapshots = [
                d for d in vers_dir.iterdir()
                if d.is_dir() and (d / "manifest.json").is_file()
            ]
            return {"status": "OK", "total_snapshots": len(snapshots)}
        except Exception as ex:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_VERSOES: {ex}",
                "total_snapshots": None,
            }

    def _processar_sob_state(self, sob_resolvida: Optional[str]) -> Dict[str, Any]:
        """
        Lê defensivamente o manifesto de preparação de projeto (.sob_state.json).
        """
        if not self.project_root:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "PROJETO_NAO_INFORMADO",
                "sob_id": None,
                "estado_preparacao": None,
                "duracao_segundos": None,
                "data_inicio": None,
                "data_fim": None,
            }

        state_file = self.project_root / ".sob_state.json"
        if not state_file.is_file():
            self.arquivos_ausentes.append(str(state_file))
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": "MANIFESTO_SOB_NAO_ENCONTRADO",
                "sob_id": None,
                "estado_preparacao": None,
                "duracao_segundos": None,
                "data_inicio": None,
                "data_fim": None,
            }

        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "MANIFESTO_SOB_INVALIDO",
                    "sob_id": None,
                    "estado_preparacao": None,
                    "duracao_segundos": None,
                    "data_inicio": None,
                    "data_fim": None,
                }

            sob_id = _normalizar_sob_id(data.get("sob_id"))
            if sob_resolvida and sob_id and sob_id != sob_resolvida:
                return {
                    "status": "NÃO DISPONÍVEL",
                    "motivo": "SOB_ID_MISMATCH",
                    "sob_id": None,
                    "estado_preparacao": None,
                    "duracao_segundos": None,
                    "data_inicio": None,
                    "data_fim": None,
                }

            return {
                "status": "OK",
                "sob_id": sob_id,
                "estado_preparacao": data.get("status"),
                "duracao_segundos": data.get("duracao_segundos"),
                "data_inicio": data.get("data_inicio"),
                "data_fim": data.get("data_fim"),
            }
        except Exception as ex:
            return {
                "status": "NÃO DISPONÍVEL",
                "motivo": f"ERRO_LEITURA_MANIFESTO_SOB: {ex}",
                "sob_id": None,
                "estado_preparacao": None,
                "duracao_segundos": None,
                "data_inicio": None,
                "data_fim": None,
            }


def consultar_indicadores(
    project_root: Optional[Union[str, Path]] = None,
    sob_id: Optional[str] = None,
    log_file: Optional[Union[str, Path]] = None,
    periodo_inicio: Optional[datetime] = None,
    periodo_fim: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Função pública de entrada read-only do motor analítico P2.1.
    """
    analyzer = IndicadoresAnalyzer(
        log_file=log_file,
        project_root=project_root,
        sob_id=sob_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
    )
    return analyzer.gerar_relatorio()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="OXCAD — Indicadores de Gestão (P2.1)")
    parser.add_argument("--project-root", type=str, default=None, help="Caminho raiz da SOB/projeto")
    parser.add_argument("--sob", type=str, default=None, help="Identificador oficial da SOB")
    parser.add_argument("--log-file", type=str, default=None, help="Caminho do arquivo application.jsonl")
    parser.add_argument("--pretty", action="store_true", help="Formatar saída JSON")

    args = parser.parse_args()

    # Fallback para log padrão se não informado
    log_path = args.log_file
    if not log_path:
        default_log = Path(__file__).resolve().parent.parent / "logs" / "application.jsonl"
        if default_log.is_file():
            log_path = default_log

    resultado = consultar_indicadores(
        project_root=args.project_root,
        sob_id=args.sob,
        log_file=log_path,
    )

    if args.pretty:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)

# -*- coding: utf-8 -*-
"""
Módulo de Domínio e Persistência de Tempo de Projeto por SOB (aux cad).
Responsabilidade única: Controle rigoroso e auditável de apontamento de tempo,
baseado em timestamps ISO 8601 (DateTimeOffset/UTC), persistência em JSON
e desacoplamento estrito de relógios visuais de interface.

Estados suportados:
- NaoIniciado: Projeto cadastrado mas apontamento não iniciado;
- EmExecucao: Sessão de trabalho ativa (tempo transcorrendo);
- Pausado: Trabalho suspenso temporariamente (tempo acumulado congelado);
- Concluido: Projeto finalizado (tempo total definitivo).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from common.logging_config import get_logger

logger = get_logger("oxcad.workspace.time")


class TimeState(str, Enum):
    """Estado do apontamento de tempo de uma SOB."""
    NAO_INICIADO = "NaoIniciado"
    EM_EXECUCAO = "EmExecucao"
    PAUSADO = "Pausado"
    INTERROMPIDO = "Interrompido"
    CONCLUIDO = "Concluido"


def processo_esta_ativo(pid: Optional[int]) -> bool:
    """Verifica com segurança se um PID específico está em execução no SO Windows/Unix."""
    if not pid or pid <= 0:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if handle == 0:
            return False
        exit_code = ctypes.c_ulong()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            STILL_ACTIVE = 259
            kernel32.CloseHandle(handle)
            return exit_code.value == STILL_ACTIVE
        kernel32.CloseHandle(handle)
        return False
    except Exception:
        try:
            import os
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def _agora_utc_iso() -> str:
    """Gera string de timestamp ISO 8601 UTC corrente."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(timestamp_str: Optional[str]) -> Optional[datetime]:
    """Interpreta com segurança uma string ISO 8601 UTC."""
    if not timestamp_str:
        return None
    try:
        # Suporta sufixo 'Z' e offsets ISO
        ts = timestamp_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def formatar_segundos_para_hhmmss(segundos_totais: Union[int, float]) -> str:
    """Converte segundos para formato amigável hh:mm:ss."""
    seg = max(0, int(round(segundos_totais)))
    horas = seg // 3600
    resto = seg % 3600
    minutos = resto // 60
    segundos = resto % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def formatar_iso_para_exibicao_local(timestamp_str: Optional[str]) -> str:
    """Converte ISO 8601 para formato visual amigável dd/mm/aaaa hh:mm."""
    dt = _parse_iso(timestamp_str)
    if not dt:
        return "-"
    # Converte para horário local do sistema para exibição no card
    dt_local = dt.astimezone()
    return dt_local.strftime("%d/%m/%Y %H:%M")


@dataclass
class OxCadTimeEntry:
    """
    Registro canônico de tempo operacional por SOB/DWG.
    Não depende de contadores em memória ou loops com Thread.Sleep.
    Campos derivados (tempo_total_segundos, tempo_formatado) são calculados em runtime
    e não constituem fonte primária de verdade.
    A fonte canônica é: tempo_acumulado_segundos + (agora - sessao_atual_inicio) se EmExecucao.
    """
    sob_id: str
    dwg_path: Optional[str] = None
    estado: TimeState = TimeState.NAO_INICIADO
    data_hora_inicio: Optional[str] = None
    data_hora_fim: Optional[str] = None
    tempo_acumulado_segundos: float = 0.0
    sessao_atual_inicio: Optional[str] = None
    ultima_atualizacao: str = field(default_factory=_agora_utc_iso)
    ultima_atividade: Optional[str] = None
    pid_processo: Optional[int] = None
    token_sessao: Optional[str] = None
    sessoes: List[Dict[str, Any]] = field(default_factory=list)

    def calcular_tempo_total_segundos(self, agora_dt: Optional[datetime] = None) -> float:
        """
        Calcula o tempo real decorrido em segundos sem deriva de timer.
        Fórmula: tempo = acumulado + (agora - sessao_atual_inicio) se EmExecucao.
        """
        total = float(self.tempo_acumulado_segundos)
        if self.estado == TimeState.EM_EXECUCAO and self.sessao_atual_inicio:
            dt_inicio = _parse_iso(self.sessao_atual_inicio)
            if dt_inicio:
                agora = agora_dt or datetime.now(timezone.utc)
                delta = (agora - dt_inicio).total_seconds()
                if delta > 0:
                    total += delta
        return max(0.0, total)

    def obter_tempo_formatado(self, agora_dt: Optional[datetime] = None) -> str:
        """Retorna o tempo total trabalhado formatado em hh:mm:ss."""
        segundos = self.calcular_tempo_total_segundos(agora_dt)
        return formatar_segundos_para_hhmmss(segundos)

    def para_dicionario(self, agora_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Serializa o registro para interoperabilidade JSON com o C#/.NET."""
        return {
            "sob_id": self.sob_id,
            "dwg_path": self.dwg_path,
            "estado": self.estado.value,
            "data_hora_inicio": self.data_hora_inicio,
            "data_hora_fim": self.data_hora_fim,
            "tempo_acumulado_segundos": round(self.tempo_acumulado_segundos, 1),
            "sessao_atual_inicio": self.sessao_atual_inicio,
            "ultima_atualizacao": self.ultima_atualizacao,
            "ultima_atividade": self.ultima_atividade,
            "pid_processo": self.pid_processo,
            "token_sessao": self.token_sessao,
            "tempo_total_segundos": round(self.calcular_tempo_total_segundos(agora_dt), 1),
            "tempo_formatado": self.obter_tempo_formatado(agora_dt),
            "inicio_formatado": formatar_iso_para_exibicao_local(self.data_hora_inicio),
            "fim_formatado": formatar_iso_para_exibicao_local(self.data_hora_fim),
            "sessoes": self.sessoes,
        }

    @classmethod
    def de_dicionario(cls, dados: Dict[str, Any]) -> "OxCadTimeEntry":
        """Reconstitui uma instância a partir de dicionário JSON."""
        estado_raw = dados.get("estado", TimeState.NAO_INICIADO.value)
        try:
            estado = TimeState(estado_raw)
        except Exception:
            estado = TimeState.NAO_INICIADO

        return cls(
            sob_id=dados.get("sob_id", "-"),
            dwg_path=dados.get("dwg_path"),
            estado=estado,
            data_hora_inicio=dados.get("data_hora_inicio"),
            data_hora_fim=dados.get("data_hora_fim"),
            tempo_acumulado_segundos=float(dados.get("tempo_acumulado_segundos", 0.0)),
            sessao_atual_inicio=dados.get("sessao_atual_inicio"),
            ultima_atualizacao=dados.get("ultima_atualizacao", _agora_utc_iso()),
            ultima_atividade=dados.get("ultima_atividade"),
            pid_processo=dados.get("pid_processo"),
            token_sessao=dados.get("token_sessao"),
            sessoes=dados.get("sessoes", []),
        )


def obter_caminho_time_json(root_dir: Union[str, Path]) -> Path:
    """Localização oficial e protegida do arquivo de tempo na SOB."""
    p_root = Path(root_dir).resolve()
    pasta_oxcad = p_root / ".oxcad"
    return pasta_oxcad / "time.json"


def carregar_tempo_projeto(
    root_dir: Union[str, Path],
    fallback_se_invalido: bool = False,
) -> Optional[OxCadTimeEntry]:
    """
    Carrega o registro de tempo a partir de .oxcad/time.json.
    Se fallback_se_invalido=True, retorna uma entrada limpa NAO_INICIADO em caso de ausência/erro.
    """
    caminho = obter_caminho_time_json(root_dir)
    p_root = Path(root_dir).resolve()

    if not caminho.exists() or not caminho.is_file():
        if fallback_se_invalido:
            sob_id = p_root.name
            return OxCadTimeEntry(sob_id=sob_id, estado=TimeState.NAO_INICIADO)
        return None

    try:
        conteudo = caminho.read_text(encoding="utf-8")
        dados = json.loads(conteudo)
        return OxCadTimeEntry.de_dicionario(dados)
    except Exception:
        if fallback_se_invalido:
            sob_id = p_root.name
            return OxCadTimeEntry(sob_id=sob_id, estado=TimeState.NAO_INICIADO)
        return None


def salvar_tempo_projeto(root_dir: Union[str, Path], entry: OxCadTimeEntry) -> bool:
    """Persiste atomicamente o registro de tempo da SOB."""
    caminho = obter_caminho_time_json(root_dir)
    pasta = caminho.parent

    try:
        pasta.mkdir(parents=True, exist_ok=True)
        temp_file = pasta / f"time_{_agora_utc_iso().replace(':', '-')}.tmp"
        payload = json.dumps(entry.para_dicionario(), indent=2, ensure_ascii=False)
        temp_file.write_text(payload, encoding="utf-8")
        temp_file.replace(caminho)
        return True
    except Exception:
        return False


def inicializar_tempo_projeto(
    root_dir: Union[str, Path],
    sob_id: Optional[str] = None,
    dwg_path: Optional[str] = None,
    iniciar_imediatamente: bool = False,
    timestamp_custom: Optional[str] = None,
    sobrescrever: bool = False,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> OxCadTimeEntry:
    """
    Inicializa o apontamento para uma nova SOB.
    Se já existir apontamento prévio e sobrescrever=False, preserva o histórico.
    """
    p_root = Path(root_dir).resolve()
    sob_id_final = str(sob_id).strip() if sob_id else p_root.name

    if not sobrescrever:
        existente = carregar_tempo_projeto(root_dir)
        if existente and (existente.data_hora_inicio or existente.tempo_acumulado_segundos > 0):
            if dwg_path and not existente.dwg_path:
                existente.dwg_path = str(dwg_path)
                salvar_tempo_projeto(root_dir, existente)
            return existente

    agora = timestamp_custom or _agora_utc_iso()
    estado = TimeState.EM_EXECUCAO if iniciar_imediatamente else TimeState.NAO_INICIADO
    sessao_inicio = agora if iniciar_imediatamente else None
    inicio_registro = agora if iniciar_imediatamente else None

    entry = OxCadTimeEntry(
        sob_id=sob_id_final,
        dwg_path=str(dwg_path) if dwg_path else None,
        estado=estado,
        data_hora_inicio=inicio_registro,
        data_hora_fim=None,
        tempo_acumulado_segundos=0.0,
        sessao_atual_inicio=sessao_inicio,
        ultima_atualizacao=agora,
        sessoes=[],
    )
    salvar_tempo_projeto(root_dir, entry)
    if execution_id:
        logger.info(
            f"Apontamento inicializado para SOB {sob_id_final}",
            extra={
                "action": "tempo.inicializado",
                "sob_id": sob_id_final,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
            },
        )
    return entry


def atualizar_heartbeat_tempo(
    root_dir: Union[str, Path],
    pid: Optional[int] = None,
    token_sessao: Optional[str] = None,
    timestamp_custom: Optional[str] = None,
) -> Optional[OxCadTimeEntry]:
    """Registra batimento periódico da sessão ativa do AutoCAD para garantir auditabilidade."""
    entry = carregar_tempo_projeto(root_dir)
    if not entry or entry.estado != TimeState.EM_EXECUCAO:
        return entry

    agora = timestamp_custom or _agora_utc_iso()
    entry.ultima_atualizacao = agora
    entry.ultima_atividade = agora
    if pid is not None:
        entry.pid_processo = pid
    if token_sessao is not None:
        entry.token_sessao = token_sessao
    salvar_tempo_projeto(root_dir, entry)
    logger.debug(
        f"Heartbeat registrado para SOB {entry.sob_id}",
        extra={"action": "tempo.heartbeat", "sob_id": entry.sob_id, "process_id": pid}
    )
    return entry


def tratar_interrupcao_se_necessario(
    root_dir: Union[str, Path],
    pid_atual: Optional[int] = None,
    token_sessao_atual: Optional[str] = None,
    forcar_interrupcao: bool = False,
    timestamp_verificacao: Optional[str] = None,
) -> Optional[OxCadTimeEntry]:
    """
    Detecta se o AutoCAD/processo anterior foi fechado enquanto o projeto estava EmExecucao.
    Se detectado, encerra a sessão pendente até o momento da última atividade registrada,
    evitando que o tempo em que o AutoCAD esteve fechado seja indevidamente computado.
    Define o estado como TimeState.INTERROMPIDO.
    Usa tanto o PID quanto o token_sessao (imunidade total a reciclagem de PID pelo Windows).
    """
    entry = carregar_tempo_projeto(root_dir)
    if not entry or entry.estado != TimeState.EM_EXECUCAO:
        return entry

    houve_interrupcao = False

    if forcar_interrupcao:
        houve_interrupcao = True
    elif token_sessao_atual is not None and entry.token_sessao is not None and token_sessao_atual != entry.token_sessao:
        # Sessão de processo diferente (mesmo se o Windows tiver reaproveitado o mesmo PID!)
        houve_interrupcao = True
    elif pid_atual is not None and entry.pid_processo is not None and pid_atual != entry.pid_processo:
        # Novo processo (ex: novo AutoCAD abrindo o DWG), processo anterior foi encerrado
        houve_interrupcao = True
    elif entry.pid_processo is not None and not processo_esta_ativo(entry.pid_processo):
        # Processo anterior já não existe mais no sistema operacional (crash/kill)
        houve_interrupcao = True

    if houve_interrupcao:
        agora = timestamp_verificacao or _agora_utc_iso()
        fim_sessao_iso = entry.ultima_atividade or entry.ultima_atualizacao or entry.sessao_atual_inicio
        dt_inicio = _parse_iso(entry.sessao_atual_inicio)
        dt_fim = _parse_iso(fim_sessao_iso)

        duracao = 0.0
        if dt_inicio and dt_fim:
            duracao = max(0.0, (dt_fim - dt_inicio).total_seconds())

        entry.tempo_acumulado_segundos += duracao
        if entry.sessao_atual_inicio:
            entry.sessoes.append({
                "inicio": entry.sessao_atual_inicio,
                "fim": fim_sessao_iso,
                "duracao_segundos": round(duracao, 1),
                "tipo": "trabalho_interrompido",
            })

        entry.estado = TimeState.INTERROMPIDO
        entry.sessao_atual_inicio = None
        entry.pid_processo = None
        entry.token_sessao = None
        entry.ultima_atualizacao = agora
        salvar_tempo_projeto(root_dir, entry)
        logger.warning(
            f"Interrupção de sessão detectada e consolidada para SOB {entry.sob_id} ({duracao:.1f}s)",
            extra={"action": "tempo.interrompido", "sob_id": entry.sob_id, "duration_ms": duracao * 1000.0}
        )

    return entry


def iniciar_ou_retomar_tempo(
    root_dir: Union[str, Path],
    sob_id: Optional[str] = None,
    dwg_path: Optional[str] = None,
    timestamp_custom: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
    pid: Optional[int] = None,
    token_sessao: Optional[str] = None,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> OxCadTimeEntry:
    """Inicia ou retoma o apontamento de tempo do projeto."""
    p_root = Path(root_dir).resolve()
    agora = timestamp_iso or timestamp_custom or _agora_utc_iso()
    entry = carregar_tempo_projeto(root_dir)

    if not entry:
        sob_id_final = str(sob_id).strip() if sob_id else p_root.name
        return inicializar_tempo_projeto(
            root_dir,
            sob_id=sob_id_final,
            dwg_path=dwg_path,
            iniciar_imediatamente=True,
            timestamp_custom=agora,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )

    # Idempotência: se já está em execução, apenas atualiza DWG, PID, token e timestamp sem alterar contagem
    if entry.estado == TimeState.EM_EXECUCAO:
        if dwg_path and not entry.dwg_path:
            entry.dwg_path = str(dwg_path)
        if pid is not None:
            entry.pid_processo = pid
        if token_sessao is not None:
            entry.token_sessao = token_sessao
        entry.ultima_atualizacao = agora
        entry.ultima_atividade = agora
        salvar_tempo_projeto(root_dir, entry)
        return entry

    # Transição para EmExecucao (de Pausado, Interrompido, NaoIniciado ou Reaberto)
    if not entry.data_hora_inicio:
        entry.data_hora_inicio = agora

    entry.estado = TimeState.EM_EXECUCAO
    entry.sessao_atual_inicio = agora
    entry.ultima_atualizacao = agora
    entry.ultima_atividade = agora
    entry.data_hora_fim = None
    if pid is not None:
        entry.pid_processo = pid
    if token_sessao is not None:
        entry.token_sessao = token_sessao
    if dwg_path and not entry.dwg_path:
        entry.dwg_path = str(dwg_path)

    salvar_tempo_projeto(root_dir, entry)
    logger.info(
        f"Tempo de projeto em execução para SOB {entry.sob_id}",
        extra={
            "action": "tempo.iniciado",
            "sob_id": entry.sob_id,
            "dwg_path": entry.dwg_path,
            "process_id": pid,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        }
    )
    return entry


def pausar_tempo(
    root_dir: Union[str, Path],
    timestamp_custom: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Optional[OxCadTimeEntry]:
    """Pausa a contagem acumulando a duração da sessão ativa."""
    entry = carregar_tempo_projeto(root_dir)
    if not entry:
        return None

    agora = timestamp_iso or timestamp_custom or _agora_utc_iso()

    # Se estiver interrompido, transição limpa para Pausado (usuário optou por manter pausado)
    if entry.estado == TimeState.INTERROMPIDO:
        entry.estado = TimeState.PAUSADO
        entry.ultima_atualizacao = agora
        salvar_tempo_projeto(root_dir, entry)
        return entry

    # Idempotência: se já está pausado, concluído ou não iniciado, não altera estado nem sessões
    if entry.estado != TimeState.EM_EXECUCAO:
        return entry

    dt_agora = _parse_iso(agora) or datetime.now(timezone.utc)

    duracao_sessao = 0.0
    if entry.sessao_atual_inicio:
        dt_inicio = _parse_iso(entry.sessao_atual_inicio)
        if dt_inicio:
            duracao_sessao = max(0.0, (dt_agora - dt_inicio).total_seconds())

    entry.tempo_acumulado_segundos += duracao_sessao
    if entry.sessao_atual_inicio:
        entry.sessoes.append({
            "inicio": entry.sessao_atual_inicio,
            "fim": agora,
            "duracao_segundos": round(duracao_sessao, 1),
            "tipo": "trabalho",
        })

    entry.estado = TimeState.PAUSADO
    entry.sessao_atual_inicio = None
    entry.pid_processo = None
    entry.token_sessao = None
    entry.ultima_atualizacao = agora

    salvar_tempo_projeto(root_dir, entry)
    logger.info(
        f"Tempo de projeto pausado para SOB {entry.sob_id} ({entry.obter_tempo_formatado()})",
        extra={
            "action": "tempo.pausado",
            "sob_id": entry.sob_id,
            "duration_ms": duracao_sessao * 1000.0,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        },
    )
    return entry


def concluir_tempo(
    root_dir: Union[str, Path],
    timestamp_custom: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Optional[OxCadTimeEntry]:
    """Conclui em definitivo o apontamento do projeto."""
    entry = carregar_tempo_projeto(root_dir)
    if not entry:
        return None

    # Idempotência: se já está concluído, não altera datas nem estado
    if entry.estado == TimeState.CONCLUIDO:
        return entry

    agora = timestamp_iso or timestamp_custom or _agora_utc_iso()
    dt_agora = _parse_iso(agora) or datetime.now(timezone.utc)

    # Se estava rodando, acumula o intervalo até o encerramento
    if entry.estado == TimeState.EM_EXECUCAO and entry.sessao_atual_inicio:
        dt_inicio = _parse_iso(entry.sessao_atual_inicio)
        if dt_inicio:
            duracao = max(0.0, (dt_agora - dt_inicio).total_seconds())
            entry.tempo_acumulado_segundos += duracao
            entry.sessoes.append({
                "inicio": entry.sessao_atual_inicio,
                "fim": agora,
                "duracao_segundos": round(duracao, 1),
                "tipo": "trabalho",
            })

    entry.estado = TimeState.CONCLUIDO
    entry.data_hora_fim = agora
    entry.sessao_atual_inicio = None
    entry.pid_processo = None
    entry.token_sessao = None
    entry.ultima_atualizacao = agora

    salvar_tempo_projeto(root_dir, entry)
    logger.info(
        f"Tempo de projeto concluído para SOB {entry.sob_id} ({entry.obter_tempo_formatado()})",
        extra={
            "action": "tempo.concluido",
            "sob_id": entry.sob_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        }
    )
    return entry


def reabrir_tempo(
    root_dir: Union[str, Path],
    timestamp_custom: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Optional[OxCadTimeEntry]:
    """Reabre um apontamento previamente concluído, mantendo o histórico acumulado."""
    entry = carregar_tempo_projeto(root_dir)
    if not entry:
        return None

    # Idempotência: se não estiver concluído, retorna o estado atual sem alterar
    if entry.estado != TimeState.CONCLUIDO:
        return entry

    agora = timestamp_iso or timestamp_custom or _agora_utc_iso()
    entry.estado = TimeState.PAUSADO
    entry.data_hora_fim = None
    entry.ultima_atualizacao = agora
    salvar_tempo_projeto(root_dir, entry)
    logger.info(
        f"Tempo de projeto reaberto para SOB {entry.sob_id}",
        extra={
            "action": "tempo.reaberto",
            "sob_id": entry.sob_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        }
    )
    return entry

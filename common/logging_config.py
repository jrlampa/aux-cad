# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Infraestrutura Central de Logs, Auditoria e Observabilidade.
Responsabilidade única: Configuração de logging estruturado (JSON Lines),
rotação, sanitização de dados sensíveis, correlação ponta-a-ponta e medição de duração.

Diretrizes:
- Zero dependências externas pesadas (apenas biblioteca padrão Python).
- Logs estruturados em formato JSON Lines (.jsonl).
- Destino canônico: aux cad/logs/application.jsonl e logs/errors.jsonl.
- Rastreabilidade via correlation_id propagado entre C# e Python.
- Resiliência: falhas de I/O em logs nunca quebram o fluxo de negócio.
- Sanitização estrita: senhas, tokens, cookies e credenciais são mascarados.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, Callable, Dict, Optional, Union

# Raiz canônica do projeto AUX CAD
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent

# Padrões regex para detecção e mascaramento de credenciais e dados sensíveis
_SENSIBLE_PATTERNS = [
    (re.compile(r'(?i)(password|senha|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s&,]+)'), r'\1=***'),
    (re.compile(r'(?i)(access_token|refresh_token|token|jwt|bearer)\s*[:=]\s*["\']?([^"\'\s&,]+)'), r'\1=***'),
    (re.compile(r'(?i)(client_secret|secret_key|api_key|secret)\s*[:=]\s*["\']?([^"\'\s&,]+)'), r'\1=***'),
    (re.compile(r'(?i)(authorization:\s*bearer\s+)([A-Za-z0-9\-\._~\+\/]+=*)'), r'\1***'),
    (re.compile(r'(?i)(cookie:\s*)([^;\r\n]+)'), r'\1***'),
]


def sanitizar_mensagem(texto: Any) -> str:
    """
    Sanitiza uma mensagem ou representação em string, mascarando credenciais conhecidas.
    """
    if texto is None:
        return ""
    val_str = str(texto)
    for padrao, subst in _SENSIBLE_PATTERNS:
        val_str = padrao.sub(subst, val_str)
    return val_str


def sanitizar_dados(obj: Any) -> Any:
    """
    Sanitiza recursivamente dicionários, listas ou strings contra dados sensíveis.
    """
    if isinstance(obj, dict):
        novo = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "senha", "token", "secret", "cookie", "auth")):
                novo[k] = "***"
            else:
                novo[k] = sanitizar_dados(v)
        return novo
    elif isinstance(obj, list):
        return [sanitizar_dados(item) for item in obj]
    elif isinstance(obj, str):
        return sanitizar_mensagem(obj)
    return obj


def obter_diretorio_logs(base_dir: Optional[Path] = None) -> Path:
    """
    Localiza e assegura a existência do diretório central de logs do projeto.
    Possui fallback para diretório temporário caso não haja permissão de escrita.
    """
    root = base_dir or _DEFAULT_ROOT
    candidato = root / "logs"

    try:
        candidato.mkdir(parents=True, exist_ok=True)
        # Teste de escrita defensivo
        teste_arq = candidato / ".write_test"
        teste_arq.write_text("ok", encoding="utf-8")
        if teste_arq.exists():
            teste_arq.unlink()
        return candidato
    except Exception:
        # Fallback para diretório temporário do sistema operacional
        fallback = Path(tempfile.gettempdir()) / "auxcad_logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class JsonLinesFormatter(logging.Formatter):
    """
    Formatador de log estruturado que serializa cada registro em uma linha JSON única (.jsonl).
    Inclui metadados essenciais para observabilidade e correlação do sistema.
    """

    def __init__(self, app_name: str = "auxcad"):
        super().__init__()
        self.app_name = app_name

    def format(self, record: logging.LogRecord) -> str:
        agora_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Campos base obrigatórios
        evento: Dict[str, Any] = {
            "timestamp": agora_utc,
            "level": record.levelname,
            "logger": record.name,
            "message": sanitizar_mensagem(record.getMessage()),
            "process_id": record.process,
            "process_name": record.processName,
            "thread_id": record.thread,
        }

        # Extração de campos contextuais passados via extra
        contexto_campos = (
            "correlation_id",
            "sob_id",
            "dwg_path",
            "module",
            "action",
            "operation",
            "duration_ms",
            "result",
            "exit_code",
            "command",
            "subproc_pid",
            "target_pid",
            "pid",
        )

        for campo in contexto_campos:
            val = getattr(record, campo, None)
            if val is not None:
                if campo == "command":
                    evento[campo] = sanitizar_dados(val)
                elif campo == "duration_ms":
                    try:
                        evento[campo] = round(float(val), 2)
                    except (ValueError, TypeError):
                        evento[campo] = val
                else:
                    evento[campo] = sanitizar_mensagem(val) if isinstance(val, str) else val

        # Tratamento de exceções
        if record.exc_info:
            exc_type, exc_val, exc_tb = record.exc_info
            evento["exception_type"] = exc_type.__name__ if exc_type else "Exception"
            evento["exception_message"] = sanitizar_mensagem(str(exc_val)) if exc_val else ""
            evento["stack_trace"] = sanitizar_mensagem("".join(traceback.format_exception(*record.exc_info)))
        elif hasattr(record, "exception_type"):
            evento["exception_type"] = getattr(record, "exception_type")
            evento["exception_message"] = sanitizar_mensagem(getattr(record, "exception_message", ""))

        return json.dumps(evento, ensure_ascii=False)


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler resiliente contra contenção de arquivos e falhas de disco no Windows.
    Em caso de falha de rotação ou I/O, descarta o erro silenciosamente sem derrubar o processo.
    """

    def doRollover(self):
        try:
            super().doRollover()
        except Exception:
            # Em ambientes concorrentes no Windows, pode haver lock transitório
            pass

    def handleError(self, record):
        # Previne que exceções de logging quebrem a execução da aplicação
        pass


class OxCadLoggerAdapter(logging.LoggerAdapter):
    """
    Adapter contextual que enriquece os logs com correlation_id, sob_id e metadados operacionais.
    """

    def process(self, msg: Any, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.setdefault("extra", {})
        # Mescla o contexto do adapter com os argumentos da chamada
        for k, v in self.extra.items():
            if k not in extra:
                extra[k] = v
        return msg, kwargs

    def com_contexto(self, **novos_metadados) -> "OxCadLoggerAdapter":
        """Retorna uma nova instância com metadados mesclados."""
        ctx_atualizado = dict(self.extra)
        ctx_atualizado.update(novos_metadados)
        return OxCadLoggerAdapter(self.logger, ctx_atualizado)


_LOGGERS_INICIALIZADOS: Dict[str, logging.Logger] = {}
_LOCK_INICIALIZACAO = threading.Lock()


def configurar_logging(
    nivel: int = logging.INFO,
    diretorio_logs: Optional[Path] = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB por arquivo
    backup_count: int = 5,
    forcar: bool = False,
) -> Path:
    """
    Inicializa os handlers centrais de logging para o processo.
    Cria application.jsonl (todos os eventos) e errors.jsonl (nível ERROR e superior).
    Retorna o caminho do diretório de logs efetivo.
    """
    dir_logs = obter_diretorio_logs(diretorio_logs)

    with _LOCK_INICIALIZACAO:
        root_logger = logging.getLogger()
        existentes = [h for h in root_logger.handlers if isinstance(h, SafeRotatingFileHandler)]

        if existentes and not forcar and diretorio_logs is None:
            return dir_logs

        # Se forçar ou se um diretório específico foi solicitado, substitui os handlers
        for h in existentes:
            try:
                h.flush()
                h.close()
            except Exception:
                pass
            root_logger.removeHandler(h)

        root_logger.setLevel(nivel)
        formatter = JsonLinesFormatter()

        # 1. Handler principal: application.jsonl
        app_log_path = dir_logs / "application.jsonl"
        app_handler = SafeRotatingFileHandler(
            str(app_log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        app_handler.setLevel(nivel)
        app_handler.setFormatter(formatter)
        root_logger.addHandler(app_handler)

        # 2. Handler de erros: errors.jsonl
        err_log_path = dir_logs / "errors.jsonl"
        err_handler = SafeRotatingFileHandler(
            str(err_log_path),
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=3,
            encoding="utf-8",
        )
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(formatter)
        root_logger.addHandler(err_handler)

    return dir_logs


def get_logger(nome: str = "oxcad", **contexto_inicial) -> OxCadLoggerAdapter:
    """
    Obtém um logger contextualizado configurado com saída estruturada JSON Lines.
    Garante inicialização automática da infraestrutura se ainda não configurada.
    """
    configurar_logging()
    logger_base = logging.getLogger(nome)
    return OxCadLoggerAdapter(logger_base, contexto_inicial)


@contextmanager
def cronometrar(
    logger: Union[OxCadLoggerAdapter, logging.Logger],
    operacao: str,
    nivel: int = logging.INFO,
    correlation_id: Optional[str] = None,
    sob_id: Optional[str] = None,
    **metadados_extras,
):
    """
    Context manager para medição de duração com registro automático de início, fim ou falha.
    Exemplo:
        with cronometrar(logger, "abrir_cqt", correlation_id=cid, sob_id=sob) as ctx:
            executar_tarefa()
            ctx["itens"] = 10
    """
    t_inicio = time.perf_counter()
    ctx = dict(metadados_extras)
    if correlation_id:
        ctx["correlation_id"] = correlation_id
    if sob_id:
        ctx["sob_id"] = sob_id

    ctx["operation"] = operacao
    ctx["result"] = "iniciado"

    logger.log(
        nivel,
        f"Iniciando operação: {operacao}",
        extra=ctx,
    )

    try:
        yield ctx
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        ctx["duration_ms"] = duracao_ms
        ctx["result"] = "sucesso"
        logger.log(
            nivel,
            f"Operação concluída com sucesso: {operacao} ({duracao_ms:.1f}ms)",
            extra=ctx,
        )
    except Exception as ex:
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        ctx["duration_ms"] = duracao_ms
        ctx["result"] = "falha"
        ctx["exception_type"] = type(ex).__name__
        ctx["exception_message"] = str(ex)
        logger.error(
            f"Falha na operação: {operacao} ({duracao_ms:.1f}ms) — {ex}",
            exc_info=True,
            extra=ctx,
        )
        raise


def medir_duracao(
    logger: Union[OxCadLoggerAdapter, logging.Logger],
    operacao: Optional[str] = None,
    nivel: int = logging.INFO,
):
    """
    Decorator para funções e métodos para aferição automática de duração e observabilidade.
    """
    def decorator(func: Callable):
        nome_op = operacao or func.__name__

        def wrapper(*args, **kwargs):
            cid = kwargs.get("correlation_id")
            sob = kwargs.get("sob_id")
            with cronometrar(logger, nome_op, nivel=nivel, correlation_id=cid, sob_id=sob):
                return func(*args, **kwargs)

        return wrapper
    return decorator

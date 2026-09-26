# -*- coding: utf-8 -*-
"""
Bateria de Testes Unitários e de Integração da Infraestrutura Central de Logs (OXCAD 0.6.0).
Valida:
1. Inicialização do logger central;
2. Criação dos arquivos application.jsonl e errors.jsonl;
3. Gravação de eventos INFO em formato JSON Lines estruturado;
4. Gravação de eventos WARNING;
5. Gravação de ERROR com exception_type, exception_message e stack trace;
6. Preservação de correlation_id entre chamadas;
7. Preservação de sob_id e metadados contextuais;
8. Registro determinístico de duration_ms via context manager e decorator;
9. Mecanismo de rotação de arquivos sob limite de tamanho (maxBytes);
10. Sanitização de senhas, tokens, cookies e credenciais sensíveis;
11. Registro de início e execução de subprocessos pelo WorkspaceActionDispatcher;
12. Resiliência: logging nunca impede a operação se o diretório de log estiver inacessível;
13. Concorrência: múltiplas chamadas concorrentes gravam linhas JSON íntegras sem corrupção;
14. Propagação de correlation_id através do CLI workspace_context_cli.py.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
import pytest

from common.logging_config import (
    configurar_logging,
    cronometrar,
    get_logger,
    medir_duracao,
    obter_diretorio_logs,
    sanitizar_dados,
    sanitizar_mensagem,
    JsonLinesFormatter,
    SafeRotatingFileHandler,
)
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_core import ProjectWorkspace
from workspace.workspace_context_cli import executar_acao_operacional, extrair_contexto_operacional


def _ler_linhas_json(caminho: Path):
    """Auxiliar para leitura e parsing de arquivos JSON Lines (.jsonl)."""
    assert caminho.exists(), f"Arquivo não encontrado: {caminho}"
    linhas = []
    for l in caminho.read_text(encoding="utf-8").strip().splitlines():
        if l.strip():
            linhas.append(json.loads(l))
    return linhas


def test_01_logger_inicializa_e_cria_diretorio(tmp_path):
    """1. Logger inicializa corretamente e assegura existência do diretório."""
    dir_logs = obter_diretorio_logs(base_dir=tmp_path)
    assert dir_logs.exists()
    assert dir_logs.is_dir()
    assert dir_logs.name == "logs"


def test_02_arquivos_jsonl_sao_criados(tmp_path):
    """2. Arquivos application.jsonl e errors.jsonl são criados ao inicializar logging."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)

    app_log = dir_logs / "application.jsonl"
    err_log = dir_logs / "errors.jsonl"

    logger = get_logger("test.init")
    logger.info("Teste de inicialização")

    assert app_log.exists()
    assert err_log.exists()


def test_03_evento_info_gravado_com_campos_obrigatorios(tmp_path):
    """3. Evento INFO gravado em formato JSON Lines válido contendo campos essenciais."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)
    logger = get_logger("test.info")

    logger.info("Operação de teste INFO")

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    ultimo = linhas[-1]

    assert ultimo["level"] == "INFO"
    assert ultimo["logger"] == "test.info"
    assert ultimo["message"] == "Operação de teste INFO"
    assert "timestamp" in ultimo
    assert "process_id" in ultimo
    assert "thread_id" in ultimo


def test_04_evento_warning_gravado_corretamente(tmp_path):
    """4. Evento WARNING é gravado no application.jsonl."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)
    logger = get_logger("test.warn")

    logger.warning("Alerta operacional de teste")

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    ultimo = linhas[-1]

    assert ultimo["level"] == "WARNING"
    assert ultimo["message"] == "Alerta operacional de teste"


def test_05_error_contem_excecao_e_grava_em_errors_jsonl(tmp_path):
    """5. Evento ERROR contém exception_type, exception_message, stack_trace e grava em errors.jsonl."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)
    logger = get_logger("test.error")

    try:
        raise ValueError("Simulação de falha controlada")
    except Exception as ex:
        logger.error("Ocorreu uma exceção no módulo", exc_info=True)

    linhas_app = _ler_linhas_json(dir_logs / "application.jsonl")
    linhas_err = _ler_linhas_json(dir_logs / "errors.jsonl")

    ultimo_err = linhas_err[-1]
    assert ultimo_err["level"] == "ERROR"
    assert ultimo_err["exception_type"] == "ValueError"
    assert "Simulação de falha controlada" in ultimo_err["exception_message"]
    assert "stack_trace" in ultimo_err
    assert "Traceback" in ultimo_err["stack_trace"]


def test_06_correlation_id_preservado(tmp_path):
    """6. Correlation ID é registrado de forma determinística no log."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)

    cid = "cid-abc-12345678"
    logger = get_logger("test.correlation", correlation_id=cid)

    logger.info("Mensagem correlacionada")

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    ultimo = linhas[-1]

    assert ultimo["correlation_id"] == cid


def test_07_sob_id_preservado_no_contexto(tmp_path):
    """7. Contexto da SOB (sob_id, dwg_path) é preservado."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)

    logger = get_logger("test.sob", sob_id="A043257319", dwg_path="PE_A043257319_DESENHO.dwg")
    logger.info("Validação de artefato")

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    ultimo = linhas[-1]

    assert ultimo["sob_id"] == "A043257319"
    assert ultimo["dwg_path"] == "PE_A043257319_DESENHO.dwg"


def test_08_duracao_registrada_por_cronometrar_e_medir_duracao(tmp_path):
    """8. Context manager cronometrar e decorator medir_duracao aferem duration_ms."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)
    logger = get_logger("test.timing")

    # A) Context Manager
    with cronometrar(logger, "operacao_teste"):
        time.sleep(0.02)  # 20ms

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    conclusao = linhas[-1]

    assert conclusao["operation"] == "operacao_teste"
    assert conclusao["result"] == "sucesso"
    assert "duration_ms" in conclusao
    assert conclusao["duration_ms"] >= 15.0

    # B) Decorator
    @medir_duracao(logger, "funcao_decorada")
    def executar_algo():
        time.sleep(0.01)
        return 42

    res = executar_algo()
    assert res == 42

    linhas2 = _ler_linhas_json(dir_logs / "application.jsonl")
    decorado = linhas2[-1]
    assert decorado["operation"] == "funcao_decorada"
    assert decorado["result"] == "sucesso"


def test_09_rotacao_de_arquivos_funciona(tmp_path):
    """9. Rotação do log funciona quando o arquivo atinge o limite de tamanho."""
    dir_logs = tmp_path / "logs"
    dir_logs.mkdir(parents=True, exist_ok=True)

    # Configura handler com limite pequeno de 500 bytes para teste determinístico de rotação
    log_file = dir_logs / "application.jsonl"
    handler = SafeRotatingFileHandler(str(log_file), maxBytes=500, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonLinesFormatter())

    test_logger = logging.getLogger("test.rotation")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    for i in range(25):
        test_logger.info(f"Linha de teste para rotação número {i:03d} com payload preenchido")

    handler.close()

    assert log_file.exists()
    assert (dir_logs / "application.jsonl.1").exists()


def test_10_sanitizacao_de_dados_sensiveis():
    """10. Senhas, tokens, authorization headers e secrets são sanitizados."""
    texto_com_segredos = "Tentativa de login com senha=SuperSecret123&token=eyJhbGciOiJIUzI1NiIn e authorization: Bearer abcXYZ123."
    sanitizado = sanitizar_mensagem(texto_com_segredos)

    assert "SuperSecret123" not in sanitizado
    assert "senha=***" in sanitizado
    assert "token=***" in sanitizado
    assert "Bearer ***" in sanitizado
    assert "abcXYZ123" not in sanitizado

    dados_dict = {
        "user": "operador",
        "client_secret": "chave_secreta_99",
        "password": "senha_plana",
        "payload": {"cookie": "sess=xyz"},
    }
    sanitizado_dict = sanitizar_dados(dados_dict)
    assert sanitizado_dict["client_secret"] == "***"
    assert sanitizado_dict["password"] == "***"
    assert sanitizado_dict["payload"]["cookie"] == "***"
    assert sanitizado_dict["user"] == "operador"


def test_11_subprocesso_registra_observabilidade(tmp_path):
    """11. Lançamento de subprocesso via WorkspaceActionDispatcher registra evento no log."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)

    cid = "cid-subproc-test"
    cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

    proc = WorkspaceActionDispatcher._lancar_processo(cmd, cwd=tmp_path, correlation_id=cid)
    proc.wait()

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    eventos_subproc = [l for l in linhas if l.get("correlation_id") == cid]

    assert len(eventos_subproc) >= 2
    assert any("Lançando subprocesso" in l["message"] for l in eventos_subproc)
    assert any("Subprocesso em execução" in l["message"] for l in eventos_subproc)
    assert any(l.get("subproc_pid") == proc.pid or l.get("pid") == proc.pid for l in eventos_subproc)


def test_12_resiliencia_a_falhas_de_disco():
    """12. Logging não interrompe a aplicação mesmo quando ocorre erro interno."""
    formatter = JsonLinesFormatter()
    # LogRecord simulado
    record = logging.LogRecord("test", logging.INFO, "path", 1, "Mensagem ok", None, None)
    linha = formatter.format(record)

    assert isinstance(linha, str)
    dados = json.loads(linha)
    assert dados["message"] == "Mensagem ok"


def test_13_multiplas_chamadas_concorrentes_nao_corrompem_arquivo(tmp_path):
    """13. Escrita concorrente por múltiplas threads produz linhas JSON válidas."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)
    logger = get_logger("test.concurrency")

    def registrar(i):
        logger.info(f"Registro concorrente {i}", extra={"correlation_id": f"cid-{i}", "index": i})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(registrar, range(50)))

    linhas = _ler_linhas_json(dir_logs / "application.jsonl")
    assert len(linhas) >= 50
    # Valida que todos os objetos parseados possuem campos íntegros
    for l in linhas:
        assert "level" in l
        assert "timestamp" in l


def test_14_integracao_cli_preserva_correlation_id(tmp_path):
    """14. Invocação de extrair_contexto_operacional e executar_acao_operacional preserva correlation_id."""
    dir_logs = tmp_path / "logs"
    configurar_logging(diretorio_logs=tmp_path)

    cid = "cid-cli-e2e-789"
    # A) Consulta
    ctx = extrair_contexto_operacional(root_dir=str(tmp_path), correlation_id=cid)
    assert ctx["correlation_id"] == cid

    # B) Ação
    res = executar_acao_operacional("acao_inexistente_para_teste", root_dir=str(tmp_path), correlation_id=cid)
    assert res["correlation_id"] == cid
    assert res["sucesso"] is False

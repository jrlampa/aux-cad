# -*- coding: utf-8 -*-
"""
Interface Headless de Contexto Operacional do Workspace para OXCAD.
Responsabilidade única: Receber o caminho do DWG ou diretório, consultar
o ProjectWorkspace e o WorkspaceScanner, detectar eventuais inconsistências
e retornar estritamente um contrato JSON serializável.

NÃO contém Tkinter.
NÃO contém execução de especialistas ou ações de engenharia.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import warnings

# Suprime warnings de pacotes terceiros (ex: urllib3/requests) para manter stdout 100% JSON limpo
warnings.filterwarnings("ignore")

# Garante a resolução correta dos módulos do projeto
_curr_dir = Path(__file__).resolve().parent
_root_dir = _curr_dir.parent
for _d in [str(_curr_dir), str(_root_dir)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_time import (
    carregar_tempo_projeto,
    iniciar_ou_retomar_tempo,
    pausar_tempo,
    concluir_tempo,
    reabrir_tempo,
    inicializar_tempo_projeto,
    tratar_interrupcao_se_necessario,
    atualizar_heartbeat_tempo,
)
import time
import uuid
from common.logging_config import get_logger

logger = get_logger("oxcad.workspace.cli")


def _obter_metadados_locais(root_dir: Path, sob_id: str) -> Dict[str, str]:
    """
    Recupera metadados (Município, Bairro, Endereço) de arquivos conhecidos
    da SOB caso existam, retornando '-' para campos inexistentes.
    Nunca inventa dados.
    """
    meta = {
        "municipio": "-",
        "bairro": "-",
        "endereco": "-",
    }

    if not root_dir.exists() or not root_dir.is_dir():
        return meta

    # 1. Tenta ler de .sob_state.json (manifesto de preparação da SOB)
    manifesto_path = root_dir / ".sob_state.json"
    if manifesto_path.exists() and manifesto_path.is_file():
        try:
            dados = json.loads(manifesto_path.read_text(encoding="utf-8"))
            if dados.get("municipio"):
                meta["municipio"] = str(dados["municipio"]).strip().upper()
            if dados.get("bairro"):
                meta["bairro"] = str(dados["bairro"]).strip().upper()
            if dados.get("endereco"):
                meta["endereco"] = str(dados["endereco"]).strip()
        except Exception:
            pass

    # 2. Tenta ler de preferências ambientais se município estiver vazio
    if meta["municipio"] == "-":
        pref_amb = root_dir / "preferencias_ambiental.json"
        if pref_amb.exists() and pref_amb.is_file():
            try:
                dados_amb = json.loads(pref_amb.read_text(encoding="utf-8"))
                if dados_amb.get("municipio"):
                    meta["municipio"] = str(dados_amb["municipio"]).strip().upper()
            except Exception:
                pass

    return meta


def _gerar_matriz_artefatos(ws: ProjectWorkspace) -> List[Dict[str, Any]]:
    """
    Normaliza a matriz de artefatos para apresentação na paleta OXCAD.
    Mapeia os principais artefatos monitorados com rótulos amigáveis.
    """
    ordem_chaves = [
        ("DWG", "DWG Principal"),
        ("CROQUI", "Pasta de Croqui de Campo"),
        ("DOCUMENTOS", "Documentos e Anexos"),
        ("CHECKLIST_AMBIENTAL", "Checklist Ambiental"),
        ("MEMORIAL_AMBIENTAL", "Memorial Ambiental"),
        ("CROQUI_AMBIENTAL", "Croqui Satélite"),
        ("CQT", "Queda de Tensão (CQT)"),
        ("ORCAMENTO", "Orçamento de Materiais"),
        ("CPFC", "Participação Financeira (CPFC)"),
        ("UNIFILAR", "Diagrama Unifilar"),
    ]

    matriz = []
    for chave, rotulo in ordem_chaves:
        art = ws.artefatos.get(chave)
        st = art.status.value if art else ArtifactStatus.NAO_EXISTE.value
        existe = (st == ArtifactStatus.EXISTE.value)
        caminho_str = str(art.caminho) if (art and art.caminho) else None
        nome_arquivo = art.caminho.name if (art and art.caminho) else None

        matriz.append({
            "chave": chave,
            "rotulo": rotulo,
            "status": st,
            "existe": existe,
            "icone": "✓" if existe else "○",
            "caminho": caminho_str,
            "nome_arquivo": nome_arquivo,
        })

    return matriz


def extrair_contexto_operacional(
    dwg_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    sob_id_esperada: Optional[str] = None,
    acad_pid: Optional[int] = None,
    acad_token: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extrai o contexto operacional completo conectando o DWG ou diretório
    ao ProjectWorkspace e WorkspaceScanner.
    """
    t_inicio = time.perf_counter()
    logger.info(
        "Iniciando extração de contexto operacional",
        extra={
            "correlation_id": correlation_id,
            "dwg_path": dwg_path,
            "root_dir": root_dir,
            "action": "consultar_contexto"
        }
    )
    # 1. Determinação de diretório e arquivo DWG
    p_dwg: Optional[Path] = None
    p_root: Optional[Path] = None
    sob_dwg: Optional[str] = None

    if dwg_path:
        p_dwg = Path(dwg_path).resolve()
        sob_dwg = WorkspaceScanner.extrair_sob_de_texto(p_dwg.name)
        if not root_dir:
            p_root = p_dwg.parent
        else:
            p_root = Path(root_dir).resolve()
    elif root_dir:
        p_root = Path(root_dir).resolve()

    if not p_root:
        p_root = Path.cwd()

    # 2. Verificação de existência física do diretório
    if not p_root.exists() or not p_root.is_dir():
        return {
            "sob_id": sob_id_esperada or sob_dwg or "-",
            "root_dir": str(p_root),
            "dwg_principal": p_dwg.name if p_dwg else "-",
            "municipio": "-",
            "bairro": "-",
            "endereco": "-",
            "artefatos": [],
            "status": "Diretório não encontrado",
            "inconsistencia": False,
            "mensagem_inconsistencia": "",
            "erro": f"Diretório inexistente ou inacessível: {p_root}",
        }

    # 3. Execução da varredura pelo scanner oficial
    # O scanner examina o diretório e seus arquivos para determinar a SOB do Workspace
    ws = WorkspaceScanner.scan(p_root, sob_id=sob_id_esperada)

    # 4. Avaliação de Inconsistência de Contexto (Seção 13)
    inconsistencia = False
    msg_inconsistencia = ""

    # Se o nome do DWG aponta explicitamente para uma SOB diferente da SOB do Workspace da pasta
    if sob_dwg and ws.sob_id and sob_dwg != ws.sob_id and ws.sob_id != "PROJETO":
        inconsistencia = True
        msg_inconsistencia = f"DWG: {sob_dwg} | Workspace: {ws.sob_id}"
        status_texto = "⚠ Inconsistência de contexto"
    else:
        # Se não há conflito com a pasta e o DWG tem SOB, adota a SOB do DWG caso ws seja genérico
        if ws.sob_id == "PROJETO" and sob_dwg:
            ws = WorkspaceScanner.scan(p_root, sob_id=sob_dwg)

        if ws.sob_id and ws.sob_id != "PROJETO":
            status_texto = "Projeto identificado"
        else:
            status_texto = "Contexto identificado"

    # 5. Recuperação de Metadados locais
    metadados = _obter_metadados_locais(p_root, ws.sob_id)

    # 6. Matriz de artefatos normalizada
    artefatos_lista = _gerar_matriz_artefatos(ws)

    # 7. Nome do DWG exibido
    dwg_exibido = "-"
    if ws.dwg_principal and ws.dwg_principal.exists():
        dwg_exibido = ws.dwg_principal.name
    elif p_dwg:
        dwg_exibido = p_dwg.name

    # 8. Estado do apontamento de tempo do projeto (OXCAD 0.5.2 com detecção por PID + Token de Sessão)
    entry_tempo = tratar_interrupcao_se_necessario(ws.root_dir, pid_atual=acad_pid, token_sessao_atual=acad_token)
    if not entry_tempo:
        entry_tempo = carregar_tempo_projeto(ws.root_dir)

    if entry_tempo:
        tempo_dados = entry_tempo.para_dicionario()
    else:
        tempo_dados = {
            "sob_id": ws.sob_id if ws.sob_id else "-",
            "dwg_path": dwg_exibido if dwg_exibido != "-" else None,
            "estado": "NaoIniciado",
            "data_hora_inicio": None,
            "data_hora_fim": None,
            "tempo_acumulado_segundos": 0.0,
            "sessao_atual_inicio": None,
            "ultima_atualizacao": None,
            "ultima_atividade": None,
            "pid_processo": None,
            "token_sessao": None,
            "tempo_total_segundos": 0.0,
            "tempo_formatado": "00:00:00",
            "inicio_formatado": "-",
            "fim_formatado": "-",
            "sessoes": [],
        }

    duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
    logger.info(
        f"Contexto operacional extraído com sucesso ({duracao_ms:.1f}ms)",
        extra={
            "correlation_id": correlation_id,
            "sob_id": ws.sob_id if ws.sob_id else "-",
            "dwg_path": dwg_exibido,
            "duration_ms": duracao_ms,
            "result": "sucesso",
            "action": "consultar_contexto"
        }
    )

    return {
        "sob_id": ws.sob_id if ws.sob_id else "-",
        "root_dir": str(ws.root_dir),
        "dwg_principal": dwg_exibido,
        "municipio": metadados["municipio"],
        "bairro": metadados["bairro"],
        "endereco": metadados["endereco"],
        "artefatos": artefatos_lista,
        "status": status_texto,
        "inconsistencia": inconsistencia,
        "mensagem_inconsistencia": msg_inconsistencia,
        "tempo": tempo_dados,
        "correlation_id": correlation_id,
        "erro": None,
    }


def executar_acao_operacional(
    acao: str,
    dwg_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    alvo: Optional[str] = None,
    acad_pid: Optional[int] = None,
    acad_token: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executa uma ação do Workspace através do WorkspaceActionDispatcher existente.
    Retorna um dicionário estruturado com o resultado da execução.
    """
    t_inicio = time.perf_counter()
    acao_limpa = (acao or "").strip().lower()

    logger.info(
        f"Recebida solicitação de ação: {acao_limpa}",
        extra={
            "correlation_id": correlation_id,
            "action": acao_limpa,
            "dwg_path": dwg_path,
            "alvo": alvo,
            "acad_pid": acad_pid
        }
    )

    # Resolve o contexto físico preliminar
    p_dwg = Path(dwg_path).resolve() if dwg_path else None
    p_root = Path(root_dir).resolve() if root_dir else (p_dwg.parent if p_dwg else Path.cwd())

    # Ações dedicadas ao controle operacional de tempo do projeto (OXCAD 0.5.2)
    if acao_limpa in ("tempo_iniciar", "tempo_retomar"):
        sob_id_cand = WorkspaceScanner.extrair_sob_de_texto(p_dwg.name) if p_dwg else None
        if not sob_id_cand:
            ws_tmp = WorkspaceScanner.scan(p_root)
            sob_id_cand = ws_tmp.sob_id or "PROJETO"
        entry = iniciar_ou_retomar_tempo(
            p_root,
            sob_id_cand,
            dwg_path=str(p_dwg) if p_dwg else None,
            pid=acad_pid,
            token_sessao=acad_token,
        )
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value,
            "mensagem": f"Apontamento de tempo em execução ({entry.obter_tempo_formatado()}).",
            "pid": acad_pid,
            "erro": None,
        }

    if acao_limpa == "tempo_pausar":
        entry = pausar_tempo(p_root)
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": f"Apontamento pausado em {entry.obter_tempo_formatado()}.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento ativo para pausar.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    if acao_limpa == "tempo_heartbeat":
        entry = atualizar_heartbeat_tempo(p_root, pid=acad_pid, token_sessao=acad_token)
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value if entry else "NaoIniciado",
            "mensagem": "Heartbeat de sessão registrado.",
            "pid": acad_pid,
            "erro": None,
        }

    if acao_limpa == "tempo_interromper":
        entry = tratar_interrupcao_se_necessario(p_root, forcar_interrupcao=True)
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value if entry else "Pausado",
            "mensagem": "Sessão interrompida consolidada com sucesso.",
            "pid": None,
            "erro": None,
        }

    if acao_limpa == "tempo_concluir":
        entry = concluir_tempo(p_root)
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": f"Apontamento concluído. Tempo total: {entry.obter_tempo_formatado()}.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento ativo para concluir.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    if acao_limpa == "tempo_reabrir":
        entry = reabrir_tempo(p_root)
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": "Apontamento reaberto com histórico preservado.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento encontrado para reabrir.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    # Tratamento específico: Unifilar requer interação manual no AutoCAD
    if acao_limpa == "unifilar":
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Requer especificação",
            "mensagem": "O Diagrama Unifilar requer interação gráfica dentro do AutoCAD (comandos UNIFILAR ou PROTECAO).",
            "pid": None,
            "erro": None,
        }

    # Resolve o contexto físico
    p_dwg = Path(dwg_path).resolve() if dwg_path else None
    p_root = Path(root_dir).resolve() if root_dir else (p_dwg.parent if p_dwg else Path.cwd())

    # Ação de abrir artefato físico
    if acao_limpa == "abrir":
        alvo_path = Path(alvo).resolve() if alvo else p_dwg
        if not alvo_path or not alvo_path.exists():
            return {
                "sucesso": False,
                "acao": acao_limpa,
                "estado": "Falhou",
                "mensagem": f"Artefato não encontrado no disco: {alvo_path}",
                "pid": None,
                "correlation_id": correlation_id,
                "erro": "Arquivo ou diretório inexistente.",
            }
        ok = WorkspaceActionDispatcher.abrir_artefato(alvo_path, correlation_id=correlation_id)
        return {
            "sucesso": ok,
            "acao": acao_limpa,
            "estado": "Concluído" if ok else "Falhou",
            "mensagem": f"Artefato aberto no aplicativo padrão: {alvo_path.name}" if ok else "Falha ao abrir artefato.",
            "pid": None,
            "correlation_id": correlation_id,
            "erro": None if ok else "Falha no despacho do sistema operacional.",
        }

    # Ação de localizar no Explorer
    if acao_limpa == "localizar":
        alvo_path = Path(alvo).resolve() if alvo else p_root
        ok = WorkspaceActionDispatcher.localizar_artefato(alvo_path, correlation_id=correlation_id)
        return {
            "sucesso": ok,
            "acao": acao_limpa,
            "estado": "Concluído" if ok else "Falhou",
            "mensagem": f"Localizado no Explorer: {alvo_path.name}" if ok else "Falha ao abrir Explorer.",
            "pid": None,
            "correlation_id": correlation_id,
            "erro": None if ok else "Falha no despacho do Explorer.",
        }

    # Demais ações requerem resolução de ProjectWorkspace
    ws = WorkspaceScanner.scan(p_root)

    try:
        proc: Optional[Any] = None

        if acao_limpa == "cqt":
            proc = WorkspaceActionDispatcher.executar_cqt(ws, correlation_id=correlation_id)
            nome_modulo = "CQT (Queda de Tensão BT)"
        elif acao_limpa == "orcamento":
            proc = WorkspaceActionDispatcher.executar_orcamento(ws, correlation_id=correlation_id)
            nome_modulo = "Orçamento de Materiais"
        elif acao_limpa == "cpfc":
            proc = WorkspaceActionDispatcher.executar_cpfc(ws, correlation_id=correlation_id)
            nome_modulo = "Participação Financeira (CPFC)"
        elif acao_limpa == "ambiental":
            proc = WorkspaceActionDispatcher.executar_ambiental(ws, correlation_id=correlation_id)
            nome_modulo = "Memorial e Checklist Ambiental"
        elif acao_limpa == "prancha":
            proc = WorkspaceActionDispatcher.executar_prancha(ws, correlation_id=correlation_id)
            duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
            return {
                "sucesso": True,
                "acao": "prancha",
                "estado": "AutoCAD",
                "mensagem": "Módulo AutoPranche: Contexto exportado. Digite AUTOPRANCHA no AutoCAD.",
                "pid": proc.pid if proc else None,
                "correlation_id": correlation_id,
                "duration_ms": round(duracao_ms, 2),
                "erro": None,
            }
        elif acao_limpa == "sob":
            proc = WorkspaceActionDispatcher.executar_sob(ws, correlation_id=correlation_id)
            nome_modulo = "Preparador de SOB"
        else:
            return {
                "sucesso": False,
                "acao": acao_limpa,
                "estado": "Requer especificação",
                "mensagem": f"Ação '{acao}' não homologada ou requer especificação adicional.",
                "pid": None,
                "correlation_id": correlation_id,
                "erro": "Ação desconhecida.",
            }

        pid = proc.pid if proc else None
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        logger.info(
            f"Ação {acao_limpa} concluída com sucesso ({duracao_ms:.1f}ms)",
            extra={
                "correlation_id": correlation_id,
                "action": acao_limpa,
                "duration_ms": duracao_ms,
                "process_id": pid,
                "result": "sucesso"
            }
        )
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": "Executando...",
            "mensagem": f"Módulo {nome_modulo} iniciado com sucesso.",
            "pid": pid,
            "correlation_id": correlation_id,
            "duration_ms": round(duracao_ms, 2),
            "erro": None,
        }

    except Exception as ex:
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        logger.error(
            f"Erro ao disparar ação {acao_limpa} ({duracao_ms:.1f}ms): {ex}",
            exc_info=True,
            extra={
                "correlation_id": correlation_id,
                "action": acao_limpa,
                "duration_ms": duracao_ms,
                "result": "falha"
            }
        )
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": f"Erro ao disparar ação {acao_limpa}: {ex}",
            "pid": None,
            "correlation_id": correlation_id,
            "duration_ms": round(duracao_ms, 2),
            "erro": str(ex),
        }


def main():
    parser = argparse.ArgumentParser(description="AUX CAD — Headless Context and Action CLI for OXCAD")
    parser.add_argument("--dwg", type=str, help="Caminho do arquivo DWG ativo")
    parser.add_argument("--dir", type=str, help="Caminho do diretório raiz do projeto")
    parser.add_argument("--sob", type=str, help="Identificador SOB esperado (opcional)")
    parser.add_argument("--acao", type=str, help="Ação do Dispatcher a executar (ex: cqt, orcamento, cpfc, ambiental, prancha, sob, abrir)")
    parser.add_argument("--alvo", type=str, help="Caminho do artefato alvo para ações como abrir ou localizar")
    parser.add_argument("--acad-pid", type=int, help="Identificador de processo (PID) do AutoCAD chamador")
    parser.add_argument("--acad-token", type=str, help="Token/SessionId identificador único do AutoCAD chamador")
    parser.add_argument("--correlation-id", type=str, default=None, help="Identificador único de correlação da operação")

    args = parser.parse_args()
    correlation_id = args.correlation_id or uuid.uuid4().hex

    try:
        # Se uma ação foi solicitada, executa o despacho
        if args.acao:
            resultado = executar_acao_operacional(
                acao=args.acao,
                dwg_path=args.dwg,
                root_dir=args.dir,
                alvo=args.alvo,
                acad_pid=args.acad_pid,
                acad_token=args.acad_token,
                correlation_id=correlation_id,
            )
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            sys.exit(0 if resultado["sucesso"] else 1)

        # Caso contrário, consulta o contexto operacional
        resultado = extrair_contexto_operacional(
            dwg_path=args.dwg,
            root_dir=args.dir,
            sob_id_esperada=args.sob,
            acad_pid=args.acad_pid,
            acad_token=args.acad_token,
            correlation_id=correlation_id,
        )
        # Saída JSON estrita na stdout com utf-8
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        sys.exit(0)
    except Exception as ex:
        logger.error(f"Erro fatal na execução CLI: {ex}", exc_info=True, extra={"correlation_id": correlation_id})
        erro_json = {
            "sob_id": "-",
            "root_dir": args.dir or "-",
            "dwg_principal": args.dwg or "-",
            "municipio": "-",
            "bairro": "-",
            "endereco": "-",
            "artefatos": [],
            "status": "Erro na execução CLI",
            "inconsistencia": False,
            "mensagem_inconsistencia": "",
            "correlation_id": correlation_id,
            "erro": str(ex),
        }
        print(json.dumps(erro_json, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()


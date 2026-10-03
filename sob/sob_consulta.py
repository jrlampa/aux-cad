# -*- coding: utf-8 -*-
"""Consulta e download de anexos de uma SOB no GOMNET para a Palette AutoCAD."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

try:
    from sob.sob_core import obter_sob_id, validar_sob
    from sob.sob_gomnet import GomnetAnexo, GomnetClient
except ModuleNotFoundError:
    from sob_core import obter_sob_id, validar_sob
    from sob_gomnet import GomnetAnexo, GomnetClient


MENSAGEM_STATUS_INDISPONIVEL = "Status cadastral não encontrado no grid principal do GOMNET."


def avaliar_contexto_oxcad(
    sob_consultada: str,
    contexto_ativo_sob: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Avalia a relação entre a SOB consultada e o contexto de projeto ativo no AutoCAD.
    Soberania de identidade:
      AutoCAD -> FingerprintGuid -> AUXCAD_PROJECT_SCOPE -> SOB_ID
    O Python não pode fabricar identidade e apenas compara a identidade fornecida pelo Host.
    """
    sob_norm = (obter_sob_id(sob_consultada) or "").strip().upper()
    if not contexto_ativo_sob or not str(contexto_ativo_sob).strip():
        return {
            "status_contexto": "SEM_CONTEXTO",
            "congruente": False,
            "contexto_ativo_sob": None,
            "sob_consultada": sob_norm,
            "vinculado_projeto_ativo": False,
            "mensagem": "Nenhum projeto OXCAD vinculado ao DWG ativo (operação avulsa de consulta).",
        }

    try:
        ctx_norm = (obter_sob_id(contexto_ativo_sob) or "").strip().upper()
        if not validar_sob(ctx_norm):
            raise ValueError("SOB inválida.")
    except Exception:
        return {
            "status_contexto": "CONTEXTO_INVALIDO",
            "congruente": False,
            "contexto_ativo_sob": str(contexto_ativo_sob),
            "sob_consultada": sob_norm,
            "vinculado_projeto_ativo": False,
            "mensagem": f"Contexto de projeto ativo informado possui formato inválido ({contexto_ativo_sob}).",
        }

    if sob_norm == ctx_norm:
        return {
            "status_contexto": "CONGRUENTE",
            "congruente": True,
            "contexto_ativo_sob": ctx_norm,
            "sob_consultada": sob_norm,
            "vinculado_projeto_ativo": True,
            "mensagem": "A SOB consultada corresponde ao projeto OXCAD ativo no DWG.",
        }

    return {
        "status_contexto": "DIVERGENTE",
        "congruente": False,
        "contexto_ativo_sob": ctx_norm,
        "sob_consultada": sob_norm,
        "vinculado_projeto_ativo": False,
        "mensagem": (
            f"A SOB consultada ({sob_norm}) diverge do projeto ativo ({ctx_norm}). "
            "Os artefatos pertencem à SOB consultada e não serão vinculados ao DWG ativo."
        ),
    }


def _serializar_anexos(anexos: List[GomnetAnexo]) -> List[Dict[str, str]]:
    resultado = []
    for anexo in anexos:
        item = anexo.to_dict()
        item["extensao"] = Path(anexo.nome_arquivo).suffix.lower()
        resultado.append(item)
    return resultado


def consultar_sob(
    sob_input: str,
    client: Optional[Any] = None,
    contexto_ativo_sob: Optional[str] = None,
) -> Dict[str, Any]:
    """Consulta anexos e devolve dados serializáveis, sem inferir o status cadastral."""
    sob_id = obter_sob_id((sob_input or "").strip())
    if not validar_sob(sob_id):
        return {
            "success": False,
            "sob": sob_id,
            "error_code": "SOB_INVALIDA",
            "error": "Informe um número de SOB válido.",
        }

    contexto_info = avaliar_contexto_oxcad(sob_id, contexto_ativo_sob)
    gomnet = client or GomnetClient()
    try:
        anexos = gomnet.localizar_sob_e_listar_anexos(sob_id)
        obter_status = getattr(gomnet, "obter_status_sob", None)
        status = None
        status_mensagem = MENSAGEM_STATUS_INDISPONIVEL
        if callable(obter_status):
            try:
                status = obter_status(sob_id)
                status_mensagem = (
                    ""
                    if status
                    else "Status cadastral em branco no GOMNET."
                    if status == ""
                    else MENSAGEM_STATUS_INDISPONIVEL
                )
            except Exception as exc:
                status_mensagem = f"Falha ao consultar status no GOMNET: {exc}"
        return {
            "success": True,
            "sob": sob_id,
            "status": status or None,
            "status_mensagem": status_mensagem,
            "anexos": _serializar_anexos(anexos),
            "contexto": contexto_info,
            "status_contexto": contexto_info["status_contexto"],
            "congruente": contexto_info["congruente"],
            "vinculado_projeto_ativo": contexto_info["vinculado_projeto_ativo"],
            "divergencia": contexto_info["status_contexto"] == "DIVERGENTE",
            "message": (
                "Anexos localizados no GOMNET."
                if anexos
                else "Nenhum projeto ou anexo vinculado a esta SOB."
            ),
        }
    finally:
        if client is None:
            gomnet.fechar()


def baixar_sob(
    sob_input: str,
    destino_base: Optional[Union[str, Path]] = None,
    client: Optional[Any] = None,
    diretorio_download: Optional[Union[str, Path]] = None,
    contexto_ativo_sob: Optional[str] = None,
    confirmar_divergencia: bool = False,
) -> Dict[str, Any]:
    """Baixa em um diretório exato ou em <destino_base>/PROJETO CONSULTADO."""
    sob_id = obter_sob_id((sob_input or "").strip())
    if not validar_sob(sob_id):
        return {
            "success": False,
            "sob": sob_id,
            "error_code": "SOB_INVALIDA",
            "error": "Informe um número de SOB válido.",
        }

    contexto_info = avaliar_contexto_oxcad(sob_id, contexto_ativo_sob)
    if contexto_info["status_contexto"] == "DIVERGENTE" and not confirmar_divergencia:
        return {
            "success": False,
            "sob": sob_id,
            "error_code": "CONFIRMACAO_DIVERGENCIA_NECESSARIA",
            "error": (
                f"A SOB consultada ({sob_id}) é diferente da SOB do projeto ativo "
                f"({contexto_info['contexto_ativo_sob']}). Confirmação explícita é necessária para download divergente."
            ),
            "contexto": contexto_info,
            "divergencia": True,
            "anexos": [],
        }

    gomnet = client or GomnetClient()
    try:
        anexos = gomnet.localizar_sob_e_listar_anexos(sob_id)
        if not anexos:
            return {
                "success": False,
                "sob": sob_id,
                "error_code": "SEM_ANEXOS",
                "error": "Nenhum projeto ou anexo vinculado a esta SOB.",
                "contexto": contexto_info,
                "anexos": [],
            }

        if diretorio_download:
            diretorio = Path(diretorio_download).expanduser().resolve()
        elif destino_base:
            diretorio = Path(destino_base).expanduser().resolve() / "PROJETO CONSULTADO"
        else:
            return {
                "success": False,
                "sob": sob_id,
                "error_code": "DESTINO_OBRIGATORIO",
                "error": "Selecione um diretório de destino antes de baixar os arquivos.",
                "contexto": contexto_info,
            }

        destinos = []
        for anexo in anexos:
            nome_seguro = Path(anexo.nome_arquivo).name
            if nome_seguro and nome_seguro not in {".", ".."}:
                destinos.append((anexo, diretorio / nome_seguro))
        existentes = [str(caminho) for _, caminho in destinos if caminho.exists()]
        if existentes:
            return {
                "success": False,
                "sob": sob_id,
                "error_code": "ARQUIVO_EXISTENTE",
                "error": "Download cancelado para não sobrescrever arquivos existentes: " + "; ".join(existentes),
                "arquivos_existentes": existentes,
                "contexto": contexto_info,
            }

        diretorio.mkdir(parents=True, exist_ok=True)
        arquivos = []
        for anexo, destino in destinos:
            caminho = gomnet.baixar_anexo_atomico(anexo, destino)
            arquivos.append(str(caminho))

        msg = (
            f"Download concluído: {len(arquivos)} arquivo(s)."
            if contexto_info["congruente"]
            else f"Download concluído: {len(arquivos)} arquivo(s) salvos para a SOB consultada ({sob_id}), sem vínculo ao projeto ativo."
        )

        return {
            "success": True,
            "sob": sob_id,
            "status": None,
            "status_mensagem": MENSAGEM_STATUS_INDISPONIVEL,
            "diretorio": str(diretorio),
            "arquivos": arquivos,
            "contexto": contexto_info,
            "divergencia": contexto_info["status_contexto"] == "DIVERGENTE",
            "vinculado_projeto_ativo": contexto_info["vinculado_projeto_ativo"],
            "pertence_a_sob_consultada": True,
            "message": msg,
        }
    finally:
        if client is None:
            gomnet.fechar()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Consulta ou baixa anexos de uma SOB no GOMNET.")
    parser.add_argument("--sob", required=True, help="Número da SOB")
    parser.add_argument("--acao", choices=("consultar", "baixar"), default="consultar")
    parser.add_argument("--destino", default="", help="Diretório-base para salvar em PROJETO CONSULTADO")
    parser.add_argument("--diretorio-download", default="", help="Diretório exato para salvar os anexos")
    parser.add_argument("--contexto-sob", default="", help="SOB do projeto OXCAD ativo no AutoCAD")
    parser.add_argument(
        "--confirmar-divergencia",
        action="store_true",
        help="Confirmação explícita para baixar SOB divergente do projeto ativo",
    )
    args = parser.parse_args(argv)

    try:
        if args.acao == "baixar":
            if not args.destino and not args.diretorio_download:
                resultado = {
                    "success": False,
                    "error_code": "DESTINO_OBRIGATORIO",
                    "error": "Selecione um diretório de destino antes de baixar os arquivos.",
                }
            else:
                resultado = baixar_sob(
                    args.sob,
                    args.destino or None,
                    diretorio_download=args.diretorio_download or None,
                    contexto_ativo_sob=args.contexto_sob or None,
                    confirmar_divergencia=args.confirmar_divergencia,
                )
        else:
            resultado = consultar_sob(
                args.sob,
                contexto_ativo_sob=args.contexto_sob or None,
            )
    except Exception as exc:
        resultado = {
            "success": False,
            "error_code": type(exc).__name__,
            "error": str(exc),
        }

    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

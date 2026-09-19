# -*- coding: utf-8 -*-
"""
sob_cli.py - Interface de Linha de Comando (CLI) para automação da SOB.
Responsabilidade única: Parseamento de argumentos, inicialização da GUI de progresso
ou modo headless, e emissão de arquivo JSON de intercâmbio para o AutoCAD.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Optional


def main(args_list: Optional[list] = None):
    try:
        from sob.sob_manager import SobOrchestrator
    except ImportError:
        from sob_manager import SobOrchestrator

    parser = argparse.ArgumentParser(
        description="Preparador Automático de Projeto SOB para AutoCAD."
    )
    parser.add_argument("--sob", required=True, help="Número da SOB (ex: A057349839)")
    parser.add_argument("--destino", required=True, help="Diretório de destino da pasta da SOB")
    parser.add_argument("--base", default="PE", help="Sigla da base técnica (ex: PE, CF, AN, RE). Padrão: PE")
    parser.add_argument("--sem-sharepoint", action="store_true", help="Ignora a etapa do SharePoint")
    parser.add_argument("--abrir-cad", action="store_true", help="Abre o arquivo gerado no AutoCAD")
    parser.add_argument("--json-out", help="Caminho do arquivo JSON de intercâmbio para resposta")
    parser.add_argument(
        "--no-ui",
        "--headless",
        dest="no_ui",
        action="store_true",
        help="Executa sem interface gráfica",
    )

    args = parser.parse_args(args_list)
    orchestrator = SobOrchestrator()
    resultado = None

    # Tenta usar interface gráfica caso não esteja desabilitada e não esteja sob pytest
    if not args.no_ui and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            try:
                from sob.sob_progress_gui import SobProgressGUI
            except ImportError:
                from sob_progress_gui import SobProgressGUI

            def _tarefa(observer):
                base_usada = getattr(observer, "base_selecionada", None) or args.base
                return orchestrator.executar(
                    sob_raw=args.sob,
                    destino_dir=args.destino,
                    base=base_usada,
                    baixar_croqui_sp=not args.sem_sharepoint,
                    abrir_cad=args.abrir_cad,
                    callback_progresso=observer,
                    verificador_cancelamento=observer,
                )

            gui = SobProgressGUI(sob_id=args.sob, tarefa_executora=_tarefa, base_inicial=args.base)
            resultado = gui.iniciar()
        except Exception as e_gui:
            orchestrator.logger.warning(f"Interface gráfica não pôde ser inicializada ({e_gui}). Executando em modo console.")
            resultado = None

    if resultado is None:
        resultado = orchestrator.executar(
            sob_raw=args.sob,
            destino_dir=args.destino,
            base=args.base,
            baixar_croqui_sp=not args.sem_sharepoint,
            abrir_cad=args.abrir_cad,
        )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

    sys.exit(0 if resultado.get("sucesso", False) else 1)


if __name__ == "__main__":
    main()

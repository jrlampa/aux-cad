"""
cpfc_manager.py - Ponto de Entrada e Orquestrador (CLI/GUI)
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (IM3 Brasil / Concessionária)

Permite inicialização direta pelo usuário (2 cliques) ou chamada pelo AutoCAD via AutoLISP.
Suporta leitura de parâmetros de intercâmbio em JSON.
"""

import os
import sys
import json
from typing import Optional, Dict, Any

from cpfc.cpfc_gui import CPFCManagerGUI


def carregar_dados_intercambio(caminho_json: str) -> Dict[str, Any]:
    """Carrega dados cadastrais ou parâmetros exportados pelo AutoCAD em JSON."""
    if not os.path.exists(caminho_json):
        return {}
    try:
        with open(caminho_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        print(f"[AVISO CPFC] Não foi possível ler JSON de intercâmbio: {err}")
        return {}


def main():
    """Ponto de entrada principal."""
    projeto_inicial = "A057032667"
    pasta_padrao = os.getcwd()
    dados_iniciais = {}

    # Trata argumentos da linha de comando
    # Exemplo: python cpfc_manager.py [pasta_ou_json] [projeto]
    if len(sys.argv) > 1:
        arg1 = sys.argv[1].strip().strip('"')
        if arg1.endswith(".json") and os.path.exists(arg1):
            dados_iniciais = carregar_dados_intercambio(arg1)
            if "projeto" in dados_iniciais:
                projeto_inicial = dados_iniciais["projeto"]
            if "pasta_destino" in dados_iniciais:
                pasta_padrao = dados_iniciais["pasta_destino"]
        elif os.path.isdir(arg1):
            pasta_padrao = arg1

    if len(sys.argv) > 2:
        projeto_arg = sys.argv[2].strip().strip('"')
        if projeto_arg:
            projeto_inicial = projeto_arg

    app = CPFCManagerGUI(
        projeto_inicial=projeto_inicial,
        pasta_padrao=pasta_padrao,
        dados_iniciais=dados_iniciais,
    )
    app.mainloop()


if __name__ == "__main__":
    main()

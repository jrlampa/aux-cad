"""
cpfc_manager.py - Ponto de Entrada e Orquestrador (CLI/GUI)
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (IM3 Brasil / Concessionária)

Permite inicialização direta pelo usuário (2 cliques) ou chamada pelo AutoCAD via AutoLISP.
Suporta leitura de parâmetros de intercâmbio em JSON.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

_curr_dir = Path(__file__).resolve().parent
_root_dir = _curr_dir.parent
for _d in [str(_curr_dir), str(_root_dir)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

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


def limpar_arquivo_temporario_contexto(caminho_arquivo: Optional[str]) -> bool:
    """
    Remove de forma segura e exclusiva o arquivo temporário de contexto (cpfc_contexto_*.json)
    pertencente à execução atual do CPFC.

    Regras de Segurança:
    - Valida se o caminho é não nulo e string válida.
    - Valida estritamente se o nome do arquivo corresponde ao padrão de contexto temporário:
      prefixo 'cpfc_contexto_' e extensão '.json'. Nunca apaga arquivos arbitrários do usuário.
    - Remove apenas o arquivo específico referenciado, sem executar glob ou tocar em outros arquivos.
    - Trata silenciosamente ausência prévia do arquivo (idempotente).
    - Captura falhas de I/O (PermissionError, OSError) emitindo aviso sem mascarar exceções do app.

    Retorna True se o arquivo foi removido com sucesso, False caso contrário ou se não aplicável.
    """
    if not caminho_arquivo or not isinstance(caminho_arquivo, str):
        return False

    caminho = Path(caminho_arquivo).resolve()
    nome_arquivo = caminho.name

    # Validação estrita do padrão de segurança de arquivo temporário desta execução
    if not (nome_arquivo.startswith("cpfc_contexto_") and nome_arquivo.endswith(".json")):
        return False

    if not caminho.is_file():
        return False

    try:
        caminho.unlink()
        return True
    except (OSError, PermissionError) as err:
        print(f"[AVISO CPFC] Não foi possível remover arquivo temporário de contexto {caminho}: {err}")
        return False


def main():
    """Ponto de entrada principal."""
    projeto_inicial = "A057032667"
    pasta_padrao = os.getcwd()
    dados_iniciais = {}
    arquivo_contexto_proprio: Optional[str] = None

    try:
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

                # Registra exclusivamente o arquivo temporário desta execução
                nome_base = os.path.basename(arg1)
                if nome_base.startswith("cpfc_contexto_") and nome_base.endswith(".json"):
                    arquivo_contexto_proprio = str(Path(arg1).resolve())
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
    finally:
        if arquivo_contexto_proprio:
            limpar_arquivo_temporario_contexto(arquivo_contexto_proprio)


if __name__ == "__main__":
    main()

"""
Orquestrador e Ponto de Entrada do Módulo de Orçamento e Levantamento de Materiais.
Aceita dados intermediários JSON gerados pelo AutoCAD (comando ORCAD) ou inicia modo interativo.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_curr_dir, ".."))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from orcamento_core import processar_dados_orcamento
from orcamento_excel import exportar_planilha_orcamento
from orcamento_gui import OrcamentoGUI


def carregar_dados_json(caminho_json: str) -> Dict[str, Any]:
    """Lê arquivo JSON intermediário gerado pela rotina AutoLISP ORCAD."""
    if not os.path.exists(caminho_json):
        print(f"[AVISO] Arquivo JSON não encontrado: {caminho_json}. Iniciando com dados vazios.")
        return {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}
    try:
        with open(caminho_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao decodificar JSON: {e}")
        return {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}


def main():
    parser = argparse.ArgumentParser(description="Orçamento e Levantamento Automático de Materiais - AUX CAD")
    parser.add_argument("--json", type=str, help="Caminho do arquivo orcamento_dados.json exportado pelo AutoCAD")
    parser.add_argument("--saida", type=str, help="Caminho de saída para geração direta da planilha .xlsx")
    parser.add_argument("--no-gui", action="store_true", help="Gera o orçamento diretamente sem abrir a interface gráfica")
    parser.add_argument("--projeto", type=str, default="PROJETO PADRÃO", help="Identificação da obra / ordem de serviço")
    parser.add_argument("--municipio", type=str, default="RIO DE JANEIRO - RJ", help="Município da obra")
    parser.add_argument("--projetista", type=str, default="ENG. PROJETISTA", help="Nome do engenheiro/projetista")

    args = parser.parse_args()

    dados_cad = {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}
    if args.json:
        dados_cad = carregar_dados_json(args.json)

    # Modo Silencioso / CLI direta
    if args.no_gui and args.saida:
        processados = processar_dados_orcamento(dados_cad)
        planilha_gerada = exportar_planilha_orcamento(
            dados_processados=processados,
            caminho_saida=args.saida,
            num_projeto=args.projeto,
            municipio=args.municipio,
            projetista=args.projetista
        )
        print(f"[SUCESSO] Planilha de orçamento gerada em: {planilha_gerada}")
        print(f"Total de Postes: {processados['qtd_postes']}")
        print(f"Extensão de Cabos: {processados['extensao_total_m']:.2f} m")
        print(f"Valor Total Estimado: R$ {processados['total_geral']:,.2f}")
        return

    # Modo Interface Gráfica
    app = OrcamentoGUI(dados_cad_iniciais=dados_cad, caminho_arquivo_cad=args.json)
    if args.projeto and args.projeto != "PROJETO PADRÃO":
        app.num_projeto_var.set(args.projeto)
    if args.municipio and args.municipio != "RIO DE JANEIRO - RJ":
        app.municipio_var.set(args.municipio)
    if args.projetista and args.projetista != "ENG. PROJETISTA":
        app.projetista_var.set(args.projetista)

    app.mainloop()


if __name__ == "__main__":
    main()

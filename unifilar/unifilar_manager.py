# -*- coding: utf-8 -*-
"""
Módulo Orquestrador e CLI do Diagrama Unifilar.
Responsabilidade única: Interface CLI e ponte de intercâmbio JSON com o AutoCAD.
"""

import argparse
import json
from pathlib import Path
import sys

from arvore_client import ArvoreClient
from arvore_database import ArvoreDatabase
from unifilar_diagrama_builder import (
    determinar_bloco_protecao,
    construir_esquema_unifilar,
    gerar_dicionario_esquema,
)
from dispositivos_kmz_finder import buscar_dispositivo_kmz


def processar_ponto(
    ponto: str,
    resumo_manual: str = "",
    arquivo_saida: str = "",
    client: ArvoreClient = None,
    fuso_utm: int = 23,
    escala_h: float = 2.5,
) -> dict:
    """Processa a busca do ponto, localiza dispositivo em KMZ e gera o esquema gráfico."""
    if client is None:
        client = ArvoreClient()

    ponto_limpo = ponto.strip().upper()
    if resumo_manual:
        resultado = client.consultar_resumo_manual(resumo_manual, ponto_limpo)
    else:
        resultado = client.consultar(ponto_limpo)

    linhas = resultado.gerar_linhas_diagrama() if resultado.sucesso else []

    # Determina o bloco CAD oficial ('chaves_' ou 'REL')
    bloco_protecao = "chaves_"
    geo_disp = None
    esquema_dict = None

    if resultado.sucesso:
        bloco_protecao = determinar_bloco_protecao(resultado.protecao_tipo, resultado.protecao_rotulo)

        # Busca coordenadas geográficas nos KMZs de apoio
        cod_busca = resultado.protecao_codigo or resultado.protecao_rotulo
        geo_disp = buscar_dispositivo_kmz(cod_busca, fuso_utm=fuso_utm)

        # Constrói o diagrama unifilar esquemático sem escala
        esquema = construir_esquema_unifilar(
            subestacao=resultado.subestacao,
            alimentador=resultado.alimentador,
            protecao_rotulo=resultado.protecao_rotulo,
            protecao_tipo=resultado.protecao_tipo,
            ponto_alvo=resultado.ponto_alvo or ponto_limpo or "P01",
            clientes_a=resultado.clientes_a,
            clientes_b=resultado.clientes_b,
            kva=resultado.kva,
            escala_h=escala_h,
        )
        esquema_dict = gerar_dicionario_esquema(esquema)

    dados_retorno = {
        "sucesso": resultado.sucesso,
        "ponto_alvo": resultado.ponto_alvo,
        "subestacao": resultado.subestacao,
        "alimentador": resultado.alimentador,
        "protecao_tipo": resultado.protecao_tipo,
        "protecao_codigo": resultado.protecao_codigo,
        "protecao_rotulo": resultado.protecao_rotulo,
        "bloco_protecao": bloco_protecao,
        "clientes_a": resultado.clientes_a,
        "clientes_b": resultado.clientes_b,
        "kva": resultado.kva,
        "linhas_diagrama": linhas,
        "geo_dispositivo": geo_disp,
        "esquema_grafico": esquema_dict,
        "mensagem": resultado.mensagem,
    }

    if arquivo_saida:
        p_out = Path(arquivo_saida)
        p_out.parent.mkdir(parents=True, exist_ok=True)
        with open(p_out, "w", encoding="utf-8") as f:
            json.dump(dados_retorno, f, indent=2, ensure_ascii=False)

    return dados_retorno


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta a árvore de dispositivos e localiza a proteção a montante."
    )
    parser.add_argument(
        "--ponto",
        type=str,
        default="",
        help="Código do Ponto Elétrico alvo (ex: SG40995)",
    )
    parser.add_argument(
        "--resumo",
        type=str,
        default="",
        help="Texto do resumo a montante (breadcrumb) colado manualmente",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Caminho do arquivo JSON para gravar o resultado",
    )
    parser.add_argument(
        "--sincronizar",
        action="store_true",
        help="Força reindexação do banco SQLite a partir da planilha oficial",
    )

    parser.add_argument(
        "--fuso",
        type=int,
        default=23,
        help="Fuso UTM para conversão de coordenadas (padrão 23)",
    )
    parser.add_argument(
        "--escala",
        type=float,
        default=2.5,
        help="Escala/altura do texto do esquema unifilar (padrão 2.5)",
    )

    args = parser.parse_args()

    if args.sincronizar:
        db = ArvoreDatabase()
        total = db.sincronizar_de_planilha()
        print(f"[SUCESSO] Base SQLite sincronizada com {total} registros.")
        sys.exit(0)

    if not args.ponto and not args.resumo:
        parser.print_help()
        sys.exit(1)

    ret = processar_ponto(
        ponto=args.ponto,
        resumo_manual=args.resumo,
        arquivo_saida=args.out,
        fuso_utm=args.fuso,
        escala_h=args.escala,
    )

    print(json.dumps(ret, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

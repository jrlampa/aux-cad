"""
cpfc_excel.py - Camada de Persistência e I/O de Planilhas CPFC (openpyxl)
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (IM3 Brasil / Concessionária)

Responsabilidade Única:
  - Localizar a planilha modelo oficial de CPFC (REN 1.059)
  - Preencher cirurgicamente as células de entrada de dados
  - Preservar rigorosamente todas as fórmulas nativas, estilos, formatações e imagens
  - Salvar no destino indicado pelo usuário
"""

import os
from pathlib import Path
from typing import Optional
import openpyxl

from cpfc.cpfc_core import DadosCadastrais, OrcamentoObra, ParametrosDemanda


def localizar_modelo_cpfc() -> str:
    """Localiza o arquivo modelo oficial da planilha CPFC."""
    candidatos = [
        # Pasta de modelos padronizada
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "modelos", "cpfc_modelo.xlsx"),
        os.path.join(os.path.dirname(__file__), "modelos", "cpfc_modelo.xlsx"),
        # Arquivo de referência na raiz
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "PE_A057032667_CPFC_REN1.059_ate_2027_V3_REV.xlsx",
        ),
        # Caminho relativo direto
        "modelos/cpfc_modelo.xlsx",
        "PE_A057032667_CPFC_REN1.059_ate_2027_V3_REV.xlsx",
    ]

    for cand in candidatos:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    raise FileNotFoundError(
        "Planilha modelo CPFC não encontrada! Verifique 'modelos/cpfc_modelo.xlsx' "
        "ou 'PE_A057032667_CPFC_REN1.059_ate_2027_V3_REV.xlsx'."
    )


def preencher_e_salvar_cpfc(
    cadastrais: DadosCadastrais,
    orcamento: OrcamentoObra,
    demanda: ParametrosDemanda,
    caminho_destino: str,
    modelo_path: Optional[str] = None,
) -> str:
    """
    Preenche os dados do formulário na planilha oficial mantendo fórmulas e formatação intactas.

    Mapeamento de Células no modelo:
      - C11: Projeto Nº
      - C13: Tipo de Ligação
      - C15: Subgrupo
      - C17: Endereço
      - C19: Município
      - C24: Origem do Orçamento (GOM, OPD, Engenharia)
      - F30: Serviço de Terceiros (R$)
      - F31: Material (R$)
      - C30: Trafos (opcional)
      - C31: Mão de Obra (opcional)
      - C41: Demanda de Carga (kW)
      - C43: Demanda de Geração (kW - apenas se > 0)
      - G66: Demanda do cliente - Carga (kW para cálculo do ERD)
      - G80: Demanda disponibilizada no orçamento (kW)
    """
    path_modelo = modelo_path or localizar_modelo_cpfc()
    if not os.path.exists(path_modelo):
        raise FileNotFoundError(f"Arquivo modelo não localizado: {path_modelo}")

    cad = cadastrais.sanitizar()
    orc = orcamento.sanitizar()
    dem = demanda.sanitizar()

    # Carrega mantendo todas as fórmulas e elementos
    wb = openpyxl.load_workbook(path_modelo, data_only=False)

    # Seleciona a aba principal do modelo
    sheet_name = "BASE PFC MODELO" if "BASE PFC MODELO" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]

    # 1. Dados Cadastrais
    ws["C11"] = cad.projeto
    ws["C13"] = cad.tipo_ligacao
    ws["C15"] = cad.subgrupo
    ws["C17"] = cad.endereco
    ws["C19"] = cad.municipio

    # 2. Orçamento
    ws["C24"] = orc.origem
    ws["F30"] = float(orc.servico_terceiros)
    ws["F31"] = float(orc.material)
    if orc.trafos > 0:
        ws["C30"] = float(orc.trafos)
    if orc.mao_de_obra > 0:
        ws["C31"] = float(orc.mao_de_obra)

    # 3. Demandas (REN 1.059)
    ws["C41"] = float(dem.demanda_carga)
    if dem.demanda_geracao > 0:
        ws["C43"] = float(dem.demanda_geracao)
    else:
        ws["C43"] = None

    # Demanda do cliente - Carga para cálculo do ERD (G66)
    ws["G66"] = float(dem.get_demanda_erd())

    # Demanda disponibilizada no orçamento (G80)
    ws["G80"] = float(dem.demanda_disponibilizada)

    # 4. Criação do diretório de destino se necessário
    destino_path = Path(caminho_destino).resolve()
    destino_path.parent.mkdir(parents=True, exist_ok=True)

    # 5. Salva com segurança
    wb.save(str(destino_path))
    return str(destino_path)

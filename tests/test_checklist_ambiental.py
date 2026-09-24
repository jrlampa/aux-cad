import os
import pytest
import openpyxl
from checklist_ambiental_manager import (
    extrair_municipio,
    analisar_incidencias_kmz,
    preencher_checklist_ambiental,
    TEMPLATE_DEFAULT,
    TEMPLATE_FALLBACK
)

def test_extrair_municipio():
    assert extrair_municipio("Ilha Grande, Angra dos Reis - RJ") == "ANGRA DOS REIS"
    assert extrair_municipio("Rua das Flores, São Gonçalo - RJ") == "SÃO GONÇALO"
    assert extrair_municipio("Estrada do Catete, Magé") == "MAGÉ"
    assert extrair_municipio("Niterói") == "NITERÓI"

def test_analisar_incidencias_kmz(tmp_path):
    # Caso 1: Vazio
    empty_file = str(tmp_path / "empty_boxes.txt")
    with open(empty_file, "w", encoding="utf-8") as f:
        pass
    res1 = analisar_incidencias_kmz(empty_file)
    assert res1["em_app"] is False
    assert res1["em_uc"] is False
    assert res1["em_exclusao"] is False

    # Caso 2: Zona de Amortecimento do Parque da Ilha Grande
    uc_file = str(tmp_path / "uc_boxes.txt")
    with open(uc_file, "w", encoding="utf-8") as f:
        f.write("ZONA DE AMORTECIMENTO DE UNIDADE DE CONSERVAÇÃO|PARQUE ESTADUAL DA ILHA GRANDE\n")
    res2 = analisar_incidencias_kmz(uc_file)
    assert res2["em_app"] is False
    assert res2["em_uc"] is True
    assert any("PARQUE ESTADUAL DA ILHA GRANDE" in s for s in res2["ucs"])

    # Caso 3: APP de Manguezal
    app_file = str(tmp_path / "app_boxes.txt")
    with open(app_file, "w", encoding="utf-8") as f:
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|MANGUEZAL\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|RESTINGA\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|NASCENTE\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|ENCOSTA COM DECLIVIDADE\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|TOPO DE MORRO\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|VEREDA\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|LAGO\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|RESERVATORIO\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|TABULEIRO\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|CURSO DAGUA\n")
        f.write("ÁREA DE EXCLUSÃO|ZONA INTANGÍVEL\n")
    res3 = analisar_incidencias_kmz(app_file)
    assert res3["em_app"] is True
    assert 36 in res3["app_rows"]  # Manguezal
    assert 35 in res3["app_rows"]  # Restinga
    assert 33 in res3["app_rows"]  # Nascente
    assert 34 in res3["app_rows"]  # Encosta
    assert 38 in res3["app_rows"]  # Topo de morro
    assert 40 in res3["app_rows"]  # Vereda
    assert 29 in res3["app_rows"]  # Lago
    assert 32 in res3["app_rows"]  # Reservatório
    assert 37 in res3["app_rows"]  # Tabuleiro
    assert 24 in res3["app_rows"]  # Rio < 10m
    assert res3["em_exclusao"] is True
    assert any("INTANGÍVEL" in s or "ZONA" in s for s in res3["exclusoes"])

def test_preencher_checklist_ambiental(tmp_path):
    template = TEMPLATE_DEFAULT if os.path.exists(TEMPLATE_DEFAULT) else TEMPLATE_FALLBACK
    if not os.path.exists(template):
        pytest.skip("Template do checklist não encontrado.")

    boxes_file = str(tmp_path / "boxes.txt")
    with open(boxes_file, "w", encoding="utf-8") as f:
        f.write("ZONA DE AMORTECIMENTO DE UNIDADE DE CONSERVAÇÃO|PARQUE ESTADUAL DA ILHA GRANDE\n")
        f.write("ÁREA DE PRESERVAÇÃO PERMANENTE|MANGUEZAL\n")
        f.write("ÁREA DE EXCLUSÃO|PARQUE NACIONAL\n")

    out_file = str(tmp_path / "CHECKLIST_A057146257.xlsx")
    dados = {
        "NUMERO_PROJETO": "A057146257",
        "LOCAL_OBRA": "Ilha Grande, Angra dos Reis - RJ",
        "PROJETISTA_RESPONSAVEL": "FABIO VARGAS",
        "EMPRESA": "HBT",
        "QTD_PODAS": "2",
        "QTD_SUPRESSOES": "0"
    }

    result_path = preencher_checklist_ambiental(template, out_file, dados, boxes_txt_path=boxes_file)
    assert os.path.exists(result_path)

    wb = openpyxl.load_workbook(result_path)
    ws = wb["Planilha1"]

    assert ws["B6"].value == "A057146257"
    assert ws["B7"].value == "ANGRA DOS REIS"
    assert ws["B8"].value == "PROJETO"
    assert ws["B9"].value == "FABIO VARGAS"
    assert ws["B10"].value == "HBT"
    assert ws["B12"].value == "SIM"
    assert ws.cell(36, 4).value == "✓"  # Linha 36 Manguezal marcado
    assert ws["B14"].value == "SIM"
    assert "PARQUE ESTADUAL DA ILHA GRANDE" in ws["B15"].value
    assert ws["B17"].value == "SIM"
    assert "PARQUE NACIONAL" in ws["B18"].value
    assert ws["A44"].value is not None
    assert "Podas previstas: 2" in ws["A44"].value

def test_regra_negocio_omissao_memorial(tmp_path):
    """Valida a regra correta: sem restrição ambiental o Memorial é dispensado; com restrição ambiental o Memorial é gerado."""
    template = TEMPLATE_DEFAULT if os.path.exists(TEMPLATE_DEFAULT) else TEMPLATE_FALLBACK
    if not os.path.exists(template):
        pytest.skip("Template do checklist não encontrado.")

    # Caso A: Projeto SEM restrição ambiental -> Memorial NÃO deve ser gerado, apenas o Checklist
    boxes_limpo = str(tmp_path / "boxes_sem_restricao.txt")
    with open(boxes_limpo, "w", encoding="utf-8") as f:
        pass  # Vazio, sem incidências

    analise_limpo = analisar_incidencias_kmz(boxes_limpo)
    tem_restricao_limpo = analise_limpo["em_app"] or analise_limpo["em_uc"] or analise_limpo["em_exclusao"]
    assert tem_restricao_limpo is False

    chk_limpo = str(tmp_path / "CHECKLIST_LIMPO.xlsx")
    dados = {
        "NUMERO_PROJETO": "A057146257",
        "LOCAL_OBRA": "Ilha Grande, Angra dos Reis - RJ",
        "PROJETISTA_RESPONSAVEL": "FABIO VARGAS",
        "EMPRESA": "HBT"
    }
    res_chk = preencher_checklist_ambiental(template, chk_limpo, dados, boxes_txt_path=boxes_limpo)
    assert os.path.exists(res_chk)

    wb_limpo = openpyxl.load_workbook(res_chk)
    assert wb_limpo["Planilha1"]["B12"].value == "NÃO"
    assert wb_limpo["Planilha1"]["B14"].value == "NÃO"
    assert wb_limpo["Planilha1"]["B17"].value == "NÃO"

    # Caso B: Projeto COM restrição ambiental -> Memorial DEVE ser gerado juntamente com o Checklist
    boxes_restricao = str(tmp_path / "boxes_restricao.txt")
    with open(boxes_restricao, "w", encoding="utf-8") as f:
        f.write("ZONA DE AMORTECIMENTO DE UNIDADE DE CONSERVAÇÃO|PARQUE ESTADUAL DA ILHA GRANDE\n")

    analise_restricao = analisar_incidencias_kmz(boxes_restricao)
    tem_restricao = analise_restricao["em_app"] or analise_restricao["em_uc"] or analise_restricao["em_exclusao"]
    assert tem_restricao is True


def test_is_safe_writable_dir(tmp_path):
    from memorial_ambiental_generator import is_safe_writable_dir

    # Diretório temporário válido e gravável
    assert is_safe_writable_dir(str(tmp_path)) is True

    # Entradas inválidas
    assert is_safe_writable_dir(None) is False
    assert is_safe_writable_dir("") is False
    assert is_safe_writable_dir("   ") is False
    assert is_safe_writable_dir("C:\\CaminhoInexistente_12345XYZ") is False

    # Diretórios protegidos do sistema operacional
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    assert is_safe_writable_dir(win_dir) is False
    assert is_safe_writable_dir(os.path.join(win_dir, "System32")) is False


def test_determinar_pasta_saida(tmp_path):
    from memorial_ambiental_generator import determinar_pasta_saida

    # 1. Candidato válido é respeitado
    candidato = str(tmp_path)
    res = determinar_pasta_saida(candidate=candidato)
    assert res == os.path.abspath(candidato)

    # 2. Candidato perigoso (System32) é rejeitado e substituído por pasta segura
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    sys32 = os.path.join(win_dir, "System32")
    res_perigoso = determinar_pasta_saida(candidate=sys32)
    assert not res_perigoso.lower().startswith(win_dir.lower())
    assert os.path.exists(res_perigoso)

    # 3. Template vazio ou inexistente não causa retorno de System32
    res_sem_template = determinar_pasta_saida(candidate="", template_path="")
    assert not res_sem_template.lower().startswith(win_dir.lower())
    assert os.path.exists(res_sem_template)



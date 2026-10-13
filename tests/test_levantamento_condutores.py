from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LISP_PATH = ROOT / "orcamento" / "levantamento_condutores.lsp"


def test_levantamento_condutores_lisp_balance_and_contract():
    source = LISP_PATH.read_text(encoding="utf-8")

    depth = 0
    in_string = False
    in_comment = False
    for index, char in enumerate(source):
        if in_comment:
            if char == "\n":
                in_comment = False
            continue
        if char == ";" and not in_string:
            in_comment = True
            continue
        if char == '"':
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and source[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                in_string = not in_string
            continue
        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                assert depth >= 0

    assert depth == 0
    assert not in_string
    assert "(defun c:LEVANTAR_CONDUTORES" in source
    assert '(= entity-type "DIMENSION")' in source
    assert '(= entity-type "TEXT")' in source
    assert '(= entity-type "MTEXT")' in source
    assert "(vla-AddTable" in source
    assert '"INSTALAR (m)"' in source
    assert '"RETIRAR (m)"' in source
    assert '"REAPROVEITAR (m)"' in source
    assert '(ssget \'((0 . "DIMENSION,TEXT,MTEXT")))' in source
    assert '(setvar "PICKADD" 2)' in source
    assert "Shift+clique remove" in source
    assert "(setvar \"PICKADD\" old-pickadd)" in source
    assert "(entsel" not in source


def test_levantamento_condutores_is_loaded_globally():
    loader = (ROOT / "acaddoc.lsp").read_text(encoding="utf-8")
    assert 'load-aux-safe "orcamento\\\\levantamento_condutores.lsp"' in loader


def test_dimension_override_precedes_geometric_measurement():
    source = LISP_PATH.read_text(encoding="utf-8")
    dimension_branch = source.split('((= entity-type "DIMENSION")', 1)[1].split(
        '((or (= entity-type "TEXT")', 1
    )[0]
    assert "(setq override (cdr (assoc 1 data)))" in dimension_branch
    assert '"<>" override' in dimension_branch
    assert "(lc-parse-meters (lc-strip-mtext override))" in dimension_branch
    assert dimension_branch.index("(setq override (cdr (assoc 1 data)))") < dimension_branch.index("'Measurement")
    assert "TextOverride" not in dimension_branch


def test_conductor_lengths_are_displayed_rounded_up_to_whole_meters():
    source = LISP_PATH.read_text(encoding="utf-8")
    formatter = source.split("(defun lc-format-meters", 1)[1].split(
        "(defun lc-create-table", 1
    )[0]
    assert "(fix amount)" in formatter
    assert "(1+ whole)" in formatter
    assert '(strcat (itoa whole) "m")' in formatter
    assert "rtos" not in formatter


def test_oxcad_button_dispatches_conductor_command_to_active_document():
    xaml = (ROOT / "oxcad" / "OxCadControl.xaml").read_text(encoding="utf-8")
    code = (ROOT / "oxcad" / "OxCadControl.xaml.cs").read_text(encoding="utf-8")
    assert 'x:Name="BtnLevantamentoCondutores"' in xaml
    assert 'Click="BtnLevantarCondutores_Click"' in xaml
    assert 'doc.SendStringToExecute("_.LEVANTAR_CONDUTORES "' in code


def test_preselection_and_manual_debug_feedback():
    source = LISP_PATH.read_text(encoding="utf-8")
    command_body = source.split("(defun c:LEVANTAR_CONDUTORES", 1)[1]
    implied_selection = command_body.index('(ssget "_I"')
    conductor_prompt = command_body.index('"\\nCondutor (Enter para concluir ou \'P\' para pausar): "')
    assert implied_selection < conductor_prompt
    assert "usando pré-seleção para " in command_body
    assert '(if (numberp old-pickadd)' in command_body
    assert "[LEVANTAMENTO][ITEM] tipo=" in command_body
    assert "origem=" in command_body
    assert "[LEVANTAMENTO][IGNORADO]" in command_body


def test_persistencia_por_dwg_via_ldata():
    """Valida o isolamento por DWG usando o dicionário OXCAD_LEVANTAMENTO_CONDUTORES via LData."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert '*lc-dict-name* "OXCAD_LEVANTAMENTO_CONDUTORES"' in source
    assert '*lc-key-name*  "ESTADO"' in source
    assert "(defun lc-db-obter-estado" in source
    assert "(defun lc-db-salvar-estado" in source
    assert "(defun lc-db-limpar-estado" in source
    assert "(vlax-ldata-get *lc-dict-name* *lc-key-name*)" in source
    assert "(vlax-ldata-put *lc-dict-name* *lc-key-name*" in source
    assert "(vlax-ldata-delete *lc-dict-name* *lc-key-name*)" in source


def test_prevencao_de_dupla_contabilizacao_por_handle():
    """Valida que entidades com o mesmo Handle no DWG são detectadas e desduplicadas."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(cdr (assoc 5 (entget entity)))" in source
    assert "(= (car it) handle)" in source
    assert "motivo=entidade já contabilizada nesta operação" in source
    assert "duplicadas=" in source


def test_menu_retomada_opcoes_e_revisao():
    """Valida o menu de opções para coletas em andamento (Continuar, Revisar, Gerar, Descartar)."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert '"Continuar Pausar Revisar Concluir Gerar Descartar"' in source
    assert "(defun lc-exibir-revisao" in source
    assert "Deseja realmente descartar toda a coleta pendente deste DWG?" in source
    assert "[Sim/Nao] <Nao>:" in source


def test_auditoria_entidades_excluidas_ou_modificadas():
    """Valida funções de auditoria de integridade que checam handent e alterações métricas."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(defun lc-verificar-integridade-itens" in source
    assert "(defun lc-reconciliar-itens" in source
    assert '(list "EXCLUIDA" handle item)' in source
    assert '(list "MODIFICADA" handle item' in source
    assert "(handent handle)" in source


def test_seguranca_na_conclusao_e_limpeza_condicional():
    """Valida que a limpeza do LData só ocorre após sucesso confirmado da tabela nativa."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(setq table-ok (lc-create-table rows))" in source
    assert "(if table-ok" in source
    assert "(lc-db-limpar-estado)" in source
    assert "coleta preservada no DWG." in source
    assert "(vl-catch-all-apply" in source
    assert "vla-AddTable" in source


def test_resiliencia_cancelamento_por_esc_e_preservacao():
    """Valida que interrupções por Esc preservam a coleta e informam o usuário."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "Operação interrompida. Dados preservados no DWG ativo." in source
    # Não chama lc-db-limpar-estado no *error*
    error_block = source.split("(defun *error*", 1)[1].split("(if (and items (> (length items) 0))", 1)[0]
    assert "lc-db-limpar-estado" not in error_block


def test_separacao_entre_condutores_e_tres_operacoes():
    """Valida a separação de totais por condutor e pelas três operações."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert '"Instalar Retirar Reaproveitar"' in source
    assert '((= (strcase operation) "REAPROVEITAR") 4)' in source
    assert '((= (strcase operation) "RETIRAR") 3)' in source
    assert "(lc-add-total key conductor column amount rows)" in source


def test_pause_retomada_e_limpeza_somente_apos_sucesso():
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "Coleta pausada" in source
    assert "(lc-db-salvar-estado items rows)" in source
    assert "(lc-db-limpar-estado)" in source
    assert source.index("(lc-db-limpar-estado)") > source.index("(if table-ok")

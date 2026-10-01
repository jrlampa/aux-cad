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
    assert '"INSTALAR"' in source
    assert '"RETIRAR"' in source
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
    conductor_prompt = command_body.index('"\\nCondutor (Enter para concluir): "')
    assert implied_selection < conductor_prompt
    assert "usando pré-seleção para " in command_body
    assert '(if (numberp old-pickadd)' in command_body
    assert "[LEVANTAMENTO][ITEM] tipo=" in command_body
    assert "origem=" in command_body
    assert "[LEVANTAMENTO][IGNORADO]" in command_body
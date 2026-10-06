import json
import logging
import builtins
import socket
import subprocess
import webbrowser
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

import pytest

from workspace.workspace_integrations import (
    AuthenticationScheme, IBusinessSystemProvider, IWorkOrderProvider,
    IntegrationCapability, IntegrationContext, IntegrationRegistry,
    IntegrationStatus,
)
from workspace.workspace_universalizacao_client import (
    BASE_URL, ORDER_PATH, HandshakeStep, UniversalizacaoCode,
    UniversalizacaoDiagnostic, UniversalizacaoResult,
)
from workspace.workspace_universalizacao_provider import (
    UniversalizacaoProvider, parse_order_response,
)


def positive_html(grupo="A", sob="SYNTHETIC_001"):
    return (
        "synthetic-debug-data nome=synthetic-outside-name "
        "notas_obs=synthetic-outside-notes "
        "SELECT synthetic_sql_marker FROM synthetic_table;<br>"
        "<script language='javascript'>"
        "if (parent.mainFrame.document.frm1) {"
        f'parent.mainFrame.document.frm1.numero_ordem_projeto.value = "{sob}";'
        f'parent.mainFrame.document.frm1.grupo.value = "{grupo}";'
        f'parent.mainFrame.document.frm1.select_grupo.value = "{grupo}";'
        "parent.mainFrame.document.frm1.etapa_ordem_proj.value = 'ESTUDO';"
        "parent.mainFrame.document.frm1.estado_ordem_proj.value = 'EXECUCAO';"
        "parent.mainFrame.document.frm1.status_ordem.value = 'NO PRAZO';"
        "parent.mainFrame.document.frm1.nome.value = "
        "'synthetic-private-person';"
        "parent.mainFrame.document.frm1.notas_obs.value = "
        "'synthetic-private-notes';"
        "parent.mainFrame.document.frm1.bt_gravar.disabled = false;"
        "parent.mainFrame.document.frm1.bt_excluir.disabled = false;"
        "}</script>"
    )


def transport_result(code=UniversalizacaoCode.SUCCESS, status=200):
    return UniversalizacaoResult(
        success=code == UniversalizacaoCode.SUCCESS,
        code=code, http_status=status, url=BASE_URL + ORDER_PATH,
        operation="QUERY_ORDER", elapsed_seconds=0.1,
        authenticated=status == 200, message="Sanitized result",
        diagnostic=UniversalizacaoDiagnostic(
            stage="RESPONSE_CONSUMPTION",
            steps=(
                HandshakeStep("GET", 401, ("negotiate", "ntlm"), False),
                HandshakeStep("TYPE1", 401, ("ntlm",), True, 1, 4, 2, 8),
                HandshakeStep("TYPE3", 200, (), True, 3, 12),
            ),
            connection_reused=True, expected_target_seen=True,
        ),
    )


def provider_with_html(html):
    def read_order(sob, grupo, username, password, *, consume):
        consume(html)
        return transport_result()

    client = Mock()
    client.read_order.side_effect = read_order
    provider = UniversalizacaoProvider(client)
    return provider, client


@pytest.mark.parametrize("grupo", ["A", "B"])
def test_positive_identity_and_minimal_status(grupo, caplog):
    html = positive_html(grupo)
    provider, client = provider_with_html(html)
    caplog.set_level(logging.DEBUG)
    result = provider.consultar_os_sob(
        "SYNTHETIC_001", grupo,
        username="synthetic-user", password="synthetic-secret",
    )
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data["outcome"] == "SUCCEEDED"
    assert result.data["returned_sob"] == "SYNTHETIC_001"
    assert result.data["returned_grupo"] == grupo
    assert client.read_order.call_count == 1
    output = json.dumps(asdict(result)) + caplog.text
    assert result.data["project_data"]["nome"] == "synthetic-private-person"
    assert "synthetic-private-person" not in caplog.text
    for value in (html, "synthetic-secret",
                  "synthetic-user", "synthetic-debug-data", "bt_gravar"):
        assert value not in output


@pytest.mark.parametrize("sob,grupo", [
    ("", "A"), (" ", "A"), ("SYNTHETIC_001", None),
    ("SYNTHETIC_001", ""), ("SYNTHETIC_001", "C"),
    ("SYNTHETIC_001", "a"), ("SYNTHETIC_001", "b"),
])
def test_invalid_identity_never_requests_credentials_or_http(sob, grupo):
    client, credentials = Mock(), Mock()
    provider = UniversalizacaoProvider(client, credentials)
    result = provider.consultar_os_sob(sob, grupo)
    assert result.status == IntegrationStatus.INVALID_REQUEST
    client.read_order.assert_not_called()
    credentials.assert_not_called()


@pytest.mark.parametrize("requested,returned", [("A", "B"), ("B", "A")])
def test_group_mismatch(requested, returned):
    provider, _ = provider_with_html(positive_html(returned))
    result = provider.consultar_os_sob(
        "SYNTHETIC_001", requested, username="synthetic-user",
        password="synthetic-secret",
    )
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH


def test_missing_group_argument_is_not_an_overload():
    with pytest.raises(TypeError):
        UniversalizacaoProvider().consultar_os_sob("SYNTHETIC_001")


def test_parser_ignores_non_script_private_text():
    parsed = parse_order_response(positive_html())
    assert parsed.valid
    assert set(parsed.fields) == {
        "numero_ordem_projeto", "grupo", "select_grupo",
        "etapa_ordem_proj", "estado_ordem_proj", "status_ordem", "nome",
        "notas_obs",
    }
    assert "synthetic-outside-name" not in parsed.fields.values()


@pytest.mark.parametrize("code,outcome", [
    (UniversalizacaoCode.TIMEOUT, "TIMEOUT"),
    (UniversalizacaoCode.CONNECTION_ERROR, "UNAVAILABLE"),
    (UniversalizacaoCode.INVALID_CHALLENGE, "INVALID_RESPONSE"),
    (UniversalizacaoCode.INTERNAL_ERROR, "ERROR"),
])
def test_typed_failure_after_initial_401_is_not_auth_rejection(code, outcome):
    client = Mock()
    client.read_order.return_value = transport_result(code, 401)
    result = UniversalizacaoProvider(client).consultar_os_sob(
        "SYNTHETIC_001", "A", username="synthetic-user",
        password="synthetic-secret",
    )
    assert result.error_code == outcome


@pytest.mark.parametrize("grupo", ["A", "B"])
def test_full_provider_client_pure_ntlm_pipeline(monkeypatch, grupo, caplog):
    import base64
    from email.message import Message

    from spnego._ntlm_raw.messages import Challenge, NegotiateFlags
    from workspace import workspace_universalizacao_client as client_module

    monkeypatch.delenv("LM_COMPAT_LEVEL", raising=False)
    challenge = Challenge(
        flags=NegotiateFlags.unicode | NegotiateFlags.ntlm
        | NegotiateFlags.extended_session_security
        | NegotiateFlags.request_target,
        server_challenge=b"12345678", target_name="ENELINT",
    ).pack()

    def response(status, authenticate=None, body=b""):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        if authenticate:
            headers["WWW-Authenticate"] = authenticate
        return Mock(status=status, headers=headers,
                    read=Mock(return_value=body))

    connection = Mock(sock=object())
    connection.getresponse.side_effect = [
        response(401, "Negotiate, NTLM"),
        response(401, "NTLM " + base64.b64encode(challenge).decode()),
        response(200, body=positive_html(grupo).encode()),
    ]
    monkeypatch.setattr(client_module.http.client, "HTTPConnection", Mock(
        return_value=connection
    ))
    caplog.set_level(logging.DEBUG)
    result = UniversalizacaoProvider().consultar_os_sob(
        "SYNTHETIC_001", grupo, username="synthetic-user",
        password="synthetic-secret",
    )
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data["authenticated"]
    assert result.data["returned_grupo"] == grupo
    calls = connection.request.call_args_list
    assert len(calls) == 3
    for call, expected in zip(calls[1:], (1, 3)):
        value = call.kwargs["headers"]["Authorization"].split()[1]
        assert client_module._message_type(base64.b64decode(value)) == expected
        assert value not in caplog.text
    assert "synthetic-secret" not in caplog.text
    assert result.data["project_data"]["nome"] == "synthetic-private-person"
    assert "synthetic-private-person" not in caplog.text
    connection.close.assert_called_once()


@pytest.fixture(autouse=True)
def prohibit_provider_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Provider unit test attempted real network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def _context(sob="SYNTHETIC_001"):
    return IntegrationContext(
        sob_id=sob, project_root="C:/synthetic/project",
        dwg_path="C:/synthetic/project/synthetic.dwg",
        database_fingerprint="synthetic-fingerprint",
        correlation_id="synthetic-correlation",
        execution_id="synthetic-execution",
    )


def _query(provider, **kwargs):
    return provider.consultar_os_sob(
        "SYNTHETIC_001", "A", username="synthetic-user",
        password="synthetic-secret", **kwargs,
    )


def _assert_sanitized(result, caplog, *extra):
    output = json.dumps(asdict(result)) + repr(result) + caplog.text
    for value in (
        "synthetic-user", "synthetic-secret", "synthetic-outside-name",
        "synthetic-outside-notes", "synthetic_sql_marker", *extra,
    ):
        assert value not in output, "Private synthetic marker escaped"
    assert "synthetic-private-person" not in caplog.text
    assert "synthetic-private-notes" not in caplog.text
    if not result.is_success:
        assert "synthetic-private-person" not in output
        assert "synthetic-private-notes" not in output
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("sob,grupo", [
    ("SYNTHETIC_001", " A"), ("SYNTHETIC_001", "B "),
    ("SYNTHETIC_001", " "), ("https://synthetic.invalid/order", "A"),
    ("SYNTHETIC_001\r\n", "A"), ("SYNTHETIC_001\x00", "B"),
    ("SYNTHETIC_001&grupo=B", "A"), ("SYNTHETIC_001?grupo=B", "A"),
])
def test_extended_invalid_identity_is_rejected_before_supplier(
    sob, grupo, caplog,
):
    client, supplier = Mock(), Mock()
    result = UniversalizacaoProvider(client, supplier).consultar_os_sob(
        sob, grupo,
    )
    assert result.status == IntegrationStatus.INVALID_REQUEST
    assert result.data["outcome"] == "INVALID_REQUEST"
    assert result.data["requested_sob"] is None
    client.read_order.assert_not_called()
    supplier.assert_not_called()
    _assert_sanitized(result, caplog)


@pytest.mark.parametrize("field,value", [
    ("numero_ordem_projeto", "SYNTHETIC_002"), ("select_grupo", "B"),
])
def test_returned_sob_and_selected_group_must_match(field, value):
    original = "SYNTHETIC_001" if field == "numero_ordem_projeto" else "A"
    html = positive_html().replace(
        f'{field}.value = "{original}"',
        f'{field}.value = "{value}"',
    )
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH
    assert result.data["outcome"] == "IDENTITY_MISMATCH"


@pytest.mark.parametrize(
    "kind", ["malformed", "identity-only", "empty-identity"],
)
def test_incomplete_response_is_invalid_not_not_found(kind):
    html = positive_html()
    if kind == "malformed":
        html = "<html><body>synthetic malformed response</body></html>"
    elif kind == "identity-only":
        for field, value in [
            ("etapa_ordem_proj", "ESTUDO"), ("estado_ordem_proj", "EXECUCAO"),
            ("status_ordem", "NO PRAZO"),
        ]:
            html = html.replace(
                f"{field}.value = '{value}'", f"{field}.value = ''",
            )
    else:
        html = html.replace('numero_ordem_projeto.value = "SYNTHETIC_001"',
                            'numero_ordem_projeto.value = ""')
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.status == IntegrationStatus.REMOTE_ERROR
    assert result.error_code == "INVALID_RESPONSE"
    assert result.data["outcome"] != "NOT_FOUND"
    if kind == "empty-identity":
        assert result.data["returned_sob"] == ""


@pytest.mark.parametrize("code,http_status,status,outcome", [
    (UniversalizacaoCode.AUTH_REJECTED, 401,
     IntegrationStatus.AUTH_REQUIRED, "AUTHENTICATION_REQUIRED"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 403,
     IntegrationStatus.AUTH_REQUIRED, "AUTHENTICATION_REQUIRED"),
    (UniversalizacaoCode.TIMEOUT, None, IntegrationStatus.TIMEOUT, "TIMEOUT"),
    (UniversalizacaoCode.CONNECTION_ERROR, None,
     IntegrationStatus.UNAVAILABLE, "UNAVAILABLE"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 500,
     IntegrationStatus.REMOTE_ERROR, "ERROR"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 404,
     IntegrationStatus.REMOTE_ERROR, "ERROR"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 302,
     IntegrationStatus.REMOTE_ERROR, "ERROR"),
])
def test_transport_failure_is_classified_without_fabricated_not_found(
    code, http_status, status, outcome, caplog,
):
    client = Mock()
    client.read_order.return_value = transport_result(code, http_status)
    result = _query(UniversalizacaoProvider(client))
    assert result.status == status
    assert result.data["outcome"] == outcome
    assert result.error_code == outcome
    assert result.data["returned_sob"] is None
    _assert_sanitized(result, caplog)


@pytest.mark.parametrize(
    "supplier_value", [None, (None, None), ("synthetic-user", "")],
)
def test_missing_credentials_and_supplier_require_auth_locally(supplier_value):
    client = Mock()
    supplier = (
        None if supplier_value is None else Mock(return_value=supplier_value)
    )
    provider = UniversalizacaoProvider(client, supplier)
    result = provider.consultar_os_sob("SYNTHETIC_001", "A")
    assert result.status == IntegrationStatus.AUTH_REQUIRED
    client.read_order.assert_not_called()
    if supplier is not None:
        supplier.assert_called_once_with()


@pytest.mark.parametrize("context", [object(), _context("SYNTHETIC_002")],
                         ids=["wrong-context-type", "foreign-sob"])
def test_invalid_sovereign_context_precedes_supplier_and_http(context):
    client, supplier = Mock(), Mock()
    result = UniversalizacaoProvider(client, supplier).consultar_os_sob(
        "SYNTHETIC_001", "A", context=context,
    )
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH
    supplier.assert_not_called()
    client.read_order.assert_not_called()


def test_independent_query_requires_active_integration_context():
    client, supplier = Mock(), Mock()
    result = UniversalizacaoProvider(client, supplier).consultar_os_sob(
        "SYNTHETIC_002", "B", independent_query=True,
    )
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH
    supplier.assert_not_called()
    client.read_order.assert_not_called()


def test_context_identifiers_survive_without_credentials_or_payload(caplog):
    provider, _ = provider_with_html(positive_html())
    state = dict(vars(provider))
    caplog.set_level(logging.DEBUG)
    result = _query(provider, context=_context())
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data["correlation_id"] == "synthetic-correlation"
    assert result.data["execution_id"] == "synthetic-execution"
    assert result.data["order_status"] == {
        "etapa_ordem_proj": "ESTUDO", "estado_ordem_proj": "EXECUCAO",
        "status_ordem": "NO PRAZO",
    }
    assert vars(provider) == state
    assert set(vars(provider)) == {
        "_client", "_credential_supplier", "_descriptor",
    }
    _assert_sanitized(result, caplog, positive_html())


@pytest.mark.parametrize("method", ["business", "work-order"])
def test_generic_interfaces_require_explicit_group_then_use_supplier(method):
    provider, client = provider_with_html(positive_html("B"))
    supplier = Mock(return_value=("synthetic-user", "synthetic-secret"))
    provider = UniversalizacaoProvider(client, supplier)
    args = (_context(), "SOB", "SYNTHETIC_001") if method == "business" else (
        _context(), "SYNTHETIC_001",
    )
    operation = (
        provider.query_business_entity if method == "business"
        else provider.get_work_order_status
    )
    rejected = operation(*args)
    assert rejected.status == IntegrationStatus.INVALID_REQUEST
    supplier.assert_not_called()
    client.read_order.assert_not_called()
    result = operation(*args, grupo="B")
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data["returned_grupo"] == "B"
    supplier.assert_called_once_with()
    assert client.read_order.call_args.args == (
        "SYNTHETIC_001", "B", "synthetic-user", "synthetic-secret",
    )


def test_read_only_interfaces_manual_registry_and_default_catalog_are_local():
    client, supplier = Mock(), Mock()
    provider = UniversalizacaoProvider(client, supplier)
    assert isinstance(provider, IBusinessSystemProvider)
    assert isinstance(provider, IWorkOrderProvider)
    assert not UniversalizacaoProvider.__abstractmethods__
    assert (
        provider.descriptor.authentication.scheme == AuthenticationScheme.NTLM
    )
    assert provider.descriptor.capabilities == {
        IntegrationCapability.WORK_ORDER_READ,
        IntegrationCapability.BUSINESS_DATA_READ,
    }
    default = IntegrationRegistry.create_default()
    baseline = [item.provider_id for item in default.list_providers()]
    assert "universalizacao" not in baseline
    registry = IntegrationRegistry()
    registry.register(provider)
    assert registry.get("universalizacao") is provider
    assert (
        registry.get_capabilities("universalizacao")
        == provider.descriptor.capabilities
    )
    assert [item.provider_id for item in default.list_providers()] == baseline
    fresh_default = IntegrationRegistry.create_default()
    assert (
        [item.provider_id for item in fresh_default.list_providers()]
        == baseline
    )
    assert provider.check_availability().data == {
        "status": "LOCAL_CONFIGURATION_READY", "network_checked": False,
    }
    supplier.assert_not_called()
    client.read_order.assert_not_called()


@pytest.mark.parametrize("spoof", ["quoted", "line-comment", "block-comment"])
def test_spoofed_identity_cannot_prove_success(spoof):
    source = positive_html().split("<script language='javascript'>", 1)[1]
    source = source.split("</script>")[0]
    if spoof == "quoted":
        source = "var synthetic = " + json.dumps(source) + ";"
    elif spoof == "line-comment":
        source = "// " + source + "\n"
    else:
        source = "/* " + source + " */"
    provider, _ = provider_with_html("<script>" + source + "</script>")
    result = _query(provider)
    assert result.error_code == "INVALID_RESPONSE"
    assert result.status == IntegrationStatus.REMOTE_ERROR


@pytest.mark.parametrize(
    "literal", [
        "123", "'SYNTHETIC_' + '001'", "synthetic_call()",
        r"'SYNTHETIC_\q001'", r"'SYNTHETIC_\uZZZZ'",
    ],
)
def test_nonliteral_identity_is_rejected(literal):
    html = positive_html().replace('"SYNTHETIC_001"', literal)
    assert not parse_order_response(html).valid
    provider, _ = provider_with_html(html)
    assert _query(provider).error_code == "INVALID_RESPONSE"


@pytest.mark.parametrize(
    "damage", ["duplicate", "unclosed-script", "unclosed-block"],
)
def test_ambiguous_or_unclosed_script_fails_closed(damage):
    html = positive_html()
    if damage == "duplicate":
        html = html.replace(
            "}</script>",
            "parent.mainFrame.document.frm1.grupo.value='B';}</script>",
        )
    elif damage == "unclosed-script":
        html = html.removesuffix("</script>")
    else:
        html = html.replace(
            "}</script>", "}/* synthetic unclosed comment</script>",
        )
    assert not parse_order_response(html).valid
    provider, _ = provider_with_html(html)
    assert _query(provider).error_code == "INVALID_RESPONSE"


def test_literal_escapes_are_decoded_without_evaluation():
    html = positive_html().replace(
        '"SYNTHETIC_001"', r"'SYNTHETIC_\x30\u00301'",
    )
    html = html.replace("'ESTUDO'", r"'ESTUDO \'SYNTHETIC\''")
    parsed = parse_order_response(html)
    assert parsed.valid
    assert parsed.fields["numero_ordem_projeto"] == "SYNTHETIC_001"
    assert parsed.fields["etapa_ordem_proj"] == "ESTUDO 'SYNTHETIC'"


def test_status_vocabulary_is_not_inferred_from_one_example():
    html = positive_html()
    for value in ("ESTUDO", "EXECUCAO", "NO PRAZO"):
        html = html.replace(f"'{value}'", "'SYNTHETIC_INVALID_STATUS'")
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data["order_status"]["status_ordem"] == "SYNTHETIC_INVALID_STATUS"


def test_script_buttons_never_execute_or_persist(monkeypatch, caplog):
    provider, _ = provider_with_html(positive_html())
    guards = []
    with monkeypatch.context() as patches:
        for owner, name in [
            (builtins, "eval"), (builtins, "exec"), (builtins, "open"),
            (subprocess, "Popen"), (subprocess, "run"), (webbrowser, "open"),
            (Path, "write_text"), (Path, "write_bytes"),
        ]:
            guard = Mock(side_effect=AssertionError("Forbidden operation"))
            patches.setattr(owner, name, guard)
            guards.append(guard)
        result = _query(provider)
    assert result.status == IntegrationStatus.SUCCESS
    for guard in guards:
        guard.assert_not_called()
    _assert_sanitized(result, caplog, "bt_gravar", "bt_excluir")


def test_hostile_provider_error_does_not_retain_or_log_private_fields(caplog):
    client = Mock()
    client.read_order.side_effect = RuntimeError(
        "synthetic-user synthetic-secret "
        "synthetic_sql_marker synthetic-private-notes"
    )
    provider = UniversalizacaoProvider(client)
    state = dict(vars(provider))
    caplog.set_level(logging.DEBUG)
    result = _query(provider)
    assert result.error_code == "ERROR"
    assert result.status == IntegrationStatus.REMOTE_ERROR
    assert vars(provider) == state
    _assert_sanitized(result, caplog)


def test_project_data_from_observed_literal_fields_without_logging(caplog):
    html = positive_html().replace(
        "}</script>",
        "parent.mainFrame.document.frm1.logradouro.value='synthetic-address';"
        "parent.mainFrame.document.frm1.bairro.value='synthetic-district';"
        "parent.mainFrame.document.frm1.municipio.value='synthetic-city';"
        "parent.mainFrame.document.frm1.area_tecnica.value='synthetic-pole';"
        "parent.mainFrame.document.frm1.tipo_servico.value='synthetic-service';"
        "parent.mainFrame.document.frm1.notas_referencia.value='synthetic-ref';"
        "}</script>",
    )
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.is_success
    assert result.data["identity"] == {"grupo": "A", "sob": "SYNTHETIC_001"}
    assert result.data["project_data"] == {
        "nome": "synthetic-private-person", "endereco": "synthetic-address",
        "bairro": "synthetic-district", "municipio": "synthetic-city",
        "polo_tecnico": "synthetic-pole", "tipo_servico": "synthetic-service",
        "notas_observacao": "synthetic-private-notes",
        "referencia": "synthetic-ref",
    }
    assert all(value not in caplog.text
               for value in result.data["project_data"].values())


_SYNTHETIC_PROJECT_SOURCES = {
    "nome": "nome",
    "endereco": "logradouro",
    "bairro": "bairro",
    "municipio": "municipio",
    "polo_tecnico": "area_tecnica",
    "tipo_servico": "tipo_servico",
    "notas_observacao": "notas_obs",
    "referencia": "notas_referencia",
}
_SYNTHETIC_PROJECT_VALUES = {
    canonical: "synthetic-authorized-" + canonical
    for canonical in _SYNTHETIC_PROJECT_SOURCES
}


def _project_html(grupo="A", values=None):
    values = _SYNTHETIC_PROJECT_VALUES if values is None else values
    html = positive_html(grupo)
    for source, value in (
        ("nome", "synthetic-private-person"),
        ("notas_obs", "synthetic-private-notes"),
    ):
        html = html.replace(
            f"parent.mainFrame.document.frm1.{source}.value = '{value}';",
            "",
        )
    assignments = "".join(
        f"parent.mainFrame.document.frm1."
        f"{_SYNTHETIC_PROJECT_SOURCES[canonical]}.value="
        f"{json.dumps(value, ensure_ascii=True)};"
        for canonical, value in values.items()
    )
    return html.replace("}</script>", assignments + "}</script>")


def _with_script(html, source):
    return html.replace("}</script>", source + "}</script>")


def _assert_project_result(result, caplog, expected):
    assert result.data["project_data"] == expected
    assert set(result.data["project_data"]) == set(
        _SYNTHETIC_PROJECT_SOURCES
    )
    for value in _SYNTHETIC_PROJECT_VALUES.values():
        assert value not in caplog.text
        if not result.is_success:
            assert value not in json.dumps(asdict(result)) + repr(result)
    _assert_sanitized(result, caplog)


@pytest.mark.parametrize("grupo", ["A", "B"])
def test_authorized_full_project_preserves_existing_contract(grupo, caplog):
    caplog.set_level(logging.DEBUG)
    provider, client = provider_with_html(_project_html(grupo))
    result = provider.consultar_os_sob(
        "SYNTHETIC_001", grupo, context=_context(),
        username="synthetic-user", password="synthetic-secret",
    )
    assert result.status == IntegrationStatus.SUCCESS
    assert result.error_code is None
    assert result.data == {
        "outcome": "SUCCEEDED", "requested_sob": "SYNTHETIC_001",
        "requested_grupo": grupo, "returned_sob": "SYNTHETIC_001",
        "returned_grupo": grupo,
        "order_status": {
            "etapa_ordem_proj": "ESTUDO",
            "estado_ordem_proj": "EXECUCAO", "status_ordem": "NO PRAZO",
        },
        "http_status": 200, "authenticated": True,
        "transport": {
            "operation": "QUERY_ORDER", "method": "GET", "route": ORDER_PATH,
            "authentication_backend": "pyspnego.NTLMProxy/use_ntlm",
            "ntlm_version": "NTLMv2", "sspi": False,
            "expected_target_seen": True, "proxy_mode": "DIRECT",
            "redirects_followed": False, "connection_reused": True,
            "cookies_sent": False, "cookies_persisted": False,
            "handshake_steps": [
                {
                    "stage": "GET", "http_status": 401,
                    "authenticate_schemes": ["negotiate", "ntlm"],
                    "authorization_present": False,
                    "outgoing_type": None, "outgoing_token_bytes": 0,
                    "incoming_type": None, "incoming_token_bytes": 0,
                },
                {
                    "stage": "TYPE1", "http_status": 401,
                    "authenticate_schemes": ["ntlm"],
                    "authorization_present": True,
                    "outgoing_type": 1, "outgoing_token_bytes": 4,
                    "incoming_type": 2, "incoming_token_bytes": 8,
                },
                {
                    "stage": "TYPE3", "http_status": 200,
                    "authenticate_schemes": [],
                    "authorization_present": True,
                    "outgoing_type": 3, "outgoing_token_bytes": 12,
                    "incoming_type": None, "incoming_token_bytes": 0,
                },
            ],
        },
        "identity": {"grupo": grupo, "sob": "SYNTHETIC_001"},
        "project_data": _SYNTHETIC_PROJECT_VALUES,
        "correlation_id": "synthetic-correlation",
        "execution_id": "synthetic-execution",
    }
    client.read_order.assert_called_once()
    _assert_project_result(result, caplog, _SYNTHETIC_PROJECT_VALUES)


@pytest.mark.parametrize("missing", [
    ("polo_tecnico",), ("referencia",),
    tuple(_SYNTHETIC_PROJECT_SOURCES),
], ids=["pole", "reference", "all-business-fields"])
def test_optional_project_fields_missing_are_null(missing, caplog):
    values = {key: value for key, value in _SYNTHETIC_PROJECT_VALUES.items()
              if key not in missing}
    provider, _ = provider_with_html(_project_html(values=values))
    result = _query(provider)
    assert result.is_success
    expected = {key: values.get(key) for key in _SYNTHETIC_PROJECT_SOURCES}
    _assert_project_result(result, caplog, expected)


@pytest.mark.parametrize("empty", ["", "   ", "\n\r\t"],
                         ids=["empty", "spaces", "escaped-whitespace"])
def test_empty_or_whitespace_project_values_are_null(empty, caplog):
    values = dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES, empty)
    provider, _ = provider_with_html(_project_html(values=values))
    result = _query(provider)
    assert result.is_success
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


def test_business_unicode_spaces_quotes_and_escaped_controls_preserved(
    caplog,
):
    value = "  synthetic-P\u00f3lo '\u00e7' \"quoted\" \\ path\n\r\tend  "
    values = dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES, value)
    html = _project_html(values=values)
    parsed = parse_order_response(html)
    assert parsed.valid
    for source in _SYNTHETIC_PROJECT_SOURCES.values():
        assert parsed.fields[source] == value
    caplog.set_level(logging.DEBUG)
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.is_success
    _assert_project_result(result, caplog, values)
    assert value not in caplog.text
    assert "synthetic-P" not in caplog.text


@pytest.mark.parametrize("length", [257, 16384, 16385])
def test_business_notes_have_separate_exact_length_bound(length, caplog):
    value = "synthetic-note-" + "x" * (length - len("synthetic-note-"))
    values = dict(_SYNTHETIC_PROJECT_VALUES)
    values.update(notas_observacao=value, referencia=value)
    html = _project_html(values=values)
    parsed = parse_order_response(html)
    provider, _ = provider_with_html(html)
    result = _query(provider)
    if length <= 16384:
        assert parsed.valid
        assert result.is_success
        _assert_project_result(result, caplog, values)
    else:
        assert not parsed.valid
        assert result.error_code == "INVALID_RESPONSE"
        _assert_project_result(
            result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
        )
    assert value not in caplog.text


@pytest.mark.parametrize("field,original", [
    ("numero_ordem_projeto", '"SYNTHETIC_001"'),
    ("status_ordem", "'NO PRAZO'"),
])
def test_original_identity_and_status_keep_256_character_parser_limit(
    field, original,
):
    for length in (256, 257):
        html = _project_html().replace(
            f"{field}.value = {original}",
            f"{field}.value = {json.dumps('x' * length)}",
        )
        parsed = parse_order_response(html)
        assert parsed.valid is (length == 256)
        if length == 256:
            assert parsed.fields[field] == "x" * 256
        else:
            provider, _ = provider_with_html(html)
            assert _query(provider).error_code == "INVALID_RESPONSE"


@pytest.mark.parametrize("literal", [
    "'synthetic-raw\nline'", "'synthetic-raw\rline'",
    "'synthetic-raw\ttab'", "'synthetic-nul\x00'",
    r"'synthetic-control\b'",
], ids=["raw-lf", "raw-cr", "raw-tab", "nul", "escaped-control"])
def test_business_raw_newlines_and_controls_fail_closed(literal, caplog):
    html = _project_html(values={})
    for source in _SYNTHETIC_PROJECT_SOURCES.values():
        damaged = _with_script(
            html, f"parent.mainFrame.document.frm1.{source}.value={literal};",
        )
        assert not parse_order_response(damaged).valid
        provider, _ = provider_with_html(damaged)
        result = _query(provider)
        assert result.error_code == "INVALID_RESPONSE"
        _assert_project_result(
            result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
        )


@pytest.mark.parametrize("expression", [
    "123", "'synthetic-' + 'expression'", "synthetic_call()",
])
def test_new_project_fields_require_literal_strings(expression, caplog):
    for source in _SYNTHETIC_PROJECT_SOURCES.values():
        html = _with_script(
            _project_html(values={}),
            f"parent.mainFrame.document.frm1.{source}.value={expression};",
        )
        assert not parse_order_response(html).valid
        provider, _ = provider_with_html(html)
        result = _query(provider)
        assert result.error_code == "INVALID_RESPONSE"
        _assert_project_result(
            result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
        )


def test_conflicting_project_duplicates_are_invalid(caplog):
    for source in _SYNTHETIC_PROJECT_SOURCES.values():
        html = _with_script(
            _project_html(),
            f"parent.mainFrame.document.frm1.{source}.value="
            "'synthetic-conflicting-value';",
        )
        assert not parse_order_response(html).valid
        provider, _ = provider_with_html(html)
        result = _query(provider)
        assert result.error_code == "INVALID_RESPONSE"
        _assert_project_result(
            result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
        )
        assert "synthetic-conflicting-value" not in repr(result)


@pytest.mark.parametrize("spoof", ["quoted", "line-comment", "block-comment"])
def test_project_assignments_in_quotes_or_comments_are_not_data(spoof):
    assignments = "".join(
        f"parent.mainFrame.document.frm1.{source}.value="
        "'synthetic-spoofed-business';"
        for source in _SYNTHETIC_PROJECT_SOURCES.values()
    )
    if spoof == "quoted":
        assignments = "var synthetic = " + json.dumps(assignments) + ";"
    elif spoof == "line-comment":
        assignments = "// " + assignments + "\n"
    else:
        assignments = "/* " + assignments + " */"
    html = _with_script(_project_html(values={}), assignments)
    parsed = parse_order_response(html)
    assert parsed.valid
    assert not set(_SYNTHETIC_PROJECT_SOURCES.values()) & set(parsed.fields)
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.is_success
    assert result.data["project_data"] == dict.fromkeys(
        _SYNTHETIC_PROJECT_SOURCES,
    )


def test_unknown_fields_and_guessed_aliases_never_supply_project_data(caplog):
    source = "".join(
        f"parent.mainFrame.document.frm1.{name}.value="
        "'synthetic-unapproved-alias';"
        for name in (
            "base", "polo_tecnico", "ref_projeto_interno", "automaticgroup",
            "synthetic_unknown",
        )
    )
    html = _with_script(_project_html(values={}), source)
    parsed = parse_order_response(html)
    assert parsed.valid
    assert "synthetic-unapproved-alias" not in parsed.fields.values()
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.is_success
    assert result.data["identity"] == {"grupo": "A", "sob": "SYNTHETIC_001"}
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )
    assert "base" not in result.data["project_data"]
    assert "synthetic-unapproved-alias" not in repr(result) + caplog.text
    provider, _ = provider_with_html(_with_script(_project_html(), source))
    result = _query(provider)
    _assert_project_result(result, caplog, _SYNTHETIC_PROJECT_VALUES)
    for name in ("grupo", "select_grupo"):
        html = html.replace(
            f'parent.mainFrame.document.frm1.{name}.value = "A";', "",
        )
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.error_code == "INVALID_RESPONSE"
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


@pytest.mark.parametrize("field,original,replacement", [
    ("numero_ordem_projeto", "SYNTHETIC_001", "SYNTHETIC_OTHER"),
    ("grupo", "A", "B"),
])
def test_wrong_identity_never_discloses_authorized_project(
    field, original, replacement, caplog,
):
    html = _project_html().replace(
        f'{field}.value = "{original}"',
        f'{field}.value = "{replacement}"',
    )
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH
    assert result.data["outcome"] == "IDENTITY_MISMATCH"
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


@pytest.mark.parametrize("tail", [
    "parent.mainFrame.document.frm1.notas_referencia.value =",
    "parent.mainFrame.document.frm1.area_tecnica.value = "
    "'synthetic-truncated-business'",
], ids=["missing-literal", "missing-terminator"])
def test_truncated_recognized_business_assignment_is_invalid(tail, caplog):
    html = _project_html().replace("}</script>", "}" + tail + "</script>")
    parsed = parse_order_response(html)
    provider, _ = provider_with_html(html)
    result = _query(provider)
    assert not parsed.valid
    assert result.status == IntegrationStatus.REMOTE_ERROR
    assert result.error_code == "INVALID_RESPONSE"
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


@pytest.mark.parametrize("code,http_status,outcome", [
    (UniversalizacaoCode.AUTH_REJECTED, 401, "AUTHENTICATION_REQUIRED"),
    (UniversalizacaoCode.TIMEOUT, None, "TIMEOUT"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 500, "ERROR"),
    (UniversalizacaoCode.UNEXPECTED_HTTP, 200, "ERROR"),
])
def test_consumed_project_is_null_on_transport_nonsuccess(
    code, http_status, outcome, caplog,
):
    html = _project_html()
    provider, client = provider_with_html(html)
    successful_read = client.read_order.side_effect

    def failing_read(*args, **kwargs):
        successful_read(*args, **kwargs)
        return transport_result(code, http_status)

    client.read_order.side_effect = failing_read
    caplog.set_level(logging.DEBUG)
    result = _query(provider, context=_context())
    assert not result.is_success
    assert result.data["outcome"] == outcome
    assert result.error_code == outcome
    assert result.data["outcome"] != "NOT_FOUND"
    assert result.data["correlation_id"] == "synthetic-correlation"
    assert result.data["execution_id"] == "synthetic-execution"
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


@pytest.mark.parametrize("failure,status,outcome", [
    ("request", IntegrationStatus.INVALID_REQUEST, "INVALID_REQUEST"),
    ("credentials", IntegrationStatus.AUTH_REQUIRED,
     "AUTHENTICATION_REQUIRED"),
    ("context", IntegrationStatus.IDENTITY_MISMATCH, "IDENTITY_MISMATCH"),
])
def test_local_nonsuccess_returns_only_null_project_values(
    failure, status, outcome, caplog,
):
    client = Mock()
    provider = UniversalizacaoProvider(client)
    if failure == "request":
        result = provider.consultar_os_sob(
            "SYNTHETIC_001", "C", username="synthetic-user",
            password="synthetic-secret",
        )
    elif failure == "credentials":
        result = provider.consultar_os_sob("SYNTHETIC_001", "A")
    else:
        result = _query(provider, context=object())
    assert result.status == status
    assert result.data["outcome"] == outcome
    client.read_order.assert_not_called()
    _assert_project_result(
        result, caplog, dict.fromkeys(_SYNTHETIC_PROJECT_SOURCES),
    )


def test_project_return_is_authorized_but_never_executed_logged_or_saved(
    monkeypatch, caplog,
):
    import sqlite3

    html = _project_html()
    provider, _ = provider_with_html(html)
    state = dict(vars(provider))
    caplog.set_level(logging.DEBUG)
    guards = []
    with monkeypatch.context() as patches:
        for owner, name in [
            (builtins, "eval"), (builtins, "exec"), (builtins, "open"),
            (subprocess, "Popen"), (subprocess, "run"),
            (webbrowser, "open"), (sqlite3, "connect"),
            (Path, "write_text"), (Path, "write_bytes"), (Path, "open"),
        ]:
            guard = Mock(side_effect=AssertionError("Forbidden operation"))
            patches.setattr(owner, name, guard)
            guards.append(guard)
        result = _query(provider)
    assert result.is_success
    assert vars(provider) == state
    for guard in guards:
        guard.assert_not_called()
    _assert_project_result(result, caplog, _SYNTHETIC_PROJECT_VALUES)
    _assert_sanitized(result, caplog, html, "bt_gravar", "bt_excluir")
    serialized = json.dumps(asdict(result)) + repr(result)
    assert all(value in serialized
               for value in _SYNTHETIC_PROJECT_VALUES.values())
    assert "parent.mainFrame" not in serialized + caplog.text

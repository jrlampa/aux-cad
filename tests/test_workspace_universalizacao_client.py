import base64
import json
import logging
import os
import socket
import struct
from urllib.parse import parse_qs, urlsplit
from dataclasses import asdict, replace
from email.message import Message
from importlib.metadata import version
from unittest.mock import Mock

import pytest
from spnego._ntlm_raw.messages import Challenge, NegotiateFlags

from workspace import workspace_universalizacao_client as module


@pytest.fixture
def exchange(monkeypatch):
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
        headers["Set-Cookie"] = "synthetic-cookie=do-not-return"
        if authenticate:
            headers["WWW-Authenticate"] = authenticate
        return Mock(status=status, headers=headers, read=Mock(return_value=body))

    connection = Mock(sock=object())
    connection.getresponse.side_effect = [
        response(401, "Negotiate, NTLM"),
        response(401, "NTLM " + base64.b64encode(challenge).decode()),
        response(200, body=b"<title>Universaliza&#231;&#227;o</title>"),
    ]
    monkeypatch.setattr(module.http.client, "HTTPConnection", Mock(
        return_value=connection
    ))
    return connection, challenge, response


def test_complete_pure_ntlmv2_handshake(exchange, caplog):
    connection, _, _ = exchange
    caplog.set_level(logging.DEBUG)
    client = module.UniversalizacaoClient()
    result = client.get_home("EXAMPLE\\synthetic-user", "synthetic-secret")
    assert result.success
    assert result.http_status == 200
    assert result.authenticated
    assert result.diagnostic.page_confirmed
    assert result.diagnostic.connection_reused
    assert not result.diagnostic.sspi
    assert result.provider_status == "SUCCESS"
    assert [step.http_status for step in result.diagnostic.steps] == [401, 401, 200]
    calls = connection.request.call_args_list
    assert "Authorization" not in calls[0].kwargs["headers"]
    for call, expected in zip(calls[1:], (1, 3)):
        value = call.kwargs["headers"]["Authorization"].split()[1]
        token = base64.b64decode(value)
        assert module._message_type(token) == expected
        assert value not in caplog.text
    assert "synthetic-secret" not in caplog.text
    assert "Authorization" not in caplog.text
    assert "NTLM step" not in caplog.text
    serialized = json.dumps(asdict(result))
    for forbidden in ("synthetic-secret", "synthetic-user", "synthetic-cookie"):
        assert forbidden not in serialized
    assert not hasattr(client, "password")
    connection.close.assert_called_once()


@pytest.mark.parametrize("username,password,code", [
    (None, "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    ("EXAMPLE\\synthetic-user", None, module.UniversalizacaoCode.PASSWORD_REQUIRED),
])
def test_missing_credentials_do_not_connect(exchange, username, password, code):
    connection, _, _ = exchange
    result = module.UniversalizacaoClient().get_home(username, password)
    assert result.code == code
    assert result.provider_status == "AUTH_REQUIRED"
    connection.request.assert_not_called()


def test_type3_rejection_is_auth_required(exchange):
    connection, _, response = exchange
    responses = list(connection.getresponse.side_effect)
    responses[2] = response(401, "Negotiate, NTLM")
    connection.getresponse.side_effect = responses
    result = module.UniversalizacaoClient().get_home(
        "EXAMPLE\\synthetic-user", "synthetic-secret"
    )
    assert not result.success
    assert not result.authenticated
    assert result.http_status == 401
    assert result.code == module.UniversalizacaoCode.AUTH_REJECTED
    assert result.provider_status == "AUTH_REQUIRED"
    assert result.diagnostic.stage == "TYPE3"


def test_order_invalid_identity_maps_locally_to_invalid_request(exchange):
    connection, _, _ = exchange
    result = module.UniversalizacaoClient().read_order(
        "SYNTHETIC_001", "C", "synthetic-user", "synthetic-secret",
        consume=Mock(),
    )
    assert result.code == module.UniversalizacaoCode.INVALID_REQUEST
    assert result.provider_status == "INVALID_REQUEST"
    connection.request.assert_not_called()


@pytest.mark.parametrize("grupo", ["A", "B"])
def test_order_get_reuses_ntlm_and_sends_explicit_identity(exchange, grupo):
    connection, _, _ = exchange
    responses = _responses(connection)
    html = _synthetic_order_html(grupo)
    responses[2].read.return_value = html.encode("utf-8")
    connection.getresponse.side_effect = responses
    original_socket = connection.sock
    consume = Mock()
    result = module.UniversalizacaoClient().read_order(
        "SYNTHETIC_001", grupo, "EXAMPLE\\synthetic-user", "synthetic-secret",
        consume=consume,
    )
    assert result.success
    assert result.operation == "QUERY_ORDER"
    assert result.url == module.BASE_URL + module.ORDER_PATH
    assert result.diagnostic.connection_reused
    assert not result.diagnostic.sspi
    assert result.diagnostic.backend == "pyspnego.NTLMProxy/use_ntlm"
    assert [step.http_status for step in result.diagnostic.steps] == [
        401, 401, 200,
    ]
    assert connection.sock is original_socket
    assert connection.request.call_count == 3
    for call in connection.request.call_args_list:
        assert call.args[0] == "GET"
        path = urlsplit(call.args[1])
        assert path.path == module.ORDER_PATH
        assert parse_qs(path.query) == {
            "num_ordem_proj": ["SYNTHETIC_001"], "grupo": [grupo]
        }
        assert path.query == "num_ordem_proj=SYNTHETIC_001&grupo=" + grupo
        assert call.kwargs["headers"]["Connection"] == "keep-alive"
        assert "Cookie" not in call.kwargs["headers"]
    calls = connection.request.call_args_list
    assert "Authorization" not in calls[0].kwargs["headers"]
    for call, expected in zip(calls[1:], (1, 3)):
        token = base64.b64decode(
            call.kwargs["headers"]["Authorization"].split()[1]
        )
        assert module._message_type(token) == expected
    consume.assert_called_once_with(html)
    assert html not in json.dumps(asdict(result))
    connection.close.assert_called_once()


@pytest.fixture(autouse=True)
def prohibit_real_connections(monkeypatch):
    def forbidden_connection(*_args, **_kwargs):
        pytest.fail("A unit test attempted a real network connection")

    monkeypatch.setattr(socket, "create_connection", forbidden_connection)
    monkeypatch.setattr(socket, "socket", forbidden_connection)


def _run_client():
    return module.UniversalizacaoClient().get_home(
        "EXAMPLE\\synthetic-user", "synthetic-secret"
    )


def _responses(connection):
    return list(connection.getresponse.side_effect)


def _assert_private(result, caplog, forbidden):
    serialized = json.dumps(asdict(result)) + repr(result)
    leaked = any(
        value in serialized or value in caplog.text for value in forbidden
    )
    assert not leaked, "Sensitive data escaped into diagnostics or logs"
    assert not any(record.exc_info for record in caplog.records), (
        "Exception traceback escaped into logs"
    )


def _assert_closed(connection):
    connection.close.assert_called_once_with()
    module.http.client.HTTPConnection.assert_called_once_with(
        "gtecprorio.enelint.global", 80, timeout=20.0
    )


def _target_info_challenge(challenge, target_info):
    packet = bytearray(challenge)
    flags = struct.unpack_from("<I", packet, 20)[0] | 0x00800000
    struct.pack_into("<I", packet, 20, flags)
    struct.pack_into(
        "<HHI", packet, 40, len(target_info), len(target_info), len(packet)
    )
    return bytes(packet) + target_info


def test_installed_ntlm_dependency_version():
    assert version("pyspnego") == "0.12.1"


def test_real_ntlm_type1_type2_and_structural_ntlmv2_type3(exchange, caplog):
    connection, challenge, _ = exchange
    domain = "ENELINT".encode("utf-16-le")
    target_info = struct.pack("<HH", 2, len(domain)) + domain
    target_info += struct.pack("<HHQ", 7, 8, 132537600000000000)
    target_info += struct.pack("<HH", 0, 0)
    challenge = _target_info_challenge(challenge, target_info)
    responses = _responses(connection)
    encoded = base64.b64encode(challenge).decode("ascii")
    responses[1].headers.replace_header("WWW-Authenticate", "NTLM " + encoded)
    connection.getresponse.side_effect = responses
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="spnego")
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.SUCCESS
    assert result.diagnostic.expected_target_seen
    assert result.diagnostic.backend == "pyspnego.NTLMProxy/use_ntlm"
    assert result.diagnostic.ntlm_version == "NTLMv2"
    assert [step.stage for step in result.diagnostic.steps] == [
        "GET", "TYPE1", "TYPE3"
    ]
    assert [step.outgoing_type for step in result.diagnostic.steps] == [
        None, 1, 3
    ]
    assert result.diagnostic.steps[1].incoming_type == 2
    assert result.diagnostic.steps[1].incoming_token_bytes == len(challenge)
    outgoing = [
        call.kwargs["headers"]["Authorization"].split()[1]
        for call in connection.request.call_args_list[1:]
    ]
    type1, type3 = [
        base64.b64decode(value, validate=True) for value in outgoing
    ]
    assert type1[:8] == b"NTLMSSP\x00"
    assert struct.unpack_from("<I", type1, 8)[0] == 1
    assert struct.unpack_from("<I", challenge, 8)[0] == 2
    assert module.Challenge.unpack(challenge).target_name == "ENELINT"
    assert type3[:8] == b"NTLMSSP\x00"
    assert struct.unpack_from("<I", type3, 8)[0] == 3
    nt_length, nt_allocated, nt_offset = struct.unpack_from("<HHI", type3, 20)
    assert nt_allocated == nt_length
    assert nt_offset >= 64
    assert nt_offset + nt_length <= len(type3)
    nt_response = type3[nt_offset:nt_offset + nt_length]
    assert len(nt_response) >= 48
    assert nt_response[16:24] == b"\x01\x01" + b"\x00" * 6
    assert nt_response[24:32] == struct.pack("<Q", 132537600000000000)
    assert nt_response[40:44] == b"\x00" * 4
    for field_offset, expected in [(28, "EXAMPLE"), (36, "synthetic-user")]:
        length, allocated, offset = struct.unpack_from(
            "<HHI", type3, field_offset
        )
        assert allocated == length
        assert offset + length <= len(type3)
        assert type3[offset:offset + length].decode("utf-16-le") == expected
    assert result.diagnostic.steps[2].outgoing_token_bytes == len(type3)
    for call in connection.request.call_args_list:
        assert call.args == ("GET", module.HOME_PATH)
        assert call.kwargs["headers"]["Connection"] == "keep-alive"
        assert "Cookie" not in call.kwargs["headers"]
    for response in responses:
        response.read.assert_called_once_with(module.MAX_BODY_BYTES + 1)
    _assert_private(
        result, caplog, outgoing + [encoded, "Authorization", "NTLM step"]
    )
    _assert_closed(connection)


def test_software_context_forces_ntlm_and_suppresses_pyspnego_debug(
    exchange, monkeypatch
):
    real_client = module.spnego.client
    contexts = []

    def capture_context(*args, **kwargs):
        context = real_client(*args, **kwargs)
        contexts.append(context)
        return context

    factory = Mock(side_effect=capture_context)
    monkeypatch.setattr(module.spnego, "client", factory)
    result = _run_client()
    assert result.success
    assert type(contexts[0]) is module.NTLMProxy
    assert contexts[0]._nt_v2 is True
    assert contexts[0]._is_wrapped is True
    assert (
        factory.call_args.kwargs["options"]
        == module.spnego.NegotiateOptions.use_ntlm
    )
    assert factory.call_args.kwargs["protocol"] == "ntlm"
    assert factory.call_args.kwargs["service"] == "http"
    assert not result.diagnostic.sspi


@pytest.mark.parametrize("backend", ["non-ntlm", "ntlm-without-v2"])
def test_non_software_or_non_v2_context_never_connects(
    exchange, monkeypatch, backend
):
    context = (
        object() if backend == "non-ntlm" else Mock(spec=module.NTLMProxy)
    )
    if backend == "ntlm-without-v2":
        context._nt_v2 = False
    monkeypatch.setattr(module.spnego, "client", Mock(return_value=context))
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INTERNAL_ERROR
    assert not result.success
    module.http.client.HTTPConnection.assert_not_called()


@pytest.mark.parametrize("username,password,code", [
    (None, "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    ("EXAMPLE\\synthetic-user", None,
     module.UniversalizacaoCode.PASSWORD_REQUIRED),
    ("", "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    ("   ", "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    ("\t\n", "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    (123, "synthetic-secret", module.UniversalizacaoCode.USERNAME_REQUIRED),
    ("EXAMPLE\\synthetic-user", "",
     module.UniversalizacaoCode.PASSWORD_REQUIRED),
    ("EXAMPLE\\synthetic-user", "   ",
     module.UniversalizacaoCode.PASSWORD_REQUIRED),
    ("EXAMPLE\\synthetic-user", "\t\n",
     module.UniversalizacaoCode.PASSWORD_REQUIRED),
    ("EXAMPLE\\synthetic-user", 123,
     module.UniversalizacaoCode.PASSWORD_REQUIRED),
], ids=[
    "missing-user", "missing-password", "empty-user", "space-user",
    "whitespace-user", "nonstring-user", "empty-password", "space-password",
    "whitespace-password", "nonstring-password",
])
def test_blank_credentials_never_create_connection(
    exchange, username, password, code
):
    connection, _, _ = exchange
    result = module.UniversalizacaoClient().get_home(username, password)
    assert result.code == code
    assert not result.success
    assert not result.authenticated
    assert result.diagnostic.stage == "CREDENTIALS"
    assert result.diagnostic.steps == ()
    module.http.client.HTTPConnection.assert_not_called()
    connection.close.assert_not_called()


@pytest.mark.parametrize(
    "stage,index", [("GET", 0), ("TYPE1", 1), ("TYPE3", 2)]
)
@pytest.mark.parametrize("operation", ["request", "getresponse", "read"])
@pytest.mark.parametrize("error_class,code", [
    (TimeoutError, module.UniversalizacaoCode.TIMEOUT),
    (ConnectionError, module.UniversalizacaoCode.CONNECTION_ERROR),
    (module.http.client.HTTPException,
     module.UniversalizacaoCode.INVALID_RESPONSE),
])
def test_transport_failure_at_every_exchange_stage(
    exchange, stage, index, operation, error_class, code
):
    connection, _, _ = exchange
    responses = _responses(connection)
    error = error_class("Synthetic transport failure")
    connection.getresponse.side_effect = responses
    if operation == "request":
        connection.request.side_effect = [None] * index + [error]
    elif operation == "getresponse":
        connection.getresponse.side_effect = responses[:index] + [error]
    else:
        responses[index].read.side_effect = error
        connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == code
    assert result.diagnostic.stage == stage
    assert len(result.diagnostic.steps) == index
    assert not result.success
    assert not result.authenticated
    assert connection.request.call_count == index + 1
    _assert_closed(connection)


@pytest.mark.parametrize("stage,index,status", [
    (stage, index, status)
    for stage, index in [("GET", 0), ("TYPE1", 1), ("TYPE3", 2)]
    for status in [200, 204, 301, 302, 403, 500]
    if not (stage == "TYPE3" and status == 200)
])
def test_unexpected_http_and_redirects_are_not_followed(
    exchange, stage, index, status
):
    connection, _, response = exchange
    responses = _responses(connection)
    responses[index] = response(status, body=b"<title>Universalizacao</title>")
    responses[index].headers["Location"] = "http://redirect.invalid/private"
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.UNEXPECTED_HTTP
    assert result.http_status == status
    assert result.diagnostic.stage == stage
    assert not result.success
    assert not result.authenticated
    assert not result.diagnostic.redirects_followed
    assert connection.request.call_count == index + 1
    _assert_closed(connection)


@pytest.mark.parametrize("kind", [
    "invalid-base64", "invalid-padding", "oversized-token", "wrong-type",
    "bad-signature", "short-message", "truncated-target-info",
    "invalid-target-info",
])
def test_malformed_type2_is_rejected_before_type3(exchange, kind):
    connection, challenge, _ = exchange
    if kind == "invalid-base64":
        encoded = "%%%"
    elif kind == "invalid-padding":
        encoded = "A"
    elif kind == "oversized-token":
        encoded = "A" * (module.MAX_TOKEN_CHARS + 1)
    else:
        packet = bytearray(challenge)
        if kind == "wrong-type":
            struct.pack_into("<I", packet, 8, 1)
        elif kind == "bad-signature":
            packet[:8] = b"INVALID!"
        elif kind == "short-message":
            packet = packet[:47]
        elif kind == "truncated-target-info":
            packet = bytearray(_target_info_challenge(
                challenge, struct.pack("<HH", 2, 12)
            ))
        else:
            packet = bytearray(_target_info_challenge(
                challenge,
                struct.pack("<HH", 2, 1) + b"\xff" + struct.pack("<HH", 0, 0)
            ))
        encoded = base64.b64encode(packet).decode("ascii")
    responses = _responses(connection)
    responses[1].headers.replace_header("WWW-Authenticate", "NTLM " + encoded)
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INVALID_CHALLENGE
    assert result.diagnostic.stage in {"TYPE1", "TYPE3"}
    assert not result.authenticated
    assert connection.request.call_count == 2
    _assert_closed(connection)


@pytest.mark.parametrize(
    "offer", [None, "Negotiate", 'Basic realm="synthetic"']
)
def test_initial_401_without_ntlm_offer_stops(exchange, offer):
    connection, _, response = exchange
    connection.getresponse.side_effect = [response(401, offer)]
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INVALID_CHALLENGE
    assert result.diagnostic.stage == "GET"
    assert connection.request.call_count == 1
    _assert_closed(connection)


@pytest.mark.parametrize("offer", [None, "Negotiate, NTLM"])
def test_type1_401_without_challenge_stops(exchange, offer):
    connection, _, response = exchange
    responses = _responses(connection)
    responses[1] = response(401, offer)
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INVALID_CHALLENGE
    assert result.diagnostic.stage == "TYPE1"
    assert connection.request.call_count == 2
    _assert_closed(connection)


@pytest.mark.parametrize(
    "index,stage", [(0, "GET"), (1, "TYPE1"), (2, "TYPE3")]
)
def test_oversized_body_is_rejected_at_every_stage(
    exchange, index, stage, monkeypatch
):
    connection, _, _ = exchange
    monkeypatch.setattr(module, "MAX_BODY_BYTES", 64)
    responses = _responses(connection)
    responses[index].read.return_value = b"x" * 65
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INVALID_RESPONSE
    assert result.diagnostic.stage == stage
    responses[index].read.assert_called_once_with(65)
    assert connection.request.call_count == index + 1
    _assert_closed(connection)


def test_body_at_exact_size_limit_is_accepted(exchange, monkeypatch):
    connection, _, _ = exchange
    responses = _responses(connection)
    monkeypatch.setattr(
        module, "MAX_BODY_BYTES", len(responses[2].read.return_value)
    )
    connection.getresponse.side_effect = responses
    assert _run_client().success
    _assert_closed(connection)


@pytest.mark.parametrize("charset,body", [
    ("not-a-real-codec", b"<title>Universalizacao</title>"),
    ("utf-8", b"<title>Universaliza\xffcao</title>"),
    ("ascii", "<title>Universaliza\u00e7\u00e3o</title>".encode("utf-8")),
])
def test_invalid_charset_or_encoding_rejects_200(exchange, charset, body):
    connection, _, _ = exchange
    responses = _responses(connection)
    responses[2].headers.replace_header(
        "Content-Type", "text/html; charset=" + charset
    )
    responses[2].read.return_value = body
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.INVALID_RESPONSE
    assert result.http_status == 200
    assert result.authenticated
    assert not result.success
    assert result.diagnostic.stage == "PAGE_VALIDATION"
    _assert_closed(connection)


@pytest.mark.parametrize("body", [
    b"<title>Login</title>", b"<body>Universalizacao</body>",
    b"<title>AntiUniversalizacaoPortal</title>", b"",
])
def test_200_with_wrong_or_missing_title_is_identity_mismatch(exchange, body):
    connection, _, _ = exchange
    responses = _responses(connection)
    responses[2].read.return_value = body
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.IDENTITY_MISMATCH
    assert result.provider_status == "IDENTITY_MISMATCH"
    assert result.authenticated
    assert not result.diagnostic.page_confirmed
    _assert_closed(connection)


@pytest.mark.parametrize("title,charset,encoding", [
    ("Universaliza\u00e7\u00e3o", "utf-8", "utf-8"),
    ("UNIVERSALIZAC\u0327A\u0303O", "utf-8", "utf-8"),
    ("Portal - Universaliza&ccedil;&atilde;o", "utf-8", "utf-8"),
    ("Universaliza\u00e7\u00e3o", None, "cp1252"),
])
def test_valid_unicode_html_titles(exchange, title, charset, encoding):
    connection, _, _ = exchange
    responses = _responses(connection)
    content_type = "text/html" + ("; charset=" + charset if charset else "")
    responses[2].headers.replace_header("Content-Type", content_type)
    responses[2].read.return_value = (
        "<TITLE>" + title + "</TITLE>"
    ).encode(encoding)
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.success
    assert result.diagnostic.page_confirmed
    _assert_closed(connection)


@pytest.mark.parametrize("index,stage", [(0, "TYPE1"), (1, "TYPE3")])
@pytest.mark.parametrize("change", ["closed", "replaced"])
def test_socket_closed_or_changed_between_rounds_aborts_without_reconnect(
    exchange, index, stage, change
):
    connection, _, _ = exchange
    responses = _responses(connection)
    body = responses[index].read.return_value

    def read_and_change_socket(*_args):
        connection.sock = None if change == "closed" else object()
        return body

    responses[index].read.side_effect = read_and_change_socket
    connection.getresponse.side_effect = responses
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.CONNECTION_CHANGED
    assert result.diagnostic.stage == stage
    assert not result.success
    assert connection.request.call_count == index + 1
    _assert_closed(connection)


@pytest.mark.parametrize("index,stage", [(1, "TYPE1"), (2, "TYPE3")])
def test_socket_replaced_during_authenticated_request_aborts(
    exchange, index, stage
):
    connection, _, _ = exchange
    request_number = 0

    def request_and_change_socket(*_args, **_kwargs):
        nonlocal request_number
        if request_number == index:
            connection.sock = object()
        request_number += 1

    connection.request.side_effect = request_and_change_socket
    result = _run_client()
    assert result.code == module.UniversalizacaoCode.CONNECTION_CHANGED
    assert result.diagnostic.stage == stage
    assert connection.getresponse.call_count == index
    _assert_closed(connection)


@pytest.mark.parametrize("index", [0, 1, 2], ids=["get", "type1", "type3"])
@pytest.mark.parametrize("error_class,code", [
    (TimeoutError, module.UniversalizacaoCode.TIMEOUT),
    (ConnectionError, module.UniversalizacaoCode.CONNECTION_ERROR),
    (module.http.client.HTTPException,
     module.UniversalizacaoCode.INVALID_RESPONSE),
    (RuntimeError, module.UniversalizacaoCode.INTERNAL_ERROR),
])
def test_hostile_exception_never_leaks_password_tokens_or_cookies(
    exchange, caplog, index, error_class, code
):
    connection, _, _ = exchange
    responses = _responses(connection)
    private_values = [
        "synthetic-secret", "synthetic-user", "synthetic-access-token-marker",
        "synthetic-session-cookie-marker", "synthetic-cookie=do-not-return",
    ]
    responses[index].read.side_effect = error_class(" ".join(private_values))
    connection.getresponse.side_effect = responses
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="spnego")
    result = _run_client()
    assert result.code == code
    outgoing = [
        call.kwargs["headers"]["Authorization"]
        for call in connection.request.call_args_list
        if "Authorization" in call.kwargs["headers"]
    ]
    private_values += outgoing + [value.split()[1] for value in outgoing]
    _assert_private(
        result, caplog, private_values + ["Authorization", "NTLM step"]
    )
    _assert_closed(connection)


@pytest.mark.parametrize("base_url", [
    "https://gtecprorio.enelint.global", "ftp://gtecprorio.enelint.global",
    "http://gtecprorio.enelint.global:443",
    "http://gtecprorio.enelint.global:8080",
    "http://synthetic-user@gtecprorio.enelint.global",
    "http://synthetic-user:synthetic-secret@gtecprorio.enelint.global",
    "http://gtecprorio.enelint.global/?query=1",
    "http://gtecprorio.enelint.global/#fragment",
    "http://gtecprorio.enelint.global/other", "http:///missing-host", "",
    "http://gtecprorio.enelint.global:invalid",
    "http://gtecprorio.enelint.global:65536",
    "http://[invalid-host",
], ids=["https", "ftp", "port443", "port8080", "userinfo", "userinfo-password",
        "query", "fragment", "wrong-path", "missing-host", "empty-url",
        "nonnumeric-port", "out-of-range-port", "unmatched-bracket"])
def test_invalid_configuration_url_never_connects(exchange, caplog, base_url):
    caplog.set_level(logging.DEBUG)
    result = module.UniversalizacaoClient(module.UniversalizacaoConfig(
        base_url=base_url
    )).get_home("EXAMPLE\\synthetic-user", "synthetic-secret")
    assert result.code == module.UniversalizacaoCode.INVALID_CONFIGURATION
    assert result.diagnostic.stage == "CONFIGURATION"
    assert result.url == module.BASE_URL + module.HOME_PATH
    assert not result.success
    module.http.client.HTTPConnection.assert_not_called()
    _assert_private(result, caplog, ["synthetic-user", "synthetic-secret"])


@pytest.mark.parametrize(
    "timeout", [0, -1, True, "20", None, float("nan"), float("inf")]
)
def test_invalid_timeout_never_connects(exchange, timeout):
    result = module.UniversalizacaoClient(module.UniversalizacaoConfig(
        timeout=timeout
    )).get_home("EXAMPLE\\synthetic-user", "synthetic-secret")
    assert result.code == module.UniversalizacaoCode.INVALID_CONFIGURATION
    module.http.client.HTTPConnection.assert_not_called()


@pytest.mark.parametrize("level", ["0", "1", "2"])
def test_insecure_lm_compat_level_is_rejected_without_environment_mutation(
    exchange, monkeypatch, level
):
    monkeypatch.setenv("LM_COMPAT_LEVEL", level)
    result = _run_client()
    assert not result.success
    assert result.code == module.UniversalizacaoCode.INVALID_CONFIGURATION
    module.http.client.HTTPConnection.assert_not_called()
    assert os.environ["LM_COMPAT_LEVEL"] == level


@pytest.mark.parametrize("level", ["3", "4", "5"])
def test_secure_lm_compat_levels_keep_real_ntlmv2(
    exchange, monkeypatch, level
):
    monkeypatch.setenv("LM_COMPAT_LEVEL", level)
    result = _run_client()
    assert result.success
    assert result.diagnostic.ntlm_version == "NTLMv2"
    assert os.environ["LM_COMPAT_LEVEL"] == level


def test_environment_proxies_are_ignored(exchange, monkeypatch):
    connection, _, _ = exchange
    for name in [
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy"
    ]:
        monkeypatch.setenv(name, "http://synthetic-proxy.invalid:9999")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    result = _run_client()
    assert result.success
    assert result.diagnostic.proxy_mode == "DIRECT"
    connection.set_tunnel.assert_not_called()
    connection.set_debuglevel.assert_called_once_with(0)
    _assert_closed(connection)


@pytest.mark.parametrize("status", [200, 401])
def test_client_keeps_only_configuration_after_operation(exchange, status):
    connection, _, response = exchange
    responses = _responses(connection)
    if status == 401:
        responses[2] = response(401, "NTLM")
    connection.getresponse.side_effect = responses
    client = module.UniversalizacaoClient()
    original_state = dict(vars(client))
    result = client.get_home("EXAMPLE\\synthetic-user", "synthetic-secret")
    assert result.http_status == status
    assert vars(client) == original_state
    assert set(vars(client)) == {"config"}
    assert not any(hasattr(client, name) for name in [
        "username", "password", "credentials", "context",
        "connection", "token", "cookies"
    ])
    _assert_closed(connection)


def test_close_oserror_does_not_destroy_success_or_leak(exchange, caplog):
    connection, _, _ = exchange
    connection.close.side_effect = OSError(
        "synthetic-secret synthetic-close-cookie"
    )
    caplog.set_level(logging.DEBUG)
    result = _run_client()
    assert result.success
    _assert_private(
        result, caplog, ["synthetic-secret", "synthetic-close-cookie"]
    )
    _assert_closed(connection)


def test_hostile_unexpected_close_exception_does_not_escape(exchange, caplog):
    connection, _, _ = exchange
    connection.close.side_effect = RuntimeError(
        "synthetic-secret synthetic-close-token"
    )
    caplog.set_level(logging.DEBUG)
    try:
        result = _run_client()
    except Exception:
        pytest.fail("Client leaked an exception from cleanup", pytrace=False)
    _assert_private(
        result, caplog, ["synthetic-secret", "synthetic-close-token"]
    )
    assert result.code in {
        module.UniversalizacaoCode.SUCCESS,
        module.UniversalizacaoCode.INTERNAL_ERROR
    }
    _assert_closed(connection)


@pytest.mark.parametrize("code,expected", [
    (module.UniversalizacaoCode.SUCCESS, "SUCCESS"),
    (module.UniversalizacaoCode.USERNAME_REQUIRED, "AUTH_REQUIRED"),
    (module.UniversalizacaoCode.PASSWORD_REQUIRED, "AUTH_REQUIRED"),
    (module.UniversalizacaoCode.AUTH_REJECTED, "AUTH_REQUIRED"),
    (module.UniversalizacaoCode.TIMEOUT, "TIMEOUT"),
    (module.UniversalizacaoCode.CONNECTION_ERROR, "UNAVAILABLE"),
    (module.UniversalizacaoCode.CONNECTION_CHANGED, "UNAVAILABLE"),
    (module.UniversalizacaoCode.INVALID_CONFIGURATION, "UNAVAILABLE"),
    (module.UniversalizacaoCode.IDENTITY_MISMATCH, "IDENTITY_MISMATCH"),
    (module.UniversalizacaoCode.UNEXPECTED_HTTP, "REMOTE_ERROR"),
    (module.UniversalizacaoCode.INVALID_CHALLENGE, "REMOTE_ERROR"),
    (module.UniversalizacaoCode.INVALID_RESPONSE, "REMOTE_ERROR"),
    (module.UniversalizacaoCode.INTERNAL_ERROR, "REMOTE_ERROR"),
    ("FUTURE_PROVIDER_CODE", "REMOTE_ERROR"),
])
def test_future_provider_mapping_codes(exchange, code, expected):
    result = replace(_run_client(), code=code)
    assert result.provider_status == expected


def _synthetic_order_html(grupo="A"):
    return (
        "nome=synthetic-outside-name notas_obs=synthetic-outside-notes "
        "SELECT synthetic_sql_marker FROM synthetic_table;"
        "<script>if(parent.mainFrame.document.frm1){"
        "parent.mainFrame.document.frm1.numero_ordem_projeto.value="
        "'SYNTHETIC_001';"
        f"parent.mainFrame.document.frm1.grupo.value='{grupo}';"
        f"parent.mainFrame.document.frm1.select_grupo.value='{grupo}';"
        "parent.mainFrame.document.frm1.etapa_ordem_proj.value='ESTUDO';"
        "parent.mainFrame.document.frm1.estado_ordem_proj.value='EXECUCAO';"
        "parent.mainFrame.document.frm1.status_ordem.value='NO PRAZO';"
        "parent.mainFrame.document.frm1.bt_gravar.disabled=false;"
        "parent.mainFrame.document.frm1.bt_excluir.disabled=false;"
        "}</script>"
    )


def _read_synthetic_order(client=None, consume=None):
    client = client if client is not None else module.UniversalizacaoClient()
    return client.read_order(
        "SYNTHETIC_001", "A", "EXAMPLE\\synthetic-user", "synthetic-secret",
        consume=consume if consume is not None else Mock(),
    )


@pytest.mark.parametrize("sob,grupo", [
    ("", "A"), ("https://synthetic.invalid/order", "A"),
    ("SYNTHETIC_001\r\n", "A"), ("SYNTHETIC_001&grupo=B", "A"),
    ("SYNTHETIC_001?route=other", "B"), ("SYNTHETIC_001", None),
    ("SYNTHETIC_001", ""), ("SYNTHETIC_001", "C"),
    ("SYNTHETIC_001", "a"), ("SYNTHETIC_001", "b"),
    ("SYNTHETIC_001", " A"), ("SYNTHETIC_001", "B "),
])
def test_order_invalid_identity_precedes_credentials_ntlm_and_http(
    exchange, monkeypatch, sob, grupo,
):
    connection, _, _ = exchange
    context_factory = Mock()
    monkeypatch.setattr(module, "_new_context", context_factory)
    consume = Mock()
    result = module.UniversalizacaoClient().read_order(
        sob, grupo, None, None, consume=consume,
    )
    assert result.code == module.UniversalizacaoCode.INVALID_REQUEST
    assert result.diagnostic.stage == "REQUEST_VALIDATION"
    assert result.diagnostic.steps == ()
    assert not result.authenticated
    context_factory.assert_not_called()
    module.http.client.HTTPConnection.assert_not_called()
    connection.request.assert_not_called()
    consume.assert_not_called()


@pytest.mark.parametrize("base_url", [
    "http://synthetic.invalid", module.BASE_URL + "/arbitrary-route.asp",
    module.BASE_URL + module.ORDER_PATH,
])
def test_order_rejects_arbitrary_hosts_and_routes_before_http(
    exchange, base_url,
):
    consume = Mock()
    client = module.UniversalizacaoClient(module.UniversalizacaoConfig(
        base_url=base_url,
    ))
    result = _read_synthetic_order(client, consume)
    assert result.code == module.UniversalizacaoCode.INVALID_CONFIGURATION
    assert result.url == module.BASE_URL + module.ORDER_PATH
    module.http.client.HTTPConnection.assert_not_called()
    consume.assert_not_called()


@pytest.mark.parametrize(
    "index,status", [(0, 403), (1, 403), (2, 401), (2, 403)],
)
def test_query_auth_rejection_never_consumes_or_retries(
    exchange, index, status,
):
    connection, _, response = exchange
    responses = _responses(connection)
    responses[index] = response(status, body=_synthetic_order_html().encode())
    connection.getresponse.side_effect = responses
    consume = Mock()
    result = _read_synthetic_order(consume=consume)
    assert result.code == module.UniversalizacaoCode.AUTH_REJECTED
    assert result.provider_status == "AUTH_REQUIRED"
    assert result.http_status == status
    assert not result.success
    assert not result.authenticated
    consume.assert_not_called()
    assert connection.request.call_count == index + 1
    _assert_closed(connection)


@pytest.mark.parametrize("failure", ["timeout", "bad-gateway"])
def test_query_timeout_and_502_stop_without_callback(
    exchange, failure, caplog,
):
    connection, _, response = exchange
    responses = _responses(connection)
    if failure == "timeout":
        responses[2].read.side_effect = TimeoutError(
            "synthetic-secret synthetic_sql_marker"
        )
        expected = module.UniversalizacaoCode.TIMEOUT
    else:
        responses[2] = response(502, body=_synthetic_order_html().encode())
        expected = module.UniversalizacaoCode.UNEXPECTED_HTTP
    connection.getresponse.side_effect = responses
    consume = Mock()
    result = _read_synthetic_order(consume=consume)
    assert result.code == expected
    assert not result.success
    assert not result.authenticated
    assert connection.request.call_count == 3
    consume.assert_not_called()
    _assert_private(
        result, caplog, ["synthetic-secret", "synthetic_sql_marker"],
    )
    _assert_closed(connection)


@pytest.mark.parametrize("failure", ["redirect", "socket-change"])
def test_order_has_no_redirect_cookie_reconnect_or_retry(exchange, failure):
    connection, _, response = exchange
    responses = _responses(connection)
    if failure == "redirect":
        responses[2] = response(302, body=_synthetic_order_html().encode())
        responses[2].headers["Location"] = "http://synthetic.invalid/other"
        expected, requests = module.UniversalizacaoCode.UNEXPECTED_HTTP, 3
    else:
        body = responses[1].read.return_value

        def change_socket(*_args):
            connection.sock = object()
            return body

        responses[1].read.side_effect = change_socket
        expected, requests = module.UniversalizacaoCode.CONNECTION_CHANGED, 2
    connection.getresponse.side_effect = responses
    consume = Mock()
    result = _read_synthetic_order(consume=consume)
    assert result.code == expected
    assert not result.diagnostic.redirects_followed
    assert connection.request.call_count == requests
    assert all("Cookie" not in call.kwargs["headers"]
               for call in connection.request.call_args_list)
    consume.assert_not_called()
    _assert_closed(connection)


@pytest.mark.parametrize("consumer_fails", [False, True])
def test_order_payload_and_credentials_never_remain_on_client_or_result(
    exchange, caplog, consumer_fails,
):
    connection, _, _ = exchange
    html = _synthetic_order_html()
    responses = _responses(connection)
    responses[2].read.return_value = html.encode()
    connection.getresponse.side_effect = responses
    client = module.UniversalizacaoClient()
    state = dict(vars(client))
    consume = Mock(side_effect=RuntimeError(html) if consumer_fails else None)
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="spnego")
    result = _read_synthetic_order(client, consume)
    expected = (module.UniversalizacaoCode.INTERNAL_ERROR if consumer_fails
                else module.UniversalizacaoCode.SUCCESS)
    assert result.code == expected
    consume.assert_called_once_with(html)
    assert vars(client) == state
    assert set(vars(client)) == {"config"}
    assert set(asdict(result)) == {
        "success", "code", "http_status", "url", "operation",
        "elapsed_seconds", "authenticated", "message", "diagnostic",
    }
    outgoing = [call.kwargs["headers"]["Authorization"].split()[1]
                for call in connection.request.call_args_list[1:]]
    _assert_private(result, caplog, outgoing + [
        html, "synthetic-user", "synthetic-secret", "synthetic-outside-name",
        "synthetic-outside-notes", "synthetic_sql_marker", "synthetic-cookie",
    ])
    _assert_closed(connection)


def test_order_missing_consumer_is_rejected_before_http(exchange):
    connection, _, _ = exchange
    result = module.UniversalizacaoClient().read_order(
        "SYNTHETIC_001", "A", "EXAMPLE\\synthetic-user", "synthetic-secret",
        consume=None,
    )
    assert result.code == module.UniversalizacaoCode.INVALID_REQUEST
    assert result.diagnostic.stage == "REQUEST_VALIDATION"
    module.http.client.HTTPConnection.assert_not_called()
    connection.request.assert_not_called()

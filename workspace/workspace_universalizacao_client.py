"""Isolated, read-only Universalizacao client using software NTLMv2.

Credentials are operation arguments, never client state. HTTP is direct on
port 80; redirects, environment proxies and cookies are deliberately unused.
Private backend fields are version-pinned; exception boundaries must never
return third-party error text or expose a traceback containing credentials.
"""

# pylint: disable=protected-access,broad-exception-caught

from __future__ import annotations

import base64
import binascii
import http.client
import logging
import math
import os
import re
import struct
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlencode, urlsplit

import spnego
from spnego._ntlm import NTLMProxy
from spnego._ntlm_raw.messages import Challenge, NegotiateFlags


BASE_URL = "http://gtecprorio.enelint.global"
HOME_PATH = "/sistemas/universalizacao/"
ORDER_PATH = HOME_PATH + "controle.asp"
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TOKEN_CHARS = 65536
logger = logging.getLogger("aux_cad.workspace.universalizacao_client")


class UniversalizacaoCode(str, Enum):
    SUCCESS = "SUCCESS"
    USERNAME_REQUIRED = "USERNAME_REQUIRED"
    PASSWORD_REQUIRED = "PASSWORD_REQUIRED"
    AUTH_REJECTED = "AUTH_REJECTED"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    UNEXPECTED_HTTP = "UNEXPECTED_HTTP"
    INVALID_CHALLENGE = "INVALID_CHALLENGE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CONNECTION_CHANGED = "CONNECTION_CHANGED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True)
class UniversalizacaoConfig:
    base_url: str = field(default=BASE_URL, repr=False)
    timeout: float = 20.0


@dataclass(frozen=True)
class HandshakeStep:
    stage: str
    http_status: int
    authenticate_schemes: tuple[str, ...]
    authorization_present: bool
    outgoing_type: int | None = None
    outgoing_token_bytes: int = 0
    incoming_type: int | None = None
    incoming_token_bytes: int = 0


@dataclass(frozen=True)
class UniversalizacaoDiagnostic:
    stage: str
    steps: tuple[HandshakeStep, ...] = ()
    backend: str = "pyspnego.NTLMProxy/use_ntlm"
    sspi: bool = False
    ntlm_version: str = "NTLMv2"
    proxy_mode: str = "DIRECT"
    redirects_followed: bool = False
    connection_reused: bool = False
    expected_target_seen: bool = False
    page_confirmed: bool = False


@dataclass(frozen=True)
class UniversalizacaoResult:
    success: bool
    code: UniversalizacaoCode
    http_status: int | None
    url: str
    operation: str
    elapsed_seconds: float
    authenticated: bool
    message: str
    diagnostic: UniversalizacaoDiagnostic

    @property
    def provider_status(self) -> str:
        if self.code == UniversalizacaoCode.SUCCESS:
            return "SUCCESS"
        if self.code == UniversalizacaoCode.INVALID_REQUEST:
            return "INVALID_REQUEST"
        if self.code in {
            UniversalizacaoCode.USERNAME_REQUIRED,
            UniversalizacaoCode.PASSWORD_REQUIRED,
            UniversalizacaoCode.AUTH_REJECTED,
        }:
            return "AUTH_REQUIRED"
        if self.code == UniversalizacaoCode.TIMEOUT:
            return "TIMEOUT"
        if self.code in {
            UniversalizacaoCode.CONNECTION_ERROR,
            UniversalizacaoCode.CONNECTION_CHANGED,
            UniversalizacaoCode.INVALID_CONFIGURATION,
        }:
            return "UNAVAILABLE"
        if self.code == UniversalizacaoCode.IDENTITY_MISMATCH:
            return "IDENTITY_MISMATCH"
        return "REMOTE_ERROR"


class _ClientFailure(Exception):
    def __init__(self, code: UniversalizacaoCode) -> None:
        super().__init__(code.value)
        self.code = code


class _PageTitle(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


def _message_type(token: bytes) -> int:
    if len(token) < 12 or token[:8] != b"NTLMSSP\x00":
        raise ValueError("Invalid NTLM message")
    return struct.unpack_from("<I", token, 8)[0]


def _new_context(username: str, password: str, hostname: str) -> NTLMProxy:
    """Mark the context wrapped to suppress pyspnego's raw-token DEBUG logs."""
    try:
        lm_level = int(os.environ.get("LM_COMPAT_LEVEL", "3"))
    except ValueError:
        raise _ClientFailure(
            UniversalizacaoCode.INVALID_CONFIGURATION
        ) from None
    if lm_level not in (3, 4, 5):
        raise _ClientFailure(UniversalizacaoCode.INVALID_CONFIGURATION)
    context = spnego.client(
        username=username,
        password=password,
        hostname=hostname,
        service="http",
        protocol="ntlm",
        options=spnego.NegotiateOptions.use_ntlm,
    )
    if not isinstance(context, NTLMProxy) or not context._nt_v2:
        raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)
    context._is_wrapped = True
    return context


def _validate_type3(token: bytes) -> None:
    if _message_type(token) != 3 or len(token) < 64:
        raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)
    length, _, offset = struct.unpack_from("<HHI", token, 20)
    if offset < 64 or offset + length > len(token) or length < 48:
        raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)
    if token[offset + 16:offset + 20] != b"\x01\x01\x00\x00":
        raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)


def _validate_challenge(token: bytes) -> None:
    if len(token) < 48 or _message_type(token) != 2:
        raise ValueError("Expected Type 2")
    flags = struct.unpack_from("<I", token, 20)[0]
    header_size = 56 if flags & NegotiateFlags.version else 48
    if len(token) < header_size:
        raise ValueError("Truncated header")
    for position in (12, 40):
        length, allocated, offset = struct.unpack_from("<HHI", token, position)
        if allocated < length or (
            length and (offset < header_size or offset + length > len(token))
        ):
            raise ValueError("Invalid security buffer")
    if flags & NegotiateFlags.target_info:
        length, _, offset = struct.unpack_from("<HHI", token, 40)
        end = offset + length
        while offset + 4 <= end:
            pair_id, pair_length = struct.unpack_from("<HH", token, offset)
            offset += 4
            if pair_id == 0:
                if pair_length != 0 or offset != end:
                    raise ValueError("Invalid AV terminator")
                return
            if offset + pair_length > end:
                raise ValueError("Truncated AV pair")
            offset += pair_length
        raise ValueError("Missing AV terminator")


def _challenge(headers) -> tuple[tuple[str, ...], bytes | None]:
    values = headers.get_all("WWW-Authenticate", [])
    schemes = tuple(sorted({
        match.group(1).lower() for value in values
        for match in re.finditer(
            r"(?:^|,)\s*(Negotiate|NTLM|Basic|Digest)\b", value, re.I
        )
    }))
    for value in values:
        match = re.search(r"(?:^|,)\s*NTLM\s+([^,\s]+)", value, re.I)
        if match:
            encoded = match.group(1)
            try:
                if len(encoded) > MAX_TOKEN_CHARS:
                    raise ValueError("Oversized challenge")
                token = base64.b64decode(encoded, validate=True)
                _validate_challenge(token)
                Challenge.unpack(token)
            except (ValueError, binascii.Error, struct.error, UnicodeError):
                raise _ClientFailure(
                    UniversalizacaoCode.INVALID_CHALLENGE
                ) from None
            return schemes, token
    return schemes, None


def _page_confirmed(body: bytes, charset: str | None) -> bool:
    try:
        if charset:
            text = body.decode(charset)
        else:
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                text = body.decode("windows-1252")
        parser = _PageTitle()
        parser.feed(text)
    except (ValueError, LookupError, UnicodeError):
        raise _ClientFailure(UniversalizacaoCode.INVALID_RESPONSE) from None
    title = unicodedata.normalize("NFKD", "".join(parser.parts)).casefold()
    title = "".join(char for char in title if not unicodedata.combining(char))
    return bool(re.search(r"\buniversalizacao\b", title))


def valid_order_identity(sob: object, grupo: object) -> bool:
    return (
        isinstance(sob, str)
        and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sob) is not None
        and isinstance(grupo, str) and grupo in ("A", "B")
    )


class UniversalizacaoClient:
    """Fixed home/order GETs; no arbitrary route or credential store."""

    def __init__(self, config: UniversalizacaoConfig | None = None) -> None:
        self.config = config or UniversalizacaoConfig()

    def get_home(
        self, username: str | None, password: str | None
    ) -> UniversalizacaoResult:
        return self._authenticated_read(username, password)

    def read_order(
        self, sob: str, grupo: str, username: str | None, password: str | None,
        *, consume: Callable[[str], None],
    ) -> UniversalizacaoResult:
        return self._authenticated_read(
            username, password, order=(sob, grupo), consume=consume
        )

    def _authenticated_read(
        self, username: str | None, password: str | None,
        *, order: tuple[str, str] | None = None,
        consume: Callable[[str], None] | None = None,
    ) -> UniversalizacaoResult:
        started = time.monotonic()
        stage = "CONFIGURATION"
        steps: list[HandshakeStep] = []
        endpoint = HOME_PATH if order is None else ORDER_PATH
        operation = "GET_HOME" if order is None else "QUERY_ORDER"
        url = BASE_URL + endpoint
        status = None
        authenticated = False
        reused = False
        target_seen = False
        confirmed = False
        connection = None
        context = None
        code = UniversalizacaoCode.INTERNAL_ERROR
        try:
            if order is not None and (
                not valid_order_identity(*order) or not callable(consume)
            ):
                stage = "REQUEST_VALIDATION"
                raise _ClientFailure(UniversalizacaoCode.INVALID_REQUEST)
            try:
                parsed = urlsplit(self.config.base_url)
                port = parsed.port
            except (ValueError, TypeError):
                raise _ClientFailure(
                    UniversalizacaoCode.INVALID_CONFIGURATION
                ) from None
            if (
                parsed.scheme != "http" or not parsed.hostname
                or port not in (None, 80)
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ("", "/", HOME_PATH)
                or parsed.query or parsed.fragment
                or (order is not None and
                    parsed.hostname != urlsplit(BASE_URL).hostname)
                or not isinstance(self.config.timeout, (int, float))
                or isinstance(self.config.timeout, bool)
                or not math.isfinite(self.config.timeout)
                or self.config.timeout <= 0
            ):
                raise _ClientFailure(UniversalizacaoCode.INVALID_CONFIGURATION)
            url = "http://" + parsed.hostname + endpoint
            request_path = endpoint
            if order is not None:
                request_path += "?" + urlencode({
                    "num_ordem_proj": order[0], "grupo": order[1]
                })

            def exchange(token=None, expected_socket=None):
                if order is None:
                    return self._exchange(connection, token, expected_socket)
                return self._exchange_path(
                    connection, request_path, token, expected_socket
                )

            stage = "CREDENTIALS"
            if not isinstance(username, str) or not username.strip():
                raise _ClientFailure(UniversalizacaoCode.USERNAME_REQUIRED)
            if not isinstance(password, str) or not password.strip():
                raise _ClientFailure(UniversalizacaoCode.PASSWORD_REQUIRED)
            stage = "NTLM_CONTEXT"
            context = _new_context(username, password, parsed.hostname)
            username = password = None
            connection = http.client.HTTPConnection(
                parsed.hostname, 80, timeout=self.config.timeout
            )
            connection.set_debuglevel(0)
            stage = "GET"
            status, schemes, _, _, socket = exchange()
            steps.append(HandshakeStep(stage, status, schemes, False))
            if order is not None and status == 403:
                raise _ClientFailure(UniversalizacaoCode.AUTH_REJECTED)
            if status != 401:
                raise _ClientFailure(UniversalizacaoCode.UNEXPECTED_HTTP)
            if "ntlm" not in schemes:
                raise _ClientFailure(UniversalizacaoCode.INVALID_CHALLENGE)
            stage = "TYPE1"
            type1 = context.step()
            if type1 is None or _message_type(type1) != 1:
                raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)
            status, schemes, type2, _, _ = exchange(type1, socket)
            reused = True
            steps.append(HandshakeStep(
                stage, status, schemes, True, 1, len(type1),
                2 if type2 else None, len(type2) if type2 else 0,
            ))
            if order is not None and status == 403:
                raise _ClientFailure(UniversalizacaoCode.AUTH_REJECTED)
            if status != 401:
                raise _ClientFailure(UniversalizacaoCode.UNEXPECTED_HTTP)
            if type2 is None:
                raise _ClientFailure(UniversalizacaoCode.INVALID_CHALLENGE)
            target_seen = Challenge.unpack(type2).target_name == "ENELINT"
            stage = "TYPE3"
            try:
                type3 = context.step(type2)
            except (ValueError, struct.error, UnicodeError):
                raise _ClientFailure(
                    UniversalizacaoCode.INVALID_CHALLENGE
                ) from None
            if type3 is None:
                raise _ClientFailure(UniversalizacaoCode.INTERNAL_ERROR)
            _validate_type3(type3)
            status, schemes, _, payload, _ = exchange(type3, socket)
            body, charset = payload
            steps.append(HandshakeStep(
                stage, status, schemes, True, 3, len(type3),
            ))
            if status == 401 or (order is not None and status == 403):
                raise _ClientFailure(UniversalizacaoCode.AUTH_REJECTED)
            if status != 200:
                raise _ClientFailure(UniversalizacaoCode.UNEXPECTED_HTTP)
            authenticated = True
            if order is None:
                stage = "PAGE_VALIDATION"
                confirmed = _page_confirmed(body, charset)
                if not confirmed:
                    raise _ClientFailure(UniversalizacaoCode.IDENTITY_MISMATCH)
            else:
                stage = "RESPONSE_CONSUMPTION"
                try:
                    if charset:
                        text = body.decode(charset)
                    else:
                        try:
                            text = body.decode("utf-8")
                        except UnicodeDecodeError:
                            text = body.decode("windows-1252")
                except (UnicodeError, LookupError):
                    raise _ClientFailure(
                        UniversalizacaoCode.INVALID_RESPONSE
                    ) from None
                consume(text)
                text = None
            code = UniversalizacaoCode.SUCCESS
        except _ClientFailure as error:
            code = error.code
        except TimeoutError:
            code = UniversalizacaoCode.TIMEOUT
        except OSError:
            code = UniversalizacaoCode.CONNECTION_ERROR
        except http.client.HTTPException:
            code = UniversalizacaoCode.INVALID_RESPONSE
        except Exception:
            code = UniversalizacaoCode.INTERNAL_ERROR
        finally:
            username = password = context = None
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        messages = {
            UniversalizacaoCode.SUCCESS: "Pagina Universalizacao confirmada.",
            UniversalizacaoCode.USERNAME_REQUIRED: "Usuario nao informado.",
            UniversalizacaoCode.PASSWORD_REQUIRED: "Senha nao informada.",
            UniversalizacaoCode.AUTH_REJECTED: "Autenticacao rejeitada.",
            UniversalizacaoCode.TIMEOUT: "Tempo limite excedido.",
            UniversalizacaoCode.CONNECTION_ERROR: "Conexao indisponivel.",
            UniversalizacaoCode.UNEXPECTED_HTTP: "Status HTTP inesperado.",
            UniversalizacaoCode.INVALID_CHALLENGE: "Desafio NTLM invalido.",
            UniversalizacaoCode.INVALID_RESPONSE: "Resposta HTTP invalida.",
            UniversalizacaoCode.IDENTITY_MISMATCH: "Pagina inesperada.",
            UniversalizacaoCode.CONNECTION_CHANGED: "Conexao nao reutilizada.",
            UniversalizacaoCode.INVALID_CONFIGURATION: (
                "Configuracao invalida."
            ),
            UniversalizacaoCode.INTERNAL_ERROR: "Erro interno do cliente.",
            UniversalizacaoCode.INVALID_REQUEST: "Identidade invalida.",
        }
        if order is not None and code == UniversalizacaoCode.SUCCESS:
            messages[code] = "Resposta recebida para validacao funcional."
        result = UniversalizacaoResult(
            success=code == UniversalizacaoCode.SUCCESS,
            code=code, http_status=status, url=url, operation=operation,
            elapsed_seconds=max(0.0, time.monotonic() - started),
            authenticated=authenticated, message=messages[code],
            diagnostic=UniversalizacaoDiagnostic(
                stage=stage, steps=tuple(steps), connection_reused=reused,
                expected_target_seen=target_seen, page_confirmed=confirmed,
            ),
        )
        logger.info(
            "Universalizacao operation=%s code=%s http=%s stage=%s",
            operation, code.value, status, stage,
        )
        return result

    @staticmethod
    def _exchange(connection, token=None, expected_socket=None):
        return UniversalizacaoClient._exchange_path(
            connection, HOME_PATH, token, expected_socket
        )

    @staticmethod
    def _exchange_path(connection, path, token=None, expected_socket=None):
        if expected_socket is not None and (
            connection.sock is not expected_socket or connection.sock is None
        ):
            raise _ClientFailure(UniversalizacaoCode.CONNECTION_CHANGED)
        if token is not None and connection.sock is None:
            raise _ClientFailure(UniversalizacaoCode.CONNECTION_CHANGED)
        headers = {"Connection": "keep-alive", "Accept": "text/html"}
        if path != HOME_PATH:
            headers["Referer"] = BASE_URL + HOME_PATH + "principal.asp"
        if token is not None:
            headers["Authorization"] = (
                "NTLM " + base64.b64encode(token).decode("ascii")
            )
        connection.request("GET", path, headers=headers)
        socket = connection.sock
        if expected_socket is not None and socket is not expected_socket:
            raise _ClientFailure(UniversalizacaoCode.CONNECTION_CHANGED)
        response = connection.getresponse()
        schemes, challenge = _challenge(response.headers)
        body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise _ClientFailure(UniversalizacaoCode.INVALID_RESPONSE)
        return (
            response.status, schemes, challenge,
            (body, response.headers.get_content_charset()), socket,
        )

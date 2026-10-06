"""Read-only Universalizacao contract; never executes returned JavaScript.

Only approved literal identity, status and project fields are extracted.
Business data is returned only after identity validation, never logged.
SQL and raw HTML are excluded. NOT_FOUND requires a real negative example.
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from typing import Callable

from workspace.workspace_integrations import (
    AuthenticationDescriptor, AuthenticationScheme, AvailabilityStatus,
    ConfigurationStatus, IBusinessSystemProvider, IWorkOrderProvider,
    IntegrationCapability, IntegrationContext, IntegrationDescriptor,
    IntegrationResult, IntegrationStatus, WorkOrderQuery,
)
from workspace.workspace_universalizacao_client import (
    MAX_BODY_BYTES, ORDER_PATH, UniversalizacaoClient, UniversalizacaoCode,
    UniversalizacaoResult, valid_order_identity,
)


logger = logging.getLogger("aux_cad.workspace.universalizacao_provider")
STATUS_FIELDS = frozenset({
    "etapa_ordem_proj", "estado_ordem_proj", "status_ordem",
})
PROJECT_FIELDS = {
    "nome": "nome",
    "endereco": "logradouro",
    "bairro": "bairro",
    "municipio": "municipio",
    "polo_tecnico": "area_tecnica",
    "tipo_servico": "tipo_servico",
    "notas_observacao": "notas_obs",
    "referencia": "notas_referencia",
}
BUSINESS_FIELDS = frozenset(PROJECT_FIELDS.values())
MAX_BUSINESS_FIELD_CHARS = 16384
ALLOWED_FIELDS = STATUS_FIELDS | BUSINESS_FIELDS | {
    "numero_ordem_projeto", "grupo", "select_grupo",
}
TOKEN = re.compile(
    r"//[^\r\n]*|/\*[\s\S]*?\*/"
    r'|"(?:\\[\s\S]|[^"\\])*"'
    r"|'(?:\\[\s\S]|[^'\\])*'"
    r"|[A-Za-z_$][A-Za-z0-9_$]*|\s+|[^\s]"
)
TARGET = ("parent", ".", "mainFrame", ".", "document", ".", "frm1", ".")
CredentialSupplier = Callable[[], tuple[str | None, str | None]]


class UniversalizacaoOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


@dataclass(frozen=True)
class ParsedOrder:
    valid: bool
    fields: dict[str, str] = field(default_factory=dict, repr=False)


def _tokens(source: str) -> list[str]:
    result = []
    position = 0
    while position < len(source):
        match = TOKEN.match(source, position)
        if match is None:
            raise ValueError("Invalid script structure")
        token = match.group()
        if source.startswith("/*", position) and not token.startswith("/*"):
            raise ValueError("Unterminated block comment")
        position = match.end()
        if token.isspace() or token.startswith(("//", "/*")):
            continue
        if token in ("'", '"'):
            raise ValueError("Unterminated literal")
        result.append(token)
        if len(result) > 100000:
            raise ValueError("Too many tokens")
    return result


def _literal(token: str, *, business_field: bool = False) -> str:
    if len(token) < 2 or token[0] not in ("'", '"') or token[-1] != token[0]:
        raise ValueError("Expected string literal")
    value = []
    position = 1
    escapes = {
        "n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
        "v": "\v", "\\": "\\", "'": "'", '"': '"',
    }
    while position < len(token) - 1:
        char = token[position]
        position += 1
        escaped = char == "\\"
        if char == "\\":
            if position >= len(token) - 1:
                raise ValueError("Incomplete escape")
            char = token[position]
            position += 1
            if char in ("u", "x"):
                width = 4 if char == "u" else 2
                digits = token[position:position + width]
                pattern = r"[0-9A-Fa-f]{" + str(width) + "}"
                if not re.fullmatch(pattern, digits):
                    raise ValueError("Invalid escape")
                char = chr(int(digits, 16))
                position += width
            elif char in escapes:
                char = escapes[char]
            else:
                raise ValueError("Unsupported escape")
        if (
            (ord(char) < 32 and not (
                business_field and escaped and char in "\r\n\t"
            )) or 0xD800 <= ord(char) <= 0xDFFF
        ):
            raise ValueError("Unsupported control character")
        value.append(char)
        limit = MAX_BUSINESS_FIELD_CHARS if business_field else 256
        if len(value) > limit:
            raise ValueError("Oversized field")
    return "".join(value)


class _OrderScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self.parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attributes = dict(attrs)
        script_type = (attributes.get("type") or "").lower()
        if tag == "script" and not attributes.get("src") and script_type in (
            "", "text/javascript", "application/javascript",
        ):
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.parts is not None:
            self.scripts.append("".join(self.parts))
            self.parts = None


def parse_order_response(html: str) -> ParsedOrder:
    """Read bounded literal assignments without interpreting JS or SQL."""
    try:
        if not isinstance(html, str) or len(html) > MAX_BODY_BYTES:
            return ParsedOrder(False)
        parser = _OrderScripts()
        parser.feed(html)
        if parser.parts is not None:
            return ParsedOrder(False)
        fields: dict[str, str] = {}
        for source in parser.scripts:
            tokens = _tokens(source)
            for position in range(len(tokens)):
                if tuple(tokens[position:position + len(TARGET)]) != TARGET:
                    continue
                start = position + len(TARGET)
                if start >= len(tokens) or tokens[start] not in ALLOWED_FIELDS:
                    continue
                name = tokens[start]
                if tokens[start + 1:start + 4] != [".", "value", "="]:
                    continue
                if start + 5 >= len(tokens):
                    return ParsedOrder(False)
                if tokens[start + 5] not in (";", "}"):
                    return ParsedOrder(False)
                value = _literal(
                    tokens[start + 4], business_field=name in BUSINESS_FIELDS
                )
                if name in fields and fields[name] != value:
                    return ParsedOrder(False)
                fields[name] = value
        return ParsedOrder(True, fields)
    except (ValueError, TypeError, IndexError, RecursionError):
        return ParsedOrder(False)


class UniversalizacaoProvider(IBusinessSystemProvider, IWorkOrderProvider):
    def __init__(
        self, client: UniversalizacaoClient | None = None,
        credential_supplier: CredentialSupplier | None = None,
    ) -> None:
        self._client = (
            client if client is not None else UniversalizacaoClient()
        )
        self._credential_supplier = credential_supplier
        self._descriptor = IntegrationDescriptor(
            provider_id="universalizacao", display_name="Universalizacao",
            provider_type="DistributorPortal", version="1.0.0",
            capabilities={IntegrationCapability.WORK_ORDER_READ,
                          IntegrationCapability.BUSINESS_DATA_READ},
            authentication=AuthenticationDescriptor(
                AuthenticationScheme.NTLM, requires_client_credential=True,
            ),
            configuration_status=ConfigurationStatus.CONFIGURED,
            availability=AvailabilityStatus.UNKNOWN,
        )

    @property
    def provider_id(self) -> str:
        return self._descriptor.provider_id

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def check_availability(self) -> IntegrationResult:
        if self._credential_supplier is None:
            return IntegrationResult.auth_required(
                "Credenciais devem ser fornecidas por operacao."
            )
        return IntegrationResult.success({
            "status": "LOCAL_CONFIGURATION_READY", "network_checked": False,
        })

    def consultar_os_sob(
        self, sob: str, grupo: str | None, *,
        context: IntegrationContext | None = None,
        username: str | None = None, password: str | None = None,
        independent_query: bool = False,
    ) -> IntegrationResult:
        fields: dict[str, str] = {}
        transport = None
        parsed = ParsedOrder(False)
        outcome = UniversalizacaoOutcome.ERROR
        try:
            if not isinstance(grupo, str) or not valid_order_identity(
                sob, grupo
            ):
                outcome = UniversalizacaoOutcome.INVALID_REQUEST
            elif independent_query and not isinstance(
                context, IntegrationContext
            ):
                outcome = UniversalizacaoOutcome.IDENTITY_MISMATCH
            elif context is not None and (
                not isinstance(context, IntegrationContext)
                or (not independent_query and not context.validate_sovereignty(
                    sob, context.database_fingerprint
                ))
            ):
                outcome = UniversalizacaoOutcome.IDENTITY_MISMATCH
            else:
                if (
                    username is None and password is None
                    and self._credential_supplier is not None
                ):
                    username, password = self._credential_supplier()
                if not isinstance(username, str) or not username.strip() or (
                    not isinstance(password, str) or not password.strip()
                ):
                    outcome = UniversalizacaoOutcome.AUTHENTICATION_REQUIRED
                else:
                    def consume(html: str) -> None:
                        nonlocal parsed
                        parsed = parse_order_response(html)

                    transport = self._client.read_order(
                        sob, grupo, username, password, consume=consume,
                    )
                    fields = parsed.fields
                    outcome = self._classify(transport, parsed, sob, grupo)
        except TimeoutError:
            outcome = UniversalizacaoOutcome.TIMEOUT
        except OSError:
            outcome = UniversalizacaoOutcome.UNAVAILABLE
        except Exception:
            outcome = UniversalizacaoOutcome.ERROR
        finally:
            username = password = None
        return self._result(outcome, sob, grupo, fields, transport, context)

    @staticmethod
    def _classify(
        transport: UniversalizacaoResult, parsed: ParsedOrder,
        sob: str, grupo: str | None,
    ) -> UniversalizacaoOutcome:
        if transport.code in {
            UniversalizacaoCode.AUTH_REJECTED,
            UniversalizacaoCode.USERNAME_REQUIRED,
            UniversalizacaoCode.PASSWORD_REQUIRED,
        }:
            return UniversalizacaoOutcome.AUTHENTICATION_REQUIRED
        if transport.code == UniversalizacaoCode.TIMEOUT:
            return UniversalizacaoOutcome.TIMEOUT
        if transport.code in {
            UniversalizacaoCode.CONNECTION_ERROR,
            UniversalizacaoCode.CONNECTION_CHANGED,
            UniversalizacaoCode.INVALID_CONFIGURATION,
        }:
            return UniversalizacaoOutcome.UNAVAILABLE
        if transport.code == UniversalizacaoCode.INVALID_REQUEST:
            return UniversalizacaoOutcome.INVALID_REQUEST
        if transport.code in {
            UniversalizacaoCode.INVALID_RESPONSE,
            UniversalizacaoCode.INVALID_CHALLENGE,
        }:
            return UniversalizacaoOutcome.INVALID_RESPONSE
        if transport.code == UniversalizacaoCode.INTERNAL_ERROR:
            return UniversalizacaoOutcome.ERROR
        if transport.http_status in (401, 403):
            return UniversalizacaoOutcome.AUTHENTICATION_REQUIRED
        if (
            not transport.success or not transport.authenticated
            or transport.http_status != 200
        ):
            return UniversalizacaoOutcome.ERROR
        fields = parsed.fields
        if not parsed.valid:
            return UniversalizacaoOutcome.INVALID_RESPONSE
        if any(
            fields[name] != expected for name, expected in (
                ("numero_ordem_projeto", sob), ("grupo", grupo),
                ("select_grupo", grupo),
            ) if name in fields and fields[name]
        ):
            return UniversalizacaoOutcome.IDENTITY_MISMATCH
        if not fields.get("numero_ordem_projeto") or not fields.get("grupo"):
            return UniversalizacaoOutcome.INVALID_RESPONSE
        if not any(fields.get(name, "").strip() for name in STATUS_FIELDS):
            return UniversalizacaoOutcome.INVALID_RESPONSE
        return UniversalizacaoOutcome.SUCCEEDED

    @staticmethod
    def _result(
        outcome: UniversalizacaoOutcome,
        sob: str,
        grupo: str | None,
        fields: dict[str, str],
        transport: UniversalizacaoResult | None,
        context: IntegrationContext | None,
    ) -> IntegrationResult:
        statuses: dict[UniversalizacaoOutcome, IntegrationStatus] = {
            UniversalizacaoOutcome.SUCCEEDED: IntegrationStatus.SUCCESS,
            UniversalizacaoOutcome.AUTHENTICATION_REQUIRED: (
                IntegrationStatus.AUTH_REQUIRED
            ),
            UniversalizacaoOutcome.INVALID_REQUEST: (
                IntegrationStatus.INVALID_REQUEST
            ),
            UniversalizacaoOutcome.IDENTITY_MISMATCH: (
                IntegrationStatus.IDENTITY_MISMATCH
            ),
            UniversalizacaoOutcome.UNAVAILABLE: IntegrationStatus.UNAVAILABLE,
            UniversalizacaoOutcome.TIMEOUT: IntegrationStatus.TIMEOUT,
        }
        data: dict[str, object] = {
            "outcome": outcome.value,
            "requested_sob": sob if valid_order_identity(sob, grupo) else None,
            "requested_grupo": grupo if grupo in ("A", "B") else None,
            "returned_sob": fields.get("numero_ordem_projeto"),
            "returned_grupo": fields.get("grupo"),
            "order_status": {
                name: fields[name] for name in sorted(STATUS_FIELDS)
                if name in fields
            },
            "http_status": transport.http_status if transport else None,
            "authenticated": transport.authenticated if transport else False,
            "transport": (
                {
                    "operation": transport.operation,
                    "method": "GET",
                    "route": ORDER_PATH,
                    "authentication_backend": transport.diagnostic.backend,
                    "ntlm_version": transport.diagnostic.ntlm_version,
                    "sspi": transport.diagnostic.sspi,
                    "expected_target_seen": (
                        transport.diagnostic.expected_target_seen
                    ),
                    "proxy_mode": transport.diagnostic.proxy_mode,
                    "redirects_followed": (
                        transport.diagnostic.redirects_followed
                    ),
                    "connection_reused": (
                        transport.diagnostic.connection_reused
                    ),
                    "cookies_sent": False,
                    "cookies_persisted": False,
                    "handshake_steps": [
                        {
                            "stage": step.stage,
                            "http_status": step.http_status,
                            "authenticate_schemes": list(
                                step.authenticate_schemes
                            ),
                            "authorization_present": (
                                step.authorization_present
                            ),
                            "outgoing_type": step.outgoing_type,
                            "outgoing_token_bytes": (
                                step.outgoing_token_bytes
                            ),
                            "incoming_type": step.incoming_type,
                            "incoming_token_bytes": (
                                step.incoming_token_bytes
                            ),
                        } for step in transport.diagnostic.steps
                    ],
                } if transport else None
            ),
        }
        data["identity"] = {
            "grupo": data["requested_grupo"], "sob": data["requested_sob"],
        }
        data["project_data"] = {
            canonical: (
                fields[source] if outcome == UniversalizacaoOutcome.SUCCEEDED
                and fields.get(source, "").strip() else None
            ) for canonical, source in PROJECT_FIELDS.items()
        }
        if isinstance(context, IntegrationContext):
            data["correlation_id"] = context.correlation_id
            data["execution_id"] = context.execution_id
        logger.info("Universalizacao outcome=%s http=%s", outcome.value,
                    data["http_status"])
        return IntegrationResult(
            status=statuses.get(outcome, IntegrationStatus.REMOTE_ERROR),
            data=data,
            error_code=(
                None if outcome == UniversalizacaoOutcome.SUCCEEDED
                else outcome.value
            ),
            error_message=(
                None if outcome == UniversalizacaoOutcome.SUCCEEDED
                else "Consulta Universalizacao nao concluida; " + outcome.value
            ),
        )

    def query_business_entity(
        self, context: IntegrationContext, entity_type: str, entity_key: str,
        *, grupo: str | None = None,
    ) -> IntegrationResult:
        if entity_type != "SOB":
            return IntegrationResult.not_supported("Somente SOB e suportada.")
        return self.consultar_os_sob(entity_key, grupo, context=context)

    def get_work_order_status(
        self, context: IntegrationContext, order_id: str,
        *, grupo: str | None = None,
    ) -> IntegrationResult:
        return self.consultar_os_sob(order_id, grupo, context=context)

    def query_work_order(
        self, context: IntegrationContext, query: WorkOrderQuery,
        *, independent_query: bool = False,
    ) -> IntegrationResult:
        return self.consultar_os_sob(
            query.sob, query.grupo, context=context,
            independent_query=independent_query,
        )

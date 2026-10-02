"""Contratos e modelo de estados operacionais resilientes do OXCAD (P2.5).

Distinção obrigatória de 4 dimensões de estado independentes:
1. CORE_STATUS: O núcleo local está operacional?
2. CONNECTIVITY_MODE: Existe conectividade externa?
3. INTEGRATION_AVAILABILITY: As integrações necessárias estão disponíveis/configuradas?
4. OPERATIONAL_MODE: Esta operação pode efetivamente ser executada?
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class CoreStatus(str, Enum):
    """Estado do núcleo operacional local do OXCAD/AutoCAD."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ConnectivityMode(str, Enum):
    """Modo de conectividade de rede externa."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class IntegrationAvailability(str, Enum):
    """Disponibilidade agregada dos provedores de integração externos."""
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class OperationalMode(str, Enum):
    """Capacidade operacional efetiva do sistema ou de uma operação específica."""
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    BLOCKED = "BLOCKED"


# Mensagens de orientação operacional para a UI
OPERATIONAL_MODE_MESSAGES: Dict[OperationalMode, str] = {
    OperationalMode.NORMAL: "Operação online completa; integrações ativas e disponíveis.",
    OperationalMode.DEGRADED: "Operação online parcial; uma ou mais dependências externas estão indisponíveis.",
    OperationalMode.OFFLINE: "Operação local disponível; sincronização externa pendente.",
    OperationalMode.BLOCKED: "Esta operação exige integração externa indisponível/não configurada ou núcleo inoperante.",
}


def derive_system_mode(
    core_status: CoreStatus,
    connectivity_mode: ConnectivityMode,
    integration_availability: IntegrationAvailability,
) -> OperationalMode:
    """
    Deriva o modo operacional geral do sistema a partir das 3 dimensões fundamentais.

    Regras contratuais:
    - Core UNAVAILABLE -> BLOCKED independentemente dos demais estados.
    - Core AVAILABLE + conectividade ONLINE + integrações AVAILABLE -> NORMAL.
    - Core AVAILABLE + conectividade ONLINE + integrações PARTIAL/UNAVAILABLE/NOT_CONFIGURED -> DEGRADED.
    - Core AVAILABLE + conectividade OFFLINE/UNKNOWN -> OFFLINE.
    """
    if core_status == CoreStatus.UNAVAILABLE:
        return OperationalMode.BLOCKED

    if connectivity_mode == ConnectivityMode.ONLINE:
        if integration_availability == IntegrationAvailability.AVAILABLE:
            return OperationalMode.NORMAL
        return OperationalMode.DEGRADED

    # Ausência de conectividade externa com núcleo local disponível
    return OperationalMode.OFFLINE


def evaluate_operation_mode(
    system_context: OperationalStateContext,
    requires_connectivity: bool = False,
    required_providers: Optional[List[str]] = None,
    is_local_supported: bool = True,
    provider_checker: Optional[Callable[[str], bool]] = None,
) -> OperationalMode:
    """
    Avalia a viabilidade operacional de uma ação técnica específica.

    Uma operação individual pode ser BLOCKED mesmo quando o sistema geral
    está OFFLINE ou DEGRADED, caso ela exija conectividade ou provedores externos ausentes.
    """
    if system_context.core_status == CoreStatus.UNAVAILABLE:
        return OperationalMode.BLOCKED

    # Se a operação exige conectividade externa obrigatória e estamos sem rede
    if requires_connectivity and system_context.connectivity_mode != ConnectivityMode.ONLINE:
        return OperationalMode.BLOCKED

    # Se a operação exige provedores externos específicos
    if required_providers:
        for provider_id in required_providers:
            if provider_checker is not None:
                if not provider_checker(provider_id):
                    return OperationalMode.BLOCKED
            else:
                # Sem checker granular, avalia a disponibilidade geral das integrações
                if system_context.integration_availability in (
                    IntegrationAvailability.UNAVAILABLE,
                    IntegrationAvailability.NOT_CONFIGURED,
                ):
                    return OperationalMode.BLOCKED

    # Operação suportada localmente
    if is_local_supported:
        if system_context.connectivity_mode == ConnectivityMode.ONLINE:
            if system_context.integration_availability == IntegrationAvailability.AVAILABLE:
                return OperationalMode.NORMAL
            return OperationalMode.DEGRADED
        return OperationalMode.OFFLINE

    return OperationalMode.BLOCKED


@dataclass(frozen=True)
class OperationalStateContext:
    """
    Contexto contendo as 4 dimensões explícitas do estado operacional.
    NÃO unifica os status em uma propriedade única.
    """
    core_status: CoreStatus = CoreStatus.AVAILABLE
    connectivity_mode: ConnectivityMode = ConnectivityMode.OFFLINE
    integration_availability: IntegrationAvailability = IntegrationAvailability.NOT_CONFIGURED
    operational_mode: OperationalMode = OperationalMode.OFFLINE

    @classmethod
    def create(
        cls,
        core_status: CoreStatus = CoreStatus.AVAILABLE,
        connectivity_mode: ConnectivityMode = ConnectivityMode.OFFLINE,
        integration_availability: IntegrationAvailability = IntegrationAvailability.NOT_CONFIGURED,
    ) -> OperationalStateContext:
        derived = derive_system_mode(core_status, connectivity_mode, integration_availability)
        return cls(
            core_status=core_status,
            connectivity_mode=connectivity_mode,
            integration_availability=integration_availability,
            operational_mode=derived,
        )

    @property
    def ui_message(self) -> str:
        return OPERATIONAL_MODE_MESSAGES.get(
            self.operational_mode,
            "Estado operacional não determinado."
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_status": self.core_status.value,
            "connectivity_mode": self.connectivity_mode.value,
            "integration_availability": self.integration_availability.value,
            "operational_mode": self.operational_mode.value,
            "ui_message": self.ui_message,
        }

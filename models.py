"""Shared data structures passed between the agents.

The whole system operates on one object: `Incident`. Each agent reads it,
enriches the fields it owns, and passes it on. No agent overwrites a field
belonging to another agent -- that constraint is what keeps the pipeline
independently testable.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Contact:
    """One entry in the user's emergency contact roster."""
    name: str
    relation: str
    channels: List[str]
    distance_km: float          # distance from the user's usual location
    availability: float         # historical response reliability, 0.0 - 1.0
    medically_qualified: bool = False
    weight: float = 0.0         # filled in by the Prioritisation Agent
    status: str = "idle"        # idle -> queued -> sent -> acknowledged / escalated


@dataclass
class SensorPacket:
    """Raw input as it arrives from the wearable, phone or vehicle unit."""
    event: str                  # fall | cardiac | crash | sos | fire | inactive
    heart_rate: int             # bpm
    impact_g: float             # peak acceleration in G
    user_reply: int             # 0 = no reply, 1 = "I'm OK", 2 = "Need help"
    location_key: str           # home | road | campus | unknown
    signal_integrity: float = 0.98


@dataclass
class Message:
    """One composed, channel-specific notification."""
    contact: str
    channel: str
    body: str


@dataclass
class Incident:
    """The shared state object that flows through the six agents."""
    incident_id: str
    packet: Optional[SensorPacket] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # Agent 1 - Perception
    normalised: Dict[str, Any] = field(default_factory=dict)

    # Agent 2 - Triage
    severity: int = 0
    tier: int = 3
    scoring_terms: List[str] = field(default_factory=list)
    suppressed: bool = False

    # Agent 3 - Context
    location: str = ""
    coordinates: str = ""
    nearest_facility: str = ""
    medical_profile: Dict[str, str] = field(default_factory=dict)

    # Agent 4 - Prioritisation
    ranked_contacts: List[Contact] = field(default_factory=list)

    # Agent 5 - Composer
    messages: List[Message] = field(default_factory=list)

    # Agent 6 - Dispatch and escalation
    dispatched: List[str] = field(default_factory=list)
    acknowledged: List[str] = field(default_factory=list)
    escalated: List[str] = field(default_factory=list)
    outcome: str = "pending"

    # Audit trail: every agent appends its reasoning here
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, agent: str, lines: List[str]) -> None:
        """Append one agent's reasoning to the audit trail."""
        self.trace.append({
            "agent": agent,
            "at": datetime.now().strftime("%H:%M:%S"),
            "lines": lines,
        })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

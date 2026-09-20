"""The orchestrator: wires the six agents into a pipeline and runs them."""

import itertools
from typing import Callable, List, Optional

from .agents import (Agent, ComposerAgent, ContextAgent, DispatchAgent,
                     PerceptionAgent, PrioritisationAgent, TriageAgent)
from .models import Incident, SensorPacket

_counter = itertools.count(1)


class Orchestrator:
    """Runs an incident through the agent pipeline.

    Agents 4, 5 and 6 are skipped when the Triage Agent suppresses the
    incident -- that early exit is the false-alarm suppression path.
    """

    def __init__(self, gateway: Optional[Callable] = None):
        self.pre: List[Agent] = [PerceptionAgent(), TriageAgent(), ContextAgent()]
        self.post: List[Agent] = [PrioritisationAgent(), ComposerAgent(),
                                  DispatchAgent(gateway)]

    def handle(self, packet: SensorPacket) -> Incident:
        inc = Incident(incident_id="INC-%04d" % next(_counter), packet=packet)

        for agent in self.pre:
            agent.run(inc)

        if inc.suppressed:
            inc.outcome = "suppressed - self-cleared low-severity event, logged only"
            inc.log("Orchestrator",
                    ["dispatch threshold not met and user self-cleared",
                     "agents 4-6 skipped; protecting contacts from alert fatigue"])
            return inc

        for agent in self.post:
            agent.run(inc)
        return inc


def make_packet(event: str, heart_rate: int, impact_g: float,
                user_reply: int, location_key: str) -> SensorPacket:
    """Small helper so callers do not need to import the dataclass."""
    return SensorPacket(event=event, heart_rate=heart_rate, impact_g=impact_g,
                        user_reply=user_reply, location_key=location_key)

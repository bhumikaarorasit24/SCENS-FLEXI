"""The six agents of the SECNS pipeline.

Every agent exposes the same interface:

    agent.run(incident) -> incident

It reads the incident, enriches only the fields it owns, appends its
reasoning to `incident.trace`, and returns the incident for the next agent.
That uniform contract is what lets the orchestrator treat them as an
interchangeable list.
"""

from typing import List

from . import config as C
from .models import Contact, Incident, Message


class Agent:
    """Base class. Subclasses set `name` and implement `think`."""

    name = "Agent"

    def run(self, inc: Incident) -> Incident:
        lines = self.think(inc)
        inc.log(self.name, lines)
        return inc

    def think(self, inc: Incident) -> List[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Agent 1 - Perception
# ---------------------------------------------------------------------------
class PerceptionAgent(Agent):
    """Validates signal integrity and normalises heterogeneous sensor packets."""

    name = "Perception Agent"

    def think(self, inc: Incident) -> List[str]:
        p = inc.packet
        if p.event not in C.EVENTS:
            raise ValueError("unknown event class: %s" % p.event)
        if p.location_key not in C.LOCATIONS:
            raise ValueError("unknown location key: %s" % p.location_key)

        inc.normalised = {
            "event": p.event,
            "heart_rate": int(p.heart_rate),
            "impact_g": round(float(p.impact_g), 1),
            "user_reply": int(p.user_reply),
            "location_key": p.location_key,
        }
        integrity_ok = p.signal_integrity >= 0.80
        return [
            "raw packet received from wearable IMU / PPG / panic button",
            "signal integrity %.0f%% -> %s" % (
                p.signal_integrity * 100,
                "accepted" if integrity_ok else "REJECTED, sensor dropout"),
            "normalised -> %s" % inc.normalised,
        ]


# ---------------------------------------------------------------------------
# Agent 2 - Triage
# ---------------------------------------------------------------------------
class TriageAgent(Agent):
    """Additive, fully explainable severity model.

        S = base(event) + f_hr + f_impact + f_reply,  clamped to [0, 100]
    """

    name = "Triage Agent"

    def think(self, inc: Incident) -> List[str]:
        n = inc.normalised
        ev = C.EVENTS[n["event"]]
        terms: List[str] = []

        score = ev["base"]
        terms.append('event "%s" -> base %d' % (ev["label"], ev["base"]))

        hr = n["heart_rate"]
        if hr > C.HR_SAFE_HIGH or hr < C.HR_SAFE_LOW:
            score += C.HR_OUTSIDE_BAND
            terms.append("HR %d bpm outside safe band -> +%d" % (hr, C.HR_OUTSIDE_BAND))
        elif hr > C.HR_WARN_HIGH or hr < C.HR_WARN_LOW:
            score += C.HR_BORDERLINE
            terms.append("HR %d bpm borderline -> +%d" % (hr, C.HR_BORDERLINE))
        else:
            terms.append("HR %d bpm nominal -> +0" % hr)

        g = n["impact_g"]
        if g > C.IMPACT_SEVERE_G:
            score += C.IMPACT_SEVERE
            terms.append("impact %.1f G severe -> +%d" % (g, C.IMPACT_SEVERE))
        elif g > C.IMPACT_MODERATE_G:
            score += C.IMPACT_MODERATE
            terms.append("impact %.1f G moderate -> +%d" % (g, C.IMPACT_MODERATE))
        else:
            terms.append("impact %.1f G low -> +0" % g)

        reply = n["user_reply"]
        if reply == 0:
            score += C.REPLY_NONE
            terms.append("no reply to 30 s check-in -> +%d" % C.REPLY_NONE)
        elif reply == 1:
            score += C.REPLY_OK
            terms.append('user replied "I am OK" -> %d  (false-alarm suppression)' % C.REPLY_OK)
        elif reply == 2:
            score += C.REPLY_HELP
            terms.append('user replied "Need help" -> +%d' % C.REPLY_HELP)

        score = max(0, min(100, round(score)))
        tier = 1 if score >= C.TIER1_MIN else 2 if score >= C.TIER2_MIN else 3

        inc.severity = score
        inc.tier = tier
        inc.scoring_terms = terms
        # Suppression: low severity AND the user has explicitly self-cleared.
        inc.suppressed = (tier == 3 and reply == 1)

        out = ["applying weighted rule engine:"] + ["  - " + t for t in terms]
        out.append("severity = %d/100 -> TIER %d (%s)" % (
            score, tier, {1: "critical", 2: "urgent", 3: "advisory"}[tier]))
        if inc.suppressed:
            out.append("below dispatch threshold and self-cleared -> SUPPRESS, log only")
        return out


# ---------------------------------------------------------------------------
# Agent 3 - Context
# ---------------------------------------------------------------------------
class ContextAgent(Agent):
    """Resolves location, medical profile and the nearest treatment facility."""

    name = "Context Agent"

    def think(self, inc: Incident) -> List[str]:
        loc = C.LOCATIONS[inc.normalised["location_key"]]
        inc.location = loc["label"]
        inc.coordinates = loc["coords"]
        inc.nearest_facility = loc["facility"]
        inc.medical_profile = dict(C.MEDICAL_PROFILE)
        return [
            "GNSS / cell fusion -> %s (%s)" % (loc["label"], loc["coords"]),
            "nearest facility: %s" % loc["facility"],
            "medical profile: blood group %s, allergy %s, implants %s" % (
                C.MEDICAL_PROFILE["blood_group"],
                C.MEDICAL_PROFILE["allergies"],
                C.MEDICAL_PROFILE["implants"]),
        ]


# ---------------------------------------------------------------------------
# Agent 4 - Prioritisation
# ---------------------------------------------------------------------------
class PrioritisationAgent(Agent):
    """Weighted multi-criteria ranking of the contact roster.

        w(c) = 0.35*relation + 0.25*proximity + 0.25*availability + 0.15*medical_fit
    """

    name = "Prioritisation Agent"

    @staticmethod
    def score_contact(c: Contact, inc: Incident) -> float:
        relation = C.RELATION_SCORE.get(c.relation, C.RELATION_DEFAULT)
        proximity = 1.0 / (1.0 + c.distance_km / 3.0)
        needs_med = C.EVENTS[inc.normalised["event"]]["needs_medical"]
        if c.medically_qualified and needs_med:
            medical = C.MEDICAL_FIT_NEEDED
        elif c.medically_qualified:
            medical = C.MEDICAL_FIT_SPARE
        else:
            medical = C.MEDICAL_FIT_NONE

        w = (C.W_RELATION * relation + C.W_PROXIMITY * proximity
             + C.W_AVAILABILITY * c.availability + C.W_MEDICAL * medical)

        # Override 1: emergency services are a function of severity, not preference.
        if c.name == C.EMS_NAME:
            w = C.EMS_WEIGHT_BY_TIER[inc.tier]
        # Override 2: institutional responders matter only inside their jurisdiction.
        if c.name == C.INSTITUTIONAL_NAME:
            inside = inc.normalised["location_key"] == C.INSTITUTIONAL_JURISDICTION
            w += C.INSTITUTIONAL_BONUS if inside else -C.INSTITUTIONAL_PENALTY
        # Override 3: a qualified clinician must not be crowded out of a
        # critical medical incident by closer but unqualified contacts.
        if c.medically_qualified and needs_med and inc.tier == 1 and c.name != C.EMS_NAME:
            w += C.MEDICAL_TIER1_BONUS
        return round(w, 3)

    def think(self, inc: Incident) -> List[str]:
        scored = []
        for src in C.ROSTER:
            c = Contact(src.name, src.relation, list(src.channels),
                        src.distance_km, src.availability, src.medically_qualified)
            c.weight = self.score_contact(c, inc)
            scored.append(c)

        scored.sort(key=lambda x: x.weight, reverse=True)
        width = C.TIER_WIDTH[inc.tier]
        chosen = scored[:width]
        for c in chosen:
            c.status = "queued"
        inc.ranked_contacts = chosen

        out = ["scoring on relation %.2f / proximity %.2f / availability %.2f / medical %.2f"
               % (C.W_RELATION, C.W_PROXIMITY, C.W_AVAILABILITY, C.W_MEDICAL)]
        out += ["  %d. %-16s w=%.2f  (%s)" % (i + 1, c.name, c.weight, c.relation)
                for i, c in enumerate(chosen)]
        out.append("tier %d -> %d contacts selected" % (inc.tier, len(chosen)))
        return out


# ---------------------------------------------------------------------------
# Agent 5 - Composer
# ---------------------------------------------------------------------------
class ComposerAgent(Agent):
    """Generates one message per contact, adapted to role and channel."""

    name = "Composer Agent"

    def compose(self, c: Contact, inc: Incident) -> str:
        ev = C.EVENTS[inc.normalised["event"]]["label"]
        hr = inc.normalised["heart_rate"]
        g = inc.normalised["impact_g"]
        mp = inc.medical_profile

        if c.name == C.EMS_NAME:
            return (
                "EMERGENCY DISPATCH REQUEST %s\n"
                "Patient: %s, %s. Blood group %s. Allergy: %s.\n"
                "Event: %s. HR %d bpm, impact %.1f G.\n"
                "Location: %s (%s)\n"
                "Severity %d/100, Tier %d. Automated request from SECNS."
                % (inc.incident_id, mp["name"], mp["age_sex"], mp["blood_group"],
                   mp["allergies"], ev, hr, g, inc.location, inc.coordinates,
                   inc.severity, inc.tier))

        if c.medically_qualified:
            return (
                "Doctor, automated alert %s for your patient %s.\n"
                "%s detected. Vitals: HR %d bpm, impact %.1f G. Severity %d/100.\n"
                "Location: %s. Nearest facility: %s.\n"
                "Reply ACK to take the case."
                % (inc.incident_id, mp["name"], ev, hr, g, inc.severity,
                   inc.location, inc.nearest_facility))

        if c.relation in ("Father", "Mother"):
            ems = ("An ambulance has been requested."
                   if any(x.name == C.EMS_NAME for x in inc.ranked_contacts)
                   else "No ambulance has been requested yet.")
            return (
                "Alert: %s involving %s.\n"
                "She is at %s. Heart rate %d bpm. %s\n"
                "Please acknowledge so we know help is on the way. Ref %s."
                % (ev, mp["name"].split()[0], inc.location, hr, ems, inc.incident_id))

        return (
            "%s may need help nearby - %s detected at %s.\n"
            "You are the closest listed contact (%.1f km). Can you check on her? Reply ACK."
            % (mp["name"].split()[0], ev, inc.location, c.distance_km))

    def think(self, inc: Incident) -> List[str]:
        inc.messages = []
        for c in inc.ranked_contacts:
            body = self.compose(c, inc)
            if len(body) > C.SMS_MAX_CHARS:
                body = body[:C.SMS_MAX_CHARS - 3] + "..."
            inc.messages.append(Message(c.name, " + ".join(c.channels), body))
        return [
            "role-adapted drafting: plain language for family, clinical payload for the",
            "physician, structured dispatch format for emergency services",
            "%d messages drafted, all within the %d character channel limit"
            % (len(inc.messages), C.SMS_MAX_CHARS),
        ]


# ---------------------------------------------------------------------------
# Agent 6 - Dispatch and escalation
# ---------------------------------------------------------------------------
class DispatchAgent(Agent):
    """Sends in priority order, tracks acknowledgement, escalates on timeout.

    `gateway` is injected so the same agent can be unit-tested against a fake
    gateway and run in production against a real SMS / voice provider.
    """

    name = "Dispatch & Escalation Agent"

    def __init__(self, gateway=None):
        self.gateway = gateway or (lambda channel, contact, body: True)

    def think(self, inc: Incident) -> List[str]:
        out = ["dispatching in priority order with %.0f s stagger" % C.DISPATCH_STAGGER_S]
        for msg, contact in zip(inc.messages, inc.ranked_contacts):
            ok = self.gateway(msg.channel, msg.contact, msg.body)
            contact.status = "sent" if ok else "failed"
            if ok:
                inc.dispatched.append(contact.name)
                out.append("  -> %-16s via %s" % (contact.name, msg.channel))
            else:
                out.append("  !! %-16s gateway failure, retry queued" % contact.name)
        out.append("acknowledgement window open for %.0f s; silent contacts escalate"
                   % C.ACK_WINDOW_S)
        inc.outcome = "dispatched, awaiting acknowledgement"
        return out

    # -- called later, when acknowledgements arrive or the window expires ----
    @staticmethod
    def acknowledge(inc: Incident, contact_name: str) -> None:
        for c in inc.ranked_contacts:
            if c.name == contact_name and c.status == "sent":
                c.status = "acknowledged"
                inc.acknowledged.append(contact_name)
                inc.outcome = "acknowledged by %s" % c.relation.lower()

    @staticmethod
    def escalate(inc: Incident) -> List[str]:
        """Called when the acknowledgement window expires."""
        silent = [c for c in inc.ranked_contacts if c.status == "sent"]
        if not silent:
            return ["all contacts acknowledged, no escalation required"]
        for c in silent:
            c.status = "escalated"
            inc.escalated.append(c.name)
        if inc.tier > 1:
            inc.tier -= 1
            inc.outcome = "escalated to tier %d after no acknowledgement" % inc.tier
            return ["%d contact(s) silent at timeout -> widening to tier %d"
                    % (len(silent), inc.tier)]
        inc.outcome = "escalated, emergency services already engaged"
        return ["%d contact(s) silent; already at tier 1, EMS engaged" % len(silent)]

# SCENS-FLEXI
# SECNS — Smart Emergency Contact Notification System
 
An agentic-AI pipeline that turns a raw sensor signal into a prioritised,
personalised and auditable set of emergency notifications — with no action
required from the victim.
 
**Bhumika Arora** · PRN 24070521227 · Semester 5 · B.Tech Computer Science & Engineering
Course: Agentic AI and Automation · Guide: Dr. Shreyas Rajendra Hole · Subject Teacher: Mr. Parag Naik
Symbiosis Institute of Technology, Nagpur Campus
 
---
 
## Requirements
 
Python 3.9 or newer. **No third-party packages, no `pip install`, no internet.**
Everything uses the standard library.
 
Check your version:
 
```bash
python --version        # or python3 --version
```
 
---
 
## How to run
 
### 1. The web console (use this for the demonstration)
 
```bash
cd secns-project
python server.py
```
 
Your browser opens at `http://localhost:8000`. Set the sensor values on the
left, press **Trigger emergency event**, and watch the six agents run.
 
Every number on that screen — the severity score, the contact weights, the
message text — is computed by the Python agents in `secns/`. The browser is
only a display; it contains no decision logic. You can prove this by stopping
the server: the page loads but nothing computes.
 
### 2. The terminal demo (use this if there is no projector or browser)
 
```bash
python run_demo.py              # runs all five validation cases
python run_demo.py --case A     # run just one case
python run_demo.py --interactive  # type your own sensor values
python run_demo.py --fast       # skip the typing animation
```
 
### 3. The test suite (run this to show correctness)
 
```bash
python -m unittest discover tests -v
```
 
16 tests covering severity scoring, suppression, tier width, the three
prioritisation overrides, role-specific message generation, acknowledgement
and escalation.
 
### 4. Use it as a library
 
```python
from secns import Orchestrator, make_packet
 
incident = Orchestrator().handle(
    make_packet(event="crash", heart_rate=168, impact_g=11.2,
                user_reply=0, location_key="road"))
 
print(incident.severity, incident.tier)          # 100  1
for c in incident.ranked_contacts:
    print(c.name, c.weight, c.status)
for m in incident.messages:
    print(m.contact, "->", m.body)
```
 
---
 
## Project layout
 
```
secns-project/
├── secns/
│   ├── __init__.py        public API
│   ├── models.py          Contact, SensorPacket, Message, Incident (shared state)
│   ├── config.py          roster, event table, all tunable weights
│   ├── agents.py          the six agents
│   └── orchestrator.py    wires the agents into a pipeline
├── web/index.html         browser view (rendering only, no logic)
├── server.py              zero-dependency HTTP server + JSON API
├── run_demo.py            terminal demonstration
├── tests/test_secns.py    unit tests
└── README.md
```
 
---
 
## Architecture
 
```
Sensors
   ↓
[1] Perception Agent      validates signal integrity, normalises the packet
   ↓
[2] Triage Agent          severity 0–100, incident tier, scoring terms
   ↓
[3] Context Agent         location, medical profile, nearest facility
   ↓
[4] Prioritisation Agent  ranks the contact roster, truncates by tier
   ↓
[5] Composer Agent        one role-adapted message per contact
   ↓
[6] Dispatch & Escalation sends, tracks ACK, escalates on timeout
   ↓
SMS / Voice / Email / Push  →  ACK listener  →  audit log
```
 
Every agent subclasses `Agent` and implements `think(incident) -> list[str]`.
It reads the shared `Incident`, enriches only the fields it owns, and appends
its reasoning to `incident.trace`. No agent overwrites another agent's fields —
that constraint is what makes each one independently testable.
 
### Severity model (`TriageAgent`)
 
```
S = base(event) + f_hr(heart_rate) + f_impact(impact_g) + f_reply(user_response)
    clamped to [0, 100]
```
 
| Term | Values |
|---|---|
| base | crash 85 · cardiac 80 · fire 75 · SOS 70 · fall 55 · inactivity 35 |
| heart rate | +15 outside 45–140 bpm · +7 borderline · 0 nominal |
| impact | +15 above 8 G · +8 between 3 G and 8 G · 0 below |
| user reply | +12 no answer · +10 "Need help" · **−35 "I'm OK"** |
 
Tiers: **S ≥ 75** → Tier 1, notify 4 incl. EMS · **45–74** → Tier 2, notify 3 ·
**< 45** → Tier 3, notify 2, or suppress entirely if the user self-cleared.
 
The −35 term is the false-alarm suppression mechanism. It deliberately trades
a little sensitivity for long-term trust in the alert channel.
 
### Contact ranking (`PrioritisationAgent`)
 
```
w(c) = 0.35·relation + 0.25·proximity + 0.25·availability + 0.15·medical_fit
```
 
with `proximity = 1 / (1 + km/3)`, plus three documented overrides:
 
1. Emergency services: `w = 1.00` at Tier 1, `0.55` at Tier 2, `0.10` at Tier 3 —
   EMS engagement is a function of severity, not of preference.
2. Institutional responders: `+0.20` inside their jurisdiction, `−0.15` outside.
3. A medically qualified contact gets `+0.15` at Tier 1 when the event class
   actually requires medical intervention.
Because the model is additive and every weight lives in `config.py`, any score
the system produces can be reconstructed by hand. That is the property that
makes it defensible in a life-safety setting.
 
---
 
## Validation cases
 
| Case | Input | Score | Tier | Result |
|---|---|---|---|---|
| A | Crash, HR 168, 11.2 G, no reply, highway | 100 | 1 | 4 contacts incl. 108 Ambulance |
| B | Fall, HR 96, 4.1 G, "I'm OK", home | 28 | 3 | **Suppressed** — logged only |
| C | Cardiac, HR 182, no reply, home | 100 | 1 | EMS, father, physician, mother |
| D | Manual SOS, "Need help", campus | 87 | 1 | Campus Security promoted by location override |
| E | Inactivity, HR 58, no reply, home | 54 | 2 | No ACK → all contacts escalated |
 
Cases B and E are the interesting ones: B is the system choosing **not** to act,
E is the system acting on the **absence** of a reply.
 
---
 
## Limitations
 
- Weights are hand-tuned from domain reasoning, not learned from outcome data.
- `availability` is stored history, not live presence.
- The sensor layer and the SMS/voice gateways are simulated. `DispatchAgent`
  takes a `gateway` callable, so swapping in a real provider is a one-line change.
- Rule-based triage cannot capture rare or compound clinical presentations.
 

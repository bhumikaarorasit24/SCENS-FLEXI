"""All tunable knowledge of the system lives here.

Keeping the weights in one file (rather than scattered through the agents)
is what makes the system auditable: a reviewer can read this file and then
reconstruct any severity score or contact ranking by hand.
"""

from .models import Contact

# --------------------------------------------------------------------------
# Emergency contact roster
# --------------------------------------------------------------------------
ROSTER = [
    Contact("Rajesh Arora",    "Father",            ["Call", "SMS"],   2.1, 0.95),
    Contact("Sunita Arora",    "Mother",            ["Call", "SMS"],   2.1, 0.90),
    Contact("Dr. M. Kulkarni", "Family physician",  ["SMS", "Email"],  5.4, 0.70, True),
    Contact("Aditi Sharma",    "Roommate",          ["SMS"],           0.3, 0.60),
    Contact("108 Ambulance",   "Emergency service", ["Call"],          3.8, 1.00, True),
    Contact("Campus Security", "Institutional",     ["SMS"],           1.2, 0.85),
]

MEDICAL_PROFILE = {
    "name": "Bhumika Arora",
    "age_sex": "20 F",
    "blood_group": "B+",
    "allergies": "Penicillin",
    "implants": "None",
    "conditions": "None recorded",
}

# --------------------------------------------------------------------------
# Agent 2 - Triage: base severity by event class
# --------------------------------------------------------------------------
EVENTS = {
    "crash":    {"label": "Vehicle crash",        "base": 85, "needs_medical": True},
    "cardiac":  {"label": "Cardiac anomaly",      "base": 80, "needs_medical": True},
    "fire":     {"label": "Smoke / fire",         "base": 75, "needs_medical": False},
    "sos":      {"label": "Manual SOS",           "base": 70, "needs_medical": False},
    "fall":     {"label": "Fall detected",        "base": 55, "needs_medical": True},
    "inactive": {"label": "Prolonged inactivity", "base": 35, "needs_medical": False},
}

# Modifier weights
HR_SAFE_HIGH, HR_SAFE_LOW = 140, 45
HR_WARN_HIGH, HR_WARN_LOW = 120, 55
HR_OUTSIDE_BAND, HR_BORDERLINE = 15, 7

IMPACT_SEVERE_G, IMPACT_MODERATE_G = 8.0, 3.0
IMPACT_SEVERE, IMPACT_MODERATE = 15, 8

REPLY_NONE, REPLY_OK, REPLY_HELP = 12, -35, 10

# Tier thresholds and how many contacts each tier notifies
TIER1_MIN, TIER2_MIN = 75, 45
TIER_WIDTH = {1: 4, 2: 3, 3: 2}

# --------------------------------------------------------------------------
# Agent 4 - Prioritisation weights
# --------------------------------------------------------------------------
W_RELATION, W_PROXIMITY, W_AVAILABILITY, W_MEDICAL = 0.35, 0.25, 0.25, 0.15

RELATION_SCORE = {"Father": 1.0, "Mother": 1.0, "Roommate": 0.75}
RELATION_DEFAULT = 0.6

MEDICAL_FIT_NEEDED, MEDICAL_FIT_SPARE, MEDICAL_FIT_NONE = 0.9, 0.4, 0.2

EMS_NAME = "108 Ambulance"
EMS_WEIGHT_BY_TIER = {1: 1.00, 2: 0.55, 3: 0.10}

INSTITUTIONAL_NAME = "Campus Security"
INSTITUTIONAL_JURISDICTION = "campus"
INSTITUTIONAL_BONUS, INSTITUTIONAL_PENALTY = 0.20, 0.15

# Override 3: at Tier 1 a medically qualified contact is pulled up the queue
# when the event class actually requires medical intervention.
MEDICAL_TIER1_BONUS = 0.15

# --------------------------------------------------------------------------
# Agent 3 - Context: known locations
# --------------------------------------------------------------------------
LOCATIONS = {
    "home":    {"label": "Home, Rajapeth, Amravati",
                "coords": "20.932 N, 77.780 E",
                "facility": "Dr. Panjabrao Deshmukh Hospital - 3.1 km"},
    "road":    {"label": "NH-53, near Badnera bypass, Amravati",
                "coords": "20.855 N, 77.744 E",
                "facility": "Amravati Civil Hospital - 8.7 km"},
    "campus":  {"label": "SIT Nagpur Campus",
                "coords": "21.096 N, 79.017 E",
                "facility": "AIIMS Nagpur - 6.2 km"},
    "unknown": {"label": "Cell-tower estimate, +/- 850 m, Amravati",
                "coords": "approximate",
                "facility": "Nearest PHC - approx. 4 km"},
}

# --------------------------------------------------------------------------
# Agent 6 - Dispatch
# --------------------------------------------------------------------------
DISPATCH_STAGGER_S = 2.0     # gap between outgoing messages, avoids throttling
ACK_WINDOW_S = 60.0          # time allowed before escalation
SMS_MAX_CHARS = 480

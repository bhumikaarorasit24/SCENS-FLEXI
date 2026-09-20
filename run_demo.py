#!/usr/bin/env python3
"""Terminal demonstration of SECNS.

Usage:
    python run_demo.py              run all five validation cases
    python run_demo.py --case C     run one case (A-E)
    python run_demo.py --interactive  enter your own sensor values
"""

import argparse
import sys
import time

from secns import Orchestrator, make_packet
from secns.agents import DispatchAgent
from secns.config import EVENTS, LOCATIONS

# ANSI colours, disabled automatically when output is piped to a file
_tty = sys.stdout.isatty()
def c(code, s):
    return "\033[%sm%s\033[0m" % (code, s) if _tty else s

BOLD, RED, GREEN, YELLOW, CYAN, GREY = "1", "31", "32", "33", "36", "90"

CASES = {
    "A": ("Vehicle crash on the highway, no response",
          dict(event="crash", heart_rate=168, impact_g=11.2, user_reply=0, location_key="road")),
    "B": ("Fall at home, user says 'I am OK'  -> suppression path",
          dict(event="fall", heart_rate=96, impact_g=4.1, user_reply=1, location_key="home")),
    "C": ("Cardiac anomaly at home, no response",
          dict(event="cardiac", heart_rate=182, impact_g=0.2, user_reply=0, location_key="home")),
    "D": ("Manual SOS on campus, user says 'Need help'",
          dict(event="sos", heart_rate=112, impact_g=0.0, user_reply=2, location_key="campus")),
    "E": ("Prolonged inactivity at home -> escalation path",
          dict(event="inactive", heart_rate=58, impact_g=0.0, user_reply=0, location_key="home")),
}


def gateway(channel, contact, body):
    """Stub gateway. Replace with a real SMS / voice provider in production."""
    return True


def show(inc, delay):
    print()
    print(c(BOLD, "=" * 78))
    print(c(BOLD, " %s   severity %d/100   TIER %d" % (inc.incident_id, inc.severity, inc.tier)))
    print(c(BOLD, "=" * 78))

    for step in inc.trace:
        print()
        print(c(CYAN, "[%s] %s" % (step["at"], step["agent"])))
        for line in step["lines"]:
            print("    " + c(GREY, line))
            time.sleep(delay)

    if inc.suppressed:
        print()
        print(c(YELLOW, ">> SUPPRESSED - no notification sent. %s" % inc.outcome))
        return

    print()
    print(c(BOLD, "-- contact priority queue " + "-" * 52))
    for i, ct in enumerate(inc.ranked_contacts, 1):
        print("  %d. %-16s w=%.2f  %-18s %-13s %s"
              % (i, ct.name, ct.weight, ct.relation,
                 "/".join(ct.channels), c(YELLOW, ct.status)))

    print()
    print(c(BOLD, "-- dispatched messages " + "-" * 54))
    for m in inc.messages:
        print()
        print(c(GREEN, "  to %s  via %s" % (m.contact, m.channel)))
        for line in m.body.split("\n"):
            print("     " + line)


def main():
    ap = argparse.ArgumentParser(description="SECNS terminal demonstration")
    ap.add_argument("--case", choices=sorted(CASES), help="run a single case")
    ap.add_argument("--interactive", action="store_true", help="enter your own values")
    ap.add_argument("--fast", action="store_true", help="no typing delay")
    args = ap.parse_args()

    delay = 0.0 if args.fast else 0.06
    orch = Orchestrator(gateway=gateway)

    if args.interactive:
        print("event classes:", ", ".join(EVENTS))
        event = input("event            : ").strip() or "fall"
        hr = int(input("heart rate (bpm) : ") or 120)
        g = float(input("impact (G)       : ") or 0)
        print("reply  0 = no answer, 1 = I am OK, 2 = Need help")
        reply = int(input("user reply       : ") or 0)
        print("locations:", ", ".join(LOCATIONS))
        loc = input("location         : ").strip() or "home"
        inc = orch.handle(make_packet(event, hr, g, reply, loc))
        show(inc, delay)
        return

    cases = [args.case] if args.case else sorted(CASES)
    for key in cases:
        title, kw = CASES[key]
        print()
        print(c(BOLD, "### CASE %s - %s" % (key, title)))
        inc = orch.handle(make_packet(**kw))
        show(inc, delay)

        # Case E demonstrates the escalation path: nobody acknowledges.
        if key == "E":
            print()
            print(c(RED, ">> acknowledgement window expired"))
            for line in DispatchAgent.escalate(inc):
                print("    " + c(RED, line))
            for ct in inc.ranked_contacts:
                print("    %-16s -> %s" % (ct.name, ct.status))
        # Case A demonstrates a normal acknowledgement.
        if key == "A":
            DispatchAgent.acknowledge(inc, inc.ranked_contacts[1].name)
            print()
            print(c(GREEN, ">> %s acknowledged. outcome: %s"
                    % (inc.ranked_contacts[1].name, inc.outcome)))

    print()


if __name__ == "__main__":
    main()

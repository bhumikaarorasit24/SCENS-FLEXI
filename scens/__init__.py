"""SECNS - Smart Emergency Contact Notification System.

An agentic-AI pipeline that turns a raw sensor signal into a prioritised,
personalised and auditable set of emergency notifications.

Author : Bhumika Arora (PRN 24070521227), Semester 5, B.Tech CSE
Course : Agentic AI and Automation
Guide  : Dr. Shreyas Rajendra Hole   |   Subject Teacher: Mr. Parag Naik
"""

from .models import Contact, Incident, Message, SensorPacket
from .orchestrator import Orchestrator, make_packet

__version__ = "1.0.0"
__all__ = ["Contact", "Incident", "Message", "SensorPacket",
           "Orchestrator", "make_packet"]

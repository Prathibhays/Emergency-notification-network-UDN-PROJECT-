"""Traffic classification rules for the SDN emergency controller.

Kept free of Ryu imports so it can be unit-tested on any machine.
Port numbers match common/protocol.py from the UDP application (Person 1).
"""

from dataclasses import dataclass
from typing import Optional

# UDP ports used by the notification application
EMERGENCY_PORT = 9999
NORMAL_PORT = 5000
CONTROL_PORT = 5001  # registration + delivery ACKs

# OVS queue IDs (configured by Person 3 on the switch ports)
HIGH_PRIORITY_QUEUE = 1
DEFAULT_QUEUE = 0

# DSCP Expedited Forwarding, marks emergency packets for downstream QoS
DSCP_EF = 46


@dataclass(frozen=True)
class TrafficClass:
    name: str               # label shown in logs
    flow_priority: int      # OpenFlow flow-rule priority
    level: str              # human readable priority level
    queue_id: Optional[int]  # OVS queue to enqueue on (None = don't set)
    dscp: Optional[int] = None  # DSCP value to mark (None = leave unchanged)


EMERGENCY = TrafficClass("EMERGENCY", 100, "HIGH", HIGH_PRIORITY_QUEUE, DSCP_EF)
CONTROL = TrafficClass("CONTROL", 50, "MEDIUM", HIGH_PRIORITY_QUEUE)
NORMAL = TrafficClass("NORMAL", 10, "NORMAL", DEFAULT_QUEUE)
BACKGROUND = TrafficClass("BACKGROUND", 5, "LOW", DEFAULT_QUEUE)  # other UDP, e.g. iperf
OTHER = TrafficClass("OTHER", 1, "LOW", None)  # non-UDP IP traffic (ICMP, TCP)

ALL_CLASSES = (EMERGENCY, CONTROL, NORMAL, BACKGROUND, OTHER)


def classify_udp(src_port: int, dst_port: int) -> TrafficClass:
    """Classify a UDP packet by its ports."""
    if dst_port == EMERGENCY_PORT:
        return EMERGENCY
    if dst_port == CONTROL_PORT or src_port == CONTROL_PORT:
        # ACKs go to the server's control port; registration replies come from it
        return CONTROL
    if dst_port == NORMAL_PORT:
        return NORMAL
    return BACKGROUND


def class_for_priority(priority: int) -> Optional[TrafficClass]:
    """Map an installed flow's priority back to its traffic class (for stats)."""
    for traffic_class in ALL_CLASSES:
        if traffic_class.flow_priority == priority:
            return traffic_class
    return None

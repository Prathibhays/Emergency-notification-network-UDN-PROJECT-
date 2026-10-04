"""Ryu SDN controller for the UDP emergency notification network.

Person 2 component:
- Detects switches and installs a table-miss rule
- Learns MAC addresses and forwards packets (L2 learning switch)
- Detects UDP traffic and inspects the destination port
- Classifies UDP/9999 as EMERGENCY, UDP/5000 as NORMAL, UDP/5001 as CONTROL
- Installs per-flow OpenFlow rules with emergency at a higher priority
- Puts emergency traffic on the high-priority OVS queue and marks it DSCP EF
- Periodically logs flow statistics per traffic class

Run:
    ryu-manager controller/emergency_controller.py
"""

import csv
import os
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from ryu.lib import hub
from ryu.lib.packet import ether_types, ethernet, in_proto, ipv4, packet, udp
from ryu.ofproto import ofproto_v1_3

from traffic_classifier import ALL_CLASSES, OTHER, class_for_priority, classify_udp

# Seconds a per-flow rule stays installed without matching packets
FLOW_IDLE_TIMEOUT = 30
# Seconds between flow statistics requests (0 disables the monitor)
STATS_INTERVAL = 10

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"
)
STATS_CSV = os.path.join(RESULTS_DIR, "sdn_flow_stats.csv")


class EmergencyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}  # dpid -> {mac: port}
        self.datapaths = {}  # dpid -> datapath
        self.packet_counts = {c.name: 0 for c in ALL_CLASSES}

        if STATS_INTERVAL > 0:
            self._prepare_stats_csv()
            self.monitor_thread = hub.spawn(self._monitor)

        self.logger.info("=" * 58)
        self.logger.info("SDN EMERGENCY CONTROLLER STARTED")
        self.logger.info("=" * 58)
        for c in ALL_CLASSES:
            self.logger.info(
                "  %-10s flow priority %-3d level %-6s queue %s",
                c.name, c.flow_priority, c.level,
                "-" if c.queue_id is None else c.queue_id,
            )

    # ------------------------------------------------------------------
    # Switch connection
    # ------------------------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info("[SDN] Switch connected: dpid=%016x", datapath.id)

        # Table-miss: send unknown packets to the controller
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("[SDN] Table-miss flow installed on dpid=%016x", datapath.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER and datapath.id in self.datapaths:
            self.logger.info("[SDN] Switch disconnected: dpid=%016x", datapath.id)
            del self.datapaths[datapath.id]
            self.mac_to_port.pop(datapath.id, None)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
        )
        datapath.send_msg(mod)

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        out_port = self.mac_to_port[dpid].get(eth.dst, ofproto.OFPP_FLOOD)

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        udp_pkt = pkt.get_protocol(udp.udp)

        if ip_pkt is not None and udp_pkt is not None:
            traffic_class = classify_udp(udp_pkt.src_port, udp_pkt.dst_port)
            self._log_udp(dpid, in_port, ip_pkt, udp_pkt, traffic_class)
            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=ether_types.ETH_TYPE_IP,
                ip_proto=in_proto.IPPROTO_UDP,
                ipv4_src=ip_pkt.src,
                ipv4_dst=ip_pkt.dst,
                udp_src=udp_pkt.src_port,
                udp_dst=udp_pkt.dst_port,
            )
        elif ip_pkt is not None:
            # Non-UDP IPv4 (ICMP, TCP): plain forwarding, matched per protocol
            # so it never shadows a UDP flow that still needs classifying.
            traffic_class = OTHER
            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=ether_types.ETH_TYPE_IP,
                ip_proto=ip_pkt.proto,
                ipv4_src=ip_pkt.src,
                ipv4_dst=ip_pkt.dst,
            )
        else:
            # ARP, IPv6, etc.: forward without installing a flow
            traffic_class = OTHER
            match = None

        self.packet_counts[traffic_class.name] += 1
        actions = self._build_actions(parser, traffic_class, out_port)

        if match is not None and out_port != ofproto.OFPP_FLOOD:
            self.add_flow(
                datapath, traffic_class.flow_priority, match, actions,
                idle_timeout=FLOW_IDLE_TIMEOUT,
            )
            if traffic_class is not OTHER:
                self.logger.info(
                    "[SDN] Flow installed: dpid=%016x priority=%d queue=%s out_port=%s",
                    dpid, traffic_class.flow_priority, traffic_class.queue_id, out_port,
                )

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    def _build_actions(self, parser, traffic_class, out_port):
        actions = []
        if traffic_class.queue_id is not None:
            actions.append(parser.OFPActionSetQueue(traffic_class.queue_id))
        if traffic_class.dscp is not None:
            actions.append(parser.OFPActionSetField(ip_dscp=traffic_class.dscp))
        actions.append(parser.OFPActionOutput(out_port))
        return actions

    def _log_udp(self, dpid, in_port, ip_pkt, udp_pkt, traffic_class):
        self.logger.info("")
        self.logger.info("[SDN] Packet received (dpid=%016x, in_port=%s)", dpid, in_port)
        self.logger.info("[SDN] UDP packet detected: %s:%s -> %s:%s",
                         ip_pkt.src, udp_pkt.src_port, ip_pkt.dst, udp_pkt.dst_port)
        self.logger.info("[SDN] Protocol: UDP")
        self.logger.info("[SDN] Destination port: %s", udp_pkt.dst_port)
        self.logger.info("[SDN] Classification: %s", traffic_class.name)
        self.logger.info("[SDN] Type: %s", traffic_class.name)
        self.logger.info("[SDN] Priority: %s (flow priority %d)",
                         traffic_class.level, traffic_class.flow_priority)

    # ------------------------------------------------------------------
    # Flow statistics monitor
    # ------------------------------------------------------------------

    def _prepare_stats_csv(self):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        if os.path.exists(STATS_CSV) and os.path.getsize(STATS_CSV) > 0:
            return
        with open(STATS_CSV, "w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(
                ["timestamp", "dpid", "class", "flow_priority", "flows", "packets", "bytes"]
            )

    def _monitor(self):
        while True:
            for datapath in list(self.datapaths.values()):
                parser = datapath.ofproto_parser
                datapath.send_msg(parser.OFPFlowStatsRequest(datapath))
            hub.sleep(STATS_INTERVAL)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        totals = {}  # class name -> [flows, packets, bytes]

        for stat in ev.msg.body:
            traffic_class = class_for_priority(stat.priority)
            if traffic_class is None or traffic_class is OTHER:
                continue
            entry = totals.setdefault(traffic_class.name, [0, 0, 0])
            entry[0] += 1
            entry[1] += stat.packet_count
            entry[2] += stat.byte_count

        if not totals:
            return

        now = time.time()
        rows = []
        self.logger.info("[SDN-STATS] dpid=%016x", dpid)
        for c in ALL_CLASSES:
            if c.name not in totals:
                continue
            flows, packets, nbytes = totals[c.name]
            self.logger.info(
                "[SDN-STATS]   %-10s priority=%-3d flows=%d packets=%d bytes=%d",
                c.name, c.flow_priority, flows, packets, nbytes,
            )
            rows.append([f"{now:.3f}", dpid, c.name, c.flow_priority, flows, packets, nbytes])

        with open(STATS_CSV, "a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerows(rows)

"""Offline tests for the SDN emergency controller (no Mininet needed).

Feeds simulated OpenFlow PacketIn messages into the controller and checks
the FlowMod / PacketOut messages it sends back.

Run from the project root:
    python -m unittest controller/test_emergency_controller.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import traffic_classifier as tc  # noqa: E402

try:
    from ryu.controller import ofp_event
    from ryu.lib.packet import arp, ethernet, ether_types, in_proto, ipv4, packet, tcp, udp
    from ryu.ofproto import ofproto_v1_3, ofproto_v1_3_parser

    import emergency_controller
    HAVE_RYU = True
except ImportError:
    HAVE_RYU = False

H1_MAC, H1_IP = "00:00:00:00:00:01", "10.0.0.1"  # server
H2_MAC, H2_IP = "00:00:00:00:00:02", "10.0.0.2"  # client
H3_MAC, H3_IP = "00:00:00:00:00:03", "10.0.0.3"  # client (never seen)


class ClassifierTest(unittest.TestCase):
    def test_emergency(self):
        self.assertIs(tc.classify_udp(40000, 9999), tc.EMERGENCY)

    def test_normal(self):
        self.assertIs(tc.classify_udp(40000, 5000), tc.NORMAL)

    def test_ack_and_registration(self):
        self.assertIs(tc.classify_udp(40000, 5001), tc.CONTROL)  # ACK / REGISTER
        self.assertIs(tc.classify_udp(5001, 40000), tc.CONTROL)  # REGISTERED reply

    def test_other_udp(self):
        self.assertIs(tc.classify_udp(40000, 5201), tc.BACKGROUND)

    def test_emergency_has_highest_priority(self):
        others = [c.flow_priority for c in tc.ALL_CLASSES if c is not tc.EMERGENCY]
        self.assertGreater(tc.EMERGENCY.flow_priority, max(others))
        self.assertGreater(tc.EMERGENCY.flow_priority, tc.NORMAL.flow_priority)


class FakeDatapath:
    def __init__(self, dpid=1):
        self.id = dpid
        self.ofproto = ofproto_v1_3
        self.ofproto_parser = ofproto_v1_3_parser
        self.sent = []

    def send_msg(self, msg):
        msg.serialize()  # fails loudly if the message is malformed
        self.sent.append(msg)


@unittest.skipUnless(HAVE_RYU, "Ryu is not installed")
class ControllerTest(unittest.TestCase):
    def setUp(self):
        emergency_controller.STATS_INTERVAL = 0
        self.app = emergency_controller.EmergencyController()
        self.dp = FakeDatapath()

    # helpers -----------------------------------------------------------

    def packet_in(self, in_port, *protocols):
        pkt = packet.Packet()
        for proto in protocols:
            pkt.add_protocol(proto)
        pkt.serialize()

        parser = self.dp.ofproto_parser
        msg = parser.OFPPacketIn(
            self.dp,
            buffer_id=ofproto_v1_3.OFP_NO_BUFFER,
            total_len=len(pkt.data),
            reason=ofproto_v1_3.OFPR_NO_MATCH,
            table_id=0,
            match=parser.OFPMatch(in_port=in_port),
            data=pkt.data,
        )
        self.dp.sent.clear()
        self.app.packet_in_handler(ofp_event.EventOFPPacketIn(msg))
        return self.dp.sent

    def learn_h2(self):
        """h2 answers ARP on port 2 so the switch learns its MAC."""
        self.packet_in(
            2,
            ethernet.ethernet(dst=H1_MAC, src=H2_MAC, ethertype=ether_types.ETH_TYPE_ARP),
            arp.arp(opcode=arp.ARP_REPLY, src_mac=H2_MAC, src_ip=H2_IP,
                    dst_mac=H1_MAC, dst_ip=H1_IP),
        )

    def udp_from_h1(self, dst_mac, dst_ip, src_port, dst_port):
        return self.packet_in(
            1,
            ethernet.ethernet(dst=dst_mac, src=H1_MAC, ethertype=ether_types.ETH_TYPE_IP),
            ipv4.ipv4(src=H1_IP, dst=dst_ip, proto=in_proto.IPPROTO_UDP),
            udp.udp(src_port=src_port, dst_port=dst_port),
            b"1|EMERGENCY|0.0|Fire detected",
        )

    def split(self, sent):
        parser = self.dp.ofproto_parser
        mods = [m for m in sent if isinstance(m, parser.OFPFlowMod)]
        outs = [m for m in sent if isinstance(m, parser.OFPPacketOut)]
        return mods, outs

    @staticmethod
    def describe(actions):
        out = []
        for a in actions:
            name = type(a).__name__
            if name == "OFPActionSetQueue":
                out.append(("queue", a.queue_id))
            elif name == "OFPActionSetField":
                out.append(("set", a.key, a.value))
            elif name == "OFPActionOutput":
                out.append(("output", a.port))
        return out

    # tests -------------------------------------------------------------

    def test_switch_connect_installs_table_miss(self):
        parser = self.dp.ofproto_parser
        features = parser.OFPSwitchFeatures(self.dp)
        self.app.switch_features_handler(ofp_event.EventOFPSwitchFeatures(features))

        (mod,) = self.dp.sent
        self.assertEqual(mod.priority, 0)
        actions = mod.instructions[0].actions
        self.assertEqual(actions[0].port, ofproto_v1_3.OFPP_CONTROLLER)

    def test_emergency_gets_high_priority_flow_and_queue(self):
        self.learn_h2()
        mods, outs = self.split(self.udp_from_h1(H2_MAC, H2_IP, 45000, 9999))

        self.assertEqual(len(mods), 1)
        mod = mods[0]
        self.assertEqual(mod.priority, 100)
        self.assertEqual(mod.match["udp_dst"], 9999)
        self.assertEqual(mod.match["ip_proto"], in_proto.IPPROTO_UDP)
        self.assertEqual(
            self.describe(mod.instructions[0].actions),
            [("queue", 1), ("set", "ip_dscp", 46), ("output", 2)],
        )
        # the first packet itself is also forwarded with the same treatment
        self.assertEqual(self.describe(outs[0].actions),
                         [("queue", 1), ("set", "ip_dscp", 46), ("output", 2)])

    def test_normal_gets_low_priority_flow(self):
        self.learn_h2()
        mods, _ = self.split(self.udp_from_h1(H2_MAC, H2_IP, 45000, 5000))

        self.assertEqual(mods[0].priority, 10)
        self.assertEqual(self.describe(mods[0].instructions[0].actions),
                         [("queue", 0), ("output", 2)])

    def test_emergency_priority_above_normal(self):
        self.learn_h2()
        emergency, _ = self.split(self.udp_from_h1(H2_MAC, H2_IP, 45000, 9999))
        normal, _ = self.split(self.udp_from_h1(H2_MAC, H2_IP, 45000, 5000))
        self.assertGreater(emergency[0].priority, normal[0].priority)

    def test_ack_to_server_is_control(self):
        self.packet_in(  # learn h1 on port 1
            1,
            ethernet.ethernet(dst=H2_MAC, src=H1_MAC, ethertype=ether_types.ETH_TYPE_ARP),
            arp.arp(src_mac=H1_MAC, src_ip=H1_IP, dst_ip=H2_IP),
        )
        sent = self.packet_in(
            2,
            ethernet.ethernet(dst=H1_MAC, src=H2_MAC, ethertype=ether_types.ETH_TYPE_IP),
            ipv4.ipv4(src=H2_IP, dst=H1_IP, proto=in_proto.IPPROTO_UDP),
            udp.udp(src_port=46000, dst_port=5001),
            b"ACK|1|client1",
        )
        mods, _ = self.split(sent)
        self.assertEqual(mods[0].priority, 50)
        self.assertEqual(self.describe(mods[0].instructions[0].actions),
                         [("queue", 1), ("output", 1)])

    def test_unknown_destination_floods_without_flow(self):
        mods, outs = self.split(self.udp_from_h1(H3_MAC, H3_IP, 45000, 9999))
        self.assertEqual(mods, [])
        self.assertEqual(self.describe(outs[0].actions)[-1],
                         ("output", ofproto_v1_3.OFPP_FLOOD))

    def test_tcp_does_not_shadow_udp(self):
        self.learn_h2()
        sent = self.packet_in(
            1,
            ethernet.ethernet(dst=H2_MAC, src=H1_MAC, ethertype=ether_types.ETH_TYPE_IP),
            ipv4.ipv4(src=H1_IP, dst=H2_IP, proto=in_proto.IPPROTO_TCP),
            tcp.tcp(src_port=45000, dst_port=80),
        )
        mods, _ = self.split(sent)
        self.assertEqual(mods[0].priority, 1)
        # TCP rule is pinned to ip_proto=TCP, so UDP still reaches the controller
        self.assertEqual(mods[0].match["ip_proto"], in_proto.IPPROTO_TCP)

    def test_flow_stats_grouped_by_class(self):
        parser = self.dp.ofproto_parser

        def stat(priority, packets):
            return parser.OFPFlowStats(priority=priority, packet_count=packets,
                                       byte_count=packets * 100, match=parser.OFPMatch(),
                                       instructions=[])

        reply = parser.OFPFlowStatsReply(self.dp)
        reply.body = [stat(100, 5), stat(100, 3), stat(10, 7), stat(0, 99)]

        with self.assertLogs(self.app.logger, level="INFO") as logs:
            self.app.flow_stats_reply_handler(ofp_event.EventOFPFlowStatsReply(reply))

        text = "\n".join(logs.output)
        self.assertIn("EMERGENCY  priority=100 flows=2 packets=8", text)
        self.assertIn("NORMAL     priority=10  flows=1 packets=7", text)


if __name__ == "__main__":
    unittest.main()

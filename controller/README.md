# Person 2 — SDN Controller (Ryu)

The controller makes the network recognise emergency UDP traffic and give it priority.

## Files

| File | Purpose |
|---|---|
| `emergency_controller.py` | Ryu app: switch handling, L2 forwarding, UDP classification, priority flows, queue mapping, flow stats |
| `traffic_classifier.py` | Port → traffic-class rules (no Ryu dependency) |
| `test_emergency_controller.py` | Offline tests using simulated OpenFlow messages |

## Classification

Ports match `common/protocol.py` from the UDP application.

| UDP port | Class | Flow priority | Level | OVS queue | DSCP |
|---|---|---|---|---|---|
| dst 9999 | EMERGENCY | 100 | HIGH | 1 | 46 (EF) |
| dst/src 5001 (register + ACK) | CONTROL | 50 | MEDIUM | 1 | – |
| dst 5000 | NORMAL | 10 | NORMAL | 0 | – |
| any other UDP (e.g. iperf) | BACKGROUND | 5 | LOW | 0 | – |
| non-UDP IP (ICMP, TCP) | OTHER | 1 | LOW | – | – |
| table-miss | → controller | 0 | | | |

How it works:

1. When a switch connects, the controller installs a table-miss rule that sends unknown packets to the controller.
2. For each new UDP flow, the controller reads the destination port, classifies it, and logs the result.
3. It then installs an OpenFlow 1.3 rule matching that flow (in_port, IPs, UDP ports) at the class priority. The rule applies `set_queue`, applies `set_field ip_dscp` for emergency traffic, and outputs to the learned port.
4. Non-UDP rules are pinned to their IP protocol, so they never shadow a UDP flow that still needs classifying.
5. Every 10 s the controller requests flow stats and logs packets and bytes per class. It also appends them to `results/sdn_flow_stats.csv` for graphs.

Constants (ports, queue IDs, timeouts, stats interval) are at the top of the two `.py` files.

## Setup (Ubuntu VM)

Ryu needs Python 3.8 or 3.9. Newer Python versions break its `eventlet` dependency.

```bash
sudo apt install python3.9 python3.9-venv mininet openvswitch-switch
python3.9 -m venv ~/ryu-venv
source ~/ryu-venv/bin/activate
pip install "setuptools<58" wheel pbr
pip install --no-build-isolation -r controller/requirements.txt
```

## Run

From the project root:

```bash
ryu-manager controller/emergency_controller.py
```

## Test with Mininet

Terminal 1 (controller):

```bash
ryu-manager controller/emergency_controller.py
```

Terminal 2 (network; Person 3's topology replaces this simple one):

```bash
sudo mn --topo single,4 --mac --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6653
```

Inside Mininet:

```
mininet> pingall
mininet> h1 python3 -m server.notification_server &      # or use xterm h1
mininet> h2 python3 -m client.notification_client --id client1 --server 10.0.0.1 &
```

Send `emergency Fire in Block A` and `normal Test message` from the server, then check the installed flows:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Emergency flows show `priority=100,udp,...,tp_dst=9999 actions=set_queue:1,set_field:46->ip_dscp,output:N`.
Normal flows show `priority=10`.

Quick test without the app:

```
mininet> h2 nc -u -l 9999 &
mininet> h1 bash -c 'echo test | nc -u -w1 10.0.0.2 9999'
```

## Offline tests (no Mininet needed)

```bash
python -m unittest controller/test_emergency_controller.py -v
```

## Notes for Person 3 (queues / QoS)

- Emergency traffic and ACKs go to **queue 1**. Normal and background traffic go to **queue 0**.
- Configure queue 1 with a high guaranteed rate on each switch port. Example for a 10 Mbit/s link:

```bash
sudo ovs-vsctl -- set port s1-eth2 qos=@q -- --id=@q create qos type=linux-htb \
  other-config:max-rate=10000000 queues:0=@q0 queues:1=@q1 \
  -- --id=@q0 create queue other-config:max-rate=10000000 \
  -- --id=@q1 create queue other-config:min-rate=8000000 other-config:max-rate=10000000
```

- If no queues are configured, `set_queue` has no effect, and the flow-priority classification still works.
- Use Mininet links with bandwidth limits (`TCLink`, `bw=10`) and generate congestion with iperf UDP on another port, e.g. `iperf -u -c 10.0.0.2 -b 20M -p 5201`. That traffic is classified BACKGROUND.
- The topology must be loop-free (single or tree), because the controller is a learning switch without STP.

## Testing checklist

- [x] Ryu starts
- [x] Switch connects (table-miss installed)
- [x] Normal UDP traffic is detected
- [x] Emergency UDP traffic is detected
- [x] Emergency receives higher flow priority
- [x] Flow rules are installed
- [x] Packets are forwarded correctly
- [x] Controller logs classification

# Person 2 — SDN Controller (OS-Ken)

The SDN controller identifies emergency UDP traffic and assigns it a higher forwarding priority than normal and background traffic.

## Files

| File                           | Purpose                                                                                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `emergency_controller.py`      | OS-Ken controller application, OpenFlow switch handling, learning-switch forwarding, UDP classification, priority rules, queue mapping and flow statistics |
| `traffic_classifier.py`        | Classifies traffic based on protocol and UDP ports without depending on OS-Ken                                                                             |
| `test_emergency_controller.py` | Offline unit tests for controller classification and flow handling                                                                                         |
| `requirements.txt`             | Python dependencies for the controller                                                                                                                     |

## Traffic Classification

The port numbers correspond to `common/protocol.py` in the UDP notification application.

| Traffic    | Match                               | Flow priority | Level  | OVS queue | DSCP    |
| ---------- | ----------------------------------- | ------------: | ------ | --------: | ------- |
| Emergency  | UDP destination port 9999           |           100 | HIGH   |         1 | 46 (EF) |
| Control    | UDP source or destination port 5001 |            50 | MEDIUM |         1 | —       |
| Normal     | UDP destination port 5000           |            10 | NORMAL |         0 | —       |
| Background | Other UDP traffic                   |             5 | LOW    |         0 | —       |
| Other      | Non-UDP IP traffic                  |             1 | LOW    |         — | —       |
| Table miss | Unmatched packets                   |             0 | —      |         — | —       |

## How It Works

1. When a switch connects, the controller installs a table-miss rule that sends unmatched packets to the controller.
2. The controller examines new packets and classifies UDP traffic using the configured ports.
3. It installs OpenFlow rules with the appropriate traffic priority and forwarding actions.
4. Emergency traffic receives queue 1 and DSCP 46 when supported by the switch and configured QoS queues.
5. The controller learns MAC addresses and forwards packets through the appropriate switch ports.
6. Periodically, the controller requests flow statistics and records traffic information in `results/sdn_flow_stats.csv`, if implemented in the controller code.

## Prerequisites

- Kali Linux or Ubuntu
- Mininet
- Open vSwitch
- Python
- OS-Ken compatible with the Python environment

The controller must use the same OpenFlow version and listening port as Mininet. This project uses OpenFlow 1.3 and port 6633 in the tested setup.

## Run the Controller

From the project root, activate the Python environment that contains the working OS-Ken installation and run:

```bash
source ~/osken-venv/bin/activate
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
```

Use the controller launcher available in your installed OS-Ken version. If `osken-manager` is installed:

```bash
osken-manager controller/emergency_controller.py
```

OS-Ken 4.x releases may not provide the older `osken-manager` command. Do not assume the command exists; use the launcher compatible with your installed version.

## Run Mininet

In a separate terminal:

```bash
sudo systemctl start openvswitch-switch
sudo mn -c
sudo mn --topo single,4 --mac --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6633
```

At the Mininet prompt:

```text
pingall
```

All hosts should be able to reach one another when the controller and forwarding rules are working.

## Inspect OpenFlow Rules

In another terminal:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Generate traffic before checking for classification rules. A table-miss rule alone does not demonstrate that emergency-specific rules were installed.

## Run the Offline Tests

From the project root, using the project's Python environment:

```bash
python -m unittest controller/test_emergency_controller.py -v
```

## QoS Notes

- Emergency and control traffic are assigned queue 1 by the controller.
- Normal and background traffic are assigned queue 0.
- The queues must be configured on the relevant Open vSwitch ports for queue selection to have an effect.
- Flow priority and queue assignment are separate: a higher OpenFlow priority determines which rule matches, while QoS configuration determines queue treatment.
- Use a loop-free topology unless the controller implements loop prevention or spanning-tree support.

## Testing Checklist

- [ ] Controller starts without errors.
- [ ] Switch connects using OpenFlow 1.3.
- [ ] `pingall` succeeds.
- [ ] Normal UDP traffic is classified.
- [ ] Emergency UDP traffic on port 9999 is classified.
- [ ] Emergency flow rules use higher priority than normal traffic.
- [ ] Forwarding works after rules are installed.
- [ ] Flow statistics are recorded when statistics logging is implemented.
- [ ] QoS queues are configured and verified before claiming preferential queue treatment.

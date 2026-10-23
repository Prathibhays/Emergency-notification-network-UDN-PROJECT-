# Emergency Notification Network
## UDP Socket Programming + Software-Defined Networking (SDN)

**Mini Project:** SDN–Socket Programming — Jackfruit Mini Project  
**Application:** Emergency Notification Network  
**Transport Protocol:** UDP  
**Network Emulator:** Mininet  
**Virtual Switch:** Open vSwitch (OVS)  
**SDN Controller:** OS-Ken  
**OpenFlow Version:** OpenFlow 1.3  
**Platform:** Kali Linux / Ubuntu

---

# 1. Project Overview

The Emergency Notification Network is a networked application that distributes urgent notifications to multiple registered clients using UDP sockets. An SDN controller monitors traffic entering the network, identifies emergency-related UDP packets, and installs OpenFlow rules to classify and prioritize different traffic types.

The project combines two important concepts:

1. **Socket programming:** Implementing application-level communication between a server and multiple clients.
2. **Software-Defined Networking:** Using a programmable controller to influence how packets are forwarded through the network.

The system is evaluated using message delivery, acknowledgements, notification latency, packet loss, flow statistics, and experiments involving background traffic.

## 1.1 Problem Statement

During emergencies such as fires, medical incidents, accidents, and security threats, notifications must reach multiple recipients quickly.

A conventional notification application can send messages to many clients, but the network may treat emergency messages and ordinary background traffic similarly. Under congestion, emergency packets may experience increased delay or loss.

The problem addressed by this project is:

**How can a UDP-based notification application distribute emergency messages to multiple clients while an SDN-controlled network identifies emergency traffic and assigns it a higher forwarding priority?**

## 1.2 Objectives

- Implement UDP communication between a notification server and multiple clients.
- Allow clients to register with the server.
- Distribute normal and emergency notifications.
- Provide application-level acknowledgements for emergency notifications.
- Classify traffic using UDP ports.
- Use an SDN controller to install OpenFlow forwarding rules with different priorities.
- Assign emergency traffic to a designated QoS queue when queues are configured.
- Measure notification latency and record results.
- Collect OpenFlow flow statistics.
- Build and test the system using Mininet.
- Compare network behavior under different traffic conditions.

## 1.3 Scope and Limitations

This is an educational prototype running in a controlled virtual network. It demonstrates notification delivery and programmable network forwarding.

It does not currently claim to be a production emergency-alert service. UDP does not guarantee delivery, ordering, or retransmission. Application-level acknowledgements confirm receipt of a message by a client, but the current implementation does not automatically retry messages when an acknowledgement is missing.

Similarly, an OpenFlow priority value alone does not guarantee lower end-to-end latency. Actual queue-based preferential treatment requires suitable QoS queues and a correctly configured network.

---

# 2. System Architecture

The system contains three main layers.

## 2.1 Application Layer

The application layer consists of:

- **Notification server:** Registers subscribers and sends notifications.
- **Subscriber manager:** Maintains the list of registered clients.
- **Notification clients:** Listen for normal and emergency notifications.
- **Shared protocol:** Defines message formats, port numbers, registration messages, and acknowledgements.

## 2.2 SDN Layer

The SDN layer consists of:

- **SDN controller:** Implements the traffic classification and forwarding policy.
- **Open vSwitch:** Acts as the programmable network switch.
- **OpenFlow 1.3:** Allows the controller to install forwarding rules and request flow statistics.

## 2.3 Emulated Network

Mininet creates a virtual topology containing four hosts and one switch.

| Mininet node | IP address | Role |
|---|---|---|
| h1 | 10.0.0.1 | Notification server |
| h2 | 10.0.0.2 | Client 1 |
| h3 | 10.0.0.3 | Client 2 |
| h4 | 10.0.0.4 | Additional host for testing |

The default topology connects all four hosts to switch s1.

## 2.4 Architecture Diagram

```text
                  Notification Server
                       h1
                    10.0.0.1
                        |
                        |
                 +-------------+
                 | Open vSwitch|
                 |     s1      |
                 +-------------+
                        |
              OpenFlow 1.3 connection
                        |
                 +-------------+
                 | OS-Ken SDN  |
                 | Controller  |
                 +-------------+

              Switch-connected hosts
                  /           \
                 /             \
          Client h2           Client h3
          10.0.0.2            10.0.0.3
```

The controller communicates with the switch over an OpenFlow control connection. Notification messages travel through the emulated data network, not through the controller itself.

---

# 3. Repository Structure

```text
Emergency-notification-network-UDN-PROJECT/
|
|-- README.md
|-- README_PERSON1.md
|-- requirements.txt
|-- .gitignore
|
|-- client/
|   |-- __init__.py
|   |-- notification_client.py
|
|-- common/
|   |-- __init__.py
|   |-- protocol.py
|
|-- server/
|   |-- __init__.py
|   |-- notification_server.py
|   |-- subscriber_manager.py
|
|-- controller/
|   |-- README.md
|   |-- emergency_controller.py
|   |-- traffic_classifier.py
|   |-- test_emergency_controller.py
|   |-- requirements.txt
|
|-- results/
    |-- latency_client1.csv
    |-- latency_client2.csv
    |-- sdn_flow_stats.csv
```

The `results/` directory is generated when the relevant components run. Its contents depend on which experiments have been executed.

### Purpose of each important file

| File | Responsibility |
|---|---|
| `server/notification_server.py` | Registers subscribers, sends notifications, receives acknowledgements |
| `server/subscriber_manager.py` | Stores and retrieves registered subscribers safely |
| `client/notification_client.py` | Registers with the server, receives messages, measures latency, sends emergency ACKs |
| `common/protocol.py` | Defines shared ports, message types, serialization and parsing |
| `controller/traffic_classifier.py` | Maps UDP ports to traffic classes and priorities |
| `controller/emergency_controller.py` | Handles switch events, learns MAC addresses, installs OpenFlow rules, and requests statistics |
| `controller/test_emergency_controller.py` | Tests traffic classification and simulated OpenFlow behavior |
| `requirements.txt` | Documents dependencies for the application |
| `controller/requirements.txt` | Declares the OS-Ken dependency |

---

# 4. UDP Socket Programming

## 4.1 What is UDP?

UDP stands for User Datagram Protocol.

UDP sends independent datagrams between network endpoints. Unlike TCP, it does not establish a connection before sending data.

### Advantages

- Low protocol overhead.
- No connection establishment handshake.
- Suitable for time-sensitive messages.
- Supports communication between multiple endpoints.

### Limitations

- Delivery is not guaranteed.
- Packets may be lost, duplicated, or arrive out of order.
- UDP does not automatically retransmit lost application messages.
- The application must implement any additional delivery-confirmation mechanism it requires.

For this project, UDP is used because emergency notifications should be transmitted without the connection-establishment overhead of TCP. Acknowledgements are implemented at the application level for emergency notifications.

## 4.2 Server and Client Sockets

The server uses UDP sockets to receive registration messages and acknowledgements and to send notifications.

Each client uses UDP sockets to:

1. Register with the server.
2. Listen for normal notifications on UDP port 5000.
3. Listen for emergency notifications on UDP port 9999.
4. Send emergency acknowledgements through the control socket.

The client uses a selector to monitor its normal and emergency sockets without requiring a separate receive thread for each socket.

## 4.3 UDP Ports Used

| Port | Purpose |
|---|---|
| 5000/UDP | Normal notifications |
| 5001/UDP | Registration and acknowledgement control messages |
| 9999/UDP | Emergency notifications |

These port numbers are defined in `common/protocol.py` and are reused by the application and SDN classifier.

## 4.4 Application Protocol

The project uses a simple text-based protocol.

### Registration request

```text
REGISTER|client1
```

### Registration response

```text
REGISTERED|client1
```

### Notification message

```text
message_id|message_type|timestamp|payload
```

Example:

```text
1|EMERGENCY|1790000000.123456|Fire detected in Block A
```

The timestamp is the sender's Unix timestamp in seconds.

### Acknowledgement

```text
ACK|message_id|client_id
```

Example:

```text
ACK|1|client1
```

The server uses the message ID and client ID to identify the acknowledgement.

The protocol uses the pipe character (`|`) as a delimiter. The shared protocol sanitizes payloads so that embedded pipes do not break message parsing.

---

# 5. How the Application Works

## 5.1 Subscriber Registration

1. The client starts and creates its UDP sockets.
2. It sends a `REGISTER` message to the server's control port.
3. The server receives the registration.
4. The subscriber manager stores the client ID, IP address, and registration time.
5. The server sends a `REGISTERED` response.
6. The client starts listening for normal and emergency messages.

The current subscriber manager stores clients in memory. Registrations are not persisted across server restarts.

## 5.2 Sending a Normal Notification

When the server receives a command such as:

```text
normal Scheduled maintenance at 6 PM
```

it:

1. Checks the registered subscriber list.
2. Creates a message ID and timestamp.
3. Serializes the notification.
4. Sends the message to each subscriber's IP address on UDP port 5000.

## 5.3 Sending an Emergency Notification

When the server receives:

```text
emergency Fire detected in Block A. Evacuate immediately.
```

it:

1. Creates a message ID and timestamp.
2. Builds an emergency notification.
3. Sends the message to each registered subscriber on UDP port 9999.
4. Waits for acknowledgement messages on the control socket.

When a client receives an emergency notification, it displays the message and measured latency, writes a CSV record, and sends an ACK to the server.

The current server logs acknowledgements when they arrive. It does not implement automatic retransmission or timeout-based retry.

## 5.4 Measuring Latency

The client calculates:

```text
latency_ms = (receive_timestamp - send_timestamp) * 1000
```

This is the elapsed time between the server timestamp and the client receive timestamp.

Both timestamps come from the system clocks. The measurement is meaningful when those clocks are synchronized closely enough. In a single Kali VM, the hosts generally share the same system clock, which makes this a useful prototype measurement.

The measured value is application-level elapsed time; it is not a pure measurement of switch forwarding delay.

---

# 6. SDN and Traffic Classification

## 6.1 What is SDN?

Software-Defined Networking separates network control decisions from packet forwarding.

In this project:

- The OS-Ken controller implements the forwarding policy.
- Open vSwitch forwards packets according to installed OpenFlow rules.
- OpenFlow 1.3 provides the protocol used by the controller to communicate with the switch.

This allows traffic classification and forwarding policy to be changed in software instead of relying only on static switch configuration.

## 6.2 Traffic Classification Rules

The project's classifier uses UDP ports to identify traffic categories.

| Traffic class | Condition | OpenFlow priority | Queue ID | DSCP |
|---|---|---:|---:|---:|
| EMERGENCY | UDP destination port 9999 | 100 | 1 | 46 |
| CONTROL | UDP source or destination port 5001 | 50 | 1 | Unchanged |
| NORMAL | UDP destination port 5000 | 10 | 0 | Unchanged |
| BACKGROUND | Other UDP traffic | 5 | 0 | Unchanged |
| OTHER | Non-UDP IPv4 traffic | 1 | Not assigned | Unchanged |
| Table miss | No matching rule | 0 | Not assigned | Unchanged |

### Meaning of flow priority

A higher OpenFlow priority is selected over a lower-priority rule when both rules match a packet.

The value 100 for emergency traffic is therefore higher than 10 for normal traffic.

### Meaning of queue ID

The controller assigns queue 1 to emergency and control traffic and queue 0 to normal and background traffic.

**Queue assignment is effective only when the relevant queues are configured on the switch ports.** Without that configuration, the controller may install `set_queue` actions, but preferential scheduling is not guaranteed.

### Meaning of DSCP 46

DSCP stands for Differentiated Services Code Point. The value 46 corresponds to Expedited Forwarding (EF), a marking associated with low-delay traffic treatment in appropriately configured networks.

Marking a packet with DSCP 46 does not, by itself, guarantee low latency.

## 6.3 How the Controller Handles Packets

1. The switch connects to the controller.
2. The controller installs a table-miss rule that sends unmatched packets to the controller.
3. When a new packet arrives, the controller examines its Ethernet, IP, and UDP headers.
4. It learns the source MAC address and incoming switch port.
5. It classifies UDP traffic using source and destination ports.
6. It determines the outgoing port using its MAC learning table, or floods the packet if the destination is not yet known.
7. For known destinations, it installs a flow rule with the appropriate priority and actions.
8. It forwards the first packet using a PacketOut message.
9. The switch handles subsequent packets that match the installed rule.
10. The controller periodically requests flow statistics and records matching traffic classes in a CSV file.

Flow rules have an idle timeout, so an unused rule can expire and be installed again when traffic returns.

The controller is a learning switch, not a complete routing protocol. The supplied single-switch topology is loop-free, which suits this implementation.

## 6.4 Dynamic Behavior and Current Limitations

The controller dynamically reacts to switch and packet events by learning MAC addresses, classifying newly observed flows, installing forwarding rules, and requesting flow statistics.

However, the current implementation does not automatically reroute around failed links or change queue rates in response to measured congestion. Those would be additional features.

---

# 7. Prerequisites

Use Kali Linux or Ubuntu with:

- Python 3
- Mininet
- Open vSwitch
- A working OS-Ken environment
- OpenFlow 1.3 support
- `xterm` for separate Mininet host terminals

The UDP application uses Python standard-library modules and does not require third-party packages.

The controller depends on OS-Ken. The controller launcher must be compatible with the installed OS-Ken version.

**Important version note:** OS-Ken 4.x releases may not include the legacy `osken-manager` command. Do not assume that the launcher is available simply because the package is installed. Use the launch method that works with your installed controller environment.

---

# 8. Start the Project in Kali Linux

The following commands assume that the repository is located at:

```text
~/Desktop/Emergency-notification-network-UDN-PROJECT--main
```

If you cloned it to another directory, substitute that path.

## Step 1: Open a terminal and enter the project directory

```bash
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
```

**What it does:** Changes the current directory to the project root. Run the application's module commands from this directory so that Python can import `client`, `server`, and `common`.

Check the files:

```bash
ls
```

## Step 2: Start Open vSwitch

```bash
sudo systemctl start openvswitch-switch
```

**What it does:** Starts the Open vSwitch service.

Check the service:

```bash
sudo ovs-vsctl show
```

You should see the OVS configuration and version information. If this command fails, troubleshoot Open vSwitch before starting Mininet.

## Step 3: Activate the controller environment

If you created the environment at `~/osken-venv`, run:

```bash
source ~/osken-venv/bin/activate
```

**What it does:** Activates the Python virtual environment containing the controller's dependencies.

Check the installed package:

```bash
python -m pip show os-ken
```

Check whether the legacy launcher exists:

```bash
command -v osken-manager
```

If it exists, use the next step. If it does not, follow the instructions for the launcher compatible with your installed OS-Ken version.

## Step 4: Start the SDN controller

From the project root, if the installed environment provides `osken-manager`:

```bash
osken-manager controller/emergency_controller.py
```

**What it does:** Loads the controller application and starts listening for OpenFlow switch connections. Keep this terminal open.

Look for controller startup messages and a switch connection message when Mininet starts.

If you see `command not found`, the controller is not running from this command. Do not continue under the assumption that the SDN controller is active.

## Step 5: Open a second terminal and start Mininet

Keep the controller terminal open. Open another Kali terminal and run:

```bash
sudo mn -c
```

**What it does:** Cleans up stale Mininet processes and network state from earlier experiments.

Now start the topology:

```bash
sudo mn --topo single,4 --mac --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6633
```

**What the options mean:**

- `--topo single,4`: Creates one switch and four hosts.
- `--mac`: Assigns predictable MAC addresses.
- `--switch ovsk`: Uses Open vSwitch.
- `protocols=OpenFlow13`: Enables OpenFlow 1.3.
- `--controller remote`: Connects to an external controller.
- `ip=127.0.0.1`: Uses the local Kali VM as the controller host.
- `port=6633`: Connects to TCP port 6633.

The controller and Mininet must use the same port. If your working controller uses a different port, update the Mininet command to match it.

## Step 6: Test host connectivity

At the Mininet prompt:

```text
mininet> nodes
mininet> net
mininet> pingall
```

- `nodes` lists Mininet hosts, switches, and controllers.
- `net` displays the links between nodes.
- `pingall` checks whether the hosts can reach one another.

Expected result for a working topology:

```text
*** Results: 0% dropped
```

This confirms connectivity, but it does not yet prove that emergency flow rules are working.

## Step 7: Open terminals for the Mininet hosts

At the `mininet>` prompt:

```text
mininet> xterm h1 h2 h3
```

This attempts to open separate terminal windows for h1, h2, and h3.

If `xterm` is not installed, open a separate Kali terminal and run:

```bash
sudo apt update
sudo apt install xterm -y
```

Return to Mininet and run the `xterm` command again.

The hosts share the VM's project filesystem, but they have separate network namespaces and IP addresses.

## Step 8: Start the notification server in h1

In the h1 terminal:

```bash
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
python3 -m server.notification_server
```

The default server host is `0.0.0.0`, and the default control port is 5001.

The server should display its command prompt:

```text
server>
```

The supported server commands are:

```text
list
normal <message>
emergency <message>
quit
```

## Step 9: Start client 1 in h2

In the h2 terminal:

```bash
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
python3 -m client.notification_client --id client1 --server 10.0.0.1
```

The `--id` argument sets the client's unique identifier. The `--server` argument is the IP address of h1.

Wait for the client to display:

```text
[REGISTERED] client1 with server 10.0.0.1
```

It should then listen on UDP ports 5000 and 9999.

## Step 10: Start client 2 in h3

In the h3 terminal:

```bash
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
python3 -m client.notification_client --id client2 --server 10.0.0.1
```

Wait for `client2` to register successfully.

If registration fails, stop here and troubleshoot before sending notifications.

---

# 9. Live Demonstration

Once the server and both clients are running, use the following sequence.

## 9.1 Verify registered clients

In the h1 server terminal, type:

```text
server> list
```

Expected result: the registered clients appear with their IP addresses.

## 9.2 Send a normal notification

In h1:

```text
server> normal Scheduled maintenance at 6 PM
```

Expected behavior:

- The server prints the message ID, type, destination port, and subscriber count.
- The server sends the message to registered clients on UDP port 5000.
- Each client displays the message and measured latency.
- The client writes a row to its latency CSV file.

## 9.3 Send an emergency notification

In h1:

```text
server> emergency Fire detected in Block A. Evacuate immediately.
```

Expected behavior:

- The server sends the message to registered clients on UDP port 9999.
- Clients display the emergency message and latency.
- Each client sends an application-level ACK.
- The server prints acknowledgement messages.

An acknowledgement confirms that the application received the message and sent an ACK. It is not a guarantee that every possible client received the alert.

## 9.4 Inspect the OpenFlow rules

Open another Kali terminal outside Mininet and run:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

**What it does:** Queries switch s1 and prints its installed OpenFlow rules.

Generate traffic before checking. The controller learns MAC addresses and installs per-flow rules as it observes packets.

Look for emergency flow rules with priority 100 and UDP destination port 9999. Normal notification flows should have priority 10.

Emergency actions should include queue 1 and DSCP 46 when the controller installs those actions.

If only a table-miss rule is present, emergency-specific rule installation has not yet been demonstrated.

---

# 10. Performance Measurement and Results

## 10.1 Latency CSV files

The client creates a CSV file named:

```text
results/latency_<client_id>.csv
```

The file contains:

- `message_id`
- `type`
- `client_id`
- `server_timestamp`
- `receive_timestamp`
- `latency_ms`

For example, client 1 uses `results/latency_client1.csv` relative to its working directory.

To inspect a result file from a Kali terminal:

```bash
cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main
find results -maxdepth 1 -type f -print
```

Then:

```bash
cat results/latency_client1.csv
cat results/latency_client2.csv
```

If the files are missing from the VM's project directory, check the working directory from which the clients were launched. The `--results-dir` argument can be used to specify another results directory.

## 10.2 SDN flow statistics

The controller periodically requests flow statistics and records statistics for recognized traffic classes.

The expected file is:

```text
results/sdn_flow_stats.csv
```

To inspect it:

```bash
cat results/sdn_flow_stats.csv
```

Its columns are:

```text
timestamp,dpid,class,flow_priority,flows,packets,bytes
```

The statistics include flow counts, packet counts, and byte counts. They are useful for showing which classes have matching installed flows and how much traffic they have carried.

The file may be empty beyond its header if no recognized traffic-class flows have been installed or statistics replies have not been received.

## 10.3 Packet loss

UDP does not guarantee delivery. Packet loss can be measured by comparing the number of sent messages or datagrams with the number received, using a repeatable experiment and a clearly defined counting method.

`pingall` measures ICMP reachability. It does not directly measure the loss rate of the application's UDP notifications.

The current application does not automatically retransmit messages whose acknowledgements are missing. If a notification is lost, the server does not currently retry it.

## 10.4 Congestion Experiment

To evaluate the system under congestion, use a bandwidth-limited Mininet topology and generate competing background traffic.

A meaningful experiment should include:

1. A baseline with little or no competing traffic.
2. A congestion condition with background UDP traffic.
3. A priority/QoS condition with the appropriate queues configured.
4. Repeated measurements of emergency latency and loss under each condition.

The default `single,4` topology does not specify bandwidth limits. A congestion experiment therefore needs a bandwidth-constrained topology or other deliberate traffic-limiting setup.

Do not claim that the current project has achieved a particular latency improvement until the experiments have been run and the results recorded.

## 10.5 Comparison Table for the Report

Fill in the table with actual measured values.

| Scenario | Background load | QoS configured? | Emergency latency | Notification loss |
|---|---|---|---|---|
| A: Baseline | Low or none | Record actual setup | Measure | Measure |
| B: Congestion | Competing traffic | Record actual setup | Measure | Measure |
| C: Priority/QoS | Same competing load | Yes, if configured | Measure | Measure |

For a fair comparison, use the same topology, message size, number of notifications, and background traffic rate wherever possible.

---

# 11. Running the Unit Tests

The project contains offline tests for traffic classification and simulated OpenFlow controller behavior.

From the project root, activate the controller environment if needed:

```bash
source ~/osken-venv/bin/activate
```

Run:

```bash
python -m unittest controller/test_emergency_controller.py -v
```

The `-v` option displays the name and status of each test.

The tests check classification of emergency, normal, control, and background traffic; table-miss handling; priority rules; queue and DSCP actions; forwarding; and flow-statistics handling.

Some controller tests require OS-Ken. If the dependency is unavailable, those tests may be skipped. A skipped test is not a passing runtime test of the controller.

---

# 12. Useful Troubleshooting Commands

## 12.1 Check Open vSwitch

```bash
sudo systemctl status openvswitch-switch
sudo ovs-vsctl show
```

Use these commands when Mininet cannot create switches or the OVS database is unavailable.

## 12.2 Clean up Mininet

```bash
sudo mn -c
```

Use this after a failed or interrupted Mininet session. It removes stale Mininet state.

Do not run it while you need to preserve the active topology for a demonstration.

## 12.3 Inspect the switch flow table

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Use this to check whether flow rules have been installed.

## 12.4 Inspect the controller port

```bash
sudo ss -ltnp | grep -E ':(6633|6653)\b'
```

This shows TCP listeners on common OpenFlow controller ports. Ensure that the controller's actual listening port matches the port specified in the Mininet command.

## 12.5 Check Mininet host interfaces and routes

At the Mininet prompt:

```text
mininet> h1 ip addr
mininet> h2 ip addr
mininet> h1 ip route
mininet> h2 ip route
```

Use these commands if the application cannot communicate between hosts.

## 12.6 Check Python syntax

From the project root:

```bash
python3 -m compileall client common server controller
```

This checks Python files for syntax errors. It does not prove that imports, dependencies, sockets, or runtime behavior are correct.

## 12.7 Check application help

```bash
python3 -m server.notification_server --help
python3 -m client.notification_client --help
```

These commands display the supported command-line arguments.

## 12.8 Stop the application

Use `Ctrl+C` in client terminals to stop clients.

Type the following in the server prompt to stop the server:

```text
quit
```

Exit Mininet with:

```text
mininet> exit
```

If cleanup is required after the experiment:

```bash
sudo mn -c
```

---

# 13. Common Problems and Solutions

### Problem: `osken-manager: command not found`

**Cause:** The installed OS-Ken version or environment does not provide the legacy launcher.

**Solution:** Activate the correct virtual environment, verify the installed OS-Ken version, and use a launcher compatible with that version. The package version alone does not prove that the command is available.

### Problem: Mininet reports that the controller cannot be contacted

**Possible causes:**

- The controller is not running.
- The controller failed during startup.
- The controller listens on another port.
- The switch uses a different OpenFlow version.

**Solution:** Check the controller terminal, verify the listening port, and ensure the Mininet command uses the same port.

### Problem: `pingall` reports packet loss

**Possible causes:**

- The controller is disconnected.
- The table-miss or forwarding behavior is not working.
- The switch or topology has stale state.
- An IP or link configuration is incorrect.

**Solution:** Inspect the controller logs, run `nodes` and `net`, check the flow table, and verify the host IP addresses.

### Problem: Client registration fails

**Possible causes:**

- The server is not running.
- The client is using the wrong server IP.
- UDP port 5001 is unreachable.
- The server and client are running in different network environments.

**Solution:** Confirm that the server is running in h1, that the client uses `--server 10.0.0.1`, and that h1 and h2 can reach each other.

### Problem: Notifications are sent but not received

**Possible causes:**

- Clients are not registered.
- The server is sending to an incorrect subscriber address.
- The client is not listening on the expected UDP port.
- A forwarding rule or network configuration is incorrect.

**Solution:** Run `list` on the server, check the client terminal, verify host connectivity, and inspect the OpenFlow rules.

### Problem: No emergency-specific flow appears

**Possible causes:**

- No matching emergency packet has reached the switch.
- The controller is disconnected.
- The destination MAC has not been learned.
- The controller did not install the expected rule.

**Solution:** Generate emergency traffic, inspect controller logs, verify host connectivity, and check `dump-flows` again.

### Problem: Queue assignment does not improve latency

**Cause:** The queue actions may exist without corresponding QoS queues or sufficient scheduling configuration.

**Solution:** Configure and verify queues on the relevant switch ports, then compare measured performance with and without QoS.

### Problem: Results CSV is missing

**Cause:** The application may have created the file relative to a different working directory, or the component may not have received the expected traffic.

**Solution:** Check the launch directory, inspect the configured results path, and generate another notification.

---

# 14. What We Learned

## 14.1 Socket Programming

- How to create UDP sockets and bind them to ports.
- How to send and receive datagrams.
- How to implement application-level registration.
- How to manage multiple subscribers.
- How to design a message protocol and serialize structured messages.
- How to use selectors to monitor multiple sockets.
- How to implement application-level acknowledgements.
- Why UDP delivery is not guaranteed.

## 14.2 Protocol Design

The project uses shared constants and helper functions so the client and server agree on ports, message types, and message formats.

Separating protocol code from server and client logic reduces duplication and helps prevent mismatches.

## 14.3 Software-Defined Networking

- How an SDN controller communicates with an OpenFlow switch.
- How OpenFlow 1.3 flow rules match packet headers.
- How rule priorities determine which matching rule is selected.
- How a learning switch discovers MAC addresses and forwards packets.
- How traffic can be classified based on UDP ports.
- How queue assignment and DSCP marking can be used as part of a QoS policy.
- How to query flow statistics.

## 14.4 Network Emulation

Mininet allows multiple virtual hosts and switches to run within one Linux environment. This makes it possible to test a multi-node application without requiring several physical computers.

## 14.5 Performance Evaluation

We learned to distinguish between:

- Network reachability.
- Application message delivery.
- Application-level acknowledgement.
- Application-level latency.
- Packet loss.
- OpenFlow rule priority.
- QoS queue treatment.

These metrics describe different aspects of system behavior and should not be treated as interchangeable.

---

# 15. Evaluation Rubric Mapping

| Requirement | Project component | Evidence to demonstrate |
|---|---|---|
| Problem understanding and architecture | Overall design | Explain server, clients, switch, and controller |
| UDP socket implementation | Server and client | Registration, normal messages, emergency messages, ACKs |
| Mininet and SDN | Mininet, OVS, OS-Ken | Successful `pingall`, controller connection, flow table |
| Socket–SDN integration | UDP application plus controller | Generate UDP notification traffic and observe its classification |
| Initial testing | Application and network | Successful registration and end-to-end message delivery |
| Complete application | Server and clients | Multiple registered subscribers receive notifications |
| Dynamic SDN functionality | Controller | Learning, classification, flow installation, and statistics |
| Challenging scenario | Congestion experiment | Background traffic and repeatable measurements |
| Performance evaluation | CSV results | Compare latency and loss under multiple conditions |
| Documentation and viva | README and tests | Reproduce commands, explain source code and results |

A rubric item should be marked complete only after the corresponding behavior has been tested and evidence has been collected.

---

# 16. Viva Preparation

### Q1. Why did you use UDP instead of TCP?

UDP has lower protocol overhead and does not require connection establishment. It is suitable for a time-sensitive notification prototype. Since UDP does not guarantee delivery, the application implements acknowledgements for emergency notifications.

### Q2. Does UDP guarantee that every client receives the alert?

No. UDP does not guarantee delivery. The server sends a datagram to each registered client, and the client sends an application-level ACK for emergency messages. The current implementation does not automatically retransmit messages when ACKs are missing.

### Q3. What is the purpose of the subscriber manager?

It maintains the registered client IDs and IP addresses so the server can distribute notifications to the correct subscribers.

### Q4. What is SDN?

Software-Defined Networking separates network control decisions from packet forwarding. A controller can program the forwarding behavior of compatible switches using a protocol such as OpenFlow.

### Q5. What is OpenFlow?

OpenFlow is a protocol that allows a controller to communicate with compatible switches, install flow rules, and request flow statistics.

### Q6. What is the difference between flow priority and queue priority?

Flow priority determines which OpenFlow rule matches a packet when multiple rules match. A queue controls how packets are scheduled for transmission. A high-priority rule alone does not guarantee a low-delay queue.

### Q7. Why is the emergency priority 100?

It is a policy choice that makes the emergency rule higher priority than the normal, background, control, and other traffic rules defined in this project.

### Q8. Why is DSCP 46 used?

DSCP 46 is the Expedited Forwarding marking. It can help downstream devices identify traffic intended for low-delay treatment when those devices are configured to honor the marking.

### Q9. Why do we use Mininet?

Mininet creates virtual hosts, switches, and links in a controlled Linux environment. It lets us test multi-host communication and SDN behavior on one machine.

### Q10. What does `pingall` prove?

It checks basic ICMP reachability among Mininet hosts. It does not prove that the application works or that emergency packets receive preferential treatment.

### Q11. How is latency calculated?

The client subtracts the server's send timestamp from its receive timestamp and converts the difference to milliseconds. The measurement depends on sufficiently synchronized clocks.

### Q12. How does the controller classify emergency traffic?

It examines the UDP source and destination ports. A packet whose UDP destination port is 9999 is classified as emergency traffic and assigned flow priority 100, queue 1, and DSCP 46.

### Q13. What happens when the controller sees a new packet?

It learns the source MAC address and input port, classifies the packet when possible, determines the output port, installs a flow rule for a known destination, and forwards the packet. Unknown destinations may be flooded while the controller learns the network.

### Q14. How would you demonstrate congestion?

Use a bandwidth-limited topology, generate competing background traffic, and measure notification latency and loss. Repeat the test with a suitable QoS configuration and compare the results.

### Q15. What are the limitations of your current implementation?

UDP messages can be lost, ACKs are not automatically retried, subscriber registration is in memory, and congestion-aware rerouting is not implemented. QoS queues must be configured separately. The current topology and tests demonstrate a prototype rather than a production emergency communication system.

---

# 17. Quick Command Reference

| Task | Command |
|---|---|
| Enter project root | `cd ~/Desktop/Emergency-notification-network-UDN-PROJECT--main` |
| Activate controller environment | `source ~/osken-venv/bin/activate` |
| Check OS-Ken package | `python -m pip show os-ken` |
| Start Open vSwitch | `sudo systemctl start openvswitch-switch` |
| Check OVS | `sudo ovs-vsctl show` |
| Clean Mininet | `sudo mn -c` |
| Start Mininet | `sudo mn --topo single,4 --mac --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6633` |
| Test reachability | `pingall` at the Mininet prompt |
| Open host terminals | `xterm h1 h2 h3` at the Mininet prompt |
| Start server in h1 | `python3 -m server.notification_server` |
| Start client 1 in h2 | `python3 -m client.notification_client --id client1 --server 10.0.0.1` |
| Start client 2 in h3 | `python3 -m client.notification_client --id client2 --server 10.0.0.1` |
| Inspect flows | `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` |
| Run unit tests | `python -m unittest controller/test_emergency_controller.py -v` |
| Check syntax | `python3 -m compileall client common server controller` |
| List result files | `find results -maxdepth 1 -type f -print` |
| View latency results | `cat results/latency_client1.csv` |
| View flow statistics | `cat results/sdn_flow_stats.csv` |

---

# 18. Final Checklist Before Submission

- [ ] The controller starts with the documented command.
- [ ] Open vSwitch connects to the controller using OpenFlow 1.3.
- [ ] Mininet `pingall` succeeds.
- [ ] The server starts successfully.
- [ ] Multiple clients register successfully.
- [ ] Normal notifications reach registered clients.
- [ ] Emergency notifications reach registered clients.
- [ ] Emergency ACKs appear in the server terminal.
- [ ] Emergency-specific OpenFlow rules are visible.
- [ ] Latency records are generated.
- [ ] Flow statistics are generated.
- [ ] Congestion tests are conducted and documented.
- [ ] QoS behavior is tested if preferential queue treatment is claimed.
- [ ] The README matches the actual commands and dependencies used.
- [ ] Results are based on real measurements rather than assumed values.

## Conclusion

The Emergency Notification Network demonstrates how UDP socket programming and SDN can work together. The application provides subscriber registration, notification delivery, emergency acknowledgements, and latency measurement. The controller adds programmable traffic classification, flow prioritization, queue selection, DSCP marking, and flow-statistics collection.

The main lesson is that an application and a programmable network must be evaluated together: successful message delivery establishes application functionality, while installed flow rules and controlled performance experiments establish whether the SDN policy behaves as intended.

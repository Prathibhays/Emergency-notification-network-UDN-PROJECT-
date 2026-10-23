# Person 1 — UDP Emergency Notification Application

## Responsibilities
- UDP server
- Multiple subscriber registration
- Normal notifications on UDP/5000
- Emergency notifications on UDP/9999
- ACKs on UDP/5001
- Client-side latency measurement
- CSV logging

## Common ports
- Normal: 5000
- Emergency: 9999
- Registration/ACK: 5001

## Local test
Terminal 1:
python -m server.notification_server

Terminal 2:
python -m client.notification_client --id client1 --server 127.0.0.1

Then in the server:
normal Test normal message
emergency Fire detected in Block A

For the final Mininet run, the server will normally be h1 (10.0.0.1), and clients will be h2/h3/h4.

## Expected final files
server/notification_server.py
server/subscriber_manager.py
client/notification_client.py
common/protocol.py

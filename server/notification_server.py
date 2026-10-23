"""UDP emergency notification server.

Person 1 component:
- Registers multiple subscribers
- Sends normal traffic to UDP/5000
- Sends emergency traffic to UDP/9999
- Receives application-level ACKs on UDP/5001
"""

import argparse
import itertools
import socket
import threading
import time

from common.protocol import (
    ACK,
    CONTROL_PORT,
    EMERGENCY_PORT,
    TYPE_EMERGENCY,
    TYPE_NORMAL,
    NORMAL_PORT,
    build_notification,
    parse_ack,
    parse_register,
)
from server.subscriber_manager import SubscriberManager


class NotificationServer:
    def __init__(self, host: str, control_port: int = CONTROL_PORT):
        self.host = host
        self.control_port = control_port
        self.manager = SubscriberManager()
        self.next_message_id = itertools.count(1)
        self.running = True

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.control_socket.bind((host, control_port))

        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        print("=" * 58)
        print("UDP EMERGENCY NOTIFICATION SERVER")
        print("=" * 58)
        print(f"Control/ACK port : UDP {self.control_port}")
        print(f"Normal port      : UDP {NORMAL_PORT}")
        print(f"Emergency port   : UDP {EMERGENCY_PORT}")
        print("Waiting for subscribers...")
        print()

        threading.Thread(target=self._control_loop, daemon=True).start()
        self._command_loop()

    def _control_loop(self):
        while self.running:
            try:
                data, addr = self.control_socket.recvfrom(4096)
            except OSError:
                break

            try:
                text = data.decode("utf-8", errors="replace")
                if text.startswith("REGISTER|"):
                    client_id = parse_register(data)
                    self.manager.register(client_id, addr[0], time.time())
                    self.control_socket.sendto(
                        f"REGISTERED|{client_id}".encode("utf-8"), addr
                    )
                    print(f"[REGISTER] {client_id} from {addr[0]}")
                    print(f"[REGISTER] Subscribers: {len(self.manager)}")

                elif text.startswith(f"{ACK}|"):
                    message_id, client_id = parse_ack(data)
                    print(f"[ACK] Message {message_id} acknowledged by {client_id}")

                else:
                    print(f"[CONTROL] Unknown packet from {addr}: {text!r}")

            except (ValueError, UnicodeError) as exc:
                print(f"[CONTROL] Invalid packet from {addr}: {exc}")

    def send_notification(self, message_type: str, payload: str):
        subscribers = self.manager.all()
        if not subscribers:
            print("[WARN] No subscribers registered.")
            return

        message_id = next(self.next_message_id)
        timestamp = time.time()

        packet = build_notification(
            message_id=message_id,
            message_type=message_type,
            timestamp=timestamp,
            payload=payload,
        )

        destination_port = (
            EMERGENCY_PORT if message_type == TYPE_EMERGENCY else NORMAL_PORT
        )

        print()
        print(f"[SEND] Message ID : {message_id}")
        print(f"[SEND] Type       : {message_type}")
        print(f"[SEND] Destination: UDP/{destination_port}")
        print(f"[SEND] Subscribers: {len(subscribers)}")

        for subscriber in subscribers:
            try:
                self.send_socket.sendto(
                    packet, (subscriber.ip, destination_port)
                )
                print(f"       -> {subscriber.client_id} ({subscriber.ip})")
            except OSError as exc:
                print(f"       -> FAILED {subscriber.client_id}: {exc}")

    def _command_loop(self):
        print()
        print("Commands:")
        print("  normal <message>     Send normal notification")
        print("  emergency <message>  Send emergency notification")
        print("  list                 Show registered clients")
        print("  quit                 Stop server")
        print()

        while self.running:
            try:
                command = input("server> ").strip()
            except (EOFError, KeyboardInterrupt):
                command = "quit"

            if not command:
                continue

            if command.lower() == "list":
                subscribers = self.manager.all()
                if not subscribers:
                    print("No subscribers.")
                else:
                    for s in subscribers:
                        print(f"- {s.client_id}: {s.ip}")
                continue

            if command.lower() == "quit":
                self.running = False
                break

            prefix, separator, payload = command.partition(" ")
            if not separator or not payload.strip():
                print("Use: normal <message> OR emergency <message>")
                continue

            prefix = prefix.lower()
            if prefix == "normal":
                self.send_notification(TYPE_NORMAL, payload.strip())
            elif prefix == "emergency":
                self.send_notification(TYPE_EMERGENCY, payload.strip())
            else:
                print("Unknown command.")

        self.stop()

    def stop(self):
        self.running = False
        for sock in (self.control_socket, self.send_socket):
            try:
                sock.close()
            except OSError:
                pass
        print("Server stopped.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--control-port", type=int, default=CONTROL_PORT)
    args = parser.parse_args()

    NotificationServer(args.host, args.control_port).start()


if __name__ == "__main__":
    main()

"""UDP subscriber/client for the emergency notification system."""

import argparse
import csv
import os
import selectors
import socket
import time

from common.protocol import (
    CONTROL_PORT,
    EMERGENCY_PORT,
    NORMAL_PORT,
    TYPE_EMERGENCY,
    TYPE_NORMAL,
    build_ack,
    build_register,
    parse_notification,
)


class NotificationClient:
    def __init__(
        self,
        client_id: str,
        server_ip: str,
        server_control_port: int = CONTROL_PORT,
        normal_port: int = NORMAL_PORT,
        emergency_port: int = EMERGENCY_PORT,
        results_dir: str = "results",
    ):
        self.client_id = client_id
        self.server = (server_ip, server_control_port)
        self.normal_port = normal_port
        self.emergency_port = emergency_port
        self.results_dir = results_dir

        os.makedirs(results_dir, exist_ok=True)
        self.csv_path = os.path.join(
            results_dir, f"latency_{self.client_id}.csv"
        )

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.normal_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.normal_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.normal_socket.bind(("0.0.0.0", normal_port))

        self.emergency_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.emergency_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.emergency_socket.bind(("0.0.0.0", emergency_port))

        self.selector = selectors.DefaultSelector()
        self.selector.register(self.normal_socket, selectors.EVENT_READ, TYPE_NORMAL)
        self.selector.register(
            self.emergency_socket, selectors.EVENT_READ, TYPE_EMERGENCY
        )

        self._prepare_csv()

    def _prepare_csv(self):
        if os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0:
            return

        with open(self.csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "message_id",
                    "type",
                    "client_id",
                    "server_timestamp",
                    "receive_timestamp",
                    "latency_ms",
                ]
            )

    def register(self):
        self.control_socket.sendto(
            build_register(self.client_id), self.server
        )

        self.control_socket.settimeout(3)
        try:
            data, addr = self.control_socket.recvfrom(1024)
            text = data.decode("utf-8", errors="replace")
            if text == f"REGISTERED|{self.client_id}":
                print(f"[REGISTERED] {self.client_id} with server {addr[0]}")
                return True

            print(f"[REGISTER] Unexpected response: {text}")
            return False

        except socket.timeout:
            print("[REGISTER] No response from server.")
            return False
        finally:
            self.control_socket.settimeout(None)

    def run(self):
        print("=" * 58)
        print(f"UDP CLIENT: {self.client_id}")
        print("=" * 58)

        if not self.register():
            print("Registration failed. Exiting.")
            return

        print(f"Listening on UDP/{self.normal_port} for NORMAL traffic")
        print(f"Listening on UDP/{self.emergency_port} for EMERGENCY traffic")
        print("Press Ctrl+C to stop.")
        print()

        try:
            while True:
                events = self.selector.select(timeout=1)
                for key, _ in events:
                    data, addr = key.fileobj.recvfrom(65535)
                    self._handle_notification(data, addr)

        except KeyboardInterrupt:
            print("\nClient stopped.")
        finally:
            self.close()

    def _handle_notification(self, data: bytes, addr):
        receive_time = time.time()

        try:
            message_id, message_type, send_time, payload = parse_notification(data)
        except (ValueError, UnicodeError) as exc:
            print(f"[ERROR] Invalid notification from {addr}: {exc}")
            return

        latency_ms = max(0.0, (receive_time - send_time) * 1000)

        print()
        print("=" * 58)
        print(f"{message_type} NOTIFICATION")
        print("=" * 58)
        print(f"Message ID : {message_id}")
        print(f"From       : {addr[0]}:{addr[1]}")
        print(f"Message    : {payload}")
        print(f"Latency    : {latency_ms:.3f} ms")
        print("=" * 58)

        with open(self.csv_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    message_id,
                    message_type,
                    self.client_id,
                    f"{send_time:.6f}",
                    f"{receive_time:.6f}",
                    f"{latency_ms:.3f}",
                ]
            )

        # Delivery confirmation is sent for emergency messages.
        if message_type == TYPE_EMERGENCY:
            self.control_socket.sendto(
                build_ack(message_id, self.client_id),
                self.server,
            )
            print(f"[ACK] Sent ACK for message {message_id}")

    def close(self):
        try:
            self.selector.close()
        except Exception:
            pass

        for sock in (
            self.control_socket,
            self.normal_socket,
            self.emergency_socket,
        ):
            try:
                sock.close()
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Unique client ID, e.g. client1")
    parser.add_argument("--server", required=True, help="Server IP, e.g. 10.0.0.1")
    parser.add_argument("--control-port", type=int, default=CONTROL_PORT)
    parser.add_argument("--normal-port", type=int, default=NORMAL_PORT)
    parser.add_argument("--emergency-port", type=int, default=EMERGENCY_PORT)
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()

    client = NotificationClient(
        client_id=args.id,
        server_ip=args.server,
        server_control_port=args.control_port,
        normal_port=args.normal_port,
        emergency_port=args.emergency_port,
        results_dir=args.results_dir,
    )
    client.run()


if __name__ == "__main__":
    main()

"""Shared protocol constants and helpers for the UDP emergency notification project."""

NORMAL_PORT = 5000
EMERGENCY_PORT = 9999
CONTROL_PORT = 5001

TYPE_NORMAL = "NORMAL"
TYPE_EMERGENCY = "EMERGENCY"

REGISTER = "REGISTER"
ACK = "ACK"


def sanitize_payload(payload: str) -> str:
    """Keep the pipe-delimited protocol parseable."""
    return " ".join(str(payload).split()).replace("|", "/")


def build_notification(message_id: int, message_type: str, timestamp: float, payload: str) -> bytes:
    payload = sanitize_payload(payload)
    return f"{message_id}|{message_type}|{timestamp:.6f}|{payload}".encode("utf-8")


def parse_notification(data: bytes):
    """Return (message_id, message_type, timestamp, payload)."""
    text = data.decode("utf-8", errors="replace")
    parts = text.split("|", 3)
    if len(parts) != 4:
        raise ValueError(f"Invalid notification: {text!r}")

    message_id = int(parts[0])
    message_type = parts[1]
    timestamp = float(parts[2])
    payload = parts[3]
    return message_id, message_type, timestamp, payload


def build_register(client_id: str) -> bytes:
    return f"{REGISTER}|{client_id}".encode("utf-8")


def parse_register(data: bytes):
    text = data.decode("utf-8", errors="replace")
    parts = text.split("|", 1)
    if len(parts) != 2 or parts[0] != REGISTER:
        raise ValueError(f"Invalid registration: {text!r}")
    return parts[1].strip()


def build_ack(message_id: int, client_id: str) -> bytes:
    return f"{ACK}|{message_id}|{client_id}".encode("utf-8")


def parse_ack(data: bytes):
    text = data.decode("utf-8", errors="replace")
    parts = text.split("|")
    if len(parts) != 3 or parts[0] != ACK:
        raise ValueError(f"Invalid ACK: {text!r}")
    return int(parts[1]), parts[2].strip()

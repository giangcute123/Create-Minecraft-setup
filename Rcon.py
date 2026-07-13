"""
Minimal Source RCON protocol client (dung duoc voi Minecraft RCON).
Khong can thu vien ngoai.
"""
import socket
import struct

SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RconError(Exception):
    pass


def _send_packet(sock, request_id, ptype, body):
    payload = struct.pack("<ii", request_id, ptype) + body.encode("utf-8") + b"\x00\x00"
    packet = struct.pack("<i", len(payload)) + payload
    sock.sendall(packet)


def _read_packet(sock):
    raw_len = _recv_exact(sock, 4)
    (length,) = struct.unpack("<i", raw_len)
    data = _recv_exact(sock, length)
    req_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode("utf-8", errors="replace")
    return req_id, ptype, body


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RconError("Mat ket noi toi server khi doc du lieu.")
        buf += chunk
    return buf


def rcon_command(host, port, password, command, timeout=5):
    """Gui mot lenh qua RCON va tra ve chuoi ket qua. Nem RconError neu that bai."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        _send_packet(sock, 1, SERVERDATA_AUTH, password)
        req_id, ptype, _ = _read_packet(sock)
        if req_id == -1:
            raise RconError("Sai mat khau RCON.")

        _send_packet(sock, 2, SERVERDATA_EXECCOMMAND, command)
        _, _, body = _read_packet(sock)
        return body
      

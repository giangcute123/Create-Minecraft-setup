#!/usr/bin/env python3
"""
mcctl.py - Quan ly nhieu Minecraft server cung luc
=====================================================
Chay lenh nay tu THU MUC CHA chua cac thu muc server (moi thu muc con
duoc tao boi setup.py, co file mcserver_config.json).

Vi du:
    python mcctl.py list
    python mcctl.py start survival
    python mcctl.py stop survival
    python mcctl.py status
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time

import mc_common as mc
from rcon import rcon_command, RconError

PID_FILE = "server.pid"


def discover_servers():
    """Tra ve dict {ten_thu_muc: duong_dan_tuyet_doi} cho moi server tim thay."""
    servers = {}
    for entry in sorted(os.listdir(".")):
        if os.path.isdir(entry) and os.path.exists(os.path.join(entry, mc.CONFIG_FILE)):
            servers[entry] = os.path.abspath(entry)
    return servers


def is_running(server_dir):
    pid_path = os.path.join(server_dir, PID_FILE)
    if not os.path.exists(pid_path):
        return False, None
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return False, None

    try:
        import psutil  # type: ignore
        if psutil.pid_exists(pid):
            return True, pid
        return False, None
    except ImportError:
        # Fallback don gian, khong co psutil
        if platform.system() == "Windows":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            return (str(pid) in out), pid
        else:
            try:
                os.kill(pid, 0)
                return True, pid
            except (OSError, ProcessLookupError):
                return False, None


def cmd_list(args):
    servers = discover_servers()
    if not servers:
        print("Khong tim thay server nao trong thu muc hien tai.")
        print("(Chay lenh nay tu thu muc CHA cua cac thu muc server duoc tao boi setup.py)")
        return

    print(f"{'TEN':<20} {'LOAI':<10} {'PHIEN BAN':<12} {'PORT':<7} {'TRANG THAI'}")
    print("-" * 65)
    for name, path in servers.items():
        cfg = mc.load_config(path)
        running, pid = is_running(path)
        status = f"DANG CHAY (pid {pid})" if running else "da dung"
        print(f"{name:<20} {cfg.get('server_type', '?'):<10} {cfg.get('mc_version', '?'):<12} "
              f"{cfg.get('port', '?'):<7} {status}")


def cmd_start(args):
    servers = discover_servers()
    if args.name not in servers:
        print(f"Khong tim thay server '{args.name}'. Dung 'python mcctl.py list' de xem danh sach.")
        return
    server_dir = servers[args.name]

    running, pid = is_running(server_dir)
    if running:
        print(f"Server '{args.name}' da dang chay (pid {pid}).")
        return

    cfg = mc.load_config(server_dir)
    jar_name = cfg.get("jar_name", "server.jar")
    min_ram = cfg.get("min_ram", "1G")
    max_ram = cfg.get("max_ram", "4G")
    use_aikar_flags = cfg.get("use_aikar_flags", False)
    java = mc.which_java()
    if not java:
        print("!! Khong tim thay Java trong PATH.")
        return

    command = mc.build_java_command(java, jar_name, min_ram, max_ram, use_aikar_flags)
    os.makedirs(server_dir, exist_ok=True)
    console_log = open(os.path.join(server_dir, "console.log"), "a")

    kwargs = dict(cwd=server_dir, stdin=subprocess.DEVNULL, stdout=console_log, stderr=subprocess.STDOUT)
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(command, **kwargs)
    with open(os.path.join(server_dir, PID_FILE), "w") as f:
        f.write(str(proc.pid))

    print(f"Da khoi dong '{args.name}' (pid {proc.pid}). Log: {os.path.join(server_dir, 'console.log')}")
    print("Luu y: server chay nen, khong go lenh console truc tiep duoc.")
    print(f"Dung 'python mcctl.py stop {args.name}' de dung, hoac dung RCON qua manage.py status.")


def cmd_stop(args):
    servers = discover_servers()
    if args.name not in servers:
        print(f"Khong tim thay server '{args.name}'.")
        return
    server_dir = servers[args.name]

    running, pid = is_running(server_dir)
    if not running:
        print(f"Server '{args.name}' khong dang chay.")
        return

    cfg = mc.load_config(server_dir)
    props = {}
    props_path = os.path.join(server_dir, "server.properties")
    if os.path.exists(props_path):
        with open(props_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    props[k] = v

    stopped_gracefully = False
    if props.get("enable-rcon") == "true" or cfg.get("rcon_enabled"):
        port = int(props.get("rcon.port", cfg.get("rcon_port", 25575)))
        password = props.get("rcon.password", cfg.get("rcon_password", ""))
        try:
            rcon_command("127.0.0.1", port, password, "stop")
            print(f"Da gui lenh 'stop' qua RCON toi '{args.name}'. Dang cho tat...")
            for _ in range(30):
                time.sleep(1)
                if not is_running(server_dir)[0]:
                    stopped_gracefully = True
                    break
        except (RconError, ConnectionRefusedError, OSError):
            pass

    if not stopped_gracefully:
        print("Dang dung server bang tin hieu he thong (khong qua RCON)...")
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                os.kill(pid, 15)  # SIGTERM
        except (OSError, ProcessLookupError):
            pass

    pid_path = os.path.join(server_dir, PID_FILE)
    if os.path.exists(pid_path):
        os.remove(pid_path)
    print(f"Da dung '{args.name}'.")


def cmd_status(args):
    servers = discover_servers()
    if not servers:
        print("Khong tim thay server nao.")
        return
    for name, path in servers.items():
        running, pid = is_running(path)
        print(f"\n=== {name} ===")
        print(f"Trang thai: {'DANG CHAY (pid ' + str(pid) + ')' if running else 'da dung'}")
        if not running:
            continue
        cfg = mc.load_config(path)
        props = {}
        props_path = os.path.join(path, "server.properties")
        if os.path.exists(props_path):
            with open(props_path) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        props[k] = v
        if props.get("enable-rcon") == "true" or cfg.get("rcon_enabled"):
            port = int(props.get("rcon.port", cfg.get("rcon_port", 25575)))
            password = props.get("rcon.password", cfg.get("rcon_password", ""))
            try:
                print(rcon_command("127.0.0.1", port, password, "list"))
            except (RconError, ConnectionRefusedError, OSError) as e:
                print(f"(Khong lay duoc danh sach nguoi choi: {e})")
        else:
            print("(RCON chua bat - khong xem duoc nguoi choi online)")


def build_parser():
    parser = argparse.ArgumentParser(description="Quan ly nhieu Minecraft server cung luc")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Liet ke tat ca server tim thay")
    p_list.set_defaults(func=cmd_list)

    p_start = sub.add_parser("start", help="Khoi dong mot server (chay nen)")
    p_start.add_argument("name")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Dung mot server (uu tien dung qua RCON)")
    p_stop.add_argument("name")
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="Xem trang thai + nguoi choi online cua tat ca server")
    p_status.set_defaults(func=cmd_status)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
          

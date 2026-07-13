#!/usr/bin/env python3
"""
Minecraft Server - Cong cu quan ly nang cao
=============================================
Chay lenh nay BEN TRONG thu muc server (noi co server.properties / mcserver_config.json).

Vi du:
    python ../manage.py backup
    python ../manage.py restore
    python ../manage.py update
    python ../manage.py watchdog
    python ../manage.py whitelist add Steve
    python ../manage.py ops add Steve
    python ../manage.py ban add Griefer123 --reason "Pha hoai"
    python ../manage.py install "Lithium"
    python ../manage.py status
    python ../manage.py logs --lines 100
    python ../manage.py notify test
    python ../manage.py service install
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

import mc_common as mc
from rcon import rcon_command, RconError


# ---------------------------------------------------------------------------
# Config / tien ich chung
# ---------------------------------------------------------------------------

def load_config():
    if not os.path.exists(mc.CONFIG_FILE):
        print(f"!! Khong tim thay {mc.CONFIG_FILE} trong thu muc hien tai.")
        print("   Hay chay lenh nay ben trong thu muc server (duoc tao boi setup.py).")
        return {}
    return mc.load_config(".")


def read_properties(path="server.properties"):
    props = {}
    if not os.path.exists(path):
        return props
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    return props


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


# ---------------------------------------------------------------------------
# 1) BACKUP
# ---------------------------------------------------------------------------

def cmd_backup(args):
    world_dirs = [d for d in os.listdir(".") if os.path.isdir(d) and d.startswith("world")]
    if not world_dirs:
        print("Khong tim thay thu muc world nao (world, world_nether, ...). Server da chay lan nao chua?")
        return None

    os.makedirs("backups", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"backup-{timestamp}.zip"
    backup_path = os.path.join("backups", backup_name)

    print(f"Dang sao luu: {', '.join(world_dirs)} -> {backup_path}")
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for world_dir in world_dirs:
            for root, _, files in os.walk(world_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    zf.write(full_path, full_path)

    size_mb = os.path.getsize(backup_path) / (1024 * 1024)
    print(f"Da tao backup: {backup_path} ({size_mb:.1f} MB)")

    keep = getattr(args, "keep", 5)
    backups = sorted(
        (f for f in os.listdir("backups") if f.startswith("backup-") and f.endswith(".zip")),
        reverse=True,
    )
    for old in backups[keep:]:
        os.remove(os.path.join("backups", old))
        print(f"Da xoa backup cu: {old}")

    cfg = load_config()
    if cfg:
        mc.notify(cfg, f"💾 Backup hoan tat: {backup_name} ({size_mb:.1f} MB)")

    if not getattr(args, "_quiet_tip", False):
        print()
        print("Meo: de backup tu dong dinh ky, dat lich chay lenh nay:")
        if platform.system() == "Windows":
            print(r'  schtasks /create /tn "MC Backup" /tr "python manage.py backup" /sc daily /st 03:00')
        else:
            print('  crontab -e   # roi them dong:')
            print('  0 3 * * * cd /duong/dan/toi/server && python3 ../manage.py backup')

    return backup_path


# ---------------------------------------------------------------------------
# 2) RESTORE
# ---------------------------------------------------------------------------

def cmd_restore(args):
    if not os.path.isdir("backups"):
        print("Khong co thu muc backups/. Chua co ban sao luu nao.")
        return
    backups = sorted(f for f in os.listdir("backups") if f.endswith(".zip"))
    if not backups:
        print("Khong co backup nao trong backups/.")
        return

    target = args.file
    if target:
        if target not in backups:
            print(f"Khong tim thay '{target}' trong backups/.")
            return
    else:
        print("Cac backup co san (moi nhat o cuoi):")
        for i, b in enumerate(backups):
            print(f"  [{i}] {b}")
        choice = input("Chon so thu tu de khoi phuc (Enter de huy): ").strip()
        if not choice:
            print("Da huy.")
            return
        try:
            target = backups[int(choice)]
        except (ValueError, IndexError):
            print("Lua chon khong hop le.")
            return

    print()
    print(f"CANH BAO: thao tac nay se GHI DE cac thu muc world hien tai bang noi dung trong '{target}'.")
    print("Hay dam bao server DANG DUNG truoc khi khoi phuc.")
    confirm = input("Go 'yes' de xac nhan: ").strip()
    if confirm != "yes":
        print("Da huy.")
        return

    backup_path = os.path.join("backups", target)
    with zipfile.ZipFile(backup_path, "r") as zf:
        zf.extractall(".")
    print(f"Da khoi phuc tu '{target}'. Khoi dong lai server de ap dung.")


# ---------------------------------------------------------------------------
# 3) UPDATE
# ---------------------------------------------------------------------------

def cmd_update(args):
    cfg = load_config()
    if not cfg:
        return
    server_type = cfg.get("server_type")
    jar_name = cfg.get("jar_name", "server.jar")
    current_version = cfg.get("mc_version")

    print(f"Phien ban hien tai: {current_version} ({server_type})")
    print("Dang sao luu world truoc khi cap nhat (de phong loi)...")

    class _Args:
        keep = 5
        _quiet_tip = True

    cmd_backup(_Args())
    print()

    target_version = args.version

    if server_type == "vanilla":
        latest = mc.list_vanilla_versions()
        target_version = target_version or ask("Phien ban muon cap nhat len", latest)
        url = mc.get_vanilla_download_url(target_version)
        mc.download_file(url, jar_name)

    elif server_type == "paper":
        latest = mc.list_paper_versions()
        target_version = target_version or ask("Phien ban muon cap nhat len", latest)
        url, _ = mc.get_paper_download_url(target_version)
        mc.download_file(url, jar_name)

    elif server_type == "fabric":
        target_version = target_version or current_version
        print(f"Dang tai lai Fabric installer va cap nhat loader cho {target_version}...")
        installer_url, installer_name = mc.get_fabric_installer_url()
        mc.download_file(installer_url, installer_name)
        java = mc.which_java()
        if not java:
            print("!! Khong co Java, khong the tu chay installer.")
            return
        subprocess.run(
            [java, "-jar", installer_name, "server", "-mcversion", target_version, "-downloadMinecraft"],
            check=False,
        )
    else:
        print("!! Khong xac dinh duoc loai server trong mcserver_config.json.")
        return

    cfg["mc_version"] = target_version
    mc.save_config(cfg)
    print(f"\nDa cap nhat server len phien ban {target_version}. Khoi dong lai de ap dung.")


# ---------------------------------------------------------------------------
# 4) WATCHDOG (console tuong tac + tu khoi dong lai + thong bao)
# ---------------------------------------------------------------------------

def _stdin_forwarder(proc, stop_event):
    """Doc lenh nguoi dung go va gui vao stdin cua server dang chay."""
    while not stop_event.is_set():
        try:
            line = sys.stdin.readline()
        except Exception:
            return
        if not line:
            return
        try:
            proc.stdin.write(line.encode())
            proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            return
        if stop_event.is_set():
            return


def _tail_join_leave(cfg, stop_event, log_path=os.path.join("logs", "latest.log")):
    """Theo doi log server de bao khi co nguoi vao/roi (chi dung khi da cau hinh thong bao)."""
    if not (cfg.get("discord_webhook") or cfg.get("telegram_bot_token")):
        return
    for _ in range(30):
        if stop_event.is_set():
            return
        if os.path.exists(log_path):
            break
        time.sleep(1)
    else:
        return

    join_re = re.compile(r": (\w+) joined the game")
    leave_re = re.compile(r": (\w+) left the game")

    try:
        with open(log_path, "r", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    time.sleep(1)
                    continue
                m = join_re.search(line)
                if m:
                    mc.notify(cfg, f"🟢 {m.group(1)} da vao server")
                    continue
                m = leave_re.search(line)
                if m:
                    mc.notify(cfg, f"🔴 {m.group(1)} da roi server")
    except OSError:
        return


def cmd_watchdog(args):
    cfg = load_config()
    jar_name = cfg.get("jar_name", "server.jar")
    min_ram = cfg.get("min_ram", "1G")
    max_ram = cfg.get("max_ram", "4G")
    use_aikar_flags = cfg.get("use_aikar_flags", False)
    java = mc.which_java()
    if not java:
        print("!! Khong tim thay Java trong PATH.")
        return

    max_restarts = args.max_restarts
    delay = args.delay
    restart_count = 0
    log_path = "watchdog.log"

    def log(msg):
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    print("Che do watchdog: go lenh va nhan Enter de gui toi console server (vd: say hello, stop).")
    print("Nhan Ctrl+C de dung watchdog hoan toan.\n")

    log(f"Watchdog bat dau. jar={jar_name} ram={min_ram}/{max_ram} aikar_flags={use_aikar_flags}")

    tail_stop = threading.Event()
    tail_thread = threading.Thread(target=_tail_join_leave, args=(cfg, tail_stop), daemon=True)
    tail_thread.start()

    try:
        while True:
            log(f"Khoi dong server (lan chay #{restart_count + 1})...")
            command = mc.build_java_command(java, jar_name, min_ram, max_ram, use_aikar_flags)
            start_time = time.time()

            proc = subprocess.Popen(command, stdin=subprocess.PIPE)
            stdin_stop = threading.Event()
            forwarder = threading.Thread(target=_stdin_forwarder, args=(proc, stdin_stop), daemon=True)
            forwarder.start()

            proc.wait()
            stdin_stop.set()
            runtime = time.time() - start_time
            log(f"Server da dung voi ma thoat {proc.returncode} (chay {runtime:.0f} giay).")

            if runtime < 10:
                restart_count += 1
                mc.notify(cfg, f"⚠️ Server crash sau {runtime:.0f}s (lan {restart_count}/{max_restarts}). Dang tu khoi dong lai...")
            else:
                restart_count = 0

            if restart_count >= max_restarts:
                log(f"Da vuot qua {max_restarts} lan crash lien tiep. Dung watchdog de kiem tra loi.")
                mc.notify(cfg, f"🛑 Server crash lien tuc {max_restarts} lan. Watchdog da dung, can kiem tra thu cong.")
                break

            log(f"Tu dong khoi dong lai sau {delay} giay... (Ctrl+C de huy)")
            time.sleep(delay)
    except KeyboardInterrupt:
        log("Watchdog da bi dung boi nguoi dung.")
    finally:
        tail_stop.set()


# ---------------------------------------------------------------------------
# 5) WHITELIST / OPS / BAN
# ---------------------------------------------------------------------------

def get_mojang_profile(username):
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        data = mc.http_get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Khong tim thay tai khoan Minecraft ten '{username}'.")
        raise
    raw_uuid = data["id"]
    uuid = f"{raw_uuid[0:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}-{raw_uuid[16:20]}-{raw_uuid[20:32]}"
    return uuid, data["name"]


def load_json_list(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save_json_list(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def cmd_playerlist(args):
    file_map = {
        "whitelist": "whitelist.json",
        "ops": "ops.json",
        "ban": "banned-players.json",
    }
    path = file_map[args.list_name]
    entries = load_json_list(path)

    if args.action == "remove":
        before = len(entries)
        entries = [e for e in entries if e.get("name", "").lower() != args.username.lower()]
        if len(entries) == before:
            print(f"'{args.username}' khong co trong {path}.")
            return
        save_json_list(path, entries)
        print(f"Da xoa '{args.username}' khoi {path}.")
        return

    if any(e.get("name", "").lower() == args.username.lower() for e in entries):
        print(f"'{args.username}' da co trong {path} roi.")
        return

    try:
        uuid, real_name = get_mojang_profile(args.username)
    except ValueError as e:
        print(f"!! {e}")
        return
    except urllib.error.URLError as e:
        print(f"!! Loi mang khi tra cuu UUID: {e}")
        return

    if args.list_name == "whitelist":
        entries.append({"uuid": uuid, "name": real_name})
    elif args.list_name == "ops":
        entries.append({"uuid": uuid, "name": real_name, "level": 4, "bypassesPlayerLimit": False})
    elif args.list_name == "ban":
        entries.append({
            "uuid": uuid,
            "name": real_name,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000"),
            "source": "Server",
            "expires": "forever",
            "reason": args.reason or "Banned by an operator.",
        })

    save_json_list(path, entries)
    print(f"Da them '{real_name}' vao {path}.")
    print("Luu y: neu server dang chay, hay khoi dong lai hoac dung lenh trong-game tuong ung")
    print("       (/whitelist reload, /op, /ban) de ap dung ngay lap tuc.")


# ---------------------------------------------------------------------------
# 6) CAI PLUGIN / MOD (qua Modrinth)
# ---------------------------------------------------------------------------

MODRINTH_API = "https://api.modrinth.com/v2"


def cmd_install(args):
    cfg = load_config()
    server_type = cfg.get("server_type")
    mc_version = cfg.get("mc_version")

    if server_type == "vanilla":
        print("!! Server Vanilla khong ho tro plugin/mod. Hay tao server Paper (plugin) hoac Fabric (mod).")
        return

    loader = "fabric" if server_type == "fabric" else "paper"
    target_dir = "mods" if loader == "fabric" else "plugins"
    os.makedirs(target_dir, exist_ok=True)

    print(f"Dang tim '{args.query}' cho {loader}...")
    search_url = f"{MODRINTH_API}/search?query={urllib.parse.quote(args.query)}&limit=8"
    try:
        results = mc.http_get_json(search_url)
    except urllib.error.URLError as e:
        print(f"!! Loi mang khi tim kiem tren Modrinth: {e}")
        return

    hits = [h for h in results.get("hits", []) if loader in h.get("display_categories", []) + h.get("categories", [])]
    if not hits:
        hits = results.get("hits", [])
    if not hits:
        print("Khong tim thay ket qua nao. Thu tu khoa khac.")
        return

    print()
    for i, h in enumerate(hits[:8]):
        desc = h.get("description", "")[:70]
        print(f"  [{i}] {h['title']}  -  {desc}")
    print()
    choice = input("Chon so thu tu de cai dat (Enter de huy): ").strip()
    if not choice:
        print("Da huy.")
        return
    try:
        project = hits[int(choice)]
    except (ValueError, IndexError):
        print("Lua chon khong hop le.")
        return

    project_id = project["project_id"]
    versions_url = f"{MODRINTH_API}/project/{project_id}/version"
    versions = mc.http_get_json(versions_url)

    matching = [
        v for v in versions
        if loader in v.get("loaders", []) and (not mc_version or mc_version in v.get("game_versions", []))
    ]
    chosen_version = matching[0] if matching else (versions[0] if versions else None)
    if not chosen_version:
        print("Khong tim thay file nao de tai cho project nay.")
        return

    file_info = next((f for f in chosen_version["files"] if f.get("primary")), chosen_version["files"][0])
    dest_path = os.path.join(target_dir, file_info["filename"])
    print(f"Dang tai: {file_info['filename']} -> {target_dir}/")
    mc.download_file(file_info["url"], dest_path)
    print(f"Da cai dat '{project['title']}' vao thu muc {target_dir}/.")
    print("Khoi dong lai server de ap dung.")


# ---------------------------------------------------------------------------
# 7) STATUS
# ---------------------------------------------------------------------------

def find_java_process(jar_name):
    try:
        import psutil  # type: ignore
    except ImportError:
        return None, "psutil_missing"

    for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info", "cpu_percent"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any(jar_name in part for part in cmdline):
                return proc, None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None, "not_found"


def cmd_status(args):
    cfg = load_config()
    jar_name = cfg.get("jar_name", "server.jar")

    print("=== Trang thai tien trinh ===")
    proc, err = find_java_process(jar_name)
    if err == "psutil_missing":
        print("(Cai 'pip install psutil' de xem chi tiet RAM/CPU cua tien trinh Java.)")
        if platform.system() == "Windows":
            out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
            running = "java.exe" in out
        else:
            out = subprocess.run(["pgrep", "-f", jar_name], capture_output=True, text=True).stdout
            running = bool(out.strip())
        print(f"Java dang chay: {'CO' if running else 'KHONG'}")
    elif err == "not_found":
        print("Khong tim thay tien trinh server dang chay (jar khong khop hoac server chua khoi dong).")
    else:
        proc.cpu_percent(interval=0.5)
        mem_mb = proc.info["memory_info"].rss / (1024 * 1024)
        cpu = proc.cpu_percent(interval=0.5)
        print(f"PID: {proc.pid}")
        print(f"RAM dang dung: {mem_mb:.0f} MB")
        print(f"CPU: {cpu:.1f}%")

    print()
    print("=== Nguoi choi online (qua RCON) ===")
    props = read_properties()
    rcon_enabled = props.get("enable-rcon", "false") == "true" or cfg.get("rcon_enabled")
    if not rcon_enabled:
        print("RCON chua duoc bat. Bat trong server.properties (enable-rcon=true) de dung chuc nang nay.")
        return

    port = int(props.get("rcon.port", cfg.get("rcon_port", 25575)))
    password = props.get("rcon.password", cfg.get("rcon_password", ""))
    try:
        response = rcon_command("127.0.0.1", port, password, "list")
        print(response)
    except RconError as e:
        print(f"!! Loi RCON: {e}")
    except (ConnectionRefusedError, OSError):
        print("Khong ket noi duoc RCON. Server co dang chay khong?")


# --------------------------------------------------------------------

#!/usr/bin/env python3
"""
Minecraft Server Auto-Setup
============================
Tu dong tai va cau hinh Minecraft server: Vanilla, Paper/Spigot, hoac Fabric.
Chay tren ca Windows va Linux.

Cach dung:
    python setup.py

Yeu cau: Python 3.7+ va Java da duoc cai dat tren may.
"""

import os
import platform
import subprocess
import sys
import urllib.error

import mc_common as mc


def ask(prompt, default=None, choices=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default is not None:
            val = default
        if choices and val not in choices:
            print(f"  Vui long chon mot trong: {', '.join(choices)}")
            continue
        return val


def check_java():
    java = mc.which_java()
    if not java:
        print("!! Khong tim thay Java trong PATH. Hay cai dat Java (JDK 17+ khuyen nghi)")
        print("   truoc khi khoi dong server. Setup se tiep tuc nhung server se khong chay duoc.")
        return None
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True)
        version_line = (out.stderr or out.stdout).splitlines()[0]
        print(f"Java tim thay: {version_line}")
    except Exception:
        print("Java tim thay nhung khong doc duoc phien ban.")
    return java


def write_eula(server_dir):
    with open(os.path.join(server_dir, "eula.txt"), "w") as f:
        f.write("# Duoc tao tu dong boi minecraft-server-setup\n")
        f.write("eula=true\n")


def write_server_properties(server_dir, port, max_players, motd, difficulty, gamemode, online_mode):
    props = {
        "server-port": port,
        "max-players": max_players,
        "motd": motd,
        "difficulty": difficulty,
        "gamemode": gamemode,
        "online-mode": "true" if online_mode else "false",
        "pvp": "true",
        "spawn-protection": "16",
        "view-distance": "10",
    }
    path = os.path.join(server_dir, "server.properties")
    with open(path, "w") as f:
        for k, v in props.items():
            f.write(f"{k}={v}\n")


def write_start_scripts(server_dir, jar_name, min_ram, max_ram, use_aikar_flags):
    flags = mc.AIKAR_FLAGS if use_aikar_flags else ""

    sh_path = os.path.join(server_dir, "start.sh")
    with open(sh_path, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write(f'java -Xms{min_ram} -Xmx{max_ram} {flags} -jar "{jar_name}" nogui\n')
    try:
        os.chmod(sh_path, 0o755)
    except Exception:
        pass

    bat_path = os.path.join(server_dir, "start.bat")
    with open(bat_path, "w", newline="\r\n") as f:
        f.write("@echo off\n")
        f.write(f'java -Xms{min_ram} -Xmx{max_ram} {flags} -jar "{jar_name}" nogui\n')
        f.write("pause\n")


def main():
    print("=" * 60)
    print(" MINECRAFT SERVER AUTO-SETUP")
    print("=" * 60)
    print(f"He dieu hanh hien tai: {platform.system()}")
    check_java()
    print()

    server_type = ask(
        "Loai server ban muon tao (vanilla / paper / fabric)",
        default="vanilla",
        choices=["vanilla", "paper", "fabric"],
    )

    folder_name = ask("Ten thu muc server", default=f"mc-server-{server_type}")
    server_dir = os.path.join(os.getcwd(), folder_name)
    os.makedirs(server_dir, exist_ok=True)

    jar_name = "server.jar"

    print()
    if server_type == "vanilla":
        latest = mc.list_vanilla_versions()
        mc_version = ask("Nhap phien ban Minecraft muon dung", default=latest)
        url = mc.get_vanilla_download_url(mc_version)
        mc.download_file(url, os.path.join(server_dir, jar_name))

    elif server_type == "paper":
        latest = mc.list_paper_versions()
        mc_version = ask("Nhap phien ban Minecraft muon dung", default=latest)
        url, remote_name = mc.get_paper_download_url(mc_version)
        mc.download_file(url, os.path.join(server_dir, jar_name))

    elif server_type == "fabric":
        latest = mc.list_fabric_game_versions()
        mc_version = ask("Nhap phien ban Minecraft muon dung", default=latest)
        installer_url, installer_name = mc.get_fabric_installer_url()
        installer_path = os.path.join(server_dir, installer_name)
        mc.download_file(installer_url, installer_path)
        java = mc.which_java()
        if java:
            print("  Dang chay Fabric installer de tai server + loader...")
            subprocess.run(
                [java, "-jar", installer_name, "server", "-mcversion", mc_version, "-downloadMinecraft"],
                cwd=server_dir,
                check=False,
            )
            if os.path.exists(os.path.join(server_dir, "fabric-server-launch.jar")):
                jar_name = "fabric-server-launch.jar"
        else:
            print("  Java khong co san, khong the chay Fabric installer tu dong.")
            print(f"  Hay chay thu cong: java -jar {installer_name} server -mcversion {mc_version} -downloadMinecraft")

    print()
    print("Cau hinh server.properties:")
    port = ask("Cong (port)", default="25565")
    max_players = ask("So nguoi choi toi da", default="20")
    motd = ask("MOTD (dong chao)", default="A Minecraft Server")
    difficulty = ask("Do kho (peaceful/easy/normal/hard)", default="normal",
                      choices=["peaceful", "easy", "normal", "hard"])
    gamemode = ask("Che do choi (survival/creative/adventure/spectator)", default="survival",
                    choices=["survival", "creative", "adventure", "spectator"])
    online_mode = ask("Yeu cau tai khoan Minecraft chinh chu? (yes/no)", default="yes",
                       choices=["yes", "no"]) == "yes"

    print()
    print("RCON cho phep manage.py xem trang thai / nguoi choi online tu xa.")
    enable_rcon = ask("Bat RCON de dung voi manage.py status? (yes/no)", default="yes",
                       choices=["yes", "no"]) == "yes"
    rcon_port = "25575"
    rcon_password = ""
    if enable_rcon:
        rcon_port = ask("Cong RCON", default="25575")
        rcon_password = ask("Mat khau RCON", default="changeme123")

    write_eula(server_dir)
    write_server_properties(server_dir, port, max_players, motd, difficulty, gamemode, online_mode)

    if enable_rcon:
        with open(os.path.join(server_dir, "server.properties"), "a") as f:
            f.write("enable-rcon=true\n")
            f.write(f"rcon.port={rcon_port}\n")
            f.write(f"rcon.password={rcon_password}\n")

    print()
    print("Cau hinh RAM cho server:")
    min_ram = ask("RAM toi thieu (vd: 1G)", default="1G")
    max_ram = ask("RAM toi da (vd: 4G)", default="4G")
    use_aikar_flags = ask(
        "Dung Aikar's flags (JVM flags toi uu, khuyen nghi neu RAM >= 4G)? (yes/no)",
        default="yes" if max_ram.upper().endswith("G") and int(max_ram[:-1] or 0) >= 4 else "no",
        choices=["yes", "no"],
    ) == "yes"

    write_start_scripts(server_dir, jar_name, min_ram, max_ram, use_aikar_flags)

    print()
    print("Thong bao Discord/Telegram khi server crash, co nguoi join/leave, backup xong (tuy chon).")
    setup_notify = ask("Ban co muon cau hinh thong bao ngay bay gio? (yes/no)", default="no",
                        choices=["yes", "no"]) == "yes"
    discord_webhook = ""
    telegram_bot_token = ""
    telegram_chat_id = ""
    if setup_notify:
        channel = ask("Kenh thong bao (discord/telegram/ca hai)", default="discord",
                       choices=["discord", "telegram", "ca hai"])
        if channel in ("discord", "ca hai"):
            discord_webhook = ask("Discord webhook URL", default="")
        if channel in ("telegram", "ca hai"):
            telegram_bot_token = ask("Telegram bot token", default="")
            telegram_chat_id = ask("Telegram chat ID", default="")

    loader = "fabric" if server_type == "fabric" else None
    cfg = {
        "server_type": server_type,
        "mc_version": mc_version,
        "jar_name": jar_name,
        "loader": loader,
        "min_ram": min_ram,
        "max_ram": max_ram,
        "use_aikar_flags": use_aikar_flags,
        "port": int(port),
        "rcon_enabled": enable_rcon,
        "rcon_port": int(rcon_port),
        "rcon_password": rcon_password,
    }
    if discord_webhook:
        cfg["discord_webhook"] = discord_webhook
    if telegram_bot_token:
        cfg["telegram_bot_token"] = telegram_bot_token
        cfg["telegram_chat_id"] = telegram_chat_id

    mc.save_config(cfg, server_dir)

    print()
    print("=" * 60)
    print(f"HOAN TAT! Server da duoc tao tai: {server_dir}")
    print("Cach khoi dong:")
    print(f"  - Windows: mo thu muc va chay start.bat")
    print(f"  - Linux/macOS: cd {folder_name} && ./start.sh")
    print()
    print("Quan ly nang cao (chay ben trong thu muc server):")
    print("  python ../manage.py backup                    -> sao luu world")
    print("  python ../manage.py restore                    -> khoi phuc tu backup")
    print("  python ../manage.py update                     -> cap nhat len phien ban moi")
    print("  python ../manage.py watchdog                    -> chay server, tu restart, go lenh console")
    print("  python ../manage.py whitelist add TEN           -> them whitelist")
    print("  python ../manage.py ops add TEN                 -> cap quyen op")
    print("  python ../manage.py ban add TEN                 -> ban nguoi choi")
    print("  python ../manage.py install \"ten mod/plugin\"    -> tim va cai mod/plugin")
    print("  python ../manage.py status                      -> xem RAM/CPU + nguoi choi online")
    print("  python ../manage.py logs                        -> xem log gan nhat")
    print("  python ../manage.py notify test                 -> gui thu thong bao")
    print("  python ../manage.py service install              -> tao file chay nen (systemd/service)")
    print("  python ../mcctl.py list                          -> quan ly nhieu server cung luc")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"\nLoi mang: {e}. Kiem tra ket noi internet roi thu lai.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDa huy.")
        sys.exit(1)
    except Exception as e:
        print(f"\nLoi: {e}")
        sys.exit(1)
      

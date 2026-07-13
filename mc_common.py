"""
mc_common.py - Cac ham dung chung giua setup.py va manage.py
"""
import json
import os
import shutil
import urllib.error
import urllib.request

CONFIG_FILE = "mcserver_config.json"

# JVM flags toi uu cho Minecraft, de xuat boi Aikar (PaperMC).
# Phu hop nhat khi RAM cap >= 4G.
AIKAR_FLAGS = (
    "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 "
    "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch "
    "-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M "
    "-XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 "
    "-XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 "
    "-XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem "
    "-XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true"
)


# ---------------------------------------------------------------------------
# HTTP tien ich
# ---------------------------------------------------------------------------

def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mc-server-setup/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url, dest_path):
    print(f"  Dang tai: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "mc-server-setup/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
        total = resp.getheader("Content-Length")
        total = int(total) if total else None
        downloaded = 0
        chunk_size = 1024 * 256
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  Tien do: {pct}% ({downloaded // 1024} KB / {total // 1024} KB)", end="")
        print()
    print(f"  Da luu vao: {dest_path}")


# ---------------------------------------------------------------------------
# Vanilla
# ---------------------------------------------------------------------------

VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"


def get_vanilla_download_url(mc_version):
    manifest = http_get_json(VERSION_MANIFEST_URL)
    entry = next((v for v in manifest["versions"] if v["id"] == mc_version), None)
    if not entry:
        raise ValueError(f"Khong tim thay phien ban '{mc_version}'.")
    version_meta = http_get_json(entry["url"])
    server_info = version_meta.get("downloads", {}).get("server")
    if not server_info:
        raise ValueError(f"Phien ban '{mc_version}' khong co server jar (co the qua cu).")
    return server_info["url"]


def list_vanilla_versions(limit=15):
    manifest = http_get_json(VERSION_MANIFEST_URL)
    releases = [v["id"] for v in manifest["versions"] if v["type"] == "release"]
    print(f"Cac phien ban release moi nhat (moi nhat: {manifest['latest']['release']}):")
    print("  " + ", ".join(releases[:limit]))
    return manifest["latest"]["release"]


# ---------------------------------------------------------------------------
# Paper
# ---------------------------------------------------------------------------

def get_paper_download_url(mc_version):
    builds_info = http_get_json(f"https://api.papermc.io/v2/projects/paper/versions/{mc_version}")
    build = builds_info["builds"][-1]
    build_info = http_get_json(
        f"https://api.papermc.io/v2/projects/paper/versions/{mc_version}/builds/{build}"
    )
    filename = build_info["downloads"]["application"]["name"]
    url = (
        f"https://api.papermc.io/v2/projects/paper/versions/{mc_version}"
        f"/builds/{build}/downloads/{filename}"
    )
    return url, filename


def list_paper_versions(limit=15):
    info = http_get_json("https://api.papermc.io/v2/projects/paper")
    versions = info["versions"]
    print("Cac phien ban Paper ho tro (moi nhat o cuoi):")
    print("  " + ", ".join(versions[-limit:]))
    return versions[-1]


# ---------------------------------------------------------------------------
# Fabric
# ---------------------------------------------------------------------------

def get_fabric_installer_url():
    installers = http_get_json("https://meta.fabricmc.net/v2/versions/installer")
    latest = installers[0]
    return latest["url"], f"fabric-installer-{latest['version']}.jar"


def list_fabric_game_versions(limit=15):
    versions = http_get_json("https://meta.fabricmc.net/v2/versions/game")
    stable = [v["version"] for v in versions if v["stable"]]
    print("Cac phien ban Minecraft on dinh ho tro boi Fabric:")
    print("  " + ", ".join(stable[:limit]))
    return stable[0]


# ---------------------------------------------------------------------------
# Config (mcserver_config.json)
# ---------------------------------------------------------------------------

def load_config(directory="."):
    path = os.path.join(directory, CONFIG_FILE)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_config(cfg, directory="."):
    path = os.path.join(directory, CONFIG_FILE)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def build_java_command(java, jar_name, min_ram, max_ram, use_aikar_flags, extra_args=""):
    flags = AIKAR_FLAGS if use_aikar_flags else ""
    parts = [java, f"-Xms{min_ram}", f"-Xmx{max_ram}"]
    if flags:
        parts += flags.split(" ")
    if extra_args:
        parts += extra_args.split(" ")
    parts += ["-jar", jar_name, "nogui"]
    return parts


# ---------------------------------------------------------------------------
# Thong bao Discord / Telegram
# ---------------------------------------------------------------------------

def notify_discord(webhook_url, message):
    body = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.URLError:
        return False


def notify_telegram(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.URLError:
        return False


def notify(cfg, message):
    """Gui thong bao toi moi kenh da cau hinh trong cfg. Khong nem loi neu that bai."""
    sent = False
    webhook = cfg.get("discord_webhook")
    if webhook:
        sent = notify_discord(webhook, message) or sent

    token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if token and chat_id:
        sent = notify_telegram(token, chat_id, message) or sent

    return sent


def which_java():
    return shutil.which("java")
  

# Minecraft Server Auto-Setup

Script tự động tải và cấu hình Minecraft server (Vanilla, Paper/Spigot, hoặc Fabric).
Chạy được trên cả **Windows** và **Linux/macOS**.

## Yêu cầu

- Python 3.7 trở lên
- Java đã cài đặt (khuyến nghị Java 17+ cho các phiên bản Minecraft mới)
  - Kiểm tra: `java -version`
  - Nếu chưa có, tải tại: https://adoptium.net/

## Cài đặt

Không cần thư viện ngoài — script chỉ dùng thư viện chuẩn của Python.

## Cách dùng

```bash
python setup.py
```

Script sẽ hỏi bạn:

1. **Loại server**: `vanilla` (gốc), `paper` (hỗ trợ plugin), hoặc `fabric` (hỗ trợ mod)
2. **Tên thư mục** để tạo server
3. **Phiên bản Minecraft** (script tự liệt kê các phiên bản mới nhất)
4. **Cấu hình server.properties**: cổng, số người chơi tối đa, MOTD, độ khó, chế độ chơi, online-mode
5. **RAM** tối thiểu/tối đa cấp cho server

Sau khi chạy xong, script tự động:

- Tải file server (.jar) phù hợp
- Tự động chấp nhận `eula.txt`
- Tạo `server.properties` với cấu hình bạn chọn
- Tạo sẵn `start.bat` (Windows) và `start.sh` (Linux/macOS)

## Khởi động server

- **Windows**: mở thư mục server vừa tạo, double-click `start.bat`
- **Linux/macOS**:
  ```bash
  cd ten-thu-muc-server
  ./start.sh
  ```

## Lưu ý

- **Forge**: chưa được tự động hoá trong bản này do quy trình cài đặt phức tạp hơn
  (installer GUI/offline riêng cho từng phiên bản). Nếu cần, dùng
  [Fabric](https://fabricmc.net/) — tương tự về mặt hỗ trợ mod nhưng có API tải tự động.
- Mở cổng (mặc định `25565`) trên router/firewall nếu muốn bạn bè kết nối từ ngoài mạng LAN.
- Đổi RAM cấp cho server bằng cách sửa `-Xms` / `-Xmx` trong `start.sh` / `start.bat` bất cứ lúc nào.

## Quản lý nâng cao — `manage.py`

Sau khi `setup.py` tạo xong server, dùng `manage.py` **bên trong thư mục server** để quản lý
(server cần file `mcserver_config.json` do `setup.py` tạo sẵn).

```bash
cd ten-thu-muc-server
python ../manage.py <lệnh>
```

### 1. Backup tự động
```bash
python ../manage.py backup            # nén thư mục world/world_nether/world_the_end
python ../manage.py backup --keep 10  # giữ lại 10 bản gần nhất, tự xoá bản cũ hơn
```
File backup được lưu ở `backups/backup-<ngày-giờ>.zip`. Lệnh cũng gợi ý cách đặt lịch
chạy tự động bằng `cron` (Linux/macOS) hoặc `schtasks` (Windows).

### 2. Console tương tác + tự khởi động lại khi crash (watchdog)
```bash
python ../manage.py watchdog
python ../manage.py watchdog --max-restarts 5 --delay 10
```
Chạy server thay cho `start.sh`/`start.bat`. Trong lúc server chạy, gõ lệnh và nhấn Enter
để gửi thẳng vào console server (`say hello`, `stop`, `give Steve diamond`...) — không cần
mở cửa sổ khác. Nếu server thoát bất ngờ, watchdog tự khởi động lại sau vài giây; nếu
crash liên tục nhanh (dưới 10s) quá `--max-restarts` lần, watchdog dừng hẳn để bạn kiểm
tra lỗi. Log được ghi vào `watchdog.log`. Nếu đã cấu hình thông báo (mục 8), watchdog cũng
tự báo khi server crash và khi có người vào/rời server.

### 3. Whitelist / Ops / Ban
```bash
python ../manage.py whitelist add Steve
python ../manage.py whitelist remove Steve
python ../manage.py ops add Steve
python ../manage.py ban add Griefer123 --reason "Phá hoại"
python ../manage.py ban remove Griefer123
```
Tự tra UUID qua Mojang API rồi ghi trực tiếp vào `whitelist.json` / `ops.json` /
`banned-players.json`. Nếu server đang chạy, dùng thêm lệnh trong game
(`/whitelist reload`, `/op`, `/ban`) để áp dụng ngay lập tức.

### 4. Cài plugin/mod tự động
```bash
python ../manage.py install "Lithium"
```
Tìm kiếm trên [Modrinth](https://modrinth.com), hiển thị danh sách kết quả để bạn chọn,
rồi tự tải file phù hợp (đúng loader Paper/Fabric và phiên bản Minecraft) vào thư mục
`plugins/` hoặc `mods/`. Không dùng được với server Vanilla.

### 5. Theo dõi trạng thái
```bash
python ../manage.py status
```
Hiển thị RAM/CPU của tiến trình Java (cần `pip install psutil` để có số liệu chi tiết)
và danh sách người chơi đang online (yêu cầu RCON đã được bật — `setup.py` sẽ hỏi bạn
lúc tạo server, hoặc tự thêm `enable-rcon=true` vào `server.properties`).

### 6. Khôi phục từ backup
```bash
python ../manage.py restore                       # chọn từ danh sách
python ../manage.py restore backup-20260101-030000.zip
```
Ghi đè thư mục world hiện tại bằng nội dung trong file backup đã chọn. Luôn hỏi xác nhận
(`yes`) trước khi ghi đè — hãy dừng server trước khi chạy lệnh này.

### 7. Cập nhật server
```bash
python ../manage.py update                # cập nhật lên bản mới nhất
python ../manage.py update --version 1.21.2
```
Tự sao lưu world trước, sau đó tải lại jar (Vanilla/Paper) hoặc chạy lại Fabric installer
cho phiên bản mới, và cập nhật `mcserver_config.json`.

### 8. Thông báo Discord / Telegram
```bash
python ../manage.py notify set --discord-webhook "https://discord.com/api/webhooks/..."
python ../manage.py notify set --telegram-token "123:ABC" --telegram-chat "123456789"
python ../manage.py notify test
```
Sau khi cấu hình, `watchdog` sẽ tự gửi thông báo khi: server crash / tự khởi động lại,
crash liên tục vượt ngưỡng, có người chơi vào hoặc rời server; và `backup` sẽ báo khi
sao lưu xong.

### 9. Xem log nhanh
```bash
python ../manage.py logs                  # 50 dòng gần nhất
python ../manage.py logs --lines 200
python ../manage.py logs --errors-only    # chỉ dòng ERROR/WARN
```

### 10. Chạy dạng service/daemon nền
```bash
python ../manage.py service install
```
- **Linux**: tạo file `mc-<tên-thư-mục>.service` (systemd) kèm hướng dẫn `sudo systemctl enable --now`.
- **Windows**: tạo `start_service.bat` kèm 2 lựa chọn — chạy tự động khi đăng nhập (`schtasks`)
  hoặc chạy nền thật sự bằng [NSSM](https://nssm.cc/).

## Quản lý nhiều server — `mcctl.py`

Nếu bạn có nhiều thư mục server (mỗi thư mục tạo bởi `setup.py`) nằm chung một thư mục cha,
dùng `mcctl.py` **từ thư mục cha đó** để quản lý tất cả cùng lúc — server chạy nền (không
cần giữ terminal mở), log ghi vào `console.log` trong từng thư mục:

```bash
python mcctl.py list             # liệt kê server + trạng thái
python mcctl.py start survival   # khởi động nền
python mcctl.py stop survival    # dừng (ưu tiên qua RCON, có "stop" mượt)
python mcctl.py status           # trạng thái + người chơi online của tất cả server
```

Lưu ý: server khởi động qua `mcctl.py start` chạy nền và không nhận lệnh console trực
tiếp như `watchdog` — dùng RCON (`mcctl.py status`) hoặc `/whitelist`, `/op`... qua lệnh
trong game để tương tác.

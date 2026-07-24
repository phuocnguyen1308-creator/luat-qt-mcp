# Hướng dẫn cài connector luật quốc tế (luat-qt)

MCP này cho Claude tra cứu **pháp luật quốc tế toàn văn** ngay trong hội thoại — hiện có EU
(GDPR, AI Act, NIS2, Cyber Resilience Act, DSA, DMA, EECC, ePrivacy, LED), đang mở rộng.

Dữ liệu nằm trên máy chủ riêng, truy cập qua **Tailscale** bằng tài khoản **chỉ-đọc** `luatqt_ro`.
Link repo công khai; mật khẩu chỉ-đọc do quản trị gửi riêng.

> Ai đã cài connector `luat` (luật Việt Nam) thì Tailscale + uv đã sẵn — chỉ cần Bước 3.

---

## 1. Cài Tailscale (nếu chưa)
Tải https://tailscale.com/download, đăng nhập bằng email được mời, Accept máy chia sẻ.
Kiểm tra: `ping 100.85.147.69` có `Reply` là được.

## 2. Cài uv (nếu chưa)
PowerShell:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Đóng/mở lại PowerShell, kiểm tra `uv --version`.

## 3. Thêm connector vào Claude Desktop
Mở file cấu hình:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Trong `"mcpServers"`, thêm khối (điền mật khẩu chỉ-đọc quản trị gửi):
```json
"luat-qt": {
  "command": "uvx",
  "args": ["--from", "git+https://github.com/phuocnguyen1308-creator/luat-qt-mcp", "luat-qt-mcp"],
  "env": {
    "PGHOST": "100.85.147.69",
    "PGDATABASE": "luatqt_db",
    "PGUSER": "luatqt_ro",
    "PGPASSWORD": "<mật khẩu chỉ-đọc>",
    "E5_URL": "http://100.85.147.69:8899"
  }
}
```
> Windows dùng `"uvx"` (uv tự vào PATH). Nếu báo không thấy lệnh, thay bằng đường dẫn đầy đủ
> tới `uvx.exe` (giống cách đã làm cho connector `luat`).

## 4. Khởi động lại + kiểm chứng
Thoát hẳn Claude Desktop, mở lại, hội thoại **mới**, hỏi:
> Connector luat-qt dặn dùng thế nào? Thử tra "right to erasure".

Đạt nếu Claude nhắc nguyên tắc "hỏi bằng thuật ngữ tiếng Anh" và tra ra **GDPR Article 17**.

## Sự cố
| Hiện tượng | Xử lý |
|---|---|
| `password authentication failed` | Sai mật khẩu `luatqt_ro` — hỏi lại quản trị |
| `could not connect` | Tailscale chưa Connected, hoặc `ping 100.85.147.69` fail |
| Không thấy tool luat-qt | Sai JSON (thiếu dấu phẩy giữa các entry). Thoát hẳn Claude rồi mở lại |
| `tim_ngu_nghia` báo lỗi service nhúng | Service e5 (:8899) trên Pi chưa chạy — báo quản trị |

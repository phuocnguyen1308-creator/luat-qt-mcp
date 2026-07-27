# Hướng dẫn cài connector luật quốc tế (luat-qt)

MCP này cho Claude tra cứu **pháp luật quốc tế toàn văn** ngay trong hội thoại.

Kho hiện có **115 văn bản · 8.392 điều · 38 nền tài phán**:

| Vùng | Có gì |
|---|---|
| EU | GDPR, AI Act, NIS2, Cyber Resilience Act, DSA, DMA, EECC, ePrivacy, LED |
| Anh ngữ | Anh, Ireland, Canada, New Zealand, Úc, Singapore |
| Mỹ | luật liên bang, CFR, sắc lệnh, án lệ SCOTUS, **20 bang** có luật privacy |
| Không phải tiếng Anh | 🇯🇵 Nhật · 🇩🇪 Đức · 🇫🇷 Pháp · 🇪🇸 Tây Ban Nha · 🇧🇷 Brazil · 🇨🇱 Chile · 🇦🇪 UAE (Ả Rập) · 🇨🇭 Thụy Sĩ |
| Chủ đề | privacy · telecom · cyber · AI · drone/UAV |

Dữ liệu nằm trên máy chủ riêng, truy cập qua **Tailscale** bằng tài khoản **chỉ-đọc** `luatqt_ro`.
Repo công khai; **mật khẩu chỉ-đọc do quản trị gửi riêng, không nằm trong tài liệu này.**

> Ai đã cài connector `luat` (luật Việt Nam) thì Tailscale + uv đã sẵn — chỉ cần Bước 3.

---

## 0. Quản trị làm trước (không phải việc của người cài)

- Mời email của người dùng vào tailnet, **và chia sẻ máy `phuocn`** cho tài khoản đó
  (Tailscale admin → Machines → phuocn → Share).
- Gửi mật khẩu `luatqt_ro` qua kênh riêng — **đừng gửi qua chat chung hay email không mã hoá**.

## 1. Cài Tailscale (nếu chưa)

Tải https://tailscale.com/download, đăng nhập bằng email được mời, bấm **Accept** máy được chia sẻ.

Kiểm tra: `ping 100.85.147.69` có `Reply` là được.

## 2. Cài uv (nếu chưa)

**Windows** (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
**Mac**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Đóng/mở lại terminal, kiểm tra `uv --version`.

## 3. Thêm connector vào Claude Desktop

Mở file cấu hình:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Trong `"mcpServers"`, thêm khối sau (điền mật khẩu chỉ-đọc quản trị gửi):
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

Thoát **hẳn** Claude Desktop (không chỉ đóng cửa sổ), mở lại, hội thoại **mới**, hỏi ba câu:

1. `Thử tra "right to erasure" trong kho luật quốc tế.`
   → phải ra **GDPR Article 17** (Right to erasure / right to be forgotten).

2. `Luật Nhật quy định thế nào về việc cung cấp dữ liệu cá nhân cho bên thứ ba ở nước ngoài?`
   → phải ra **APPI 第二十八条 — 外国にある第三者への提供の制限**.
   Câu này kiểm tra thứ khó nhất: hỏi tiếng Việt, trúng văn bản tiếng Nhật.

3. `Kho luật quốc tế hiện có bao nhiêu văn bản?`
   → khoảng **115 văn bản · 8.392 điều**.

## Cách hỏi cho ra kết quả tốt

Kho phần lớn là tiếng Anh, nên **thuật ngữ pháp lý tiếng Anh** cho kết quả tốt nhất
(`right to erasure`, `data breach notification`).

Với văn bản **không phải tiếng Anh** (Nhật, Đức, Pháp, Tây Ban Nha, Brazil, UAE):

- Nói rõ nước cần tìm — Claude sẽ đặt `jurisdiction`. Không nói thì kết quả tiếng Anh lấn át,
  vì mô hình nhúng bắc cầu được giữa các thứ tiếng nhưng **yếu hơn nhiễu cùng ngôn ngữ**
  (đo thực tế: cùng tiếng 0,93 · Anh→Nhật 0,82).
- Chắc ăn nhất là hỏi bằng **chính ngôn ngữ của văn bản**.

## Sự cố

| Hiện tượng | Xử lý |
|---|---|
| `password authentication failed` | Sai mật khẩu `luatqt_ro` — hỏi lại quản trị |
| `could not connect` | Tailscale chưa Connected, hoặc `ping 100.85.147.69` fail, hoặc chưa Accept máy chia sẻ |
| Không thấy tool luat-qt | Sai JSON (thiếu dấu phẩy giữa các entry). Thoát hẳn Claude rồi mở lại |
| `tim_ngu_nghia` báo lỗi service nhúng | Service e5 (:8899) trên Pi chưa chạy — báo quản trị |
| Hỏi về luật Nhật/Đức/Pháp mà không ra gì | Cần bản **0.25.0 trở lên**. Bản cũ lọc sai chỗ nên các nước không nói tiếng Anh luôn trả rỗng. Xoá cache uv rồi mở lại Claude: `uv cache clean` |

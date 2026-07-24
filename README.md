# luat-qt-mcp

MCP server tra cứu **pháp luật quốc tế toàn văn** trên PostgreSQL (`luatqt_db`).
Song sinh với `vn-luat-mcp` nhưng cho kho quốc tế; dùng chung hạ tầng Pi (Postgres + service nhúng e5).

## Kho hiện có (EU pilot)

9 văn bản landmark · 689 điều · 4 chủ đề, lấy trực tiếp từ EUR-Lex:

| Chủ đề | Văn bản |
|---|---|
| privacy | GDPR · ePrivacy · LED |
| ai | AI Act |
| cyber | NIS2 · Cyber Resilience Act |
| telecom | DSA · DMA · EECC |

Khóa ổn định do EU cấp: `doc_id` = CELEX, `article_key` = CELEX + eId (vd `32016R0679_art_17`).
Mỗi điều/văn bản kèm `date_in_force` + `status` để suy luận hiệu lực.

## Tools

| Tool | Việc |
|---|---|
| `tra_dieu(tu_khoa, jurisdiction?, topic?)` | Tìm điều theo từ khóa (full-text) — tiếng Anh tốt nhất |
| `tim_ngu_nghia(cau_hoi, jurisdiction?, topic?)` | Tìm ngữ nghĩa (hybrid vector e5 + FTS, RRF) |
| `xem_dieu(article_key)` | Toàn văn một điều + metadata văn bản |
| `tra_van_ban(tu_khoa?, jurisdiction?, topic?)` | Tìm/liệt kê văn bản |
| `xem_van_ban(doc_id)` | Metadata văn bản + danh mục điều |
| `liet_ke(jurisdiction?, topic?)` | Danh mục gọn |
| `thong_ke()` | Tổng quan kho |

Server kèm `instructions` — "sổ tay tư duy hiệu lực & ngôn ngữ" host đưa cho mọi AI mỗi phiên
(kiểm ngày hiệu lực, bản gốc vs hợp nhất, tra tiếng Anh cho sắc, xuyên quốc gia thuật ngữ khác nhau).

## Kiến trúc

- Client nhẹ: chỉ `mcp` + `psycopg2-binary`. Kết nối Postgres trên Pi qua Tailscale bằng role **chỉ-đọc** `luatqt_ro`.
- Nhúng câu hỏi: gọi service e5 trên Pi (`E5_URL`, mặc định `:8899`) — cùng model với kho VN → vector tương thích.

## Cấu hình

Xem `.mcp.json.example` (Mac chạy local qua `uvx --from <path>`) và `.env.example`.
Env: `PGHOST PGDATABASE PGUSER PGPASSWORD E5_URL`.

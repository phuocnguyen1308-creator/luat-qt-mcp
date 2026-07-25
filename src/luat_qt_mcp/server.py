#!/usr/bin/env python3
"""MCP server "luat-qt": tra cứu PHÁP LUẬT QUỐC TẾ toàn văn trong PostgreSQL (luatqt_db).
Hiện có EU (EUR-Lex); đang mở rộng UK/US/CH/UAE... Điều lấy trực tiếp từ văn bản gốc,
khóa ổn định do cơ quan cấp (CELEX + eId). Tra full-text + ngữ nghĩa (e5) gộp bằng RRF."""
import os, json, urllib.request
from mcp.server.fastmcp import FastMCP
from .db import query

# ─────────────────── SỔ TAY TƯ DUY cho MỌI AI dùng connector này ───────────────────
_HUONG_DAN = """\
Connector "luat-qt": kho pháp luật QUỐC TẾ toàn văn. Hiện có:
  • EU (EUR-Lex): GDPR, AI Act, NIS2, Cyber Resilience Act, DSA, DMA, EECC, ePrivacy, LED
  • Thụy Sĩ (fedlex): FADP (Luật bảo vệ dữ liệu) + Data Protection Ordinance
  • Singapore (SSO): PDPA · Cybersecurity Act · Computer Misuse · Telecom/Electronic Transactions/Spam Control
  • Ireland (eISB): Data Protection Act 2018
  • Anh (legislation.gov.uk): DPA 2018 · Data (Use and Access) Act 2025 · PECR 2003
  • Canada (justice laws): PIPEDA · Privacy Act · Telecommunications Act
  • New Zealand (legislation.govt.nz): Privacy Act 2020 · Telecom Act 2001 · Harmful Digital Comms 2015
  • Úc (legislation.gov.au): Privacy Act 1988 · Online Safety Act 2021 · Critical Infrastructure 2018
  • Đức (gesetze-im-internet.de): BDSG · TTDSG · TKG · BSIG · DDG · NetzDG · LuftVO — ⚠ TIẾNG ĐỨC
  • Tây Ban Nha (BOE): LOPDGDD · LSSI — ⚠ TIẾNG TÂY BAN NHA
  • Chile (leychile/BCN): Ley 19.628 (vida privada) — ⚠ TIẾNG TÂY BAN NHA
  • Brazil (planalto): LGPD (Lei 13.709/2018) · Marco Civil da Internet — ⚠ TIẾNG BỒ ĐÀO NHA
  • UAE 3 tầng: LIÊN BANG 'AE' = PDPL (Nghị định-luật 45/2021) — ⚠ TIẾNG Ả RẬP (bản chính thức
    duy nhất) · free zone tài chính 'AE-ADGM' = ADGM DP Regulations 2021, 'AE-DIFC' = DIFC DP
    Law 5/2020 — tiếng Anh, ✅ BẢN HỢP NHẤT
  • Mỹ – LUẬT BANG (7/20 bang có luật privacy toàn diện): 'US-CA' California CCPA/CPRA ·
    'US-VA' Virginia CDPA · 'US-TX' Texas DPSA · 'US-FL' Florida Digital Bill of Rights ·
    'US-MT' Montana CDPA · 'US-DE' Delaware DPDPA · 'US-IA' Iowa CDPA
    ⚠ CHƯA có 13 bang: CO, CT, UT, OR, TN, IN, MN, NE, NH, NJ, KY, RI, MD (cổng bang chặn
    truy cập từ ngoài Mỹ). Thiếu ≠ bang đó không có luật.
  • Mỹ – LIÊN BANG, 3 TẦNG (jurisdiction='US'), lọc bằng doc_type:
      - doc_type='act' — 20 đạo luật (U.S. Code): CFAA · ECPA Wiretap + Stored Communications ·
        Privacy Act 1974 · FOIA · HIPAA · FCRA · FERPA · FISA · Pen/Trap · DPPA · COPPA ·
        GLBA-Privacy · CAN-SPAM · CPNI · TCPA · CDA 230 · FISMA · CALEA
      - doc_type='regulation' — QUY ĐỊNH (eCFR, ✅bản hợp nhất): COPPA Rule 16 CFR 312 ·
        GLBA Safeguards 16 CFR 314 · HIPAA Rules 45 CFR 164 · DOJ Bulk Data 28 CFR 202 ·
        FCC 47 CFR 64
      - doc_type='executive_order' — SẮC LỆNH: EO 14117 (dữ liệu nhạy cảm ra nước ngoài) ·
        14086 (tình báo tín hiệu, nền EU-US DPF) · 14179 + 14365 (AI)
đang mở rộng UAE/Pháp... Mỗi điều lấy trực tiếp từ văn bản gốc chính thức, khóa ổn định do cơ quan cấp
(EU: CELEX; CH/IE: ELI; SG/CA/NZ/AU/DE: số điều; UK: pid CLML; US: bang=số mục Code, LB=Title+§; article_key=doc_id+điều).
Chủ đề gồm cả UAV/Drone (EU/AU/CA/SG/UK) ngoài privacy/ai/cyber/telecom.
LUÔN suy nghĩ chủ động về HIỆU LỰC & NGÔN NGỮ:

1. KIỂM NGÀY HIỆU LỰC vs HÔM NAY. Mỗi văn bản có date_in_force + status. Có luật ĐÃ ban
   hành nhưng CHƯA tới ngày áp dụng (vd Cyber Resilience Act hiệu lực 2027-12-11) — chưa
   tới ngày thì KHÔNG dùng làm căn cứ hiện hành. status='repealed' = đã bị bãi bỏ.

2. KẾT QUẢ LÀ BẢN NGUYÊN VĂN BAN HÀNH (consolidated=false), KHÔNG phải bản hợp nhất. Luật
   EU thường có bản HỢP NHẤT riêng đã gộp các lần sửa; với trích dẫn quan trọng, đối chiếu
   bản consolidated trên nguồn chính thức (mở source_url → EUR-Lex).

3. TRA CÙNG NGÔN NGỮ VỚI CORPUS cho kết quả SẮC NHẤT. Kho lưu bằng TIẾNG ANH. Model nhúng
   nhỏ (e5-small) YẾU khi hỏi tiếng Việt trên text tiếng Anh — hãy DIỄN ĐẠT CÂU HỎI BẰNG
   THUẬT NGỮ PHÁP LÝ TIẾNG ANH trước khi tim_ngu_nghia (vd 'quyền được xóa dữ liệu' →
   'right to erasure right to be forgotten'). Bạn (AI) song ngữ, tự dịch ý sang tiếng corpus.
   ⚠ THỤY SĨ: bản tiếng Anh là DỊCH KHÔNG CHÍNH THỨC; văn bản có hiệu lực pháp lý là
   tiếng Đức/Pháp/Ý. Trích dẫn quan trọng phải dẫn bản DE/FR/IT trên fedlex (source_url).
   ⚠ ĐỨC (DE) / TÂY BAN NHA (ES): lưu bằng TIẾNG ĐỨC / TIẾNG TÂY BAN NHA (chính thức, không có
   bản EN). Tra sắc nhất bằng thuật ngữ pháp lý đúng tiếng đó (DE: 'Auskunftsrecht',
   'personenbezogene Daten'; ES: 'datos personales', 'derecho de acceso'); hỏi Anh/Việt thì tự
   dịch ý sang tiếng corpus trước khi tim_ngu_nghia.

4. HAI CÁCH TRA: tra_dieu (full-text — chính xác thuật ngữ/số điều, nhanh) và tim_ngu_nghia
   (ngữ nghĩa — cho câu mô tả). Truy vấn đã đúng thuật ngữ tiếng Anh thì tra_dieu thường đủ.

5. XUYÊN QUỐC GIA: cùng khái niệm mỗi hệ một thuật ngữ ('personal data' EU ↔ 'personal
   information' US). Khi so sánh nhiều nước, lọc theo jurisdiction/topic và nêu rõ mỗi bên
   gọi tên gì. Thiếu một nước trong kho ≠ nước đó không có luật — chỉ là chưa nạp.
   ⚠ UAE phân tầng — PHẢI nói rõ đang dẫn tầng nào: 'AE' = PDPL LIÊN BANG (áp dụng toàn UAE,
   trừ free zone có luật riêng); 'AE-ADGM'/'AE-DIFC' = hai free zone tài chính, mỗi zone là hệ
   pháp luật riêng kiểu common law, KHÔNG áp dụng cho phần còn lại của UAE. Đừng dùng ADGM/DIFC
   để trả lời câu hỏi về "luật UAE" nói chung.
   ⚠ PDPL lưu bằng TIẾNG Ả RẬP (bản chính thức duy nhất — u.ae không phát hành bản EN). Tra sắc
   nhất bằng thuật ngữ Ả Rập ('البيانات الشخصية' dữ liệu cá nhân, 'المتحكم' bên kiểm soát,
   'انتهاك البيانات' vi phạm dữ liệu). Lưu ý PDF gốc bị lỗi rời chữ nhẹ khi trích (ví dụ
   'الإبلاغ' có thể thành 'اإلبالغ') — vector vẫn khớp tốt, nhưng khi TRÍCH DẪN nguyên văn cho
   người dùng thì nên đối chiếu source_url.
   ⚠ MỸ phân mảnh — KHÔNG có luật privacy LIÊN BANG toàn diện. Khi user hỏi "luật bảo vệ dữ liệu
   của Mỹ", nêu rõ sự phân mảnh, đừng ngầm coi có một đạo luật chung. Ba điều PHẢI nhớ:
   (a) NGHĨA VỤ TUÂN THỦ THỰC TẾ thường nằm ở QUY ĐỊNH (doc_type='regulation'), không phải luật
       gốc. Hỏi "phải làm gì để tuân thủ COPPA/HIPAA" → trả lời từ 16 CFR 312 / 45 CFR 164, rồi
       mới dẫn luật gốc. Trả lời chỉ bằng U.S. Code là THIẾU phần hành động cụ thể.
   (b) TẦNG SẮC LỆNH (doc_type='executive_order') đổi theo nhiệm kỳ và đang là nơi biến động
       mạnh nhất — luôn kiểm date_document. Vd EO 14110 (AI, Biden) đã bị bãi bỏ và thay bằng
       EO 14179 (2025); EO 14365 (12/2025) hạn chế luật AI cấp bang. Kho chỉ giữ EO còn hiệu lực.
   (c) LUẬT BANG mới là nơi có luật privacy tổng quát. Kho hiện CHỈ có California ('US-CA',
       CCPA/CPRA) trong khi thực tế đã có ~20 bang. Thiếu một bang trong kho ≠ bang đó không có
       luật — phải nói rõ giới hạn này thay vì kết luận.
   (d) Kho CHƯA có ÁN LỆ Mỹ (Carpenter, Van Buren, Riley, TransUnion...). Với câu hỏi mà kết quả
       phụ thuộc cách tòa giải thích luật, hãy cảnh báo là còn thiếu tầng án lệ.

6. Trích dẫn LUÔN kèm doc_id (CELEX) + số điều + ngày để người dùng tự kiểm trên nguồn chính thức.

7. HỎI VỀ "CẢNH BÁO / THAY ĐỔI / CẦN CHÚ Ý" pháp lý → GỌI THẲNG xem_canh_bao NGAY, đừng hỏi lại
   người dùng lĩnh vực nào (tool trả toàn bộ kho: thay đổi gần đây + văn bản sắp áp dụng). Nếu
   muốn lọc thì tự lọc kết quả theo jurisdiction/topic, không bắt người dùng làm rõ trước.
"""

mcp = FastMCP("luat-qt", instructions=_HUONG_DAN)

# Trọng số ts_rank_cd theo hạng D,C,B,A. search_vector dựng bằng config 'simple' (đa ngôn ngữ).
_RANK_W = "'{0.1, 0.2, 0.4, 1.0}'"
NGUONG_DIEM = 0.02   # điểm cao nhất dưới mức này = khớp rải rác → cảnh báo

E5_URL = os.environ.get("E5_URL", "http://100.85.147.69:8899")


def _shape(rows, offset):
    total = rows[0]["_total"] if rows else 0
    for r in rows:
        r.pop("_total", None)
    return {"tong_so": total, "offset": offset, "so_tra": len(rows),
            "con_nua": offset + len(rows) < total, "ket_qua": rows}


def _loc(jurisdiction, topic, alias=""):
    """Trả (mệnh_đề_SQL, params) cho bộ lọc jurisdiction/topic tùy chọn."""
    p, a = "", (alias + "." if alias else "")
    params = []
    if jurisdiction:
        p += f" AND {a}jurisdiction = %s"; params.append(jurisdiction)
    if topic:
        p += f" AND {a}topic = %s"; params.append(topic)
    return p, params


# ─────────────────────────── TRA ĐIỀU (full-text) ───────────────────────────

@mcp.tool()
def tra_dieu(tu_khoa: str, gioi_han: int = 10, offset: int = 0,
             jurisdiction: str = None, topic: str = None) -> dict:
    """Tìm ĐIỀU luật quốc tế theo từ khóa (full-text). Truy vấn TIẾNG ANH cho kết quả tốt nhất.
    Lọc tùy chọn: jurisdiction ('EU','UK'...), topic ('privacy','ai','cyber','telecom','uav'...).
    Mỗi kết quả kèm 'diem' (độ liên quan) + doc_id/số điều + ngày hiệu lực & tình trạng.
    Phân trang: gioi_han tối đa 50; offset để lấy trang kế.
    Trả {tong_so, offset, so_tra, con_nua, ket_qua[...]}."""
    gioi_han = max(1, min(int(gioi_han), 50)); offset = max(0, int(offset))
    cond, extra = _loc(jurisdiction, topic, "d")
    params = [tu_khoa, tu_khoa, tu_khoa] + extra + [gioi_han, offset]
    rows = query(f"""
        SELECT count(*) OVER() AS _total,
               round(ts_rank_cd({_RANK_W}, d.search_vector,
                     plainto_tsquery('simple', unaccent(%s)))::numeric, 4)::float8 AS diem,
               d.article_key, d.doc_id, d.jurisdiction, d.topic, d.nhan, d.tieu_de,
               ts_headline('simple', left(d.noi_dung, 4000),
                    plainto_tsquery('simple', unaccent(%s)),
                    'StartSel=«, StopSel=», MaxFragments=1, MaxWords=28, MinWords=10') AS trich_doan,
               v.date_in_force::text AS date_in_force, v.status, v.title AS ten_van_ban,
               v.source_url
        FROM dieu_qt d JOIN van_ban_qt v ON v.doc_id = d.doc_id
        WHERE d.search_vector @@ plainto_tsquery('simple', unaccent(%s)){cond}
        ORDER BY diem DESC
        LIMIT %s OFFSET %s
    """, tuple(params))
    if rows and offset == 0 and rows[0]["diem"] < NGUONG_DIEM:
        return {"tong_so": rows[0]["_total"], "so_tra": 0, "ket_qua": [],
                "canh_bao": f"Khớp yếu (điểm cao nhất {rows[0]['diem']}).",
                "goi_y": "Rút gọn còn thuật ngữ pháp lý tiếng Anh cốt lõi, hoặc dùng tim_ngu_nghia."}
    return _shape(rows, offset)


@mcp.tool()
def xem_dieu(article_key: str) -> dict:
    """Xem TOÀN VĂN một điều theo article_key (vd '32016R0679_art_17').
    Kèm metadata văn bản: tên, ngày ban hành/hiệu lực, tình trạng, nguồn chính thức."""
    key = (article_key or "").strip()
    rows = query("""
        SELECT d.article_key, d.doc_id, d.jurisdiction, d.topic, d.so_dieu,
               d.nhan, d.tieu_de, d.noi_dung,
               v.title AS ten_van_ban, v.doc_type, v.date_document::text AS date_document,
               v.date_in_force::text AS date_in_force, v.status, v.consolidated, v.source_url
        FROM dieu_qt d JOIN van_ban_qt v ON v.doc_id = d.doc_id
        WHERE d.article_key = %s
    """, (key,))
    if not rows:
        return {"error": f"Không thấy điều '{key}'.",
                "goi_y": "Kiểm tra dạng khóa (CELEX_art_N), hoặc tìm bằng tra_dieu/tim_ngu_nghia."}
    return rows[0]


# ──────────────── TÌM NGỮ NGHĨA (pgvector + service nhúng e5 trên Pi) ────────────────

def _nhung_cau_hoi(text):
    body = json.dumps({"texts": [text], "prefix": "query"}).encode()
    req = urllib.request.Request(E5_URL + "/embed", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["vectors"][0]


def _vstr(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _rrf(danh_sach, k0=60):
    """Weighted Reciprocal Rank Fusion. Vector trọng số cao hơn FTS."""
    diem = {}
    for lst, w in danh_sach:
        for hang, khoa in enumerate(lst):
            diem[khoa] = diem.get(khoa, 0.0) + w / (k0 + hang)
    return sorted(diem, key=diem.get, reverse=True)


@mcp.tool()
def tim_ngu_nghia(cau_hoi: str, gioi_han: int = 8,
                  jurisdiction: str = None, topic: str = None) -> dict:
    """Tìm theo NGỮ NGHĨA — hiểu ý kể cả không trùng từ khóa. Hybrid vector(e5)+FTS gộp RRF.
    QUAN TRỌNG: kho tiếng Anh, model nhúng nhỏ → hãy diễn đạt câu hỏi bằng THUẬT NGỮ PHÁP LÝ
    TIẾNG ANH (vd 'right to erasure', 'data breach notification'). Hỏi tiếng Việt trên text
    tiếng Anh cho kết quả mỏng/kém tin.
    Lọc tùy chọn jurisdiction/topic. LẤY RỘNG rồi tự lọc: đọc 'trich_doan', giữ cái đúng ngữ cảnh.
    Mở toàn văn bằng xem_dieu(article_key)."""
    gioi_han = max(1, min(int(gioi_han), 20))
    cau_hoi = (cau_hoi or "").strip()
    if not cau_hoi:
        return {"error": "Câu hỏi rỗng."}
    try:
        vec = _vstr(_nhung_cau_hoi(cau_hoi))
    except Exception as e:
        return {"error": f"Không gọi được service nhúng ({e}).",
                "goi_y": "Kiểm tra service e5 trên Pi (:8899), hoặc dùng tra_dieu (full-text)."}
    # 1) Vector: 120 đoạn gần nhất, gom theo điều giữ đoạn khớp nhất
    chunks = query("""
        SELECT ref_id, doan, 1 - (embedding <=> %s::vector) AS sim
        FROM doc_embeddings WHERE nguon = 'dieu_qt'
        ORDER BY embedding <=> %s::vector LIMIT 120
    """, (vec, vec))
    if not chunks:
        return {"tong_so": 0, "ket_qua": [], "goi_y": "Kho chưa có vector — dùng tra_dieu."}
    best = {}
    for c in chunks:
        if c["ref_id"] not in best or c["sim"] > best[c["ref_id"]][0]:
            best[c["ref_id"]] = (c["sim"], c["doan"])
    vec_order = sorted(best, key=lambda s: best[s][0], reverse=True)
    # 2) Full-text
    fcond, fextra = _loc(jurisdiction, topic, "d")
    fts = query(f"""SELECT d.article_key AS k,
                    ts_rank_cd({_RANK_W}, d.search_vector,
                    plainto_tsquery('simple', unaccent(%s))) AS diem
                    FROM dieu_qt d
                    WHERE d.search_vector @@ plainto_tsquery('simple', unaccent(%s)){fcond}
                    ORDER BY diem DESC LIMIT 60""", tuple([cau_hoi, cau_hoi] + fextra))
    # 3) RRF gộp
    ranked = _rrf([(vec_order, 1.0), ([r["k"] for r in fts][:25], 0.5)])
    # 4) metadata cho toàn bộ ứng viên, rồi lọc jurisdiction/topic + cắt gioi_han
    if not ranked:
        return {"tong_so": 0, "ket_qua": [], "goi_y": "Thử tra_dieu với thuật ngữ cụ thể."}
    meta = {r["article_key"]: r for r in query("""
        SELECT d.article_key, d.doc_id, d.jurisdiction, d.topic, d.nhan, d.tieu_de,
               v.date_in_force::text AS date_in_force, v.status, v.source_url
        FROM dieu_qt d JOIN van_ban_qt v ON v.doc_id = d.doc_id
        WHERE d.article_key = ANY(%s)""", (ranked,))}
    kq = []
    for k in ranked:
        m = meta.get(k)
        if not m:
            continue
        if jurisdiction and m["jurisdiction"] != jurisdiction:
            continue
        if topic and m["topic"] != topic:
            continue
        sim = best.get(k, (None, None))
        kq.append({"article_key": k, "doc_id": m["doc_id"], "jurisdiction": m["jurisdiction"],
                   "topic": m["topic"], "nhan": m["nhan"], "tieu_de": m["tieu_de"],
                   "do_tuong_dong": round(sim[0], 3) if sim[0] is not None else None,
                   "trich_doan": (sim[1][:300] if sim[1] else None),
                   "date_in_force": m["date_in_force"], "status": m["status"],
                   "source_url": m["source_url"]})
        if len(kq) >= gioi_han:
            break
    return {"tong_so": len(kq), "phuong_phap": "hybrid vector+FTS (RRF)",
            "ghi_chu": "Mở toàn văn bằng xem_dieu(article_key). Đối chiếu bản hợp nhất trên source_url khi trích dẫn quan trọng.",
            "ket_qua": kq}


# ─────────────────────────── VĂN BẢN (document level) ───────────────────────────

@mcp.tool()
def tra_van_ban(tu_khoa: str = None, jurisdiction: str = None, topic: str = None,
                gioi_han: int = 20) -> dict:
    """Tìm/liệt kê VĂN BẢN (cấp tài liệu). Có tu_khoa → full-text trên tiêu đề+toàn văn;
    không tu_khoa → liệt kê theo jurisdiction/topic. Mỗi mục kèm ngày hiệu lực, tình trạng, số điều."""
    gioi_han = max(1, min(int(gioi_han), 100))
    cond, extra = _loc(jurisdiction, topic, "v")
    if tu_khoa:
        params = [tu_khoa] + extra + [gioi_han]
        rows = query(f"""
            SELECT v.doc_id, v.jurisdiction, v.topic, v.doc_type, v.title,
                   v.date_in_force::text AS date_in_force, v.status, v.n_dieu, v.source_url,
                   round(ts_rank_cd({_RANK_W}, v.search_vector,
                         plainto_tsquery('simple', unaccent(%s)))::numeric,4)::float8 AS diem
            FROM van_ban_qt v
            WHERE v.search_vector @@ plainto_tsquery('simple', unaccent(%s)){cond}
            ORDER BY diem DESC LIMIT %s""", tuple([tu_khoa] + params))
    else:
        params = extra + [gioi_han]
        rows = query(f"""
            SELECT v.doc_id, v.jurisdiction, v.topic, v.doc_type, v.title,
                   v.date_in_force::text AS date_in_force, v.status, v.n_dieu, v.source_url
            FROM van_ban_qt v WHERE 1=1{cond}
            ORDER BY v.jurisdiction, v.topic, v.date_in_force LIMIT %s""", tuple(params))
    return {"tong_so": len(rows), "ket_qua": rows}


@mcp.tool()
def xem_van_ban(doc_id: str) -> dict:
    """Xem metadata một VĂN BẢN + danh mục các điều (số + tiêu đề). doc_id = CELEX."""
    key = (doc_id or "").strip()
    v = query("""SELECT doc_id, jurisdiction, topic, doc_type, title, lang, status,
                        date_document::text AS date_document, date_in_force::text AS date_in_force,
                        consolidated, n_dieu, source_url
                 FROM van_ban_qt WHERE doc_id = %s""", (key,))
    if not v:
        return {"error": f"Không thấy văn bản '{key}'.", "goi_y": "Dùng tra_van_ban/liet_ke để tìm doc_id."}
    dieu = query("""SELECT article_key, so_dieu, nhan, tieu_de
                    FROM dieu_qt WHERE doc_id = %s
                    ORDER BY (regexp_replace(so_dieu,'[^0-9].*$','')::int), so_dieu""", (key,))
    out = v[0]; out["so_dieu_list"] = dieu
    return out


# ─────────────────────────────── THỐNG KÊ / DANH MỤC ───────────────────────────────

@mcp.tool()
def thong_ke() -> dict:
    """Tổng quan kho: số văn bản & điều theo jurisdiction × topic, tổng vector đã nhúng."""
    theo = query("""SELECT jurisdiction, topic, count(*) AS so_van_ban, sum(n_dieu) AS so_dieu
                    FROM van_ban_qt GROUP BY 1,2 ORDER BY 1,2""")
    tong = query("""SELECT (SELECT count(*) FROM van_ban_qt) AS van_ban,
                           (SELECT count(*) FROM dieu_qt) AS dieu,
                           (SELECT count(*) FROM doc_embeddings WHERE nguon='dieu_qt') AS vector""")
    return {"tong": tong[0], "theo_jurisdiction_topic": theo}


@mcp.tool()
def xem_canh_bao(so_ngay: int = 90) -> dict:
    """Xem CẢNH BÁO pháp lý do monitor định kỳ ghi nhận:
      (1) thay đổi gần đây — đổi tình trạng (🔴), bản hợp nhất mới (🟡 = toàn văn [GỐC] đã cũ);
      (2) văn bản SẮP tới ngày áp dụng (canh mốc hiệu lực, vd luật tương lai);
      (3) lần giám sát gần nhất (biết dữ liệu có mới không).
    Dùng khi người dùng hỏi 'có gì thay đổi/cần chú ý về pháp lý' hoặc trước khi trích dẫn quan trọng.
    so_ngay: cửa sổ nhìn lại cho thay đổi đã ghi (mặc định 90)."""
    so_ngay = max(1, min(int(so_ngay), 365))
    thay_doi = query("""SELECT to_char(ts,'YYYY-MM-DD') AS ngay, doc_id, loai, muc_do, noi_dung
                        FROM giam_sat_log
                        WHERE ts >= now() - (%s || ' days')::interval
                        ORDER BY ts DESC""", (so_ngay,))
    sap = query("""SELECT doc_id, title, date_in_force::text AS date_in_force,
                          (date_in_force - CURRENT_DATE) AS con_ngay, jurisdiction, topic
                   FROM van_ban_qt
                   WHERE date_in_force > CURRENT_DATE
                   ORDER BY date_in_force""")
    kiem = query("SELECT max(last_checked)::text AS t FROM van_ban_qt")
    return {"so_thay_doi": len(thay_doi), "thay_doi_gan_day": thay_doi,
            "sap_toi_ngay_ap_dung": sap,
            "lan_giam_sat_cuoi": kiem[0]["t"] if kiem else None,
            "ghi_chu": (f"Không có thay đổi ghi nhận trong {so_ngay} ngày qua."
                        if not thay_doi else
                        "🟡 bản hợp nhất mới = toàn văn [GỐC] đã cũ, nên đối chiếu bản consolidated trên EUR-Lex.")}


@mcp.tool()
def liet_ke(jurisdiction: str = None, topic: str = None) -> dict:
    """Danh mục văn bản (gọn) — lọc tùy chọn theo jurisdiction/topic. Kèm ngày hiệu lực + tình trạng."""
    cond, extra = _loc(jurisdiction, topic, "v")
    rows = query(f"""SELECT v.doc_id, v.jurisdiction, v.topic, v.doc_type, v.title,
                            v.date_in_force::text AS date_in_force, v.status, v.n_dieu
                     FROM van_ban_qt v WHERE 1=1{cond}
                     ORDER BY v.jurisdiction, v.topic, v.date_in_force""", tuple(extra))
    return {"tong_so": len(rows), "ket_qua": rows}


def main():
    """Entry point cho console script / uvx."""
    mcp.run()


if __name__ == "__main__":
    main()

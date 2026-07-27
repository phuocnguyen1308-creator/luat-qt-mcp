#!/usr/bin/env python3
"""MCP server "luat-qt": tra cứu PHÁP LUẬT QUỐC TẾ toàn văn trong PostgreSQL (luatqt_db).
Hiện có EU (EUR-Lex); đang mở rộng UK/US/CH/UAE... Điều lấy trực tiếp từ văn bản gốc,
khóa ổn định do cơ quan cấp (CELEX + eId). Tra full-text + ngữ nghĩa (e5) gộp bằng RRF."""
import os, re, json, urllib.request
from mcp.server.fastmcp import FastMCP
from .db import query

# ─────────────────── SỔ TAY TƯ DUY cho MỌI AI dùng connector này ───────────────────
# ⚠ TỪ 0.27.0: HƯỚNG DẪN và DANH MỤC KHO nằm trong DATABASE, không nằm trong mã.
#   Lý do: bản trước liệt kê cứng từng nước từng luật, và nó ĐÃ SAI — vẫn ghi "18/20 bang"
#   sau khi nạp đủ 20, vẫn ghi "kho hiện CHỈ có California" khi đã có 20 bang, không có Nhật
#   Bản. Mỗi lần nạp thêm nước là một lần phải phát hành lại và bắt mọi người CÀI LẠI.
#   Nay: bảng `huong_dan` giữ phần tư duy (sửa được bằng SQL), danh mục SINH TỪ KHO lúc khởi
#   động. Thêm nước/nhóm → chỉ cần KHỞI ĐỘNG LẠI Claude, không cài lại.
#   Mọi truy vấn dưới đây đều bọc try/except: kho không với tới được thì connector vẫn chạy
#   và báo lỗi tử tế, thay vì chết lúc nạp module.
_MAC_DINH = """\
Connector "luat-qt": kho pháp luật QUỐC TẾ toàn văn (PostgreSQL + tra ngữ nghĩa e5).
⚠ Không đọc được bảng hướng dẫn trong kho — đây là bản rút gọn:
1. KIỂM date_in_force vs HÔM NAY. Có luật đã ban hành nhưng CHƯA tới ngày áp dụng;
   status='repealed' = đã bị bãi bỏ.
2. Kết quả thường là NGUYÊN VĂN BAN HÀNH, không phải bản hợp nhất — đối chiếu source_url.
3. Phần lớn kho là tiếng Anh, nhưng CÒN CÓ tiếng Nhật/Đức/Pháp/Tây Ban Nha/Bồ/Ả Rập.
   Hỏi tiếng Anh mà muốn tìm trong các nước đó thì PHẢI đặt jurisdiction, không thì kết quả
   tiếng Anh lấn át. Chắc ăn nhất: hỏi bằng chính ngôn ngữ của văn bản.
4. Thiếu một nước trong kho ≠ nước đó không có luật — chỉ là chưa nạp. Phải nói rõ giới hạn.
5. Trích dẫn LUÔN kèm doc_id + số điều + ngày để người dùng tự kiểm trên nguồn chính thức.
Gọi thong_ke() để biết kho hiện có gì.
"""


def _hd_tu_kho(muc="connector"):
    try:
        r = query("SELECT noi_dung FROM huong_dan WHERE muc=%s", (muc,))
        return r[0]["noi_dung"] if r else None
    except Exception:
        return None


def _danh_muc_song():
    """Danh mục SINH TỪ KHO — không bao giờ lệch với dữ liệu thật.

    Đi qua view `van_ban_topic` nên văn bản mang nhiều chủ đề hiện ở đủ các nhóm.
    Tự nêu cảnh báo ngôn ngữ cho nước không phải tiếng Anh, vì đó là thứ quyết định
    cách đặt câu hỏi (đo 27/07/2026: cùng tiếng 0,93 · Anh→Nhật 0,82).
    """
    try:
        rows = query("""SELECT v.jurisdiction AS j, t.topic AS tp,
                               count(*) AS n, coalesce(sum(v.n_dieu), 0) AS d,
                               string_agg(DISTINCT v.lang, '/') AS langs
                        FROM van_ban_qt v JOIN van_ban_topic t ON t.doc_id = v.doc_id
                        GROUP BY 1, 2 ORDER BY 1, 2""")
    except Exception:
        return ""
    if not rows:
        return ""
    theo = {}
    for r in rows:
        theo.setdefault(r["j"], []).append(r)
    out = ["", "KHO HIỆN CÓ (đọc thẳng từ database lúc khởi động, luôn khớp dữ liệu thật):"]
    for j in sorted(theo):
        muc = theo[j]
        langs = sorted({l for r in muc for l in (r["langs"] or "").split("/") if l})
        canh = "" if langs == ["EN"] else "   ⚠ " + "/".join(langs)
        out.append("  {}: {}{}".format(
            j, " · ".join("{} {}vb/{}đ".format(r["tp"], r["n"], r["d"]) for r in muc), canh))
    out.append("⚠ Nước KHÔNG có trong danh sách trên = CHƯA NẠP, không phải không có luật.")
    return "\n".join(out)


_HUONG_DAN = (_hd_tu_kho() or _MAC_DINH) + _danh_muc_song()

mcp = FastMCP("luat-qt", instructions=_HUONG_DAN)


def _cau_hinh():
    """Hằng số điều chỉnh lấy từ bảng `cau_hinh`; thiếu thì dùng mặc định trong mã.

    Nhờ vậy tinh chỉnh ngưỡng / số ứng viên KHÔNG cần phát hành lại connector.
    ⚠ `rank_w` được nội suy THẲNG vào SQL nên phải kiểm dạng trước khi dùng — chỉ nhận
      chữ số, dấu phẩy, dấu chấm, ngoặc nhọn và nháy đơn. Giá trị lạ thì bỏ, dùng mặc định.
    """
    c = {"rank_w": "'{0.1, 0.2, 0.4, 1.0}'", "nguong_diem": "0.02",
         "ung_vien_vector": "120", "ung_vien_fts": "60", "rrf_trong_so_fts": "0.5"}
    try:
        for r in query("SELECT khoa, gia_tri FROM cau_hinh"):
            k, v = r["khoa"], (r["gia_tri"] or "").strip()
            if k not in c or not v:
                continue
            if k == "rank_w" and not re.fullmatch(r"'\{[\d.,\s]+\}'", v):
                continue
            if k != "rank_w" and not re.fullmatch(r"[\d.]+", v):
                continue
            c[k] = v
    except Exception:
        pass
    return c


_CH = _cau_hinh()
_RANK_W = _CH["rank_w"]
NGUONG_DIEM = float(_CH["nguong_diem"])
_UNG_VIEN_VECTOR = int(_CH["ung_vien_vector"])
_UNG_VIEN_FTS = int(_CH["ung_vien_fts"])
_RRF_FTS = float(_CH["rrf_trong_so_fts"])

E5_URL = os.environ.get("E5_URL", "http://100.85.147.69:8899")


def _shape(rows, offset):
    total = rows[0]["_total"] if rows else 0
    for r in rows:
        r.pop("_total", None)
    return {"tong_so": total, "offset": offset, "so_tra": len(rows),
            "con_nua": offset + len(rows) < total, "ket_qua": rows}


def _loc(jurisdiction, topic, alias="", cap="dieu"):
    """Trả (mệnh_đề_SQL, params) cho bộ lọc jurisdiction/topic tùy chọn.

    ⚠ Lọc topic đi qua VIEW `dieu_topic` / `van_ban_topic`, KHÔNG so thẳng cột `topic`.
      Cột đó chỉ chứa MỘT giá trị, mà một điều luật có thể thuộc nhiều nhóm: Điều 2 EECC
      vừa là `telecom` (định nghĩa nền của bộ luật viễn thông EU) vừa là `ott` (nơi định
      nghĩa 'number-independent interpersonal communications service'). View hợp nhất chủ
      đề chính (từ bảng gốc) với chủ đề phụ chọn tay (`*_topic_them`).
      View chứ không phải bảng dẫn xuất — luôn đồng bộ theo cấu tạo, không có chỗ trôi lệch.
    """
    p, a = "", (alias + "." if alias else "")
    params = []
    if jurisdiction:
        p += f" AND {a}jurisdiction = %s"; params.append(jurisdiction)
    if topic:
        if cap == "van_ban":
            p += (f" AND EXISTS (SELECT 1 FROM van_ban_topic vt"
                  f" WHERE vt.doc_id = {a}doc_id AND vt.topic = %s)")
        else:
            p += (f" AND EXISTS (SELECT 1 FROM dieu_topic dt"
                  f" WHERE dt.article_key = {a}article_key AND dt.topic = %s)")
        params.append(topic)
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
    NGÔN NGỮ — đo thực tế 27/07/2026 (cùng tiếng 0,93 · Anh→Nhật 0,82 · Việt→Nhật 0,81):
      • Phần lớn kho là tiếng Anh → hỏi bằng THUẬT NGỮ PHÁP LÝ TIẾNG ANH cho kết quả tốt nhất.
      • Kho CÒN CÓ văn bản tiếng Nhật, Đức, Pháp, Tây Ban Nha, Bồ Đào Nha, Ả Rập. Model bắc
        cầu được nhưng YẾU HƠN nhiễu cùng ngôn ngữ, nên khi hỏi tiếng Anh mà muốn tìm trong
        các nước đó thì PHẢI đặt jurisdiction (vd jurisdiction='JP'); không đặt thì kết quả
        tiếng Anh sẽ lấn át.
      • Chắc ăn nhất: hỏi bằng chính NGÔN NGỮ CỦA VĂN BẢN (vd '外国にある第三者への提供' cho
        luật Nhật). Với tiếng Nhật, dùng cụm danh từ liền mạch giống tiêu đề điều.
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
    # ⚠ ĐIỀU KIỆN LỌC PHẢI NẰM TRONG TRUY VẤN, KHÔNG ĐƯỢC LỌC SAU.
    #   Bản cũ cắt top-120 trên TOÀN KHO rồi mới lọc jurisdiction ở bước 4. Hậu quả đo được
    #   ngày 27/07/2026: câu hỏi tiếng Anh + jurisdiction='JP' trả về 0 kết quả, vì 120 chỗ
    #   đó bị văn bản tiếng Anh chiếm sạch — điều Nhật ĐÚNG đạt sim 0,82 còn điều tiếng Anh
    #   KHÔNG liên quan đạt 0,85. Lọc xong thì rỗng.
    #   Đây không phải giới hạn của model: e5-small bắc cầu được (Anh→Nhật 0,816, Việt→Nhật
    #   0,806, cùng tiếng 0,932). Chỉ là lọc đặt sai chỗ. Lọc sau top-K luôn bỏ đói tập con
    #   nhỏ — và mọi nền tài phán không nói tiếng Anh đều là tập con nhỏ ở kho này.
    vcond, vextra = _loc(jurisdiction, topic, "d")
    chunks = query(f"""
        SELECT e.ref_id, e.doan, 1 - (e.embedding <=> %s::vector) AS sim
        FROM doc_embeddings e
        JOIN dieu_qt d ON d.article_key = e.ref_id
        WHERE e.nguon = 'dieu_qt'{vcond}
        ORDER BY e.embedding <=> %s::vector LIMIT {_UNG_VIEN_VECTOR}
    """, tuple([vec] + vextra + [vec]))
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
                    ORDER BY diem DESC LIMIT {_UNG_VIEN_FTS}""", tuple([cau_hoi, cau_hoi] + fextra))
    # 3) RRF gộp
    # Số ứng viên và trọng số lấy từ bảng `cau_hinh` — tinh chỉnh bằng SQL,
    # không phải bằng một lần phát hành connector.
    ranked = _rrf([(vec_order, 1.0),
                   ([r["k"] for r in fts][:max(1, _UNG_VIEN_FTS // 2)], _RRF_FTS)])
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
        # ⚠ ĐÃ BỎ lọc lại theo m["topic"]. Cả hai nhánh (vector + FTS) nay đã lọc topic ngay
        #   trong SQL qua view `dieu_topic`, nên lọc lại ở đây là thừa — và SAI: nó so với
        #   CHỦ ĐỀ CHÍNH trong cột `topic`, nên mọi điều khớp nhờ CHỦ ĐỀ PHỤ sẽ bị vứt.
        #   Hỏi topic='ott' sẽ trả rỗng dù SQL vừa tìm đúng Điều 2 EECC.
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
    cond, extra = _loc(jurisdiction, topic, "v", cap="van_ban")
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
    # Đi qua view `van_ban_topic` để CHỦ ĐỀ PHỤ cũng hiện (vd EECC đếm ở cả telecom lẫn ott).
    # ⚠ Vì vậy tổng cộng các dòng LỚN HƠN số văn bản thật — văn bản hai chủ đề được đếm hai
    #   lần. Đó là con số đúng cho câu hỏi "nhóm này phủ tới đâu", nhưng đừng cộng dồn để suy
    #   ra quy mô kho; dùng khối `tong` cho việc đó.
    theo = query("""SELECT v.jurisdiction, t.topic,
                           count(*) AS so_van_ban, sum(v.n_dieu) AS so_dieu
                    FROM van_ban_qt v JOIN van_ban_topic t ON t.doc_id = v.doc_id
                    GROUP BY 1,2 ORDER BY 1,2""")
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
    cond, extra = _loc(jurisdiction, topic, "v", cap="van_ban")
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

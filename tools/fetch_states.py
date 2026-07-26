#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải luật BANG Mỹ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ).

Nhiều cổng lập pháp bang CHẶN truy cập từ ngoài nước Mỹ (timeout) hoặc chặn bot (403).
Máy ở Việt Nam (sandbox / Pi / Mac) đều không lấy được; runner GitHub ở Mỹ thì vào được.

⚠ DỮ LIỆU KHÔNG LƯU TRONG REPO: workflow đóng gói state_raw/ thành artifact (7 ngày),
   rồi nạp vào Pi (bảng luatqt_db.raw_file). Repo/Mac chỉ là đường trung chuyển.

ĐỢT 6 — COLORADO: cập nhật từ CRS 2024 lên CRS 2025.

VÌ SAO PHẢI LÀM: kho đang giữ bản pháp điển **CRS 2024** trong khi Colorado đã phát hành
**CRS 2025**. Phát hiện này KHÔNG đến từ giám sát mà từ vòng khám phá nguồn — suốt thời gian
đó Colorado neo trên một PDF theo năm, mà file đó không bao giờ đổi. Bài học: nguồn đóng băng
im lặng KHÔNG PHẢI vì luật không đổi, mà vì **nó không biết gì cả**.

CÁCH LÀM — KHÔNG ĐOÁN ĐƯỜNG DẪN (bảy vòng trước đã dạy đủ):
trang OLLS trỏ tới '/agencies/…/2025-crs-titles-download'. Script mở đúng trang đó, đọc danh
sách liên kết, tự tìm file title 06 rồi tải. Sang năm có CRS 2026 thì OLLS đổi liên kết là
script bám theo, không phải sửa tay.

⚠ Đặt tên file ĐÚNG như adapter chờ: `CO_title06.html` (usa_state._fetch_co) — dù nội dung là
   PDF. Đổi tên là adapter không thấy.
"""
import urllib.request, ssl, os, re, json, subprocess, tempfile

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state_raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
GOC = "https://leg.colorado.gov"
OLLS = GOC + "/agencies/office-legislative-legal-services/colorado-revised-statutes"


def get(url, ref=None, timeout=120):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
         "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8"}
    if ref:
        h["Referer"] = ref
    with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                timeout=timeout, context=CTX) as r:
        return r.read()


def tuyet_doi(u):
    return u if u.startswith("http") else GOC + u


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── B1: trang OLLS → trang tải CRS của NĂM MỚI NHẤT ────────────────────────
    print(f"1) mở {OLLS}")
    html = get(OLLS).decode("utf-8", "replace")
    nam = sorted(set(re.findall(r'href="([^"]*?(\d{4})-crs-titles-download[^"]*)"', html)),
                 key=lambda x: x[1])
    if not nam:
        print("   ❌ không thấy liên kết '*-crs-titles-download' — trang OLLS đã đổi cấu trúc")
        return
    trang_tai, nam_moi = tuyet_doi(nam[-1][0]), nam[-1][1]
    print(f"   → bản mới nhất: CRS {nam_moi} · {trang_tai}")

    # ── B2: trang tải → PDF title 06 ───────────────────────────────────────────
    html2 = get(trang_tai, ref=OLLS).decode("utf-8", "replace")
    ung = sorted({h for h in re.findall(r'href="([^"]+)"', html2)
                  if re.search(r"title[-_ ]?0?6\b", h, re.I) and h.lower().endswith(".pdf")})
    if not ung:
        # nói ra mình THẤY GÌ, đừng im lặng thất bại
        pdf = sorted({h for h in re.findall(r'href="([^"]+)"', html2) if h.lower().endswith(".pdf")})
        print(f"   ❌ không khớp title 06. Trang có {len(pdf)} PDF, 15 cái đầu:")
        for p in pdf[:15]:
            print(f"      {p}")
        return
    url_pdf = tuyet_doi(ung[0])
    print(f"2) tải {url_pdf}")

    data = get(url_pdf, ref=trang_tai)
    if data[:4] != b"%PDF":
        print(f"   ❌ tải về {len(data):,}B nhưng KHÔNG phải PDF — nghi trang chặn")
        return
    dich = os.path.join(OUT, "CO_title06.html")     # tên adapter đang chờ (nội dung là PDF)
    open(dich, "wb").write(data)
    print(f"   → {len(data):,}B → {os.path.basename(dich)}")

    # ── B3: kiểm NGAY, đừng để tới lúc nạp vào Pi mới biết hỏng ────────────────
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "a.pdf"); open(f, "wb").write(data)
        subprocess.run(["pdftotext", "-enc", "UTF-8", f, td + "/a.txt"], check=False)
        t = open(td + "/a.txt", encoding="utf-8", errors="replace").read()
    muc = sorted(set(re.findall(r"\b(6-1-13\d\d(?:\.\d+)?)\.", t)))
    print(f"3) kiểm: {len(t):,} ký tự · {len(muc)} mục thuộc phần 13")
    print(f"   {', '.join(muc)}")
    if len(muc) < 10:
        print("   ⚠ ít mục bất thường — xem lại trước khi nạp vào Pi")
    print("\n   Kho đang giữ 15 mục (CRS 2024). Khác con số này nghĩa là Colorado đã sửa luật.")

    json.dump({"nam": nam_moi, "url": url_pdf, "n_muc": len(muc), "muc": muc},
              open(os.path.join(OUT, "_co_crs.json"), "w"), ensure_ascii=False, indent=1)
    print("\n>>> XONG. Tải artifact 'state-raw' → trên Mac giải nén → raw_to_pi.py → "
          "load_luatqt.py us_states3 → embed_dieu_qt.py")


if __name__ == "__main__":
    main()

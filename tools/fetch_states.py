#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải luật BANG Mỹ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ).

Nhiều cổng lập pháp bang CHẶN truy cập từ ngoài nước Mỹ (timeout) hoặc chặn bot (403).
Máy ở Việt Nam (sandbox / Pi / Mac) đều không lấy được; runner GitHub ở Mỹ thì vào được.

⚠ DỮ LIỆU KHÔNG LƯU TRONG REPO: workflow đóng gói state_raw/ thành artifact (7 ngày),
   rồi nạp vào Pi (bảng luatqt_db.raw_file). Repo/Mac chỉ là đường trung chuyển.

ĐỢT 4 — 3 bang cuối. Đợt 3 thất bại KHÔNG phải vì bị chặn, mà vì SAI NGUỒN:
  • KY: chapter.aspx?id=38940 hoá ra là KRS 351 (Mỏ), không phải 367; và HB15 tải về
        là dự luật 2022 về DÂN QUYỀN. CDPA của Kentucky là HB 15 khoá **2024**.
  • UT: 19 trang mục đều đúng 2.179 ký tự = vỏ SPA. Mục lục có nhúng chuỗi phiên bản
        'C13-61_2022050420231231' → thử tham số ?v= và bản in.
  • IN: bundle JS không có endpoint /api/, nhưng lộ ra 'archive.iga.in.gov'.

MẸO RÚT RA TỪ NEBRASKA: nhiều cổng có BẢN IN TĨNH nấp sau giao diện JS
('&print=true'). Luôn thử bản in trước khi kết luận là SPA không lấy được.
"""
import urllib.request, ssl, os, re, json, time

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state_raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
LOG = []


def H(ref=None):
    h = {"User-Agent": UA,
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9", "Upgrade-Insecure-Requests": "1"}
    if ref:
        h["Referer"] = ref
    return h


def get(url, ref=None, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H(ref)),
                                timeout=timeout, context=CTX) as r:
        return r.read()


def grab(name, url, ref=None, im=False):
    try:
        data = get(url, ref=ref)
        kind = ".pdf" if data[:4] == b"%PDF" else ".html"
        open(os.path.join(OUT, name + kind), "wb").write(data)
        if not im:
            print(f"OK   {name:22} {len(data):>9,}B {kind}")
        LOG.append({"name": name, "url": url, "bytes": len(data), "ok": True})
        return data
    except Exception as e:
        if not im:
            print(f"LỖI  {name:22} {type(e).__name__}: {str(e)[:55]}")
        LOG.append({"name": name, "url": url, "ok": False, "err": f"{type(e).__name__}: {e}"})
        return None


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── KENTUCKY — CDPA = HB 15 khoá 2024 (KRS 367.3611 et seq.) ──
    print("KY: dự luật đã ban hành khoá 2024 + tra đúng chương KRS 367")
    for lab, u in [("KY24_HB15", "https://apps.legislature.ky.gov/recorddocuments/bill/24RS/hb15/bill.pdf"),
                   ("KY24_HB15_enr", "https://apps.legislature.ky.gov/recorddocuments/bill/24RS/hb15/orig_bill.pdf"),
                   ("KY24_HB15_alt", "https://apps.legislature.ky.gov/record/24rs/hb15.html")]:
        d = grab(lab, u, ref="https://apps.legislature.ky.gov/")
        if d and d[:4] == b"%PDF" and len(d) > 20000:
            break
    # tìm đúng id chương 367 bằng cách quét trang danh mục chương
    idx = grab("KY_chapters", "https://apps.legislature.ky.gov/law/statutes/", ref="https://apps.legislature.ky.gov/")
    if idx:
        html = idx.decode("utf-8", "replace")
        # dòng nào ghi 'Chapter 367' thì lấy id kèm theo
        m = re.search(r'chapter\.aspx\?id=(\d+)[^>]*>\s*367\b', html, re.I) or \
            re.search(r'>\s*367\b[^<]*</a>', html)
        print("     KY chương 367 →", m.group(0)[:60] if m else "KHÔNG THẤY (xem KY_chapters.html)")
        if m and m.lastindex:
            grab("KY_367_real", f"https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id={m.group(1)}",
                 ref="https://apps.legislature.ky.gov/law/statutes/")

    # ── UTAH — UCPA (13-61): thử bản in + tham số phiên bản + dự luật gốc ──
    print("UT: bản in / tham số phiên bản / dự luật SB 227 (2022)")
    ver = None
    ut_idx = grab("UT_idx2", "https://le.utah.gov/xcode/Title13/Chapter61/13-61.html")
    if ut_idx:
        mv = re.search(r"(C13-61_\d+)", ut_idx.decode("utf-8", "replace"))
        ver = mv.group(1) if mv else None
        print("     chuỗi phiên bản:", ver)
    for lab, u in [("UT_print", "https://le.utah.gov/xcode/Title13/Chapter61/13-61.html?print=on"),
                   ("UT_S101_v", f"https://le.utah.gov/xcode/Title13/Chapter61/13-61-S101.html?v={ver}_13-61-S101" if ver else None),
                   ("UT_S101_plain", "https://le.utah.gov/xcode/Title13/Chapter61/13-61-S101.html?v=C13-61-S101_2022050420220504"),
                   ("UT_SB227", "https://le.utah.gov/~2022/bills/static/SB0227.pdf"),
                   ("UT_SB227_htm", "https://le.utah.gov/~2022/bills/sbillenr/SB0227.pdf")]:
        if u:
            grab(lab, u, ref="https://le.utah.gov/xcode/Title13/Chapter61/13-61.html")

    # ── INDIANA — IC 24-15: thử site lưu trữ + bản in ──
    print("IN: archive.iga.in.gov + bản in")
    for lab, u in [("IN_arch1", "https://archive.iga.in.gov/2024/ic/titles/024#24-15"),
                   ("IN_arch2", "https://archive.iga.in.gov/2023/ic/titles/024"),
                   ("IN_arch3", "https://archive.iga.in.gov/static-documents/2/4/-/1/24-1-5/ic-24-15.pdf"),
                   ("IN_print", "https://iga.in.gov/laws/2025/ic/titles/24/articles/15?print=true"),
                   ("IN_SEA5_24", "https://iga.in.gov/pdf-documents/123/2023/senate/bills/SB0005/SB0005.06.ENRS.pdf"),
                   ("IN_leg", "https://iga.in.gov/legislative/2023/bills/senate/5/details")]:
        grab(lab, u, ref="https://iga.in.gov/")

    json.dump(LOG, open(os.path.join(OUT, "_log_actions.json"), "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for x in LOG if x["ok"])
    print(f"\n>>> XONG: {ok}/{len(LOG)} lượt tải thành công → {OUT}")


if __name__ == "__main__":
    main()

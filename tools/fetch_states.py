#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải luật BANG Mỹ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ).

Nhiều cổng lập pháp bang CHẶN truy cập từ ngoài nước Mỹ (timeout) hoặc chặn bot (403).
Máy ở Việt Nam (sandbox / Pi / Mac) đều không lấy được; runner GitHub ở Mỹ thì vào được.

⚠ DỮ LIỆU KHÔNG LƯU TRONG REPO: workflow đóng gói state_raw/ thành artifact (7 ngày),
   sau đó nạp vào Pi (bảng luatqt_db.raw_file). Repo/Mac chỉ là đường trung chuyển.

ĐỢT 2 — vá theo đúng cấu trúc thật đã soi được từ file đợt 1:
  • UT: trang chương là JS, nhưng nhúng tên file TOÀN CHƯƠNG 'C13-61_<version>.html' → bóc ra tải.
  • NE: trang chương có link từng mục '/laws/statutes.php?statute=87-11NN' → crawl (bỏ &print).
  • RI: link mục là '.htm' CHỮ THƯỜNG (đợt 1 regex viết hoa nên trượt).
  • KY/IN/TN: cổng tra cứu là SPA → dùng PDF DỰ LUẬT ĐÃ BAN HÀNH (tĩnh).
  • CT: máy chủ lỗi chuỗi chứng chỉ → tắt verify RIÊNG cho host này.
  • NH/MN/MD: thử các biến thể đường dẫn (đợt 1 đoán sai).
"""
import urllib.request, ssl, os, re, json, time

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state_raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX_NOVERIFY = ssl._create_unverified_context()      # chỉ dùng cho host lỗi chuỗi chứng chỉ


def H(ref=None):
    h = {"User-Agent": UA,
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9", "Upgrade-Insecure-Requests": "1"}
    if ref:
        h["Referer"] = ref
    return h


def get(url, ref=None, timeout=45, noverify=False):
    ctx = CTX_NOVERIFY if noverify else CTX
    with urllib.request.urlopen(urllib.request.Request(url, headers=H(ref)),
                                timeout=timeout, context=ctx) as r:
        return r.read()


def save(name, data):
    kind = ".pdf" if data[:4] == b"%PDF" else ".html"
    p = os.path.join(OUT, name + kind)
    open(p, "wb").write(data)
    return len(data), kind


LOG = []


def grab(name, url, ref=None, noverify=False):
    try:
        data = get(url, ref=ref, noverify=noverify)
        n, kind = save(name, data)
        print(f"OK   {name:22} {n:>9,}B {kind}")
        LOG.append({"name": name, "url": url, "bytes": n, "ok": True})
        return data
    except Exception as e:
        print(f"LỖI  {name:22} {type(e).__name__}: {str(e)[:60]}")
        LOG.append({"name": name, "url": url, "ok": False, "err": f"{type(e).__name__}: {e}"})
        return None


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── CONNECTICUT — CTDPA (Conn. Gen. Stat. ch. 743jj) — lỗi chuỗi chứng chỉ ──
    grab("CT_chap743jj", "https://www.cga.ct.gov/current/pub/chap_743jj.htm", noverify=True)

    # ── UTAH — UCPA (Utah Code ch. 13-61): lấy FILE TOÀN CHƯƠNG từ tên nhúng trong trang ──
    idx = grab("UT_13-61_idx", "https://le.utah.gov/xcode/Title13/Chapter61/13-61.html")
    if idx:
        m = re.search(r"(C13-61_\d+\.html)", idx.decode("utf-8", "replace"))
        if m:
            grab("UT_13-61_full",
                 f"https://le.utah.gov/xcode/Title13/Chapter61/{m.group(1)}",
                 ref="https://le.utah.gov/xcode/Title13/Chapter61/13-61.html")
        else:
            print("     ⚠ không thấy tên file toàn chương trong UT index")

    # ── RHODE ISLAND — RIDTPA (R.I.G.L. ch. 6-48.1): link '.htm' chữ thường ──
    ri_base = "http://webserver.rilegislature.gov/Statutes/TITLE6/6-48.1/"
    ri = grab("RI_6-48.1_idx", ri_base + "INDEX.htm")
    if ri:
        hrefs = sorted(set(re.findall(r'href="(6-48\.1-\d+\.htm)"', ri.decode("utf-8", "replace"), re.I)))
        print(f"     → {len(hrefs)} mục RI")
        for h in hrefs:
            grab(f"RI_sub_{h.split('-')[-1].split('.')[0]}", ri_base + h, ref=ri_base + "INDEX.htm")
            time.sleep(0.2)

    # ── NEBRASKA — Data Privacy Act (Neb. Rev. Stat. 87-1101 et seq.) ──
    ne = grab("NE_chap87", "https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=87")
    if ne:
        nums = sorted(set(re.findall(r"statute=(87-11\d\d)", ne.decode("utf-8", "replace"))))
        print(f"     → {len(nums)} mục NE")
        for n in nums:
            grab(f"NE_sec_{n}", f"https://nebraskalegislature.gov/laws/statutes.php?statute={n}",
                 ref="https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=87")
            time.sleep(0.2)

    # ── NEW HAMPSHIRE — NH RSA 507-H: thử các biến thể đường dẫn ──
    for lab, u in [("NH_v1", "https://www.gencourt.state.nh.us/rsa/html/LII/507-H/507-H-mrg.htm"),
                   ("NH_v2", "https://www.gencourt.state.nh.us/rsa/html/L/507-H/507-H-mrg.htm"),
                   ("NH_v3", "https://www.gencourt.state.nh.us/rsa/html/NHTOC/NHTOC-LII-507-H.htm")]:
        if grab(lab, u, ref="https://www.gencourt.state.nh.us/rsa/html/indexes/default.html"):
            break

    # ── MINNESOTA — CDPA là chương 325O (đợt 1 mọi URL đều 404) ──
    for lab, u in [("MN_v1", "https://www.revisor.mn.gov/statutes/cite/325O/"),
                   ("MN_v2", "https://www.revisor.mn.gov/statutes/2025/cite/325O/"),
                   ("MN_v3", "https://www.revisor.mn.gov/statutes/cite/325O.01/"),
                   ("MN_v4", "https://www.revisor.mn.gov/statutes/part/325O.01")]:
        if grab(lab, u, ref="https://www.revisor.mn.gov/statutes/"):
            break

    # ── MARYLAND — MODPA (Md. Code Com. Law 14-4601): trang web nạp ajax → thử PDF ──
    for lab, u in [("MD_pdf1", "https://mgaleg.maryland.gov/2025RS/Statute_Web/gcl/14-4601.pdf"),
                   ("MD_pdf2", "https://mgaleg.maryland.gov/2024RS/Statute_Web/gcl/14-4601.pdf"),
                   ("MD_bill", "https://mgaleg.maryland.gov/2024RS/bills/sb/sb0541T.pdf")]:
        if grab(lab, u, ref="https://mgaleg.maryland.gov/"):
            break

    # ── KENTUCKY / INDIANA / TENNESSEE — cổng SPA → PDF dự luật đã ban hành ──
    grab("KY_HB15", "https://apps.legislature.ky.gov/recorddocuments/bill/22RS/hb15/bill.pdf",
         ref="https://apps.legislature.ky.gov/")
    for lab, u in [("IN_SB5_a", "https://iga.in.gov/pdf-documents/123/2023/senate/bills/SB0005/SB0005.06.ENRS.pdf"),
                   ("IN_SB5_b", "https://iga.in.gov/publications/enrolled-acts/2023/senate/5"),
                   ("IN_SB5_c", "https://iga.in.gov/static-documents/e/9/1/a/e91a1b4c/SB0005.06.ENRS.pdf")]:
        d = grab(lab, u, ref="https://iga.in.gov/")
        if d and d[:4] == b"%PDF":
            break
    for lab, u in [("TN_SB73", "https://www.capitol.tn.gov/Bills/113/Bill/SB0073.pdf"),
                   ("TN_HB1181", "https://www.capitol.tn.gov/Bills/113/Bill/HB1181.pdf"),
                   ("TN_SB73_amend", "https://www.capitol.tn.gov/Bills/113/Amend/SA0273.pdf")]:
        d = grab(lab, u, ref="https://www.capitol.tn.gov/")
        if d and d[:4] == b"%PDF":
            break

    json.dump(LOG, open(os.path.join(OUT, "_log_actions.json"), "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for x in LOG if x["ok"])
    print(f"\n>>> XONG: {ok}/{len(LOG)} lượt tải thành công → {OUT}")


if __name__ == "__main__":
    main()

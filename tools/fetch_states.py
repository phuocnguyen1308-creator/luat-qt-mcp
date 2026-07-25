#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải luật BANG Mỹ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ).

Nhiều cổng lập pháp bang CHẶN truy cập từ ngoài nước Mỹ (timeout) hoặc chặn bot (403).
Máy ở Việt Nam (sandbox / Pi / Mac) đều không lấy được; runner GitHub ở Mỹ thì vào được.

⚠ DỮ LIỆU KHÔNG LƯU TRONG REPO: workflow đóng gói state_raw/ thành artifact (7 ngày),
   sau đó nạp vào Pi (bảng luatqt_db.raw_file). Repo/Mac chỉ là đường trung chuyển.

ĐỢT 3 — chỉ còn 4 bang, mỗi bang một cách:
  • KY: trang chương chỉ có link 'statute.aspx?id=NNNNN' (số hiệu KRS do JS render)
        → tải HẾT rồi lọc sau ở khâu parse.
  • UT: file "toàn chương" là vỏ rỗng → duyệt URL TỪNG MỤC '13-61-S{n}.html'.
  • NE: trang mục nạp JS, nhưng có biến thể '&print=true' — thử bản in.
  • IN: cổng là SPA, mọi PDF dự luật đều trả trang lỗi → TẢI CẢ BUNDLE JS để soi
        endpoint API (cách đã hiệu quả với UAE và Maryland: dò trước, đoán sau).

(4 bang đã xong ở đợt trước: CT, NH, RI, TN — không tải lại.)
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


def save(name, data):
    kind = ".pdf" if data[:4] == b"%PDF" else (".js" if name.endswith("_js") else ".html")
    open(os.path.join(OUT, name + kind), "wb").write(data)
    return len(data), kind


def grab(name, url, ref=None, im=False):
    """im=True: chỉ ghi log gọn (dùng khi tải hàng chục trang con)."""
    try:
        data = get(url, ref=ref)
        n, kind = save(name, data)
        if not im:
            print(f"OK   {name:24} {n:>9,}B {kind}")
        LOG.append({"name": name, "url": url, "bytes": n, "ok": True})
        return data
    except Exception as e:
        if not im:
            print(f"LỖI  {name:24} {type(e).__name__}: {str(e)[:55]}")
        LOG.append({"name": name, "url": url, "ok": False, "err": f"{type(e).__name__}: {e}"})
        return None


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── KENTUCKY — KRS 367.3611 et seq. (Consumer Data Protection Act) ──
    ky_idx = grab("KY_367_idx", "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=38940")
    if ky_idx:
        ids = sorted(set(re.findall(r'statute\.aspx\?id=(\d+)', ky_idx.decode("utf-8", "replace"))),
                     key=int)
        print(f"     → {len(ids)} mục KY (tải hết, lọc 367.36xx ở khâu parse)")
        ok = 0
        for i in ids:
            if grab(f"KY_sec_{i}", f"https://apps.legislature.ky.gov/law/statutes/statute.aspx?id={i}",
                    ref="https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=38940", im=True):
                ok += 1
            time.sleep(0.15)
        print(f"     → tải được {ok}/{len(ids)}")

    # ── UTAH — UCPA (Utah Code 13-61): duyệt URL từng mục ──
    print("UT: duyệt URL từng mục 13-61-S{n}.html")
    ut_ok = 0
    for phan in (1, 2, 3, 4, 5):
        for so in range(1, 12):
            n = phan * 100 + so
            d = grab(f"UT_sec_{n}", f"https://le.utah.gov/xcode/Title13/Chapter61/13-61-S{n}.html",
                     ref="https://le.utah.gov/xcode/Title13/Chapter61/13-61.html", im=True)
            if d and len(d) > 4000:          # trang thật ~10KB, trang lỗi nhỏ hơn nhiều
                ut_ok += 1
            time.sleep(0.15)
    print(f"     → {ut_ok} mục UT có nội dung")

    # ── NEBRASKA — Data Privacy Act (Neb. Rev. Stat. 87-1101 et seq.): thử bản IN ──
    print("NE: thử biến thể &print=true")
    ne_ok = 0
    for n in range(1101, 1131):
        d = grab(f"NE_print_87-{n}", f"https://nebraskalegislature.gov/laws/statutes.php?statute=87-{n}&print=true",
                 ref="https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=87", im=True)
        if d and len(d) > 3000:
            ne_ok += 1
        time.sleep(0.15)
    print(f"     → {ne_ok} mục NE tải được (kiểm nội dung ở khâu parse)")

    # ── INDIANA — IC 24-15: cổng SPA → tải shell + BUNDLE JS để soi endpoint API ──
    print("IN: tải shell + bundle JS để dò API")
    shell = grab("IN_shell", "https://iga.in.gov/laws/2025/ic/titles/24/articles/15")
    if shell:
        html = shell.decode("utf-8", "replace")
        srcs = sorted(set(re.findall(r'src="([^"]+\.js)"', html)))[:6]
        print(f"     → {len(srcs)} bundle JS")
        for k, s in enumerate(srcs):
            u = s if s.startswith("http") else "https://iga.in.gov" + (s if s.startswith("/") else "/" + s)
            grab(f"IN_bundle{k}_js", u, ref="https://iga.in.gov/", im=True)
    for lab, u in [("IN_api1", "https://api.iga.in.gov/2025/ic/24/15"),
                   ("IN_api2", "https://iga.in.gov/api/laws/2025/ic/titles/24/articles/15"),
                   ("IN_api3", "https://iga.in.gov/laws/2025/ic/titles/24/articles/15/chapters")]:
        grab(lab, u, ref="https://iga.in.gov/")

    json.dump(LOG, open(os.path.join(OUT, "_log_actions.json"), "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for x in LOG if x["ok"])
    print(f"\n>>> XONG: {ok}/{len(LOG)} lượt tải thành công → {OUT}")


if __name__ == "__main__":
    main()

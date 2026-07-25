#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải luật BANG Mỹ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ).

Lý do tồn tại: nhiều cổng lập pháp bang CHẶN truy cập từ ngoài nước Mỹ (timeout) hoặc
chặn bot (403). Máy ở Việt Nam — sandbox, Pi, Mac — đều không lấy được. Runner của
GitHub Actions nằm ở Mỹ nên đi thẳng vào được.

Luồng: Actions chạy file này → lưu file thô vào state_raw/ → commit vào repo →
Claude đọc qua raw.githubusercontent.com để parse và nạp DB.

Chỉ dùng thư viện chuẩn (không cài gì thêm).
"""
import urllib.request, ssl, os, re, json, time

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state_raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()


def H(ref=None):
    h = {"User-Agent": UA,
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9",
         "Upgrade-Insecure-Requests": "1"}
    if ref:
        h["Referer"] = ref
    return h


def get(url, ref=None, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H(ref)),
                                timeout=timeout, context=CTX) as r:
        return r.read()


# name → (URL trang chính, regex link mục con (None nếu không cần), base URL để ghép)
TARGETS = {
    # --- nhóm TIMEOUT với IP ngoài Mỹ ---
    "CT_chap743jj":  ("https://www.cga.ct.gov/current/pub/chap_743jj.htm", None, None),
    "UT_13-61_idx":  ("https://le.utah.gov/xcode/Title13/Chapter61/13-61.html",
                      r'href="(/xcode/Title13/Chapter61/13-61-S\d+\.html)"', "https://le.utah.gov"),
    "RI_6-48.1_idx": ("http://webserver.rilegislature.gov/Statutes/TITLE6/6-48.1/INDEX.htm",
                      r'href="([^"]*6-48\.1-\d+\.HTM)"', "http://webserver.rilegislature.gov/Statutes/TITLE6/6-48.1/"),
    "OR_646A":       ("https://www.oregonlegislature.gov/bills_laws/ors/ors646A.html", None, None),
    "KY_367_idx":    ("https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=38940",
                      r'href="(/law/statutes/statute\.aspx\?id=\d+)"', "https://apps.legislature.ky.gov"),
    "NJ_PL23-266":   ("https://pub.njleg.state.nj.us/Bills/2022/PL23/266_.PDF", None, None),
    "NE_87-1101":    ("https://nebraskalegislature.gov/laws/statutes.php?statute=87-1101", None, None),
    "NE_chap87":     ("https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=87", None, None),
    # --- nhóm 403 (chặn bot) ---
    "NH_507-H":      ("https://www.gencourt.state.nh.us/rsa/html/L/507-H/507-H-mrg.htm", None, None),
    "CO_title06":    ("https://leg.colorado.gov/sites/default/files/images/olls/crs2024-title-06.pdf", None, None),
    "TN_justia":     ("https://law.justia.com/codes/tennessee/title-47/chapter-18/part-32/", None, None),
    # --- Minnesota: CDPA là chương 325O (KHÔNG phải 325M) ---
    "MN_325O":       ("https://www.revisor.mn.gov/statutes/cite/325O", None, None),
    "MN_325O_full":  ("https://www.revisor.mn.gov/statutes/cite/325O/full", None, None),
    # --- Maryland: trang nạp bằng ajax, thử cả bản in ---
    "MD_14-4601":    ("https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gcl&section=14-4601&enactments=false", None, None),
    "MD_subtitle46": ("https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gcl&section=14-4601&enactments=False&print=true", None, None),
    # --- Indiana: cổng là SPA → thử PDF dự luật đã ban hành ---
    "IN_SB5_v1":     ("https://iga.in.gov/pdf-documents/123/2023/senate/bills/SB0005/SB0005.06.ENRS.pdf", None, None),
    "IN_SB5_v2":     ("https://iga.in.gov/static-documents/1/3/9/b/139b0c2e/SB0005.06.ENRS.pdf", None, None),
}


def save(name, data):
    kind = ".pdf" if data[:5] == b"%PDF" else ".html"
    path = os.path.join(OUT, name + kind)
    open(path, "wb").write(data)
    return path, len(data), kind


def main():
    os.makedirs(OUT, exist_ok=True)
    log = []
    for name, (url, sub_re, base) in TARGETS.items():
        try:
            data = get(url)
            p, n, kind = save(name, data)
            print(f"OK   {name:16} {n:>9,}B {kind}")
            log.append({"name": name, "url": url, "bytes": n, "ok": True})
        except Exception as e:
            print(f"LỖI  {name:16} {type(e).__name__}: {str(e)[:60]}")
            log.append({"name": name, "url": url, "ok": False, "err": f"{type(e).__name__}: {e}"})
            continue
        # tải trang mục con nếu có mẫu link
        if sub_re:
            html = data.decode("utf-8", "replace")
            hrefs, seen = [], set()
            for h in re.findall(sub_re, html):
                if h not in seen:
                    seen.add(h); hrefs.append(h)
            print(f"     → {len(hrefs)} link mục con")
            for i, h in enumerate(hrefs[:60]):
                full = h if h.startswith("http") else (base or "") + h
                try:
                    d2 = get(full, ref=url)
                    save(f"{name}_sub{i:03d}", d2)
                except Exception as e:
                    print(f"     LỖI sub{i:03d}: {type(e).__name__}")
                time.sleep(0.3)
        time.sleep(0.5)
    json.dump(log, open(os.path.join(OUT, "_log_actions.json"), "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for x in log if x["ok"])
    print(f"\n>>> XONG: {ok}/{len(TARGETS)} nguồn chính tải được → {OUT}")


if __name__ == "__main__":
    main()

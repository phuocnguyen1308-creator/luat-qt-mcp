#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KHÁM PHÁ NGUỒN cho 3 bang còn hụt — CHẠY TRÊN GITHUB ACTIONS (runner ở Mỹ). Chạy tay.

VÌ SAO CẦN: Utah/Tennessee/Colorado đã qua 4 vòng vá mà vẫn không soi được, và cả 4 vòng
đều hỏng vì CÙNG MỘT LÝ DO — tôi ĐOÁN đường dẫn từ Việt Nam, nơi không mở được các cổng
này để nhìn. Đoán trúng thì may, trật thì mất một vòng chạy. Thay vì đoán vòng thứ năm,
script này để runner LIỆT KÊ những gì thật sự có trên trang: mọi liên kết và mọi lệnh gọi
mạng chứa từ khoá của bang đó.

Khác với giam_sat_states.py: cái kia TRẢ LỜI "luật có đổi không", cái này TRẢ LỜI "địa chỉ
đúng nằm ở đâu". Chạy một lần, đọc kết quả, sửa bảng BANG rồi bỏ script này đi cũng được.

⚠ CHỈ ĐỌC. Không ghi gì vào repo, không đụng dữ liệu.

Chạy: Actions → "Khám phá nguồn 3 bang" → Run workflow.
"""
import re, time, json, sys, urllib.request, ssl

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

# (bang, URL, [từ khoá cần tìm trong liên kết], có cần render JS không)
MUC_TIEU = [
    ("US-UT-UCPA", "https://le.utah.gov/xcode/Title13/Chapter61/13-61.html",
     ["13-61", "S1", "xcode", "Chapter61"], True),
    ("US-TN-TIPA", "https://codes.findlaw.com/tn/title-47-commercial-instruments-and-transactions/",
     ["47-18", "chapter-18", "part-32"], False),
    ("US-CO-CPA", "https://leg.colorado.gov/agencies/office-legislative-legal-services/colorado-revised-statutes",
     ["crs", "title-06", "title06", ".pdf"], False),
    ("US-CO-CPA", "https://leg.colorado.gov/colorado-revised-statutes",
     ["crs", "title-06", "title06", ".pdf"], False),
]

_drv = None


def trinh_duyet():
    global _drv
    if _drv is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        o = Options()
        for a in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
            o.add_argument(a)
        o.add_argument("--user-agent=" + UA)
        # bật ghi nhật ký hiệu năng để đọc được CÁC LỆNH GỌI MẠNG của SPA — chính chỗ này
        # mới lộ ra địa chỉ thật mà trang dùng để nạp mục lục điều
        o.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        _drv = webdriver.Chrome(options=o)
        _drv.set_page_load_timeout(60)
    return _drv


def lay_tinh(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA,
                                             "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(r, timeout=45, context=CTX) as f:
        return f.read().decode("utf-8", "replace")


def lay_js(url):
    d = trinh_duyet()
    d.get(url)
    time.sleep(12)                      # để SPA gọi hết API
    goi = []
    try:
        for m in d.get_log("performance"):
            try:
                msg = json.loads(m["message"])["message"]
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                u = msg["params"]["request"]["url"]
                if not u.startswith("data:") and not re.search(r"\.(png|jpg|gif|svg|woff2?|css)", u):
                    goi.append(u)
    except Exception as e:
        print(f"    (không đọc được nhật ký mạng: {type(e).__name__})")
    return d.page_source, goi


def main():
    for ma, url, khoa, can_js in MUC_TIEU:
        print("\n" + "=" * 78)
        print(f"{ma}  ←  {url}")
        print("=" * 78)
        goi = []
        try:
            if can_js:
                nguon, goi = lay_js(url)
            else:
                nguon = lay_tinh(url)
        except Exception as e:
            print(f"  ! không lấy được: {type(e).__name__}: {str(e)[:90]}")
            continue
        print(f"  {len(nguon):,} ký tự HTML")

        # 1. mọi liên kết chứa từ khoá
        href = re.findall(r'(?:href|src)="([^"]+)"', nguon)
        hop = sorted({h for h in href if any(k.lower() in h.lower() for k in khoa)})
        print(f"\n  ── LIÊN KẾT khớp từ khoá ({len(hop)}) ──")
        for h in hop[:40]:
            print(f"     {h[:140]}")
        if len(hop) > 40:
            print(f"     … còn {len(hop)-40} cái nữa")

        # 2. các lệnh gọi mạng (chỉ có khi render) — chỗ SPA lộ địa chỉ API thật
        if goi:
            loc = sorted({g for g in goi if any(k.lower() in g.lower() for k in khoa)}) or sorted(set(goi))
            print(f"\n  ── LỆNH GỌI MẠNG khi trang dựng ({len(loc)}) ──")
            for g in loc[:30]:
                print(f"     {g[:140]}")

        # 3. mọi chuỗi trông giống số hiệu điều luật, để biết trang có chứa cái ta cần không
        chu = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", nguon)
        chu = re.sub(r"<[^>]+>", " ", chu)
        so = sorted(set(re.findall(r"\b\d{1,3}[-.:]\d{1,4}(?:[-.]\d{1,4})?\b", chu)))
        print(f"\n  ── SỐ dạng điều luật thấy trong chữ ({len(so)}) ── {', '.join(so[:40])}")

    if _drv is not None:
        try:
            _drv.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()

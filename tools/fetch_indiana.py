#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INDIANA — IC 24-15 — CHẠY TRÊN GITHUB ACTIONS, có RENDER (headless Chrome).

Vì sao phải vừa "ở Mỹ" vừa "render":
  • iga.in.gov là SPA định tuyến catch-all: mọi URL trả cùng vỏ HTML 691 byte.
  • Chặn ở TẦNG TÀI NGUYÊN: xin /static/js/main.*.js từ Việt Nam thì server trả HTML
    (console báo "Unexpected token '<'") → app không bao giờ boot, headless trên Pi vô ích.
    Cùng file đó tải từ runner Mỹ ra 2,3 MB JS thật.
  → Kết luận: phải render BẰNG TRÌNH DUYỆT ĐẶT TẠI MỸ. Đây là ca duy nhất trong dự án
    cần gộp cả hai mẹo (US runner + headless), các bang khác chỉ cần một trong hai.

Kết quả ghi ra state_raw/IN_ic24-15.json (đã trích sẵn điều) để Claude nạp thẳng,
không cần parse HTML lần nữa.
"""
import json, os, re, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state_raw")

# ⚠ Sau khi giả UA thì app BOOT được, nhưng /laws/2025/... trả 404: IC 24-15 hiệu lực
#   01/01/2026 nên nằm ở ấn bản 2026. Thử lần lượt, lấy trang nào có nội dung thật.
UNG_VIEN = [
    "https://iga.in.gov/laws/2026/ic/titles/24/articles/15",
    "https://iga.in.gov/laws/2026/ic/titles/24",
    "https://iga.in.gov/laws/2025/ic/titles/24",
    "https://iga.in.gov/laws/ic/2026/titles/24/articles/15",
]
GOC = UNG_VIEN[0]

TRICH_JS = r"""
function tx(e){return (e.innerText||'').replace(/\s+/g,' ').trim();}
const out = {bodyLen:(document.body?document.body.innerText.length:0), rows:[], links:[]};
out.links = [...document.querySelectorAll('a')]
  .map(a => a.getAttribute('href')||'')
  .filter(h => /\/ic\/titles\/24\/articles\/15\/chapters\/\d+/.test(h));
const all = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,div')];
for (const e of all) {
  const t = tx(e);
  // 'IC 24-15-3-1 Tiêu đề … nội dung'
  const m = t.match(/^IC\s+(24-15-\d+(?:\.\d+)?-\d+(?:\.\d+)?)\s+(.{2,120}?)(?:\s\s|\sSec\.|$)/);
  if (m && t.length > 80) out.rows.push([m[1], m[2], t]);
}
return out;
"""


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def driver():
    """⚠ PHẢI giả UA thường. Selenium mặc định gửi 'HeadlessChrome' → iga.in.gov trả vỏ 668B,
    trong khi CÙNG runner tải file JS bằng UA Chrome bình thường lại ra 2,3 MB thật.
    Đây là lý do lần đầu render ra body rỗng (đã ẩn UA cho UK/NZ nhưng quên áp cho Indiana)."""
    o = Options()
    for a in ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
              "--window-size=1400,3000", "--disable-blink-features=AutomationControlled",
              f"--user-agent={UA}"]:
        o.add_argument(a)
    try:
        o.add_experimental_option("excludeSwitches", ["enable-automation"])
    except Exception:
        pass
    d = webdriver.Chrome(options=o)
    try:                                  # ẩn dấu vết tự động hoá
        d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                          {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
    except Exception:
        pass
    d.set_page_load_timeout(120)
    return d


def cho(d, muc=1500, giay=40):
    truoc = -1
    for _ in range(giay // 2):
        try:
            n = d.execute_script("return (document.body?document.body.innerText.length:0)")
        except Exception:
            n = 0
        if n > muc and n == truoc:
            return n
        truoc = n
        time.sleep(2)
    return truoc


def main():
    os.makedirs(OUT, exist_ok=True)
    d = driver()

    # ⚠ ĐỪNG ĐOÁN URL NỮA: 4 mẫu đoán đều 404. Đi theo chính điều hướng của site —
    #   mở trang Laws, đọc link thật, lần tới Title 24 rồi Article 15.
    def mo(u):
        d.get(u); cho(d)
        body = d.execute_script("return document.body ? document.body.innerText : ''") or ""
        links = d.execute_script(
            "return [...document.querySelectorAll('a')].map(a=>[a.innerText.trim().slice(0,50),"
            "a.getAttribute('href')||'']).filter(x=>x[1])")
        return body, links

    nav = {}
    body, links = mo("https://iga.in.gov/laws")
    nav["/laws"] = links[:80]
    print(f"· /laws → body {len(body)} · {len(links)} link")
    ic = [l for l in links if re.search(r"/ic\b|indiana-code|/laws/\d{4}", l[1])][:12]
    print("   link kiểu Bộ luật:", ic[:6])

    res, GOC_OK = {"rows": [], "links": []}, None
    for ten, href in ic:
        u = href if href.startswith("http") else "https://iga.in.gov" + href
        b2, l2 = mo(u)
        nav[href] = l2[:80]
        t24 = [l for l in l2 if re.search(r"\b24\b", l[0]) or re.search(r"titles?/0?24\b", l[1])][:5]
        print(f"   {href} → body {len(b2)} · gợi ý Title 24: {t24[:3]}")
        if t24:
            u24 = t24[0][1] if t24[0][1].startswith("http") else "https://iga.in.gov" + t24[0][1]
            b3, l3 = mo(u24)
            nav[t24[0][1]] = l3[:80]
            a15 = [l for l in l3 if re.search(r"\b15\b", l[0]) or re.search(r"articles?/0?15\b", l[1])][:5]
            print(f"      Title 24 → body {len(b3)} · gợi ý Article 15: {a15[:3]}")
            if a15:
                u15 = a15[0][1] if a15[0][1].startswith("http") else "https://iga.in.gov" + a15[0][1]
                b4, _ = mo(u15)
                res = d.execute_script(TRICH_JS)
                GOC_OK = u15
                print(f"      Article 15 → body {len(b4)} · {len(res['rows'])} điều")
                break
    json.dump(nav, open(os.path.join(OUT, "IN_nav.json"), "w"), ensure_ascii=False, indent=1)
    print(f"  → đã lưu IN_nav.json (cấu trúc link thật) · dùng {GOC_OK or 'KHÔNG TÌM RA'}")

    # ── PHƯƠNG ÁN CUỐI: render TRANG DỰ LUẬT để lấy link PDF luật đã ban hành ──
    # Duyệt Bộ luật là ngõ cụt: nội dung dựng bằng React Router, không có href để lần theo.
    # Nhưng IC 24-15 do SEA 5 (2023) tạo ra; trang dự luật có nút tải PDF — trước đây mọi
    # URL PDF đoán mò đều trả vỏ, giờ SPA boot được (đã sửa UA) nên link thật sẽ hiện ra.
    if not res["rows"]:
        for u in ["https://iga.in.gov/legislative/2023/bills/senate/5",
                  "https://iga.in.gov/legislative/2023/bills/senate/5/details",
                  "https://iga.in.gov/laws/2023/acts/senate/5"]:
            print(f"· thử trang dự luật {u}")
            b, links = mo(u)
            pdfs = [l for l in links if ".pdf" in l[1].lower()]
            print(f"    body {len(b)} · {len(pdfs)} link PDF: {[p[1][:60] for p in pdfs[:4]]}")
            for ten, href in pdfs[:6]:
                full = href if href.startswith("http") else "https://iga.in.gov" + href
                try:
                    import urllib.request
                    req = urllib.request.Request(full, headers={"User-Agent": UA})
                    data = urllib.request.urlopen(req, timeout=60).read()
                    if data[:4] == b"%PDF" and len(data) > 20000:
                        nm = "IN_" + re.sub(r"\W+", "_", ten or "bill")[:24] + ".pdf"
                        open(os.path.join(OUT, nm), "wb").write(data)
                        print(f"    ✔ lưu {nm} ({len(data):,}B)")
                except Exception as e:
                    print(f"    (tải hỏng: {type(e).__name__})")
            if pdfs:
                break

    # ⚠ LƯU DOM ĐÃ RENDER: lần trước chỉ nhận được '[]' mà không biết trang có nội dung hay
    #   không (log job cần đăng nhập mới xem được). Giữ lại HTML + text để soi ngoại tuyến,
    #   khỏi phải đoán — đúng nguyên tắc "dò trước, đoán sau".
    try:
        open(os.path.join(OUT, "IN_rendered.html"), "w", encoding="utf-8").write(d.page_source)
        body = d.execute_script("return document.body ? document.body.innerText : ''")
        open(os.path.join(OUT, "IN_body.txt"), "w", encoding="utf-8").write(body or "")
        print(f"  đã lưu IN_rendered.html ({len(d.page_source):,}) + IN_body.txt ({len(body or ''):,})")
        print("  --- 400 ký tự đầu của body ---")
        print("  ", (body or "")[:400].replace("\n", " | "))
    except Exception as e:
        print(f"  (không lưu được DOM: {type(e).__name__})")

    rows = list(res["rows"])
    hrefs, seen = [], set()
    for h in res["links"]:
        if h not in seen:
            seen.add(h)
            hrefs.append(h if h.startswith("http") else "https://iga.in.gov" + h)
    for h in hrefs:
        d.get(h); cho(d)
        r2 = d.execute_script(TRICH_JS)
        print(f"     {h.rsplit('/',1)[-1]}: {len(r2['rows'])} điều")
        rows += r2["rows"]
        time.sleep(0.4)
    d.quit()

    best = {}
    for num, tieu, body in rows:
        if num not in best or len(body) > len(best[num][2]):
            best[num] = (num, tieu.strip(" .—-"), body)
    kq = [{"so_dieu": k, "tieu_de": v[1], "noi_dung": v[2]}
          for k, v in sorted(best.items(), key=lambda x: [int(n) for n in re.findall(r"\d+", x[0])])]
    json.dump(kq, open(os.path.join(OUT, "IN_ic24-15.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n>>> {len(kq)} điều IC 24-15 → state_raw/IN_ic24-15.json")
    for x in kq[:5]:
        print(f"   IC {x['so_dieu']} — {x['tieu_de'][:55]}")


if __name__ == "__main__":
    main()

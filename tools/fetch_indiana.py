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
GOC = "https://iga.in.gov/laws/2025/ic/titles/24/articles/15"

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


def driver():
    o = Options()
    for a in ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
              "--window-size=1400,3000"]:
        o.add_argument(a)
    d = webdriver.Chrome(options=o)
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
    print(f"· mở {GOC}")
    d.get(GOC)
    n = cho(d)
    res = d.execute_script(TRICH_JS)
    print(f"  body {n} ký tự · {len(res['rows'])} điều · {len(res['links'])} chapter")

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

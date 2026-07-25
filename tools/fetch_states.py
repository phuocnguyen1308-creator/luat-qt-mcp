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

    # ── KENTUCKY — CDPA (KRS 367.3611 et seq.) ──
    # ⚠ KRS 367 (Consumer Protection) là chương RẤT LỚN (hàng trăm mục). Tải hết rồi lọc
    #   là sai lầm: chạy hơn 20 phút. Cách đúng — DÒ NHỊ PHÂN: id sắp theo thứ tự số mục,
    #   nên chỉ cần thăm dò thưa để tìm dải id ứng với 367.36xx rồi tải đúng dải đó.
    import io, subprocess, tempfile

    def so_muc(data):
        """Đọc số hiệu KRS từ PDF một mục (vd '367.3611'). None nếu không đọc được."""
        if data[:4] != b"%PDF":
            return None
        try:
            with tempfile.TemporaryDirectory() as td:
                f = os.path.join(td, "a.pdf"); open(f, "wb").write(data)
                subprocess.run(["pdftotext", "-enc", "UTF-8", f, td + "/a.txt"], check=False)
                t = open(td + "/a.txt", encoding="utf-8", errors="replace").read(300)
        except FileNotFoundError:
            print("     ⚠ máy không có pdftotext — không dò được số mục")
            return None
        except Exception:
            return None
        m = re.search(r"\b(367\.\d+)\b", t)
        return float(m.group(1)) if m else None

    ky = grab("KY_367_real", "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=39092",
              ref="https://apps.legislature.ky.gov/law/statutes/")
    if ky:
        ids = sorted(set(re.findall(r'statute\.aspx\?id=(\d+)',
                                   ky.decode("utf-8", "replace"))), key=int)
        print(f"     → chương có {len(ids)} mục; dò thưa để tìm dải 367.36xx")
        BASE = "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id="
        REF = "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=39092"
        mau = {}
        buoc = max(1, len(ids) // 25)                 # ~25 lượt thăm dò
        for k in range(0, len(ids), buoc):
            d = get(BASE + ids[k], ref=REF)
            n = so_muc(d)
            if n:
                mau[k] = n
            print(f"        mẫu[{k}] id={ids[k]} → {n}")
            time.sleep(0.15)
        # vị trí đầu tiên có số ≥ 367.36 và cuối cùng < 367.37
        trong = [k for k, v in mau.items() if 367.36 <= v < 367.37]
        if trong:
            lo = max(0, min(trong) - buoc)
            hi = min(len(ids), max(trong) + buoc + 1)
        else:                                         # không trúng mẫu → lấy quanh chỗ gần nhất
            gan = min(mau, key=lambda k: abs(mau[k] - 367.36)) if mau else 0
            lo, hi = max(0, gan - buoc), min(len(ids), gan + 2 * buoc)
        print(f"     → tải dải id[{lo}:{hi}] ({hi-lo} mục)")
        ok = 0
        for i in ids[lo:hi]:
            if grab(f"KY367_{i}", BASE + i, ref=REF, im=True):
                ok += 1
            time.sleep(0.15)
        print(f"     → tải được {ok}/{hi-lo}")

    # (UT xong bằng PDF dự luật SB 227; IN chuyển sang headless trên Pi — in_pi_load.py)

    json.dump(LOG, open(os.path.join(OUT, "_log_actions.json"), "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for x in LOG if x["ok"])
    print(f"\n>>> XONG: {ok}/{len(LOG)} lượt tải thành công → {OUT}")


if __name__ == "__main__":
    main()

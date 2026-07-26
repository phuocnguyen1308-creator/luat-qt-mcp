#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GIÁM SÁT 12 BANG MỸ — CHẠY TRÊN GITHUB ACTIONS (runner đặt tại Mỹ). Lịch: mùng 1 hằng tháng.

VÌ SAO PHẢI CÓ RIÊNG: adapter usa_state của 12 bang này đọc từ bảng raw_file trên Pi (bản đã
bóc sẵn), nên `giam_sat_qt2.py` chạy qua nó sẽ so bản lưu với chính nó → LUÔN BÁO "KHÔNG ĐỔI"
kể cả khi cổng bang đã sửa luật. Đó là im lặng giả, nguy hơn báo lỗi. Muốn soi được NGUỒN thì
phải gọi từ máy Mỹ — mà chỉ runner GitHub mới ở Mỹ.

BÀI HỌC ĐÃ ĐƯA VÀO THIẾT KẾ
───────────────────────────
1. NGUỒN CỦA TA CÓ HAI LOẠI, KHÔNG ĐƯỢC CANH GIỐNG NHAU:
   • Bang codified (TX, OR, CT, NH, RI, NE, UT, KY, MT): kho lấy từ chương luật đã pháp
     điển hoá → canh chính trang chương đó.
   • Bang lấy từ DỰ LUẬT ĐÃ BAN HÀNH (NJ 266_.PDF, TN SB0073.pdf, CO PDF theo năm): file đó
     ĐÓNG BĂNG VĨNH VIỄN — canh nó thì đời nào cũng "không đổi", vô nghĩa. Với nhóm này phải
     canh TRANG CHƯƠNG PHÁP ĐIỂN tương ứng, vì sửa đổi về sau chỉ hiện ở đó.
     → đây là lỗi dễ mắc nhất khi làm giám sát: canh đúng chỗ mình đã tải, chứ không phải
       đúng chỗ luật thực sự thay đổi.

2. TÍN HIỆU CHÍNH LÀ DANH SÁCH SỐ MỤC, KHÔNG PHẢI md5 TRANG.
   Trang cổng bang có banner phiên họp, ngày cập nhật, token phiên → md5 đổi hằng tháng mà
   luật không đổi. Vụ pdftotext và vụ DILA <LIENS> đều cùng một bài học: SO CÁI MÌNH QUAN TÂM,
   ĐỪNG SO CÁI VỎ. Ở đây cái mình quan tâm = tập số mục (thêm/bớt mục = sửa luật, chắc chắn).
   Độ dài text là tín hiệu phụ, chỉ báo khi lệch ≥ 2%.

3. PHÂN BIỆT "BỊ CHẶN" VỚI "LUẬT ĐỔI" — đây là chỗ dễ báo động giả nhất.
   Lấy hỏng, hoặc lấy được 200 nhưng KHÔNG thấy số mục nào (vỏ SPA / trang chặn trả 200,
   đúng kiểu Indiana), đều ghi 'khong_lay_duoc' và KHÔNG báo động. Chỉ so khi thật sự đọc
   được danh sách mục. "Không soi được" phải nói thẳng là không soi được, tuyệt đối không
   được để nó trông giống "luật bị xoá mục".

CÁCH DÙNG (Actions tự chạy, không cần ai bấm):
   python tools/giam_sat_states.py            # so với mốc chuẩn, khác → exit 1 (job đỏ → GitHub gửi mail)
   python tools/giam_sat_states.py --moc      # ghi lại mốc chuẩn mới (chạy khi đã xác nhận thay đổi)
Mốc chuẩn nằm ở tools/us_state_moc.json — CHỈ LÀ SIÊU DỮ LIỆU (số mục + md5), không phải
dữ liệu luật, nên commit vào repo không phạm nguyên tắc "repo không lưu data".
"""
import urllib.request, ssl, os, re, json, sys, hashlib, time, signal, html

HERE = os.path.dirname(os.path.abspath(__file__))
MOC = os.path.join(HERE, "us_state_moc.json")
BAO_CAO = os.path.join(os.path.dirname(HERE), "state_raw", "_giam_sat.json")
GHI_MOC = "--moc" in sys.argv
CTX = ssl.create_default_context()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
NGUONG_DAI = 0.02        # lệch độ dài dưới 2% coi là banner/ngày tháng, không phải luật

# (mã, tên, [ứng viên (URL, regex số mục)…], ghi chú)
# ⚠ VÌ SAO NHIỀU ỨNG VIÊN CHỨ KHÔNG MỘT URL: thử từ VN cho thấy mỗi cổng chặn một kiểu
#   (403 bot, timeout geo, SSL hỏng, connection refused) và KHÔNG suy ra được cổng nào sẽ
#   mở với IP Mỹ của runner. Thay vì đoán, script thử lần lượt và GHI LẠI ứng viên nào ăn;
#   mốc chuẩn lưu luôn URL đó nên các lần sau đi thẳng. Đây cũng là cách tự lành khi một
#   cổng đổi đường dẫn.
#   Riêng law.justia.com đã loại: trả 403 cho mọi request không phải trình duyệt thật.
BANG = [
 ("US-TX-DPSA", "Texas DPSA — Bus. & Com. Code ch. 541", [
   ("https://statutes.capitol.texas.gov/Docs/BC/htm/BC.541.htm", r"\b541\.(\d{3})\b"),
   ("https://statutes.capitol.texas.gov/SOTWDocs/BC/htm/BC.541.htm", r"\b541\.(\d{3})\b"),
  ], "kho lấy từ PDF dự luật HB4 → canh chương pháp điển"),
 ("US-OR-OCPA", "Oregon OCPA — ORS 646A.570–589", [
   ("https://www.oregonlegislature.gov/bills_laws/ors/ors646A.html", r"\b646A\.(5[78]\d)\b"),
  ], "kho lấy từ HTML xuất Word của chương này"),
 ("US-CT-CTDPA", "Connecticut CTDPA — CGS ch. 743jj", [
   ("https://www.cga.ct.gov/current/pub/chap_743jj.htm", r"\b42-(5\d{2}[a-z]{0,2})\b"),
   ("http://www.cga.ct.gov/current/pub/chap_743jj.htm", r"\b42-(5\d{2}[a-z]{0,2})\b"),
   ("https://codes.findlaw.com/ct/title-42-sales-and-notices/", r"\b42-(5\d{2}[a-z]{0,2})\b"),
  ], "cùng trang kho đã tải"),
 ("US-NH-DPA", "New Hampshire — RSA 507-H", [
   ("https://www.gencourt.state.nh.us/rsa/html/LII/507-H/507-H-mrg.htm", r"\b507-H:(\d+)\b"),
   ("https://www.gencourt.state.nh.us/rsa/html/NHTOC/NHTOC-LII-507-H.htm", r"\b507-H:(\d+)\b"),
  ], "cùng trang kho đã tải"),
 ("US-RI-DTPPA", "Rhode Island DTPPA — RIGL 6-48.1", [
   ("http://webserver.rilegislature.gov/Statutes/TITLE6/6-48.1/INDEX.htm", r"\b6-48\.1-(\d+)\b"),
   ("https://webserver.rilegislature.gov/Statutes/TITLE6/6-48.1/INDEX.htm", r"\b6-48\.1-(\d+)\b"),
  ], "kho lấy từng mục; canh trang mục lục"),
 ("US-NE-DPA", "Nebraska DPA — Neb. Rev. Stat. ch. 87 art. 11", [
   ("https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=87", r"\b87-(11\d{2})\b"),
  ], "kho lấy bản in &print=true của từng mục"),
 ("US-UT-UCPA", "Utah UCPA — Utah Code 13-61", [
   ("https://le.utah.gov/xcode/Title13/Chapter61/13-61.html", r"\b13-61-([0-9]{3})\b"),
   ("https://le.utah.gov/xcode/Title13/Chapter61/13-61.html?print=on", r"\b13-61-([0-9]{3})\b"),
  ], "kho lấy từ PDF SB 227 (ĐÓNG BĂNG) → canh chương pháp điển"),
 ("US-KY-CDPA", "Kentucky CDPA — KRS 367.3611–3629", [
   ("https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=39092", r"\b367\.(36\d{2})\b"),
  ], "kho lấy từng mục PDF; canh mục lục chương — ⚠ mục lục chỉ in DẢI '367.3611 … 367.3629' "
     "nên chỉ bắt được 2 số: bắt được thêm/bớt ở HAI ĐẦU dải, không thấy chèn mục ở giữa"),
 ("US-MT-CDPA", "Montana CDPA — MCA 30-14-28", [
   ("https://archive.legmt.gov/bills/mca/title_0300/chapter_0140/part_0280/sections_index.html",
    r"\b30-14-28(\d{2})\b"),
   ("https://leg.mt.gov/bills/mca/title_0300/chapter_0140/part_0280/sections_index.html",
    r"\b30-14-28(\d{2})\b"),
   ("https://codes.findlaw.com/mt/title-30-trade-and-commerce/", r"\b30-14-28(\d{2})\b"),
  ], "kho lấy từng mục; canh mục lục phần 28"),
 ("US-NJ-DPA", "New Jersey DPA — NJSA 56:8-166.4 et seq.", [
   ("https://law.njstate.gov/", r"56:8-166\.(\d+)"),
   ("https://njlaw.rutgers.edu/collections/njstats/showsect.php?title=56&chapter=8&section=166.4&actn=getsect",
    r"56:8-166\.(\d+)"),
   ("https://codes.findlaw.com/nj/title-56-trade-names-marks-and-unfair-trade-practices/",
    r"56:8-166\.(\d+)"),
   ("http://njlaw.rutgers.edu/collections/njstats/showsect.php?title=56&chapter=8&section=166.4&actn=getsect",
    r"56:8-166\.(\d+)"),
  ], "kho lấy từ PDF P.L.2023 c.266 (ĐÓNG BĂNG) → cần bản pháp điển mới thấy sửa đổi"),
 ("US-TN-TIPA", "Tennessee TIPA — TCA 47-18-32", [
   ("https://codes.findlaw.com/tn/title-47-commercial-instruments-and-transactions/",
    r"\b47-18-32(\d{2})\b"),
   ("https://www.lexisnexis.com/hottopics/tncode/", r"\b47-18-32(\d{2})\b"),
   ("https://www.capitol.tn.gov/Bills/113/Bill/SB0073.pdf", r"\b47-18-32(\d{2})\b"),
  ], "kho lấy từ PDF SB0073 (ĐÓNG BĂNG) → cần bản pháp điển mới thấy sửa đổi"),
 ("US-CO-CPA", "Colorado CPA — CRS title 6 (part 13)", [
   ("https://leg.colorado.gov/agencies/office-legislative-legal-services/colorado-revised-statutes",
    r"crs(20\d{2})-title"),
   ("https://codes.findlaw.com/co/title-6-consumer-and-commercial-affairs/", r"\b6-1-13(\d{2})\b"),
   ("https://leg.colorado.gov/sites/default/files/images/olls/crs2024-title-06.pdf", r"\b6-1-13(\d{2})\b"),
  ], "kho lấy PDF CRS THEO NĂM → canh trang mục lục để biết có bản năm mới"),
]


HAN_GIO = 60          # trần thời gian cho MỖI bang


class QuaGio(Exception):
    pass


def tai(url, timeout=25):
    """⚠ timeout của urlopen chỉ tính cho MỖI thao tác socket, không phải cả lượt tải.

    Đo thật khi thử 12 cổng bang: có cổng nhận kết nối rồi nhỏ giọt vài byte một, mỗi lần
    đọc đều dưới timeout nên urlopen KHÔNG BAO GIỜ bỏ cuộc — script chạy quá 12 phút mà
    chưa qua hết danh sách. Trên Actions kiểu treo này ăn hết quota job.
    Vì vậy phải có TRẦN THỜI GIAN TỔNG bằng SIGALRM, không dựa vào timeout của socket."""
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
         "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(QuaGio()))
    signal.alarm(HAN_GIO)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                    timeout=timeout, context=CTX) as r:
            return r.read(), r.headers.get("Content-Type", "")
    finally:
        signal.alarm(0)


def giai_ma(data: bytes, ct: str = "") -> str:
    """⚠ KHÔNG được decode('utf-8') bừa. Vòng chạy đầu trên Actions: Texas trả về 250 KB,
    Colorado 58 KB — trang về ĐỦ mà ra 0 mục. Đó không phải cổng chặn, mà là mình đọc sai
    bảng mã: nhiều cổng bang xuất HTML theo UTF-16 (có BOM) hoặc windows-1252. Decode UTF-16
    bằng utf-8 thì mỗi chữ số bị chèn NUL ở giữa ('5\x004\x001') → regex số mục không bao giờ
    khớp, mà nhìn số byte lại tưởng lấy được.
    Dấu hiệu nhận ra: byte lớn + 0 mục + text đầy ký tự thay thế."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    m = re.search(r"charset=([\w-]+)", ct or "", re.I)
    thu = [m.group(1)] if m else []
    thu += ["utf-8", "windows-1252", "latin-1"]
    for enc in thu:
        try:
            t = data.decode(enc)
            if t.count("\x00") < len(t) // 20:      # còn nhiều NUL là đoán sai bảng mã
                return t
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def van_ban_thuan(data: bytes, ct: str = "") -> str:
    t = giai_ma(data, ct)
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)                             # &nbsp; &sect; … thành ký tự thật
    return re.sub(r"[\s\u00a0]+", " ", t).strip()


def chan_doan(url, data, txt):
    """In mẫu để LẦN SAU KHỎI ĐOÁN. Cổng bang mỗi nơi một kiểu; thay vì ngồi suy luận
    regex sai ở đâu, để runner ở Mỹ tự kể lại nó thấy gì."""
    so = sorted(set(re.findall(r"\b\d{1,3}[-.:]\d{1,4}[A-Za-z]?\b", txt)))
    print(f"      ↳ chẩn đoán {url[:60]}")
    print(f"        {len(data):,}B · {len(txt):,} ký tự sau khi bóc thẻ")
    print(f"        đầu trang: {txt[:180]!r}")
    print(f"        số dạng điều luật thấy được ({len(so)}): {', '.join(so[:25])}")


def do_mot_bang(ma, ten, ung_vien, ghi_chu, url_uu_tien=None):
    """Thử lần lượt các ứng viên, lấy cái ĐẦU TIÊN ra được số mục.

    ⚠ Thứ tự ưu tiên: URL đã ăn ở lần trước (ghi trong mốc chuẩn) được thử trước, để lần
    chạy định kỳ không phụ thuộc thứ tự khai báo — nếu không, thay đổi thứ tự trong bảng
    sẽ làm số mục nhảy và báo động giả."""
    ds = list(ung_vien)
    if url_uu_tien:
        ds.sort(key=lambda x: x[0] != url_uu_tien)
    loi = []
    for url, re_muc in ds:
        try:
            data, ct = tai(url)
        except QuaGio:
            loi.append(f"{url[:48]}… quá {HAN_GIO}s"); continue
        except urllib.error.HTTPError as e:
            loi.append(f"{url[:48]}… HTTP {e.code}"); continue      # mã lỗi nói rõ hơn tên lớp
        except Exception as e:
            loi.append(f"{url[:48]}… {type(e).__name__}: {str(e)[:40]}"); continue
        txt = van_ban_thuan(data, ct)
        muc = sorted(set(re.findall(re_muc, txt)), key=lambda s: (len(s), s))
        if not muc:
            # 200 nhưng không có số mục → vỏ SPA / trang chặn / sai regex. KHÔNG phải "luật bị xoá".
            loi.append(f"{url[:48]}… lấy được {len(data)}B nhưng 0 mục")
            chan_doan(url, data, txt); continue
        return {"ma": ma, "tt": "ok", "n_muc": len(muc), "muc": muc,
                "vt_muc": hashlib.md5(",".join(muc).encode()).hexdigest()[:16],
                "n_ky_tu": len(txt), "url": url}
    return {"ma": ma, "tt": "khong_lay_duoc", "loi": " | ".join(loi)}


def main():
    moc = json.load(open(MOC, encoding="utf-8")) if os.path.exists(MOC) else {}
    kq, doi, hong = {}, [], []
    print(f"Giám sát {len(BANG)} bang Mỹ (nguồn raw_file, không canh được từ Pi)\n" + "─" * 72)

    for ma, ten, ung_vien, ghi_chu in BANG:
        r = do_mot_bang(ma, ten, ung_vien, ghi_chu, (moc.get(ma) or {}).get("url"))
        r["ten"], r["ghi_chu"] = ten, ghi_chu
        kq[ma] = r
        if r["tt"] != "ok":
            print(f"  ~ {ma:13} không soi được: {r['loi'][:110]}")
            hong.append(ma); time.sleep(0.3); continue

        cu = moc.get(ma)
        if not cu:
            print(f"  · {ma:13} {r['n_muc']:>3} mục — mốc mới ({r['url'][:60]})")
            time.sleep(0.3); continue

        khac = []
        if cu.get("vt_muc") != r["vt_muc"]:
            them = sorted(set(r["muc"]) - set(cu.get("muc", [])))
            mat = sorted(set(cu.get("muc", [])) - set(r["muc"]))
            khac.append(f"danh sách mục đổi ({cu.get('n_muc')} → {r['n_muc']})"
                        + (f" · thêm {them}" if them else "") + (f" · mất {mat}" if mat else ""))
        else:
            ty = abs(r["n_ky_tu"] - cu.get("n_ky_tu", 0)) / max(cu.get("n_ky_tu", 1), 1)
            if ty >= NGUONG_DAI:
                khac.append(f"số mục y nguyên nhưng độ dài lệch {ty*100:.1f}% "
                            f"({cu.get('n_ky_tu')} → {r['n_ky_tu']} ký tự) — nghi sửa nội dung mục")
            elif ty:
                print(f"    · {ma}: lệch {ty*100:.2f}% — banner/ngày tháng, bỏ qua")
        if khac:
            doi.append((ma, ten, khac))
            print(f"  ⚠ {ma:13} " + " · ".join(khac))
        else:
            print(f"  ✅ {ma:13} {r['n_muc']:>3} mục, không đổi")
        time.sleep(0.3)

    os.makedirs(os.path.dirname(BAO_CAO), exist_ok=True)
    json.dump(kq, open(BAO_CAO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if GHI_MOC:
        json.dump({k: {x: v[x] for x in ("n_muc", "muc", "vt_muc", "n_ky_tu", "url") if x in v}
                   for k, v in kq.items() if v["tt"] == "ok"},
                  open(MOC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n>>> Đã ghi mốc chuẩn: {MOC}  ({sum(1 for v in kq.values() if v['tt']=='ok')} bang)")
        return

    print("\n" + "=" * 72)
    print(f"{len(kq)-len(hong)}/{len(BANG)} bang soi được · {len(doi)} thay đổi · {len(hong)} không lấy được")
    if doi:
        print("\n⚠ CẦN XỬ LÝ — tải lại rồi nạp vào Pi:")
        for ma, ten, k in doi:
            print(f"   {ma}: {ten}\n      " + "\n      ".join(k))
        print("\n   1) sửa tools/fetch_states.py cho bang đó → Actions tải lại → artifact")
        print("   2) trên Pi: python3 raw_to_pi.py && python3 load_luatqt.py us_statesN")
        print("   3) xác nhận xong thì chạy lại script này với --moc để chốt mốc mới")
        sys.exit(1)          # job đỏ → GitHub gửi mail cho chủ repo
    print("✅ Không bang nào đổi.")


if __name__ == "__main__":
    main()

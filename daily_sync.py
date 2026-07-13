import requests, csv, json, re, hashlib, io, shutil
from pathlib import Path
from datetime import date

# ═══════════════════════════════════════════
# CONFIG — แก้ 2 ค่านี้ก่อนใช้งาน
# ═══════════════════════════════════════════
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTniKKZNLA6S9eTblLIq8qTRBoceNStxkZnZhV5dYTFCYuAFn-0jQdlc9yebSyPbjA7d2DEdk3Zlo88/pub?output=csv"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1516309490990055494/YXugpTM77VQo0uLzXx21Zs6oO48bueXsIBi49_j2JO7d1wGqb3xnl6R5h1jaTuFelp1_"
DISCORD_USER_ID = "277090153791750146"
# ═══════════════════════════════════════════

HTML_FILE       = Path("index.html.html")
LAST_HASH_FILE  = Path("last_hash.txt")
LAST_RUN_FILE   = Path("last_run_date.txt")
BACKUP_DIR      = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

# คอลัมน์ตาม index (0-based) ตามโครงสร้าง CSV ที่ใช้อยู่
COL_MAP = {
    "brand": 0, "series": 1, "model": 2, "spec": 3, "year": 4,
    "timeSpy": 5, "tsGfx": 6, "tsExtreme": 7, "tsExtremeGfx": 8,
    "fsExt": 9, "fsExtGfx": 10, "fsExtPhys": 11,
    "fsUltra": 12, "fsUltraGfx": 13, "fsUltraPhys": 14,
    "steelNomad": 15,
    "cbR23S": 17, "cbR23M": 18, "cbR24S": 19, "cbR24M": 20,
    "battery": 22, "standby": 23,
    "pcmark": 25, "pcEss": 26, "pcProd": 27, "pcCC": 28, "pcGaming": 29,
    "cpuIdle": 31, "cpuLoad": 32, "gpuIdle": 33, "gpuLoad": 34,
}
NUMERIC_FIELDS = [k for k in COL_MAP if k not in ("brand", "series", "model", "spec", "year")]


def notify_discord(message, is_error=False):
    if not DISCORD_WEBHOOK or "PASTE_YOUR" in DISCORD_WEBHOOK:
        print("⚠️  ยังไม่ตั้งค่า DISCORD_WEBHOOK — ข้ามการแจ้งเตือน")
        return
    try:
        prefix = "🔴 **ERROR**" if is_error else "🔔 **Benchmark Update**"
        payload = {"content": f"<@{DISCORD_USER_ID}> {prefix}\n{message}"}
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    except Exception as e:
        print(f"  ⚠️  ส่ง Discord ไม่ได้: {e}")


def parse_num(v):
    if v is None:
        return None
    v = v.strip()
    if v in ("", "-", "—"):
        return None
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return None


def already_ran_today():
    if not LAST_RUN_FILE.exists():
        return False
    return LAST_RUN_FILE.read_text().strip() == str(date.today())


def mark_ran_today():
    LAST_RUN_FILE.write_text(str(date.today()))


def fetch_csv():
    resp = requests.get(CSV_URL, timeout=20)
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig")


def has_changed(csv_text):
    new_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    old_hash = LAST_HASH_FILE.read_text().strip() if LAST_HASH_FILE.exists() else ""
    if new_hash == old_hash:
        return False, new_hash
    return True, new_hash


def parse_csv_to_entries(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    entries = []
    last_brand, last_series = "", ""

    for row in rows[3:]:  # ข้าม 3 แถว header
        if len(row) < 6:
            continue
        model = row[COL_MAP["model"]].strip() if len(row) > COL_MAP["model"] else ""
        if not model:
            continue

        brand = row[COL_MAP["brand"]].strip() or last_brand
        series = row[COL_MAP["series"]].strip() or last_series
        last_brand, last_series = brand, series

        entry = {"brand": brand, "series": series, "model": model}

        spec_idx = COL_MAP["spec"]
        entry["spec"] = row[spec_idx].strip() if len(row) > spec_idx else ""

        year_idx = COL_MAP["year"]
        year_val = row[year_idx].strip() if len(row) > year_idx else ""
        entry["year"] = int(year_val) if year_val.isdigit() else None

        for field in NUMERIC_FIELDS:
            idx = COL_MAP[field]
            entry[field] = parse_num(row[idx]) if len(row) > idx else None

        entries.append(entry)

    return entries


def diff_entries(old_data, new_data):
    """คืนรายการ model ที่ถูกเพิ่มใหม่ หรือมีค่าเปลี่ยนไป"""
    old_by_model = {d["model"]: d for d in old_data}
    changed, added = [], []

    def normalize(entry):
        normalized = {}
        for key, value in entry.items():
            if key in ("brand", "series", "model", "spec"):
                # string field
                if value is None:
                    normalized[key] = None
                else:
                    normalized[key] = value.strip().lower()
            else:
                # numeric field: including year and all benchmark fields
                if value is None:
                    normalized[key] = None
                else:
                    # Round to 2 decimal places
                    normalized[key] = round(float(value), 2)
        return normalized

    for entry in new_data:
        model = entry["model"]
        if model not in old_by_model:
            added.append(model)
        else:
            old_entry = old_by_model[model]
            if normalize(old_entry) != normalize(entry):
                changed.append(model)

    return added, changed


def update_html(new_data):
    content = HTML_FILE.read_text(encoding="utf-8")

    start = content.find("const D=[")
    if start == -1:
        raise ValueError("หา 'const D=[' ใน HTML ไม่เจอ")

    depth, pos, end = 0, start + len("const D="), None
    for i, c in enumerate(content[pos:], pos):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise ValueError("หา closing bracket ของ data array ไม่เจอ")

    new_json = json.dumps(new_data, ensure_ascii=False, indent=2)
    new_html = content[:start] + "const D=" + new_json + ";" + content[end + 1:]

    # Validate ก่อนเขียนจริง
    re_check_start = new_html.find("const D=[")
    re_depth, re_pos, re_end = 0, re_check_start + len("const D="), None
    for i, c in enumerate(new_html[re_pos:], re_pos):
        if c == "[":
            re_depth += 1
        elif c == "]":
            re_depth -= 1
            if re_depth == 0:
                re_end = i + 1
                break
    test_data = json.loads(new_html[re_check_start + len("const D="):re_end])
    if len(test_data) == 0:
        raise ValueError("Validate ล้มเหลว: data array ว่างเปล่า")
    if len(new_html) < len(content) * 0.5:
        raise ValueError("Validate ล้มเหลว: ไฟล์ใหม่สั้นกว่าเดิมเกิน 50%")

    # Backup ก่อนเขียนทับ
    backup_path = BACKUP_DIR / f"index_{date.today()}.html.bak"
    shutil.copy(HTML_FILE, backup_path)

    HTML_FILE.write_text(new_html, encoding="utf-8")
    return len(test_data)


def get_current_data():
    content = HTML_FILE.read_text(encoding="utf-8")
    start = content.find("const D=[")
    depth, pos, end = 0, start + len("const D="), None
    for i, c in enumerate(content[pos:], pos):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(content[start + len("const D="):end])


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    print("=" * 50)
    print("📊 NOTEBOOKSPEC DAILY SYNC")
    print("=" * 50)

    if already_ran_today():
        print(f"✅ รันไปแล้ววันนี้ ({date.today()}) — ข้าม")
        return

    print("📥 กำลังดึง CSV จาก Google Sheets...")
    try:
        csv_text = fetch_csv()
    except Exception as e:
        print(f"❌ ดึง CSV ไม่ได้: {e}")
        notify_discord(f"ดึง CSV จาก Google Sheets ไม่ได้\n```{e}```", is_error=True)
        return

    changed, new_hash = has_changed(csv_text)
    if not changed:
        print("ℹ️  ข้อมูลใน CSV ไม่เปลี่ยนจากรอบก่อน — ไม่ต้องอัปเดต")
        mark_ran_today()
        return

    print("🔍 พบการเปลี่ยนแปลงใน CSV — กำลังประมวลผล...")

    try:
        new_data = parse_csv_to_entries(csv_text)
    except Exception as e:
        print(f"❌ Parse CSV ไม่ได้: {e}")
        notify_discord(f"Parse CSV ล้มเหลว\n```{e}```", is_error=True)
        return

    if not HTML_FILE.exists():
        print(f"❌ ไม่เจอไฟล์ {HTML_FILE}")
        notify_discord(f"ไม่เจอไฟล์ {HTML_FILE} ในโฟลเดอร์นี้", is_error=True)
        return

    old_data = get_current_data()
    added, modified = diff_entries(old_data, new_data)

    try:
        total = update_html(new_data)
    except Exception as e:
        print(f"❌ อัปเดต HTML ไม่ได้: {e}")
        notify_discord(f"อัปเดต HTML ล้มเหลว ไฟล์ปลอดภัย ไม่ถูกเขียนทับ\n```{e}```", is_error=True)
        return

    LAST_HASH_FILE.write_text(new_hash)
    mark_ran_today()

    print(f"✅ อัปเดตสำเร็จ — รวม {total} laptops")
    print(f"   เพิ่มใหม่: {len(added)} | แก้ไข: {len(modified)}")

    # สร้างข้อความแจ้งเตือน
    lines = [f"📂 รวมข้อมูลทั้งหมด: **{total} laptops**"]
    if added:
        lines.append(f"\n➕ เพิ่มใหม่ ({len(added)}):")
        lines += [f"   • {m}" for m in added[:10]]
    notify_discord("\n".join(lines))


if __name__ == "__main__":
    main()
import ollama, base64, json, shutil, re
from pathlib import Path

# ── Config ──────────────────────────────────────────────
RESULTS_DIR = Path("new_results")
DONE_DIR    = Path("done_results")
DATA_FILE   = Path("data.json")
MODEL       = "llama3.2-vision"  # เปลี่ยนเป็น "llava" ถ้าไม่มี llama3.2-vision
# ────────────────────────────────────────────────────────

DONE_DIR.mkdir(exist_ok=True)

PROMPT = """อ่านค่าจาก screenshot benchmark นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick

fields ที่ต้องดึง:
- 3DMark         → time_spy, fire_strike
- PCMark 10      → pcmark10
- Cinebench R23  → cb_r23_single, cb_r23_multi
- Cinebench R24  → cb_r24_single, cb_r24_multi
- Furmark 2      → gpu_temp_max, cpu_temp_max
- BattMon        → battery_hours

ถ้าหาค่าไม่เจอในรูปนี้ให้ใส่ null
ตัวอย่าง output: {"time_spy": 12345, "fire_strike": null, "cb_r23_multi": 23000}"""


def read_image_b64(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_scores(image_path):
    img_b64 = read_image_b64(image_path)
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": PROMPT,
                "images": [img_b64]
            }]
        )
        raw = response['message']['content'].strip()
        # ล้าง markdown backtick ถ้ามี
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ⚠️  อ่าน JSON ไม่ได้จาก {image_path.name} — ข้ามไฟล์นี้")
        return {}
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {}


# ── Main ─────────────────────────────────────────────────
images = list(RESULTS_DIR.glob("*.png")) + list(RESULTS_DIR.glob("*.jpg"))

if not images:
    print("❌ ไม่มีรูปใน new_results/")
    print("   วางรูป screenshot ผลเทสลงในโฟลเดอร์ new_results/ ก่อนนะครับ")
    exit()

print(f"พบรูป {len(images)} ใบ\n")

laptop_name = input("ชื่อ laptop (เช่น ASUS ROG Strix G16 2025): ").strip()
gpu         = input("GPU (เช่น RTX 4070): ").strip()
cpu         = input("CPU (เช่น i9-14900HX): ").strip()

combined = {}
for img in images:
    print(f"🔍 กำลังอ่าน {img.name}...")
    scores = extract_scores(img)
    found = {k: v for k, v in scores.items() if v is not None}
    if found:
        print(f"   ✅ อ่านได้: {found}")
        combined.update(found)
    shutil.move(str(img), DONE_DIR / img.name)

if not combined:
    print("\n⚠️  อ่านค่าไม่ได้เลย ลองเปลี่ยน MODEL เป็น 'llava' ใน config")
    exit()

new_entry = {"model": laptop_name, "gpu": gpu, "cpu": cpu, **combined}
print("\n📊 ผลที่อ่านได้ทั้งหมด:")
print(json.dumps(new_entry, indent=2, ensure_ascii=False))

confirm = input("\nบันทึกลง data.json? (y/n): ").strip().lower()

if confirm == "y":
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        data.append(new_entry)
        DATA_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print("✅ อัปเดต data.json แล้ว")
        print("➡️  refresh browser เพื่อดูผลใน laptop-benchmark_8.html")
    except FileNotFoundError:
        print("❌ ไม่เจอ data.json — ตรวจสอบว่ารัน script จาก folder ที่ถูกต้อง")
else:
    print("ยกเลิก — รูปถูกย้ายไป done_results/ แล้ว")
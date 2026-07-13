import ollama
import base64
import json
import shutil
import re
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Config ──────────────────────────────────────────────────────────
RESULTS_DIR = Path("new_results")
DONE_DIR    = RESULTS_DIR / "done"
DATA_FILE   = Path("data.json")
HTML_FILE   = Path("index.html.html")
MODEL       = "minicpm-v"

PROMPTS = {
    "3DMark": """อ่านผล 3DMark จาก screenshot นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick
fields:
- timeSpy: คะแนน Score หลักของ Time Spy
- tsGfx: Graphic Score ของ Time Spy
- tsExtreme: คะแนน Score หลักของ Time Spy Extreme
- tsExtremeGfx: Graphic Score ของ Time Spy Extreme
- fsExt: คะแนน Score หลักของ Fire Strike Extreme
- fsExtGfx: Graphic Score ของ Fire Strike Extreme
- fsExtPhys: Physics Score ของ Fire Strike Extreme
- fsUltra: คะแนน Score หลักของ Fire Strike Ultra
- fsUltraGfx: Graphic Score ของ Fire Strike Ultra
- fsUltraPhys: Physics Score ของ Fire Strike Ultra
- steelNomad: คะแนน Score หลักของ Steel Nomad
ถ้าไม่มี test นั้นในรูปให้ใส่ null ตอบแค่ JSON เท่านั้น""",

    "PCMark": """อ่านผล PCMark 10 จาก screenshot นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick
อ่านเฉพาะคะแนนสีส้มเท่านั้น ห้ามอ่านคะแนนอื่น
fields:
- pcmark: คะแนนหลัก (มุมขวาบน มีเครื่องหมายถูก)
- pcEss: คะแนน Essentials
- pcProd: คะแนน Productivity
- pcCC: คะแนน Digital Content Creation
- pcGaming: คะแนน Gaming
ถ้าหาไม่เจอใส่ null ตอบแค่ JSON เท่านั้นห้าม nest object ตอบเป็น flat JSON เท่านั้น เช่น {"pcmark": 11101, "pcEss": 9277, "pcProd": 18791}""",

    "Cinebench": """อ่านผล Cinebench จาก screenshot นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick
fields:
- cbR23S: Single Core R23
- cbR23M: Multi Core R23
- cbR24S: Single Core R24
- cbR24M: Multi Core R24
ถ้าไม่มีใน screenshot ใส่ null ตอบแค่ JSON เท่านั้น""",

    "Battmon": """อ่านผล Battery test จาก screenshot นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick
อ่านเฉพาะค่า Total Time เท่านั้น
fields:
- battery: Total Time ของการทดสอบ Social/ดู YouTube (หน่วยชั่วโมง ทศนิยม เช่น 7.46)
- standby: Total Time ของ Standby mode (หน่วยชั่วโมง ทศนิยม เช่น 16.38)
ถ้าหาไม่เจอใส่ null ตอบแค่ JSON เท่านั้น""",

    "Furmark Temp": """อ่านอุณหภูมิจาก HWMonitor screenshot นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick
อ่านเฉพาะค่า Max เสมอ ห้ามอ่านค่า Value หรือ Min
fields:
- cpuIdle: ค่า Max อุณหภูมิ CPU ในแถวที่มีคำว่า idle cpu
- gpuIdle: ค่า Max อุณหภูมิ GPU ในแถวที่มีคำว่า idle gpu
- cpuLoad: ค่า Max อุณหภูมิ CPU ในแถวที่มีคำว่า load cpu หรือ full load cpu
- gpuLoad: ค่า Max อุณหภูมิ GPU ในแถวที่มีคำว่า load gpu หรือ full load gpu
ถ้าหาไม่เจอใส่ null ตอบแค่ JSON เท่านั้น"""
}

# ──────────────────────────────────────────────────────────────────

def read_image_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Error reading image {path}: {e}")
        return None

def extract_scores(image_path, program_name=""):
    img_b64 = read_image_b64(image_path)
    if not img_b64:
        return {}

    # เลือก prompt โดยหา key ใน PROMPTS ที่ตรงกับ program_name (case-insensitive partial match)
    selected_prompt = None
    for key in PROMPTS:
        if key.lower() in program_name.lower():
            selected_prompt = PROMPTS[key]
            break

    if not selected_prompt:
        selected_prompt = (
            "อ่านค่าจาก screenshot benchmark นี้ ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น ห้ามมี markdown backtick "
            "fields: time_spy, fire_strike, pcmark10, cb_r23_single, cb_r23_multi, "
            "cb_r24_single, cb_r24_multi, gpu_temp_max, cpu_temp_max, battery_hours "
            "ถ้าหาค่าไม่เจอใส่ null"
        )

    for attempt in range(2):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[{
                    "role": "user",
                    "content": selected_prompt,
                    "images": [img_b64]
                }]
            )
            raw = response['message']['content'].strip()
            if not raw:
                raise ValueError("Empty response")

            # ล้าง markdown backtick
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            if attempt == 1:
                print(f"❌ อ่านไม่ได้ (Retry failed): {image_path.name}")

    return {}

def update_data_json(new_entry):
    try:
        if not DATA_FILE.exists():
            data = []
        else:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

        data.append(new_entry)
        DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception as e:
        print(f"❌ Error updating data.json: {e}")
        return None

def update_html_content(data):
    try:
        if not HTML_FILE.exists():
            print(f"⚠️ HTML file not found at {HTML_FILE}. Skipping HTML update.")
            return False

        content = HTML_FILE.read_text(encoding="utf-8")

        # รายการ patterns ที่ใช้ค้นหาข้อมูลใน HTML
        patterns = [
            r'(const\s+D\s*=\s*)\[.*?\](;)',
        ]

        # Sanitize data: json.dumps แล้ว escape backslash
        sanitized_data = json.dumps(data, ensure_ascii=False).replace('\\', '\\\\')

        current_content = content
        total_replacements = 0
        for pattern in patterns:
            replacement = f'\\1{sanitized_data};'
            current_content, n = re.subn(pattern, replacement, current_content, flags=re.DOTALL)
            total_replacements += n

        # Validation:
        # 1. ต้องมีการแทนที่ข้อมูลจริง
        # 2. เช็คความยาว result HTML (ต้องไม่น้อยกว่า 50% ของไฟล์เดิม เพื่อป้องกันไฟล์หาย/พัง)
        if total_replacements == 0 or len(current_content) < (len(content) * 0.5):
            print(f"❌ HTML Validation failed: replacements={total_replacements}, length={len(current_content)} (original={len(content)})")
            return False

        # Backup ไฟล์เดิมไว้ที่ index.html.html.bak ก่อน write
        backup_path = Path(str(HTML_FILE) + ".bak")
        shutil.copy(HTML_FILE, backup_path)

        HTML_FILE.write_text(current_content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"❌ Error updating HTML: {e}")
        return False

class BenchmarkHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in [".png", ".jpg"]:
            return

        time.sleep(1) # ให้ไฟล์ copy เสร็จ

        # โครงสร้าง: new_results/{model_name}/{program_name}/image
        model_name = path.parent.parent.name
        program_name = path.parent.name

        # ถ้า path.parent.parent.name คือ "new_results" หรือ "done" → ข้ามไฟล์นั้น
        if model_name in ["new_results", "done"] or path.parent.name == "done":
            return

        print(f"\n📸 พบไฟล์ใหม่: {path.name}")
        print(f"🔍 กำลังอ่านผลจาก {program_name} ของ {model_name}...")

        scores = extract_scores(path, path.parent.name)
        if not scores:
            print("❌ ไม่สามารถอ่านค่าได้")
            return

        print("✅ อ่านค่าได้:")
        print(json.dumps(scores, indent=2))

        try:
            data = []
            if DATA_FILE.exists():
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

            updated_data = None
            # ค้นหาใน data.json ว่ามี model ที่ชื่อตรงกัน (case-insensitive) ไหม
            found_idx = next((i for i, item in enumerate(data)
                             if item.get('model', '').lower() == model_name.lower()), None)

            if found_idx is not None:
                print(f"🎯 พบ {model_name} ในระบบ -> อัปเดตข้อมูลทันที")
                data[found_idx].update({k: v for k, v in scores.items() if v is not None})
                DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                updated_data = data
            else:
                print(f"🆕 ไม่พบ {model_name} ในระบบ -> สร้างรายการใหม่")
                brand = input(f"ระบุ Brand/Specs สำหรับ {model_name}: ").strip()
                entry = {"model": model_name, "brand": brand, **scores}
                updated_data = update_data_json(entry)

            if updated_data:
                if update_html_content(updated_data):
                    print("✅ อัปเดต data.json และ index.html เรียบร้อย")
                else:
                    print("⚠️ อัปเดต data.json แล้ว แต่ HTML ล้มเหลว")

        except Exception as e:
            print(f"❌ Error during laptop selection: {e}")

        # ย้ายรูปไป new_results/done/{ชื่อรุ่น}/{ชื่อโปรแกรม}/
        try:
            target_dir = DONE_DIR / model_name / program_name
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), target_dir / path.name)
            print(f"📁 ย้ายไฟล์ไปที่ {target_dir}")
        except Exception as e:
            print(f"❌ Error moving file: {e}")

def main():
    RESULTS_DIR.mkdir(exist_ok=True)

    event_handler = BenchmarkHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(RESULTS_DIR), recursive=True)
    observer.start()

    print(f"👀 กำลังเฝ้าดูโฟลเดอร์ {RESULTS_DIR}/ ...")
    print("วางรูป .png หรือ .jpg เพื่อเริ่มการอัปเดต (Ctrl+C เพื่อหยุด)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

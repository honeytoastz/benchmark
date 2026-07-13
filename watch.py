import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from update import extract_scores  # import จากไฟล์วิธีที่ 2
import json, shutil
from pathlib import Path

DATA_FILE = Path("data.json")
DONE_DIR  = Path("done_results")

class BenchmarkHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in [".png", ".jpg"]:
            return
        
        time.sleep(1)  # รอให้ไฟล์ copy เสร็จ
        print(f"\n📸 พบไฟล์ใหม่: {path.name}")
        
        try:
            scores = extract_scores(path)
            print("อ่านค่าได้:", scores)
            
            # อัปเดต entry ล่าสุดใน data.json อัตโนมัติ
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            last = data[-1]  # เพิ่มเข้า laptop ล่าสุด
            last.update({k: v for k, v in scores.items() if v is not None})
            DATA_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), 
                encoding="utf-8"
            )
            shutil.move(str(path), DONE_DIR / path.name)
            print(f"✅ อัปเดต {last['model']} แล้ว")
            
        except Exception as e:
            print(f"❌ Error: {e}")

observer = Observer()
observer.schedule(BenchmarkHandler(), path="new_results", recursive=False)
observer.start()
print("👀 กำลัง watch โฟลเดอร์ new_results/ อยู่...")
print("วางรูปผลเทสได้เลย (Ctrl+C เพื่อหยุด)")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
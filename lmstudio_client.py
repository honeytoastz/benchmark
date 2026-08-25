"""
lmstudio_client.py

Helper module สำหรับให้ Claude Code (หรือสคริปต์อื่นๆ บนเครื่อง) เรียกใช้
LM Studio local server ได้ง่ายๆ โดยไม่ต้องเขียน boilerplate ซ้ำทุกครั้ง

รองรับโมเดล reasoning (เช่น Qwen3.5 9B) ที่ส่ง reasoning_content แยกจาก
content จริง — ฟังก์ชันนี้จะดึงเฉพาะคำตอบจริงมาให้ พร้อม fallback
เผื่อ max_tokens ไม่พอ

ใช้งาน:
    from lmstudio_client import ask_local

    answer = ask_local("แต่งชื่อคลิป YouTube 5 แบบจากสเปกนี้: ...")
    print(answer)
"""

import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:1234/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"  # เปลี่ยนได้ถ้าโหลดโมเดลอื่นใน LM Studio


class LocalModelError(Exception):
    """Error ที่เกิดจากการเรียก LM Studio ไม่สำเร็จ หรือได้คำตอบว่างเปล่า"""
    pass


def list_models() -> list[str]:
    """คืนรายชื่อโมเดลที่โหลดอยู่ใน LM Studio ตอนนี้"""
    url = f"{BASE_URL}/models"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return [m["id"] for m in data.get("data", [])]
    except urllib.error.URLError as e:
        raise LocalModelError(
            f"เชื่อมต่อ LM Studio ไม่ได้ — เช็คว่าเปิด server ค้างไว้หรือยัง ({e})"
        )


def ask_local(
    prompt: str,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1200,
    temperature: float = 0.5,
    timeout: int = 180,
) -> str:
    """
    ส่ง prompt ไปหา local model แล้วคืนคำตอบเป็น string

    Args:
        prompt: คำสั่ง/คำถามที่จะส่งไป
        system: system prompt เสริม (ถ้ามี) — ใช้กำหนด tone/บริบท เช่น
                "คุณเป็นนักเขียนคอนเทนต์รีวิวเทคโนโลยีภาษาไทย"
        model: model id ตามที่ขึ้นใน LM Studio (ดูได้จาก list_models())
        max_tokens: จำกัด token รวม — โมเดล reasoning ใช้ token ส่วนหนึ่ง
                    ไปกับการ "คิด" ก่อนตอบ ถ้าคำตอบว่างบ่อยๆ ให้เพิ่มค่านี้
        temperature: ความสุ่มของคำตอบ (0 = นิ่ง, 1 = สร้างสรรค์กว่า)
        timeout: เวลารอสูงสุด (วินาที) — โมเดลใหญ่/reasoning อาจใช้เวลานาน

    Returns:
        เนื้อหาคำตอบจริง (ไม่รวมส่วน reasoning)

    Raises:
        LocalModelError: ถ้าเชื่อมต่อไม่ได้ หรือได้คำตอบว่างเปล่าแม้เพิ่ม
                          max_tokens แล้ว
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        raise LocalModelError(f"ยิง request ไปหา local model ไม่สำเร็จ: {e}")

    choice = data["choices"][0]
    content = choice["message"].get("content", "").strip()
    finish_reason = choice.get("finish_reason", "?")

    if not content:
        # ponytail: reasoning model (qwen3, deepseek-r1) ใช้ token ไปกับ
        # "คิด" ก่อนตอบ — ถ้า content ว่างและ finish_reason=length ให้ลอง
        # ขยาย max_tokens รอบเดียว เพราะสาเหตุเกือบทุกครั้งคือ token หมด
        # ไม่ใช่โมเดลตอบไม่ได้ — ไม่ต้องวน retry หลายรอบ
        if finish_reason == "length":
            retry_payload = {**payload, "max_tokens": max(max_tokens * 3, 4000)}
            req2 = urllib.request.Request(
                f"{BASE_URL}/chat/completions",
                data=json.dumps(retry_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req2, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode())
            except urllib.error.URLError as e:
                raise LocalModelError(f"ยิง request ซ้ำไม่สำเร็จ: {e}")
            choice = data["choices"][0]
            content = choice["message"].get("content", "").strip()
            finish_reason = choice.get("finish_reason", "?")

        if not content:
            raise LocalModelError(
                f"ได้คำตอบว่างเปล่า (finish_reason={finish_reason}) — "
                f"max_tokens ตอนนี้ {max_tokens} ยังไม่พอ โมเดล reasoning "
                f"อาจใช้ token หมดไปกับส่วน 'คิด' ก่อนตอบจริง"
            )

    return content


if __name__ == "__main__":
    # ทดสอบเร็วๆ เวลารันไฟล์นี้ตรงๆ
    print("โมเดลที่พร้อมใช้งาน:", list_models())
    result = ask_local("แนะนำชื่อคลิป YouTube สั้นๆ 1 แบบ สำหรับรีวิวโน้ตบุ๊คเกมมิ่ง")
    print("\nคำตอบ:", result)

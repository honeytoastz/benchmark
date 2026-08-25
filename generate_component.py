"""
generate_component.py

Pattern: Hybrid Split
Qwen (local) ร่างโครง component ใหม่โดยใช้ "placeholder token" แทนข้อมูลจริง
เสมอ — ห้ามใส่ตัวเลข/ชื่อรุ่นจริงเด็ดขาด จากนั้น Claude Code (หรือคุณ)
เป็นคนเติมข้อมูลจริงลงใน placeholder เองทีหลัง แยกขั้นตอนกันชัดเจน
เพื่อป้องกันข้อมูล benchmark เพี้ยน/หลอนจากโมเดล local

ใช้งาน:
    py generate_component.py

หรือ import ไปใช้ใน Claude Code:
    from generate_component import generate_component

    html = generate_component(
        component_type="spec-filter chip",
        description="ปุ่มชิปเลือกรุ่น GPU แบบมี hover state และ active state",
        placeholders=["GPU_NAME", "GPU_SCORE"],
    )
"""

import re
from lmstudio_client import ask_local, LocalModelError

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยเขียนโค้ด HTML/CSS สำหรับเว็บไซต์ NotebookSPEC
กฎเหล็กที่ต้องทำตามทุกครั้งโดยไม่มีข้อยกเว้น:

1. ห้ามใส่ตัวเลข benchmark, สเปกจริง, หรือชื่อรุ่นสินค้าจริงใดๆ ทั้งสิ้น
2. จุดไหนที่ควรมีข้อมูลจริง ให้ใส่ placeholder ในรูปแบบ {{ชื่อ_PLACEHOLDER}}
   แทน เช่น {{GPU_NAME}}, {{SCORE_VALUE}} เท่านั้น
3. ห้ามเดา/สมมติตัวเลขใดๆ แม้จะดูเหมือนเป็นตัวอย่าง — ให้ใช้ placeholder
   เสมอแม้แต่ในตัวอย่าง
4. ตอบกลับเป็นโค้ด HTML/CSS เท่านั้น ไม่ต้องอธิบายเพิ่ม ไม่ต้องมี
   markdown code fence
5. ใช้ design token ต่อไปนี้เสมอ: พื้นหลัง #0c0c0e, สีเน้นทอง #c8a96e,
   ฟอนต์หัวข้อ Space Grotesk, ฟอนต์ตัวเลข JetBrains Mono
"""

# รูปแบบ placeholder ที่ยอมรับได้ — ใช้เช็คตอน validate
PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z_]+\}\}")

# ตัวเลขที่ "ดูเหมือน" ค่า benchmark จริง (4 หลักขึ้นไปติดกัน) — ถ้าเจอ
# นอก placeholder ให้เตือน เพราะอาจเป็นโมเดล hallucinate ตัวเลขขึ้นมาเอง
SUSPICIOUS_NUMBER_PATTERN = re.compile(r"(?<!\{)\b\d{4,}\b(?!\})")


def _validate_output(html: str, required_placeholders: list[str]) -> None:
    """เช็คว่าผลลัพธ์มี placeholder ครบ และไม่มีตัวเลขต้องสงสัยหลุดมา"""
    missing = [p for p in required_placeholders if f"{{{{{p}}}}}" not in html]
    if missing:
        raise ValueError(
            f"Qwen ไม่ได้ใส่ placeholder ที่ต้องการ: {missing} — "
            f"อย่าเอาโค้ดนี้ไปใช้ ให้ลอง generate ใหม่หรือปรับ prompt"
        )

    # ponytail: strip CSS hex colors (#xxxxxx) and rgb(...) calls ออกก่อน
    # scan ตัวเลข — เพราะ design token อย่าง #0c0c0e, #c8a96e มีตัวเลขล้วน
    # 6 หลักที่ดูเหมือน benchmark id แต่จริงๆ เป็นแค่สี ไม่ใช่ข้อมูล
    scan_target = re.sub(r"#[0-9a-fA-F]{3,8}\b", "", html)
    scan_target = re.sub(r"rgba?\([^)]*\)", "", scan_target)
    suspicious = SUSPICIOUS_NUMBER_PATTERN.findall(scan_target)
    if suspicious:
        raise ValueError(
            f"พบตัวเลข 4 หลักขึ้นไปที่ไม่ได้อยู่ใน placeholder: {suspicious} — "
            f"อาจเป็นข้อมูลที่โมเดล hallucinate ขึ้นมาเอง ห้ามใช้โดยไม่ตรวจสอบ"
        )


def generate_component(component_type: str, description: str, placeholders: list[str]) -> str:
    """
    สั่ง Qwen ร่าง component โดยบังคับใช้ placeholder แทนข้อมูลจริง

    Args:
        component_type: ประเภท component เช่น "spec-filter chip", "compare card"
        description: อธิบายลักษณะ/พฤติกรรมที่ต้องการ
        placeholders: รายชื่อ placeholder ที่ต้องมีในผลลัพธ์ เช่น ["GPU_NAME", "SCORE"]

    Returns:
        โค้ด HTML/CSS ที่ผ่านการตรวจสอบเบื้องต้นแล้ว

    Raises:
        LocalModelError: ถ้าเชื่อมต่อ Qwen ไม่ได้
        ValueError: ถ้าผลลัพธ์ไม่มี placeholder ที่ต้องการ หรือมีตัวเลข
                    ต้องสงสัยที่อาจเป็นข้อมูลหลอน
    """
    placeholder_list = ", ".join(f"{{{{{p}}}}}" for p in placeholders)
    prompt = (
        f"สร้าง component ประเภท: {component_type}\n\n"
        f"รายละเอียด: {description}\n\n"
        f"ต้องใช้ placeholder ต่อไปนี้ในโค้ด (ครบทุกตัว): {placeholder_list}"
    )

    html = ask_local(prompt, system=SYSTEM_PROMPT, max_tokens=1500, temperature=0.4)

    _validate_output(html, placeholders)
    return html


def _validate_output(html: str, required_placeholders: list[str]) -> None:
    """เช็คว่าผลลัพธ์มี placeholder ครบ และไม่มีตัวเลขต้องสงสัยหลุดมา"""
    missing = [p for p in required_placeholders if f"{{{{{p}}}}}" not in html]
    if missing:
        raise ValueError(
            f"Qwen ไม่ได้ใส่ placeholder ที่ต้องการ: {missing} — "
            f"อย่าเอาโค้ดนี้ไปใช้ ให้ลอง generate ใหม่หรือปรับ prompt"
        )

    # ponytail: strip CSS hex colors (#xxxxxx) and rgb(...) calls ออกก่อน
    # scan ตัวเลข — เพราะ design token อย่าง #0c0c0e, #c8a96e มีตัวเลขล้วน
    # 6 หลักที่ดูเหมือน benchmark id แต่จริงๆ เป็นแค่สี ไม่ใช่ข้อมูล
    scan_target = re.sub(r"#[0-9a-fA-F]{3,8}\b", "", html)
    scan_target = re.sub(r"rgba?\([^)]*\)", "", scan_target)
    suspicious = SUSPICIOUS_NUMBER_PATTERN.findall(scan_target)
    if suspicious:
        raise ValueError(
            f"พบตัวเลข 4 หลักขึ้นไปที่ไม่ได้อยู่ใน placeholder: {suspicious} — "
            f"อาจเป็นข้อมูลที่โมเดล hallucinate ขึ้นมาเอง ห้ามใช้โดยไม่ตรวจสอบ"
        )


if __name__ == "__main__":
    print("ทดสอบสร้าง component ตัวอย่าง...\n")
    try:
        result = generate_component(
            component_type="spec-filter chip",
            description="ปุ่มชิปทรงกลมสำหรับเลือกรุ่น GPU ในตัวกรอง มี hover glow และ active state สีทอง",
            placeholders=["GPU_NAME", "GPU_SCORE"],
        )
        print("[OK] ผ่านการตรวจสอบ placeholder และไม่มีตัวเลขต้องสงสัย\n")
        print(result)
    except (LocalModelError, ValueError) as e:
        print(f"[FAIL] {e}")

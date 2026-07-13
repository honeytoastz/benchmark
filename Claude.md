# Project: NotebookSPEC Laptop Benchmark Website

## Project Overview
Single HTML file laptop benchmark website for Thai market.
File: laptop-benchmark_8.html
Data source: data.json (exported from Google Sheets CSV via csv_to_json.js)

## Design
- Dark gaming aesthetic
- Thai language UI
- Large text size (used for screen recording / video screenshots)

## Rules
- ทำทีละ step เล็กๆ แล้วรอ confirm ก่อนไปต่อ
- เวลาอัปเดต data ให้แก้เฉพาะ data array เท่านั้น
- อย่าแตะ CSS / layout / JS ถ้าไม่ได้สั่ง
- ห้าม refactor โค้ดที่ไม่เกี่ยวกับ task
- ห้ามเพิ่ม external dependencies ใหม่

## Features (ห้ามลบหรือแก้โดยไม่ได้รับอนุญาต)
- Brand filter buttons
- Sortable columns
- Comparison tool (สูงสุด 6 laptops)
- Sticky full data table
- GPU/CPU benchmark charts
- Thermal & battery data

#
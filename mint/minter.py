import json
import os
import re
import subprocess
from datetime import date

# --- НАСТРОЙКИ ---
LEDGER_FILE = "../ledger.json"
TEMPLATE_FRONT = "../templates/front_10.svg"
TEMPLATE_BACK = "../templates/back_10.svg"
OUTPUT_DIR = "../output_mint"

# Метки в Inkscape
PLACEHOLDERS = ["SLS-ID-01", "SLS-ID-02", "SLS-ID-03", "SLS-ID-04"]
START_SEQUENCE = 10000 

def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return {"meta": {"total_circulation": 0}, "active_units": []}
    with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_ledger(data):
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculate_checksum(number_str):
    digits = [int(d) for d in number_str]
    return str(sum(digits))[-1]

def get_next_sequence_number(ledger, batch_code):
    max_seq = START_SEQUENCE
    # Поддержка разных структур JSON
    notes = ledger.get("active_units", ledger.get("banknotes", []))
    
    for note in notes:
        note_id = note.get("id", "")
        match = re.search(f"SLS-{batch_code}(\\d{{5}})(\\d)", note_id)
        if match:
            current_seq = int(match.group(1))
            if current_seq > max_seq:
                max_seq = current_seq
    return max_seq + 1

def export_to_png(svg_path, png_path):
    """
    Адаптировано для Linux Bazzite (Flatpak).
    """
    print(f"   ⏳ Экспорт PNG (600 DPI)...")

    abs_svg = os.path.abspath(svg_path)
    abs_png = os.path.abspath(png_path)

    # Команда для запуска Inkscape через Flatpak
    cmd = [
        "flatpak", "run", 
        "--command=inkscape", 
        "org.inkscape.Inkscape",
        f"--export-filename={abs_png}",
        "--export-dpi=600",
        "--export-type=png",
        abs_svg
    ]

    try:
        # Запускаем процесс
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            print(f"🔴 Ошибка Flatpak: {result.stderr}")
            # План Б: пробуем обычный inkscape (если установлен не через flatpak)
            print("   Пробую обычную команду 'inkscape'...")
            subprocess.run([
                "inkscape", 
                f"--export-filename={abs_png}", 
                "--export-dpi=600", 
                "--export-type=png", 
                abs_svg
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    except FileNotFoundError:
        print("🔴 Inkscape не найден ни как Flatpak, ни как команда.")
        return False
    except Exception as e:
        print(f"🔴 Сбой экспорта: {e}")
        return False

def mint_sheets():
    ledger = load_ledger()
    
    print("--- 🖨 МОНЕТНЫЙ ДВОР (Sheet Mode) ---")
    batch_code = input("Код партии (например, AA): ").upper().strip()
    try:
        sheets_qty = int(input("Сколько ЛИСТОВ печатаем? (1 лист = 4 купюры): "))
    except ValueError:
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Читаем шаблоны
    with open(TEMPLATE_FRONT, 'r', encoding='utf-8') as f:
        front_template = f.read()
    with open(TEMPLATE_BACK, 'r', encoding='utf-8') as f:
        back_template = f.read()

    next_seq = get_next_sequence_number(ledger, batch_code)
    print(f"⚙️  Начинаем нумерацию с: {next_seq}")

    for sheet_num in range(sheets_qty):
        current_front_svg = front_template
        current_back_svg = back_template
        sheet_ids = []
        
        # Генерируем 4 номера для листа
        for i in range(4):
            current_seq = next_seq + i
            seq_str = str(current_seq)
            checksum = calculate_checksum(seq_str)
            full_id = f"SLS-{batch_code}{seq_str}{checksum}"
            
            target = PLACEHOLDERS[i]
            current_front_svg = current_front_svg.replace(target, full_id)
            current_back_svg = current_back_svg.replace(target, full_id)
            
            sheet_ids.append(full_id)

            # Готовим запись для JSON
            note_entry = {
                "id": full_id,
                "denomination": 10,
                "batch": batch_code,
                "sequence": current_seq,
                "checksum": int(checksum),
                "status": "Active",
                "issue_date": str(date.today()),
                "origin_sheet": f"Sheet_{next_seq}_to_{next_seq+3}"
            }
            
            if "active_units" in ledger:
                ledger["active_units"].append(note_entry)
            else:
                ledger["banknotes"].append(note_entry)

        # Сохраняем SVG
        file_base = f"Batch-{batch_code}_Seq-{next_seq}-{next_seq+3}"
        svg_front_path = f"{OUTPUT_DIR}/{file_base}_FRONT.svg"
        svg_back_path = f"{OUTPUT_DIR}/{file_base}_BACK.svg"
        png_front_path = f"{OUTPUT_DIR}/{file_base}_FRONT.png"
        png_back_path = f"{OUTPUT_DIR}/{file_base}_BACK.png"

        with open(svg_front_path, 'w', encoding='utf-8') as f:
            f.write(current_front_svg)
        with open(svg_back_path, 'w', encoding='utf-8') as f:
            f.write(current_back_svg)

        print(f"📄 Лист {sheet_num+1} готов: ID {sheet_ids[0]} ... {sheet_ids[-1]}")
        
        # Вызываем функцию экспорта (которая теперь стоит в правильном месте)
        export_to_png(svg_front_path, png_front_path)
        # export_to_png(svg_back_path, png_back_path) # Если нужен PNG задника

        next_seq += 4
        
        if "total_issued" in ledger: ledger["total_issued"] += 40
        elif "meta" in ledger: ledger["meta"]["total_circulation"] += 40

    save_ledger(ledger)
    print(f"\n🎉 Успешно! Создано {sheets_qty} листов.")
    print(f"📁 Проверь папку {OUTPUT_DIR}")

if __name__ == "__main__":
    mint_sheets()

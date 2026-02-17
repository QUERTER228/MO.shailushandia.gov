import json
import os
import re
from datetime import date

# --- НАСТРОЙКИ МОНЕТНОГО ДВОРА ---
LEDGER_FILE = "../ledger.json"
# Пути к файлам (проверь, что они лежат именно так!)
TEMPLATE_FRONT = "../templates/front_10.svg"
TEMPLATE_BACK = "../templates/back_10.svg"
OUTPUT_DIR = "../output_mint"

# Текст-заглушка, который мы ищем в Inkscape-файле
PLACEHOLDER = "SLS-XX0000000" 

# Начальный номер, если партия новая
START_SEQUENCE = 10000 

def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        print(f"🔴 Ошибка: Файл {LEDGER_FILE} не найден. Создайте его!")
        return None
    with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_ledger(data):
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculate_checksum(number_str):
    """
    Логика: Сумма 5 цифр -> берем последнюю цифру от суммы.
    Пример: 10001 -> 1+0+0+0+1 = 2. Итог: 2
    Пример: 10019 -> 1+0+0+1+9 = 11. Итог: 1
    """
    digits = [int(d) for d in number_str]
    total_sum = sum(digits)
    checksum_digit = str(total_sum)[-1] # Берем последний символ строки
    return checksum_digit

def get_next_sequence_number(ledger, batch_code):
    """
    Ищет в базе самый большой номер для указанной серии (например, AA).
    Если не находит, возвращает 10001.
    """
    max_seq = START_SEQUENCE
    
    # Определяем, где список купюр (поддержка старой и новой структуры)
    notes = ledger.get("active_units", ledger.get("banknotes", []))

    for note in notes:
        note_id = note.get("id", "")
        # Разбираем ID: ищем формат SLS-AA(цифры)(цифра)
        # Нам нужны средние 5 цифр.
        # Регулярка ищет: SLS - (ТвояПартия) - (5 цифр) - (1 цифра)
        match = re.search(f"SLS-{batch_code}(\\d{{5}})(\\d)", note_id)
        
        if match:
            current_seq = int(match.group(1)) # Берем группу с 5 цифрами
            if current_seq > max_seq:
                max_seq = current_seq
    
    return max_seq + 1

def mint_batch():
    ledger = load_ledger()
    if not ledger: return

    # 1. Спрашиваем данные у Министра
    print("--- 🖨 ПЕЧАТНЫЙ СТАНОК ШАЙЛУШАНДИИ ---")
    batch_code = input("Введите код партии (например, AA): ").upper().strip()
    try:
        quantity = int(input("Сколько купюр печатаем?: "))
    except ValueError:
        print("Ошибка: введите число.")
        return

    # 2. Проверяем шаблоны
    if not os.path.exists(TEMPLATE_FRONT) or not os.path.exists(TEMPLATE_BACK):
        print("🔴 Ошибка: Не найдены SVG шаблоны в папке templates!")
        return

    # Создаем папку вывода
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Читаем SVG в память
    with open(TEMPLATE_FRONT, 'r', encoding='utf-8') as f:
        front_svg_raw = f.read()
    with open(TEMPLATE_BACK, 'r', encoding='utf-8') as f:
        back_svg_raw = f.read()

    start_seq = get_next_sequence_number(ledger, batch_code)
    print(f"⚙️  Начинаем с порядкового номера: {start_seq}")

    new_notes_count = 0

    for i in range(quantity):
        current_seq = start_seq + i
        seq_str = str(current_seq) # Например "10001"
        
        # Генерируем контрольную цифру
        checksum = calculate_checksum(seq_str)
        
        # Собираем полный ID: SLS-AA100012
        full_id = f"SLS-{batch_code}{seq_str}{checksum}"

        # --- ЗАМЕНА В ФАЙЛАХ ---
        # Заменяем заглушку на реальный ID
        new_front = front_svg_raw.replace(PLACEHOLDER, full_id)
        new_back = back_svg_raw.replace(PLACEHOLDER, full_id)

        # Сохраняем
        f_name_front = f"{OUTPUT_DIR}/{full_id}_FRONT.svg"
        f_name_back = f"{OUTPUT_DIR}/{full_id}_BACK.svg"

        with open(f_name_front, 'w', encoding='utf-8') as f:
            f.write(new_front)
        with open(f_name_back, 'w', encoding='utf-8') as f:
            f.write(new_back)

        # --- ЗАПИСЬ В РЕЕСТР ---
        note_entry = {
            "id": full_id,
            "denomination": 10,
            "batch": batch_code,
            "sequence": current_seq,
            "checksum": int(checksum),
            "status": "Active",
            "issue_date": str(date.today()),
            "files": {
                "front": f_name_front,
                "back": f_name_back
            }
        }

        # Добавляем в список (поддержка обеих структур JSON)
        if "active_units" in ledger:
            ledger["active_units"].append(note_entry)
        elif "banknotes" in ledger:
            ledger["banknotes"].append(note_entry)
        else:
            # Если файл пустой, создаем список
            ledger["active_units"] = [note_entry]

        # Обновляем счетчик валюты
        if "total_issued" in ledger:
            ledger["total_issued"] += 10
        elif "meta" in ledger:
             # Если структура meta, проверяем есть ли total_circulation
             if "total_circulation" in ledger["meta"]:
                 ledger["meta"]["total_circulation"] += 10
        
        print(f"  ✅ [OK] {full_id}")
        new_notes_count += 1

    save_ledger(ledger)
    print(f"\n🎉 Готово! Напечатано {new_notes_count} банкнот.")
    print(f"📁 Файлы лежат в: {OUTPUT_DIR}")
    print(f"📝 Реестр обновлен.")

if __name__ == "__main__":
    mint_batch()

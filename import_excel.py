import pandas as pd
import sqlite3
import os

# ===== تحديد المسارات =====
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "vehicles.db")
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "UPDATE 06-11-2025.xlsx")

# ===== تعريف أسماء الأعمدة الممكنة باللغتين =====
COLUMN_MAP = {
    "plate_number": ["plate_number", "plate number", "رقم اللوحة", "plate", "vehicle plate", "no."],
    "model": ["model", "model year", "الموديل", "موديل"],
    "driver_name": ["driver_name", "emp name", "employee name", "اسم السائق", "السائق"],
    "department": ["department", "project", "القسم", "الإدارة"],
    "status": ["status", "vehicle status", "الحالة", "الموقف"],
    "last_maintenance": ["last_maintenance", "remarks", "ملاحظات", "الصيانة السابقة", "آخر ملاحظة"],
    "next_maintenance": ["next_maintenance", "tamm status", "الصيانة القادمة", "تاريخ الصيانة القادمة"]
}

def normalize_columns(df):
    """توحيد أسماء الأعمدة (عربي / إنجليزي / مختلفة الصيغة)"""
    new_cols = {}
    for std_col, aliases in COLUMN_MAP.items():
        for col in df.columns:
            if str(col).strip().lower() in [a.lower() for a in aliases]:
                new_cols[col] = std_col
    df = df.rename(columns=new_cols)
    return df

# ===== تحميل ملف الإكسل =====
print("🔄 جاري قراءة ملف الإكسل ...")
df = pd.read_excel(EXCEL_PATH)
df = normalize_columns(df)

# ===== التأكد من وجود العمود الأساسي =====
if "plate_number" not in df.columns:
    print("❌ لم يتم العثور على عمود رقم اللوحة (plate_number / plate number)")
    print("الأعمدة الموجودة هي:")
    print(list(df.columns))
    raise SystemExit

# ===== إنشاء قاعدة البيانات إذا لم تكن موجودة =====
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT,
    model TEXT,
    driver_name TEXT,
    department TEXT,
    status TEXT,
    last_maintenance TEXT,
    next_maintenance TEXT
)
''')

# ===== إدخال البيانات =====
count = 0
for _, row in df.iterrows():
    c.execute('''
        INSERT INTO vehicles (plate_number, model, driver_name, department, status, last_maintenance, next_maintenance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(row.get("plate_number", "")),
        str(row.get("model", "")),
        str(row.get("driver_name", "")),
        str(row.get("department", "")),
        str(row.get("status", "")),
        str(row.get("last_maintenance", "")),
        str(row.get("next_maintenance", ""))
    ))
    count += 1

conn.commit()
conn.close()

print(f"✅ تم استيراد {count} سجل من ملف Excel بنجاح إلى قاعدة البيانات!")

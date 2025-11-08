import pandas as pd
import os

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "UPDATE 06-11-2025.xlsx")

# تحميل أول صف من الملف فقط
df = pd.read_excel(EXCEL_PATH, nrows=1)

print("🟨 الأعمدة الموجودة في ملف Excel:")
for col in df.columns:
    print("-", col)

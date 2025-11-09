import pandas as pd
import sqlite3
from datetime import datetime

# Read Excel
print("📂 Reading Excel...")
df = pd.read_excel('e:/Vehicles_Update_2025.xlsx')
print(f"✅ Loaded {len(df)} rows")
print(f"Columns: {df.columns.tolist()}")

# Normalize column names
df.columns = [str(col).strip().lower().replace(" ", "_").replace(".", "") for col in df.columns]
print(f"\nNormalized columns: {df.columns.tolist()}")

# Connect to database
print("\n📊 Connecting to database...")
conn = sqlite3.connect('database/vehicles.db')
c = conn.cursor()

# Get table columns
c.execute("PRAGMA table_info(vehicles)")
table_cols = [r[1] for r in c.fetchall() if r[1] != "id"]
print(f"DB columns ({len(table_cols)}): {table_cols}")

# Test import
target_region = "Riyadh"
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
inserted = 0
errors = []

for idx, row in df.iterrows():
    row_dict = dict(row)
    
    # Skip empty rows
    if not any(pd.notna(v) and str(v).strip() for v in row_dict.values()):
        print(f"⚠️  Row {idx}: Skipped (empty)")
        continue
    
    insert_cols = []
    values = []
    
    for col in table_cols:
        val = row_dict.get(col)
        
        if col == "last_modified":
            val = None
        elif col == "region":
            val = target_region
        elif col in ["handover_pdf", "driver_id_pdf"]:
            val = None
        
        # Convert NaN to None
        if pd.isna(val):
            val = None
        
        insert_cols.append(col)
        values.append(val)
    
    try:
        placeholders = ",".join(["?"] * len(insert_cols))
        cols_sql = ",".join(insert_cols)
        c.execute(f"INSERT INTO vehicles ({cols_sql}) VALUES ({placeholders})", values)
        inserted += 1
        if inserted <= 3:
            print(f"✅ Row {idx}: Inserted plate={row_dict.get('plate_number')}")
    except Exception as e:
        errors.append(f"Row {idx}: {e}")
        if len(errors) <= 3:
            print(f"❌ Row {idx}: {e}")

conn.commit()
print(f"\n🎉 Total inserted: {inserted}")
if errors:
    print(f"⚠️  Total errors: {len(errors)}")

# Verify
c.execute('SELECT COUNT(*) FROM vehicles')
print(f"📊 Total in DB: {c.fetchone()[0]}")

c.execute('SELECT plate_number, vehicle_brand, region FROM vehicles LIMIT 3')
print("\n--- Sample records ---")
for r in c.fetchall():
    print(f"  {r}")

conn.close()
print("\n✅ Done!")

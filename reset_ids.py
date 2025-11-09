"""
Script to reset vehicle IDs to sequential order
Run this when IDs become too high
"""
import sqlite3
from datetime import datetime

DB_PATH = "database/vehicles.db"

print("=" * 50)
print("Reset Vehicle IDs")
print("=" * 50)

# Backup first
backup_name = f"database/vehicles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
print(f"\n1. Creating backup: {backup_name}")
import shutil
shutil.copy(DB_PATH, backup_name)
print("   ✅ Backup created")

# Connect
print("\n2. Connecting to database...")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get all vehicles
c.execute("SELECT * FROM vehicles ORDER BY id")
vehicles = c.fetchall()
print(f"   ✅ Found {len(vehicles)} vehicles")

# Create temp table with sequential IDs
print("\n3. Creating temporary table...")
c.execute("""
    CREATE TABLE vehicles_temp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT,
        vehicle_brand TEXT,
        model_year TEXT,
        vehicle_supplier TEXT,
        vehicle_type TEXT,
        vehicle_color TEXT,
        vehicle_status TEXT,
        district TEXT,
        iqama_no TEXT,
        emp_no TEXT,
        emp_name TEXT,
        project TEXT,
        previous_user TEXT,
        tamm_status TEXT,
        remarks TEXT,
        handover_pdf TEXT,
        driver_id_pdf TEXT,
        last_modified TEXT,
        region TEXT
    )
""")

# Insert with new sequential IDs
print("\n4. Inserting data with sequential IDs...")
for v in vehicles:
    c.execute("""
        INSERT INTO vehicles_temp 
        (plate_number, vehicle_brand, model_year, vehicle_supplier, vehicle_type,
         vehicle_color, vehicle_status, district, iqama_no, emp_no, emp_name,
         project, previous_user, tamm_status, remarks, handover_pdf, driver_id_pdf,
         last_modified, region)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, v[1:])  # Skip old ID

# Drop old table and rename
print("\n5. Replacing old table...")
c.execute("DROP TABLE vehicles")
c.execute("ALTER TABLE vehicles_temp RENAME TO vehicles")

# Reset autoincrement
c.execute("DELETE FROM sqlite_sequence WHERE name='vehicles'")

conn.commit()
print("   ✅ Table reset complete")

# Verify
c.execute("SELECT COUNT(*) FROM vehicles")
count = c.fetchone()[0]
c.execute("SELECT MIN(id), MAX(id) FROM vehicles")
min_id, max_id = c.fetchone()

print(f"\n6. Verification:")
print(f"   Total vehicles: {count}")
print(f"   ID range: {min_id} to {max_id}")

conn.close()

print("\n" + "=" * 50)
print("✅ Done! IDs reset to 1, 2, 3...")
print("=" * 50)

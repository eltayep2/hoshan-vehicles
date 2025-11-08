from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    flash,
    session,
)
import sqlite3, os, json
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "hoshan_secret_key"

BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "vehicles.db")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "xlsx"}

# =========================
# admins (super + regions)
# =========================
ADMINS = {
    "eltayep": {"password": "SScc123456", "region": "ALL"},  # super admin
    "E001": {"password": "najran123", "region": "Najran"},
    "E002": {"password": "jeddah123", "region": "Jeddah"},
    "E003": {"password": "asser123", "region": "Asser"},
    "E004": {"password": "jazan123", "region": "Jazan"},
    "E005": {"password": "baha123", "region": "Baha"},
    "E006": {"password": "riyadh123", "region": "Riyadh"},
    "E007": {"password": "dmam123", "region": "Dammam"},
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# DB INIT
# =========================
def init_db():
    """
    create vehicles table if not exists.
    removed UNIQUE from plate_number so same plate can exist in different region.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicles (
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
        """
    )
    # make sure new columns exist if table is old
    c.execute("PRAGMA table_info(vehicles)")
    cols = [r[1] for r in c.fetchall()]
    for col in ["region", "last_modified", "handover_pdf", "driver_id_pdf"]:
        if col not in cols:
            c.execute(f"ALTER TABLE vehicles ADD COLUMN {col} TEXT")
    conn.commit()
    conn.close()


init_db()


# =========================
# helpers
# =========================
def resequence_ids():
    """re-number ids after delete"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM vehicles ORDER BY id ASC")
    all_ids = [row[0] for row in c.fetchall()]
    new_id = 1
    for old_id in all_ids:
        c.execute("UPDATE vehicles SET id=? WHERE id=?", (new_id, old_id))
        new_id += 1
    c.execute("DELETE FROM sqlite_sequence WHERE name='vehicles'")
    conn.commit()
    conn.close()


# =========================
# LOGIN / LOGOUT
# =========================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET, POST"])
def login():
    error = None
    if request.method == "POST":
        emp_no = request.form.get("emp_no", "").strip()
        password = request.form.get("password", "").strip()
        admin = ADMINS.get(emp_no)
        if admin and admin["password"] == password:
            session["emp_no"] = emp_no
            session["region"] = admin["region"]
            flash(f"✅ Logged in as {emp_no} ({admin['region']})", "success")
            return redirect(url_for("home"))
        else:
            error = "❌ Incorrect EMP No or Password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    flash("🚪 Logged out successfully", "info")
    return redirect(url_for("login"))


# =========================
# HOME
# =========================
@app.route("/home", methods=["GET", "POST"])
def home():
    if "region" not in session:
        return redirect(url_for("login"))

    region = session["region"]
    search_plate = request.form.get("search_plate", "").strip()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # fetch by region
    if region == "ALL":
        if search_plate:
            c.execute(
                "SELECT * FROM vehicles WHERE plate_number LIKE ? ORDER BY id ASC",
                ("%" + search_plate + "%",),
            )
        else:
            c.execute("SELECT * FROM vehicles ORDER BY id ASC")
    else:
        if search_plate:
            c.execute(
                "SELECT * FROM vehicles WHERE region=? AND plate_number LIKE ? ORDER BY id ASC",
                (region, "%" + search_plate + "%"),
            )
        else:
            c.execute("SELECT * FROM vehicles WHERE region=? ORDER BY id ASC", (region,))
    vehicles = c.fetchall()

    # stats
    def count_query(q, params=()):
        c.execute(q, params)
        r = c.fetchone()
        return r[0] if r and r[0] else 0

    if region == "ALL":
        total = count_query("SELECT COUNT(*) FROM vehicles")
    else:
        total = count_query("SELECT COUNT(*) FROM vehicles WHERE region=?", (region,))

    def count_status_for(reg, *keywords):
        placeholders = " OR ".join(["vehicle_status LIKE ?" for _ in keywords])
        vals = tuple("%" + k + "%" for k in keywords)
        if reg == "ALL":
            c.execute(f"SELECT COUNT(*) FROM vehicles WHERE {placeholders}", vals)
        else:
            c.execute(
                f"SELECT COUNT(*) FROM vehicles WHERE region=? AND ({placeholders})",
                (reg,) + vals,
            )
        r = c.fetchone()
        return r[0] if r and r[0] else 0

    active = count_status_for(region, "Active", "نشط")
    inactive = count_status_for(region, "Inactive", "متعطل", "اجازة")
    maintenance = count_status_for(region, "Under Maintenance", "صيانة")

    if region == "ALL":
        rented = count_query("SELECT COUNT(*) FROM vehicles WHERE project IS NOT NULL AND TRIM(project) != ''")
        modified = count_query("SELECT COUNT(*) FROM vehicles WHERE last_modified IS NOT NULL AND TRIM(last_modified) != ''")
    else:
        rented = count_query(
            "SELECT COUNT(*) FROM vehicles WHERE region=? AND project IS NOT NULL AND TRIM(project) != ''",
            (region,),
        )
        modified = count_query(
            "SELECT COUNT(*) FROM vehicles WHERE region=? AND last_modified IS NOT NULL AND TRIM(last_modified) != ''",
            (region,),
        )

    conn.close()

    return render_template(
        "home.html",
        vehicles=vehicles,
        region=region,
        total=total,
        active=active,
        inactive=inactive,
        maintenance=maintenance,
        rented=rented,
        modified=modified,
        search_plate=search_plate,
    )


# =========================
# VIEW REGION (super)
# =========================
@app.route("/region/<region_name>")
def view_region(region_name):
    # only super admin
    if "region" not in session or session["region"] != "ALL":
        flash("⚠️ Only super admin can view all regions", "warning")
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM vehicles WHERE region=? ORDER BY id ASC", (region_name,))
    vehicles = c.fetchall()

    c.execute("SELECT COUNT(*) FROM vehicles WHERE region=?", (region_name,))
    total = c.fetchone()[0] or 0

    def count_status(*keywords):
        placeholders = " OR ".join(["vehicle_status LIKE ?" for _ in keywords])
        values = tuple("%" + k + "%" for k in keywords)
        q = f"SELECT COUNT(*) FROM vehicles WHERE region=? AND ({placeholders})"
        c.execute(q, (region_name,) + values)
        r = c.fetchone()
        return r[0] if r and r[0] else 0

    active = count_status("Active", "نشط")
    inactive = count_status("Inactive", "متعطل", "اجازة")
    maintenance = count_status("Under Maintenance", "صيانة")

    c.execute(
        "SELECT COUNT(*) FROM vehicles WHERE region=? AND project IS NOT NULL AND TRIM(project) != ''",
        (region_name,),
    )
    rented = c.fetchone()[0] or 0
    c.execute(
        "SELECT COUNT(*) FROM vehicles WHERE region=? AND last_modified IS NOT NULL AND TRIM(last_modified) != ''",
        (region_name,),
    )
    modified = c.fetchone()[0] or 0

    conn.close()

    return render_template(
        "home.html",
        vehicles=vehicles,
        region=region_name,
        total=total,
        active=active,
        inactive=inactive,
        maintenance=maintenance,
        rented=rented,
        modified=modified,
        search_plate="",
    )


# =========================
# upload driver ID (versioned)
# =========================
@app.route("/upload_driver_id/<int:vehicle_id>", methods=["POST"])
def upload_driver_id(vehicle_id):
    if "driver_id_pdf" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))

    file = request.files["driver_id_pdf"]
    if not (file and allowed_file(file.filename)):
        flash("⚠️ Invalid file", "danger")
        return redirect(url_for("home"))

    vehicle_folder = os.path.join(UPLOAD_FOLDER, str(vehicle_id))
    os.makedirs(vehicle_folder, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT driver_id_pdf FROM vehicles WHERE id=?", (vehicle_id,))
    row = c.fetchone()
    old_name = row[0] if row else None

    ts = datetime.now().strftime("%Y%m%d%H%M")
    if old_name:
        old_abs = os.path.join(UPLOAD_FOLDER, old_name)
        if os.path.exists(old_abs):
            os.rename(old_abs, os.path.join(vehicle_folder, f"OLD_ID_{ts}_{os.path.basename(old_name)}"))

    new_name = f"ID_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    relative_path = f"{vehicle_id}/{new_name}"
    file.save(os.path.join(vehicle_folder, new_name))

    c.execute("UPDATE vehicles SET driver_id_pdf=? WHERE id=?", (relative_path, vehicle_id))
    conn.commit()
    conn.close()

    flash("🪪 Driver ID uploaded (old kept)", "success")
    return redirect(url_for("home"))


# =========================
# upload handover (versioned)
# =========================
@app.route("/upload_handover/<int:vehicle_id>", methods=["POST"])
def upload_handover(vehicle_id):
    if "handover_pdf" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))

    file = request.files["handover_pdf"]
    if not (file and allowed_file(file.filename)):
        flash("⚠️ Invalid file", "danger")
        return redirect(url_for("home"))

    vehicle_folder = os.path.join(UPLOAD_FOLDER, str(vehicle_id))
    os.makedirs(vehicle_folder, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT handover_pdf FROM vehicles WHERE id=?", (vehicle_id,))
    row = c.fetchone()
    old_name = row[0] if row else None

    ts = datetime.now().strftime("%Y%m%d%H%M")
    if old_name:
        old_abs = os.path.join(UPLOAD_FOLDER, old_name)
        if os.path.exists(old_abs):
            os.rename(old_abs, os.path.join(vehicle_folder, f"OLD_HO_{ts}_{os.path.basename(old_name)}"))

    new_name = f"HO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    relative_path = f"{vehicle_id}/{new_name}"
    file.save(os.path.join(vehicle_folder, new_name))

    c.execute("UPDATE vehicles SET handover_pdf=? WHERE id=?", (relative_path, vehicle_id))
    conn.commit()
    conn.close()

    flash("📄 Handover uploaded (old kept)", "success")
    return redirect(url_for("home"))


# =========================
# serve uploads (with subfolders)
# =========================
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# =========================
# view vehicle
# =========================
@app.route("/vehicle/<int:vehicle_id>")
def view_vehicle(vehicle_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
    v = c.fetchone()
    conn.close()
    return render_template("view_vehicle.html", v=v)


# =========================
# edit vehicle
# =========================
@app.route("/edit_vehicle/<int:vehicle_id>", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if request.method == "POST":
        last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data = (
            request.form.get("plate_number", ""),
            request.form.get("vehicle_brand", ""),
            request.form.get("model_year", ""),
            request.form.get("vehicle_supplier", ""),
            request.form.get("vehicle_type", ""),
            request.form.get("vehicle_color", ""),
            request.form.get("vehicle_status", ""),
            request.form.get("district", ""),
            request.form.get("iqama_no", ""),
            request.form.get("emp_no", ""),
            request.form.get("emp_name", ""),
            request.form.get("project", ""),
            request.form.get("previous_user", ""),
            request.form.get("tamm_status", ""),
            request.form.get("remarks", ""),
            last_modified,
            vehicle_id,
        )

        c.execute(
            """
            UPDATE vehicles
            SET plate_number=?, vehicle_brand=?, model_year=?, vehicle_supplier=?,
                vehicle_type=?, vehicle_color=?, vehicle_status=?, district=?,
                iqama_no=?, emp_no=?, emp_name=?, project=?,
                previous_user=?, tamm_status=?, remarks=?, last_modified=?
            WHERE id=?
            """,
            data,
        )
        conn.commit()
        conn.close()
        flash("🛠️ Vehicle updated", "info")
        return redirect(url_for("home"))

    c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
    v = c.fetchone()
    conn.close()
    return render_template("edit_vehicle.html", v=v)


# =========================
# delete vehicle
# =========================
@app.route("/delete_vehicle/<int:vehicle_id>")
def delete_vehicle(vehicle_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
    conn.commit()
    conn.close()
    resequence_ids()
    flash("🗑️ Vehicle deleted", "danger")
    return redirect(url_for("home"))


# =========================
# IMPORT EXCEL (ADMIN ONLY, PER REGION)
# =========================
@app.route("/import_excel", methods=["POST"])
def import_excel():
    if "region" not in session:
        flash("⚠️ Unauthorized. Please log in again.", "danger")
        return redirect(url_for("login"))

    user_region = session.get("region")
    if user_region != "ALL":
        flash("🚫 Import Excel allowed for admin only.", "danger")
        return redirect(url_for("home"))

    target_region = (request.form.get("region_name") or "").strip()
    if not target_region or target_region == "ALL":
        flash("⚠️ Please select a specific region before import.", "warning")
        return redirect(url_for("home"))

    if "excel_file" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))
    file = request.files["excel_file"]
    if not file or not allowed_file(file.filename):
        flash("⚠️ Please upload a valid Excel file (.xlsx)", "danger")
        return redirect(url_for("home"))

    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(filepath)

    df = pd.read_excel(filepath)
    df.columns = [str(col).strip().lower().replace(" ", "_").replace(".", "") for col in df.columns]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(vehicles)")
    table_cols = [r[1] for r in c.fetchall() if r[1] != "id"]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    for _, row in df.iterrows():
        row_dict = dict(row)
        if not any(str(v).strip() for v in row_dict.values()):
            continue

        insert_cols = []
        values = []
        for col in table_cols:
            key = col.lower()
            val = row_dict.get(key)

            if col == "last_modified":
                val = now_str
            elif col == "region":
                val = target_region
            elif col in ["handover_pdf", "driver_id_pdf"]:
                val = None

            insert_cols.append(col)
            values.append(val)

        placeholders = ",".join(["?"] * len(insert_cols))
        cols_sql = ",".join(insert_cols)
        c.execute(f"INSERT OR IGNORE INTO vehicles ({cols_sql}) VALUES ({placeholders})", values)
        inserted += 1

    conn.commit()
    conn.close()

    flash(f"✅ Excel imported successfully ({inserted} records) for {target_region}", "success")
    return redirect(url_for("view_region", region_name=target_region))


# =========================
# export excel (per region)
# =========================
@app.route("/export_excel")
def export_excel():
    region = request.args.get("region") or session.get("region", "ALL")
    conn = sqlite3.connect(DB_PATH)
    if region == "ALL":
        df = pd.read_sql_query("SELECT * FROM vehicles", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM vehicles WHERE region=?", conn, params=(region,))
    export_name = f"vehicles_export_{region}.xlsx"
    export_path = os.path.join(UPLOAD_FOLDER, export_name)
    df.to_excel(export_path, index=False)
    conn.close()
    return send_from_directory(UPLOAD_FOLDER, export_name, as_attachment=True)


# =========================
# old files list
# =========================
@app.route("/old_files/<int:vehicle_id>/<string:file_type>")
def old_files(vehicle_id, file_type):
    vehicle_folder = os.path.join(UPLOAD_FOLDER, str(vehicle_id))
    files = []
    if os.path.exists(vehicle_folder):
        files = [
            f for f in os.listdir(vehicle_folder)
            if f.upper().startswith(f"OLD_{file_type.upper()}")
        ]
    return render_template("old_files.html", vehicle_id=vehicle_id, file_type=file_type, files=files)


# =========================
# maintenance request (SINGLE + MULTI) - مدمجة
# =========================
@app.route("/maintenance_request", methods=["POST"])
@app.route("/maintenance_request_multi", methods=["POST"])
def maintenance_request_combined():
    """إصدار طلب صيانة واحدة أو لعدة سيارات"""
    ids_json = request.form.get("vehicle_ids")
    desc = request.form.get("desc", "").strip()

    # حاول نقرأ عدة سيارات من JSON
    try:
        vehicle_ids = json.loads(ids_json) if ids_json else []
    except Exception:
        vehicle_ids = []

    # لو مافي JSON جاي من الواجهة، جرب نقرأ vehicle_id عادي
    if not vehicle_ids and request.form.get("vehicle_id"):
        vehicle_ids = [request.form.get("vehicle_id")]

    # تحقق من المدخلات
    if not vehicle_ids or not desc:
        flash("⚠️ Please select one or more vehicles and enter maintenance details.", "danger")
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    placeholders = ",".join("?" * len(vehicle_ids))
    c.execute(
        f"""SELECT id, plate_number, vehicle_brand, model_year, vehicle_type, emp_name, project, region
            FROM vehicles WHERE id IN ({placeholders})""",
        vehicle_ids,
    )
    vehicles = c.fetchall()

    # حدث الملاحظات
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for vid in vehicle_ids:
        c.execute(
            "UPDATE vehicles SET remarks=?, last_modified=? WHERE id=?",
            (f"Maintenance Request: {desc}", now_str, vid),
        )

    conn.commit()
    conn.close()

    request_date = datetime.now().strftime("%Y-%m-%d")
    headers = ["ID", "Plate", "Brand", "Model", "Type", "Employee", "Project", "Region"]
    return render_template(
        "maintenance_view.html",
        vehicles=vehicles,
        headers=headers,
        desc=desc,
        request_date=request_date,
    )

# =========================
# BULK TRANSFER & BULK DELETE
# =========================

@app.route("/bulk_transfer", methods=["POST"])
def bulk_transfer():
    ids_json = request.form.get("vehicle_ids")
    target_region = request.form.get("target_region", "").strip()

    try:
        vehicle_ids = json.loads(ids_json)
    except Exception:
        vehicle_ids = []

    if not vehicle_ids or not target_region:
        flash("⚠️ Please select vehicles and a target region.", "danger")
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(vehicle_ids))
    c.execute(
        f"UPDATE vehicles SET region=? WHERE id IN ({placeholders})",
        (target_region, *vehicle_ids),
    )
    conn.commit()
    conn.close()

    flash(f"🚚 {len(vehicle_ids)} vehicle(s) moved to {target_region}.", "success")

    # ✅ توجيه مباشر إلى المنطقة الجديدة بعد النقل
    return redirect(url_for("view_region", region_name=target_region))


@app.route("/bulk_delete", methods=["POST"])
def bulk_delete():
    ids_json = request.form.get("vehicle_ids")

    try:
        vehicle_ids = json.loads(ids_json)
    except Exception:
        vehicle_ids = []

    if not vehicle_ids:
        flash("⚠️ Please select at least one vehicle to delete.", "danger")
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(vehicle_ids))
    c.execute(f"DELETE FROM vehicles WHERE id IN ({placeholders})", vehicle_ids)
    conn.commit()
    conn.close()

    resequence_ids()
    flash(f"🗑️ {len(vehicle_ids)} vehicle(s) deleted successfully.", "info")

    return redirect(url_for("home"))

# =========================
# run
# =========================
if __name__ == "__main__":
    app.run(debug=True)

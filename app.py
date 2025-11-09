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
from functools import wraps
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Production mode detection
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

# Secret key configuration
if IS_PRODUCTION:
    # في Production: استخدم متغير بيئي أو مفتاح قوي
    app.secret_key = os.environ.get('SECRET_KEY', 'CHANGE_THIS_TO_STRONG_SECRET_KEY_IN_PRODUCTION')
else:
    # في Development: مفتاح تطوير
    app.secret_key = 'hoshan_dev_secret_key'

# Security settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Base directory and paths
BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "vehicles.db")

# Log startup mode
logger.info(f"Starting app in {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'} mode")
logger.info(f"Database path: {DB_PATH}")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "xlsx"}

# Allowed MIME types for security
ALLOWED_MIME_TYPES = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

# =========================
# DECORATORS
# =========================
def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'region' not in session:
            flash('⚠️ Please login first', 'warning')
            logger.warning(f'Unauthorized access attempt to {request.path}')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_only(f):
    """Decorator to restrict access to super admin only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'region' not in session:
            flash('⚠️ Please login first', 'warning')
            return redirect(url_for('login'))
        if session.get('region') != 'ALL':
            flash('🚫 This action is only available for super admin', 'danger')
            logger.warning(f'Admin-only access attempt by {session.get("emp_no")} to {request.path}')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

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


def validate_file(file):
    """Enhanced file validation with size and type checking"""
    if not file or file.filename == '':
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, "Invalid file type. Only PDF and XLSX allowed"
    
    # Check file size (already handled by MAX_CONTENT_LENGTH, but good to have)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > 16 * 1024 * 1024:  # 16MB
        return False, "File too large. Maximum 16MB"
    
    if file_size == 0:
        return False, "File is empty"
    
    return True, "Valid"


def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise


# =========================
# DB INIT
# =========================
def init_db():
    """
    create vehicles table if not exists.
    removed UNIQUE from plate_number so same plate can exist in different region.
    """
    try:
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
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        raise
    finally:
        conn.close()


init_db()


# =========================
# helpers
# =========================
def resequence_ids():
    """re-number ids after delete"""
    try:
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
        logger.info("IDs resequenced successfully")
    except sqlite3.Error as e:
        logger.error(f"Error resequencing IDs: {e}")
        raise
    finally:
        conn.close()


def redirect_to_current_region():
    """Helper function to redirect to home (which shows current region from session)"""
    # Just redirect to home - it will use the current session['region']
    return redirect(url_for('home'))


# =========================
# LOGIN / LOGOUT
# =========================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        emp_no = request.form.get("emp_no", "").strip()
        password = request.form.get("password", "").strip()
        admin = ADMINS.get(emp_no)
        if admin and admin["password"] == password:
            session["emp_no"] = emp_no
            session["region"] = admin["region"]
            logger.info(f"User {emp_no} logged in successfully from {request.remote_addr}")
            flash(f"✅ Logged in as {emp_no} ({admin['region']})", "success")
            return redirect(url_for("home"))
        else:
            logger.warning(f"Failed login attempt for {emp_no} from {request.remote_addr}")
            error = "❌ Incorrect EMP No or Password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    emp_no = session.get('emp_no', 'Unknown')
    session.clear()
    logger.info(f"User {emp_no} logged out")
    flash("🚪 Logged out successfully", "info")
    return redirect(url_for("login"))


# =========================
# HOME - Shows vehicles based on current session region
# =========================
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    # Use current region from session (set by login or region links)
    region = session.get("region", "ALL")
    search_plate = request.form.get("search_plate", "").strip()
    
    # Check if undo is still valid (within 5 minutes = 300 seconds)
    show_undo = False
    if session.get('show_undo') and session.get('delete_timestamp'):
        elapsed = datetime.now().timestamp() - session.get('delete_timestamp')
        if elapsed < 300:  # 5 minutes
            show_undo = True
        else:
            # Clear expired undo data
            session.pop('deleted_vehicles', None)
            session.pop('delete_timestamp', None)
            session.pop('show_undo', None)

    try:
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

        regions_list = ["Najran", "Jeddah", "Asser", "Jazan", "Baha", "Riyadh", "Dammam"]

        response = app.make_response(render_template(
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
            regions=regions_list,
            show_undo=show_undo,
        ))
        # Prevent caching to ensure page always reloads with fresh data
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    except sqlite3.Error as e:
        logger.error(f"Database error in home route: {e}")
        flash("⚠️ Database error occurred", "danger")
        return redirect(url_for("login"))
    finally:
        if 'conn' in locals():
            conn.close()


# =========================
# ADD VEHICLE
# =========================
@app.route("/add_vehicle", methods=["GET"])
@login_required
def add_vehicle_page():
    """صفحة إضافة سيارة جديدة"""
    return render_template("add_vehicle.html")


@app.route("/add_vehicle", methods=["POST"])
@login_required
def add_vehicle():
    """معالجة إضافة سيارة جديدة"""
    try:
        # Get form data
        plate_number = request.form.get("plate_number", "").strip()
        vehicle_brand = request.form.get("vehicle_brand", "").strip()
        model_year = request.form.get("model_year", "").strip()
        vehicle_supplier = request.form.get("vehicle_supplier", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        vehicle_color = request.form.get("vehicle_color", "").strip()
        vehicle_status = request.form.get("vehicle_status", "").strip()
        district = request.form.get("district", "").strip()
        iqama_no = request.form.get("iqama_no", "").strip()
        emp_no = request.form.get("emp_no", "").strip()
        emp_name = request.form.get("emp_name", "").strip()
        project = request.form.get("project", "").strip()
        region = request.form.get("region", "").strip()
        tamm_status = request.form.get("tamm_status", "").strip()
        remarks = request.form.get("remarks", "").strip()
        
        # Validate required fields
        if not all([plate_number, vehicle_brand, model_year, vehicle_type, vehicle_color, 
                    vehicle_status, emp_no, emp_name, project, region]):
            flash("⚠️ Please fill all required fields marked with *", "danger")
            return redirect(url_for("add_vehicle_page"))
        
        # Validate plate number format
        if len(plate_number) < 3:
            flash("⚠️ Plate number must be at least 3 characters", "danger")
            return redirect(url_for("add_vehicle_page"))
        
        # Validate model year
        try:
            year = int(model_year)
            current_year = datetime.now().year
            if year < 1990 or year > current_year + 1:
                flash(f"⚠️ Model year must be between 1990 and {current_year + 1}", "danger")
                return redirect(url_for("add_vehicle_page"))
        except ValueError:
            flash("⚠️ Model year must be a valid number", "danger")
            return redirect(url_for("add_vehicle_page"))
        
        # Validate iqama number if provided
        if iqama_no and (not iqama_no.isdigit() or len(iqama_no) != 10):
            flash("⚠️ Iqama number must be exactly 10 digits", "danger")
            return redirect(url_for("add_vehicle_page"))
        
        # Insert into database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if plate number already exists
        c.execute("SELECT id FROM vehicles WHERE plate_number=?", (plate_number,))
        existing = c.fetchone()
        if existing:
            flash(f"⚠️ Vehicle with plate number '{plate_number}' already exists (ID: {existing[0]})", "warning")
            return redirect(url_for("add_vehicle_page"))
        
        # Insert vehicle with all fields (last_modified should be NULL for new vehicles)
        c.execute("""
            INSERT INTO vehicles (
                plate_number, vehicle_brand, model_year, vehicle_supplier, vehicle_type,
                vehicle_color, vehicle_status, district, iqama_no, emp_no, emp_name,
                project, previous_user, tamm_status, remarks, last_modified, region,
                handover_pdf, driver_id_pdf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plate_number, vehicle_brand, model_year, vehicle_supplier, vehicle_type,
            vehicle_color, vehicle_status, district, iqama_no, emp_no, emp_name,
            project, "", tamm_status, remarks, None, region, None, None
        ))
        
        vehicle_id = c.lastrowid
        conn.commit()
        
        logger.info(f"New vehicle added: {plate_number} (ID: {vehicle_id}) assigned to {emp_name} ({emp_no}) in {region} by {session.get('emp_no')}")
        flash(f"✅ Vehicle '{plate_number}' added successfully and assigned to {emp_name}", "success")
        return redirect_to_current_region()
    
    except sqlite3.Error as e:
        logger.error(f"Database error adding vehicle {plate_number}: {e}")
        flash(f"⚠️ Database error: {str(e)}", "danger")
        return redirect(url_for("add_vehicle_page"))
    finally:
        if 'conn' in locals():
            conn.close()


# =========================
# VIEW ALL REGIONS (super admin)
# =========================
# VIEW ALL REGIONS - Allow any logged-in user to view all regions
# =========================
@app.route("/region/ALL")
@login_required
def view_all_regions():
    # Update session to ALL
    session['region'] = 'ALL'
    return redirect(url_for('home'))


# =========================
# VIEW REGION - Allow any logged-in user to view their own or other regions
# =========================
@app.route("/region/<region_name>")
@login_required
def view_region(region_name):
    # Update session with current region and redirect to home
    session['region'] = region_name
    return redirect(url_for('home'))


# =========================
# upload driver ID (versioned)
# =========================
@app.route("/upload_driver_id/<int:vehicle_id>", methods=["POST"])
@login_required
def upload_driver_id(vehicle_id):
    if "driver_id_pdf" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))

    file = request.files["driver_id_pdf"]
    
    # Enhanced validation
    is_valid, message = validate_file(file)
    if not is_valid:
        flash(f"⚠️ {message}", "danger")
        return redirect(url_for("home"))
    
    try:
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
        
        logger.info(f"Driver ID uploaded for vehicle {vehicle_id} by {session.get('emp_no')}")
        flash("🪪 Driver ID uploaded (old kept)", "success")
        
    except Exception as e:
        logger.error(f"Error uploading driver ID for vehicle {vehicle_id}: {e}")
        flash("⚠️ Error uploading file", "danger")
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for("home"))


# =========================
# upload handover (versioned)
# =========================
@app.route("/upload_handover/<int:vehicle_id>", methods=["POST"])
@login_required
def upload_handover(vehicle_id):
    if "handover_pdf" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))

    file = request.files["handover_pdf"]
    
    # Enhanced validation
    is_valid, message = validate_file(file)
    if not is_valid:
        flash(f"⚠️ {message}", "danger")
        return redirect(url_for("home"))

    try:
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
        
        logger.info(f"Handover uploaded for vehicle {vehicle_id} by {session.get('emp_no')}")
        flash("📄 Handover uploaded (old kept)", "success")
        
    except Exception as e:
        logger.error(f"Error uploading handover for vehicle {vehicle_id}: {e}")
        flash("⚠️ Error uploading file", "danger")
    finally:
        if 'conn' in locals():
            conn.close()

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
@login_required
def view_vehicle(vehicle_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
        v = c.fetchone()
        
        if not v:
            flash("⚠️ Vehicle not found", "warning")
            return redirect(url_for("home"))
        
        return render_template("view_vehicle.html", v=v)
    
    except sqlite3.Error as e:
        logger.error(f"Error viewing vehicle {vehicle_id}: {e}")
        flash("⚠️ Error loading vehicle details", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()


# =========================
# edit vehicle
# =========================
@app.route("/edit_vehicle/<int:vehicle_id>", methods=["GET", "POST"])
@login_required
def edit_vehicle(vehicle_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        if request.method == "POST":
            # Get current vehicle data first
            c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
            old_vehicle = c.fetchone()
            
            if not old_vehicle:
                flash("⚠️ Vehicle not found", "warning")
                return redirect(url_for("home"))
            
            # Get new data from form
            new_data = (
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
            )
            
            # Compare old and new data (indices 1-15 in old_vehicle tuple)
            old_data = old_vehicle[1:16]
            
            # Check if any field actually changed
            data_changed = False
            for old_val, new_val in zip(old_data, new_data):
                old_str = str(old_val) if old_val is not None else ""
                new_str = str(new_val) if new_val is not None else ""
                if old_str != new_str:
                    data_changed = True
                    break
            
            # Update last_modified only if data actually changed
            if data_changed:
                last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Keep the existing last_modified value
                last_modified = old_vehicle[18] if old_vehicle[18] else None
            
            c.execute(
                """
                UPDATE vehicles
                SET plate_number=?, vehicle_brand=?, model_year=?, vehicle_supplier=?,
                    vehicle_type=?, vehicle_color=?, vehicle_status=?, district=?,
                    iqama_no=?, emp_no=?, emp_name=?, project=?,
                    previous_user=?, tamm_status=?, remarks=?, last_modified=?
                WHERE id=?
                """,
                new_data + (last_modified, vehicle_id),
            )
            conn.commit()
            
            if data_changed:
                logger.info(f"Vehicle {vehicle_id} updated by {session.get('emp_no')}")
                flash("🛠️ Vehicle updated", "info")
            else:
                flash("ℹ️ No changes were made", "info")
            
            return redirect_to_current_region()

        c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
        v = c.fetchone()
        
        if not v:
            flash("⚠️ Vehicle not found", "warning")
            return redirect(url_for("home"))
        
        return render_template("edit_vehicle.html", v=v)
    
    except sqlite3.Error as e:
        logger.error(f"Error editing vehicle {vehicle_id}: {e}")
        flash("⚠️ Error updating vehicle", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()


# =========================
# delete vehicle
# =========================
@app.route("/delete_vehicle/<int:vehicle_id>")
@login_required
def delete_vehicle(vehicle_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
        conn.commit()
        logger.info(f"Vehicle {vehicle_id} deleted by {session.get('emp_no')}")
        resequence_ids()
        flash("🗑️ Vehicle deleted", "danger")
    except sqlite3.Error as e:
        logger.error(f"Error deleting vehicle {vehicle_id}: {e}")
        flash("⚠️ Error deleting vehicle", "danger")
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect_to_current_region()


# =========================
# delete multiple vehicles
# =========================
@app.route("/delete_vehicles", methods=["POST"])
@login_required
def delete_vehicles():
    vehicle_ids = request.form.getlist("vehicle_ids")
    
    if not vehicle_ids:
        flash("⚠️ No vehicles selected", "warning")
        return redirect(url_for("home"))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Store deleted vehicles data for undo
        deleted_data = []
        for vehicle_id in vehicle_ids:
            c.execute("SELECT * FROM vehicles WHERE id=?", (int(vehicle_id),))
            vehicle = c.fetchone()
            if vehicle:
                deleted_data.append(vehicle)
        
        # Store in session for undo with timestamp
        session['deleted_vehicles'] = deleted_data
        session['delete_timestamp'] = datetime.now().timestamp()
        session['show_undo'] = True
        
        # Delete vehicles
        deleted_count = 0
        for vehicle_id in vehicle_ids:
            c.execute("DELETE FROM vehicles WHERE id=?", (int(vehicle_id),))
            deleted_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"{deleted_count} vehicles deleted by {session.get('emp_no')}: IDs {vehicle_ids}")
        flash(f"🗑️ {deleted_count} vehicle(s) deleted successfully", "success")
        
        # Return to current region view
        return redirect_to_current_region()
        
    except sqlite3.Error as e:
        logger.error(f"Error deleting vehicles: {e}")
        flash("⚠️ Error deleting vehicles", "danger")
        if 'conn' in locals():
            conn.close()
        return redirect_to_current_region()


# =========================
# undo delete vehicles
# =========================
@app.route("/undo_delete_vehicles", methods=["POST"])
@login_required
def undo_delete_vehicles():
    deleted_vehicles = session.get('deleted_vehicles', [])
    
    if not deleted_vehicles:
        flash("⚠️ No delete operation to undo", "warning")
        return redirect(url_for("home"))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        restored_count = 0
        for vehicle in deleted_vehicles:
            # Insert back the deleted vehicle with all its data
            placeholders = ','.join(['?'] * len(vehicle))
            columns = ','.join([
                'id', 'plate_number', 'vehicle_brand', 'model_year', 'vehicle_type',
                'vehicle_color', 'vehicle_status', 'vehicle_supplier', 'district',
                'emp_no', 'emp_name', 'iqama_no', 'mobile', 'birth_date',
                'handover_pdf', 'driver_id_pdf', 'project', 'remarks', 'tamm_status', 'region'
            ])
            c.execute(f"INSERT INTO vehicles ({columns}) VALUES ({placeholders})", vehicle)
            restored_count += 1
        
        conn.commit()
        logger.info(f"{restored_count} vehicles restored by {session.get('emp_no')}")
        
        # Clear the session data including undo flag
        session.pop('deleted_vehicles', None)
        session.pop('delete_timestamp', None)
        session.pop('show_undo', None)
        
        flash(f"↩️ {restored_count} vehicle(s) restored successfully", "success")
    except sqlite3.Error as e:
        logger.error(f"Error restoring vehicles: {e}")
        flash("⚠️ Error restoring vehicles", "danger")
    finally:
        if 'conn' in locals():
            conn.close()
    
    # Return to current region view
    return redirect_to_current_region()


# =========================

# =========================
# IMPORT EXCEL (ADMIN ONLY, PER REGION)
# =========================
@app.route("/import_excel", methods=["POST"])
@admin_only
def import_excel():
    target_region = (request.form.get("region_name") or "").strip()
    if not target_region or target_region == "ALL":
        flash("⚠️ Please select a specific region before import.", "warning")
        return redirect(url_for("home"))

    if "excel_file" not in request.files:
        flash("⚠️ No file selected", "warning")
        return redirect(url_for("home"))
    
    file = request.files["excel_file"]
    is_valid, message = validate_file(file)
    if not is_valid:
        flash(f"⚠️ {message}", "danger")
        return redirect(url_for("home"))

    try:
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
            
            # Check if plate_number exists
            plate = row_dict.get('plate_number', '')
            if plate:
                c.execute("SELECT id FROM vehicles WHERE plate_number=?", (plate,))
                existing = c.fetchone()
                if existing:
                    # Update existing record
                    update_parts = [f"{col}=?" for col in insert_cols if col != 'plate_number']
                    update_values = [v for col, v in zip(insert_cols, values) if col != 'plate_number']
                    update_values.append(plate)  # for WHERE clause
                    c.execute(f"UPDATE vehicles SET {','.join(update_parts)} WHERE plate_number=?", update_values)
                else:
                    # Insert new record
                    c.execute(f"INSERT INTO vehicles ({cols_sql}) VALUES ({placeholders})", values)
                inserted += 1
            else:
                # No plate number, insert anyway
                c.execute(f"INSERT INTO vehicles ({cols_sql}) VALUES ({placeholders})", values)
                inserted += 1

        conn.commit()
        logger.info(f"{inserted} records imported to {target_region} by {session.get('emp_no')}")
        flash(f"✅ Excel imported successfully ({inserted} records) for {target_region}", "success")
        
        # Clean up uploaded file
        os.remove(filepath)
        
    except Exception as e:
        logger.error(f"Error importing Excel for {target_region}: {e}")
        flash(f"⚠️ Error importing Excel: {str(e)}", "danger")
        if target_region == "ALL":
            return redirect(url_for("home"))
        else:
            return redirect(url_for("view_region", region_name=target_region))
    finally:
        if 'conn' in locals():
            conn.close()
    
    # Return to the region view after import
    return redirect(url_for("view_region", region_name=target_region))


# =========================
# export excel (per region)
# =========================
@app.route("/export_excel")
@login_required
def export_excel():
    region = request.args.get("region") or session.get("region", "ALL")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        if region == "ALL":
            df = pd.read_sql_query("SELECT * FROM vehicles", conn)
        else:
            df = pd.read_sql_query("SELECT * FROM vehicles WHERE region=?", conn, params=(region,))
        
        export_name = f"vehicles_export_{region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        export_path = os.path.join(UPLOAD_FOLDER, export_name)
        df.to_excel(export_path, index=False)
        
        logger.info(f"Excel exported for {region} by {session.get('emp_no')}")
        return send_from_directory(UPLOAD_FOLDER, export_name, as_attachment=True)
    
    except Exception as e:
        logger.error(f"Error exporting Excel for {region}: {e}")
        flash("⚠️ Error exporting data", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()


# =========================
# old files list
# =========================
@app.route("/old_files/<int:vehicle_id>/<string:file_type>")
@login_required
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
@login_required
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

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        placeholders = ",".join("?" * len(vehicle_ids))
        c.execute(
            f"""SELECT id, plate_number, vehicle_brand, model_year, vehicle_supplier, 
                vehicle_type, vehicle_color, vehicle_status, district, iqama_no, 
                emp_no, emp_name, project, previous_user, tamm_status, remarks,
                handover_pdf, driver_id_pdf, last_modified, region
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
        logger.info(f"Maintenance request created for {len(vehicle_ids)} vehicles by {session.get('emp_no')}")

        request_date = datetime.now().strftime("%Y-%m-%d")
        headers = ["ID", "Plate", "Brand", "Model", "Type", "Employee", "Project", "Region"]
        return render_template(
            "maintenance_view.html",
            vehicles=vehicles,
            headers=headers,
            desc=desc,
            request_date=request_date,
        )
    
    except Exception as e:
        logger.error(f"Error creating maintenance request: {e}")
        flash("⚠️ Error creating maintenance request", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()

# =========================
# TRANSFER TO ANOTHER USER
# =========================
@app.route("/transfer_user/<int:vehicle_id>")
@login_required
def transfer_user_page(vehicle_id):
    """صفحة تحويل سيارة لمستخدم جديد"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
        row = c.fetchone()
        
        if not row:
            flash("⚠️ Vehicle not found", "danger")
            return redirect(url_for("home"))
        
        # Build vehicle dictionary
        columns = ['id', 'plate_number', 'vehicle_brand', 'model_year', 'vehicle_supplier', 
                   'vehicle_type', 'vehicle_color', 'vehicle_status', 'district', 'iqama_no', 
                   'emp_no', 'emp_name', 'project', 'previous_user', 'tamm_status', 'remarks', 
                   'handover_pdf', 'driver_id_pdf', 'last_modified', 'region']
        vehicle = dict(zip(columns, row))
        
        # Get all regions
        c.execute("SELECT DISTINCT region FROM vehicles WHERE region IS NOT NULL ORDER BY region")
        regions_list = [r[0] for r in c.fetchall()]
        
        return render_template("transfer_user.html", vehicle=vehicle, regions=regions_list)
    
    except Exception as e:
        logger.error(f"Error loading transfer page for vehicle {vehicle_id}: {e}")
        flash("⚠️ Error loading transfer page", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()


@app.route("/submit_transfer_user", methods=["POST"])
@login_required
def submit_transfer_user():
    """معالجة نموذج تحويل السيارة"""
    vehicle_id = request.form.get("vehicle_id")
    new_emp_no = request.form.get("emp_no", "").strip()
    new_emp_name = request.form.get("emp_name", "").strip()
    new_iqama_no = request.form.get("iqama_no", "").strip()
    new_mobile = request.form.get("mobile", "").strip()
    new_birth_date = request.form.get("birth_date", "").strip()
    new_region = request.form.get("region", "").strip()
    remarks = request.form.get("remarks", "").strip()
    
    if not vehicle_id or not new_emp_no or not new_emp_name:
        flash("⚠️ Required fields missing", "danger")
        return redirect(url_for("transfer_user_page", vehicle_id=vehicle_id))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get old user info
        c.execute("SELECT emp_no, emp_name, plate_number FROM vehicles WHERE id=?", (vehicle_id,))
        row = c.fetchone()
        if not row:
            flash("⚠️ Vehicle not found", "danger")
            return redirect(url_for("home"))
        
        old_emp_no, old_emp_name, plate_number = row
        previous_user = f"{old_emp_no or 'N/A'} - {old_emp_name or 'N/A'}"
        
        # Create vehicle folder
        vehicle_folder = os.path.join("uploads", str(vehicle_id))
        os.makedirs(vehicle_folder, exist_ok=True)
        
        # Handle file uploads
        id_photo = request.files.get("id_photo")
        license_photo = request.files.get("license_photo")
        handover_doc = request.files.get("handover_document")
        receipt_doc = request.files.get("receipt_document")
        
        saved_files = {}
        for file_obj, field_name in [
            (id_photo, "id_photo"),
            (license_photo, "license_photo"),
            (handover_doc, "handover_document"),
            (receipt_doc, "receipt_document")
        ]:
            if file_obj and file_obj.filename:
                if validate_file(file_obj.filename):
                    filename = secure_filename(f"{field_name}_{file_obj.filename}")
                    filepath = os.path.join(vehicle_folder, filename)
                    file_obj.save(filepath)
                    saved_files[field_name] = filepath
                    logger.info(f"Saved {field_name} for vehicle {vehicle_id}: {filename}")
        
        # Update vehicle record
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_query = """
            UPDATE vehicles 
            SET emp_no=?, emp_name=?, iqama_no=?, 
                previous_user=?, region=?, remarks=?, last_modified=?
            WHERE id=?
        """
        c.execute(update_query, (
            new_emp_no, new_emp_name, new_iqama_no,
            previous_user, new_region, remarks, now_str, vehicle_id
        ))
        conn.commit()
        
        logger.info(f"Vehicle {plate_number} (ID:{vehicle_id}) transferred from {old_emp_name} to {new_emp_name} by {session.get('emp_no')}. Files: {list(saved_files.keys())}")
        
        flash(f"✅ Vehicle {plate_number} successfully transferred to {new_emp_name}", "success")
        return redirect(url_for("home"))
    
    except Exception as e:
        logger.error(f"Error submitting transfer for vehicle {vehicle_id}: {e}")
        flash(f"⚠️ Error: {str(e)}", "danger")
        return redirect(url_for("transfer_user_page", vehicle_id=vehicle_id))
    finally:
        if 'conn' in locals():
            conn.close()

# =========================
# BULK TRANSFER & BULK DELETE
# =========================

@app.route("/bulk_transfer", methods=["POST"])
@admin_only
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

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        placeholders = ",".join("?" * len(vehicle_ids))
        c.execute(
            f"UPDATE vehicles SET region=? WHERE id IN ({placeholders})",
            (target_region, *vehicle_ids),
        )
        conn.commit()
        logger.info(f"{len(vehicle_ids)} vehicles transferred to {target_region} by {session.get('emp_no')}")
        flash(f"🚚 {len(vehicle_ids)} vehicle(s) moved to {target_region}.", "success")
    
    except Exception as e:
        logger.error(f"Error transferring vehicles: {e}")
        flash("⚠️ Error transferring vehicles", "danger")
        return redirect(url_for("home"))
    finally:
        if 'conn' in locals():
            conn.close()

    # ✅ توجيه مباشر إلى المنطقة الجديدة بعد النقل
    return redirect(url_for("view_region", region_name=target_region))


@app.route("/bulk_delete", methods=["POST"])
@login_required
def bulk_delete():
    ids_json = request.form.get("vehicle_ids")

    try:
        vehicle_ids = json.loads(ids_json)
    except Exception:
        vehicle_ids = []

    if not vehicle_ids:
        flash("⚠️ Please select at least one vehicle to delete.", "danger")
        return redirect(url_for("home"))

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        placeholders = ",".join("?" * len(vehicle_ids))
        c.execute(f"DELETE FROM vehicles WHERE id IN ({placeholders})", vehicle_ids)
        conn.commit()
        logger.info(f"{len(vehicle_ids)} vehicles deleted by {session.get('emp_no')}")
        resequence_ids()
        flash(f"🗑️ {len(vehicle_ids)} vehicle(s) deleted successfully.", "info")
    
    except Exception as e:
        logger.error(f"Error deleting vehicles: {e}")
        flash("⚠️ Error deleting vehicles", "danger")
    finally:
        if 'conn' in locals():
            conn.close()

    return redirect(url_for("home"))

# =========================
# run
# =========================
if __name__ == "__main__":
    # في Production: لا تشغل بـ debug mode
    if IS_PRODUCTION:
        app.run()
    else:
        app.run(debug=True, host='127.0.0.1', port=5000)

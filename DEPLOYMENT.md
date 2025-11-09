# Hoshan Vehicles Management - Deployment Guide for PythonAnywhere

## خطوات النشر على PythonAnywhere

### 1. إنشاء حساب
- اذهب إلى: https://www.pythonanywhere.com
- سجّل حساب جديد (مجاني أو مدفوع)

### 2. رفع المشروع

#### الطريقة الأولى: استخدام Git (الأفضل)
```bash
# في PythonAnywhere Bash Console:
cd ~
git clone https://github.com/eltayep2/hoshan-vehicles.git project-vehicles-management
cd project-vehicles-management
```

#### الطريقة الثانية: رفع الملفات يدوياً
- اذهب إلى Files → Upload files
- ارفع جميع الملفات (app.py, templates/, static/, database/, requirements.txt)

### 3. إنشاء Virtual Environment
```bash
cd ~/project-vehicles-management
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. إعداد قاعدة البيانات
```bash
# تأكد من وجود مجلد database
mkdir -p database

# إذا لديك ملف vehicles.db موجود:
# ارفعه إلى مجلد database/

# أو قم بإنشاء قاعدة بيانات جديدة:
python3
>>> from app import init_db
>>> init_db()
>>> exit()
```

### 5. إعداد Web App

#### أ. إنشاء Web App
1. اذهب إلى: Web → Add a new web app
2. اختر: Manual configuration
3. اختر: Python 3.10

#### ب. ضبط WSGI Configuration File
1. في صفحة Web، اضغط على WSGI configuration file
2. احذف المحتوى القديم واستبدله بـ:

```python
import sys
import os

# !!! IMPORTANT: غيّر YOUR_USERNAME باسم المستخدم الخاص بك !!!
project_home = '/home/YOUR_USERNAME/project-vehicles-management'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Activate virtualenv
activate_this = '/home/YOUR_USERNAME/project-vehicles-management/venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Set production environment
os.environ['FLASK_ENV'] = 'production'

# Import Flask app
from app import app as application
```

#### ج. ضبط Virtualenv
1. في صفحة Web، ابحث عن: Virtualenv
2. أدخل المسار: `/home/YOUR_USERNAME/project-vehicles-management/venv`

#### د. ضبط Static Files
1. في صفحة Web، ابحث عن: Static files
2. أضف:
   - URL: `/static/`
   - Directory: `/home/YOUR_USERNAME/project-vehicles-management/static/`

### 6. تعديل app.py للإنتاج (Production)

أضف هذا الكود في بداية app.py:

```python
import os

# Production mode detection
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

# Secret key for production
if IS_PRODUCTION:
    app.config['SECRET_KEY'] = 'YOUR_STRONG_SECRET_KEY_HERE_CHANGE_THIS'
else:
    app.config['SECRET_KEY'] = 'dev-secret-key'

# Database path
if IS_PRODUCTION:
    DB_PATH = '/home/YOUR_USERNAME/project-vehicles-management/database/vehicles.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "database", "vehicles.db")
```

### 7. إعادة تشغيل التطبيق
1. في صفحة Web، اضغط على الزر الأخضر: **Reload**

### 8. اختبار التطبيق
- افتح الرابط: `https://YOUR_USERNAME.pythonanywhere.com`

## أمور مهمة للإنتاج (Production)

### 1. تغيير SECRET_KEY
```python
# استخدم مفتاح قوي وفريد
import secrets
print(secrets.token_hex(32))  # انسخ النتيجة واستخدمها
```

### 2. تعطيل Debug Mode
```python
# في app.py تأكد من:
if __name__ == "__main__":
    if IS_PRODUCTION:
        app.run()  # بدون debug=True
    else:
        app.run(debug=True)
```

### 3. صلاحيات قاعدة البيانات
```bash
chmod 664 database/vehicles.db
chmod 775 database/
```

### 4. رفع الملفات (uploads/)
```bash
mkdir -p uploads
chmod 775 uploads/
```

## مشاكل شائعة وحلولها

### مشكلة 1: 502 Bad Gateway
- **الحل:** تحقق من WSGI configuration file
- تأكد من تغيير YOUR_USERNAME

### مشكلة 2: Static Files لا تعمل
- **الحل:** تحقق من Static files mapping في Web tab
- تأكد من المسارات صحيحة

### مشكلة 3: Database locked
- **الحل:** أغلق جميع الاتصالات بقاعدة البيانات
```python
conn.close()  # تأكد من إغلاق الاتصال بعد كل عملية
```

### مشكلة 4: Import Error
- **الحل:** تأكد من تثبيت جميع المكتبات:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## نصائح للأداء

1. **تفعيل Always On** (في الحسابات المدفوعة)
2. **استخدام MySQL بدلاً من SQLite** (للمشاريع الكبيرة)
3. **تفعيل HTTPS** (مدمج في PythonAnywhere)
4. **Backup منتظم** للـ database

## روابط مفيدة

- Documentation: https://help.pythonanywhere.com/pages/Flask/
- Dashboard: https://www.pythonanywhere.com/user/YOUR_USERNAME/
- Error Logs: في صفحة Web → Log files

---

**ملاحظة:** غيّر `YOUR_USERNAME` باسم المستخدم الخاص بك في جميع الأماكن!

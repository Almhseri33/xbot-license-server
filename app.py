#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
License Server - السيرفر الرئيسي
================================
"""

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
import os
import json
import base64
from datetime import datetime, timedelta
from functools import wraps
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


# ============================================================
# نظام التشفير (Inlined - Complete Version)
# ============================================================

class DataEncryption:
    """تشفير البيانات بـ AES-256"""
    
    def __init__(self, master_key=None):
        """
        master_key: المفتاح الأساسي (32 byte)
        إذا لم يتم تحديده، سيتم استخدام المفتاح الافتراضي
        """
        if master_key is None:
            # المفتاح الافتراضي - يجب تغييره في الإنتاج!
            master_key = b"XBotManager2026SecretKey!@#$"
        
        # توليد مفتاح Fernet من المفتاح الأساسي
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"x_bot_salt_2026",
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key))
        self.cipher = Fernet(key)
    
    def encrypt_data(self, data):
        """
        تشفير البيانات
        
        Args:
            data: dict أو list - البيانات المراد تشفيرها
        
        Returns:
            str: النص المشفر (base64)
        """
        try:
            # تحويل البيانات إلى JSON
            json_data = json.dumps(data, ensure_ascii=False)
            
            # تشفير
            encrypted = self.cipher.encrypt(json_data.encode('utf-8'))
            
            # تحويل إلى base64 لسهولة النقل
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            raise Exception(f"فشل التشفير: {e}")
    
    def decrypt_data(self, encrypted_data):
        """
        فك تشفير البيانات
        
        Args:
            encrypted_data: str - النص المشفر (base64)
        
        Returns:
            dict أو list: البيانات الأصلية
        """
        try:
            # فك base64
            encrypted = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # فك التشفير
            decrypted = self.cipher.decrypt(encrypted)
            
            # تحويل من JSON
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            raise Exception(f"فشل فك التشفير: {e}")
    
    def encrypt_accounts(self, accounts):
        """
        تشفير قائمة الحسابات بشكل خاص
        (يزيل معلومات حساسة غير ضرورية)
        
        Args:
            accounts: list - قائمة الحسابات من accounts.json
        
        Returns:
            str: البيانات المشفرة
        """
        # استخراج المعلومات المهمة فقط
        clean_accounts = []
        for acc in accounts:
            clean_accounts.append({
                'id': acc.get('id', ''),
                'name': acc.get('name', ''),
                'username': acc.get('username', ''),
                'password': acc.get('password', ''),  # 🔥 المهم!
                'profile': acc.get('profile', ''),
                'bot_mode': acc.get('bot_mode', 'exchange'),
                'default_tweet': acc.get('default_tweet', '')
            })
        
        return self.encrypt_data(clean_accounts)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # مفتاح سري للـ sessions
CORS(app)

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found', 'message': str(e)}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Server error', 'message': str(e)}), 500

# إعدادات
DATABASE = 'license_server.db'
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = hashlib.sha256('admin123'.encode()).hexdigest()  # غيّر كلمة السر!
ENCRYPTION = DataEncryption()

# إعدادات GitHub للحظر
GITHUB_USERNAME = 'Almhseri33'
GITHUB_REPO = 'xbot-license-server'
GITHUB_TOKEN = ''  # سيتم تحميله من ملف أو متغيرات البيئة


# ============================================================
# قاعدة البيانات
# ============================================================

def init_db():
    """إنشاء قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # جدول التراخيص
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            hardware_id TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            activated_at TEXT,
            last_verified TEXT,
            max_activations INTEGER DEFAULT 1,
            current_activations INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')
    
    # جدول البيانات المزامنة
    c.execute('''
        CREATE TABLE IF NOT EXISTS synced_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            hardware_id TEXT NOT NULL,
            encrypted_data TEXT NOT NULL,
            accounts_count INTEGER,
            synced_at TEXT,
            FOREIGN KEY (license_key) REFERENCES licenses(license_key)
        )
    ''')
    
    # جدول سجل العمليات
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            action TEXT,
            ip_address TEXT,
            timestamp TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")


def get_db():
    """الاتصال بقاعدة البيانات"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def log_activity(license_key, action, ip_address, details=''):
    """تسجيل نشاط"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO activity_log (license_key, action, ip_address, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (license_key, action, ip_address, datetime.now().isoformat(), details))
        conn.commit()
        conn.close()
    except:
        pass


# ============================================================
# Admin Authentication
# ============================================================

def admin_required(f):
    """Decorator للصفحات التي تحتاج تسجيل دخول"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """صفحة تسجيل دخول الأدمن"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
            session['admin_logged_in'] = True
            log_activity('ADMIN', 'login', request.remote_addr, 'Admin logged in')
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials")
    
    return render_template_string(LOGIN_TEMPLATE)


@app.route('/admin/logout')
def admin_logout():
    """تسجيل خروج"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ============================================================
# API Endpoints
# ============================================================

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return jsonify({
        'service': 'X Bot Manager License Server',
        'version': '1.0.0',
        'status': 'online'
    })


@app.before_request
def log_request():
    """تسجيل كل الطلبات"""
    print(f"[REQUEST] {request.method} {request.path} from {request.remote_addr}")
    if request.is_json:
        print(f"[REQUEST DATA] {request.get_json()}")


@app.route('/api/license/activate', methods=['POST'])
def activate_license():
    """تفعيل ترخيص"""
    try:
        data = request.get_json()
        print(f"[DEBUG] Activate request: {data}")
        
        license_key = data.get('license_key')
        hardware_id = data.get('hardware_id')
        ip_address = request.remote_addr
        
        if not license_key or not hardware_id:
            print(f"[DEBUG] Missing fields: license_key={license_key}, hardware_id={hardware_id}")
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    except Exception as e:
        print(f"[ERROR] Exception in activate: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
    conn = get_db()
    c = conn.cursor()
    
    # البحث عن الترخيص
    c.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license_row = c.fetchone()
    
    if not license_row:
        log_activity(license_key, 'activate_failed', ip_address, 'License not found')
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid license key'})
    
    license_dict = dict(license_row)
    
    # التحقق من الحالة
    if license_dict['status'] != 'active':
        log_activity(license_key, 'activate_failed', ip_address, f"License status: {license_dict['status']}")
        conn.close()
        return jsonify({'success': False, 'message': f"License is {license_dict['status']}"})
    
    # التحقق من عدد التفعيلات
    if license_dict['hardware_id'] and license_dict['hardware_id'] != hardware_id:
        # الترخيص مفعل على جهاز آخر
        if license_dict['current_activations'] >= license_dict['max_activations']:
            log_activity(license_key, 'activate_failed', ip_address, 'Max activations reached')
            conn.close()
            return jsonify({
                'success': False,
                'message': 'License already activated on another device. Contact support.'
            })
    
    # تفعيل الترخيص
    c.execute('''
        UPDATE licenses
        SET hardware_id = ?, activated_at = ?, last_verified = ?, current_activations = 1
        WHERE license_key = ?
    ''', (hardware_id, datetime.now().isoformat(), datetime.now().isoformat(), license_key))
    
    conn.commit()
    conn.close()
    
    log_activity(license_key, 'activate_success', ip_address, f'HW: {hardware_id[:16]}...')
    
    return jsonify({
        'success': True,
        'message': 'License activated successfully',
        'data': {
            'license_key': license_key,
            'activated_at': datetime.now().isoformat()
        }
    })


@app.route('/api/license/verify', methods=['POST'])
def verify_license():
    """التحقق من صلاحية الترخيص"""
    data = request.get_json()
    
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    ip_address = request.remote_addr
    
    if not license_key or not hardware_id:
        return jsonify({'valid': False, 'message': 'Missing required fields'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license_row = c.fetchone()
    
    if not license_row:
        log_activity(license_key, 'verify_failed', ip_address, 'License not found')
        conn.close()
        return jsonify({'valid': False, 'message': 'Invalid license'})
    
    license_dict = dict(license_row)
    
    # التحقق من Hardware ID
    if license_dict['hardware_id'] != hardware_id:
        log_activity(license_key, 'verify_failed', ip_address, 'Hardware ID mismatch')
        conn.close()
        return jsonify({'valid': False, 'message': 'License not registered for this device'})
    
    # التحقق من الحالة
    if license_dict['status'] != 'active':
        log_activity(license_key, 'verify_failed', ip_address, f"Status: {license_dict['status']}")
        conn.close()
        return jsonify({'valid': False, 'message': f"License is {license_dict['status']}"})
    
    # تحديث آخر تحقق
    c.execute('''
        UPDATE licenses
        SET last_verified = ?
        WHERE license_key = ?
    ''', (datetime.now().isoformat(), license_key))
    
    conn.commit()
    conn.close()
    
    log_activity(license_key, 'verify_success', ip_address, '')
    
    return jsonify({
        'valid': True,
        'message': 'License is valid',
        'data': {
            'license_key': license_key,
            'status': 'active'
        }
    })


@app.route('/api/license/deactivate', methods=['POST'])
def deactivate_license():
    """إلغاء تفعيل الترخيص"""
    data = request.get_json()
    
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    ip_address = request.remote_addr
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        UPDATE licenses
        SET hardware_id = NULL, current_activations = 0
        WHERE license_key = ? AND hardware_id = ?
    ''', (license_key, hardware_id))
    
    conn.commit()
    conn.close()
    
    log_activity(license_key, 'deactivate', ip_address, f'HW: {hardware_id[:16]}...')
    
    return jsonify({'success': True, 'message': 'License deactivated'})


@app.route('/api/sync', methods=['POST'])
def sync_data():
    """مزامنة البيانات المشفرة"""
    data = request.get_json()
    
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    encrypted_data = data.get('data')
    accounts_count = data.get('accounts_count', 0)
    ip_address = request.remote_addr
    
    if not all([license_key, hardware_id, encrypted_data]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # التحقق من الترخيص أولاً
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM licenses WHERE license_key = ? AND hardware_id = ? AND status = ?',
              (license_key, hardware_id, 'active'))
    license_row = c.fetchone()
    
    if not license_row:
        conn.close()
        log_activity(license_key, 'sync_failed', ip_address, 'Invalid license')
        return jsonify({'success': False, 'message': 'Invalid license or not activated'}), 403
    
    # حفظ البيانات المشفرة
    try:
        c.execute('''
            INSERT INTO synced_data (license_key, hardware_id, encrypted_data, accounts_count, synced_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (license_key, hardware_id, encrypted_data, accounts_count, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        log_activity(license_key, 'sync_success', ip_address, f'{accounts_count} accounts')
        
        return jsonify({
            'success': True,
            'message': 'Data synced successfully',
            'synced_at': datetime.now().isoformat()
        })
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Sync failed: {str(e)}'}), 500


# ============================================================
# Admin Dashboard
# ============================================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """لوحة تحكم الأدمن"""
    conn = get_db()
    c = conn.cursor()
    
    # إحصائيات
    c.execute('SELECT COUNT(*) FROM licenses')
    total_licenses = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
    active_licenses = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM synced_data')
    total_syncs = c.fetchone()[0]
    
    # آخر المزامنات
    c.execute('''
        SELECT sd.license_key, sd.hardware_id, sd.accounts_count, sd.synced_at
        FROM synced_data sd
        ORDER BY sd.synced_at DESC
        LIMIT 10
    ''')
    recent_syncs = c.fetchall()
    
    # قائمة التراخيص
    c.execute('SELECT * FROM licenses ORDER BY created_at DESC')
    licenses = c.fetchall()
    
    conn.close()
    
    # جلب القائمة السوداء
    blacklist = get_blacklist_from_github()
    blocked_ids = blacklist.get("blocked_hardware_ids", [])
    
    # إضافة معلومة الحظر لكل ترخيص
    licenses_with_block_info = []
    for license in licenses:
        license_dict = dict(license)
        license_dict['is_blocked'] = license_dict.get('hardware_id') in blocked_ids
        licenses_with_block_info.append(license_dict)
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        total_syncs=total_syncs,
        recent_syncs=recent_syncs,
        licenses=licenses_with_block_info
    )


@app.route('/admin/view_data/<license_key>')
@admin_required
def view_user_data(license_key):
    """عرض بيانات مستخدم معين (مفككة التشفير!)"""
    conn = get_db()
    c = conn.cursor()
    
    # جلب آخر مزامنة
    c.execute('''
        SELECT * FROM synced_data
        WHERE license_key = ?
        ORDER BY synced_at DESC
        LIMIT 1
    ''', (license_key,))
    
    sync_row = c.fetchone()
    conn.close()
    
    if not sync_row:
        return f"<h3>No data found for license: {license_key}</h3>"
    
    sync_dict = dict(sync_row)
    
    # فك التشفير!
    try:
        decrypted_accounts = ENCRYPTION.decrypt_data(sync_dict['encrypted_data'])
    except Exception as e:
        return f"<h3>Error decrypting data: {e}</h3>"
    
    return render_template_string(
        VIEW_DATA_TEMPLATE,
        license_key=license_key,
        hardware_id=sync_dict['hardware_id'],
        synced_at=sync_dict['synced_at'],
        accounts=decrypted_accounts
    )


@app.route('/admin/create_license', methods=['POST'])
@admin_required
def create_license():
    """إنشاء ترخيص جديد"""
    # توليد مفتاح ترخيص عشوائي
    license_key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    
    conn = get_db()
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT INTO licenses (license_key, status, created_at, max_activations, current_activations)
            VALUES (?, ?, ?, ?, ?)
        ''', (license_key, 'active', datetime.now().isoformat(), 1, 0))
        
        conn.commit()
        conn.close()
        
        log_activity(license_key, 'created', request.remote_addr, 'New license created')
        
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        conn.close()
        return f"Error creating license: {e}"


# ============================================================
# نظام الحظر (Kill Switch Integration)
# ============================================================

def load_github_token():
    """تحميل GitHub Token من ملف أو متغيرات البيئة"""
    global GITHUB_TOKEN
    
    # محاولة من متغيرات البيئة
    if os.environ.get('GITHUB_TOKEN'):
        GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
        return True
    
    # محاولة من ملف
    token_file = 'github_token.txt'
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                GITHUB_TOKEN = f.read().strip()
            return True
        except:
            pass
    
    return False


def get_blacklist_from_github():
    """جلب blacklist.json من GitHub"""
    try:
        import requests
        
        url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/blacklist.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"blocked_hardware_ids": [], "last_updated": "", "notes": ""}
    except Exception as e:
        print(f"Error fetching blacklist: {e}")
        return {"blocked_hardware_ids": [], "last_updated": "", "notes": ""}


def update_blacklist_on_github(blacklist_data):
    """تحديث blacklist.json على GitHub"""
    try:
        import requests
        
        if not GITHUB_TOKEN:
            raise Exception("GitHub Token not configured")
        
        # رابط API
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/blacklist.json"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # جلب SHA الحالي
        response = requests.get(api_url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]
        
        # تحويل المحتوى لـ base64
        content = json.dumps(blacklist_data, indent=2, ensure_ascii=False)
        content_bytes = content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')
        
        # تحديث الملف
        data = {
            "message": f"Update blacklist - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content_base64,
        }
        
        if sha:
            data["sha"] = sha
        
        response = requests.put(api_url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            return True
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    except Exception as e:
        print(f"Error updating blacklist: {e}")
        return False


def is_hardware_blocked(hardware_id):
    """التحقق إذا Hardware ID محظور"""
    blacklist = get_blacklist_from_github()
    return hardware_id in blacklist.get("blocked_hardware_ids", [])


@app.route('/admin/block_user/<license_key>', methods=['POST'])
@admin_required
def block_user(license_key):
    """حظر مستخدم"""
    try:
        # جلب Hardware ID من قاعدة البيانات
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT hardware_id FROM licenses WHERE license_key = ?', (license_key,))
        result = c.fetchone()
        conn.close()
        
        if not result or not result['hardware_id']:
            return jsonify({
                'success': False,
                'message': 'Hardware ID not found. User must activate license first.'
            }), 400
        
        hardware_id = result['hardware_id']
        
        # جلب القائمة الحالية
        blacklist = get_blacklist_from_github()
        blocked_ids = blacklist.get("blocked_hardware_ids", [])
        
        # التحقق إذا محظور مسبقاً
        if hardware_id in blocked_ids:
            return jsonify({
                'success': False,
                'message': 'User already blocked'
            }), 400
        
        # إضافة للقائمة
        blocked_ids.append(hardware_id)
        blacklist["blocked_hardware_ids"] = blocked_ids
        blacklist["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # رفع لـ GitHub
        if update_blacklist_on_github(blacklist):
            log_activity(license_key, 'blocked', request.remote_addr, f'HW: {hardware_id[:16]}...')
            return jsonify({
                'success': True,
                'message': 'User blocked successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update blacklist on GitHub'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/admin/unblock_user/<license_key>', methods=['POST'])
@admin_required
def unblock_user(license_key):
    """رفع الحظر عن مستخدم"""
    try:
        # جلب Hardware ID
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT hardware_id FROM licenses WHERE license_key = ?', (license_key,))
        result = c.fetchone()
        conn.close()
        
        if not result or not result['hardware_id']:
            return jsonify({
                'success': False,
                'message': 'Hardware ID not found'
            }), 400
        
        hardware_id = result['hardware_id']
        
        # جلب القائمة
        blacklist = get_blacklist_from_github()
        blocked_ids = blacklist.get("blocked_hardware_ids", [])
        
        # التحقق إذا محظور
        if hardware_id not in blocked_ids:
            return jsonify({
                'success': False,
                'message': 'User is not blocked'
            }), 400
        
        # حذف من القائمة
        blocked_ids.remove(hardware_id)
        blacklist["blocked_hardware_ids"] = blocked_ids
        blacklist["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # رفع لـ GitHub
        if update_blacklist_on_github(blacklist):
            log_activity(license_key, 'unblocked', request.remote_addr, f'HW: {hardware_id[:16]}...')
            return jsonify({
                'success': True,
                'message': 'User unblocked successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update blacklist on GitHub'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/admin/blacklist')
@admin_required
def view_blacklist():
    """عرض القائمة السوداء"""
    blacklist = get_blacklist_from_github()
    blocked_ids = blacklist.get("blocked_hardware_ids", [])
    last_updated = blacklist.get("last_updated", "N/A")
    
    # جلب معلومات المستخدمين المحظورين
    conn = get_db()
    c = conn.cursor()
    
    blocked_users = []
    for hw_id in blocked_ids:
        c.execute('SELECT * FROM licenses WHERE hardware_id = ?', (hw_id,))
        result = c.fetchone()
        if result:
            blocked_users.append(dict(result))
    
    conn.close()
    
    return render_template_string(
        BLACKLIST_TEMPLATE,
        blocked_count=len(blocked_ids),
        last_updated=last_updated,
        blocked_users=blocked_users,
        blocked_ids=blocked_ids
    )


# ============================================================
# HTML Templates
# ============================================================

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body { font-family: Arial; background: #1a1a1a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #2b2b2b; padding: 40px; border-radius: 10px; width: 350px; }
        h2 { margin-top: 0; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #444; background: #1a1a1a; color: #fff; border-radius: 5px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #4CAF50; border: none; color: #fff; font-size: 16px; font-weight: bold; border-radius: 5px; cursor: pointer; }
        button:hover { background: #45a049; }
        .error { color: #f44336; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔐 Admin Login</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        {% if error %}
        <p class="error">❌ {{ error }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
        h1 { margin-top: 0; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: #2b2b2b; padding: 20px; border-radius: 10px; flex: 1; }
        .stat-box h3 { margin: 0 0 10px 0; color: #64B5F6; }
        .stat-box .number { font-size: 36px; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; background: #2b2b2b; border-radius: 10px; overflow: hidden; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #1a1a1a; font-weight: bold; }
        .btn { padding: 8px 16px; background: #4CAF50; border: none; color: #fff; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; }
        .btn:hover { background: #45a049; }
        .btn-danger { background: #f44336; }
        .btn-danger:hover { background: #da190b; }
        .btn-info { background: #2196F3; }
        .btn-info:hover { background: #1976D2; }
        .btn-warning { background: #ff9800; }
        .btn-warning:hover { background: #e68900; }
        .btn-success { background: #4CAF50; }
        .btn-success:hover { background: #45a049; }
        .logout { float: right; }
        .status-badge { padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .status-active { background: #4CAF50; }
        .status-blocked { background: #f44336; }
        .status-inactive { background: #666; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    </style>
    <script>
        function blockUser(licenseKey) {
            if (!confirm('هل أنت متأكد من حظر هذا المستخدم؟\\n\\nلن يتمكن من استخدام البرنامج بعد الآن.')) {
                return;
            }
            
            fetch('/admin/block_user/' + licenseKey, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ ' + data.message);
                    location.reload();
                } else {
                    alert('❌ ' + data.message);
                }
            })
            .catch(error => {
                alert('❌ خطأ: ' + error);
            });
        }
        
        function unblockUser(licenseKey) {
            if (!confirm('هل تريد رفع الحظر عن هذا المستخدم؟')) {
                return;
            }
            
            fetch('/admin/unblock_user/' + licenseKey, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ ' + data.message);
                    location.reload();
                } else {
                    alert('❌ ' + data.message);
                }
            })
            .catch(error => {
                alert('❌ خطأ: ' + error);
            });
        }
    </script>
</head>
<body>
    <div class="top-bar">
        <h1>📊 Admin Dashboard</h1>
        <div>
            <a href="/admin/blacklist" class="btn btn-warning">🔒 القائمة السوداء</a>
            <a href="/admin/logout" class="btn btn-danger">Logout</a>
        </div>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>Total Licenses</h3>
            <div class="number">{{ total_licenses }}</div>
        </div>
        <div class="stat-box">
            <h3>Active Licenses</h3>
            <div class="number">{{ active_licenses }}</div>
        </div>
        <div class="stat-box">
            <h3>Total Syncs</h3>
            <div class="number">{{ total_syncs }}</div>
        </div>
    </div>
    
    <form method="POST" action="/admin/create_license">
        <button type="submit" class="btn">➕ Create New License</button>
    </form>
    
    <h2>📋 Licenses</h2>
    <table>
        <tr>
            <th>License Key</th>
            <th>Status</th>
            <th>Hardware ID</th>
            <th>Activated</th>
            <th>Last Verified</th>
            <th>Actions</th>
        </tr>
        {% for license in licenses %}
        <tr>
            <td><code>{{ license['license_key'] }}</code></td>
            <td>
                {% if license['is_blocked'] %}
                    <span class="status-badge status-blocked">🔒 BLOCKED</span>
                {% elif license['status'] == 'active' %}
                    <span class="status-badge status-active">✅ ACTIVE</span>
                {% else %}
                    <span class="status-badge status-inactive">{{ license['status'] }}</span>
                {% endif %}
            </td>
            <td><code>{{ license['hardware_id'][:16] if license['hardware_id'] else 'N/A' }}...</code></td>
            <td>{{ license['activated_at'] or 'N/A' }}</td>
            <td>{{ license['last_verified'] or 'N/A' }}</td>
            <td>
                <a href="/admin/view_data/{{ license['license_key'] }}" class="btn btn-info">👁️ View</a>
                {% if license['hardware_id'] %}
                    {% if license['is_blocked'] %}
                        <button onclick="unblockUser('{{ license['license_key'] }}')" class="btn btn-success">✅ Unblock</button>
                    {% else %}
                        <button onclick="blockUser('{{ license['license_key'] }}')" class="btn btn-danger">🔒 Block</button>
                    {% endif %}
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

VIEW_DATA_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>User Data</title>
    <style>
        body { font-family: Arial; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
        h1 { margin-top: 0; }
        .info-box { background: #2b2b2b; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .account-card { background: #2b2b2b; padding: 20px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #4CAF50; }
        .account-card h3 { margin-top: 0; color: #4CAF50; }
        .field { margin: 10px 0; }
        .label { color: #64B5F6; font-weight: bold; }
        .value { font-family: monospace; color: #fff; }
        .btn { padding: 10px 20px; background: #2196F3; border: none; color: #fff; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn:hover { background: #1976D2; }
    </style>
</head>
<body>
    <h1>👤 User Data</h1>
    <a href="/admin/dashboard" class="btn">← Back to Dashboard</a>
    
    <div class="info-box">
        <div class="field">
            <span class="label">🔑 License Key:</span>
            <span class="value">{{ license_key }}</span>
        </div>
        <div class="field">
            <span class="label">🆔 Hardware ID:</span>
            <span class="value">{{ hardware_id }}</span>
        </div>
        <div class="field">
            <span class="label">📅 Last Sync:</span>
            <span class="value">{{ synced_at }}</span>
        </div>
        <div class="field">
            <span class="label">📊 Accounts:</span>
            <span class="value">{{ accounts|length }}</span>
        </div>
    </div>
    
    <h2>🔓 Decrypted Accounts Data</h2>
    {% for account in accounts %}
    <div class="account-card">
        <h3>Account #{{ account['id'] }}: {{ account['name'] }}</h3>
        <div class="field">
            <span class="label">👤 Username:</span>
            <span class="value">@{{ account['username'] }}</span>
        </div>
        <div class="field">
            <span class="label">🔒 Password:</span>
            <span class="value">{{ account['password'] }}</span>
        </div>
        <div class="field">
            <span class="label">📂 Profile:</span>
            <span class="value">{{ account['profile'] }}</span>
        </div>
        <div class="field">
            <span class="label">🤖 Bot Mode:</span>
            <span class="value">{{ account['bot_mode'] }}</span>
        </div>
        <div class="field">
            <span class="label">🔗 Default Tweet:</span>
            <span class="value">{{ account['default_tweet'] }}</span>
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""

BLACKLIST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Blacklist Management</title>
    <style>
        body { font-family: Arial; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
        h1 { margin-top: 0; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: #2b2b2b; padding: 20px; border-radius: 10px; flex: 1; }
        .stat-box h3 { margin: 0 0 10px 0; color: #f44336; }
        .stat-box .number { font-size: 36px; font-weight: bold; color: #f44336; }
        table { width: 100%; border-collapse: collapse; background: #2b2b2b; border-radius: 10px; overflow: hidden; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #1a1a1a; font-weight: bold; }
        .btn { padding: 10px 20px; background: #2196F3; border: none; color: #fff; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; }
        .btn:hover { background: #1976D2; }
        .btn-success { background: #4CAF50; }
        .btn-success:hover { background: #45a049; }
        .blocked-badge { background: #f44336; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .empty-message { text-align: center; padding: 40px; color: #666; }
    </style>
    <script>
        function unblockUser(licenseKey) {
            if (!confirm('هل تريد رفع الحظر عن هذا المستخدم؟')) {
                return;
            }
            
            fetch('/admin/unblock_user/' + licenseKey, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ ' + data.message);
                    location.reload();
                } else {
                    alert('❌ ' + data.message);
                }
            })
            .catch(error => {
                alert('❌ خطأ: ' + error);
            });
        }
    </script>
</head>
<body>
    <div class="top-bar">
        <h1>🔒 Blacklist Management</h1>
        <a href="/admin/dashboard" class="btn">← Back to Dashboard</a>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>Blocked Users</h3>
            <div class="number">{{ blocked_count }}</div>
        </div>
        <div class="stat-box">
            <h3>Last Updated</h3>
            <div class="number" style="font-size: 18px;">{{ last_updated }}</div>
        </div>
    </div>
    
    {% if blocked_users %}
    <h2>📋 Blocked Users</h2>
    <table>
        <tr>
            <th>License Key</th>
            <th>Hardware ID</th>
            <th>Status</th>
            <th>Activated</th>
            <th>Actions</th>
        </tr>
        {% for user in blocked_users %}
        <tr>
            <td><code>{{ user['license_key'] }}</code></td>
            <td><code>{{ user['hardware_id'][:16] }}...</code></td>
            <td><span class="blocked-badge">🔒 BLOCKED</span></td>
            <td>{{ user['activated_at'] or 'N/A' }}</td>
            <td>
                <a href="/admin/view_data/{{ user['license_key'] }}" class="btn">👁️ View Data</a>
                <button onclick="unblockUser('{{ user['license_key'] }}')" class="btn btn-success">✅ Unblock</button>
            </td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <div class="empty-message">
        <h2>✅ No blocked users</h2>
        <p>القائمة السوداء فارغة - لا يوجد مستخدمين محظورين</p>
    </div>
    {% endif %}
    
    {% if blocked_ids|length > blocked_users|length %}
    <h2>⚠️ Unknown Blocked Hardware IDs</h2>
    <p>هذه Hardware IDs محظورة لكن لا توجد لها تراخيص في قاعدة البيانات:</p>
    <ul>
        {% for hw_id in blocked_ids %}
            {% set found = namespace(value=false) %}
            {% for user in blocked_users %}
                {% if user['hardware_id'] == hw_id %}
                    {% set found.value = true %}
                {% endif %}
            {% endfor %}
            {% if not found.value %}
                <li><code>{{ hw_id }}</code></li>
            {% endif %}
        {% endfor %}
    </ul>
    {% endif %}
</body>
</html>
"""


# ============================================================
# Admin Panel Desktop APIs
# ============================================================

@app.route('/api/admin/add-license', methods=['POST'])
def api_add_license():
    """API لإضافة ترخيص من Admin Panel Desktop"""
    try:
        data = request.get_json()
        
        hardware_id = data.get('hardware_id')
        license_key = data.get('license_key')
        license_type = data.get('type', 'lifetime')
        created_at = data.get('created_at', datetime.now().isoformat())
        
        if not hardware_id or not license_key:
            return jsonify({'error': 'Missing hardware_id or license_key'}), 400
        
        conn = get_db()
        c = conn.cursor()
        
        # التحقق من عدم وجود الترخيص مسبقاً
        c.execute('SELECT id FROM licenses WHERE license_key = ?', (license_key,))
        existing = c.fetchone()
        
        if existing:
            conn.close()
            return jsonify({'error': 'License key already exists'}), 400
        
        # إضافة الترخيص
        c.execute('''
            INSERT INTO licenses 
            (license_key, hardware_id, status, created_at, activated_at, max_activations, current_activations, license_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (license_key, hardware_id, 'active', created_at, datetime.now().isoformat(), 1, 1, license_type))
        
        conn.commit()
        conn.close()
        
        log_activity(license_key, 'created_via_api', request.remote_addr, f'License created from Admin Panel Desktop')
        
        return jsonify({
            'success': True,
            'message': 'License added successfully',
            'license_key': license_key
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/sync-blacklist', methods=['POST'])
def api_sync_blacklist():
    """API لمزامنة القائمة السوداء من Admin Panel Desktop"""
    try:
        data = request.get_json()
        
        blocked_hardware_ids = data.get('blocked_hardware_ids', [])
        last_updated = data.get('last_updated', datetime.now().isoformat())
        
        # حفظ القائمة السوداء محلياً
        blacklist_data = {
            'blocked_hardware_ids': blocked_hardware_ids,
            'last_updated': last_updated,
            'notes': 'Synced from Admin Panel Desktop'
        }
        
        with open('blacklist.json', 'w', encoding='utf-8') as f:
            json.dump(blacklist_data, f, indent=2, ensure_ascii=False)
        
        # رفع إلى GitHub إذا كان متوفراً
        if GITHUB_TOKEN and GITHUB_USERNAME and GITHUB_REPO:
            try:
                update_github_blacklist(blacklist_data)
            except:
                pass  # لا بأس إذا فشل GitHub
        
        return jsonify({
            'success': True,
            'message': 'Blacklist synced successfully',
            'blocked_count': len(blocked_hardware_ids)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/get-users', methods=['GET'])
def api_get_users():
    """API لجلب قائمة جميع المستخدمين"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # أولاً نتحقق من الأعمدة الموجودة
        c.execute("PRAGMA table_info(licenses)")
        columns = [col[1] for col in c.fetchall()]
        
        # نبني قائمة الأعمدة المتوفرة فقط
        available_columns = ['license_key', 'hardware_id', 'status', 'created_at', 'activated_at']
        
        # نتحقق من الأعمدة الاختيارية
        if 'last_seen' in columns:
            available_columns.append('last_seen')
        if 'current_activations' in columns:
            available_columns.append('current_activations')
        if 'license_type' in columns:
            available_columns.append('license_type')
        
        # بناء الاستعلام
        query = f"SELECT {', '.join(available_columns)} FROM licenses ORDER BY created_at DESC"
        c.execute(query)
        
        users = []
        for row in c.fetchall():
            user_data = {
                'license_key': row[0],
                'hardware_id': row[1] or 'Not activated',
                'status': row[2],
                'created_at': row[3],
                'activated_at': row[4],
                'last_seen': row[5] if len(row) > 5 and 'last_seen' in available_columns else 'N/A',
                'current_activations': row[6] if len(row) > 6 and 'current_activations' in available_columns else 1,
                'license_type': row[7] if len(row) > 7 and 'license_type' in available_columns else 'lifetime'
            }
            users.append(user_data)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users,
            'total': len(users)
        }), 200
        
    except Exception as e:
        print(f"Error in get_users: {e}")  # للتشخيص
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/get-user-details/<license_key>', methods=['GET'])
def api_get_user_details(license_key):
    """API لجلب تفاصيل مستخدم معين مع البيانات المفككة"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # التحقق من الأعمدة الموجودة
        c.execute("PRAGMA table_info(licenses)")
        columns = [col[1] for col in c.fetchall()]
        
        # بناء قائمة الأعمدة المتوفرة
        available_columns = ['license_key', 'hardware_id', 'status', 'created_at', 'activated_at', 'encrypted_data']
        
        if 'last_seen' in columns:
            available_columns.append('last_seen')
        if 'max_activations' in columns:
            available_columns.append('max_activations')
        if 'current_activations' in columns:
            available_columns.append('current_activations')
        if 'license_type' in columns:
            available_columns.append('license_type')
        
        query = f"SELECT {', '.join(available_columns)} FROM licenses WHERE license_key = ?"
        c.execute(query, (license_key,))
        
        row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'User not found'}), 404
        
        # فك تشفير البيانات
        encrypted_data = row[5]  # encrypted_data دائماً في موقع 5
        decrypted_accounts = []
        
        if encrypted_data:
            try:
                encryption = DataEncryption()
                decrypted_data = encryption.decrypt_data(encrypted_data)
                
                if 'accounts' in decrypted_data:
                    accounts = decrypted_data['accounts']
                    for acc in accounts:
                        safe_account = {
                            'username': acc.get('username', 'Unknown'),
                            'status': acc.get('status', 'Unknown'),
                            'added_at': acc.get('added_at', 'Unknown')
                        }
                        decrypted_accounts.append(safe_account)
            except:
                pass
        
        # بناء user_details حسب الأعمدة المتوفرة
        idx = 0
        user_details = {
            'license_key': row[idx],
            'hardware_id': row[idx+1] or 'Not activated',
            'status': row[idx+2],
            'created_at': row[idx+3],
            'activated_at': row[idx+4],
            # encrypted_data في idx+5 لكن ما نعرضه
            'last_seen': 'N/A',
            'max_activations': 1,
            'current_activations': 1,
            'license_type': 'lifetime',
            'accounts': decrypted_accounts,
            'total_accounts': len(decrypted_accounts)
        }
        
        # نملأ القيم الموجودة
        current_idx = 6  # بعد encrypted_data
        if 'last_seen' in available_columns:
            user_details['last_seen'] = row[current_idx] or 'N/A'
            current_idx += 1
        if 'max_activations' in available_columns:
            user_details['max_activations'] = row[current_idx] or 1
            current_idx += 1
        if 'current_activations' in available_columns:
            user_details['current_activations'] = row[current_idx] or 1
            current_idx += 1
        if 'license_type' in available_columns:
            user_details['license_type'] = row[current_idx] or 'lifetime'
        
        return jsonify({
            'success': True,
            'user': user_details
        }), 200
        
    except Exception as e:
        print(f"Error in get_user_details: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# تشغيل السيرفر
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("🚀 License Server Starting...")
    print("="*60)


# ============================================================
# تشغيل السيرفر
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("🚀 License Server Starting...")
    print("="*60)
    
    # إنشاء قاعدة البيانات
    init_db()
    
    # تحميل GitHub Token
    if load_github_token():
        print("✅ GitHub Token loaded successfully")
    else:
        print("⚠️  GitHub Token not found!")
        print("   Create 'github_token.txt' file with your token")
        print("   Or set GITHUB_TOKEN environment variable")
    
    print("\n📊 Server Info:")
    print(f"   Admin Panel: http://localhost:5000/admin/dashboard")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Password: admin123")
    print(f"\n⚠️  Change the admin password in the code before deploying!")
    print("\n" + "="*60 + "\n")
    
    # تشغيل السيرفر
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

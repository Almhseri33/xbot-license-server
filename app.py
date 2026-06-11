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
from datetime import datetime, timedelta
from functools import wraps

# استيراد نظام التشفير
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from license_system.encryption import DataEncryption

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
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        total_syncs=total_syncs,
        recent_syncs=recent_syncs,
        licenses=licenses
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
        .btn { padding: 8px 16px; background: #4CAF50; border: none; color: #fff; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn:hover { background: #45a049; }
        .btn-danger { background: #f44336; }
        .btn-danger:hover { background: #da190b; }
        .btn-info { background: #2196F3; }
        .btn-info:hover { background: #1976D2; }
        .logout { float: right; }
    </style>
</head>
<body>
    <h1>📊 Admin Dashboard</h1>
    <a href="/admin/logout" class="btn btn-danger logout">Logout</a>
    
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
            <td>{{ license['status'] }}</td>
            <td><code>{{ license['hardware_id'][:16] if license['hardware_id'] else 'N/A' }}...</code></td>
            <td>{{ license['activated_at'] or 'N/A' }}</td>
            <td>{{ license['last_verified'] or 'N/A' }}</td>
            <td>
                <a href="/admin/view_data/{{ license['license_key'] }}" class="btn btn-info">👁️ View Data</a>
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


# ============================================================
# تشغيل السيرفر
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("🚀 License Server Starting...")
    print("="*60)
    
    # إنشاء قاعدة البيانات
    init_db()
    
    print("\n📊 Server Info:")
    print(f"   Admin Panel: http://localhost:5000/admin/dashboard")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Password: admin123")
    print(f"\n⚠️  Change the admin password in the code before deploying!")
    print("\n" + "="*60 + "\n")
    
    # تشغيل السيرفر
    app.run(host='0.0.0.0', port=5000, debug=False)

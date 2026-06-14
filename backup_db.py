#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Backup Script
======================
يعمل Backup تلقائي لقاعدة البيانات إلى GitHub
"""

import sqlite3
import json
import os
from datetime import datetime
import base64
import requests

GITHUB_USERNAME = 'Almhseri33'
GITHUB_REPO = 'xbot-license-server'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATABASE = 'license_server.db'
BACKUP_FILE = 'database_backup.json'


def export_database_to_json():
    """تصدير قاعدة البيانات إلى JSON"""
    if not os.path.exists(DATABASE):
        return None
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    backup_data = {
        'backup_date': datetime.now().isoformat(),
        'licenses': [],
        'synced_data': [],
        'activity_log': []
    }
    
    # تصدير licenses
    c.execute('SELECT * FROM licenses')
    for row in c.fetchall():
        backup_data['licenses'].append(dict(row))
    
    # تصدير synced_data
    c.execute('SELECT * FROM synced_data')
    for row in c.fetchall():
        backup_data['synced_data'].append(dict(row))
    
    # تصدير activity_log (آخر 1000 سجل)
    c.execute('SELECT * FROM activity_log ORDER BY id DESC LIMIT 1000')
    for row in c.fetchall():
        backup_data['activity_log'].append(dict(row))
    
    conn.close()
    return backup_data


def upload_backup_to_github(backup_data):
    """رفع Backup إلى GitHub"""
    if not GITHUB_TOKEN:
        print("❌ GitHub Token not found!")
        return False
    
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{BACKUP_FILE}"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # جلب SHA الحالي إذا كان الملف موجوداً
    response = requests.get(api_url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json()["sha"]
    
    # تحويل المحتوى إلى base64
    content = json.dumps(backup_data, indent=2, ensure_ascii=False)
    content_bytes = content.encode('utf-8')
    content_base64 = base64.b64encode(content_bytes).decode('utf-8')
    
    # رفع الملف
    data = {
        "message": f"Auto backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": content_base64,
    }
    
    if sha:
        data["sha"] = sha
    
    response = requests.put(api_url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        print(f"✅ Backup uploaded successfully to GitHub")
        return True
    else:
        print(f"❌ Failed to upload backup: {response.status_code}")
        print(response.text)
        return False


def restore_database_from_github():
    """استرجاع قاعدة البيانات من GitHub"""
    api_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/{BACKUP_FILE}"
    
    try:
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            backup_data = response.json()
            return backup_data
        else:
            print(f"❌ Failed to fetch backup: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"❌ Error restoring backup: {e}")
        return None


def import_database_from_json(backup_data):
    """استيراد قاعدة البيانات من JSON"""
    if not backup_data:
        return False
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        # إنشاء الجداول إذا لم تكن موجودة
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
        
        # استيراد licenses
        for license_data in backup_data.get('licenses', []):
            # حذف id للسماح بـ auto-increment
            license_id = license_data.pop('id', None)
            
            columns = ', '.join(license_data.keys())
            placeholders = ', '.join(['?' for _ in license_data])
            values = list(license_data.values())
            
            try:
                c.execute(f'''
                    INSERT OR REPLACE INTO licenses ({columns})
                    VALUES ({placeholders})
                ''', values)
            except Exception as e:
                print(f"⚠️ Error importing license: {e}")
        
        # استيراد synced_data
        for sync_data in backup_data.get('synced_data', []):
            sync_data.pop('id', None)
            
            columns = ', '.join(sync_data.keys())
            placeholders = ', '.join(['?' for _ in sync_data])
            values = list(sync_data.values())
            
            try:
                c.execute(f'''
                    INSERT OR REPLACE INTO synced_data ({columns})
                    VALUES ({placeholders})
                ''', values)
            except Exception as e:
                print(f"⚠️ Error importing synced data: {e}")
        
        # استيراد activity_log
        for log_data in backup_data.get('activity_log', []):
            log_data.pop('id', None)
            
            columns = ', '.join(log_data.keys())
            placeholders = ', '.join(['?' for _ in log_data])
            values = list(log_data.values())
            
            try:
                c.execute(f'''
                    INSERT INTO activity_log ({columns})
                    VALUES ({placeholders})
                ''', values)
            except Exception as e:
                print(f"⚠️ Error importing log: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database restored from backup!")
        print(f"   - Licenses: {len(backup_data.get('licenses', []))}")
        print(f"   - Synced Data: {len(backup_data.get('synced_data', []))}")
        print(f"   - Activity Logs: {len(backup_data.get('activity_log', []))}")
        
        return True
    
    except Exception as e:
        print(f"❌ Error importing database: {e}")
        conn.rollback()
        conn.close()
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_db.py backup   - Backup database to GitHub")
        print("  python backup_db.py restore  - Restore database from GitHub")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        print("📦 Backing up database...")
        backup_data = export_database_to_json()
        if backup_data:
            upload_backup_to_github(backup_data)
        else:
            print("❌ Database not found!")
    
    elif command == 'restore':
        print("📥 Restoring database...")
        backup_data = restore_database_from_github()
        if backup_data:
            import_database_from_json(backup_data)
        else:
            print("❌ No backup found!")
    
    else:
        print(f"❌ Unknown command: {command}")

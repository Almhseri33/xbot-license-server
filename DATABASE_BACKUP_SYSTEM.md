# 🔄 نظام النسخ الاحتياطي التلقائي
## Database Backup System

---

## 📋 **المشكلة**

Render يستخدم **ephemeral filesystem** - أي أن الملفات بتنحذف عند إعادة تشغيل السيرفر!

### ⚠️ **الأعراض:**
- المستخدم يفعّل البرنامج بكود تفعيل
- بعد فترة (يوم أو أكثر)، السيرفر يعيد التشغيل
- قاعدة البيانات تُمسح
- المستخدم يطلب كود تفعيل مرة ثانية
- الكود القديم **يختفي** من Admin Panel

---

## ✅ **الحل: نظام النسخ الاحتياطي الثلاثي**

### 1️⃣ **استرجاع تلقائي عند البدء**
```python
# عند كل تشغيل للسيرفر
- يفحص إذا في backup على GitHub
- يسترجع آخر backup
- يحدّث قاعدة البيانات المحلية
```

**الكود:**
```python
if __name__ == '__main__':
    # 🔥 استرجاع دائماً عند البدء
    backup_data = restore_database_from_github()
    if backup_data:
        import_database_from_json(backup_data)
```

### 2️⃣ **Backup تلقائي كل ساعة**
```python
# Thread منفصل يعمل backup كل 3600 ثانية
def auto_backup_scheduler():
    while True:
        time.sleep(3600)  # 1 ساعة
        export_database_to_json()
        upload_backup_to_github()
```

**المميزات:**
- ✅ يشتغل في الخلفية (daemon thread)
- ✅ ما يوقف السيرفر
- ✅ يعمل backup كل ساعة تلقائياً

### 3️⃣ **Backup فوري بعد كل عملية مهمة**
```python
# بعد: تفعيل ترخيص، مزامنة بيانات، إضافة ترخيص
trigger_immediate_backup()
```

**العمليات التي تفعّل backup فوري:**
- ✅ تفعيل ترخيص جديد (`/api/license/activate`)
- ✅ مزامنة بيانات (`/api/sync`)
- ✅ إضافة ترخيص من Admin Panel (`/api/admin/add-license`)

---

## 🔧 **كيف يشتغل؟**

### **الخطوة 1: Export**
```python
def export_database_to_json():
    # يصدّر من 3 جداول:
    - licenses (كل التراخيص)
    - synced_data (البيانات المزامنة)
    - activity_log (آخر 1000 سجل)
    
    return {
        'backup_date': '2026-06-28T10:00:00',
        'licenses': [...],
        'synced_data': [...],
        'activity_log': [...]
    }
```

### **الخطوة 2: Upload to GitHub**
```python
def upload_backup_to_github(backup_data):
    # يرفع على:
    # https://github.com/Almhseri33/xbot-license-server/blob/main/database_backup.json
    
    # باستخدام GitHub API:
    PUT /repos/{owner}/{repo}/contents/database_backup.json
```

### **الخطوة 3: Restore**
```python
def restore_database_from_github():
    # يجيب من:
    # https://raw.githubusercontent.com/Almhseri33/xbot-license-server/main/database_backup.json
    
    # يستورد البيانات للـ SQLite
    import_database_from_json(backup_data)
```

---

## 📊 **الجدول الزمني**

```
00:00 - السيرفر يبدأ → استرجاع من GitHub
01:00 - Backup تلقائي #1
02:00 - Backup تلقائي #2
03:00 - Backup تلقائي #3
...

أي وقت - مستخدم يفعّل ترخيص → Backup فوري
أي وقت - مزامنة بيانات → Backup فوري
```

---

## ⚙️ **الإعدادات المطلوبة**

### **1. GitHub Token**
```bash
# في Render Dashboard → Environment Variables
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
```

**أو** ملف `github_token.txt`:
```
ghp_xxxxxxxxxxxxx
```

### **2. Repository**
- **Repository:** `Almhseri33/xbot-license-server`
- **File:** `database_backup.json`
- **Branch:** `main`

---

## 🧪 **الاختبار**

### **Test 1: Manual Backup**
```bash
cd server
python backup_db.py backup
```

**النتيجة المتوقعة:**
```
✅ Backup uploaded successfully to GitHub
```

### **Test 2: Manual Restore**
```bash
python backup_db.py restore
```

**النتيجة المتوقعة:**
```
✅ Database restored from backup!
   - Licenses: 5
   - Synced Data: 3
   - Activity Logs: 234
```

### **Test 3: Auto Backup**
```bash
# شغّل السيرفر
python app.py

# انتظر ساعة واحدة
# شوف الـ logs:
```
```
🔄 [2026-06-28 11:00:00] Running auto-backup...
✅ Auto-backup completed successfully!
```

---

## 🔍 **المراقبة**

### **في Admin Panel:**
- اذهب إلى: `http://localhost:5000/admin/dashboard`
- اضغط "📦 Backup Database"
- يعمل backup يدوي فوري

### **في GitHub:**
- افتح: https://github.com/Almhseri33/xbot-license-server
- شوف ملف `database_backup.json`
- آخر commit يبين آخر backup

### **في Render Logs:**
```bash
# شوف logs السيرفر:
🔄 Checking for database backup...
✅ Database synced with GitHub backup!
✅ Auto-backup scheduler started (every 1 hour)
```

---

## ❓ **الأسئلة الشائعة**

### **Q: كم مرة يعمل backup؟**
**A:** 
- ✅ كل ساعة (تلقائي)
- ✅ بعد كل تفعيل (فوري)
- ✅ بعد كل مزامنة (فوري)
- ✅ يدوياً من Admin Panel

### **Q: ماذا لو GitHub down؟**
**A:** السيرفر يشتغل عادي، بس ما بيعمل backup. لما GitHub يرجع، بيرجع يعمل backup عادي.

### **Q: هل البيانات آمنة؟**
**A:** نعم - الـ repo خاص (private). بس البيانات المزامنة مشفرة أصلاً بـ AES-256.

### **Q: كيف أتأكد إنه شغال؟**
**A:** 
1. شوف Render logs: `Auto-backup completed`
2. شوف GitHub: آخر commit على `database_backup.json`
3. Admin Panel: اضغط "Backup" وشوف الرسالة

---

## 🚀 **الخلاصة**

النظام الجديد يضمن:
- ✅ **لا تضيع بيانات** - backup كل ساعة
- ✅ **استرجاع تلقائي** - عند كل إعادة تشغيل
- ✅ **backup فوري** - بعد كل عملية مهمة
- ✅ **مخزّن آمن** - على GitHub private repo

**المستخدمين هسا ما بيحتاجوا كود جديد - الكود القديم بيظل شغال! 🎉**

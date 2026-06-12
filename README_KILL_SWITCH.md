# 🔒 Kill Switch System - Admin Panel Integration

## ✨ What's New?

تم إضافة نظام حظر متكامل في لوحة إدارة الموقع!

---

## 🎯 Features

### 1. Block/Unblock Users
- ✅ زر "🔒 Block" بجانب كل مستخدم نشط
- ✅ زر "✅ Unblock" بجانب كل مستخدم محظور
- ✅ تأكيد قبل الحظر/رفع الحظر
- ✅ تحديث تلقائي لـ GitHub

### 2. Status Badges
- 🔒 **BLOCKED** - محظور
- ✅ **ACTIVE** - نشط
- ⚪ **INACTIVE** - غير نشط

### 3. Blacklist Page
- عرض كل المحظورين
- إحصائيات
- رفع الحظر السريع

---

## 🚀 Setup

### Step 1: Get GitHub Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name: `License Server Kill Switch`
4. Select scopes:
   - ✅ **repo** (all)
5. Click "Generate token"
6. Copy the token (you'll see it only once!)

### Step 2: Configure Token

**Option A: File (Recommended for local)**
```bash
cd server/
echo "YOUR_TOKEN_HERE" > github_token.txt
```

**Option B: Environment Variable (Recommended for deployment)**
```bash
export GITHUB_TOKEN="YOUR_TOKEN_HERE"
```

For Railway/Heroku:
- Add environment variable in dashboard: `GITHUB_TOKEN`

### Step 3: Run Server

```bash
cd server/
python app.py
```

---

## 📖 Usage

### Block a User

1. Open Admin Panel: http://localhost:5000/admin/dashboard
2. Login with:
   - Username: `admin`
   - Password: `admin123`
3. Find the user in the licenses table
4. Click "🔒 Block" button
5. Confirm
6. Done! User blocked immediately

**What happens:**
- Hardware ID added to `blacklist.json` on GitHub
- File committed automatically
- Within 1-2 minutes: User's app will close with "Connection Error"

### Unblock a User

1. Click "✅ Unblock" button next to blocked user
2. Confirm
3. Done! User can use the app again

### View All Blocked Users

1. Click "🔒 القائمة السوداء" button in top bar
2. See all blocked users
3. Quick unblock from this page

---

## 🔧 How It Works

### Block Flow

```
Admin clicks "Block"
    ↓
Get Hardware ID from database
    ↓
Fetch current blacklist.json from GitHub
    ↓
Add Hardware ID to list
    ↓
Update blacklist.json on GitHub (via API)
    ↓
Commit changes
    ↓
Done! ✅
```

### Client Side (User's App)

```
App starts
    ↓
Check blacklist.json from GitHub
    ↓
Is Hardware ID in list?
    ├─ YES → Show "Connection Error" → Close app
    └─ NO → Continue normally
```

---

## 📊 API Endpoints

### Block User
```
POST /admin/block_user/<license_key>
```

**Response:**
```json
{
  "success": true,
  "message": "User blocked successfully"
}
```

### Unblock User
```
POST /admin/unblock_user/<license_key>
```

**Response:**
```json
{
  "success": true,
  "message": "User unblocked successfully"
}
```

### View Blacklist
```
GET /admin/blacklist
```

---

## 🛡️ Security

- ✅ Admin authentication required
- ✅ GitHub Token stored securely
- ✅ User sees generic error (doesn't know they're blocked)
- ✅ All actions logged in `activity_log` table

---

## 🎨 UI Screenshots

### Dashboard
```
┌─────────────────────────────────────────────────┐
│ 📊 Admin Dashboard              🔒 القائمة السوداء│
├─────────────────────────────────────────────────┤
│ License Key | Status  | Actions                 │
├─────────────────────────────────────────────────┤
│ ABCD-1234   │ ✅ ACTIVE│ 👁️ View  🔒 Block      │
│ EFGH-5678   │ 🔒 BLOCKED│ 👁️ View  ✅ Unblock   │
└─────────────────────────────────────────────────┘
```

### Blacklist Page
```
┌─────────────────────────────────────────────────┐
│ 🔒 Blacklist Management      ← Back to Dashboard│
├─────────────────────────────────────────────────┤
│ Blocked Users: 5           Last Updated: Now    │
├─────────────────────────────────────────────────┤
│ License Key  | Hardware ID | Actions            │
├─────────────────────────────────────────────────┤
│ ABCD-1234    │ a3f5d8b2... │ 👁️ View ✅ Unblock │
└─────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### GitHub Settings (in app.py)

```python
GITHUB_USERNAME = 'Almhseri33'
GITHUB_REPO = 'xbot-license-server'
GITHUB_TOKEN = ''  # loaded from file or env
```

### Change Admin Password

In `app.py`, line ~145:
```python
ADMIN_PASSWORD_HASH = hashlib.sha256('YOUR_NEW_PASSWORD'.encode()).hexdigest()
```

---

## 🐛 Troubleshooting

### Error: "GitHub Token not configured"
**Solution:** Create `github_token.txt` file or set `GITHUB_TOKEN` environment variable

### Error: "Failed to update blacklist on GitHub"
**Possible causes:**
- Token expired or invalid
- Token doesn't have `repo` permission
- Repository doesn't exist
- Repository is private (should be public)

**Solution:**
1. Check token is valid
2. Verify token has `repo` scope
3. Ensure repository is public

### Blocked user still using app
**Possible causes:**
- GitHub needs time to propagate (30-60 seconds)
- User doesn't have internet connection

**Solution:**
- Wait 2 minutes
- User needs to restart app or wait for hourly check

---

## 📝 Activity Log

All block/unblock actions are logged in `activity_log` table:

```sql
SELECT * FROM activity_log WHERE action LIKE '%block%' ORDER BY timestamp DESC;
```

---

## 🚀 Deployment

### Railway

1. Push code to GitHub
2. Connect repository to Railway
3. Add environment variable: `GITHUB_TOKEN`
4. Deploy!

### Heroku

```bash
heroku create your-app-name
heroku config:set GITHUB_TOKEN="your_token_here"
git push heroku main
```

---

## ✅ Testing

1. Start server: `python app.py`
2. Open: http://localhost:5000/admin/dashboard
3. Login (admin/admin123)
4. Create a test license
5. Activate it (use any Hardware ID)
6. Block the user
7. Check GitHub - `blacklist.json` should be updated
8. Unblock the user
9. Check GitHub - Hardware ID should be removed

---

## 📚 Related Files

- `app.py` - Main server file with kill switch integration
- `blacklist.json` - Blocked Hardware IDs (on GitHub)
- `github_token.txt` - GitHub Personal Access Token
- `LICENSE_SYSTEM_README.md` - License system documentation

---

## 🎉 Summary

✅ Block/Unblock users from web dashboard
✅ Automatic GitHub integration
✅ Real-time updates
✅ User-friendly interface
✅ Secure and reliable

---

**Made with ❤️ for X Bot Manager**

# Service Account Authentication Setup Guide

## Problem
Currently you need to run `gcloud auth login` every day because user authentication expires.

## Solution
Use a **Service Account** with a JSON key file for persistent authentication.

---

## Step-by-Step Setup

### 1. Create Service Account in Google Cloud

**Go to Google Cloud Console:**
```
https://console.cloud.google.com/iam-admin/serviceaccounts?project=agenticraga
```

**Create Service Account:**
1. Click `+ CREATE SERVICE ACCOUNT`
2. **Service account name**: `agent-vertex-ai`
3. **Service account ID**: `agent-vertex-ai` (auto-generated)
4. Click `CREATE AND CONTINUE`

**Grant Permissions:**
Add these roles:
- ✅ `Vertex AI User` (for using Gemini models and RAG)
- ✅ `Storage Object Viewer` (for GCS bucket access if needed)

Click `CONTINUE` → `DONE`

### 2. Create and Download JSON Key

**In the Service Accounts list:**
1. Find `agent-vertex-ai@agenticraga.iam.gserviceaccount.com`
2. Click the 3 dots (⋮) → `Manage keys`
3. Click `ADD KEY` → `Create new key`
4. Select **JSON**
5. Click `CREATE`

**A file will download:** `agenticraga-xxxxxxxxxxxx.json`

### 3. Secure the Key File

**⚠️ CRITICAL:** This file is like a password. Anyone with it can access your Vertex AI.

**Store it securely:**
```
C:\Users\gabri\.gcloud\agent-service-account.json
```

**Make the directory:**
```powershell
mkdir C:\Users\gabri\.gcloud
```

**Move the downloaded file there and rename:**
```powershell
move Downloads\agenticraga-*.json C:\Users\gabri\.gcloud\agent-service-account.json
```

### 4. Configure Your .env

**Add this line to your `.env`:**
```env
GOOGLE_APPLICATION_CREDENTIALS=C:/Users/gabri/.gcloud/agent-service-account.json
```

**Full .env example:**
```env
# Private Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key_here

# Shared Vertex AI
PROJECT_ID=agenticraga
LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=C:/Users/gabri/.gcloud/agent-service-account.json

# Gemini Keys
GEMINI_API_KEY=your_key
GEMINIFLASH_API_KEY=your_key
```

### 5. Test Authentication

**Run this test:**
```python
python -c "import vertexai; vertexai.init(project='agenticraga', location='europe-west1'); print('✅ Authentication works!')"
```

**If successful, you should see:**
```
✅ Authentication works!
```

**If it fails, check:**
- Path to JSON file is correct
- JSON file has correct permissions
- Service account has `Vertex AI User` role

---

## For Your Friend

### Option A: Share the Same Service Account (Easier)

**Steps:**
1. Send them the JSON key file (use encrypted email or secure file transfer)
2. They save it to: `C:\Users\{their-name}\.gcloud\agent-service-account.json`
3. They add to their `.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=C:/Users/{their-name}/.gcloud/agent-service-account.json
   ```

**⚠️ Security Note:**
- Both of you share the same credentials
- Either can see all Vertex AI usage
- Trust is required

### Option B: Create Separate Service Account (More Secure)

**Steps:**
1. Create another service account: `agent-vertex-ai-friend`
2. Grant same roles
3. Download separate JSON key
4. Send to your friend
5. Track usage separately

**Advantage:**
- Can revoke friend's access independently
- Separate audit logs

---

## Verification

### Check if Auth is Working

**Before (Daily Login Required):**
```bash
gcloud auth application-default login
# Expires in 24 hours
```

**After (Permanent):**
```python
# Just works, no login needed
from vertexai import rag
# Authentication automatic via GOOGLE_APPLICATION_CREDENTIALS
```

### Check Which Account is Active

```python
import os
print(f"Using: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
```

---

## Troubleshooting

### Error: "Could not automatically determine credentials"
**Fix:** Check the path in `GOOGLE_APPLICATION_CREDENTIALS` is correct

### Error: "Permission denied"
**Fix:** Service account needs `Vertex AI User` role

### Error: "File not found"
**Fix:** Use forward slashes in path: `C:/Users/...` not `C:\Users\...`

---

## Security Best Practices

✅ **DO:**
- Store key file in `.gcloud` directory (ignored by Git)
- Keep backup of key file in password manager
- Revoke old keys if creating new ones
- Use separate service accounts for production

❌ **DON'T:**
- Commit JSON key to Git
- Share key in plain text email
- Leave key in Downloads folder
- Use same key for multiple projects

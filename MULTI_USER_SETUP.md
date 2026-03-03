# Multi-User Setup Guide

## For You (Project Owner)

### 1. Create Service Account (Fix Daily Login)

**In Google Cloud Console:**
1. Go to `IAM & Admin` → `Service Accounts`
2. Click `Create Service Account`
3. Name: `agent-service-account`
4. Grant role: `Vertex AI User`
5. Create JSON key → Download it
6. Save as `service-account-key.json` (DO NOT commit to Git)

**In your `.env`:**
```env
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account-key.json
```

**Test:**
```bash
python -c "import vertexai; vertexai.init(project='agenticraga', location='europe-west1'); print('✅ Auth works!')"
```

### 2. Your Supabase (Already Set Up)
Keep your existing:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key
```

---

## For Your Friend (New User)

### 1. Get Service Account Key
- You share the `service-account-key.json` with them (secure transfer)
- OR they create their own service account in the same Google Cloud project

### 2. Create Their Own Supabase
1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Copy URL and Key

### 3. Run SQL Schema
In their Supabase SQL editor, run:
```sql
-- From agent_project/schema.sql
-- (Creates conversations, messages tables)

-- From agent_project/memory_vectors_schema.sql
-- (Creates vector memory table)
```

### 4. Configure .env
```env
# Their PRIVATE Supabase
SUPABASE_URL=https://THEIR-PROJECT.supabase.co
SUPABASE_KEY=their_key_here

# SHARED Vertex AI (same as yours)
PROJECT_ID=agenticraga
LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account-key.json

# Their API keys
GEMINI_API_KEY=their_key
GEMINIFLASH_API_KEY=their_key
```

### 5. Install & Run
```bash
git clone https://github.com/LinckK/ai_specialist-.git
cd ai_specialist-
pip install -r requirements.txt
python -m agent_project.cli
```

---

## What's Shared vs Private

| Resource | Sharing |
|:---|:---|
| RAG Corpus (Knowledge) | ✅ **Shared** (both access same documents) |
| Conversations | ❌ **Private** (each user's own Supabase) |
| Agents | ❌ **Private** (each user's own Supabase) |
| Vector Memory | ❌ **Private** (each user's own Supabase) |
| Uploads to Corpus | ✅ **Shared** (both can add documents) |

---

## Security Notes

⚠️ **Service Account Key is Sensitive**
- Acts like a password for Google Cloud
- Anyone with it can access your Vertex AI
- Share securely (encrypted email, password manager)

✅ **Supabase is Isolated**
- Your friend CANNOT see your conversations
- You CANNOT see their conversations
- Each has separate databases

⚠️ **Shared Corpus Means Trust**
- Both can upload documents to the shared knowledge base
- Both can see all documents in the corpus
- Only share with people you trust

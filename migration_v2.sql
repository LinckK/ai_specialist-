-- ============================================================
-- THE AI BOARDROOM — Database Migration V2
-- Run this in Supabase SQL Editor (alongside existing tables)
-- Existing tables (conversations, messages, agents) are UNTOUCHED
-- ============================================================

-- Enable pgvector extension (for Phase 3: episodic memory search)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. PROJECTS (The State Machine)
-- Each project holds a context_snapshot (JSONB) that is the
-- "living document" — updated by the Synthesizer agent.
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',          -- active | paused | completed | archived
    
    -- Phase 2: Google Drive integration
    drive_folder_id TEXT,                            -- Google Drive folder ID (sandbox per project)
    
    -- The Core: Living Project State (updated by AI)
    -- Example: {"phase": "Negotiation", "budget": 5000, "risks": ["Timeline"], "next_deadline": "2025-12-01"}
    context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Phase 2: Subscription/paywall
    plan_tier TEXT DEFAULT 'free',                   -- free | pro | enterprise
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for user lookups (dashboard loads user's projects)
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
-- GIN index for JSONB queries (e.g., find projects with overdue deadlines)
CREATE INDEX IF NOT EXISTS idx_projects_context ON projects USING GIN (context_snapshot);

-- ============================================================
-- 2. EPISODIC MEMORY (The Learning Layer)
-- Stores lessons, preferences, feedback. Each memory belongs
-- to a project. Vector column ready for Phase 3 similarity search.
-- ============================================================
CREATE TABLE IF NOT EXISTS episodic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    content TEXT NOT NULL,                           -- "User prefers formal contracts"
    type TEXT NOT NULL DEFAULT 'fact',               -- preference | fact | feedback | mistake | success
    
    -- Phase 3: Vector embedding for similarity search
    embedding VECTOR(768),                           -- Vertex AI text-embedding-005 = 768 dims
    
    -- Metadata for filtering
    source TEXT DEFAULT 'system',                    -- system | user | agent
    tags TEXT[] DEFAULT '{}',                        -- Searchable tags
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_episodic_project ON episodic_memory(project_id);
CREATE INDEX IF NOT EXISTS idx_episodic_type ON episodic_memory(type);
-- Phase 3: Vector similarity index (IVFFlat for fast approximate search)
-- CREATE INDEX IF NOT EXISTS idx_episodic_embedding ON episodic_memory 
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 3. EXECUTION RUNS (The Audit Log)
-- Every time the Boardroom runs (user request, cron, drive event),
-- it creates a run with the full trace.
-- ============================================================
CREATE TABLE IF NOT EXISTS execution_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- What triggered this run? (expandable for Phase 2)
    trigger_source TEXT NOT NULL DEFAULT 'cli',      -- cli | web | whatsapp | drive_event | cron
    trigger_input TEXT,                               -- The raw user message or event description
    
    -- Which agents were involved?
    agents_used TEXT[] DEFAULT '{}',                  -- ["marketing-director", "legal", "psicologist"]
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'processing',        -- processing | waiting_approval | approved | rejected | completed | failed
    
    -- Results
    agent_outputs JSONB DEFAULT '[]'::jsonb,         -- Array of {agent_name, output, timestamp}
    final_plan JSONB,                                 -- The synthesized plan (CEO output)
    state_patch JSONB,                                -- The patch applied to context_snapshot
    
    -- Phase 2: User feedback
    user_feedback TEXT,                               -- "Too expensive" / "Perfect"
    feedback_sentiment TEXT,                           -- positive | negative | neutral
    
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runs_project ON execution_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON execution_runs(status);

-- ============================================================
-- 4. ROW LEVEL SECURITY (Multi-user isolation)
-- Each user can only see/modify their own data.
-- Service role (backend) bypasses RLS.
-- ============================================================
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodic_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_runs ENABLE ROW LEVEL SECURITY;

-- Projects: user sees only their own
CREATE POLICY "projects_user_isolation" ON projects
    FOR ALL USING (auth.uid() = user_id);

-- Episodic Memory: user sees memories from their projects
CREATE POLICY "memory_user_isolation" ON episodic_memory
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

-- Execution Runs: user sees runs from their projects
CREATE POLICY "runs_user_isolation" ON execution_runs
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

-- ============================================================
-- 5. AUTO-UPDATE TRIGGER (updated_at on projects)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- DONE. Existing tables (conversations, messages, agents) 
-- are completely untouched.
-- ============================================================

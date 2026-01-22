-- ============================================
-- Vector Memory System Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create memory_vectors table
CREATE TABLE IF NOT EXISTS public.memory_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    fact_type TEXT DEFAULT 'GENERAL',      -- PREFERENCE, CONSTRAINT, DECISION, GENERAL
    scope TEXT DEFAULT 'GLOBAL',            -- CHAT, AGENT, GLOBAL
    agent_type TEXT,                        -- 'psychologist', 'business_master', NULL for GLOBAL
    embedding VECTOR(768),                  -- Google text-embedding-004 dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create index for fast vector search
CREATE INDEX IF NOT EXISTS memory_vectors_embedding_idx 
ON public.memory_vectors 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 4. Create index for scope filtering
CREATE INDEX IF NOT EXISTS memory_vectors_scope_idx 
ON public.memory_vectors (scope, agent_type);

-- 5. Create similarity search function
CREATE OR REPLACE FUNCTION match_memory(
    query_embedding VECTOR(768),
    match_count INT DEFAULT 10,
    filter_scope TEXT[] DEFAULT ARRAY['GLOBAL'],
    filter_agent_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    fact_type TEXT,
    scope TEXT,
    agent_type TEXT,
    created_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        mv.id,
        mv.content,
        mv.fact_type,
        mv.scope,
        mv.agent_type,
        mv.created_at,
        1 - (mv.embedding <=> query_embedding) AS similarity
    FROM public.memory_vectors mv
    WHERE mv.scope = ANY(filter_scope)
      AND (filter_agent_type IS NULL OR mv.agent_type IS NULL OR mv.agent_type = filter_agent_type)
    ORDER BY mv.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 6. Grant access to authenticated users
GRANT ALL ON public.memory_vectors TO authenticated;
GRANT ALL ON public.memory_vectors TO service_role;

-- Notify PostgREST to reload schema
NOTIFY pgrst, 'reload schema';

-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Users table (managed by Supabase Auth usually, but defining a public profile table is good practice)
create table public.users (
  id uuid references auth.users not null primary key,
  email text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Agents table (Configuration for different agent personas)
create table public.agents (
  id uuid default gen_random_uuid() primary key,
  name text not null unique,
  description text,
  config jsonb not null default '{}'::jsonb,
  enabled boolean default true,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Conversations table
create table public.conversations (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.users(id),
  title text default 'New Conversation',
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Messages table
create table public.messages (
  id uuid default gen_random_uuid() primary key,
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  role text not null, -- 'user', 'assistant', 'system', 'tool'
  content text,
  tool_calls jsonb, -- For assistant messages invoking tools
  tool_call_id text, -- For tool output messages
  name text, -- For tool output messages (function name)
  embedding vector(768), -- Vector embedding for RAG (768 dim for Gemini/Vertex)
  metadata jsonb default '{}'::jsonb, -- For RAG chunks references etc
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Agent Facts table (Persistent Memory)
create table public.agent_facts (
  id uuid default gen_random_uuid() primary key,
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  fact_content text not null,
  fact_type text default 'GENERAL',  -- PREFERENCE, CONSTRAINT, DECISION, GENERAL
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Indexes for performance
create index idx_messages_conversation_id on public.messages(conversation_id);
create index idx_conversations_user_id on public.conversations(user_id);
create index idx_agent_facts_conversation_id on public.agent_facts(conversation_id);

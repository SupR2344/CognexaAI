-- ==============================================================================
-- Cognexa AI - PostgreSQL Schema Initialization Script
-- Extensions, Enums, Tables, Foreign Keys, Triggers, and Vector Indexes
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Enable Required Extensions
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------------------
-- 2. Enumerated Types
-- ------------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memory_type_enum') THEN
        CREATE TYPE memory_type_enum AS ENUM ('working', 'episodic', 'semantic', 'procedural');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status_enum') THEN
        CREATE TYPE task_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'cancelled');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'step_status_enum') THEN
        CREATE TYPE step_status_enum AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_role_enum') THEN
        CREATE TYPE message_role_enum AS ENUM ('system', 'user', 'assistant', 'tool');
    END IF;
END$$;

-- ------------------------------------------------------------------------------
-- 3. Automatic Updated-At Trigger Function
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------------------------
-- 4. Users Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ------------------------------------------------------------------------------
-- 5. Conversations Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_conversations_updated_at ON conversations;
CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ------------------------------------------------------------------------------
-- 6. Messages Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role message_role_enum NOT NULL,
    content TEXT NOT NULL,
    tool_calls JSONB DEFAULT NULL,
    tool_call_id VARCHAR(255) DEFAULT NULL,
    token_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 7. Memories Table (Persistent Hierarchical Vector Memory)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type memory_type_enum NOT NULL,
    content TEXT NOT NULL,
    summary VARCHAR(512),
    embedding vector(384),
    importance_score FLOAT NOT NULL DEFAULT 0.5 CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_memories_updated_at ON memories;
CREATE TRIGGER trg_memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ------------------------------------------------------------------------------
-- 8. Tasks Table (Autonomous Goal Decomposition)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status task_status_enum NOT NULL DEFAULT 'pending',
    result JSONB DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ------------------------------------------------------------------------------
-- 9. Task Steps Table (Atomic Sandbox Steps & Reflexion)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    code TEXT,
    status step_status_enum NOT NULL DEFAULT 'pending',
    output TEXT DEFAULT NULL,
    error TEXT DEFAULT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    execution_time_ms INTEGER DEFAULT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_task_step_order UNIQUE (task_id, step_number)
);

DROP TRIGGER IF EXISTS trg_task_steps_updated_at ON task_steps;
CREATE TRIGGER trg_task_steps_updated_at
    BEFORE UPDATE ON task_steps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ------------------------------------------------------------------------------
-- 10. Performance & Foreign Key Indexes
-- ------------------------------------------------------------------------------
-- Users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

-- Messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at ASC);

-- Memories (Foreign Key & Attribute Filters)
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at DESC);

-- Tasks
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);

-- Task Steps
CREATE INDEX IF NOT EXISTS idx_task_steps_task_id ON task_steps(task_id);
CREATE INDEX IF NOT EXISTS idx_task_steps_status ON task_steps(status);
CREATE INDEX IF NOT EXISTS idx_task_steps_order ON task_steps(task_id, step_number);

-- ------------------------------------------------------------------------------
-- 11. Vector Similarity Index (IVFFlat)
-- ------------------------------------------------------------------------------
-- Note: IVFFlat index accelerates cosine similarity searches across memory embeddings.
CREATE INDEX IF NOT EXISTS idx_memories_embedding_ivfflat 
    ON memories 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);

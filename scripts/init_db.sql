-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create indexes for vector similarity search
-- These will be applied to tables after Django migrations

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized with pgvector extension';
END $$;

-- Migration: Add buyer numbering and hidden chat features
-- Date: 2026-01-02

-- Add anonymous_buyer_number column
ALTER TABLE chat ADD COLUMN IF NOT EXISTS anonymous_buyer_number INTEGER;

-- Add hidden fields
ALTER TABLE chat ADD COLUMN IF NOT EXISTS is_hidden_by_buyer BOOLEAN DEFAULT FALSE;
ALTER TABLE chat ADD COLUMN IF NOT EXISTS is_hidden_by_seller BOOLEAN DEFAULT FALSE;

-- Create index for better performance on hidden chats filtering
CREATE INDEX IF NOT EXISTS idx_chat_hidden_buyer ON chat(buyer_id, is_hidden_by_buyer);
CREATE INDEX IF NOT EXISTS idx_chat_hidden_seller ON chat(seller_id, is_hidden_by_seller);

-- Add comment
COMMENT ON COLUMN chat.anonymous_buyer_number IS 'Sequential number for anonymous buyers (1, 2, 3...) per seller';
COMMENT ON COLUMN chat.is_hidden_by_buyer IS 'Whether chat is hidden for buyer (soft delete)';
COMMENT ON COLUMN chat.is_hidden_by_seller IS 'Whether chat is hidden for seller (soft delete)';

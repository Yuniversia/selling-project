-- Migration 004: Add push subscriptions table
-- Purpose: Store user's web push notification subscriptions

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast user lookup
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions(user_id);

-- Index for endpoint lookup (check duplicates)
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_endpoint ON push_subscriptions(endpoint);

COMMENT ON TABLE push_subscriptions IS 'Web Push notification subscriptions for users';
COMMENT ON COLUMN push_subscriptions.user_id IS 'User ID (can be registered user or anonymous UUID)';
COMMENT ON COLUMN push_subscriptions.endpoint IS 'Push service endpoint URL (unique per browser/device)';
COMMENT ON COLUMN push_subscriptions.p256dh IS 'Public key for message encryption (ECDH)';
COMMENT ON COLUMN push_subscriptions.auth IS 'Authentication secret for message signing';

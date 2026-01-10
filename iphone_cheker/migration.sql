-- Migration: Add IMEI cache and logs tables
-- Version: 2.0
-- Date: 2026-01-09

-- ==========================================
-- IMEI Cache Table (7 days TTL)
-- ==========================================

CREATE TABLE IF NOT EXISTS imei_cache (
    imei VARCHAR(15) PRIMARY KEY,
    
    -- Device data
    model VARCHAR(100),
    color VARCHAR(100),
    memory INTEGER,
    serial_number VARCHAR(50),
    
    -- Warranty data (from imei.info)
    purchase_date VARCHAR(50),
    warranty_status VARCHAR(50),
    warranty_expires VARCHAR(50),
    
    -- Basic data (from imei.org)
    icloud_status VARCHAR(50),
    simlock VARCHAR(50),
    fmi BOOLEAN,
    activation_lock BOOLEAN,
    
    -- Metadata
    source VARCHAR(50) NOT NULL,
    checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_imei_cache_expires_at ON imei_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_imei_cache_source ON imei_cache(source);


-- ==========================================
-- IMEI Check Logs Table
-- ==========================================

CREATE TABLE IF NOT EXISTS imei_check_logs (
    id SERIAL PRIMARY KEY,
    imei VARCHAR(15) NOT NULL,
    source VARCHAR(50) NOT NULL,
    check_type VARCHAR(20) NOT NULL,
    success BOOLEAN NOT NULL,
    response_time_ms FLOAT NOT NULL,
    error_message TEXT,
    test_mode BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for analytics
CREATE INDEX IF NOT EXISTS idx_imei_check_logs_imei ON imei_check_logs(imei);
CREATE INDEX IF NOT EXISTS idx_imei_check_logs_created_at ON imei_check_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_imei_check_logs_source ON imei_check_logs(source);
CREATE INDEX IF NOT EXISTS idx_imei_check_logs_success ON imei_check_logs(success);


-- ==========================================
-- Add imei_data_source to iphone table
-- ==========================================

ALTER TABLE iphone 
ADD COLUMN IF NOT EXISTS imei_data_source VARCHAR(50);

-- Add comment
COMMENT ON COLUMN iphone.imei_data_source IS 'Source of IMEI data: imei.info, imei.org, cache, mock';


-- ==========================================
-- Cleanup job (delete expired cache)
-- ==========================================

-- Run periodically to clean up expired cache
-- DELETE FROM imei_cache WHERE expires_at < NOW();

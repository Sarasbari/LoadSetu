-- Migration: 003_pod_and_ai_fields.sql
-- Description: Alter tables to add POD and AI metadata fields to shipments.

ALTER TABLE shipments ADD COLUMN IF NOT EXISTS pod_status TEXT DEFAULT 'PENDING';
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS pod_note TEXT;
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS pod_media_url TEXT;
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS pod_received_at TIMESTAMPTZ;

ALTER TABLE shipments ADD COLUMN IF NOT EXISTS ai_confidence TEXT DEFAULT 'LOW';
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS ai_metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS delay_risk_score INTEGER DEFAULT 0;
ALTER TABLE shipments ADD COLUMN IF NOT EXISTS delay_risk_level TEXT DEFAULT 'Low';

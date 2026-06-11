-- Migration: 006_notification_attempts.sql
-- Description: Create notification_attempts table to track outbound message delivery status and errors.

CREATE TABLE IF NOT EXISTS notification_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    to_phone TEXT NOT NULL,
    shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,
    body TEXT NOT NULL,
    media_url TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',  -- 'PENDING' | 'SENT' | 'FAILED' | 'SENT_MOCK'
    provider_sid TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_attempts_shipment_id ON notification_attempts(shipment_id);
CREATE INDEX IF NOT EXISTS idx_notification_attempts_to_phone ON notification_attempts(to_phone);

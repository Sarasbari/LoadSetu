-- Migration: 007_manual_review_queue.sql
-- Description: Create booking_review_items table to store low-confidence AI bookings for operator review.

CREATE TABLE IF NOT EXISTS booking_review_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN' | 'RESOLVED' | 'DISMISSED'
    extracted_details JSONB DEFAULT '{}'::jsonb,
    missing_fields JSONB DEFAULT '[]'::jsonb,
    latest_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_booking_review_items_status ON booking_review_items(status);
CREATE INDEX IF NOT EXISTS idx_booking_review_items_phone_number ON booking_review_items(phone_number);

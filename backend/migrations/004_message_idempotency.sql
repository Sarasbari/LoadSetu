-- Migration: 004_message_idempotency.sql
-- Description: Alter messages table to add message_sid for Twilio webhook idempotency.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_sid TEXT UNIQUE;

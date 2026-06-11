-- Migration: 005_operator_onboarding.sql
-- Description: Alter operators table to add onboarding_status.

ALTER TABLE operators ADD COLUMN IF NOT EXISTS onboarding_status TEXT DEFAULT 'PENDING';

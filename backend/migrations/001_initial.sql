-- Migration: 001_initial.sql
-- Description: Create core tables for operators, trucks, shipments, messages, and conversation_state.

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: operators
CREATE TABLE IF NOT EXISTS operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone TEXT UNIQUE NOT NULL,        -- WhatsApp number, e.g. +919876543210
    name TEXT,
    business_name TEXT,
    gst_number TEXT,
    city TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: trucks
CREATE TABLE IF NOT EXISTS trucks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_name TEXT NOT NULL,
    driver_phone TEXT NOT NULL,
    truck_number TEXT NOT NULL,               -- e.g. MH-15-AB-1234
    truck_type TEXT,                        -- open/closed/refrigerated/flatbed
    capacity_tons DECIMAL(5,2),
    home_city TEXT,                        -- Base location of truck
    current_city TEXT,                        -- Updated after each delivery
    is_available BOOLEAN DEFAULT TRUE,
    notes TEXT,                        -- e.g. "no night driving"
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: shipments
CREATE TABLE IF NOT EXISTS shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID REFERENCES operators(id) ON DELETE SET NULL,
    truck_id UUID REFERENCES trucks(id) ON DELETE SET NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    cargo_type TEXT NOT NULL,
    weight_tons DECIMAL(6,2),
    scheduled_date DATE,
    status TEXT DEFAULT 'PENDING',
    ewb_draft_json JSONB,                       -- All e-way bill fields as JSON
    ewb_pdf_url TEXT,                        -- Supabase storage URL for PDF
    confirmed_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    delay_alerted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT NOT NULL,               -- sender's number
    direction TEXT NOT NULL,               -- 'INBOUND' | 'OUTBOUND'
    body TEXT NOT NULL,
    shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,  -- NULL if pre-booking
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Table: conversation_state
CREATE TABLE IF NOT EXISTS conversation_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT UNIQUE NOT NULL,
    last_intent TEXT,                        -- 'NEW_BOOKING' | 'STATUS_UPDATE' | 'QUERY' | 'CONFIRMATION'
    context_json JSONB,                       -- Last 5 messages + partial extraction
    active_shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on foreign keys and frequently queried fields
CREATE INDEX IF NOT EXISTS idx_shipments_operator_id ON shipments(operator_id);
CREATE INDEX IF NOT EXISTS idx_shipments_truck_id ON shipments(truck_id);
CREATE INDEX IF NOT EXISTS idx_messages_phone_number ON messages(phone_number);
CREATE INDEX IF NOT EXISTS idx_conversation_state_phone_number ON conversation_state(phone_number);
CREATE INDEX IF NOT EXISTS idx_trucks_availability_route ON trucks(is_available, home_city, capacity_tons);

-- Enable Row-Level Security (RLS)
ALTER TABLE operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipments ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies
DROP POLICY IF EXISTS "operators_own_data" ON operators;
CREATE POLICY "operators_own_data" ON operators
  FOR ALL TO authenticated
  USING (phone = (auth.jwt()->>'phone_number'))
  WITH CHECK (phone = (auth.jwt()->>'phone_number'));

DROP POLICY IF EXISTS "shipments_by_operator" ON shipments;
CREATE POLICY "shipments_by_operator" ON shipments
  FOR ALL TO authenticated
  USING (
    operator_id IN (
      SELECT id FROM operators
      WHERE phone = (auth.jwt()->>'phone_number')
    )
  );

DROP POLICY IF EXISTS "messages_own" ON messages;
CREATE POLICY "messages_own" ON messages
  FOR ALL TO authenticated
  USING (phone_number = (auth.jwt()->>'phone_number'));

-- Seed Truck Registry
INSERT INTO trucks (driver_name, driver_phone, truck_number, truck_type, capacity_tons, home_city, current_city, is_available, notes)
VALUES
  ('Ramesh Kumar', '+919876543211', 'MH-15-AB-1234', 'open', 10.00, 'Nashik', 'Nashik', true, 'Prefers short routes'),
  ('Suresh Patel', '+919876543212', 'MH-04-CX-5678', 'closed', 8.50, 'Surat', 'Surat', true, 'Available for night driving'),
  ('Dinesh Singh', '+919876543213', 'MH-12-GH-9012', 'open', 5.00, 'Mumbai', 'Mumbai', true, 'Local trips only'),
  ('Jaspreet Singh', '+919876543214', 'PB-10-CZ-2468', 'closed', 16.00, 'Ludhiana', 'Ludhiana', true, 'Interstate long haul'),
  ('Vikram Rathore', '+919876543215', 'RJ-14-GH-1357', 'flatbed', 20.00, 'Jaipur', 'Jaipur', true, 'Available for heavy loads'),
  ('Anil Sharma', '+919876543216', 'DL-01-MA-9988', 'refrigerated', 12.00, 'Delhi', 'Delhi', true, 'Cold chain specialized'),
  ('Gopal Krishnan', '+919876543217', 'TN-37-BY-4321', 'open', 9.00, 'Coimbatore', 'Coimbatore', true, 'South India trips only'),
  ('Vijay Yadav', '+919876543218', 'UP-70-ET-8765', 'closed', 15.00, 'Surat', 'Surat', true, 'Prefers Surat-Mumbai corridor'),
  ('Baldev Singh', '+919876543219', 'PB-02-KL-7777', 'open', 18.00, 'Ludhiana', 'Ludhiana', true, 'North-West route preference'),
  ('Sanjay Gupta', '+919876543220', 'MH-43-XY-3344', 'closed', 6.00, 'Mumbai', 'Mumbai', true, 'Mumbai local and Pune routes'),
  ('Karan Johar', '+919876543221', 'MH-12-PQ-8899', 'open', 10.00, 'Pune', 'Pune', true, 'Pune to Mumbai specialist'),
  ('Mohammad Ali', '+919876543222', 'GJ-05-AA-5555', 'flatbed', 15.00, 'Surat', 'Surat', true, 'Heavy machinery transport')
ON CONFLICT DO NOTHING;

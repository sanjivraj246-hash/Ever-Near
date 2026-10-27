-- EVER NEAR AI — Phase 5: PostgreSQL Database Foundation
-- Initial 5 Entities: users, parent_profiles, family_profiles, family_relationships, trusted_contacts

-- 1. Helper function for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 2. Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(32) NOT NULL UNIQUE,
    full_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'PARENT',
    password_hash VARCHAR(256) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 3. Parent Profiles Table
CREATE TABLE IF NOT EXISTS parent_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    preferred_name VARCHAR(128) NOT NULL DEFAULT 'Amma',
    age INTEGER DEFAULT 72,
    emergency_notes TEXT,
    language_pref VARCHAR(10) NOT NULL DEFAULT 'ta',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_profiles_user_id ON parent_profiles(user_id);

DROP TRIGGER IF EXISTS trg_parent_profiles_updated_at ON parent_profiles;
CREATE TRIGGER trg_parent_profiles_updated_at
    BEFORE UPDATE ON parent_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 4. Family Profiles Table
CREATE TABLE IF NOT EXISTS family_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    preferred_name VARCHAR(128) NOT NULL DEFAULT 'Family Member',
    relationship_type VARCHAR(64) NOT NULL DEFAULT 'Child',
    language_pref VARCHAR(10) NOT NULL DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_family_profiles_user_id ON family_profiles(user_id);

DROP TRIGGER IF EXISTS trg_family_profiles_updated_at ON family_profiles;
CREATE TRIGGER trg_family_profiles_updated_at
    BEFORE UPDATE ON family_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Family Relationships Table
CREATE TABLE IF NOT EXISTS family_relationships (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship_type VARCHAR(64) NOT NULL DEFAULT 'Child',
    status VARCHAR(32) NOT NULL DEFAULT 'APPROVED',
    can_view_health BOOLEAN NOT NULL DEFAULT TRUE,
    can_view_cctv BOOLEAN NOT NULL DEFAULT TRUE,
    can_receive_sos BOOLEAN NOT NULL DEFAULT TRUE,
    phone VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_parent_family_relationship UNIQUE (parent_id, family_user_id)
);

CREATE INDEX IF NOT EXISTS idx_family_relationships_parent_id ON family_relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_family_relationships_family_user_id ON family_relationships(family_user_id);
CREATE INDEX IF NOT EXISTS idx_family_relationships_status ON family_relationships(status);
CREATE INDEX IF NOT EXISTS idx_family_relationships_phone ON family_relationships(phone);

DROP TRIGGER IF EXISTS trg_family_relationships_updated_at ON family_relationships;
CREATE TRIGGER trg_family_relationships_updated_at
    BEFORE UPDATE ON family_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 6. Trusted Contacts Table
CREATE TABLE IF NOT EXISTS trusted_contacts (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES parent_profiles(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    relationship_type VARCHAR(64) NOT NULL DEFAULT 'Neighbor',
    phone VARCHAR(32) NOT NULL,
    priority_order INTEGER NOT NULL DEFAULT 1,
    can_receive_sos BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trusted_contacts_parent_id ON trusted_contacts(parent_id);
CREATE INDEX IF NOT EXISTS idx_trusted_contacts_phone ON trusted_contacts(phone);

DROP TRIGGER IF EXISTS trg_trusted_contacts_updated_at ON trusted_contacts;
CREATE TRIGGER trg_trusted_contacts_updated_at
    BEFORE UPDATE ON trusted_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

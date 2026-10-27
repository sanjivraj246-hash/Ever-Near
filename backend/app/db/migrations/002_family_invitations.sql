-- EVER NEAR AI — Migration 002: Family Invitations Table
-- Supports secure parent-family connection codes with expiry, single-use, and granular permissions

CREATE TABLE IF NOT EXISTS family_invitations (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invite_code VARCHAR(32) NOT NULL UNIQUE,
    relationship_type VARCHAR(64) NOT NULL DEFAULT 'Child',
    invited_phone VARCHAR(32),
    can_view_health BOOLEAN NOT NULL DEFAULT TRUE,
    can_view_cctv BOOLEAN NOT NULL DEFAULT TRUE,
    can_receive_sos BOOLEAN NOT NULL DEFAULT TRUE,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_family_invitations_parent_id ON family_invitations(parent_id);
CREATE INDEX IF NOT EXISTS idx_family_invitations_invite_code ON family_invitations(invite_code);
CREATE INDEX IF NOT EXISTS idx_family_invitations_invited_phone ON family_invitations(invited_phone);

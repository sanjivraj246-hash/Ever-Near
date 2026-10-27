"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-25 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # 2. parent_profiles
    op.create_table(
        'parent_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('preferred_name', sa.String(length=128), nullable=False, server_default='Amma'),
        sa.Column('age', sa.Integer(), nullable=True, server_default='72'),
        sa.Column('emergency_notes', sa.Text(), nullable=True),
        sa.Column('language_pref', sa.String(length=10), nullable=False, server_default='ta'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parent_profiles_user_id'), 'parent_profiles', ['user_id'], unique=True)
    op.create_index(op.f('ix_parent_profiles_id'), 'parent_profiles', ['id'], unique=False)

    # 3. family_profiles
    op.create_table(
        'family_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('preferred_name', sa.String(length=128), nullable=False, server_default='Family Member'),
        sa.Column('relationship_type', sa.String(length=64), nullable=False, server_default='Child'),
        sa.Column('language_pref', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_family_profiles_user_id'), 'family_profiles', ['user_id'], unique=True)
    op.create_index(op.f('ix_family_profiles_id'), 'family_profiles', ['id'], unique=False)

    # 4. family_relationships
    op.create_table(
        'family_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('family_user_id', sa.Integer(), nullable=False),
        sa.Column('relationship_type', sa.String(length=64), nullable=False, server_default='Child'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='APPROVED'),
        sa.Column('can_view_health', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('can_view_cctv', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('can_receive_sos', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['family_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_id', 'family_user_id', name='uq_parent_family_relationship')
    )
    op.create_index(op.f('ix_family_relationships_family_user_id'), 'family_relationships', ['family_user_id'], unique=False)
    op.create_index(op.f('ix_family_relationships_parent_id'), 'family_relationships', ['parent_id'], unique=False)
    op.create_index(op.f('ix_family_relationships_phone'), 'family_relationships', ['phone'], unique=False)
    op.create_index(op.f('ix_family_relationships_status'), 'family_relationships', ['status'], unique=False)
    op.create_index(op.f('ix_family_relationships_id'), 'family_relationships', ['id'], unique=False)

    # 5. trusted_contacts
    op.create_table(
        'trusted_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('relationship_type', sa.String(length=64), nullable=False, server_default='Neighbor'),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('priority_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('can_receive_sos', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['parent_id'], ['parent_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trusted_contacts_parent_id'), 'trusted_contacts', ['parent_id'], unique=False)
    op.create_index(op.f('ix_trusted_contacts_phone'), 'trusted_contacts', ['phone'], unique=False)
    op.create_index(op.f('ix_trusted_contacts_id'), 'trusted_contacts', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('trusted_contacts')
    op.drop_table('family_relationships')
    op.drop_table('family_profiles')
    op.drop_table('parent_profiles')
    op.drop_table('users')

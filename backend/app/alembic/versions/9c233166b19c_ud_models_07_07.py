"""ud models 07.07

Revision ID: 9c233166b19c
Revises: 051bb31e0ea6
Create Date: 2025-07-07 11:06:56.461383

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9c233166b19c'
down_revision = '051bb31e0ea6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_projectlist_name'), table_name='projectlist')
    op.alter_column('request', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    op.drop_index(op.f('ix_request_approver_id'), table_name='request')
    op.drop_index(op.f('ix_request_id'), table_name='request')
    op.drop_index(op.f('ix_request_project_id'), table_name='request')
    op.drop_index(op.f('ix_request_requester_id'), table_name='request')
    op.drop_index(op.f('ix_request_role_id'), table_name='request')
    op.add_column('role', sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.drop_index(op.f('ix_role_name'), table_name='role')
    op.create_index(op.f('ix_role_name'), 'role', ['name'], unique=False)
    op.alter_column('user', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('user', 'creation_time',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.alter_column('user', 'creation_time',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.alter_column('user', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.drop_index(op.f('ix_role_name'), table_name='role')
    op.create_index(op.f('ix_role_name'), 'role', ['name'], unique=True)
    op.drop_column('role', 'description')
    op.create_index(op.f('ix_request_role_id'), 'request', ['role_id'], unique=False)
    op.create_index(op.f('ix_request_requester_id'), 'request', ['requester_id'], unique=False)
    op.create_index(op.f('ix_request_project_id'), 'request', ['project_id'], unique=False)
    op.create_index(op.f('ix_request_id'), 'request', ['id'], unique=False)
    op.create_index(op.f('ix_request_approver_id'), 'request', ['approver_id'], unique=False)
    op.alter_column('request', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.create_index(op.f('ix_projectlist_name'), 'projectlist', ['name'], unique=False)
    # ### end Alembic commands ###

"""initial setup

Revision ID: 973c1a668559
Revises: 
Create Date: 2025-07-04 14:04:03.030827

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '973c1a668559'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('projectlist',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('address', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    sa.Column('investor', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projectlist_name'), 'projectlist', ['name'], unique=False)
    op.create_table('role',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_role_name'), 'role', ['name'], unique=True)
    op.create_table('user',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('creation_time', sa.DateTime(), nullable=False),
    sa.Column('role_assignment_time', sa.DateTime(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('last_logout', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_table('request',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('requester_id', sa.Uuid(), nullable=False),
    sa.Column('approver_id', sa.Uuid(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('request_message', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
    sa.Column('response_message', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['approver_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projectlist.id'], ),
    sa.ForeignKeyConstraint(['requester_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_request_approver_id'), 'request', ['approver_id'], unique=False)
    op.create_index(op.f('ix_request_id'), 'request', ['id'], unique=False)
    op.create_index(op.f('ix_request_project_id'), 'request', ['project_id'], unique=False)
    op.create_index(op.f('ix_request_requester_id'), 'request', ['requester_id'], unique=False)
    op.create_index(op.f('ix_request_role_id'), 'request', ['role_id'], unique=False)
    op.create_table('userprojectrole',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projectlist.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'project_id', 'role_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('userprojectrole')
    op.drop_index(op.f('ix_request_role_id'), table_name='request')
    op.drop_index(op.f('ix_request_requester_id'), table_name='request')
    op.drop_index(op.f('ix_request_project_id'), table_name='request')
    op.drop_index(op.f('ix_request_id'), table_name='request')
    op.drop_index(op.f('ix_request_approver_id'), table_name='request')
    op.drop_table('request')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_role_name'), table_name='role')
    op.drop_table('role')
    op.drop_index(op.f('ix_projectlist_name'), table_name='projectlist')
    op.drop_table('projectlist')
    # ### end Alembic commands ###

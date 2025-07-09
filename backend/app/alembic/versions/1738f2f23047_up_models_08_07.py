"""UP models 08.07

Revision ID: 1738f2f23047
Revises: 81b63089d054
Create Date: 2025-07-08 13:04:14.084856

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '1738f2f23047'
down_revision = '81b63089d054'
branch_labels = None
depends_on = None


def upgrade():
    # Tạo ENUM trước khi sử dụng
    request_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', name='requeststatus')
    request_status_enum.create(op.get_bind())

    # Sửa kiểu dữ liệu cột status với USING
    op.execute("ALTER TABLE request ALTER COLUMN status TYPE requeststatus USING status::requeststatus")

    # Các thay đổi khác (tuỳ bạn có thể giữ hoặc xoá nếu không cần)
    op.drop_index(op.f('ix_projectlist_name'), table_name='projectlist')
    op.drop_index(op.f('ix_role_name'), table_name='role')
    op.alter_column('user', 'email', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('user', 'creation_time', existing_type=postgresql.TIMESTAMP(), nullable=False)

def downgrade():
    # Đổi ngược kiểu ENUM về VARCHAR
    op.execute("ALTER TABLE request ALTER COLUMN status TYPE VARCHAR(50) USING status::VARCHAR")

    # Drop ENUM sau khi không còn dùng
    request_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', name='requeststatus')
    request_status_enum.drop(op.get_bind())

    # Khôi phục lại cột khác nếu có
    op.alter_column('user', 'creation_time', existing_type=postgresql.TIMESTAMP(), nullable=True)
    op.alter_column('user', 'email', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.create_index(op.f('ix_role_name'), 'role', ['name'], unique=True)
    op.create_index(op.f('ix_projectlist_name'), 'projectlist', ['name'], unique=False)
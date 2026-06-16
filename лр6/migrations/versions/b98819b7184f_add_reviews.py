"""Add reviews

Revision ID: b98819b7184f
Revises: 996046246e30
Create Date: 2026-05-17 23:09:45.269266

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b98819b7184f'
down_revision = '996046246e30'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.CheckConstraint('rating >= 0 AND rating <= 5', name=op.f('ck_reviews_rating_range')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_reviews_course_id_courses')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_reviews_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reviews')),
    sa.UniqueConstraint('course_id', 'user_id', name='unique_course_user_review')
    )


def downgrade():
    op.drop_table('reviews')

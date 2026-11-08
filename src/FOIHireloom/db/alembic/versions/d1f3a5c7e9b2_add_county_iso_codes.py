"""add county iso codes

Revision ID: d1f3a5c7e9b2
Revises: 0bd648598d5c
Create Date: 2026-11-02 14:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd1f3a5c7e9b2'
down_revision: str | Sequence[str] | None = '0bd648598d5c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTIES = (
    ('zagrebacka', 'Zagrebačka županija', 'HR-01'),
    ('krapinsko-zagorska', 'Krapinsko-zagorska županija', 'HR-02'),
    ('sisacko-moslavacka', 'Sisačko-moslavačka županija', 'HR-03'),
    ('karlovacka', 'Karlovačka županija', 'HR-04'),
    ('varazdinska', 'Varaždinska županija', 'HR-05'),
    ('koprivnicko-krizevacka', 'Koprivničko-križevačka županija', 'HR-06'),
    ('bjelovarsko-bilogorska', 'Bjelovarsko-bilogorska županija', 'HR-07'),
    ('primorsko-goranska', 'Primorsko-goranska županija', 'HR-08'),
    ('licko-senjska', 'Ličko-senjska županija', 'HR-09'),
    ('viroviticko-podravska', 'Virovitičko-podravska županija', 'HR-10'),
    ('pozesko-slavonska', 'Požeško-slavonska županija', 'HR-11'),
    ('brodsko-posavska', 'Brodsko-posavska županija', 'HR-12'),
    ('zadarska', 'Zadarska županija', 'HR-13'),
    ('osjecko-baranjska', 'Osječko-baranjska županija', 'HR-14'),
    ('sibensko-kninska', 'Šibensko-kninska županija', 'HR-15'),
    ('vukovarsko-srijemska', 'Vukovarsko-srijemska županija', 'HR-16'),
    ('splitsko-dalmatinska', 'Splitsko-dalmatinska županija', 'HR-17'),
    ('istarska', 'Istarska županija', 'HR-18'),
    ('dubrovacko-neretvanska', 'Dubrovačko-neretvanska županija', 'HR-19'),
    ('medimurska', 'Međimurska županija', 'HR-20'),
    ('grad-zagreb', 'Grad Zagreb', 'HR-21'),
)


def upgrade() -> None:
    op.add_column('counties', sa.Column('iso_code', sa.Text(), nullable=True))
    catalog = sa.values(
        sa.column('code', sa.Text), sa.column('name', sa.Text), sa.column('iso_code', sa.Text), name='catalog'
    ).data(COUNTIES)
    counties = sa.table('counties', sa.column('code'), sa.column('name'), sa.column('iso_code'))
    assigned = counties.alias('assigned')
    for column in ('code', 'name'):
        op.execute(
            counties.update()
            .where(
                counties.c[column] == catalog.c[column],
                counties.c.iso_code.is_(None),
                ~sa.exists().where(assigned.c.iso_code == catalog.c.iso_code),
            )
            .values(iso_code=catalog.c.iso_code)
        )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM counties WHERE iso_code IS NULL) THEN "
        "RAISE EXCEPTION 'Counties without an ISO 3166-2:HR code: %', "
        "(SELECT string_agg(code, ', ' ORDER BY code) FROM counties WHERE iso_code IS NULL); "
        "END IF; END $$"
    )
    op.alter_column('counties', 'iso_code', nullable=False)
    op.create_unique_constraint(op.f('uq_counties_iso_code'), 'counties', ['iso_code'])
    op.create_check_constraint(
        op.f('ck_counties_iso_code_valid'), 'counties', "iso_code ~ '^HR-(0[1-9]|1[0-9]|2[01])$'"
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_counties_iso_code_valid'), 'counties', type_='check')
    op.drop_constraint(op.f('uq_counties_iso_code'), 'counties', type_='unique')
    op.drop_column('counties', 'iso_code')

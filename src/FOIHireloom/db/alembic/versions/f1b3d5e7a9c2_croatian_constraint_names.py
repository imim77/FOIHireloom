"""Name primary keys id and give every constraint a Croatian name.

Revision ID: f1b3d5e7a9c2
Revises: e0a2c4e6f8b0

Foreign keys are id_<table>, so the primary key they point to is id. CHECK
names follow the Croatian columns they guard, and NOT NULL constraints take
PostgreSQL's default <table>_<column>_not_null form. Only names change.
Downgrade renames NOT NULL constraints by the same rule, so their English
names from before e0a2c4e6f8b0 are not restored; nothing reads them.
"""

from alembic import op

revision = "f1b3d5e7a9c2"
down_revision = "e0a2c4e6f8b0"
branch_labels = None
depends_on = None

TABLES = ['zupanije',
 'oglasi',
 'uvozi_dzs',
 'datoteke_uvoza_dzs',
 'vrijednosti_pokazatelja_dzs',
 'izvorni_kanali',
 'sinkronizacije']
APPLICATION_TABLES = [*TABLES, "pripadnosti_oglasa_kanalima"]

CHECKS = [['zupanije', 'ck_zupanije_code_not_blank', 'ck_zupanije_sifra_nije_prazna'],
 ['zupanije', 'ck_zupanije_name_not_blank', 'ck_zupanije_naziv_nije_prazan'],
 ['zupanije', 'ck_zupanije_iso_code_valid', 'ck_zupanije_iso_sifra_ispravna'],
 ['oglasi', 'ck_oglasi_url_not_blank', 'ck_oglasi_izvorni_url_nije_prazan'],
 ['oglasi', 'ck_oglasi_hash_not_blank', 'ck_oglasi_sazetak_sadrzaja_nije_prazan'],
 ['oglasi', 'ck_oglasi_observation_times_ordered', 'ck_oglasi_vremena_opazanja_redom'],
 ['oglasi', 'ck_oglasi_category_source_recorded', 'ck_oglasi_izvor_kategorije_zabiljezen'],
 ['oglasi', 'ck_oglasi_content_change_within_observation', 'ck_oglasi_promjena_unutar_opazanja'],
 ['oglasi', 'ck_oglasi_page_status_known', 'ck_oglasi_stanje_stranice_poznato'],
 ['oglasi', 'ck_oglasi_page_check_recorded', 'ck_oglasi_provjera_stranice_zabiljezena'],
 ['oglasi', 'ck_oglasi_page_fetch_recorded', 'ck_oglasi_dohvat_stranice_zabiljezen'],
 ['oglasi', 'ck_oglasi_conditions_known', 'ck_oglasi_uvjeti_poznati'],
 ['oglasi', 'ck_oglasi_experience_consistent', 'ck_oglasi_iskustvo_dosljedno'],
 ['oglasi', 'ck_oglasi_weekly_hours_positive', 'ck_oglasi_tjedni_sati_pozitivni'],
 ['oglasi', 'ck_oglasi_conditions_need_page', 'ck_oglasi_uvjeti_traze_stranicu'],
 ['uvozi_dzs', 'ck_uvozi_dzs_status_valid', 'ck_uvozi_dzs_stanje_ispravno'],
 ['uvozi_dzs', 'ck_uvozi_dzs_completion_matches_status', 'ck_uvozi_dzs_zavrsetak_prema_stanju'],
 ['uvozi_dzs', 'ck_uvozi_dzs_success_has_counts', 'ck_uvozi_dzs_uspjeh_ima_brojace'],
 ['uvozi_dzs', 'ck_uvozi_dzs_failure_has_error', 'ck_uvozi_dzs_neuspjeh_ima_gresku'],
 ['uvozi_dzs', 'ck_uvozi_dzs_counts_nonnegative', 'ck_uvozi_dzs_brojaci_nenegativni'],
 ['datoteke_uvoza_dzs', 'ck_datoteke_uvoza_dzs_role_valid', 'ck_datoteke_uvoza_dzs_uloga_ispravna'],
 ['datoteke_uvoza_dzs', 'ck_datoteke_uvoza_dzs_location_not_blank', 'ck_datoteke_uvoza_dzs_lokacija_nije_prazna'],
 ['datoteke_uvoza_dzs', 'ck_datoteke_uvoza_dzs_sha256_valid', 'ck_datoteke_uvoza_dzs_sha256_ispravan'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_indicator_valid',
  'ck_vrijednosti_pokazatelja_dzs_pokazatelj_ispravan'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_sex_valid',
  'ck_vrijednosti_pokazatelja_dzs_spol_ispravan'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_period_is_month_start',
  'ck_vrijednosti_pokazatelja_dzs_razdoblje_pocinje_mjesecom'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_missing_reason_valid',
  'ck_vrijednosti_pokazatelja_dzs_razlog_nedostupnosti_ispravan'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_value_or_missing_reason',
  'ck_vrijednosti_pokazatelja_dzs_vrijednost_ili_razlog'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_value_in_unit',
  'ck_vrijednosti_pokazatelja_dzs_vrijednost_u_jedinici'],
 ['vrijednosti_pokazatelja_dzs',
  'ck_vrijednosti_pokazatelja_dzs_source_has_indicator',
  'ck_vrijednosti_pokazatelja_dzs_izvor_ima_pokazatelj'],
 ['pripadnosti_oglasa_kanalima',
  'ck_pripadnosti_oglasa_kanalima_timestamps_ordered',
  'ck_pripadnosti_oglasa_kanalima_vremena_opazanja_redom'],
 ['pripadnosti_oglasa_kanalima',
  'ck_pripadnosti_oglasa_kanalima_presence_matches_missing_time',
  'ck_pripadnosti_oglasa_kanalima_prisutnost_prema_nestanku'],
 ['izvorni_kanali', 'ck_izvorni_kanali_label_not_blank', 'ck_izvorni_kanali_oznaka_nije_prazna'],
 ['izvorni_kanali', 'ck_izvorni_kanali_url_not_blank', 'ck_izvorni_kanali_url_kanala_nije_prazan'],
 ['izvorni_kanali', 'ck_izvorni_kanali_scope_matches_county', 'ck_izvorni_kanali_opseg_prema_zupaniji'],
 ['izvorni_kanali', 'ck_izvorni_kanali_success_not_after_check', 'ck_izvorni_kanali_uspjeh_ne_nakon_provjere'],
 ['izvorni_kanali',
  'ck_izvorni_kanali_mapping_verified_for_occupation',
  'ck_izvorni_kanali_pridruzivanje_provjereno_za_zanimanje'],
 ['izvorni_kanali',
  'ck_izvorni_kanali_mapping_evidence_consistent',
  'ck_izvorni_kanali_primjeri_pridruzivanja_dosljedni'],
 ['sinkronizacije', 'ck_sinkronizacije_status_valid', 'ck_sinkronizacije_stanje_ispravno'],
 ['sinkronizacije', 'ck_sinkronizacije_completion_matches_status', 'ck_sinkronizacije_zavrsetak_prema_stanju'],
 ['sinkronizacije', 'ck_sinkronizacije_http_status_valid', 'ck_sinkronizacije_http_status_ispravan'],
 ['sinkronizacije', 'ck_sinkronizacije_success_requires_http_200', 'ck_sinkronizacije_uspjeh_trazi_http_200'],
 ['sinkronizacije',
  'ck_sinkronizacije_not_modified_requires_http_304',
  'ck_sinkronizacije_nepromijenjeno_trazi_http_304'],
 ['sinkronizacije', 'ck_sinkronizacije_items_seen_nonnegative', 'ck_sinkronizacije_broj_videnih_stavki_nenegativan'],
 ['sinkronizacije', 'ck_sinkronizacije_items_added_nonnegative', 'ck_sinkronizacije_broj_dodanih_stavki_nenegativan'],
 ['sinkronizacije',
  'ck_sinkronizacije_items_updated_nonnegative',
  'ck_sinkronizacije_broj_azuriranih_stavki_nenegativan'],
 ['sinkronizacije',
  'ck_sinkronizacije_items_invalid_nonnegative',
  'ck_sinkronizacije_broj_neispravnih_stavki_nenegativan']]
UNIQUES = [["vrijednosti_pokazatelja_dzs", "uq_vrijednosti_pokazatelja_dzs_id_zupanije_pokazatelj_r_c673",
            "uq_vrijednosti_pokazatelja_dzs_prirodni_kljuc"]]


def _rename_constraints(pairs: list[list[str]], reverse: bool) -> None:
    for table, english, croatian in pairs:
        before, after = (croatian, english) if reverse else (english, croatian)
        op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{before}" TO "{after}"')


def _rename_primary_keys(before: str, after: str) -> None:
    for table in TABLES:
        op.alter_column(table, before, new_column_name=after)
        op.execute(f'ALTER SEQUENCE "{table}_{before}_seq" RENAME TO "{table}_{after}_seq"')


def _name_not_null_constraints() -> None:
    tables = ", ".join(f"'{table}'" for table in APPLICATION_TABLES)
    op.execute(f"""
        DO $$ DECLARE r record; BEGIN
            FOR r IN
                SELECT c.conrelid::regclass::text AS tbl, c.conname, c.conrelid::regclass::text || '_' || a.attname || '_not_null' AS target
                FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                WHERE c.contype = 'n' AND c.conrelid::regclass::text IN ({tables})
            LOOP
                IF length(r.target) > 63 THEN
                    RAISE EXCEPTION 'NOT NULL constraint name too long: %', r.target;
                END IF;
                IF r.conname <> r.target THEN
                    EXECUTE format('ALTER TABLE %I RENAME CONSTRAINT %I TO %I', r.tbl, r.conname, r.target);
                END IF;
            END LOOP;
        END $$
    """)


def upgrade() -> None:
    op.execute("LOCK TABLE " + ", ".join(f'"{table}"' for table in APPLICATION_TABLES) + " IN ACCESS EXCLUSIVE MODE")
    _rename_primary_keys("identifikator", "id")
    _rename_constraints(CHECKS + UNIQUES, reverse=False)
    _name_not_null_constraints()


def downgrade() -> None:
    op.execute("LOCK TABLE " + ", ".join(f'"{table}"' for table in APPLICATION_TABLES) + " IN ACCESS EXCLUSIVE MODE")
    _rename_constraints(CHECKS + UNIQUES, reverse=True)
    _rename_primary_keys("id", "identifikator")
    _name_not_null_constraints()

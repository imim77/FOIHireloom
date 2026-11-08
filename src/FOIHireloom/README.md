# Backend design

MCP tools translate protocol arguments and application errors. Services coordinate
use cases through repository contracts and a caller-supplied `UnitOfWorkFactory`.
SQLAlchemy repositories own SQL and participate in the transaction opened by the
service; they never commit the caller's work.

Concrete dependencies are assembled in `factories/`. `DependencyService` owns
their infrastructure lifetimes. Commands receive typed service openers, so they
can run against another implementation without constructing a database or HTTP
client. The CLI `main()` functions supply the default composition.

The MCP lifespan opens both read services through `read_services()`. They share
one database pool, while each operation opens its own Unit of Work and session.
Injected service openers retain their own cleanup. When both are supplied, the
default database is never opened; partial startup failures unwind resources in
reverse order. Dry-run import and registration also skip database construction.

Responsibilities that change independently have their own modules:

- `domain/` owns search text folding, stemming, query normalization, Croatian
  calendar days and cursor encoding. It has no database or network dependencies.
- `services/concrete/job_presentation.py` maps stored feed and page values to
  result DTOs. Previously fetched page values survive a later fetch failure.
- `services/concrete/county_indicator_calculation.py` computes ratios and monthly
  changes, preserving missing values, unavailable reasons and provisional flags.
- `dao/concrete/job_predicates.py` supplies the common SQL rules for search,
  statistics and county counts, including unknown values and effective deadlines.
- `api/job_filters.py` defines the shared MCP filter annotations and descriptions.

- `services/concrete/labour_forecast.py` forecasts county series with Amazon
  Chronos (`integrations/concrete/chronos.py`); one loader per target in
  `labour_forecast_series.py` supplies DZS monthly values or weekly HZZ ad
  counts. Chronos is the optional `forecast` extra and loads on the first
  forecast, so the server and tests run without torch.

Import implementations and contracts from their defining modules. Service and
factory package initializers do not eagerly import unrelated implementations.

MCP descriptions route by user intent. The seven `show_` workflows return data and
their appropriate app without requiring a display-format request. Raw search
and comparison counterparts remain callable with app-only visibility so they do
not compete for model selection. Hosts that ignore visibility receive explicit
routing guidance too. See [routing evaluation](../../evals/README.md) for client
regression cases and recorded-call scoring.

`show_labour_market_forecast` presents one county's Chronos history, forecast
medians, 80% intervals and exact values. `forecast_labour_market` stays available
as an app-only endpoint for raw forecasts of up to six counties. Both use the
same forecast service; presentation does not run another inference or alter
predictions. Start with `uv run --locked --extra forecast foihireloom-mcp` after
installing the optional extra with `uv sync --locked --extra forecast`.

`foihireloom-forecast-accuracy` backtests DZS unemployment-rate forecasts on
rolling monthly origins against a prior-year seasonal baseline. It reports
MAE, interval coverage, paired monthly evidence and skipped windows without
writing to the database. See [forecast accuracy](FORECAST_ACCURACY.md) for
commands, metrics and the limitations of evaluating revised source data.

Use `show_jobs(skills=["csharp", "python"])` for programming languages or tools.
An ad must mention at least one requested skill; title matches come first when
`query` is also set, then ads with more requested skills, then newest ads.
`matched_skills` identifies the explicit matches. The same filter is available
in job statistics and county comparisons; it does not affect county-wide ratios.
An empty skill list leaves search unfiltered. Text queries keep their AND-prefix
semantics, so use `query` for occupations or foreign languages.

Skill tags come from a generated database column over page text, falling back
to feed text. Apply Alembic revision `f3b5d7e9a1c2` before running this version.
Changes to `domain/skill_catalog.py` require a new migration with a frozen
expression. When direct matches are sparse, tool guidance asks the model to
offer related occupation/category results in a separate search without skills.
That fallback is model behavior; the server returns only direct matches.

Run `.venv/bin/python -m unittest discover -s tests` from the repository root.
HTTP transport tests need local loopback sockets. Tests for service orchestration,
calculations, command injection and resource cleanup use injected dependencies
and need no PostgreSQL server. Build the frontend before testing MCP App resources
when its sources have changed.

## Database storage

Apply migrations with `.venv/bin/alembic -c src/FOIHireloom/db/alembic/alembic.ini upgrade head`.
Revision `a6c8e0f2b4d6` removes four unused tables (`employers`,
`web_documents`, `employer_web_documents`, `job_web_documents`) and five
`jobs` columns (`employer_id`, `description_raw`, `availability_status`,
`availability_evidence_url`, `availability_checked_at`). Employer names come
from `jobs.page_employer_name`. Job detail responses retain
`availability_status="unknown"`; this app does not confirm availability.
The RSS snippet is parsed and hashed in memory; only its cleaned description,
parsed fields and hash are stored. Downgrade restores the old schema but cannot
recover discarded snippets. The migration refuses to remove legacy tables or
availability fields containing meaningful data.

The eight application tables are `counties`, `source_feeds`, `jobs`,
`job_feed_memberships`, `sync_runs`, `dzs_imports`, `dzs_import_files` and
`dzs_indicator_values`. Feed memberships retain county/category evidence and
missing/returned observations. Sync runs protect against unexpectedly truncated
feeds. DZS import records and files retain provenance; indicator values support
county comparisons, history and forecasts. Raw page conditions and normalized
conditions both stay: results show the source wording, while SQL filters use
normalized codes and the normalization command can rebuild them.

Current ORM models in `db/models/` are the schema reference. Earlier database
planning diagrams describe a broader design and include storage since removed.


Revisions `b7d9f1a3c5e7` and `c8e0a2b4d6f8` simplify storage: jobs use HZZ
source IDs directly; DZS values retain their last-writing import without
per-value audit timestamps. The import command still computes `size_bytes`
for its result, while the database retains SHA-256 and source provenance.
Revision `d9f1b3c5e7a9` indexes `upper(category)` and
`coalesce(page_valid_until, deadline_on)`, the expressions job filters compare.

Run PostgreSQL regressions against a migrated, disposable copy of the seeded
database (counties, at least two jobs and an occupation feed):
`TEST_DATABASE_URL=postgresql+asyncpg://... .venv/bin/python -m unittest discover -s tests`.
Without `TEST_DATABASE_URL`, the six integration tests are skipped. Each
integration test rolls back business writes, including service commits.


Croatian SQL naming comes from revisions `e0a2c4e6f8b0` and `f1b3d5e7a9c2`. The eight application
tables and their columns have Croatian names without diacritics. Models use
explicit `mapped_column` names with stable English attribute/Core keys, so
public DTOs and MCP arguments keep their existing names. SQL constraints,
generated expressions, indexes and identity sequences follow the renamed schema.
The database name `myapp` and Alembic's internal version table stay unchanged.
Primary keys are `id`, so a foreign key `id_<table>` points to `<table>.id`;
CHECK names are Croatian and NOT NULL constraints use `<table>_<column>_not_null`.
The six PostgreSQL regressions include physical catalog names, generated search
and the Core batch category update. Schema inventory and the full naming map
are in `docs/database-era.md` and `docs/database-croatian-names.md`.

## Pokretanje pomoću Makefilea

Kopiraj `.env.example` u `.env` i po potrebi promijeni `DATABASE_URL`.
Za lokalnu Docker Compose bazu zadana adresa odgovara konfiguraciji projekta.
Potrebni su `uv`, Node.js, npm i Docker Compose. `make start` pri prvom
pokretanju instalira ovisnosti, pokreće PostgreSQL 18 bazu i u prazan Docker
volumen učitava `data/initial.sql.gz`, primjenjuje migracije te gradi MCP App prikaze. Zatim pokreće
HTTP MCP poslužitelj na `http://127.0.0.1:8000/mcp`. Instalacija ovisnosti i Docker slike zahtijeva
internetsku vezu; početni podaci dolaze iz priložene snimke. Poslužitelj se zaustavlja s Ctrl+C.

Za već pokrenutu vanjsku bazu koristi `make start LOCAL_DATABASE=0`, uz njezin
`DATABASE_URL` u `.env`; time se preskače pokretanje Docker baze i snimka se
ne učitava, nego se pri početnoj pripremi uvoze podaci s interneta. `make setup`
ponavlja pripremu bez zamjene postojeće lokalne baze, a `make help` prikazuje pojedinačne naredbe. `make stop`
zaustavlja lokalnu bazu; `make down-volumes` trajno briše njezine podatke.
`make export-db` osvježava priloženu snimku iz lokalne Docker Compose baze.
Za prognoziranje pokreni poslužitelj s `make start UV_EXTRA="--extra forecast"`.

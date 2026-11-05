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

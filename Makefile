.DEFAULT_GOAL := help

LOCAL_DATABASE ?= 1
UV_EXTRA ?=
SETUP_STAMP := .setup-done
ALEMBIC := uv run --locked alembic -c src/FOIHireloom/db/alembic/alembic.ini

help: ## Prikaži dostupne naredbe.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

start: ## Pripremi projekt pri prvom pokretanju i pokreni MCP na portu 8000.
	@test -f $(SETUP_STAMP) || $(MAKE) setup
	@if [ "$(LOCAL_DATABASE)" = 1 ]; then $(MAKE) up; fi
	$(MAKE) migrate
	$(MAKE) build-frontend
	$(MAKE) run-mcp

setup: ## Instaliraj ovisnosti, pripremi početnu bazu i izgradi prikaze.
	@rm -f $(SETUP_STAMP)
	$(MAKE) sync
	$(MAKE) install-frontend
	@if [ "$(LOCAL_DATABASE)" = 1 ]; then $(MAKE) up; fi
	$(MAKE) migrate
	@if [ "$(LOCAL_DATABASE)" != 1 ]; then \
		$(MAKE) register-sources && $(MAKE) sync-jobs && $(MAKE) import-dzs; \
	fi
	$(MAKE) build-frontend
	@touch $(SETUP_STAMP)

sync: ## Instaliraj Python ovisnosti pomoću uv-a.
	uv sync --locked

install-frontend: ## Instaliraj frontend ovisnosti iz lock datoteke.
	npm --prefix frontend ci

up: ## Pokreni lokalnu PostgreSQL bazu i pričekaj spremnost.
	docker compose up -d
	@attempt=0; until docker compose exec -T postgres pg_isready -h 127.0.0.1 -U myuser -d myapp >/dev/null 2>&1; do \
		attempt=$$((attempt + 1)); \
		if [ $$attempt -ge 60 ]; then echo 'PostgreSQL nije spreman nakon 60 sekundi.' >&2; exit 1; fi; \
		sleep 1; \
	done

down: ## Zaustavi lokalnu bazu i sačuvaj podatke.
	docker compose down

stop: down ## Zaustavi lokalnu bazu; MCP poslužitelj zaustavlja se s Ctrl+C.

down-volumes: ## Zaustavi bazu i trajno izbriši Docker volumen s podacima.
	docker compose down -v
	@rm -f $(SETUP_STAMP)

export-db: ## Osvježi početnu snimku iz lokalne Docker Compose baze.
	@set -e; snapshot=$$(mktemp); \
	trap 'rm -f "$$snapshot" "$$snapshot.gz"' EXIT; \
	docker compose exec -T postgres pg_dump -U myuser -d myapp --no-owner --no-privileges > "$$snapshot"; \
	gzip -n -c "$$snapshot" > "$$snapshot.gz"; \
	chmod 644 "$$snapshot.gz"; \
	mv "$$snapshot.gz" data/initial.sql.gz

migrate: ## Primijeni migracije na bazu iz DATABASE_URL.
	$(ALEMBIC) upgrade head

create-migrations: ## Izradi migraciju: make create-migrations MESSAGE="opis".
	@test -n "$(MESSAGE)" || { echo 'Zadaj MESSAGE="opis".' >&2; exit 1; }
	$(ALEMBIC) revision --autogenerate -m "$(MESSAGE)"

register-sources: ## Registriraj izvore: make register-sources args="--dry-run".
	uv run --locked foihireloom-register-sources $(args)

sync-jobs: ## Uvezi oglase: make sync-jobs args="--feed-id 1".
	uv run --locked foihireloom-sync-jobs $(args)

fetch-job-pages: ## Preuzmi detalje oglasa: make fetch-job-pages args="--limit 10".
	uv run --locked foihireloom-fetch-job-pages $(args)

normalize-job-conditions: ## Normaliziraj uvjete zaposlenja iz detalja oglasa.
	uv run --locked foihireloom-normalize-job-conditions $(args)

import-dzs: ## Uvezi DZS podatke: make import-dzs args="--dry-run".
	uv run --locked foihireloom-import-dzs $(args)

category-snapshot: ## Izvezi kategorije: make category-snapshot args="--out snapshot.json".
	uv run --locked foihireloom-category-snapshot $(args)

forecast-accuracy: ## Procijeni prognozu: make forecast-accuracy args="--county Varazdinska".
	uv run --locked --extra forecast foihireloom-forecast-accuracy $(args)

run-mcp: ## Pokreni MCP HTTP poslužitelj: make run-mcp args="--port 8001".
	uv run --locked $(UV_EXTRA) foihireloom-mcp --transport http $(args)

run-frontend: ## Pokreni Vite razvojni poslužitelj za frontend.
	npm --prefix frontend run dev

build-frontend: ## Izgradi MCP App prikaze.
	npm --prefix frontend run build

lint-frontend: ## Provjeri frontend kod.
	npm --prefix frontend run lint

test: ## Pokreni Python testove; PostgreSQL testovi trebaju TEST_DATABASE_URL.
	uv run --locked python -m unittest discover -s tests -v $(args)

test-frontend: ## Pokreni frontend testove.
	npm --prefix frontend run test

test-browser: ## Pokreni frontend testove u pregledniku.
	npm --prefix frontend run test:browser

.PHONY: help start setup sync install-frontend up down stop down-volumes export-db migrate create-migrations register-sources sync-jobs fetch-job-pages normalize-job-conditions import-dzs category-snapshot forecast-accuracy run-mcp run-frontend build-frontend lint-frontend test test-frontend test-browser

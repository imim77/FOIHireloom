# FOIHireloom

FOIHireloom je MCP aplikacija za pretraživanje HZZ oglasa i pregled podataka o hrvatskom tržištu rada. Pomoću MCP klijenta mogu se pretraživati oglasi te pregledavati usporedbe i vizualizacije podataka po županijama.

## Preduvjeti

Za lokalno pokretanje potrebni su:

- [Git](https://git-scm.com/install/) i `make`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) i Python 3.14 ili noviji. `uv` može preuzeti odgovarajuću verziju Pythona ako nije instalirana.
- [Node.js](https://nodejs.org/) 22.12 ili noviji i npm.
- Pokrenut [Docker](https://docs.docker.com/get-docker/) s Docker Composeom.
- Internetska veza za preuzimanje ovisnosti i Docker slike pri prvom pokretanju.
- MCP klijent koji podržava Streamable HTTP; za vizualizacije klijent treba podržavati i MCP Apps.

Naredbe u nastavku pokreću se u terminalu iz korijenske mape projekta. Na Windowsu možete koristiti WSL s dostupnim Dockerom.

## Preuzimanje i pokretanje

1. Klonirajte repozitorij i uđite u mapu projekta:

   ```bash
   git clone https://github.com/imim77/FOIHireloom.git
   cd FOIHireloom
   ```

2. Pokrenite Docker, a zatim aplikaciju:

   ```bash
   make start
   ```

   Pri prvom pokretanju naredba instalira Python i frontend ovisnosti, pokreće PostgreSQL 18, učitava priloženu snimku baze, primjenjuje migracije i gradi prikaze. Priprema može potrajati. Za zadanu lokalnu bazu nije potrebna `.env` datoteka.

3. U MCP klijentu dodajte poslužitelj s adresom:

   ```text
   http://127.0.0.1:8000/mcp
   ```

   Poslužitelj mora ostati pokrenut dok koristite aplikaciju. Pokušajte, primjerice, zatražiti oglase za posao u određenoj županiji ili usporedbu podataka o županijama.

Za zaustavljanje MCP poslužitelja pritisnite **Ctrl+C** u njegovu terminalu. Zatim pokrenite `make stop` za zaustavljanje baze; podaci ostaju sačuvani. Za ponovno pokretanje koristite `make start`.

## Podaci i korisne naredbe

Početna snimka u `data/initial.sql.gz` sadrži HZZ oglase, podatke DZS-a i već dohvaćene detalje oglasa. Predstavlja stanje od 8. studenoga 2026., a ne podatke u stvarnom vremenu. Docker je učitava samo pri stvaranju praznog volumena baze; sljedeća pokretanja zadržavaju postojeće podatke.

| Naredba | Namjena |
| --- | --- |
| `make help` | Prikažite sve dostupne naredbe. |
| `make sync-jobs` | Osvježite oglase iz HZZ izvora. |
| `make import-dzs` | Osvježite podatke DZS-a. |
| `make fetch-job-pages` | Dohvatite dodatne detalje oglasa. |
| `make export-db` | Izvezite snimku trenutačne lokalne baze u `data/initial.sql.gz`. |
| `make test` | Pokrenite Python testove; PostgreSQL testovi trebaju `TEST_DATABASE_URL`. |
| `make test-frontend` | Pokrenite frontend testove. |

Za manji broj stranica pri dohvaćanju detalja koristite `make fetch-job-pages args="--limit 10"`. Dohvat i osvježavanje podataka zahtijevaju pristup odgovarajućim internetskim izvorima.

> [!WARNING]
> `make down-volumes` zaustavlja bazu i trajno briše njezin Docker volumen. Pri sljedećem pokretanju ponovno se učitava početna snimka.

## Vlastita baza i prognoziranje

Ako koristite postojeću PostgreSQL bazu, kopirajte `.env.example` u `.env`, postavite `DATABASE_URL` i pokrenite:

```bash
make start LOCAL_DATABASE=0
```

Baza mora biti dostupna prije pokretanja. U ovom načinu početna priprema registrira izvore i uvozi HZZ i DZS podatke s interneta umjesto učitavanja priložene snimke. `DATABASE_URL` sadrži pristupne podatke, pa `.env` nemojte dijeliti.

Za alate za prognoziranje pokrenite:

```bash
make start UV_EXTRA="--extra forecast"
```

Time se instaliraju dodatne ovisnosti; pri prvoj prognozi preuzima se model.

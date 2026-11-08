# FOIHireloom

FOIHireloom je MCP aplikacija za pretraživanje HZZ oglasa i pregled podataka o tržištu rada. MCP klijent prikazuje rezultate i pripadajuće vizualizacije.

## Lokalno pokretanje

Potrebni su Git, `make`, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 22 s npm-om te pokrenut Docker s Docker Composeom. Potrebna je i internetska veza za instalaciju ovisnosti i preuzimanje Docker slike.

Nakon preuzimanja repozitorija, u njegovoj glavnoj mapi pokreni:

```bash
make start
```

Pri prvom pokretanju naredba instalira ovisnosti, pokreće lokalnu PostgreSQL 18 bazu, automatski učitava priloženu snimku naše radne baze, primjenjuje migracije i gradi prikaze. Nije potrebno čekati novi uvoz HZZ i DZS podataka. Kad se poslužitelj pokrene, poveži MCP klijent na **http://127.0.0.1:8000/mcp**. Za prikaz vizualizacija potreban je klijent koji podržava MCP Apps. Poslužitelj se zaustavlja s Ctrl+C; `make stop` zaustavlja bazu i zadržava podatke.

Zadana lokalna baza radi bez `.env` datoteke. Za vlastitu bazu kopiraj `.env.example` u `.env`, postavi `DATABASE_URL` i pokreni `make start LOCAL_DATABASE=0`. Baza mora već biti dostupna. U tom načinu početna priprema registrira izvore i uvozi aktualne podatke s interneta umjesto učitavanja snimke. `DATABASE_URL` sadrži korisničko ime i lozinku.

`make help` prikazuje ostale naredbe. Oglasi se poslije osvježavaju s `make sync-jobs`, a DZS podaci s `make import-dzs`. Snimka uključuje i već preuzete detalje oglasa; preostali se postupno dohvaćaju s `make fetch-job-pages`. Za prognoziranje pokreni `make start UV_EXTRA="--extra forecast"`; ono instalira dodatne ovisnosti i pri prvoj prognozi preuzima model.

## Početna baza

Datoteka `data/initial.sql.gz` sadrži snimku radne baze od 8. studenoga 2026.: 11.263 oglasa, 21 županiju i 8.757 DZS vrijednosti, zajedno s izvorima, evidencijom uvoza i već dohvaćenim detaljima oglasa. Korisnik dobiva lokalnu kopiju tih podataka. Snimka predstavlja stanje u trenutku izvoza; svježina oglasa ovisi o naknadnom osvježavanju.

Docker učitava snimku samo kada prvi put stvara bazu u praznom volumenu. Ponovno pokretanje i `make setup` čuvaju postojeće podatke. Samo brisanje volumena naredbom `make down-volumes` trajno uklanja lokalne podatke; sljedeći `make start` tada ponovno učitava snimku.

Za osvježavanje priložene snimke iz naše lokalne Docker Compose baze koristi `make export-db`. Naredba izvozi shemu i podatke bez vlasnika i prava pristupa te zamjenjuje `data/initial.sql.gz` tek nakon uspješnog izvoza. Tu datoteku treba uključiti u repozitorij zajedno s promjenama sheme.

Za prvo pokretanje računaj na instalaciju ovisnosti, preuzimanje Docker slike, učitavanje snimke i izgradnju prikaza. HZZ i DZS izvori nisu potrebni za početno punjenje lokalne baze.

Osnovni podaci iz feedova dovoljni su za isprobavanje pretraživanja i statistike. Dodatni detalji i uvjeti oglasa dohvaćaju se zasebno:

```bash
make fetch-job-pages
```

Naredba prema zadanim postavkama obrađuje najviše 500 oglasa po pokretanju, uz pauzu od jedne sekunde između zahtjeva. Samo pauze za punu skupinu traju oko osam minuta, a preuzimanje dodaje vrijeme. Za približno 11.000 stranica trebalo bi više od tri sata kroz više pokretanja naredbe. Dok se stranice ne preuzmu, pojedini dodatni uvjeti oglasa ostaju nepoznati. Za manju probu koristi `make fetch-job-pages args="--limit 10"`.

## Licenca

Projekt je licenciran pod [Apache License 2.0](LICENSE).

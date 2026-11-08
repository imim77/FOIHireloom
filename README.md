# FOIHireloom

FOIHireloom je MCP aplikacija za pretraživanje HZZ oglasa i pregled podataka o tržištu rada. MCP klijent prikazuje rezultate i pripadajuće vizualizacije.

## Lokalno pokretanje

Potrebni su Git, `make`, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 22 s npm-om te pokrenut Docker s Docker Composeom. Potrebna je i internetska veza za instalaciju i početni uvoz podataka.

Nakon preuzimanja repozitorija, u njegovoj glavnoj mapi pokreni:

```bash
make start
```

Pri prvom pokretanju naredba instalira ovisnosti, pokreće lokalnu PostgreSQL bazu, primjenjuje migracije, registrira izvore, uvozi HZZ i DZS podatke i gradi prikaze. Početni uvoz može potrajati. Kad se poslužitelj pokrene, poveži MCP klijent na **http://127.0.0.1:8000/mcp**. Za prikaz vizualizacija potreban je klijent koji podržava MCP Apps. Poslužitelj se zaustavlja s Ctrl+C; `make stop` zaustavlja bazu i zadržava podatke.

Zadana lokalna baza radi bez `.env` datoteke. Za vlastitu bazu kopiraj `.env.example` u `.env`, postavi `DATABASE_URL` i pokreni `make start LOCAL_DATABASE=0`. Baza mora već biti dostupna. `DATABASE_URL` sadrži korisničko ime i lozinku.

`make help` prikazuje ostale naredbe. Oglasi se poslije osvježavaju s `make sync-jobs`, a DZS podaci s `make import-dzs`. Detalji oglasa nisu dio početnog uvoza; preuzimaju se postupno s `make fetch-job-pages`. Za prognoziranje pokreni `make start UV_EXTRA="--extra forecast"`; ono instalira dodatne ovisnosti i pri prvoj prognozi preuzima model.

## Početni podaci i trajanje uvoza

`make start` pri prvom pokretanju preuzima sve oglase dostupne u registriranim HZZ županijskim feedovima, bez ograničenja na mali uzorak. To ne mora obuhvaćati sve oglase na HZZ webu. Uvozi i županije te DZS pokazatelje za usporedbe i povijest. Podaci se preuzimaju s interneta; popunjena baza nije dio repozitorija. Pri lokalnoj provjeri baza je sadržavala oko 11.000 oglasa, 21 županiju i 8.757 DZS vrijednosti; stvarni broj oglasa ovisi o sadržaju feedova u trenutku uvoza.

Za prvo pokretanje računaj na nekoliko minuta. To je okvirna procjena, a ne izmjereno ili zajamčeno trajanje: uključuje instalaciju ovisnosti, uvoz i izgradnju prikaza te ovisi o računalu, internetskoj vezi i dostupnosti izvora. Feedovi donose mnogo oglasa jednim zahtjevom, pa početni uvoz ne otvara zasebnu stranicu za svaki oglas.

Osnovni podaci iz feedova dovoljni su za isprobavanje pretraživanja i statistike. Dodatni detalji i uvjeti oglasa dohvaćaju se zasebno:

```bash
make fetch-job-pages
```

Naredba prema zadanim postavkama obrađuje najviše 500 oglasa po pokretanju, uz pauzu od jedne sekunde između zahtjeva. Samo pauze za punu skupinu traju oko osam minuta, a preuzimanje dodaje vrijeme. Za približno 11.000 stranica trebalo bi više od tri sata kroz više pokretanja naredbe. Dok se stranice ne preuzmu, pojedini dodatni uvjeti oglasa ostaju nepoznati. Za manju probu koristi `make fetch-job-pages args="--limit 10"`.

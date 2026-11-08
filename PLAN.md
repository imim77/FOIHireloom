# Hrvatski nazivi baze

Datum: 7. 11. 2026. Status: dovršeno i lokalno primijenjeno, head `f1b3d5e7a9c2`.

Dopuna (`f1b3d5e7a9c2`): primarni ključevi su `id` umjesto `identifikator`,
jer strani ključevi su `id_<tablica>`; svih 47 CHECK ograničenja ima hrvatski
naziv, DZS jedinstveni ključ je `uq_vrijednosti_pokazatelja_dzs_prirodni_kljuc`,
a NOT NULL ograničenja slijede oblik `<tablica>_<stupac>_not_null`. Detalji su
u [mapi naziva](docs/database-croatian-names.md) i implementacijskom dnevniku.

## Istraživanje

Početni head d9f1b3c5e7a9 ima 8 aplikacijskih tablica i 113 stupaca.
MCP alati koriste engleske DTO-e i Python svojstva; repozitoriji većinom koriste
ORM, ali category batch update koristi Core Table ključeve. CHECK izrazi,
generirani stupci i izrazni indeksi sadrže izravne SQL nazive. Stare migracije
moraju ostati nepromijenjene kako bi se prazna baza i dalje mogla izgraditi.

## Pristup

Razmotreni su preimenovanje cijelog Python/API sloja i odvojeno preimenovanje
SQL sheme. Odabrano je eksplicitno ORM mapiranje: hrvatski SQL naziv uz stabilan
engleski Python/Core ključ, bez promjene MCP ugovora i pohranjenih kodova.
Time zahvat ostaje u pohrani. Nema zahtjeva za promjenu naziva same baze myapp.

- counties → zupanije
- jobs → oglasi
- source_feeds → izvorni_kanali
- job_feed_memberships → pripadnosti_oglasa_kanalima
- sync_runs → sinkronizacije
- dzs_imports → uvozi_dzs
- dzs_import_files → datoteke_uvoza_dzs
- dzs_indicator_values → vrijednosti_pokazatelja_dzs

Nazivi su snake_case bez dijakritika; identifikator, naslov, rok_prijave itd.
SHA-256 i HTTP status zadržavaju standardne tehničke nazive. Alembicova
interna alembic_version/version_num ostaje upravljana migracijskim alatom.

## Implementacija

Nova migracija e0a2c4e6f8b0 koristi samo RENAME za tablice, stupce, ograničenja,
indekse i identity sekvence. PostgreSQL prilagođava reference i generirane
izraze bez ponovnog stvaranja tablica. Zamrznuta mapa omogućuje potpuni downgrade.
Modeli u src/FOIHireloom/db/models imaju hrvatska SQL imena; svi ručni SQL
izrazi i dokumentacija moraju odgovarati tim imenima. Povijesne migracije i
prethodna mjerenja ostaju povijesni dokazi.

## Provjera

Prije primjene spremljen je backup
tmp/database-backups/myapp-before-croatian-names-2026-11-07.dump.
Na obnovljenoj kopiji provjeriti upgrade/downgrade/upgrade, alembic check,
sve testove uključujući PostgreSQL upise, kategorije, stranice i kursore.
Provjeriti i migracije od prazne baze. Usporediti sav sadržaj prije i poslije
preko mape imena. Tek tada primijeniti na glavnu bazu bez aktivnih writera,
ponoviti smoke provjere i ažurirati docs/database-era.* te implementacijski dnevnik.

## Granice

Podaci i značenje kodova, javni MCP parametri i Python nazivi ostaju isti.
Nijedan stupac ni poslovni redak ne smije nestati. Tehnički nazivi ograničenja
mogu imati standardne pk/fk/ck/uq/ix prefikse. Prethodni plan sačuvan je u
[docs/database-plan-before-croatian-names.md](docs/database-plan-before-croatian-names.md).

## Rezultat

Migracija e0a2c4e6f8b0 primijenjena je na glavnu bazu. Ostaje 8 aplikacijskih
tablica i 113 stupaca. Usporedba svih vrijednosti i brojeva redaka prije i
poslije, uz mapu imena, prolazi bez razlika. Backup je sačuvan.

Prolazi 287 testova, uključujući šest PostgreSQL regresija. Na kopiji su
provjereni upgrade/downgrade/upgrade, skupni Core update kategorija,
generirani tsvector/vještine, fizički katalog, DZS upisi i stranice kursora.
Migracijski lanac provjeren je i na praznoj bazi. alembic check prolazi.
Na glavnoj bazi prošli su kartice, get_job, skills, kursor i županijska usporedba.
Potpuni DZS uvoz lokalnih XLSX datoteka na kopiji vraća 8.757 unchanged.
Claude konektor nije ručno testiran; mrežna sinkronizacija nije pokrenuta.

[Aktualna shema](docs/database-era.md),
[mapa svih naziva](docs/database-croatian-names.md) i pripadajući dijagrami
su ažurirani. Povijesni dokumenti i rezultati starih SQL mjerenja zadržavaju
stare nazive. Ništa nije commitano.

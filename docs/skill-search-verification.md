# Pretraga oglasa po vještinama (5. 11. 2026.)

Implementiran je `PLAN.md` u tri cjeline: katalog i migracija; zajednički
filtar, rangiranje i kursor; MCP opisi, evaluacijski slučajevi i dokumentacija.

- `domain/skill_catalog.py` definira deset vještina: C#, .NET, Python, Java,
  JavaScript/TypeScript, SQL, PHP, Excel, AutoCAD i PLC. Uzorci čuvaju točke
  i `#`, uklanjaju HTTP(S)/www URL-ove i koriste granice koje rade u Pythonu
  i PostgreSQL-u. Excel i AutoCAD prihvaćaju izmjerene hrvatske oblike
  „Excela”, „Excelu” i „AutoCADom”. Ne zaključuju vještine iz kategorije.
- Migracija `f3b5d7e9a1c2` nakon `e2a4c6b8d0f1` dodaje generirani
  `jobs.skills text[]` i GIN indeks. Zamrznuti izraz daje prednost naslovu
  i opisu stranice pred feedom; promjena tih tekstova automatski mijenja oznake.
- Svih sedam alata sa zajedničkim filtrima prima `skills`. Unutar popisa
  vrijedi OR, s ostalim filtrima AND; prazan popis ne filtrira, a duplikati
  se broje jednom. Isti filtar vrijedi za kartice, statistiku i županije.
  Nespomenuta vještina nije nepoznat uvjet rada. Županijski pokazatelji i
  dalje koriste sve aktivne oglase za svoje nazivnike.
- Poredak je `title_match DESC, skill_matches DESC, published_on DESC NULLS
  LAST, id DESC`. Kursor čuva oba ranga; leksikografski uvjet obrađuje i
  nepoznate datume. `matched_skills` u sažecima i karticama sadrži samo presjek
  traženih i spomenutih vještina. Nema novih čipova u React karticama.
- Opisi odvajaju `skills` od upita za zanimanje ili strani jezik. Kod malo
  pogodaka model treba ponuditi zasebnu pretragu srodnog zanimanja ili IT
  kategorije bez `skills`, uz zadržane ostale filtre. Fallback nije automatski
  na poslužitelju; nema embeddinga niti promjene tokenizacije `query`.
- Provjera lokalne baze s 8.670 oglasa: upgrade, downgrade za jednu reviziju
  i ponovni upgrade prolaze. Svih deset pozitivnih/negativnih tekstualnih
  primjera daje isti rezultat u Pythonu i PostgreSQL-u. Oznake: Excel 145,
  AutoCAD 84, JavaScript 6, PLC 6, SQL 5, C# 3, Python 3, PHP 3, Java 2,
  .NET 2. Razlika prema preliminarnim brojevima iz plana dolazi od uklonjenih
  URL-ova i granica: tri oglasa navode samo MySQL/PostgreSQL bez samostalne
  oznake SQL pa ne dobivaju tu oznaku; jedan
  preliminarni Excel pogodak navodi tipfeler „Excella”.
- Izolirana transakcijska PostgreSQL shema provjerila je četiri načina
  straničenja (s/bez upita i s/bez vještina), prijelaze oba ranga, jednake i
  nepoznate datume, statistiku, županijske brojeve, nepoznate uvjete i
  prednost stranice. Sve promjene testne sheme vraćene su rollbackom.
- Stvarni MCP poziv `show_jobs(skills=["csharp", "python"], limit=2,
  include_expired=true)` vraća tri trenutačno objavljena oglasa, ID-jeve
  7774, 5984 i 6241, bez ponavljanja. U bazi postoji pet različitih oglasa
  s tim vještinama; dva više nisu prisutna u županijskim feedovima, uključujući
  jedini oglas s obje vještine. Njegov prioritet provjeren je na testnim podacima.
- Svih 281 Python testova prolazi, uključujući HTTP testove uz dopuštene
  lokalne socketove. Dodatno prolaze sva 253 testa u izoliranoj snimci
  sadržaja pripremljenog za commit, bez ranijih nepovezanih izmjena backenda.
- Dodana su dva referentna routing slučaja (C#/Python na hrvatskom i
  Excel/AutoCAD u Splitu na engleskom). Testovi provjeravaju enum u svih sedam
  alata, odbijanje nepoznatih kodova, prosljeđivanje filtara i shemu slučajeva.
  Lokalna provjera sheme nije dokaz modelskog odabira alata ili fallbacka.
- Evaluacija u Claude Desktopu nije dovršena: pokušaj otvaranja novog chata
  kroz UI automatizaciju završio je pogreškom `noWindowsAvailable`. Nema
  zabilježenog modelskog odgovora ni tvrdnje o uspješnom fallbacku. Postojeći
  javni MCP proces i tunel nisu ponovno pokretani.

The fixture is a reference snapshot of the job category fill, written on 2026-10-31 from the local
app database (the default DATABASE_URL, migrated to c4e8a2f6b1d3) with:

    uv run --locked foihireloom-category-snapshot --out tests/fixtures/category_reference_snapshot.json

`generated_at` (19:14:19 UTC) is the database's transaction time. Every feed had last downloaded
successfully between 19:03:37 and 19:03:43 UTC, and the occupation feeds' mappings were last
verified at 18:48 UTC. The snapshot was taken after that sync had finished.

It keeps, for each of the 21 county and 18 occupation feeds, the ID, scope, label, URL, CKAN
resource ID, last successful download, last content change and HZZ's Last-Modified time, and for
occupation feeds the verified category mapping: the category, its status and the matching and
contradicting examples. For each of the 7,384 listed jobs (present in at least one county feed, the
denominator) it keeps only the HZZ job ID, the category from its description, the IDs of every
occupation feed that lists or has listed it, and the stored category, its source and its feed. No
job text, employer or contact details are kept. Categories in job rows are indices into
`categories`; `job_columns` names the row columns.

At this time 3,434 jobs (46.5%) had a category from their description and 2,749 more were filled
in from confirmed occupation feed mappings, so 6,183 (83.7%) had a category and 1,201 had none.
15 occupation feeds were confirmed and 3 had too few examples. No job was listed by more than one
occupation feed, so there were no conflicting mappings; every job left without a category was in
no occupation feed.

"""Croatian wording the views show for the filters, the jobs left out for unknown values and the data's freshness.

The tools' English fields stay for the LLM; these say the same to the user
in the view.
"""

from datetime import date

from FOIHireloom.dto.job_market import JobMarketFiltersDTO
from FOIHireloom.dto.job_search import ActiveFilterDTO, CoverageDTO, JobSearchFiltersDTO

CONTRACTS = {"permanent": "na neodređeno", "fixed_term": "na određeno", "other": "drugi oblici rada"}
# The levels as HZZ names them, made short enough for a chip.
EDUCATION_LEVELS = {
    "primary_lower": "niži razredi osnovne škole",
    "primary": "osnovna škola",
    "secondary_3": "srednja škola (3 god.)",
    "secondary_4": "srednja škola (4 god.)",
    "college": "viša škola ili prvostupnik",
    "university": "fakultet ili akademija",
}
# In the order JobConditionsDTO keeps the tags.
EMPLOYMENT_TAGS = {
    "new_position": "novootvoreno radno mjesto",
    "vacancy": "upražnjeno radno mjesto",
    "replacement": "zamjena",
    "increased_workload": "povećan opseg posla",
    "seasonal": "sezonski posao",
    "reappointment": "reizbor",
    "trainee": "pripravnik",
    "retirees": "zapošljavanje umirovljenika",
    "disability": "zapošljavanje osoba s invaliditetom",
}
# What a job's unknown value is, by condition filter as count_unknown_conditions names them; ties keep this order.
UNKNOWN_VALUES = {
    "max_experience_months": "iskustvo",
    "contract": "ugovor",
    "full_time": "radno vrijeme",
    "education": "obrazovanje",
    "accommodation": "smještaj",
    "employment_tags": "vrsta zaposlenja",
    "place": "mjesto rada",
}
# Counties named in a coverage note before the rest are only counted.
NOTE_REGION_LIMIT = 3


def plural(count: float, one: str, few: str, many: str) -> str:
    """Croatian plurals: 1, 21 … take one; 2–4, 22–24 … few; the rest, 11–14 included, many."""
    n = round(count)
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def integer(value: int) -> str:
    """1325 → "1.325", grouped as hr-HR does."""
    return f"{value:,}".replace(",", ".")


def listing(names: list[str]) -> str:
    """"a", "a i b", "a, b i c"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} i {names[-1]}"


def sentence(text: str) -> str:
    """Capitalise the first letter only; a category in capitals stays."""
    return text[:1].upper() + text[1:]


def day(today: date, include_expired: bool) -> str:
    """Which jobs on which day: "aktivni oglasi na dan 30. 10. 2026.", or "svi oglasi …" with expired ones."""
    return f"{'svi' if include_expired else 'aktivni'} oglasi na dan {today:%d. %m. %Y.}"


def active_filters(filters: JobSearchFiltersDTO | JobMarketFiltersDTO) -> tuple[ActiveFilterDTO, ...]:
    """A label for each filter that is set, except the query, in the order of the tool arguments.

    A blank county, category or place and no employment tags are no filter;
    include_expired is one only when True.
    """
    tags = [name for tag, name in EMPLOYMENT_TAGS.items() if tag in (filters.employment_tags or ())]
    labels: dict[str, str | None] = {
        "county": f"županija {county}" if (county := (filters.county or "").strip()) else None,
        "category": f"kategorija {category}" if (category := (filters.category or "").strip()) else None,
        "max_experience_months": experience(filters.max_experience_months),
        "contract": CONTRACTS[filters.contract] if filters.contract else None,
        "full_time": either(filters.full_time, "puno radno vrijeme", "nepuno radno vrijeme"),
        "education": f"obrazovanje: {EDUCATION_LEVELS[filters.education]}" if filters.education else None,
        "accommodation": either(filters.accommodation, "uz smještaj", "bez smještaja"),
        "employment_tags": f"vrsta zaposlenja: {listing(tags)}" if tags else None,
        "place": f"mjesto rada {place}" if (place := (filters.place or "").strip()) else None,
        "include_expired": "i istekli oglasi" if filters.include_expired else None,
    }
    return tuple(ActiveFilterDTO(argument=argument, label=label) for argument, label in labels.items() if label)


def either(value: bool | None, true: str, false: str) -> str | None:
    return None if value is None else true if value else false


def experience(months: int | None) -> str | None:
    """max_experience_months as a label: "bez iskustva", "iskustvo do 18 mj." or, in whole years, "do 2 godine"."""
    if months is None:
        return None
    if months == 0:
        return "bez iskustva"
    if months % 12:
        return f"iskustvo do {months} mj."
    years = months // 12
    return f"iskustvo do {years} {plural(years, 'godine', 'godine', 'godina')}"


def unknown_note(unknown_conditions: dict[str, int], unknown_total: int) -> str | None:
    """How many more jobs might match and which values they lack, most often unknown first; None when there are none.

    "Još 30 oglasa možda odgovara, ali im nije poznato: iskustvo (30), ugovor (27)."
    """
    if not unknown_total:
        return None
    order = list(UNKNOWN_VALUES)
    unknown = sorted(((name, count) for name, count in unknown_conditions.items() if count),
                     key=lambda item: (-item[1], order.index(item[0])))
    values = ", ".join(f"{UNKNOWN_VALUES[name]} ({integer(count)})" for name, count in unknown)
    ads = plural(unknown_total, "oglas", "oglasa", "oglasa")
    # The verb agrees with the number as the noun does: "2 oglasa odgovaraju", "5 oglasa odgovara". "Im" refers
    # to the ads, so only a single ad is "mu".
    verb = plural(unknown_total, "odgovara", "odgovaraju", "odgovara")
    them = "mu" if unknown_total == 1 else "im"
    return f"Još {integer(unknown_total)} {ads} možda {verb}, ali {them} nije poznato: {values}."


def coverage_note(coverage: CoverageDTO) -> str | None:
    """coverage.warning for the user: which counties' data is old or missing; None when every county is fresh.

    County names stay in the nominative, as the data has them, so no sentence inflects them.
    """
    if coverage.data_status == "unavailable" and not coverage.affected_regions:
        # Only a search over no counties at all is unavailable without an affected county.
        return "Nijedna županija nije registrirana, pa nema podataka o oglasima."
    regions = coverage.affected_regions
    if not regions:
        return None
    hours = f"{coverage.stale_after_hours:g}".replace(".", ",")
    stale = f"su stariji od {hours} {plural(coverage.stale_after_hours, 'sata', 'sata', 'sati')}"
    statuses = {region.data_status for region in regions}
    if statuses == {"stale"}:
        state = stale
    elif statuses == {"unavailable"}:
        state = "nisu dostupni"
    else:
        state = f"{stale} ili nisu dostupni"
    if len(regions) == 1:
        return f"{regions[0].name}: podaci {state}, pa rezultat možda nije potpun."
    names = [region.name for region in regions[:NOTE_REGION_LIMIT]]
    if len(regions) > NOTE_REGION_LIMIT:
        names.append(f"još {len(regions) - NOTE_REGION_LIMIT}")
    counties = plural(len(regions), "županiju", "županije", "županija")
    return f"Podaci {state} za {len(regions)} {counties} ({listing(names)}), pa rezultat možda nije potpun."

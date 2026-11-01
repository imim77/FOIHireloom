"""Data for the job comparison view, which shows 2 or 3 jobs side by side, aspect by aspect.

The tool returns JobComparisonViewDTO as structured content; the host loads
the views.JOB_COMPARISON page in a sandboxed iframe and passes it that
result over the MCP Apps bridge. Text-only hosts still get the same data,
the English fields included.
"""

from collections.abc import Callable
from datetime import date

from FOIHireloom.dto.job_comparison import (
    ComparedJobDTO,
    ComparisonAspect,
    ComparisonCellDTO,
    ComparisonCellViewDTO,
    ComparisonRowDTO,
    ComparisonRowViewDTO,
    ConditionVerdict,
    JobComparisonDTO,
    JobComparisonViewDTO,
    UnknownReason,
)
from FOIHireloom.dto.job_conditions import JobConditionsDTO
from FOIHireloom.dto.job_search import JobSearchFiltersDTO

from .labels import CONTRACTS, EDUCATION_LEVELS, active_filters, date_label, plural

TITLE = "Usporedba oglasa"
NO_CONDITIONS = "Bez zadanih uvjeta"
DISCLAIMER = "Usporedba pokazuje samo što oglasi navode, ne i hoće li vas poslodavac odabrati."
ASPECTS: dict[ComparisonAspect, str] = {
    "experience": "Iskustvo",
    "education": "Obrazovanje",
    "contract": "Ugovor",
    "working_time": "Radno vrijeme",
    "accommodation": "Smještaj",
    "deadline": "Rok prijave",
}
VERDICTS: dict[ConditionVerdict, str] = {"match": "odgovara", "no_match": "ne odgovara", "unknown": "nije poznato"}
UNKNOWN_REASONS: dict[UnknownReason, str] = {
    "page_not_read": "stranica oglasa još nije pročitana",
    "page_unavailable": "HZZ nije vratio stranicu oglasa",
    "page_failed": "dohvat stranice nije uspio",
    "not_stated": "oglas ne navodi",
    "unreadable": "nije prepoznato",
    "contract_not_stated": "oglas navodi vrstu zaposlenja, ali ne i ugovor",
}
ACCOMMODATION = {
    "none": "bez smještaja",
    "shared": "zajednički smještaj",
    "single": "samački smještaj",
    "family": "obiteljski stan",
}


def job_comparison(comparison: JobComparisonDTO) -> JobComparisonViewDTO:
    jobs = {job.id: job for job in comparison.jobs}
    return JobComparisonViewDTO(
        **comparison.model_dump(exclude={"rows"}),
        rows=tuple(_row(row, jobs, comparison.today) for row in comparison.rows),
        title=TITLE,
        description=description(comparison),
        disclaimer=DISCLAIMER,
        unknown_note=unknown_note(comparison.rows),
    )


def description(comparison: JobComparisonDTO) -> str:
    """The person's conditions as the other views' filter labels: "Vaši uvjeti: bez iskustva · na neodređeno"."""
    labels = () if comparison.conditions is None else active_filters(
        JobSearchFiltersDTO(**comparison.conditions.model_dump()))
    return f"Vaši uvjeti: {' · '.join(label.label for label in labels)}" if labels else NO_CONDITIONS


def unknown_note(rows: tuple[ComparisonRowDTO, ...]) -> str | None:
    """How many verdicts are unknown, which does not make them met; None when none is.

    "Za 2 uvjeta podatak u oglasu nije poznat; to ne znači da su ispunjeni."
    Several jobs with unknown verdicts make it "u oglasima".
    """
    unknown = [cell for row in rows for cell in row.cells if cell.verdict == "unknown"]
    if not unknown:
        return None
    count = len(unknown)
    conditions = plural(count, "uvjet", "uvjeta", "uvjeta")
    ads = "oglasu" if len({cell.job_id for cell in unknown}) == 1 else "oglasima"
    met = plural(count, "je ispunjen", "su ispunjeni", "su ispunjeni")
    return f"Za {count} {conditions} podatak u {ads} nije poznat; to ne znači da {met}."


def condition_label(aspect: ComparisonAspect, condition: bool | int | str | None) -> str | None:
    """The person's condition for its row's heading, as in "Iskustvo · vi: bez iskustva"; None without one."""
    if condition is None or aspect == "deadline":
        return None
    labels: dict[ComparisonAspect, Callable[[], str]] = {
        "experience": lambda: experience(int(condition)),
        "education": lambda: EDUCATION_LEVELS[str(condition)],
        "contract": lambda: CONTRACTS[str(condition)],
        "working_time": lambda: "puno radno vrijeme" if condition else "nepuno radno vrijeme",
        "accommodation": lambda: "uz smještaj" if condition else "bez smještaja",
    }
    return labels[aspect]()


def experience(months: int) -> str:
    """"bez iskustva", "6 mj." or, in whole years, "2 godine"."""
    if months == 0:
        return "bez iskustva"
    if months % 12:
        return f"{months} mj."
    years = months // 12
    return f"{years} {plural(years, 'godina', 'godine', 'godina')}"


def deadline(job: ComparedJobDTO, today: date) -> str:
    """"do 29. 11. 2026. (još 28 dana)", "do 01. 11. 2026. (zadnji dan)", "istekao 31. 10. 2026." or "nije naveden"."""
    if job.deadline_on is None:
        return "nije naveden"
    days = (job.deadline_on - today).days
    if days < 0:
        return f"istekao {date_label(job.deadline_on)}"
    left = "zadnji dan" if days == 0 else f"još {days} {plural(days, 'dan', 'dana', 'dana')}"
    return f"do {date_label(job.deadline_on)} ({left})"


def known_value(aspect: ComparisonAspect, conditions: JobConditionsDTO) -> str | None:
    """A known value in Croatian, for a cell without the page's text; None when the value is unknown."""
    if aspect == "experience" and conditions.experience_months is not None:
        return "pripravnik" if conditions.trainee else experience(conditions.experience_months)
    if aspect == "education" and conditions.education_levels:
        names = [EDUCATION_LEVELS[level] for level in conditions.education_levels]
        return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} ili {names[-1]}"
    if aspect == "contract" and conditions.contract is not None:
        return CONTRACTS[conditions.contract]
    if aspect == "working_time" and conditions.full_time is not None:
        kind = "puno radno vrijeme" if conditions.full_time else "nepuno radno vrijeme"
        return kind if conditions.weekly_hours is None else f"{kind}, {conditions.weekly_hours} h tjedno"
    if aspect == "accommodation" and conditions.accommodation is not None:
        return ACCOMMODATION[conditions.accommodation]
    return None


def _row(row: ComparisonRowDTO, jobs: dict[int, ComparedJobDTO], today: date) -> ComparisonRowViewDTO:
    return ComparisonRowViewDTO(
        **row.model_dump(exclude={"cells"}),
        name=ASPECTS[row.aspect],
        condition_label=condition_label(row.aspect, row.condition),
        cells=tuple(_cell(row.aspect, cell, jobs[cell.job_id], today) for cell in row.cells),
    )


def _cell(aspect: ComparisonAspect, cell: ComparisonCellDTO, job: ComparedJobDTO, today: date) -> ComparisonCellViewDTO:
    """The cell's text: the deadline worded, else HZZ's own words, else why the value is unknown."""
    reason = None if cell.unknown_reason is None else UNKNOWN_REASONS[cell.unknown_reason]
    if aspect == "deadline":
        text, note = deadline(job, today), None
    elif cell.evidence:
        # An unknown value says why under the page's words, e.g. a type of employment without a contract.
        text, note = cell.evidence, reason
    elif reason is not None:
        text, note = reason, None
    else:
        text, note = known_value(aspect, job.conditions or JobConditionsDTO()) or cell.value or "", None
    return ComparisonCellViewDTO(
        **cell.model_dump(), text=text, note=note,
        verdict_label=None if cell.verdict is None else VERDICTS[cell.verdict],
    )

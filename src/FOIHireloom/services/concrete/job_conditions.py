import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from FOIHireloom.dto.job_conditions import JobConditionsDTO, RawJobConditionsDTO

# Keys are casefolded HZZ wording; tag and level codes keep the order given here.
EXPERIENCE = re.compile(r"(?:(\d+) (?:godin[aeu]|g\.)(?: i |$))?(?:(\d+) mjesec[ai]?)?")
WEEKLY_HOURS = re.compile(r"(\d+) sat[ai]? tjedno")
CONTRACTS = {
    "na neodređeno": "permanent",
    "na određeno": "fixed_term",
    "drugi oblici rada": "other",
    "privremeni/povremeni sezonski posao u poljoprivredi": "other",
}
EMPLOYMENT_TAGS = {
    "novootvoreni poslovi": "new_position",
    "upražnjeni poslovi": "vacancy",
    "zamjena": "replacement",
    "povećan opseg posla": "increased_workload",
    "sezonski": "seasonal",
    "privremeni/povremeni sezonski posao u poljoprivredi": "seasonal",
    "reizbor": "reappointment",
    "pripravnik": "trainee",
    "mogućnost zapošljavanja umirovljenika": "retirees",
    "mogućnost zaposlenja osobe sa invaliditetom": "disability",
}
EDUCATION_LEVELS = {
    "osnovna škola niži razredi": "primary_lower",
    "završena osnovna škola": "primary",
    "srednja škola 3 godine": "secondary_3",
    "srednja škola 4 godine": "secondary_4",
    "viša ili prvostupanjska": "college",
    "fakultet, akademija, magisterij, doktorat": "university",
}
ACCOMMODATION = {
    "nema smještaja": "none",
    "zajednički smještaj": "shared",
    "samački smještaj": "single",
    "obiteljski stan": "family",
}
SCHEDULE_TAGS = {
    "smjena - prijepodne": "morning",
    "smjena - poslijepodne": "afternoon",
    "2 smjene": "two_shifts",
    "3i smjene": "three_shifts",
    "dvokratno radno vrijeme": "split",
    "noćni rad": "night",
    "rad vikendom i praznikom": "weekends_holidays",
}
TRANSPORT_ALLOWANCE = {"u cijelosti": "full", "djelomično": "partial", "bez naknade": "none"}

type Parts = tuple[str, ...]


class JobConditionsNormalizer:
    """Map the conditions on an HZZ job page to fixed codes without guessing.

    Values are compared casefolded with whitespace collapsed. A list value
    is recognised only when every part is, so no part is silently dropped.
    """

    def normalize(self, raw: RawJobConditionsDTO) -> JobConditionsDTO:
        parsers: dict[str, Callable[[Parts], dict[str, Any] | None]] = {
            "experience": self._experience,
            "employment_type": self._employment_type,
            "working_hours": self._working_hours,
            "education": lambda parts: self._codes(parts, EDUCATION_LEVELS, "education_levels"),
            "accommodation": lambda parts: self._single(parts, ACCOMMODATION, "accommodation"),
            "work_schedule": lambda parts: self._codes(parts, SCHEDULE_TAGS, "schedule_tags"),
            "transport_allowance": lambda parts: self._single(parts, TRANSPORT_ALLOWANCE, "transport_allowance"),
        }
        fields: dict[str, Any] = {}
        unrecognised = []
        for name, parse in parsers.items():
            parts = self._parts(getattr(raw, name))
            if not parts:
                continue
            parsed = parse(parts)
            if parsed is None:
                unrecognised.append(name)
            else:
                fields.update(parsed)
        return JobConditionsDTO(**fields, unrecognised=tuple(unrecognised))

    @staticmethod
    def _parts(value: str | None) -> Parts:
        return tuple(key for part in (value or "").split(";") if (key := " ".join(part.split()).casefold()))

    @staticmethod
    def _experience(parts: Parts) -> dict[str, Any] | None:
        if parts == ("nije važno",):
            return {"experience_months": 0, "trainee": False}
        if parts == ("traži se pripravnik",):
            return {"experience_months": 0, "trainee": True}
        match = EXPERIENCE.fullmatch(parts[0]) if len(parts) == 1 else None
        if match is None:
            return None
        years, months = (int(group or 0) for group in match.groups())
        return {"experience_months": years * 12 + months, "trainee": False}

    @classmethod
    def _employment_type(cls, parts: Parts) -> dict[str, Any] | None:
        contracts = {CONTRACTS[part] for part in parts if part in CONTRACTS}
        if len(contracts) > 1 or not all(part in CONTRACTS or part in EMPLOYMENT_TAGS for part in parts):
            return None
        tags = cls._ordered((EMPLOYMENT_TAGS[part] for part in parts if part in EMPLOYMENT_TAGS), EMPLOYMENT_TAGS)
        return {"contract": next(iter(contracts), None), "employment_tags": tags}

    @staticmethod
    def _working_hours(parts: Parts) -> dict[str, Any] | None:
        if parts == ("puno radno vrijeme",):
            return {"full_time": True}
        match = WEEKLY_HOURS.fullmatch(parts[0]) if len(parts) == 1 else None
        if match is None:
            return None
        hours = int(match.group(1))
        return {"full_time": hours >= 40, "weekly_hours": hours}

    @classmethod
    def _codes(cls, parts: Parts, vocabulary: Mapping[str, str], field: str) -> dict[str, Any] | None:
        if not all(part in vocabulary for part in parts):
            return None
        return {field: cls._ordered((vocabulary[part] for part in parts), vocabulary)}

    @staticmethod
    def _single(parts: Parts, vocabulary: Mapping[str, str], field: str) -> dict[str, Any] | None:
        if len(parts) != 1 or parts[0] not in vocabulary:
            return None
        return {field: vocabulary[parts[0]]}

    @staticmethod
    def _ordered(codes: Iterable[str], vocabulary: Mapping[str, str]) -> tuple[str, ...]:
        """Distinct codes in the order the vocabulary lists them."""
        found = set(codes)
        return tuple(code for code in dict.fromkeys(vocabulary.values()) if code in found)

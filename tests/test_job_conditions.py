import unittest

from FOIHireloom.dto import JobConditionsDTO, ParsedJobPageDTO, RawJobConditionsDTO
from FOIHireloom.services import JobConditionsNormalizer

# Every distinct experience and working hours value on fetched HZZ pages.
EXPERIENCE_MONTHS = {
    "1 mjesec": 1, "2 mjeseca": 2, "3 mjeseca": 3, "6 mjeseci": 6,
    "1 godinu": 12, "1 g.": 12, "2 godine": 24, "2 g.": 24, "3 godine": 36, "3 g.": 36, "4 godine": 48,
    "5 godina": 60, "5 g.": 60, "6 godina": 72, "7 godina": 84, "8 godina": 96, "10 godina": 120, "20 godina": 240,
    "1 godinu i 1 mjesec": 13, "1 godinu i 2 mjeseca": 14, "1 godinu i 5 mjeseci": 17, "1 godinu i 6 mjeseci": 18,
    "1 godinu i 7 mjeseci": 19, "2 godine i 1 mjesec": 25, "2 godine i 2 mjeseca": 26, "2 godine i 6 mjeseci": 30,
    "2 godine i 10 mjeseci": 34, "3 godine i 1 mjesec": 37, "4 godine i 1 mjesec": 49, "4 godine i 3 mjeseca": 51,
}
WEEKLY_HOURS = {
    **{f"{hours} sat tjedno": hours for hours in (1, 11, 21, 31)},
    **{f"{hours} sata tjedno": hours for hours in (2, 3, 4, 12, 13, 14, 22, 23, 24, 32, 33, 34)},
    **{f"{hours} sati tjedno": hours for hours in (*range(5, 11), *range(15, 21), *range(25, 31), 35, 36, 37, 39, 40)},
}
# Every part of the list values on fetched HZZ pages.
EMPLOYMENT_PARTS = {
    "Na neodređeno": ("permanent", ()),
    "Na određeno": ("fixed_term", ()),
    "Drugi oblici rada": ("other", ()),
    "Privremeni/povremeni sezonski posao u poljoprivredi": ("other", ("seasonal",)),
    "Na određeno; novootvoreni poslovi": ("fixed_term", ("new_position",)),
    "Na neodređeno; upražnjeni poslovi": ("permanent", ("vacancy",)),
    "Na određeno; zamjena": ("fixed_term", ("replacement",)),
    "Na određeno; povećan opseg posla": ("fixed_term", ("increased_workload",)),
    "Na određeno; sezonski": ("fixed_term", ("seasonal",)),
    "Na određeno; reizbor": ("fixed_term", ("reappointment",)),
    "Na neodređeno; novootvoreni poslovi; pripravnik": ("permanent", ("new_position", "trainee")),
    "Drugi oblici rada; mogućnost zapošljavanja umirovljenika": ("other", ("retirees",)),
    "Na određeno; zamjena; mogućnost zaposlenja osobe sa invaliditetom": ("fixed_term", ("replacement", "disability")),
}
EDUCATION_LEVELS = {
    "Osnovna škola niži razredi": "primary_lower",
    "Završena osnovna škola": "primary",
    "Srednja škola 3 godine": "secondary_3",
    "Srednja škola 4 godine": "secondary_4",
    "Viša ili prvostupanjska": "college",
    "Fakultet, akademija, magisterij, doktorat": "university",
}
SCHEDULE_TAGS = {
    "Smjena - prijepodne": "morning",
    "Smjena - poslijepodne": "afternoon",
    "2 smjene": "two_shifts",
    "3i smjene": "three_shifts",
    "Dvokratno radno vrijeme": "split",
    "Noćni rad": "night",
    "Rad vikendom i praznikom": "weekends_holidays",
}


class JobConditionsNormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalizer = JobConditionsNormalizer()

    def normalize(self, **fields: str | None) -> JobConditionsDTO:
        return self.normalizer.normalize(RawJobConditionsDTO(**fields))

    def test_experience_is_counted_in_months(self) -> None:
        for raw, months in EXPERIENCE_MONTHS.items():
            with self.subTest(raw):
                conditions = self.normalize(experience=raw)
                self.assertEqual((conditions.experience_months, conditions.trainee), (months, False))

    def test_no_experience_needed_and_trainees_need_none(self) -> None:
        not_needed, trainee = self.normalize(experience="Nije važno"), self.normalize(experience="Traži se pripravnik")
        self.assertEqual((not_needed.experience_months, not_needed.trainee), (0, False))
        self.assertEqual((trainee.experience_months, trainee.trainee), (0, True))

    def test_employment_type_gives_the_contract_and_ordered_tags(self) -> None:
        for raw, expected in EMPLOYMENT_PARTS.items():
            with self.subTest(raw):
                conditions = self.normalize(employment_type=raw)
                self.assertEqual((conditions.contract, conditions.employment_tags), expected)
        conditions = self.normalize(employment_type=(
            "Na neodređeno; mogućnost zapošljavanja umirovljenika; pripravnik; "
            "mogućnost zaposlenja osobe sa invaliditetom; novootvoreni poslovi"
        ))
        self.assertEqual(conditions.employment_tags, ("new_position", "trainee", "retirees", "disability"))

    def test_working_hours_give_full_time_from_forty_hours(self) -> None:
        full = self.normalize(working_hours="Puno radno vrijeme")
        self.assertEqual((full.full_time, full.weekly_hours), (True, None))
        for raw, hours in WEEKLY_HOURS.items():
            with self.subTest(raw):
                conditions = self.normalize(working_hours=raw)
                self.assertEqual((conditions.full_time, conditions.weekly_hours), (hours >= 40, hours))

    def test_education_levels_are_listed_from_lowest_to_highest(self) -> None:
        for raw, level in EDUCATION_LEVELS.items():
            with self.subTest(raw):
                self.assertEqual(self.normalize(education=raw).education_levels, (level,))
        raw = "Fakultet, akademija, magisterij, doktorat; Završena osnovna škola; Srednja škola 4 godine"
        self.assertEqual(self.normalize(education=raw).education_levels, ("primary", "secondary_4", "university"))

    def test_schedule_tags_follow_a_fixed_order(self) -> None:
        for raw, tag in SCHEDULE_TAGS.items():
            with self.subTest(raw):
                self.assertEqual(self.normalize(work_schedule=raw).schedule_tags, (tag,))
        # HZZ once listed weekends before the shifts; a repeated part counts once.
        raw = "Rad vikendom i praznikom; 2 smjene"
        self.assertEqual(self.normalize(work_schedule=raw).schedule_tags, ("two_shifts", "weekends_holidays"))
        raw = "Noćni rad; Smjena - poslijepodne; Smjena - prijepodne; Smjena - prijepodne"
        self.assertEqual(self.normalize(work_schedule=raw).schedule_tags, ("morning", "afternoon", "night"))

    def test_accommodation_and_transport_allowance(self) -> None:
        for raw, expected in (
            ("Nema smještaja", "none"), ("Zajednički smještaj", "shared"),
            ("Samački smještaj", "single"), ("Obiteljski stan", "family"),
        ):
            with self.subTest(raw):
                self.assertEqual(self.normalize(accommodation=raw).accommodation, expected)
        for raw, expected in (("U cijelosti", "full"), ("Djelomično", "partial"), ("Bez naknade", "none")):
            with self.subTest(raw):
                self.assertEqual(self.normalize(transport_allowance=raw).transport_allowance, expected)

    def test_comparison_ignores_case_and_whitespace(self) -> None:
        conditions = self.normalize(experience="  NIJE VAŽNO ", employment_type="na  određeno ;ZAMJENA")
        self.assertEqual(
            (conditions.experience_months, conditions.contract, conditions.employment_tags, conditions.unrecognised),
            (0, "fixed_term", ("replacement",), ()),
        )

    def test_missing_and_empty_values_are_unknown_rather_than_not_required(self) -> None:
        for value in (None, "", " ; "):
            with self.subTest(value):
                self.assertEqual(self.normalize(**dict.fromkeys(RawJobConditionsDTO.model_fields, value)), JobConditionsDTO())

    def test_unrecognised_values_stay_unknown_and_are_named(self) -> None:
        conditions = self.normalize(
            experience="Poželjno", employment_type="Na određeno; Na neodređeno",
            working_hours="Puno radno vrijeme; 20 sati tjedno", education="Srednja škola 4 godine; Doktorat znanosti",
            accommodation="Hotel", work_schedule="2 smjene; Turnus", transport_allowance="Po dogovoru",
        )
        self.assertEqual(conditions, JobConditionsDTO(unrecognised=tuple(RawJobConditionsDTO.model_fields)))
        for raw in ("0,5 godina", "godinu", "1 godinu i", "6 mjeseci i 1 godinu"):
            with self.subTest(raw):
                self.assertEqual(self.normalize(experience=raw), JobConditionsDTO(unrecognised=("experience",)))
        # One unknown part leaves the whole field unknown instead of dropping the part.
        conditions = self.normalize(employment_type="Na određeno; sezonski; vikendom", accommodation="Nema smještaja")
        self.assertEqual(
            (conditions.contract, conditions.employment_tags, conditions.accommodation, conditions.unrecognised),
            (None, None, "none", ("employment_type",)),
        )

    def test_raw_conditions_validate_from_a_parsed_job_page(self) -> None:
        parsed = ParsedJobPageDTO(
            title="KUHAR/ICA", work_place="ZAGREB", workers_needed=1, valid_from=None, valid_until=None,
            description_text=None, employer_name=None, experience="1 godinu",
            employment_type="Na neodređeno; upražnjeni poslovi", working_hours="20 sati tjedno",
            education="Srednja škola 3 godine; Srednja škola 4 godine", accommodation="Zajednički smještaj",
            work_schedule="2 smjene; Rad vikendom i praznikom", transport_allowance="Djelomično",
        )
        self.assertEqual(self.normalizer.normalize(RawJobConditionsDTO.model_validate(parsed)), JobConditionsDTO(
            experience_months=12, trainee=False, contract="permanent", employment_tags=("vacancy",),
            full_time=False, weekly_hours=20, education_levels=("secondary_3", "secondary_4"),
            accommodation="shared", schedule_tags=("two_shifts", "weekends_holidays"), transport_allowance="partial",
        ))

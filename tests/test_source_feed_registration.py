import copy
import json
import unittest
from pathlib import Path
from uuid import uuid4

from FOIHireloom.dto.ckan import CkanResource
from FOIHireloom.exceptions import SourceFeedRegistrationError
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.source_feed_registration import SourceFeedRegistrationPlanner


class RegistrationPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads((Path(__file__).parent / "fixtures/ckan_package_show.json").read_text())
        occupations = json.loads((Path(__file__).parent / "fixtures/ckan_occupation_package_show.json").read_text())
        self.occupations = [CkanResource.model_validate(row) for row in occupations["result"]["resources"]]
        self.planner = SourceFeedRegistrationPlanner(CroatianCountyCatalog())

    def build(self):
        resources = [CkanResource.model_validate(row) for row in self.payload["result"]["resources"]]
        return self.planner.build(resources, self.occupations)

    def test_real_fixture_maps_all_counties_and_distinguishes_city_from_county(self) -> None:
        plan = self.build()
        self.assertEqual(len(plan.sources), 39)
        self.assertEqual(plan.resources_skipped, 1)
        self.assertEqual({source.county.code for source in plan.sources if source.county}, {c.code for c in self.planner.catalog.definitions})
        self.assertEqual(plan.sources[3].county.name, "Grad Zagreb")
        self.assertEqual(plan.sources[20].county.name, "Zagrebačka županija")
        self.assertEqual(plan.sources[9].county.code, "medimurska")

    def test_catalog_has_one_iso_code_per_county(self) -> None:
        definitions = self.planner.catalog.definitions
        self.assertEqual(sorted(d.iso_code for d in definitions), [f"HR-{number:02d}" for number in range(1, 22)])
        self.assertEqual(self.planner.catalog.match("Zagrebačka").iso_code, "HR-01")
        self.assertEqual(self.planner.catalog.match("Grad Zagreb").iso_code, "HR-21")
        self.assertEqual(self.planner.catalog.match("Međimurska ").iso_code, "HR-20")

    def test_labels_accept_case_spacing_accents_and_name_fallback(self) -> None:
        resource = self.payload["result"]["resources"][6]
        resource.update(description=" ", name="  koprivnicko – krizevacka ZUPANIJA ")
        self.assertEqual(self.build().sources[6].county.code, "koprivnicko-krizevacka")

    def test_inactive_and_non_feed_resources_are_skipped(self) -> None:
        resources = self.payload["result"]["resources"]
        resources.extend([
            dict(resources[0], id=str(uuid4()), state="deleted", description="Unknown"),
            dict(resources[0], id=str(uuid4()), format="PDF", description="Attachment"),
        ])
        plan = self.build()
        self.assertEqual(len(plan.sources), 39)
        self.assertEqual(plan.resources_skipped, 3)

    def test_unknown_active_county_label_is_not_guessed(self) -> None:
        self.payload["result"]["resources"][0]["description"] = "Unknown county"
        with self.assertRaisesRegex(SourceFeedRegistrationError, "Unrecognised"):
            self.build()

    def test_duplicate_ids_or_urls_are_rejected(self) -> None:
        for field in ("id", "url"):
            payload = copy.deepcopy(self.payload)
            payload["result"]["resources"][1][field] = payload["result"]["resources"][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(SourceFeedRegistrationError, "Duplicate"):
                self.planner.build(
                    [CkanResource.model_validate(row) for row in payload["result"]["resources"]], self.occupations
                )

    def test_empty_or_only_eu_resources_are_rejected(self) -> None:
        for resources in ([], [CkanResource.model_validate(self.payload["result"]["resources"][-1])]):
            with self.subTest(resources=resources), self.assertRaisesRegex(SourceFeedRegistrationError, "no supported"):
                self.planner.build(resources, self.occupations)

    def test_occupation_feeds_keep_their_ckan_label_without_a_county(self) -> None:
        occupations = [source for source in self.build().sources if source.scope == "occupation"]
        self.assertEqual(len(occupations), 18)
        self.assertTrue(all(source.county is None for source in occupations))
        self.assertEqual(occupations[0].label, "Direktori, menadžeri i čelnici")
        self.assertEqual(str(occupations[0].resource.url), "http://burzarada.hzz.hr/rss/rsskat1001.xml")

    def test_missing_occupation_feeds_and_urls_shared_across_datasets_are_rejected(self) -> None:
        resources = [CkanResource.model_validate(row) for row in self.payload["result"]["resources"]]
        inactive = [resource.model_copy(update={"state": "deleted"}) for resource in self.occupations]
        for occupations in ([], inactive):
            with self.subTest(occupations=len(occupations)), self.assertRaisesRegex(SourceFeedRegistrationError, "occupation"):
                self.planner.build(resources, occupations)
        shared = [self.occupations[0].model_copy(update={"url": resources[0].url})]
        with self.assertRaisesRegex(SourceFeedRegistrationError, "Duplicate"):
            self.planner.build(resources, shared)

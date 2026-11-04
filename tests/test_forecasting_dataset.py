import unittest

from FOIHireloom.forecasting import ForecastDatasetBuilder, ForecastPointDTO


class ForecastDatasetBuilderTests(unittest.TestCase):
    def test_build_groups_and_sorts_series(self) -> None:
        rows = [
            {"date": "2024-01-01", "region": "Zagreb", "metric": "vacancies", "value": 10.0, "source": "ckan"},
            {"date": "2023-12-01", "region": "Zagreb", "metric": "vacancies", "value": 7.5, "source": "ckan"},
            {"date": "2024-01-01", "region": "Istra", "metric": "unemployment", "value": 12.0, "source": "dzs"},
        ]

        dataset = ForecastDatasetBuilder.from_rows(rows)
        series = dataset.by_region_metric("Zagreb", "vacancies")

        self.assertEqual([point.date.isoformat() for point in series], ["2023-12-01", "2024-01-01"])
        self.assertEqual(series[0].value, 7.5)
        self.assertEqual(series[1].value, 10.0)

    def test_points_validate_date_and_value(self) -> None:
        point = ForecastPointDTO(
            date="2024-02-01",
            region="Split-Dalmatia",
            metric="unemployment_rate",
            value=5.4,
            source="dzs",
        )
        self.assertEqual(point.region, "Split-Dalmatia")
        self.assertEqual(point.metric, "unemployment_rate")
        self.assertAlmostEqual(point.value, 5.4)

    def test_builder_rejects_missing_required_fields(self) -> None:
        with self.assertRaises(ValueError):
            ForecastDatasetBuilder.from_rows([{"date": "2024-01-01", "metric": "vacancies", "value": 3.0}])

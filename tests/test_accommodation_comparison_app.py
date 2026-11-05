import unittest
from contextlib import asynccontextmanager
from datetime import date

from fastmcp import Client
from fastmcp.exceptions import ToolError

from FOIHireloom.api.apps.accommodation_comparison import accommodation_comparison
from FOIHireloom.api.apps.views import ACCOMMODATION_COMPARISON
from FOIHireloom.api.mcp_server import INSTRUCTIONS, McpServer
from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO, MarketCountDTO
from FOIHireloom.dto.job_search import CoverageDTO
from FOIHireloom.exceptions import InvalidJobSearchError
from test_mcp_server import FakeJobSearchService, NO_BREAKDOWNS


def stats(jobs=10, counts=(('shared', 2), ('single', 1), ('family', 1), ('none', 5))):
    return JobMarketStatsDTO(
        jobs=jobs, with_details=jobs, with_category=0, category_from_description=0, category_from_feed=0,
        workers_needed=999, published_recently=0, closing_soon=0, counties=(),
        **(NO_BREAKDOWNS | {'accommodation': tuple(MarketCountDTO(name=name, jobs=count, workers_needed=100)
                                                  for name, count in counts)}),
        today=date(2026, 11, 2), coverage=CoverageDTO(data_status='fresh', data_as_of=None,
                                                   stale_after_hours=6, affected_regions=(), warning=None),
    )


class AccommodationComparisonAppTests(unittest.TestCase):
    def test_groups_partition_ads_not_workers_and_keep_all_known_types(self):
        source = stats()
        chart = accommodation_comparison(source, JobMarketFiltersDTO())
        self.assertEqual((chart.total_jobs, chart.known_jobs), (10, 9))
        self.assertEqual([(g.key, g.jobs, g.share) for g in chart.groups],
                         [('offered', 4, 40), ('not_offered', 5, 50), ('unknown', 1, 10)])
        self.assertEqual(chart.accommodation_types, source.accommodation)
        self.assertEqual(sum(g.jobs for g in chart.groups), source.jobs)

    def test_unknown_is_separate_from_unknown_other_conditions(self):
        source = stats().model_copy(update={'unknown_conditions': {'full_time': 4}, 'unknown_total': 4})
        chart = accommodation_comparison(source, JobMarketFiltersDTO(full_time=True))
        self.assertEqual((chart.groups[2].jobs, chart.unknown_total), (1, 4))
        self.assertIn('Još 4 oglasa', chart.unknown_note)

    def test_empty_and_completely_unknown_results_keep_three_explicit_groups(self):
        empty = accommodation_comparison(stats(0, ()), JobMarketFiltersDTO())
        self.assertEqual([(g.jobs, g.share) for g in empty.groups], [(0, 0)] * 3)
        missing = accommodation_comparison(stats(10, ()), JobMarketFiltersDTO())
        self.assertEqual([(g.jobs, g.share) for g in missing.groups], [(0, 0), (0, 0), (10, 100)])

    def test_context_names_county_query_category_and_day_and_warns_about_scope(self):
        chart = accommodation_comparison(stats(), JobMarketFiltersDTO(
            county='varazdinska', query='kuhar', category='UGOSTITELJI', include_expired=True))
        for text in ('Varaždinska', 'kuhar', 'UGOSTITELJI', 'svi oglasi na dan 02. 11. 2026.'):
            self.assertIn(text, chart.description)
        self.assertIn('nije stroga klasifikacija', ' '.join(chart.view_notes))
        self.assertIn('kategorija poznata', ' '.join(chart.view_notes))
        self.assertIn('Nepoznat podatak ne znači', ' '.join(chart.view_notes))

    def test_coverage_warning_survives(self):
        coverage = stats().coverage.model_copy(update={'data_status': 'unavailable'})
        chart = accommodation_comparison(stats().model_copy(update={'coverage': coverage}), JobMarketFiltersDTO())
        self.assertTrue(chart.coverage_note)
        self.assertEqual(chart.coverage.data_status, 'unavailable')

    def test_comparison_cannot_be_biased_by_accommodation_filter_or_invalid_totals(self):
        for value in (True, False):
            with self.assertRaises(ValueError):
                accommodation_comparison(stats(), JobMarketFiltersDTO(accommodation=value))
        with self.assertRaises(ValueError):
            accommodation_comparison(stats(1), JobMarketFiltersDTO())
        with self.assertRaises(ValueError):
            accommodation_comparison(stats(10, (('hotel', 1),)), JobMarketFiltersDTO())

    def test_built_page_has_the_supplied_ring_features_and_no_external_assets(self):
        page = ACCOMMODATION_COMPARISON.page()
        for text in ('allocation-ring', 'allocation-glass', 'Nudi smještaj', 'Bez smještaja', 'Podatak nije poznat',
                     'prikazanim oglasima', 'Udjeli skupina smještaja', 'Nema oglasa za zadane filtre.'):
            self.assertIn(text, page)
        for text in ('src="http', '<link', 'of portfolio', 'Equities'):
            self.assertNotIn(text, page)


class AccommodationMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_routes_filters_and_serves_the_built_resource(self):
        service = FakeJobSearchService()

        @asynccontextmanager
        async def open_service():
            yield service

        server = McpServer(Settings(_env_file=None), job_search_service=open_service).server
        async with Client(server) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'show_accommodation_comparison')
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.openWorldHint)
            self.assertNotIn('accommodation', tool.inputSchema['properties'])
            self.assertIn('show_accommodation_comparison', INSTRUCTIONS)
            uri = tool.meta['ui']['resourceUri']
            self.assertEqual(uri, ACCOMMODATION_COMPARISON.uri)
            self.assertEqual((await client.read_resource(uri))[0].text, ACCOMMODATION_COMPARISON.page())
            result = await client.call_tool('show_accommodation_comparison', {
                'county': 'varazdinska', 'query': 'kuhar', 'category': 'UGOSTITELJI', 'full_time': True,
                'contract': 'permanent', 'education': 'secondary_3', 'max_experience_months': 12,
                'employment_tags': ['seasonal'], 'place': 'Varaždin', 'include_expired': True,
                'skills': ['excel'],
            })
            filters = service.market_filters[-1]
            self.assertEqual((filters.county, filters.query, filters.category), ('varazdinska', 'kuhar', 'UGOSTITELJI'))
            self.assertEqual((filters.accommodation, filters.full_time, filters.contract), (None, True, 'permanent'))
            self.assertEqual((filters.education, filters.max_experience_months, filters.employment_tags),
                             ('secondary_3', 12, ('seasonal',)))
            self.assertEqual((filters.place, filters.include_expired), ('Varaždin', True))
            self.assertEqual(filters.skills, ('excel',))
            self.assertEqual(result.structured_content['total_jobs'], 0)
            self.assertEqual(len(result.structured_content['groups']), 3)
            service.error = InvalidJobSearchError('Unknown county')
            with self.assertRaisesRegex(ToolError, 'Unknown county'):
                await client.call_tool('show_accommodation_comparison', {'county': 'missing'})

import copy
import json
import unittest
from pathlib import Path
from uuid import UUID

import httpx

from FOIHireloom.integrations.ckan_client import (
    CkanApiError, CkanClient, CkanHttpError, CkanResponseError, CkanTransportError,
)


class CkanClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.payload = json.loads((Path(__file__).parent / "fixtures/ckan_package_show.json").read_text())

    async def test_real_metadata_shape_supports_null_name_and_description_labels(self) -> None:
        requests = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=self.payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = CkanClient(http, "https://data.gov.hr/ckan/", timeout=2)
            resources = await client.get_resources("dataset slug")
            self.assertEqual(len(resources), 22)
            self.assertIsNone(resources[0].name)
            self.assertEqual(resources[0].description, "BJELOVARSKO-BILOGORSKA")
            self.assertIsInstance(resources[0].id, UUID)
            self.assertEqual(resources[-1].description, "Poslovi u EU")
            self.assertFalse(http.is_closed)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].method, "GET")
        self.assertEqual(requests[0].url.path, "/ckan/api/3/action/package_show")
        self.assertEqual(requests[0].url.params["id"], "dataset slug")
        self.assertEqual(requests[0].extensions["timeout"]["read"], 2)

    async def test_http_errors_preserve_status(self) -> None:
        for status in (404, 429, 500, 503):
            with self.subTest(status=status):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(status, text="upstream error")
                )) as http:
                    with self.assertRaises(CkanHttpError) as error:
                        await CkanClient(http).get_resources("dataset")
                self.assertEqual(error.exception.status_code, status)

    async def test_http_200_with_unsuccessful_action_is_an_api_error(self) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"success": False, "error": {"__type": "Not Found Error"}})
        )) as http:
            with self.assertRaises(CkanApiError):
                await CkanClient(http).get_resources("missing")

    async def test_invalid_envelopes_and_resource_fields_fail_explicitly(self) -> None:
        invalid = [[], {}, {"success": "true"}, {"success": True, "result": {}},
                   {"success": True, "result": {"resources": {}}}]
        for field, value in [("id", "not-a-uuid"), ("url", "file:///etc/passwd")]:
            payload = copy.deepcopy(self.payload)
            payload["result"]["resources"][0][field] = value
            invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=payload)
                )) as http:
                    with self.assertRaises(CkanResponseError):
                        await CkanClient(http).get_resources("dataset")

    async def test_html_response_is_not_treated_as_an_empty_dataset(self) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>proxy error</html>")
        )) as http:
            with self.assertRaises(CkanResponseError):
                await CkanClient(http).get_resources("dataset")

    async def test_transport_errors_are_reported_without_retrying_or_closing_injected_client(self) -> None:
        for exception in (httpx.ConnectError, httpx.ReadTimeout):
            calls = []

            def fail(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                raise exception("dependency unavailable", request=request)

            async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as http:
                with self.assertRaises(CkanTransportError):
                    await CkanClient(http).get_resources("dataset")
                self.assertFalse(http.is_closed)
            self.assertEqual(len(calls), 1)

    async def test_blank_dataset_and_invalid_configuration_are_rejected(self) -> None:
        async with httpx.AsyncClient() as http:
            with self.assertRaises(ValueError):
                await CkanClient(http).get_resources(" ")
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    CkanClient(http, timeout=timeout)
            for url in ("file:///tmp/ckan", "https://data.gov.hr/ckan?query=1"):
                with self.assertRaises(ValueError):
                    CkanClient(http, base_url=url)

from __future__ import annotations

import json

import httpx
import pytest

from app.course_catalog.schemas import CourseAvailability, CourseSourceType
from app.course_catalog.skillscommons import (
    SkillsCommonsAccessStatus,
    SkillsCommonsBitstreamType,
    SkillsCommonsCourseProvider,
    SkillsCommonsLearningAccess,
    SkillsCommonsMaterialType,
    SkillsCommonsProviderError,
    classify_bitstream,
    classify_material_type,
    to_normalized_candidate,
)

UUID = "033ef675-a2dc-426b-b174-eac304086ec6"
BUNDLE_UUID = "0c9f81f5-d4b0-4969-bc6d-6c04f320e1d0"
BITSTREAM_UUID = "2445a76d-538b-4606-bed3-4015c83f30e8"
BASE = "https://library.skillscommons.org/server"


def item_payload(*, material_type: str = "Online Course", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "uuid": UUID,
        "name": "Environmental Science Course",
        "handle": "taaccct/7823",
        "lastModified": "2016-04-27T15:42:21Z",
        "inArchive": True,
        "withdrawn": False,
        "discoverable": True,
        "metadata": {
            "dc.title": [{"value": "Environmental Science Course", "language": "en"}],
            "dc.description.abstract": [{"value": "A complete course."}],
            "dc.type": [{"value": material_type}],
            "dc.identifier.uri": [
                {"value": "https://library.skillscommons.org/handle/taaccct/7823"}
            ],
            "dc.language": [{"value": "en"}],
            "dcterms.license": [{"value": "CC BY"}],
            "taaccct.deliveryFormat": [{"value": "Online"}],
        },
        "_links": {
            "bundles": {"href": f"{BASE}/api/core/items/{UUID}/bundles"},
            "self": {"href": f"{BASE}/api/core/items/{UUID}"},
        },
    }
    payload.update(overrides)
    return payload


def bundle_payload() -> dict[str, object]:
    return {
        "uuid": BUNDLE_UUID,
        "name": "ORIGINAL",
        "_links": {"bitstreams": {"href": f"{BASE}/api/core/bundles/{BUNDLE_UUID}/bitstreams"}},
    }


def bitstream_payload(*, package: bool = False) -> dict[str, object]:
    name = "SCORM course package.zip" if package else "course materials.zip"
    return {
        "uuid": BITSTREAM_UUID,
        "name": name,
        "sizeBytes": 2048,
        "mimeType": "application/zip",
        "checksum": "abc",
        "_links": {"content": {"href": f"{BASE}/api/core/bitstreams/{BITSTREAM_UUID}/content"}},
    }


def search_payload() -> dict[str, object]:
    return {
        "_embedded": {
            "searchResult": {
                "page": {"totalElements": 2, "size": 2, "number": 0, "totalPages": 1},
                "_embedded": {
                    "objects": [
                        {"_links": {"indexableObject": {"href": f"{BASE}/api/core/items/{UUID}"}}},
                        {"_links": {"indexableObject": {"href": f"{BASE}/api/core/items/{UUID}2"}}},
                    ]
                },
            }
        }
    }


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.asyncio
async def test_bounded_post_filter_fetches_exact_type_and_traverses_hal() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/discover/search/objects"):
            return httpx.Response(200, json=search_payload(), request=request)
        if request.url.path.endswith(f"/items/{UUID}"):
            return httpx.Response(200, json=item_payload(), request=request)
        if request.url.path.endswith("/items/" + UUID + "2"):
            return httpx.Response(
                200, json=item_payload(material_type="Online Course Module"), request=request
            )
        if request.url.path.endswith(f"/items/{UUID}/bundles"):
            return httpx.Response(
                200, json={"_embedded": {"bundles": [bundle_payload()]}}, request=request
            )
        if request.url.path.endswith(f"/bundles/{BUNDLE_UUID}/bitstreams"):
            return httpx.Response(
                200, json={"_embedded": {"bitstreams": [bitstream_payload()]}}, request=request
            )
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"content-type": "application/zip", "accept-ranges": "bytes"},
                request=request,
            )
        raise AssertionError(request.url)

    async with client(handler) as http_client:
        provider = SkillsCommonsCourseProvider(client=http_client, resolver=public_resolver)
        sample = await provider.live_sample(target_full_courses=30)

    assert sample.raw_search_results_seen == 2
    assert sample.exact_online_course_candidates == 1
    assessment = sample.assessments[0]
    assert assessment.material_type is SkillsCommonsMaterialType.ONLINE_COURSE
    assert len(assessment.bundles) == 1
    assert len(assessment.bitstreams) == 1
    assert assessment.learning_access is SkillsCommonsLearningAccess.HOSTED_COURSEWARE
    assert assessment.strict_provider_candidate is True
    assert assessment.external_course is not None
    assert assessment.normalized_candidate is not None
    assert assessment.normalized_candidate.course_ref == f"skillscommons:{UUID}"
    assert assessment.normalized_candidate.capabilities == []
    assert assessment.normalized_candidate.target_level is None
    assert assessment.normalized_candidate.prerequisites == []
    assert requests[0].url.params["query"] == "Online Course"
    assert requests[0].url.params["page"] == "0"


@pytest.mark.asyncio
async def test_explicit_course_package_is_strict_candidate() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/items/{UUID}/bundles"):
            return httpx.Response(
                200, json={"_embedded": {"bundles": [bundle_payload()]}}, request=request
            )
        if request.url.path.endswith(f"/bundles/{BUNDLE_UUID}/bitstreams"):
            return httpx.Response(
                200,
                json={"_embedded": {"bitstreams": [bitstream_payload(package=True)]}},
                request=request,
            )
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "application/zip"}, request=request)
        raise AssertionError(request.url)

    async with client(handler) as http_client:
        provider = SkillsCommonsCourseProvider(client=http_client, resolver=public_resolver)
        payload = item_payload()
        metadata = payload["metadata"]
        assert isinstance(metadata, dict)
        metadata.pop("dc.identifier.uri")
        assessment = await provider.assess_item(provider._parse_item(payload))

    assert assessment.learning_access is SkillsCommonsLearningAccess.DOWNLOADABLE_COURSE_PACKAGE
    assert assessment.strict_provider_candidate is True


def test_exact_material_type_and_bitstream_classification() -> None:
    assert classify_material_type(("Online Course",)) is SkillsCommonsMaterialType.ONLINE_COURSE
    assert (
        classify_material_type(("Online Course Module",)) is SkillsCommonsMaterialType.COURSE_MODULE
    )
    assert (
        classify_material_type(("Course about online learning",))
        is SkillsCommonsMaterialType.UNKNOWN
    )
    assert (
        classify_bitstream("SCORM course package.zip", "application/zip", {})
        is SkillsCommonsBitstreamType.COURSE_PACKAGE
    )
    assert (
        classify_bitstream("course-export.imscc", None, {})
        is SkillsCommonsBitstreamType.COURSE_PACKAGE
    )
    assert (
        classify_bitstream("course materials.zip", "application/zip", {})
        is SkillsCommonsBitstreamType.ARCHIVE
    )


def test_normalization_keeps_capability_boundary() -> None:
    item = SkillsCommonsCourseProvider._parse_item(item_payload())
    course = __import__(
        "app.course_catalog.skillscommons", fromlist=["SkillsCommonsCourseProvider"]
    ).SkillsCommonsCourseProvider._to_external_course
    # Build the public contract through the provider method without network access.
    provider = SkillsCommonsCourseProvider()
    external = course(provider, item, ())
    candidate = to_normalized_candidate(external)
    assert candidate.source_type is CourseSourceType.EXTERNAL
    assert candidate.source_system == "skillscommons"
    assert candidate.availability is CourseAvailability.AVAILABLE
    assert candidate.capabilities == []
    assert candidate.target_level is None
    assert candidate.prerequisites == []
    assert candidate.provenance[0].source_ref == UUID


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 410, 429, 500])
async def test_access_status_mapping(status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, request=request)

    async with client(handler) as http_client:
        provider = SkillsCommonsCourseProvider(client=http_client, resolver=public_resolver)
        result = await provider.verify_access(
            "https://library.skillscommons.org/server/api/core/bitstreams/x/content"
        )

    expected = {
        401: SkillsCommonsAccessStatus.RESTRICTED,
        403: SkillsCommonsAccessStatus.RESTRICTED,
        404: SkillsCommonsAccessStatus.BROKEN,
        410: SkillsCommonsAccessStatus.BROKEN,
    }.get(status, SkillsCommonsAccessStatus.UNKNOWN)
    assert result.status is expected


@pytest.mark.asyncio
async def test_head_fallback_is_bounded_and_redirect_to_private_is_blocked() -> None:
    methods: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(405, request=request)
        return httpx.Response(206, content=b"small", request=request)

    async with client(handler) as http_client:
        provider = SkillsCommonsCourseProvider(client=http_client, resolver=public_resolver)
        result = await provider.verify_access(
            "https://library.skillscommons.org/server/api/content"
        )
    assert result.status is SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE
    assert methods == ["HEAD", "GET"]

    async def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"}, request=request)

    async with client(redirect_handler) as http_client:
        provider = SkillsCommonsCourseProvider(client=http_client, resolver=public_resolver)
        result = await provider.verify_access(
            "https://library.skillscommons.org/server/api/content"
        )
    assert result.status is SkillsCommonsAccessStatus.UNKNOWN
    assert result.reason == "unsafe redirect target"


def test_malformed_hal_and_unsafe_configuration_fail_closed() -> None:
    with pytest.raises(SkillsCommonsProviderError, match="missing _embedded"):
        SkillsCommonsCourseProvider._embedded_list({}, "bundles")
    with pytest.raises(ValueError, match="library.skillscommons.org"):
        SkillsCommonsCourseProvider(base_url="https://www.skillscommons.org/server")


def test_fixture_is_json_serializable() -> None:
    assert (
        json.loads(json.dumps(item_payload()))["metadata"]["dc.type"][0]["value"] == "Online Course"
    )

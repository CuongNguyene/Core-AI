"""Bounded SkillsCommons DSpace REST/HAL provider.

The provider uses the current public DSpace API. It deliberately stops at
provider-grounded course facts: capabilities stay empty, target level stays
unset, and no recommendation or semantic enrichment is performed.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

import httpx

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseProvenance,
    CourseSourceType,
    ExternalCourse,
    NormalizedCourseCandidate,
)


class SkillsCommonsProviderError(RuntimeError):
    """Safe, bounded failure from SkillsCommons or malformed HAL."""


class SkillsCommonsMaterialType(StrEnum):
    ONLINE_COURSE = "ONLINE_COURSE"
    HYBRID_COURSE = "HYBRID_COURSE"
    COURSE_MODULE = "COURSE_MODULE"
    LEARNING_RESOURCE = "LEARNING_RESOURCE"
    UNKNOWN = "UNKNOWN"


class SkillsCommonsAccessStatus(StrEnum):
    VERIFIED_ACCESSIBLE = "VERIFIED_ACCESSIBLE"
    RESTRICTED = "RESTRICTED"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class SkillsCommonsLearningAccess(StrEnum):
    HOSTED_COURSEWARE = "HOSTED_COURSEWARE"
    DOWNLOADABLE_COURSE_PACKAGE = "DOWNLOADABLE_COURSE_PACKAGE"
    DOWNLOADABLE_MATERIALS = "DOWNLOADABLE_MATERIALS"
    RESTRICTED = "RESTRICTED"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class SkillsCommonsBitstreamType(StrEnum):
    COURSE_PACKAGE = "COURSE_PACKAGE"
    DOCUMENT = "DOCUMENT"
    SLIDES = "SLIDES"
    VIDEO = "VIDEO"
    ARCHIVE = "ARCHIVE"
    TEXT = "TEXT"
    UNKNOWN = "UNKNOWN"


class SkillsCommonsLicenseStatus(StrEnum):
    KNOWN_OPEN = "KNOWN_OPEN"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SkillsCommonsDspaceItem:
    uuid: str
    handle: str | None
    name: str | None
    metadata: Mapping[str, tuple[str, ...]]
    last_modified: str | None
    in_archive: bool | None
    withdrawn: bool | None
    discoverable: bool | None
    entity_type: str | None
    links: Mapping[str, str]

    def values(self, key: str) -> tuple[str, ...]:
        return self.metadata.get(key, ())


@dataclass(frozen=True)
class SkillsCommonsDspaceBundle:
    uuid: str
    name: str | None
    metadata: Mapping[str, tuple[str, ...]]
    links: Mapping[str, str]


@dataclass(frozen=True)
class SkillsCommonsDspaceBitstream:
    uuid: str
    name: str | None
    size_bytes: int | None
    mime_type: str | None
    checksum: str | None
    description: str | None
    metadata: Mapping[str, tuple[str, ...]]
    content_url: str | None
    bundle_name: str | None
    bitstream_type: SkillsCommonsBitstreamType


@dataclass(frozen=True)
class SkillsCommonsAccessVerification:
    url: str
    status: SkillsCommonsAccessStatus
    http_status: int | None = None
    final_url: str | None = None
    method: str | None = None
    content_type: str | None = None
    content_length: str | None = None
    accept_ranges: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SkillsCommonsCourseAssessment:
    item: SkillsCommonsDspaceItem
    bundles: tuple[SkillsCommonsDspaceBundle, ...]
    bitstreams: tuple[SkillsCommonsDspaceBitstream, ...]
    material_type: SkillsCommonsMaterialType
    license_status: SkillsCommonsLicenseStatus
    access_verifications: tuple[SkillsCommonsAccessVerification, ...]
    learning_access: SkillsCommonsLearningAccess
    strict_provider_candidate: bool
    external_course: ExternalCourse | None
    normalized_candidate: NormalizedCourseCandidate | None
    error: str | None = None


@dataclass(frozen=True)
class SkillsCommonsLiveSample:
    raw_search_results_seen: int
    exact_online_course_candidates: int
    assessments: tuple[SkillsCommonsCourseAssessment, ...]
    raw_type_counts: Mapping[str, int]
    items_fetched_success: int
    items_fetched_failure: int

    @property
    def strict_candidates(self) -> tuple[SkillsCommonsCourseAssessment, ...]:
        return tuple(item for item in self.assessments if item.strict_provider_candidate)


_OPEN_LICENSES = {
    "CC BY",
    "CC BY-SA",
    "CC BY-ND",
    "CC BY-NC",
    "CC BY-NC-SA",
    "CC BY-NC-ND",
    "Public Domain",
    "CC0",
}
_MATERIAL_TYPE_KEY = "dc.type"
_PACKAGE_WORDS = ("course package", "scorm", "common cartridge", "ims package", "lms export")
_PUBLIC_HOSTS = {"library.skillscommons.org", "partner.skillscommons.org", "www.skillscommons.org"}


def classify_material_type(material_types: Sequence[str]) -> SkillsCommonsMaterialType:
    """Classify only exact DSpace metadata values."""
    values = set(material_types)
    if "Online Course" in values:
        return SkillsCommonsMaterialType.ONLINE_COURSE
    if "Hybrid/Blended Course" in values:
        return SkillsCommonsMaterialType.HYBRID_COURSE
    if "Online Course Module" in values:
        return SkillsCommonsMaterialType.COURSE_MODULE
    if values.intersection(
        {
            "Tutorial",
            "Open Textbook",
            "Video - Instructional",
            "Syllabus",
            "Assignment",
            "Quiz/Test",
            "Reference Material",
        }
    ):
        return SkillsCommonsMaterialType.LEARNING_RESOURCE
    return SkillsCommonsMaterialType.UNKNOWN


def normalize_license(raw: str | None) -> SkillsCommonsLicenseStatus:
    if raw is None or not raw.strip():
        return SkillsCommonsLicenseStatus.UNKNOWN
    return (
        SkillsCommonsLicenseStatus.KNOWN_OPEN
        if raw in _OPEN_LICENSES
        else SkillsCommonsLicenseStatus.OTHER
    )


def classify_bitstream(
    name: str | None, mime_type: str | None, metadata: Mapping[str, tuple[str, ...]]
) -> SkillsCommonsBitstreamType:
    haystack = " ".join(
        (name or "", mime_type or "", *(value for values in metadata.values() for value in values))
    ).lower()
    suffix = PurePosixPath(name or "").suffix.lower()
    if any(word in haystack for word in _PACKAGE_WORDS) or suffix in {".imscc", ".imsmanifest"}:
        return SkillsCommonsBitstreamType.COURSE_PACKAGE
    if suffix in {".zip", ".tar", ".gz", ".7z", ".rar"} or "zip" in (mime_type or "").lower():
        return SkillsCommonsBitstreamType.ARCHIVE
    if (mime_type or "").startswith("video/") or suffix in {".mp4", ".webm", ".mov", ".avi"}:
        return SkillsCommonsBitstreamType.VIDEO
    if "presentation" in (mime_type or "").lower() or suffix in {".ppt", ".pptx", ".odp"}:
        return SkillsCommonsBitstreamType.SLIDES
    if (mime_type or "").startswith("text/") or suffix in {".txt", ".html", ".htm", ".md"}:
        return SkillsCommonsBitstreamType.TEXT
    if "pdf" in (mime_type or "").lower() or suffix in {".doc", ".docx", ".pdf", ".rtf"}:
        return SkillsCommonsBitstreamType.DOCUMENT
    return SkillsCommonsBitstreamType.UNKNOWN


class SkillsCommonsCourseProvider:
    provider_ref = "skillscommons"
    source_system = "skillscommons"
    base_url = "https://library.skillscommons.org/server"
    material_type_key = _MATERIAL_TYPE_KEY
    search_query = "Online Course"
    max_redirects = 3

    def __init__(
        self,
        base_url: str = base_url,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
        max_pages: int = 5,
        max_records: int = 200,
        max_response_bytes: int = 2 * 1024 * 1024,
        max_access_body_bytes: int = 32 * 1024,
        resolver: Callable[[str], Sequence[str]] | None = None,
    ) -> None:
        parsed = urlsplit(base_url.rstrip("/"))
        if parsed.scheme != "https" or parsed.hostname != "library.skillscommons.org":
            raise ValueError("SkillsCommons base_url must use library.skillscommons.org over HTTPS")
        if timeout_seconds <= 0 or max_pages < 1 or max_records < 1:
            raise ValueError("SkillsCommons bounds must be positive")
        self._base_url = base_url.rstrip("/")
        self._api_base = f"{self._base_url}/api"
        self._client = client
        self._timeout_seconds = min(timeout_seconds, 60.0)
        self._max_pages = min(max_pages, 5)
        self._max_records = min(max_records, 200)
        self._max_response_bytes = max_response_bytes
        self._max_access_body_bytes = max_access_body_bytes
        self._resolver = resolver or self._resolve_host

    async def list_courses(self, limit: int = 50) -> tuple[ExternalCourse, ...]:
        sample = await self.live_sample(target_full_courses=min(limit, 30))
        return tuple(
            item.external_course
            for item in sample.strict_candidates
            if item.external_course is not None
        )

    async def list_candidates(self, limit: int = 50) -> tuple[NormalizedCourseCandidate, ...]:
        sample = await self.live_sample(target_full_courses=min(limit, 30))
        return tuple(
            item.normalized_candidate
            for item in sample.assessments
            if item.normalized_candidate is not None
        )

    async def get_course(self, provider_course_id: str) -> ExternalCourse:
        item = await self.fetch_item(provider_course_id)
        assessment = await self.assess_item(item)
        if assessment.external_course is None:
            raise SkillsCommonsProviderError(
                assessment.error or "course is not an eligible external course"
            )
        return assessment.external_course

    async def live_sample(self, *, target_full_courses: int = 30) -> SkillsCommonsLiveSample:
        target = min(max(target_full_courses, 1), 30)
        raw_seen = 0
        exact_items: list[SkillsCommonsDspaceItem] = []
        seen_ids: set[str] = set()
        raw_type_counts: dict[str, int] = {}
        fetched_success = 0
        fetched_failure = 0
        page_size = min(40, self._max_records)
        for page in range(self._max_pages):
            remaining = self._max_records - raw_seen
            if remaining <= 0:
                break
            refs = await self._search_item_refs(page=page, size=min(page_size, remaining))
            if not refs:
                break
            raw_seen += len(refs)
            items, failures = await self._fetch_items_bounded(refs)
            fetched_success += len(items)
            fetched_failure += failures
            for item in items:
                if item.uuid in seen_ids:
                    continue
                seen_ids.add(item.uuid)
                raw_types = item.values(self.material_type_key)
                raw_type = raw_types[0] if raw_types else "UNKNOWN"
                raw_type_counts[raw_type] = raw_type_counts.get(raw_type, 0) + 1
                if (
                    classify_material_type(item.values(self.material_type_key))
                    is SkillsCommonsMaterialType.ONLINE_COURSE
                ):
                    exact_items.append(item)
            if len(exact_items) >= target or len(refs) < page_size:
                break
        assessments = tuple(
            await asyncio.gather(*(self.assess_item(item) for item in exact_items[:target]))
        )
        return SkillsCommonsLiveSample(
            raw_seen,
            len(exact_items),
            assessments,
            raw_type_counts,
            fetched_success,
            fetched_failure,
        )

    async def fetch_item(self, provider_course_id: str) -> SkillsCommonsDspaceItem:
        if not self._looks_like_uuid(provider_course_id):
            raise SkillsCommonsProviderError("provider course ID must be a DSpace UUID")
        payload = await self._request_json(f"{self._api_base}/core/items/{provider_course_id}")
        return self._parse_item(payload)

    async def assess_item(self, item: SkillsCommonsDspaceItem) -> SkillsCommonsCourseAssessment:
        material_type = classify_material_type(item.values(self.material_type_key))
        if material_type is not SkillsCommonsMaterialType.ONLINE_COURSE:
            return self._empty_assessment(item, material_type, "item is not an exact Online Course")
        if not item.name and not item.values("dc.title"):
            return self._empty_assessment(item, material_type, "item has no title")
        try:
            bundles = await self.fetch_bundles(item)
            bitstreams = await self.fetch_bitstreams(bundles)
            urls = list(self._external_learning_urls(item))
            urls.extend(stream.content_url for stream in bitstreams if stream.content_url)
            verifications = tuple(await self._verify_many([url for url in urls if url]))
            learning_access = self.classify_learning_access(item, bitstreams, verifications)
            external = self._to_external_course(item, verifications)
            candidate = to_normalized_candidate(external)
            strict = (
                item.withdrawn is not True
                and item.discoverable is not False
                and item.in_archive is not False
                and learning_access
                in {
                    SkillsCommonsLearningAccess.HOSTED_COURSEWARE,
                    SkillsCommonsLearningAccess.DOWNLOADABLE_COURSE_PACKAGE,
                }
            )
            return SkillsCommonsCourseAssessment(
                item,
                bundles,
                bitstreams,
                material_type,
                normalize_license(self._first(item, "dcterms.license")),
                verifications,
                learning_access,
                strict,
                external,
                candidate,
            )
        except SkillsCommonsProviderError as exc:
            return self._empty_assessment(item, material_type, str(exc))

    async def fetch_bundles(
        self, item: SkillsCommonsDspaceItem
    ) -> tuple[SkillsCommonsDspaceBundle, ...]:
        href = item.links.get("bundles", f"{self._api_base}/core/items/{item.uuid}/bundles")
        payload = await self._request_json(self._trusted_api_url(href))
        return tuple(self._parse_bundle(value) for value in self._embedded_list(payload, "bundles"))

    async def fetch_bitstreams(
        self, bundles: Sequence[SkillsCommonsDspaceBundle]
    ) -> tuple[SkillsCommonsDspaceBitstream, ...]:
        streams: list[SkillsCommonsDspaceBitstream] = []
        for bundle in bundles:
            href = bundle.links.get("bitstreams")
            if not href:
                continue
            payload = await self._request_json(self._trusted_api_url(href))
            streams.extend(
                self._parse_bitstream(value, bundle.name)
                for value in self._embedded_list(payload, "bitstreams")
            )
        return tuple(streams)

    def classify_learning_access(
        self,
        item: SkillsCommonsDspaceItem,
        bitstreams: Sequence[SkillsCommonsDspaceBitstream],
        verifications: Sequence[SkillsCommonsAccessVerification],
    ) -> SkillsCommonsLearningAccess:
        external_count = len(self._external_learning_urls(item))
        hosted = verifications[:external_count]
        file_results = verifications[external_count:]
        if any(result.status is SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE for result in hosted):
            return SkillsCommonsLearningAccess.HOSTED_COURSEWARE
        package_ids = {
            stream.uuid
            for stream in bitstreams
            if stream.bitstream_type is SkillsCommonsBitstreamType.COURSE_PACKAGE
        }
        package_results = [
            result
            for stream, result in zip(bitstreams, file_results, strict=False)
            if stream.uuid in package_ids
        ]
        if package_results and any(
            result.status is SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE
            for result in package_results
        ):
            return SkillsCommonsLearningAccess.DOWNLOADABLE_COURSE_PACKAGE
        if any(
            result.status is SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE
            for result in file_results
        ):
            return SkillsCommonsLearningAccess.DOWNLOADABLE_MATERIALS
        all_results = [*hosted, *file_results]
        if all_results and all(
            result.status is SkillsCommonsAccessStatus.RESTRICTED for result in all_results
        ):
            return SkillsCommonsLearningAccess.RESTRICTED
        if all_results and all(
            result.status is SkillsCommonsAccessStatus.BROKEN for result in all_results
        ):
            return SkillsCommonsLearningAccess.BROKEN
        return SkillsCommonsLearningAccess.UNKNOWN

    async def verify_access(self, url: str) -> SkillsCommonsAccessVerification:
        self._validate_public_url(url)
        current = url
        for _ in range(self.max_redirects + 1):
            try:
                status, headers, _ = await self._request_bounded("HEAD", current)
            except (httpx.TimeoutException, httpx.TransportError):
                return SkillsCommonsAccessVerification(
                    url, SkillsCommonsAccessStatus.UNKNOWN, reason="network failure"
                )
            if 300 <= status < 400:
                location = headers.get("location")
                if not location:
                    return SkillsCommonsAccessVerification(
                        url,
                        SkillsCommonsAccessStatus.UNKNOWN,
                        status,
                        current,
                        "HEAD",
                        reason="redirect without location",
                    )
                target = urljoin(current, location)
                try:
                    self._validate_public_url(target)
                except SkillsCommonsProviderError:
                    return SkillsCommonsAccessVerification(
                        url,
                        SkillsCommonsAccessStatus.UNKNOWN,
                        status,
                        target,
                        "HEAD",
                        reason="unsafe redirect target",
                    )
                current = target
                continue
            result = self._access_result(url, current, status, headers, "HEAD")
            if status not in {405, 501}:
                return result
            break
        try:
            status, headers, _ = await self._request_bounded(
                "GET",
                current,
                headers={"Range": f"bytes=0-{self._max_access_body_bytes - 1}"},
                max_bytes=self._max_access_body_bytes,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return SkillsCommonsAccessVerification(
                url, SkillsCommonsAccessStatus.UNKNOWN, reason="network failure"
            )
        if 300 <= status < 400:
            location = headers.get("location")
            target = urljoin(current, location) if location else current
            try:
                self._validate_public_url(target)
            except SkillsCommonsProviderError:
                return SkillsCommonsAccessVerification(
                    url,
                    SkillsCommonsAccessStatus.UNKNOWN,
                    status,
                    target,
                    "GET",
                    reason="unsafe redirect target",
                )
            current = target
        return self._access_result(url, current, status, headers, "GET")

    async def _search_item_refs(self, *, page: int, size: int) -> tuple[str, ...]:
        payload = await self._request_json(
            f"{self._api_base}/discover/search/objects",
            params={"query": self.search_query, "page": str(page), "size": str(size)},
        )
        refs: list[str] = []
        for obj in self._embedded_list(payload, "objects", parent="searchResult"):
            link = self._link(obj, "indexableObject") or self._link(obj, "self")
            if link:
                refs.append(link)
        return tuple(refs)

    async def _fetch_items_bounded(
        self, refs: Sequence[str]
    ) -> tuple[tuple[SkillsCommonsDspaceItem, ...], int]:
        semaphore = asyncio.Semaphore(5)

        async def fetch(ref: str) -> SkillsCommonsDspaceItem:
            async with semaphore:
                return await self.fetch_item(ref.rsplit("/", 1)[-1])

        results = await asyncio.gather(*(fetch(ref) for ref in refs), return_exceptions=True)
        items = tuple(result for result in results if isinstance(result, SkillsCommonsDspaceItem))
        return items, len(results) - len(items)

    async def _verify_many(self, urls: Sequence[str]) -> list[SkillsCommonsAccessVerification]:
        unique = list(dict.fromkeys(urls))
        semaphore = asyncio.Semaphore(5)

        async def bounded(url: str) -> SkillsCommonsAccessVerification:
            async with semaphore:
                return await self.verify_access(url)

        return list(await asyncio.gather(*(bounded(url) for url in unique)))

    async def _request_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> Mapping[str, object]:
        status, headers, body = await self._request_bounded("GET", url, params=params)
        if not 200 <= status < 300:
            raise SkillsCommonsProviderError(f"SkillsCommons returned HTTP {status}")
        if "json" not in headers.get("content-type", "").lower() and not body.lstrip().startswith(
            b"{"
        ):
            raise SkillsCommonsProviderError("SkillsCommons response is not JSON")
        try:
            value = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise SkillsCommonsProviderError("malformed SkillsCommons JSON") from exc
        if not isinstance(value, Mapping):
            raise SkillsCommonsProviderError("SkillsCommons HAL response is not an object")
        return value

    async def _request_bounded(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> tuple[int, httpx.Headers, bytes]:
        limit = max_bytes or self._max_response_bytes

        async def request_with(client: httpx.AsyncClient) -> tuple[int, httpx.Headers, bytes]:
            async with client.stream(
                method,
                url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as response:
                content_length = response.headers.get("content-length")
                if (
                    method != "HEAD"
                    and content_length
                    and content_length.isdigit()
                    and int(content_length) > limit
                ):
                    raise SkillsCommonsProviderError("response exceeds bounded size")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > limit:
                        raise SkillsCommonsProviderError("response exceeds bounded size")
                    chunks.append(chunk)
                return response.status_code, response.headers, b"".join(chunks)

        if self._client is not None:
            return await request_with(self._client)
        async with httpx.AsyncClient() as client:
            return await request_with(client)

    def _to_external_course(
        self,
        item: SkillsCommonsDspaceItem,
        verifications: Sequence[SkillsCommonsAccessVerification],
    ) -> ExternalCourse:
        title = self._first(item, "dc.title") or item.name
        if not title:
            raise SkillsCommonsProviderError("item has no title")
        external_urls = self._external_learning_urls(item)
        verified_url = next(
            (
                result.final_url
                for result in verifications[: len(external_urls)]
                if result.status is SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE
            ),
            None,
        )
        provenance = [
            CourseProvenance(
                kind="provider", source_ref=item.uuid, source_field="uuid", method="dspace_rest_hal"
            )
        ]
        if item.handle:
            provenance.append(
                CourseProvenance(
                    kind="provider",
                    source_ref=item.uuid,
                    source_field="handle",
                    evidence_text=item.handle,
                    method="dspace_rest_hal",
                )
            )
        return ExternalCourse(
            provider_ref=self.provider_ref,
            provider_course_id=item.uuid,
            title=title,
            description=self._first(item, "dc.description.abstract")
            or self._first(item, "dc.description"),
            delivery_mode=self._first(item, "taaccct.deliveryFormat"),
            language=self._first(item, "dc.language"),
            availability=self._availability(item),
            course_url=verified_url or (external_urls[0] if external_urls else None),
            provenance=provenance,
        )

    def _empty_assessment(
        self, item: SkillsCommonsDspaceItem, material_type: SkillsCommonsMaterialType, error: str
    ) -> SkillsCommonsCourseAssessment:
        return SkillsCommonsCourseAssessment(
            item,
            (),
            (),
            material_type,
            SkillsCommonsLicenseStatus.UNKNOWN,
            (),
            SkillsCommonsLearningAccess.UNKNOWN,
            False,
            None,
            None,
            error,
        )

    def _external_learning_urls(self, item: SkillsCommonsDspaceItem) -> tuple[str, ...]:
        keys = (
            "dc.identifier.uri",
            "taaccct.object.uri",
            "taaccct.courseUrl",
            "taaccct.resourceUrl",
        )
        return tuple(
            dict.fromkeys(
                value
                for key in keys
                for value in item.values(key)
                if value.startswith(("http://", "https://"))
            )
        )

    def _availability(self, item: SkillsCommonsDspaceItem) -> CourseAvailability:
        if item.withdrawn is True or item.discoverable is False or item.in_archive is False:
            return CourseAvailability.UNAVAILABLE
        if item.withdrawn is False and item.discoverable is True and item.in_archive is True:
            return CourseAvailability.AVAILABLE
        return CourseAvailability.UNKNOWN

    def _access_result(
        self, original: str, current: str, status: int, headers: httpx.Headers, method: str
    ) -> SkillsCommonsAccessVerification:
        if status in {401, 403}:
            access = SkillsCommonsAccessStatus.RESTRICTED
        elif status in {404, 410}:
            access = SkillsCommonsAccessStatus.BROKEN
        elif 200 <= status < 300:
            access = SkillsCommonsAccessStatus.VERIFIED_ACCESSIBLE
        else:
            access = SkillsCommonsAccessStatus.UNKNOWN
        return SkillsCommonsAccessVerification(
            original,
            access,
            status,
            current,
            method,
            headers.get("content-type"),
            headers.get("content-length"),
            headers.get("accept-ranges"),
        )

    @staticmethod
    def _embedded_list(
        payload: Mapping[str, object], key: str, *, parent: str | None = None
    ) -> list[Mapping[str, object]]:
        current: object = payload.get("_embedded")
        if not isinstance(current, Mapping):
            raise SkillsCommonsProviderError("HAL response missing _embedded")
        if parent:
            current = current.get(parent)
            if not isinstance(current, Mapping):
                raise SkillsCommonsProviderError(f"HAL response missing {parent}")
            current = current.get("_embedded")
            if not isinstance(current, Mapping):
                raise SkillsCommonsProviderError(f"HAL response missing {parent}._embedded")
        values = current.get(key)
        if values is None:
            return []
        if not isinstance(values, list) or any(not isinstance(value, Mapping) for value in values):
            raise SkillsCommonsProviderError(f"HAL response has malformed {key}")
        return list(values)

    @classmethod
    def _parse_item(cls, payload: Mapping[str, object]) -> SkillsCommonsDspaceItem:
        uuid = cls._string(payload.get("uuid"))
        if not uuid:
            raise SkillsCommonsProviderError("DSpace item missing UUID")
        raw_metadata = payload.get("metadata", {})
        if not isinstance(raw_metadata, Mapping):
            raise SkillsCommonsProviderError("DSpace item metadata is malformed")
        metadata = {str(key): cls._metadata_values(value) for key, value in raw_metadata.items()}
        return SkillsCommonsDspaceItem(
            uuid,
            cls._string(payload.get("handle")),
            cls._string(payload.get("name")),
            metadata,
            cls._string(payload.get("lastModified")),
            cls._bool(payload.get("inArchive")),
            cls._bool(payload.get("withdrawn")),
            cls._bool(payload.get("discoverable")),
            cls._string(payload.get("entityType")),
            cls._links(payload),
        )

    @classmethod
    def _parse_bundle(cls, payload: Mapping[str, object]) -> SkillsCommonsDspaceBundle:
        uuid = cls._string(payload.get("uuid"))
        if not uuid:
            raise SkillsCommonsProviderError("DSpace bundle missing UUID")
        raw_metadata = payload.get("metadata", {})
        metadata = (
            {str(key): cls._metadata_values(value) for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, Mapping)
            else {}
        )
        return SkillsCommonsDspaceBundle(
            uuid, cls._string(payload.get("name")), metadata, cls._links(payload)
        )

    @classmethod
    def _parse_bitstream(
        cls, payload: Mapping[str, object], bundle_name: str | None
    ) -> SkillsCommonsDspaceBitstream:
        uuid = cls._string(payload.get("uuid"))
        if not uuid:
            raise SkillsCommonsProviderError("DSpace bitstream missing UUID")
        raw_metadata = payload.get("metadata", {})
        metadata = (
            {str(key): cls._metadata_values(value) for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, Mapping)
            else {}
        )
        links = cls._links(payload)
        name = cls._string(payload.get("name"))
        mime = cls._string(payload.get("mimeType"))
        size = payload.get("sizeBytes")
        return SkillsCommonsDspaceBitstream(
            uuid,
            name,
            int(size) if isinstance(size, int) else None,
            mime,
            cls._string(payload.get("checksum")),
            cls._string(payload.get("description")),
            metadata,
            links.get("content"),
            bundle_name,
            classify_bitstream(name, mime, metadata),
        )

    @staticmethod
    def _links(payload: Mapping[str, object]) -> dict[str, str]:
        raw = payload.get("_links", {})
        if not isinstance(raw, Mapping):
            return {}
        return {
            str(key): value["href"]
            for key, value in raw.items()
            if isinstance(value, Mapping) and isinstance(value.get("href"), str)
        }

    @staticmethod
    def _link(payload: Mapping[str, object], key: str) -> str | None:
        links = payload.get("_links", {})
        value = links.get(key) if isinstance(links, Mapping) else None
        return (
            value.get("href")
            if isinstance(value, Mapping) and isinstance(value.get("href"), str)
            else None
        )

    @staticmethod
    def _metadata_values(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        values: list[str] = []
        for entry in value:
            if isinstance(entry, Mapping):
                entry_value = entry.get("value")
                if isinstance(entry_value, str) and entry_value:
                    values.append(entry_value)
            elif isinstance(entry, str) and entry:
                values.append(entry)
        return tuple(values)

    @staticmethod
    def _string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _first(item: SkillsCommonsDspaceItem, key: str) -> str | None:
        values = item.values(key)
        return values[0] if values else None

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        parts = value.split("-")
        return (
            len(parts) == 5
            and all(parts)
            and all(all(char in "0123456789abcdefABCDEF" for char in part) for part in parts)
        )

    def _trusted_api_url(self, url: str) -> str:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "library.skillscommons.org"
            or not parsed.path.startswith("/server/api/")
        ):
            raise SkillsCommonsProviderError("unsafe DSpace API URL")
        return url

    def _validate_public_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SkillsCommonsProviderError("unsafe URL")
        host = parsed.hostname.lower()
        if host in _PUBLIC_HOSTS:
            return
        try:
            if not ipaddress.ip_address(host).is_global:
                raise SkillsCommonsProviderError("unsafe URL")
        except ValueError:
            pass
        try:
            addresses = self._resolver(host)
        except OSError as exc:
            raise SkillsCommonsProviderError("unsafe URL") from exc
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise SkillsCommonsProviderError("unsafe URL")

    @staticmethod
    def _resolve_host(host: str) -> Sequence[str]:
        return tuple(
            str(item[4][0]) for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        )


def to_normalized_candidate(course: ExternalCourse) -> NormalizedCourseCandidate:
    """Convert provider facts without adding capabilities or inferred semantics."""
    return NormalizedCourseCandidate(
        course_ref=f"{course.provider_ref}:{course.provider_course_id}",
        source_type=CourseSourceType.EXTERNAL,
        source_system=course.provider_ref,
        provider_ref=course.provider_ref,
        provider_course_id=course.provider_course_id,
        title=course.title,
        description=course.description,
        capabilities=[],
        prerequisites=[],
        target_level=None,
        duration_minutes=course.duration_minutes,
        delivery_mode=course.delivery_mode,
        language=course.language,
        availability=course.availability,
        provenance=list(course.provenance),
    )

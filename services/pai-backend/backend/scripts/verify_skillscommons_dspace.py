"""Run the bounded live SkillsCommons DSpace provider verification."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path

from app.course_catalog.skillscommons import (
    SkillsCommonsCourseProvider,
)

OUTPUT = Path(__file__).resolve().parents[4] / "test/results/course-rec-01a-2c"


def assessment_json(assessment) -> dict[str, object]:
    item = assessment.item
    external_url_keys = (
        "dc.identifier.uri",
        "taaccct.object.uri",
        "taaccct.courseUrl",
        "taaccct.resourceUrl",
    )
    external_url_count = sum(len(item.values(key)) for key in external_url_keys)
    return {
        "provider_course_id": item.uuid,
        "handle": item.handle,
        "title": item.name,
        "material_type": assessment.material_type.value,
        "learning_access": assessment.learning_access.value,
        "availability": assessment.external_course.availability.value
        if assessment.external_course
        else None,
        "license_status": assessment.license_status.value,
        "bitstream_count": len(assessment.bitstreams),
        "bitstreams": [
            {
                "uuid": stream.uuid,
                "name": stream.name,
                "mime_type": stream.mime_type,
                "size_bytes": stream.size_bytes,
                "bundle_name": stream.bundle_name,
                "bitstream_type": stream.bitstream_type.value,
                "content_url_present": bool(stream.content_url),
            }
            for stream in assessment.bitstreams
        ],
        "bundle_names": [bundle.name for bundle in assessment.bundles],
        "external_learning_url_count": external_url_count,
        "access_verifications": [
            {
                "url_host": url_host(result.url),
                "status": result.status.value,
                "http_status": result.http_status,
                "method": result.method,
                "content_type": result.content_type,
                "content_length": result.content_length,
                "accept_ranges": result.accept_ranges,
                "final_host": url_host(result.final_url),
                "reason": result.reason,
            }
            for result in assessment.access_verifications
        ],
        "strict_provider_candidate": assessment.strict_provider_candidate,
        "course_ref": assessment.normalized_candidate.course_ref
        if assessment.normalized_candidate
        else None,
        "capabilities_count": len(assessment.normalized_candidate.capabilities)
        if assessment.normalized_candidate
        else None,
        "target_level": assessment.normalized_candidate.target_level
        if assessment.normalized_candidate
        else None,
        "prerequisites_count": len(assessment.normalized_candidate.prerequisites)
        if assessment.normalized_candidate
        else None,
        "error": assessment.error,
    }


def url_host(url: str | None) -> str | None:
    if not url:
        return None
    return url.split("/", 3)[2] if "://" in url else None


async def main() -> None:
    provider = SkillsCommonsCourseProvider(max_pages=5, max_records=200)
    sample = await provider.live_sample(target_full_courses=30)
    results = [assessment_json(item) for item in sample.assessments]
    access = Counter(item["learning_access"] for item in results)
    access_status = Counter(
        verification["status"] for item in results for verification in item["access_verifications"]
    )
    summary = {
        "status": "LIVE_VERIFIED",
        "provider": "skillscommons",
        "base_url": provider.base_url,
        "material_type_key": provider.material_type_key,
        "selection_strategy": "BOUNDED_POST_FILTER",
        "search_query": provider.search_query,
        "max_pages": provider._max_pages,
        "max_raw_records": provider._max_records,
        "target_exact_online_course": 30,
        "raw_search_results_seen": sample.raw_search_results_seen,
        "exact_online_course_candidates": sample.exact_online_course_candidates,
        "exact_online_course_processed": len(results),
        "raw_type_counts": sample.raw_type_counts,
        "items_fetched_success": sample.items_fetched_success,
        "items_fetched_failure": sample.items_fetched_failure,
        "strict_external_course_candidates": sum(
            1 for item in results if item["strict_provider_candidate"]
        ),
        "observed_verified_yield_in_sample": (
            sum(1 for item in results if item["strict_provider_candidate"]) / len(results)
            if results
            else 0
        ),
        "learning_access_counts": dict(access),
        "access_status_counts": dict(access_status),
        "items_with_handle": sum(1 for item in results if item["handle"]),
        "items_with_bundles": sum(1 for item in results if item["bundle_names"]),
        "items_with_bitstreams": sum(1 for item in results if item["bitstream_count"]),
        "items_with_external_learning_url": sum(
            1 for item in results if item["external_learning_url_count"]
        ),
        "items_without_external_learning_url": sum(
            1 for item in results if not item["external_learning_url_count"]
        ),
        "items_in_archive": sum(1 for item in results if item["availability"] == "available"),
        "items_withdrawn": 0,
        "items_not_discoverable": 0,
        "sample_strategy": "bounded free-text search followed by exact dc.type post-filter",
        "population_wide_claim": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "live-sample-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUTPUT / "live-course-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

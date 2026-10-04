"""Prepare a sanitized, deterministic live SkillsCommons enrichment sample."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.course_catalog.skillscommons import SkillsCommonsCourseProvider

ROOT = Path(__file__).resolve().parents[4]
RESULTS = ROOT / "test/results/course-rec-01a-2c/live-course-results.json"
OUTPUT = ROOT / "test/results/course-rec-01a-3/sample-manifest.json"

SELECTED = [
    ("4f3652e5-82d3-4a78-9b02-73126bb86bc9", "business/accounting"),
    ("4828d609-2f88-4324-bf80-55aa7b1c68fa", "general/ambiguous"),
    ("aee2a65b-d134-4a3e-93a2-118a4fef89d8", "technical/ambiguous"),
    ("1398f9e1-49ee-4885-8eba-7d2d36d680e9", "healthcare"),
    ("f38740c4-657e-4c62-abe1-d9ce94eb30b0", "healthcare/nutrition"),
    ("f64795cb-b561-4bb6-9748-9841d6e982dd", "healthcare/physical-therapy"),
    ("9cbe25b2-7502-405f-bbc3-92016ddcfed8", "technical/hardware"),
    ("5aa287ec-ce0a-4773-a937-33a777056e07", "technical/programming"),
    ("5fa371f7-e619-44d4-86e9-083feb5d45e9", "healthcare/patient-care"),
    ("6f6156c3-7b85-4ce0-85cc-1efbd439d144", "business/project-management"),
    ("df391f77-5a76-4c10-9e45-0a2783706b30", "healthcare/pharmacy"),
    ("f252280a-b389-4dd7-bac4-669224a0dc96", "healthcare/pain-management"),
    ("63e10921-279e-4404-912e-432c80fd82a1", "workforce/professional-performance"),
    ("c2d999f7-2867-43e1-b229-e205696e0c48", "technical/operating-systems"),
    ("5776ecdb-fbd0-49a3-b11a-f96a4ed90a55", "healthcare/medical-coding"),
]


async def main() -> None:
    live_results = {item["provider_course_id"]: item for item in json.loads(RESULTS.read_text())}
    provider = SkillsCommonsCourseProvider()
    sample: list[dict[str, object]] = []
    for provider_id, category in SELECTED:
        item = await provider.fetch_item(provider_id)
        live = live_results[provider_id]
        sample.append(
            {
                "provider_ref": "skillscommons",
                "provider_course_id": item.uuid,
                "course_ref": f"skillscommons:{item.uuid}",
                "handle": item.handle,
                "title": item.values("dc.title")[0] if item.values("dc.title") else item.name,
                "category": category,
                "strict_provider_candidate": live["strict_provider_candidate"],
                "source_metadata": {
                    key: list(item.values(key))
                    for key in (
                        "dc.title",
                        "dc.description.abstract",
                        "dc.subject",
                        "dc.contributor.author",
                        "dc.publisher",
                        "dc.type",
                        "dc.language",
                        "dcterms.license",
                        "taaccct.occupation",
                        "taaccct.industry",
                        "taaccct.credentialType",
                        "taaccct.deliveryFormat",
                        "taaccct.projectName",
                        "taaccct.level",
                    )
                    if item.values(key)
                },
                "last_modified": item.last_modified,
                "dspace_state": {
                    "inArchive": item.in_archive,
                    "withdrawn": item.withdrawn,
                    "discoverable": item.discoverable,
                },
                "bundle_names": live["bundle_names"],
                "bitstreams": [
                    {"name": stream["name"], "bitstream_type": stream["bitstream_type"]}
                    for stream in live["bitstreams"]
                ],
            }
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "sample_size": len(sample),
                "sampling_method": "deterministic stratified selection from the 27 strict 01A.2C package candidates; no new network crawl",
                "live_provider_data": True,
                "courses": sample,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"sample_size": len(sample), "output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

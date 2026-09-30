"""Source-of-truth projection for capability analysis evidence."""

from dataclasses import dataclass

from app.extraction.profile import CandidateProfile
from app.extraction.profile_builder import build_candidate_profile_from_output
from app.extraction.schemas import CVExtractionOutput, ExtractionProfile


@dataclass(frozen=True)
class EvidenceIndex:
    """Semantic evidence view built without mutating the accepted profile."""

    source: str
    candidate_profile: CandidateProfile


def build_evidence_index(profile: ExtractionProfile) -> EvidenceIndex:
    """Prefer accepted raw CV claims over a stale compatibility projection.

    Graph-only CV profiles have an empty legacy output and retain their persisted
    CandidateProfile because that graph is their source of truth.
    """
    if isinstance(profile.output, CVExtractionOutput) and any(
        (profile.output.skills, profile.output.experience, profile.output.education)
    ):
        return EvidenceIndex(
            source="accepted_cv_extraction_output",
            candidate_profile=build_candidate_profile_from_output(profile.output),
        )
    if profile.candidate_profile is None:
        raise ValueError("Capability analysis requires a CandidateProfile")
    return EvidenceIndex(source="candidate_profile_graph", candidate_profile=profile.candidate_profile)

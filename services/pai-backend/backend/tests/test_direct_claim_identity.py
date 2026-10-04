import pytest

from app.capability_governance.direct_claim_identity import make_direct_claim_source_id


def test_direct_claim_source_id_uses_canonical_structured_hash() -> None:
    assert (
        make_direct_claim_source_id(course_ref="course-A#segment", claim_id="claim-B")
        == "dc1_cdbd9870f3cf9fd14b405f8edcd4148eefae80b08a3f429ce1e64791fa4e0457"
    )


def test_direct_claim_source_id_is_fixed_length_and_deterministic() -> None:
    first = make_direct_claim_source_id(course_ref="skillscommons:course-1", claim_id="claim-1")
    second = make_direct_claim_source_id(course_ref="skillscommons:course-1", claim_id="claim-1")

    assert first == second
    assert first.startswith("dc1_")
    assert len(first) == 68


def test_structurally_distinct_inputs_have_distinct_ids() -> None:
    pairs = {
        ("a#b", "c"),
        ("a", "b#c"),
        ("a:b", "c"),
        ("a", "b:c"),
    }
    ids = {
        make_direct_claim_source_id(course_ref=course, claim_id=claim) for course, claim in pairs
    }

    assert len(ids) == len(pairs)


def test_exact_reported_collision_pair_has_distinct_ids() -> None:
    pair_a = make_direct_claim_source_id(
        course_ref="skillscommons:course-A#segment", claim_id="claim-B"
    )
    pair_b = make_direct_claim_source_id(
        course_ref="skillscommons:course-A", claim_id="segment#claim-B"
    )

    assert pair_a != pair_b
    assert len(pair_a) <= 512
    assert len(pair_b) <= 512


def test_direct_claim_source_id_preserves_unicode_and_exact_values() -> None:
    composed = make_direct_claim_source_id(course_ref="café", claim_id="claim")
    decomposed = make_direct_claim_source_id(course_ref="cafe\u0301", claim_id="claim")
    spaced = make_direct_claim_source_id(course_ref=" course ", claim_id=" claim ")
    unspaced = make_direct_claim_source_id(course_ref="course", claim_id="claim")

    assert composed != decomposed
    assert spaced != unspaced


@pytest.mark.parametrize("character", ("#", ":", "/", "%", "?", "&", "="))
def test_direct_claim_source_id_supports_special_identifier_characters(character: str) -> None:
    source_id = make_direct_claim_source_id(
        course_ref=f"provider:course{character}part", claim_id=f"claim{character}part"
    )

    assert source_id.startswith("dc1_")
    assert len(source_id) == 68


@pytest.mark.parametrize(
    ("course_ref", "claim_id", "error"),
    (
        ("", "claim", "course_ref_required"),
        ("  ", "claim", "course_ref_required"),
        ("course", "", "claim_id_required"),
        ("course", " \t", "claim_id_required"),
    ),
)
def test_direct_claim_source_id_rejects_blank_identity_parts(
    course_ref: str, claim_id: str, error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        make_direct_claim_source_id(course_ref=course_ref, claim_id=claim_id)


def test_large_identity_parts_still_produce_bounded_source_id() -> None:
    source_id = make_direct_claim_source_id(course_ref="c" * 512, claim_id="x" * 100_000)

    assert len(source_id) == 68

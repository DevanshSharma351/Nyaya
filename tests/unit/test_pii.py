"""PII shield behaviour.

The properties tested here are the ones the privacy claim depends on: that
real identifiers are caught, that lookalikes are not, and that surrogates are
stable enough to preserve coreference without leaking the value.
"""

from __future__ import annotations

from nyaya.ingestion.pii import mask, pan_valid, unmask, verhoeff_valid

# Structurally valid Aadhaar-format numbers (correct Verhoeff check digit),
# generated for testing. They identify no real person.
VALID_AADHAAR = "234123412346"
VALID_PAN = "ABCPD1234E"


def test_verhoeff_accepts_valid_and_rejects_corrupted():
    assert verhoeff_valid(VALID_AADHAAR)
    # flipping any digit must invalidate the checksum
    corrupted = VALID_AADHAAR[:-1] + str((int(VALID_AADHAAR[-1]) + 1) % 10)
    assert not verhoeff_valid(corrupted)


def test_pan_structure_validation():
    assert pan_valid(VALID_PAN)
    assert not pan_valid("ABCXD1234E")  # invalid holder-type char at position 4
    assert not pan_valid("ABC1D1234E")  # digit in the alpha prefix
    assert not pan_valid("ABCPD1234")  # too short


def test_checksum_prevents_masking_ordinary_numbers():
    """A 12-digit transaction reference must not be mistaken for an Aadhaar.

    This is why the recogniser validates rather than pattern-matching alone:
    over-masking destroys the requirement text the system is meant to analyse.
    """
    text = "Transaction reference 111111111111 was settled."
    assert mask(text).text == text


def test_aadhaar_is_masked_in_both_written_forms():
    spaced = f"{VALID_AADHAAR[:4]} {VALID_AADHAAR[4:8]} {VALID_AADHAAR[8:]}"
    for form in (VALID_AADHAAR, spaced):
        result = mask(f"Customer Aadhaar is {form} on file.")
        assert form not in result.text
        assert "IN_AADHAAR" in result.text
        assert result.entity_counts.get("IN_AADHAAR") == 1


def test_surrogates_are_stable_within_a_project():
    """The same identifier must map to the same token, preserving coreference."""
    a = mask(f"KYC for {VALID_PAN} pending.", salt="proj-1")
    b = mask(f"Escalate the case for {VALID_PAN}.", salt="proj-1")
    assert a.detections[0].token == b.detections[0].token


def test_surrogates_differ_across_projects():
    """A per-project salt prevents correlating an individual across engagements."""
    a = mask(f"PAN {VALID_PAN}", salt="proj-1")
    b = mask(f"PAN {VALID_PAN}", salt="proj-2")
    assert a.detections[0].token != b.detections[0].token


def test_masking_is_reversible():
    original = f"Contact ravi@example.com regarding PAN {VALID_PAN}."
    result = mask(original, salt="p")
    assert "ravi@example.com" not in result.text
    assert unmask(result.text, result.mapping) == original


def test_multiple_entity_types_in_one_statement():
    text = (
        f"Applicant PAN {VALID_PAN}, Aadhaar {VALID_AADHAAR}, "
        "email a.kumar@bank.example, phone 9876543210."
    )
    result = mask(text, salt="p")
    assert set(result.entity_counts) == {
        "IN_PAN",
        "IN_AADHAAR",
        "EMAIL_ADDRESS",
        "IN_PHONE",
    }
    for detection in result.detections:
        assert detection.value not in result.text


def test_requirement_text_survives_masking():
    """Masking must not damage the surrounding requirement wording."""
    text = f"The system shall verify PAN {VALID_PAN} before account activation."
    result = mask(text, salt="p")
    assert result.text.startswith("The system shall verify PAN ")
    assert result.text.endswith(" before account activation.")

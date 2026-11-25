import io
import json
import zipfile

from update_verification_status_mapping import (
    MAPPING_PATH,
    is_verified,
    propose,
    read_counts,
)


def test_rules_are_anchored_and_honour_exceptions():
    """The rules must not catch negations ("not validated" contains
    "validated"), and the explicit exceptions win over the broad "^accepted"
    pattern: Waarnemingen.be's "accepted (plausible)" was decided unverified
    in #522, yet the pattern alone would propose it as verified."""
    assert is_verified("Accepted - correct")
    assert is_verified("accepted (with evidence)")
    assert is_verified("Verificado por especialista")
    assert not is_verified("not validated")
    assert not is_verified("Unvalidated")
    assert not is_verified("accepted (plausible)")
    assert not is_verified("")


def test_rules_agree_with_the_shipped_mapping():
    """The shipped JSON was produced by these rules (#43) plus the #522
    decisions. If they drift apart, new values would be judged by different
    rules than the existing ones without anyone noticing. A deliberate
    reviewer override that contradicts the rules should update the rules
    (or their exceptions) at the same time."""
    entries = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    disagreeing = [e["key"] for e in entries if is_verified(e["key"]) != e["verified"]]
    assert disagreeing == []


def test_propose_adds_only_new_values_and_drops_the_unverified_long_tail():
    """Existing entries are never re-judged (a reviewer may have overridden
    them). New verified values are always added, however rare, because a
    missing one hides records from verified-only alerts; new unverified
    values below min_count are left out, since absent already means
    unverified and the long tail is mostly per-record junk. Verified ones
    come first so reviewers see the risky part at the top."""
    existing = [{"key": "validated", "verified": True}]
    counts = {
        "validated": 1000,  # already known
        "confirmed by expert": 1,  # rare but verified
        "unverified": 50,  # common, unverified
        "Challenge ID 123": 1,  # rare junk
    }
    added, skipped = propose(existing, counts, min_count=10)
    assert added == [
        {"key": "confirmed by expert", "verified": True},
        {"key": "unverified", "verified": False},
    ]
    assert skipped == 1


def test_read_counts_parses_the_gbif_sql_tsv():
    """GBIF's SQL_TSV_ZIP has one TSV with a header row. Quotes are part of
    raw publisher strings and must not be interpreted as CSV quoting, or a
    value like '"Approved"' would silently change."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "0000001-000000000000000.csv",
            "identificationverificationstatus\tCOUNT(*)\n"
            "validated\t12\n"
            '"Approved"\t3\n'
            "\t7\n",
        )
    assert read_counts(buffer.getvalue()) == {
        "validated": 12,
        '"Approved"': 3,
        "": 7,
    }

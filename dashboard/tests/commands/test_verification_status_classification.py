from dashboard.management.commands.import_observations import (
    load_verification_status_hash,
)


def test_waarnemingen_be_current_vocabulary_is_classified():
    """Waarnemingen.be (one of the largest and most alert-relevant datasets)
    switched to a new identificationVerificationStatus vocabulary in 2026
    (issue #522). Unmapped values silently count as unverified, so before
    this was fixed nearly all its observations were missing from
    verified-only alerts. Each of its current values must be an explicit
    entry, with "plausible" and "unknown" deliberately unverified.
    """
    hash_table = load_verification_status_hash()

    assert hash_table["accepted (automatic validation)"] is True
    assert hash_table["accepted (with evidence)"] is True
    assert hash_table["accepted (plausible)"] is False
    assert hash_table["unknown"] is False

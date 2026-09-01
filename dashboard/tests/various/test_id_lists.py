import pytest

from dashboard.id_lists import MAX_EXPANDED_IDS, parse_id_list


def test_repeated_params_still_work():
    """The historical spelling (one param per id) is unchanged."""
    assert parse_id_list(["1", "2", "3"]) == [1, 2, 3]


def test_empty_input():
    assert parse_id_list([]) == []


def test_comma_separated_single_value():
    assert parse_id_list(["1,2,3"]) == [1, 2, 3]


def test_inclusive_range():
    assert parse_id_list(["10-13"]) == [10, 11, 12, 13]


def test_range_of_one():
    assert parse_id_list(["7-7"]) == [7]


def test_mixed_ranges_and_singles():
    assert parse_id_list(["1-3,10,20-22"]) == [1, 2, 3, 10, 20, 21, 22]


def test_mixed_spellings_across_params():
    """A client may combine both forms in the same request."""
    assert parse_id_list(["1-3", "10", "20,21"]) == [1, 2, 3, 10, 20, 21]


def test_surrounding_whitespace_is_tolerated():
    assert parse_id_list([" 1 , 3 - 5 "]) == [1, 3, 4, 5]


def test_empty_tokens_are_skipped():
    """`?speciesIds=` and stray commas mean "nothing", not an error."""
    assert parse_id_list([""]) == []
    assert parse_id_list(["1,,2"]) == [1, 2]


def test_order_and_duplicates_are_preserved():
    """The parser does not reorder: callers only ever use these with `__in`."""
    assert parse_id_list(["3", "1", "3"]) == [3, 1, 3]


@pytest.mark.parametrize("value", ["abc", "1-", "-5", "1-2-3", "1.5", "1-abc"])
def test_malformed_tokens_are_rejected(value):
    with pytest.raises(ValueError):
        parse_id_list([value])


def test_reversed_range_is_rejected():
    with pytest.raises(ValueError):
        parse_id_list(["10-3"])


def test_oversized_range_is_rejected_without_being_expanded():
    """A range is measured before expansion, so it cannot exhaust memory."""
    with pytest.raises(ValueError):
        parse_id_list([f"1-{MAX_EXPANDED_IDS + 2}"])


def test_cap_applies_to_the_total_across_tokens():
    with pytest.raises(ValueError):
        parse_id_list([f"1-{MAX_EXPANDED_IDS}", f"{MAX_EXPANDED_IDS + 1}"])


def test_cap_boundary_is_accepted():
    assert len(parse_id_list([f"1-{MAX_EXPANDED_IDS}"])) == MAX_EXPANDED_IDS

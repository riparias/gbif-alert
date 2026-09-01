"""Parsing of the id lists carried by the observation filter query params.

Every filter that selects a list of ids (species, datasets, areas, basis of
record, data imports) accepts two interchangeable spellings:

    ?speciesIds=1&speciesIds=2&speciesIds=3     one param per id
    ?speciesIds=1-3                             compact

The compact form exists because an alert can select several hundred species,
and one param per id overflows the web server's request-line limit (gunicorn
defaults to 4094 bytes, which a ~400-species alert exceeds). A token is either
a single id or an inclusive `low-high` range, tokens are comma-separated, and
the two spellings may be mixed freely within one request - so the compact form
is purely additive and old clients keep working.

Order and duplicates are preserved: these lists only ever reach the database
through an `IN` clause, so normalizing them here would buy nothing and would
make the parser's output harder to reason about in tests.
"""

from collections.abc import Iterable

# Upper bound on how many ids one filter may expand to. Without it, a
# hand-written `?speciesIds=1-999999999` would have the server build a
# billion-element list on an endpoint that needs no authentication.
MAX_EXPANDED_IDS = 10_000


def parse_id_list(values: Iterable[str]) -> list[int]:
    """Expand the received values of one id filter into a list of ids.

    `values` is the raw list of occurrences of a single query parameter, as
    returned by `QueryDict.getlist()` (each may itself be a comma-separated
    list of tokens).

    Raises ValueError on a malformed token, on a reversed or negative range,
    and when the expansion would exceed MAX_EXPANDED_IDS.
    """
    ids: list[int] = []
    for value in values:
        for token in str(value).split(","):
            token = token.strip()
            if not token:  # `?speciesIds=` and stray commas mean "nothing"
                continue
            ids.extend(_expand_token(token))
            if len(ids) > MAX_EXPANDED_IDS:
                raise ValueError(f"Too many ids requested (limit: {MAX_EXPANDED_IDS})")
    return ids


def _expand_token(token: str) -> Iterable[int]:
    low, separator, high = token.partition("-")
    if not separator:
        return (int(token),)

    # int() rejects the malformed cases for us: an empty bound ("1-", "-5"),
    # a non-numeric one, and a second separator ("1-2-3" -> high == "2-3").
    start = int(low)
    end = int(high)
    if start < 0:
        raise ValueError(f"Negative id in range: {token}")
    if end < start:
        raise ValueError(f"Reversed range: {token}")
    # Measured before expanding, so an absurd range never gets materialized.
    if end - start + 1 > MAX_EXPANDED_IDS:
        raise ValueError(f"Range too wide (limit: {MAX_EXPANDED_IDS}): {token}")
    return range(start, end + 1)

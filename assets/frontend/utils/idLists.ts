/**
 * Compact encoding for the id lists carried by the filter params.
 *
 * An alert can select several hundred species, and one query param per id
 * (`speciesIds=1&speciesIds=2&...`) overflows the web server's request-line
 * limit - gunicorn defaults to 4094 bytes, which a ~400-species alert exceeds,
 * and every observation/tile request carries the full filter set.
 *
 * So a list is sent as a single value: comma-separated tokens, where a run of
 * three or more consecutive ids collapses into `low-high`. The backend
 * (dashboard/id_lists.py) accepts this and the historical one-param-per-id
 * spelling interchangeably, so old links keep working.
 */

// Mirrors MAX_EXPANDED_IDS in dashboard/id_lists.py: a hand-written
// `?speciesIds=1-999999999` must not freeze the tab before the request is
// even sent.
const MAX_EXPANDED_IDS = 10000;

// A run of two costs the same either way ("10-11" and "10,11" are both five
// characters), so only three or more is worth a range.
const MIN_RUN_FOR_RANGE = 3;

/**
 * Encode ids as the compact form. The result is sorted and deduplicated, which
 * is what makes runs collapsible and what keeps the address bar canonical: the
 * same selection always produces the same URL. Filter id order is not
 * meaningful anywhere in the app.
 *
 * Returns "" for an empty list, so callers can skip the param entirely.
 */
export function encodeIdList(ids: number[]): string {
    const sorted = [...new Set(ids)].sort((a, b) => a - b);
    const parts: string[] = [];

    let start = 0;
    while (start < sorted.length) {
        let end = start;
        while (end + 1 < sorted.length && sorted[end + 1] === sorted[end] + 1) end++;
        if (end - start + 1 >= MIN_RUN_FOR_RANGE) {
            parts.push(`${sorted[start]}-${sorted[end]}`);
        } else {
            for (let i = start; i <= end; i++) parts.push(String(sorted[i]));
        }
        start = end + 1;
    }

    return parts.join(",");
}

/**
 * Decode either spelling back into ids. Lenient by design - it parses URLs
 * typed or bookmarked by people, so an unparseable token (such as the
 * `areaIds=none` sentinel) is skipped rather than throwing.
 */
export function decodeIdList(raw: string): number[] {
    const ids: number[] = [];

    for (const rawToken of raw.split(",")) {
        const token = rawToken.trim();
        if (!token) continue;

        // indexOf > 0, not >= 0: a leading "-" is a negative number, not a range.
        const separator = token.indexOf("-");
        if (separator > 0) {
            const start = Number(token.slice(0, separator));
            const end = Number(token.slice(separator + 1));
            if (!Number.isInteger(start) || !Number.isInteger(end)) continue;
            if (end < start || end - start + 1 > MAX_EXPANDED_IDS) continue;
            for (let i = start; i <= end; i++) ids.push(i);
        } else {
            const id = Number(token);
            if (Number.isInteger(id)) ids.push(id);
        }
        if (ids.length > MAX_EXPANDED_IDS) return ids.slice(0, MAX_EXPANDED_IDS);
    }

    return ids;
}

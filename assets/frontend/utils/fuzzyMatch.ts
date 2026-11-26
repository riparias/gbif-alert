// Search helper shared by the filter modals (species, datasets, areas).
//
// Matching is accent- and case-insensitive. A plain substring match always
// wins; typo tolerance is only a fallback for when the substring search finds
// nothing, so the list is not flooded with near-misses while typing.

/** Lowercase and strip diacritics (e-acute -> e). */
function normalize(s: string): string {
    return s
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

/** Typos tolerated for a query word: none when short, 1 from 4 letters, 2 from 8. */
function allowedEdits(word: string): number {
    return word.length >= 8 ? 2 : word.length >= 4 ? 1 : 0;
}

/**
 * Smallest edit distance between `query` and any prefix of `word`. Comparing
 * to prefixes keeps a name matching while it is still being typed. A swap of
 * two adjacent letters counts as one edit (optimal string alignment).
 */
function prefixDistance(query: string, word: string): number {
    let prev2: number[] = [];
    let prev = Array.from({ length: word.length + 1 }, (_, j) => j);
    for (let i = 1; i <= query.length; i++) {
        const cur = [i];
        for (let j = 1; j <= word.length; j++) {
            const cost = query[i - 1] === word[j - 1] ? 0 : 1;
            cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
            if (i > 1 && j > 1 && query[i - 1] === word[j - 2] && query[i - 2] === word[j - 1]) {
                cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
            }
        }
        prev2 = prev;
        prev = cur;
    }
    return Math.min(...prev);
}

/** True when every query word is a near-prefix of some word of `text`. */
function fuzzyMatch(queryWords: string[], text: string): boolean {
    const words = text.split(/\s+/);
    return queryWords.every((qw) => words.some((w) => prefixDistance(qw, w) <= allowedEdits(qw)));
}

/**
 * Filter `items` on `query`, looking in the strings returned by `getTexts`.
 * Returns the substring matches, or the typo-tolerant ones if there are none.
 */
export function searchFilter<T>(
    items: T[],
    query: string,
    getTexts: (item: T) => (string | null | undefined)[],
): T[] {
    const q = normalize(query.trim());
    if (!q) return items;
    const texts = (item: T) => getTexts(item).map((s) => normalize(s ?? ""));

    const exact = items.filter((item) => texts(item).some((s) => s.includes(q)));
    if (exact.length) return exact;

    const queryWords = q.split(/\s+/);
    return items.filter((item) => texts(item).some((s) => fuzzyMatch(queryWords, s)));
}

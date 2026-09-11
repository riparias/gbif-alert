import { ref, type Ref } from "vue";

export interface LatestRequest<T> {
    /** True while the most recent request is in flight. */
    loading: Ref<boolean>;
    /** True when the most recent request failed (non-2xx or network error). */
    error: Ref<boolean>;
    /**
     * Fetch `url` and resolve with its parsed JSON body, or with `undefined`
     * when the request failed or was superseded by a newer `load()` call.
     */
    load: (url: string, init?: RequestInit) => Promise<T | undefined>;
}

/**
 * Latest-request-wins fetching for views that reload on every filter change.
 *
 * Each `load()` aborts the previous in-flight request, and a response that
 * was superseded never reaches the caller, so a slow earlier request cannot
 * paint over the result of a later one. Only the latest request touches
 * `loading` and `error`: a superseded request's completion (or abort) leaves
 * both alone, so `loading` stays true while the newer request is still
 * running.
 *
 * A non-2xx response is an error, not silently ignored: callers show it, so a
 * 400 or a 429 does not leave stale data on screen with no feedback.
 */
export function useLatestRequest<T>(): LatestRequest<T> {
    const loading = ref(false);
    const error = ref(false);
    let controller: AbortController | null = null;
    let latest = 0;

    async function load(url: string, init: RequestInit = {}): Promise<T | undefined> {
        controller?.abort();
        controller = new AbortController();
        const mine = ++latest;
        loading.value = true;
        error.value = false;
        try {
            const response = await fetch(url, { ...init, signal: controller.signal });
            if (mine !== latest) return undefined;
            if (!response.ok) {
                error.value = true;
                return undefined;
            }
            const data = (await response.json()) as T;
            return mine === latest ? data : undefined;
        } catch {
            // An abort rejects the fetch; that is the superseded case and is
            // not an error. Anything else (network failure, bad JSON) on the
            // latest request is.
            if (mine === latest) error.value = true;
            return undefined;
        } finally {
            if (mine === latest) loading.value = false;
        }
    }

    return { loading, error, load };
}

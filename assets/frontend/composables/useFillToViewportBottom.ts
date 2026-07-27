import { onMounted, onUnmounted, ref, type Ref } from "vue";

/**
 * Size an element so the page ends at the bottom of the viewport, without ever
 * making it shorter than `minHeight`.
 *
 * A plain `calc(100dvh - Npx)` cannot do this here: how far down the page the
 * element starts differs per page (the index has a welcome text and a histogram
 * brush above it, the alert detail page has neither) and the welcome text is an
 * operator-editable page fragment, so its height is not knowable at build time.
 * The offset is therefore measured rather than hardcoded.
 *
 * The measured top is the element's position in the document, not in the
 * viewport, so scrolling does not change the result - only a resize, or a change
 * in the content above it, does.
 */

const BOTTOM_GAP_PX = 24;

export function useFillToViewportBottom(
    getEl: () => HTMLElement | null | undefined,
    minHeight: number,
): Ref<string> {
    const height = ref(`${minHeight}px`);

    function recompute(): void {
        const el = getEl();
        if (!el) return;
        // The element's own height never feeds into its own top, so measuring
        // here cannot oscillate: everything deciding the top sits above it.
        const documentTop = el.getBoundingClientRect().top + window.scrollY;
        const footer = document.querySelector("footer");
        const footerHeight = footer ? footer.getBoundingClientRect().height : 0;
        const available = window.innerHeight - documentTop - footerHeight - BOTTOM_GAP_PX;
        const next = `${Math.max(minHeight, Math.round(available))}px`;
        if (next !== height.value) height.value = next;
    }

    /**
     * The siblings stacked above us, whose heights move our top.
     *
     * Deliberately NOT document.body: our own height changes the body's, so
     * observing it feeds the element's size back into its own trigger, and the
     * browser drops the resulting ResizeObserver loop - which is exactly how an
     * earlier version silently kept a stale height once the welcome text
     * arrived. Nothing above us can depend on our height, so this cannot loop.
     */
    function elementsAbove(el: HTMLElement): HTMLElement[] {
        const column = el.closest(".sidebar-layout__main");
        if (!column) return [];
        let branch: HTMLElement = el;
        while (branch.parentElement && branch.parentElement !== column) {
            branch = branch.parentElement;
        }
        const above: HTMLElement[] = [];
        for (let sib = branch.previousElementSibling; sib; sib = sib.previousElementSibling) {
            above.push(sib as HTMLElement);
        }
        return above;
    }

    let resizeAbove: ResizeObserver | null = null;
    let columnChanges: MutationObserver | null = null;

    /** (Re)point the ResizeObserver at whatever currently sits above us. */
    function watchElementsAbove(): void {
        const el = getEl();
        if (!el || !resizeAbove) return;
        resizeAbove.disconnect();
        for (const node of elementsAbove(el)) resizeAbove.observe(node);
        recompute();
    }

    onMounted(() => {
        recompute();
        window.addEventListener("resize", recompute);

        const el = getEl();
        if (!el) return;

        // Existing siblings resizing: the filter chips wrap onto a second row as
        // filters are added, pushing our top down.
        resizeAbove = new ResizeObserver(recompute);

        // Siblings APPEARING: the welcome text is `v-if` on a fetch that resolves
        // after mount, so at this point the element does not exist yet and cannot
        // be observed - watch the column for the insertion itself. childList only,
        // deliberately: our own height lands as a style attribute, and watching
        // attributes here would feed our size back into our own trigger.
        const column = el.closest(".sidebar-layout__main");
        if (column) {
            columnChanges = new MutationObserver(watchElementsAbove);
            columnChanges.observe(column, { childList: true });
        }
        watchElementsAbove();
    });

    onUnmounted(() => {
        window.removeEventListener("resize", recompute);
        resizeAbove?.disconnect();
        columnChanges?.disconnect();
        resizeAbove = null;
        columnChanges = null;
    });

    return height;
}

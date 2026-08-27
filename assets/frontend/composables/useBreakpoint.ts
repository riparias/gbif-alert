import { onScopeDispose, readonly, ref, type Ref } from "vue";

/**
 * Reactive "are we on a small screen?" flag.
 *
 * Most of the responsive work is plain CSS (see the @media rules in
 * styles/layout.css and the components' scoped blocks). This composable exists
 * only for the handful of places where the DOM itself has to differ rather than
 * just its styling: the navbar swaps a menubar for a drawer, the filter/alert
 * sidebar moves into a drawer, and the observations table becomes a card list.
 *
 * The threshold is kept in sync by hand with the CSS: 768px is the boundary,
 * expressed here as `max-width: 767.98px` so it cannot overlap the
 * `min-width: 768px` rules on a fractional (zoomed / scaled) viewport width.
 * If you change it, change styles/layout.css too.
 */
const MOBILE_QUERY = "(max-width: 767.98px)";

export function useBreakpoint(): { isMobile: Readonly<Ref<boolean>> } {
    const mediaQuery = window.matchMedia(MOBILE_QUERY);
    const isMobile = ref(mediaQuery.matches);

    function update(event: MediaQueryListEvent): void {
        isMobile.value = event.matches;
    }

    mediaQuery.addEventListener("change", update);

    // onScopeDispose rather than onUnmounted: this keeps the composable usable
    // from a store or a detached effect scope, not only from a component.
    onScopeDispose(() => mediaQuery.removeEventListener("change", update));

    return { isMobile: readonly(isMobile) };
}

<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import Drawer from "primevue/drawer";
import { useBreakpoint } from "../../composables/useBreakpoint";
import { useResultsStore } from "../../stores/results";

/**
 * The dark side panel shared by the index and alert-detail pages.
 *
 * On a wide screen it is an ordinary sticky <aside> next to the results. On a
 * phone there is no room for a 310px column beside anything, and stacking the
 * panel above the results would bury the observations under a full-height
 * filter form - so it moves into a drawer, opened from a sticky bar that also
 * keeps the result count visible (the count otherwise lives in the panel's
 * stat block, which is now hidden).
 *
 * The panel itself is passed as a slot and is identical in both cases; only its
 * container changes.
 */
defineProps<{
    /** Button label for the drawer trigger, e.g. "Filters" or "Alert details". */
    triggerLabel: string;
}>();

const { t } = useI18n();
const { isMobile } = useBreakpoint();
const resultsStore = useResultsStore();

const drawerOpen = ref(false);

// Growing past the breakpoint while the drawer is open would leave it stranded
// over a layout that already shows the panel inline.
watch(isMobile, (mobile) => {
    if (!mobile) drawerOpen.value = false;
});
</script>

<template>
    <aside v-if="!isMobile" class="sidebar-layout__aside">
        <slot />
    </aside>

    <template v-else>
        <div class="mobile-sidebar-bar">
            <button
                type="button"
                class="mobile-sidebar-trigger"
                :aria-expanded="drawerOpen"
                @click="drawerOpen = true"
            >
                <i class="pi pi-sliders-h" />
                <span>{{ triggerLabel }}</span>
            </button>

            <span class="mobile-sidebar-count">
                <strong>{{
                    resultsStore.loading && resultsStore.observationCount === 0
                        ? "--"
                        : resultsStore.observationCount.toLocaleString()
                }}</strong>
                {{ t("message.statObservationsLabel") }}
            </span>
        </div>

        <!-- Page-specific actions that must stay reachable without opening the
             drawer (on the alert page: the seen/unseen toggle and "mark all as
             viewed", which are the point of the page). Outside the sticky bar
             above: pinning all three rows would keep ~200px of chrome on a
             812px screen. -->
        <div class="mobile-sidebar-actions">
            <slot name="actions" />
        </div>

        <Drawer
            v-model:visible="drawerOpen"
            position="left"
            class="mobile-sidebar-drawer"
            :header="triggerLabel"
        >
            <slot />
        </Drawer>
    </template>
</template>

<style scoped>
.mobile-sidebar-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    /* Sticky so the filter trigger and the count follow a long results list.
     * One row only - see the comment on .mobile-sidebar-actions. */
    position: sticky;
    top: 0;
    z-index: 5;
    padding: 0.5rem 0;
    background: var(--p-content-background, #ffffff);
}

.mobile-sidebar-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}

.mobile-sidebar-actions:empty {
    display: none;
}

.mobile-sidebar-trigger {
    all: unset;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    min-height: 40px;
    padding: 0 0.75rem;
    border: 1px solid var(--p-primary-color);
    border-radius: 6px;
    color: var(--p-primary-color);
    font-weight: 600;
    cursor: pointer;
}

.mobile-sidebar-trigger:hover,
.mobile-sidebar-trigger:focus-visible {
    background: var(--p-primary-50, rgba(0, 165, 141, 0.08));
}

.mobile-sidebar-count {
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
}

.mobile-sidebar-count strong {
    color: var(--p-text-color);
}
</style>

<!--
    The drawer is teleported to <body>, so the dark panel styling it inherits
    from .sidebar-layout__aside on desktop cannot reach it from a scoped block.
-->
<style>
.mobile-sidebar-drawer {
    width: min(20rem, 85vw) !important;
}

.mobile-sidebar-drawer .p-drawer-content {
    /* The panel paints its own dark background; remove the drawer's padding so
     * it reaches the edges the way the desktop aside does. */
    padding: 0;
    background: #1e293b;
}

.mobile-sidebar-drawer .p-drawer-header {
    background: #1e293b;
    color: #f1f5f9;
}
</style>

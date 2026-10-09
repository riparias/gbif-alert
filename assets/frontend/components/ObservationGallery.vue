<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import Paginator, { type PageState } from "primevue/paginator";
import SpeciesName from "./SpeciesName.vue";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { filtersToParams } from "../utils/filterParams";
import { pickVernacular } from "../utils/vernacular";
import { licenseLabel } from "../utils/license";
import { useBreakpoint } from "../composables/useBreakpoint";
import { useLatestRequest } from "../composables/useLatestRequest";
import type { components } from "../types/api";

type GalleryPageOut = components["schemas"]["GalleryPageOut"];
type ObservationImage = components["schemas"]["ObservationImageOut"];

/**
 * The first photo of each matching observation that has some, newest first.
 * A tile opens the observation in the drawer, which shows all its photos.
 *
 * Fetched on demand like the breakdown tabs: while the tab is hidden, a change
 * only marks the page stale. It pages, unlike them, so it does not use
 * useFilteredBreakdown.
 */
const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ open: [stableId: string] }>();

const { t, locale } = useI18n();
const { isMobile } = useBreakpoint();
const filtersStore = useFiltersStore();
const resultsStore = useResultsStore();

const PAGE_SIZE = 48; // fills the last row at 2, 3, 4, 6 and 8 columns
const page = ref(1);
const data = ref<GalleryPageOut | null>(null);
const stale = ref(true);
const top = ref<HTMLElement | null>(null);
const { loading, error, load: fetchLatest } = useLatestRequest<GalleryPageOut>();

async function load() {
    const params = filtersToParams(filtersStore);
    params.set("page", String(page.value));
    params.set("pageSize", String(PAGE_SIZE));
    const result = await fetchLatest(`/api/v2/observations/gallery/?${params}`);
    if (result === undefined) return; // superseded, or failed (error is set)
    // Under a status filter, the observation just viewed leaves the results and
    // can empty the last page: step back rather than show nothing.
    if (result.items.length === 0 && page.value > 1) {
        page.value -= 1;
        return load();
    }
    data.value = result;
    stale.value = false;
}

function loadIfActive() {
    if (props.active) {
        load();
    } else {
        stale.value = true;
    }
}

const reloadOnFilterChange = debounce(() => {
    page.value = 1;
    loadIfActive();
}, 300);

// Watch the request the filters make, not the store: the URL sync rewrites the
// store with equal values on every query change, the drawer's ?obs= included,
// which would send the gallery back to page 1 whenever a tile is opened.
watch(() => filtersToParams(filtersStore).toString(), reloadOnFilterChange);
// Closing the drawer can change a status (see bumpStatusEpoch). Stay on the
// page, unlike for a filter change: browsing goes tile, drawer, next tile.
watch(() => resultsStore.statusEpoch, loadIfActive);
watch(
    () => props.active,
    (isActive) => {
        if (isActive && stale.value) load();
    },
);

onMounted(() => {
    if (props.active) load();
});
onUnmounted(() => reloadOnFilterChange.cancel());

function onPage(event: PageState) {
    page.value = event.page + 1;
    load();
    // The paginator sits below the grid: bring the new page's first row back.
    top.value?.scrollIntoView({ block: "start" });
}

// A thumbnail GBIF's cache cannot serve becomes a placeholder: unlike in the
// detail panel the tile stays, since it still opens the observation.
const failedThumbnails = ref(new Set<string>());

function dropThumbnail(image: ObservationImage) {
    failedThumbnails.value = new Set(failedThumbnails.value).add(image.thumbnailUrl);
}

function credit(image: ObservationImage): string {
    return [image.attribution, licenseLabel(image.license)].filter(Boolean).join(" · ");
}
</script>

<template>
    <div v-if="error" class="gallery-message">
        {{ t("message.resultsLoadFailed") }}
        <a href="#" class="gallery-retry" @click.prevent="load()">{{ t("message.retry") }}</a>
    </div>

    <div v-else-if="!data" class="gallery-message">
        <i class="pi pi-spin pi-spinner" />
    </div>

    <div v-else-if="data.count === 0" class="gallery-message">
        <i class="pi pi-images" /> {{ t("message.galleryEmpty") }}
    </div>

    <div v-else ref="top" class="gallery">
        <p class="gallery-count">
            {{
                t(
                    "message.observationsWithPhotos",
                    { count: data.count.toLocaleString(locale) },
                    data.count,
                )
            }}
        </p>

        <ul class="gallery-grid" :class="{ 'gallery-grid-loading': loading }">
            <li v-for="item in data.items" :key="item.stableId">
                <!-- A button: the whole tile opens the observation, with
                     keyboard activation and focus for free. -->
                <button type="button" class="gallery-tile" @click="emit('open', item.stableId)">
                    <img
                        v-if="!failedThumbnails.has(item.image.thumbnailUrl)"
                        :src="item.image.thumbnailUrl"
                        :alt="t('message.observationPhoto')"
                        :title="credit(item.image) || undefined"
                        loading="lazy"
                        @error="dropThumbnail(item.image)"
                    />
                    <span v-else class="gallery-placeholder"><i class="pi pi-image" /></span>
                    <span class="gallery-caption">
                        <span class="gallery-species">
                            <SpeciesName
                                :scientific-name="item.scientificName"
                                :vernacular-name="pickVernacular(item, locale)"
                            />
                        </span>
                        <span class="gallery-date">{{ item.date }}</span>
                    </span>
                </button>
            </li>
        </ul>

        <Paginator
            v-if="data.count > PAGE_SIZE"
            :rows="PAGE_SIZE"
            :total-records="data.count"
            :first="(page - 1) * PAGE_SIZE"
            :template="isMobile ? 'PrevPageLink CurrentPageReport NextPageLink' : undefined"
            @page="onPage"
        />
    </div>
</template>

<style scoped>
.gallery-message {
    padding: 2rem 1rem;
    text-align: center;
    color: var(--p-text-muted-color);
}

.gallery-retry {
    margin-left: 0.5rem;
}

.gallery-count {
    margin: 0.5rem 0;
    font-size: 0.9rem;
    color: var(--p-text-muted-color);
}

.gallery-grid {
    list-style: none;
    margin: 0 0 0.75rem;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
    gap: 0.75rem;
}

/* Without it, a 200px-wide thumbnail widens its column past its share. */
.gallery-grid > li {
    min-width: 0;
}

/* Two columns on a phone: 10rem does not fit twice, and a single column would
   stretch the 200px thumbnails to the full width. */
@media (max-width: 767.98px) {
    .gallery-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 0.5rem;
    }
}

.gallery-grid-loading {
    opacity: 0.5;
}

.gallery-tile {
    all: unset;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    width: 100%;
    border: 1px solid var(--p-content-border-color);
    border-radius: 8px;
    background: var(--p-content-background);
    overflow: hidden;
    cursor: pointer;
}

.gallery-tile:hover,
.gallery-tile:focus-visible {
    border-color: var(--p-primary-color);
}

.gallery-tile img,
.gallery-placeholder {
    display: block;
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    /* GBIF's cache can take seconds on a first request: show a box meanwhile */
    background: var(--p-content-hover-background);
}

.gallery-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: var(--p-text-muted-color);
}

.gallery-caption {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 0.375rem 0.5rem;
    min-width: 0;
}

.gallery-species {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 0.85rem;
    font-weight: 600;
}

.gallery-date {
    font-size: 0.8rem;
    color: var(--p-text-muted-color);
}
</style>

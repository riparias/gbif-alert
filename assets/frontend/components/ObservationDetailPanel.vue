<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Card from "primevue/card";
import Button from "primevue/button";
import Textarea from "primevue/textarea";
import Tag from "primevue/tag";
import SingleObservationMap from "./SingleObservationMap.vue";
import SpeciesName from "./SpeciesName.vue";
import type { components } from "../types/api";
import { getCsrf } from "../utils/csrf";
import { getNavConfig } from "../utils/navConfig";
import { pickVernacular } from "../utils/vernacular";
import { licenseLabel } from "../utils/license";
import { useDisplayLabels } from "../composables/useDisplayLabels";
import { usePreferencesStore } from "../stores/preferences";

type ObservationDetail = components["schemas"]["ObservationDetailOut"];
type ObservationImage = components["schemas"]["ObservationImageOut"];
type Comment = components["schemas"]["CommentOut"];

const props = defineProps<{ stableId: string }>();
const emit = defineEmits<{ close: [] }>();

const { t, locale } = useI18n();
const { ensureBasisOfRecordLoaded, basisOfRecordName } = useDisplayLabels();
const preferences = usePreferencesStore();

const obs = ref<ObservationDetail | null>(null);
const loading = ref(true);
const errorMessage = ref<string | null>(null);

// Comment form
const newCommentText = ref("");
const commentSubmitting = ref(false);
const commentError = ref<string | null>(null);

// Mark-unseen
const markingUnseen = ref(false);

// Photos. Camera-trap observations carry hundreds of frames: show the first
// ones and link to GBIF for the rest. A thumbnail GBIF's cache cannot serve
// (e.g. xeno-canto sonograms) is dropped rather than shown broken.
const MAX_PHOTOS = 12;
const failedThumbnails = ref(new Set<string>());
const shownImages = computed(() =>
    (obs.value?.images ?? [])
        .filter((image) => !failedThumbnails.value.has(image.thumbnailUrl))
        .slice(0, MAX_PHOTOS),
);

function dropThumbnail(image: ObservationImage) {
    failedThumbnails.value = new Set(failedThumbnails.value).add(image.thumbnailUrl);
}

// dcterms:references is meant to be the source page, but some publishers put a
// credit there (Pl@ntNet): only link to it when it is a URL.
function photoLink(image: ObservationImage): string {
    return image.sourceUrl.startsWith("http") ? image.sourceUrl : image.originalUrl;
}

function photoCredit(image: ObservationImage): string {
    return [image.attribution, licenseLabel(image.license)].filter(Boolean).join(" \u00b7 ");
}

const isAuthenticated: boolean = getNavConfig().user.isAuthenticated;

// The public API no longer exposes a Django admin URL; superusers rebuild it
// here from the observation id (the API used to leak this staff-only link).
const adminUrl = computed(() => {
    const nc = getNavConfig();
    return nc.user.isSuperuser && obs.value
        ? `${nc.urls.admin}dashboard/observation/${obs.value.id}/change/`
        : null;
});

// initialDataImport is now a structured object; reproduce the old
// "Data import #N (date)" label for display.
const initialDataImportLabel = computed(() => {
    if (!obs.value) return "";
    const di = obs.value.initialDataImport;
    return `${di.name} (${new Date(di.startedAt).toLocaleDateString(locale.value)})`;
});

// The title is a SpeciesName (preferred name style + generic-image tooltip);
// the subtitle shows the other name, when there is a vernacular one at all.
const secondaryName = computed(() => {
    if (!obs.value) return null;
    const vernacular = pickVernacular(obs.value, locale.value);
    if (!vernacular) return null;
    return preferences.speciesNameMode === "vernacular"
        ? { text: obs.value.scientificName, scientific: true }
        : { text: vernacular, scientific: false };
});

// obs.date is a plain YYYY-MM-DD: format it in UTC so it never shifts a day.
const formattedDate = computed(() =>
    obs.value
        ? new Date(obs.value.date).toLocaleDateString(locale.value, {
              day: "numeric",
              month: "short",
              year: "numeric",
              timeZone: "UTC",
          })
        : "",
);

// "2 days ago", "last month", ... in the active locale.
const relativeDate = computed(() => {
    if (!obs.value) return "";
    const days = Math.round((Date.parse(obs.value.date) - Date.now()) / 86_400_000);
    const rtf = new Intl.RelativeTimeFormat(locale.value, { numeric: "auto" });
    if (Math.abs(days) < 31) return rtf.format(days, "day");
    if (Math.abs(days) < 365) return rtf.format(Math.round(days / 30.4), "month");
    return rtf.format(Math.round(days / 365.25), "year");
});

async function load() {
    errorMessage.value = null;
    obs.value = null;
    failedThumbnails.value = new Set();
    commentError.value = null;
    loading.value = true;
    try {
        const resp = await fetch(`/api/v2/observations/${props.stableId}/`);
        if (!resp.ok) {
            // Anything but 404 (e.g. 429 from the API throttle, 500) is generic.
            errorMessage.value = t(
                resp.status === 404 ? "message.observationNotFound" : "message.unexpectedError",
            );
            return;
        }
        obs.value = await resp.json();
        // Resolve the basis-of-record name from its id (idempotent; covers the
        // deep-link case where the drawer mounts before the table's load).
        ensureBasisOfRecordLoaded();
        if (isAuthenticated) {
            // The detail GET no longer marks the observation as seen (the API is
            // side-effect free); do it explicitly so the table/sidebar reflect it
            // when the drawer closes. Best-effort: seen state isn't load-critical.
            await fetch(`/api/v2/observations/${props.stableId}/mark-as-viewed/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrf() },
            }).catch(() => {
                /* non-fatal */
            });
        }
    } catch {
        // Network failure: without this the drawer would stay blank.
        errorMessage.value = t("message.unexpectedError");
    } finally {
        loading.value = false;
    }
}

async function submitComment() {
    if (!newCommentText.value.trim()) return;
    commentSubmitting.value = true;
    commentError.value = null;
    try {
        const resp = await fetch(`/api/v2/observations/${props.stableId}/comments/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
            body: JSON.stringify({ text: newCommentText.value.trim() }),
        });
        if (!resp.ok) {
            commentError.value = t("message.errorPostingComment");
            return;
        }
        const comment: Comment = await resp.json();
        obs.value!.comments.unshift(comment);
        newCommentText.value = "";
    } finally {
        commentSubmitting.value = false;
    }
}

async function markUnseen() {
    markingUnseen.value = true;
    try {
        const resp = await fetch(`/api/v2/observations/${props.stableId}/mark-as-not-viewed/`, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrf() },
        });
        if (resp.ok) {
            emit("close");
        }
    } finally {
        markingUnseen.value = false;
    }
}

function gbifOccurrenceUrl(id: string) {
    return `https://www.gbif.org/occurrence/${id}`;
}

function gbifDatasetUrl(key: string) {
    return `https://www.gbif.org/dataset/${key}`;
}

watch(() => props.stableId, load);
onMounted(load);
</script>

<template>
    <div class="obs-detail-panel">
        <!-- Loading / error (not found, throttled, ...) -->
        <div v-if="loading" class="detail-loading">
            <i class="pi pi-spin pi-spinner" /> {{ t("message.loading") }}
        </div>
        <div v-else-if="errorMessage" class="detail-not-found">
            {{ errorMessage }}
        </div>

        <template v-else-if="obs">
            <!-- Header: species + GBIF link -->
            <div class="detail-header">
                <div class="detail-title">
                    <h2>
                        <SpeciesName
                            :scientific-name="obs.scientificName"
                            :vernacular-name="pickVernacular(obs, locale)"
                        />
                    </h2>
                    <div
                        v-if="secondaryName"
                        class="detail-subtitle"
                        :class="{ 'scientific-name': secondaryName.scientific }"
                    >
                        {{ secondaryName.text }}
                    </div>
                </div>
                <div class="detail-header-actions">
                    <a
                        :href="gbifOccurrenceUrl(obs.gbifId)"
                        target="_blank"
                        rel="noopener"
                        class="gbif-button"
                        :title="t('message.viewOnGbif')"
                        :aria-label="`${t('message.viewOnGbif')} (${t('message.gbifId')} ${obs.gbifId})`"
                    >
                        <!-- GBIF mark, paths from gbif.org's own logo -->
                        <svg class="gbif-mark" viewBox="0 0 247 239" aria-hidden="true">
                            <path
                                d="M105.17,116.46c0-46.6,22.75-86.94,90.42-86.94,0,46.7-30.72,86.94-90.42,86.94"
                            />
                            <path
                                d="M213.6,238.83c12.68,0,22.42-1.8,32.42-5.49,0-36.88-22-63.24-60.87-82.23-29.74-14.91-66.35-22.64-99.73-22.64,14.65-43.97,3.97-98.53-10.23-128.47-15.73,31.37-25.54,85.16-10.44,128.92-29.66,2.16-53.17,15.08-63.12,32.11-.75,1.3-2.26,4.07-1.36,4.54.71.38,1.86-.78,2.57-1.43,10.72-9.92,24.9-14.75,38.53-14.75,31.48,0,53.71,26.13,69.41,41.82,33.75,33.75,66.74,47.67,102.82,47.6"
                            />
                        </svg>
                        {{ obs.gbifId }}
                        <i class="pi pi-external-link" aria-hidden="true" />
                    </a>
                    <a
                        v-if="adminUrl"
                        :href="adminUrl"
                        class="p-button p-button-danger p-button-sm"
                    >
                        {{ t("message.showInAdmin") }}
                    </a>
                </div>
            </div>

            <!-- Mark unseen -->
            <div v-if="obs.canBeMarkedNotViewed" class="mark-unseen-row">
                <Button
                    severity="warn"
                    size="small"
                    icon="pi pi-eye-slash"
                    :label="t('message.markObservationAsUnseen')"
                    :loading="markingUnseen"
                    @click="markUnseen"
                />
            </div>

            <!-- Body -->
            <div class="detail-body">
                <!-- Key facts first (#519), provenance below -->
                <div class="key-facts">
                    <div class="fact-tile">
                        <div class="fact-label">
                            <i class="pi pi-calendar" aria-hidden="true" /> {{ t("message.date") }}
                        </div>
                        <div class="fact-value">{{ formattedDate }}</div>
                        <div class="fact-hint">{{ relativeDate }}</div>
                    </div>
                    <div class="fact-tile">
                        <div class="fact-label">
                            <i class="pi pi-hashtag" aria-hidden="true" />
                            {{ t("message.individualCount") }}
                        </div>
                        <div class="fact-value">{{ obs.individualCount ?? "—" }}</div>
                    </div>
                </div>

                <div class="fact-tags">
                    <Tag
                        :severity="obs.verified ? 'success' : 'danger'"
                        :icon="obs.verified ? 'pi pi-check-circle' : 'pi pi-times-circle'"
                        :title="
                            obs.verifiedByDatasetOverride
                                ? obs.verified
                                    ? t('message.datasetAlwaysVerified')
                                    : t('message.datasetNeverVerified')
                                : undefined
                        "
                    >
                        {{ obs.verified ? t("message.verified") : t("message.unverified") }}
                        <template v-if="obs.identificationVerificationStatus">
                            &middot; {{ obs.identificationVerificationStatus }}
                        </template>
                    </Tag>
                    <Tag
                        severity="secondary"
                        icon="pi pi-tag"
                        :value="basisOfRecordName(obs.basisOfRecordId)"
                    />
                </div>

                <section class="provenance">
                    <h3>{{ t("message.source") }}</h3>
                    <dl>
                        <dt>{{ t("message.dataset") }}</dt>
                        <dd>
                            <a :href="gbifDatasetUrl(obs.gbifDatasetKey)" target="_blank">
                                {{ obs.datasetName }}
                            </a>
                        </dd>

                        <dt>{{ t("message.recordedBy") }}</dt>
                        <dd>{{ obs.recordedBy || "—" }}</dd>

                        <template v-if="obs.references">
                            <dt>{{ t("message.references") }}</dt>
                            <dd>
                                <a
                                    v-if="obs.references.startsWith('http')"
                                    :href="obs.references"
                                    target="_blank"
                                    >{{ obs.references }}</a
                                >
                                <span v-else>{{ obs.references }}</span>
                            </dd>
                        </template>

                        <dt>{{ t("message.firstImportedDuring") }}</dt>
                        <dd>{{ initialDataImportLabel }}</dd>
                    </dl>
                </section>

                <!-- Photos of this observation (not the generic species image) -->
                <Card v-if="shownImages.length" class="observation-photos">
                    <template #title
                        ><i class="pi pi-camera" /> {{ t("message.observationPhotos") }}</template
                    >
                    <template #content>
                        <ul class="photo-grid">
                            <li v-for="(image, index) in shownImages" :key="index">
                                <a :href="photoLink(image)" target="_blank" rel="noopener">
                                    <img
                                        :src="image.thumbnailUrl"
                                        :alt="t('message.observationPhoto')"
                                        @error="dropThumbnail(image)"
                                    />
                                </a>
                                <span
                                    v-if="photoCredit(image)"
                                    class="photo-credit"
                                    :title="photoCredit(image)"
                                    >{{ photoCredit(image) }}</span
                                >
                            </li>
                        </ul>
                        <a
                            v-if="obs.images.length > MAX_PHOTOS"
                            :href="gbifOccurrenceUrl(obs.gbifId)"
                            target="_blank"
                            rel="noopener"
                        >
                            {{ t("message.viewAllPhotosOnGbif", { count: obs.images.length }) }}
                        </a>
                    </template>
                </Card>

                <!-- Map + location details -->
                <Card class="detail-map-card">
                    <template #title
                        ><i class="pi pi-map-marker" /> {{ t("message.location") }}</template
                    >
                    <template #content>
                        <SingleObservationMap
                            v-if="obs.lat != null && obs.lon != null"
                            :lat="obs.lat"
                            :lon="obs.lon"
                            :coordinate-uncertainty-in-meters="obs.coordinateUncertaintyInMeters"
                        />
                        <div v-else class="no-location">{{ t("message.noLocationData") }}</div>

                        <dl class="detail-dl location-dl">
                            <dt>{{ t("message.coordinates") }}</dt>
                            <dd>
                                <span v-if="obs.lon != null && obs.lat != null">
                                    {{ obs.lon }}, {{ obs.lat }}
                                </span>
                                <span v-else class="muted-small">{{ t("message.unknown") }}</span>
                            </dd>

                            <dt>{{ t("message.coordinatesUncertainty") }}</dt>
                            <dd>
                                <span v-if="obs.coordinateUncertaintyInMeters != null">
                                    {{ obs.coordinateUncertaintyInMeters }}
                                    {{ t("message.meters") }}
                                </span>
                                <span v-else class="muted-small">{{ t("message.unknown") }}</span>
                            </dd>

                            <dt>{{ t("message.municipality") }}</dt>
                            <dd>{{ obs.municipality || t("message.unknown") }}</dd>

                            <dt>{{ t("message.locality") }}</dt>
                            <dd>{{ obs.locality || t("message.unknown") }}</dd>
                        </dl>
                    </template>
                </Card>
            </div>

            <!-- Comments -->
            <Card class="comments-card">
                <template #title
                    ><i class="pi pi-comments" /> {{ t("message.userComments") }}</template
                >
                <template #content>
                    <div v-if="obs.comments.length === 0" class="no-comments">
                        {{ t("message.noCommentsYet") }}
                    </div>
                    <div v-for="comment in obs.comments" :key="comment.id" class="comment">
                        <p class="comment-meta">
                            <em>
                                {{
                                    comment.deletedBecauseAuthorDeleted
                                        ? t("message.deletedUser")
                                        : comment.authorUsername
                                }}
                            </em>
                            &mdash; {{ new Date(comment.createdAt).toLocaleString() }}
                        </p>
                        <p v-if="comment.deletedBecauseAuthorDeleted" class="muted-small">
                            <em>{{ t("message.deletedComment") }}</em>
                        </p>
                        <p v-else>{{ comment.text }}</p>
                        <hr />
                    </div>

                    <template v-if="isAuthenticated">
                        <h3 class="new-comment-title">{{ t("message.newComment") }}</h3>
                        <Textarea
                            v-model="newCommentText"
                            rows="3"
                            class="comment-textarea"
                            :placeholder="t('message.writeComment')"
                        />
                        <div v-if="commentError" class="comment-error">{{ commentError }}</div>
                        <Button
                            size="small"
                            icon="pi pi-send"
                            :label="t('message.postComment')"
                            :loading="commentSubmitting"
                            :disabled="!newCommentText.trim()"
                            @click="submitComment"
                        />
                    </template>
                    <p v-else class="sign-in-prompt">
                        {{ t("message.signInToComment") }}
                    </p>
                </template>
            </Card>
        </template>
    </div>
</template>

<style scoped>
.obs-detail-panel {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.detail-loading,
.detail-not-found {
    color: var(--p-text-muted-color);
    font-style: italic;
    padding: 2rem 0;
    text-align: center;
}

.detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}

.detail-title {
    min-width: 0;
}

.detail-title h2 {
    margin: 0;
    font-size: 1.4rem;
    line-height: 1.2;
}

.detail-subtitle {
    color: var(--p-text-muted-color);
}

.scientific-name {
    font-style: italic;
}

.detail-header-actions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
}

/* GBIF green from the GBIF logo */
.gbif-button {
    --gbif-green: #4e9f41;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    height: 2rem;
    padding: 0 0.65rem;
    border: 1px solid var(--p-content-border-color);
    border-radius: var(--p-border-radius-md, 6px);
    background: var(--p-content-background);
    color: var(--p-text-color);
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-size: 0.85rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
    transition:
        border-color 0.15s,
        background 0.15s;
}

.gbif-button:hover,
.gbif-button:focus-visible {
    border-color: var(--gbif-green);
    background: color-mix(in srgb, var(--gbif-green) 8%, transparent);
}

.gbif-mark {
    width: 1.05rem;
    height: 1.05rem;
    fill: var(--gbif-green);
    flex: none;
}

.gbif-button .pi {
    font-size: 0.65rem;
    color: var(--p-text-muted-color);
}

.key-facts {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 0.5rem;
}

.fact-tile {
    border: 1px solid var(--p-content-border-color);
    border-radius: var(--p-border-radius-lg, 8px);
    padding: 0.5rem 0.75rem;
}

.fact-label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--p-text-muted-color);
}

.fact-label .pi {
    font-size: 0.7rem;
}

.fact-value {
    font-size: 1.15rem;
    font-weight: 700;
    margin-top: 0.1rem;
}

.fact-hint {
    font-size: 0.8rem;
    color: var(--p-text-muted-color);
}

.fact-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: -0.25rem;
}

.provenance {
    border-top: 1px solid var(--p-content-border-color);
    padding-top: 0.75rem;
    font-size: 0.85rem;
}

.provenance h3 {
    margin: 0 0 0.4rem;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--p-text-muted-color);
}

.provenance dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.2rem 0.75rem;
    margin: 0;
}

.provenance dt {
    color: var(--p-text-muted-color);
}

.provenance dd {
    margin: 0;
    overflow-wrap: anywhere;
}

.mark-unseen-row {
    display: flex;
}

.detail-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.detail-dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
    margin: 0 0 1rem;
}

.detail-dl dt {
    font-weight: 600;
    white-space: nowrap;
}

.detail-dl dd {
    margin: 0;
}

.location-dl {
    margin-top: 0.75rem;
}

.photo-grid {
    list-style: none;
    margin: 0 0 0.5rem;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
}

.photo-grid img {
    display: block;
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: 4px;
    /* GBIF's cache can take seconds on a first request: show a box meanwhile */
    background: var(--p-content-hover-background);
}

.photo-credit {
    display: block;
    margin-top: 0.25rem;
    font-size: 0.75rem;
    color: var(--p-text-muted-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.no-location {
    color: var(--p-text-muted-color);
    font-style: italic;
    padding: 1rem 0;
    text-align: center;
}

.muted-small {
    color: var(--p-text-muted-color);
    font-size: 0.875rem;
}

.comment {
    margin-bottom: 0.5rem;
}

.comment-meta {
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
    margin-bottom: 0.25rem;
}

.no-comments {
    color: var(--p-text-muted-color);
    font-style: italic;
    margin-bottom: 1rem;
}

.new-comment-title {
    font-size: 1rem;
    margin: 1rem 0 0.5rem;
}

.comment-textarea {
    width: 100%;
    margin-bottom: 0.5rem;
    display: block;
}

.comment-error {
    color: var(--p-red-500, #ef4444);
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
}

.sign-in-prompt {
    color: var(--p-text-muted-color);
    font-style: italic;
}

@media (max-width: 767.98px) {
    /* A `max-content` label column plus a long dataset name is wider than the
     * screen, so labels move above their values instead of beside them. */
    .detail-dl {
        grid-template-columns: 1fr;
        gap: 0 0;
    }

    .detail-dl dt {
        margin-top: 0.5rem;
        font-size: 0.8rem;
        color: var(--p-text-muted-color);
    }

    .detail-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .detail-header-actions {
        align-items: flex-start;
    }

    .provenance dl {
        grid-template-columns: 1fr;
        gap: 0;
    }

    .provenance dt {
        margin-top: 0.4rem;
    }
}
</style>

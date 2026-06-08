<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Card from "primevue/card";
import Button from "primevue/button";
import Textarea from "primevue/textarea";
import SingleObservationMap from "./SingleObservationMap.vue";
import SpeciesName from "./SpeciesName.vue";
import type { components } from "../types/api";
import { getCsrf } from "../utils/csrf";
import { getNavConfig } from "../utils/navConfig";
import { pickVernacular } from "../utils/vernacular";
import { useDisplayLabels } from "../composables/useDisplayLabels";

type ObservationDetail = components["schemas"]["ObservationDetailOut"];
type Comment = components["schemas"]["CommentOut"];

const props = defineProps<{ stableId: string }>();
const emit = defineEmits<{ close: [] }>();

const { t, locale } = useI18n();
const { ensureBasisOfRecordLoaded, basisOfRecordName } = useDisplayLabels();

const obs = ref<ObservationDetail | null>(null);
const loading = ref(true);
const notFound = ref(false);

// Comment form
const newCommentText = ref("");
const commentSubmitting = ref(false);
const commentError = ref<string | null>(null);

// Mark-unseen
const markingUnseen = ref(false);

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
    return `${di.name} (${new Date(di.startTimestamp).toLocaleDateString(locale.value)})`;
});

async function load() {
    notFound.value = false;
    obs.value = null;
    commentError.value = null;
    loading.value = true;
    try {
        const resp = await fetch(`/api/v2/observations/${props.stableId}/`);
        if (resp.status === 404) {
            notFound.value = true;
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
            }).catch(() => { /* non-fatal */ });
        }
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
        <!-- Loading / not found -->
        <div v-if="loading" class="detail-loading"><i class="pi pi-spin pi-spinner" /> {{ t("message.loading") }}</div>
        <div v-else-if="notFound" class="detail-not-found">
            {{ t("message.observationNotFound") }}
        </div>

        <template v-else-if="obs">
            <!-- Header -->
            <div class="detail-header">
                <div class="detail-title">
                    <span
                        class="verified-badge"
                        :class="obs.verified ? 'badge-success' : 'badge-danger'"
                    >
                        {{ obs.verified ? t("message.verified") : t("message.unverified") }}
                    </span>
                    <h2>
                        <SpeciesName
                            :scientific-name="obs.scientificName"
                            :vernacular-name="pickVernacular(obs, locale)"
                        />
                        &mdash; {{ obs.date }}
                    </h2>
                </div>
                <div class="detail-header-actions">
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
                <!-- Metadata -->
                <Card class="detail-meta-card">
                    <template #title><i class="pi pi-info-circle" /> {{ t("message.details") }}</template>
                    <template #content>
                        <dl class="detail-dl">
                            <dt>{{ t("message.gbifId") }}</dt>
                            <dd>
                                <a :href="gbifOccurrenceUrl(obs.gbifId)" target="_blank">
                                    {{ obs.gbifId }}
                                </a>
                            </dd>

                            <dt>{{ t("message.species") }}</dt>
                            <dd>
                                <SpeciesName
                                    :scientific-name="obs.scientificName"
                                    :vernacular-name="pickVernacular(obs, locale)"
                                />
                            </dd>

                            <dt>{{ t("message.individualCount") }}</dt>
                            <dd>{{ obs.individualCount ?? "—" }}</dd>

                            <dt>{{ t("message.sourceDataset") }}</dt>
                            <dd>
                                <a :href="gbifDatasetUrl(obs.datasetGbifKey)" target="_blank">
                                    {{ obs.datasetName }}
                                </a>
                            </dd>

                            <dt>{{ t("message.verified") }}</dt>
                            <dd>
                                {{ obs.verified ? t("message.yes") : t("message.no") }}
                                <span
                                    v-if="obs.identificationVerificationStatus"
                                    class="muted-small"
                                >
                                    ({{ obs.identificationVerificationStatus }})
                                </span>
                            </dd>

                            <dt>{{ t("message.basisOfRecord") }}</dt>
                            <dd>{{ basisOfRecordName(obs.basisOfRecordId) }}</dd>

                            <dt>{{ t("message.date") }}</dt>
                            <dd>{{ obs.date }}</dd>

                            <dt>{{ t("message.recordedBy") }}</dt>
                            <dd>{{ obs.recordedBy || "—" }}</dd>

                            <template v-if="obs.references">
                                <dt>{{ t("message.references") }}</dt>
                                <dd>
                                    <a
                                        v-if="obs.references.startsWith('http')"
                                        :href="obs.references"
                                        target="_blank"
                                    >{{ obs.references }}</a>
                                    <span v-else>{{ obs.references }}</span>
                                </dd>
                            </template>

                            <dt>{{ t("message.firstImportedDuring") }}</dt>
                            <dd>{{ initialDataImportLabel }}</dd>
                        </dl>

                    </template>
                </Card>

                <!-- Map + location details -->
                <Card class="detail-map-card">
                    <template #title><i class="pi pi-map-marker" /> {{ t("message.location") }}</template>
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
                <template #title><i class="pi pi-comments" /> {{ t("message.userComments") }}</template>
                <template #content>
                    <div v-if="obs.comments.length === 0" class="no-comments">
                        {{ t("message.noCommentsYet") }}
                    </div>
                    <div
                        v-for="comment in obs.comments"
                        :key="comment.id"
                        class="comment"
                    >
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
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
}

.detail-title {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.detail-title h2 {
    margin: 0;
    font-size: 1.25rem;
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
</style>

<template>
  <p v-if="props.areaIds.length === 0">{{ $t("message.noAreasYet") }}</p>
  <div v-for="areaId in props.areaIds" :key="areaId">
    <SingleAreaMap :areasUrlTemplate="frontendConfig.apiEndpoints.areasUrlTemplate" :areaId="areaId"></SingleAreaMap>
    <delete-area-button
            :area-id="areaId"
            :form-action="frontendConfig.apiEndpoints.areaDeleteUrlTemplate.replace('{id}', areaId.toString())"
            :csrf-token="window.CSRF_TOKEN">
    </delete-area-button>
  </div>

</template>

<script setup lang="ts">
import SingleAreaMap from "../SingleAreaMap.vue";
import {FrontEndConfig} from "../../interfaces";
import {ref} from "vue";
import DeleteAreaButton from "../DeleteAreaButton.vue";

declare const pteroisConfig: FrontEndConfig;

const frontendConfig = ref(pteroisConfig);

const props = defineProps<{
  areaIds: number[]
}>()


</script>
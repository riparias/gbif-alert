<template>
  <SingleAreaMap v-for="areaId in props.areaIds" :areasUrlTemplate="frontendConfig.apiEndpoints.areasUrlTemplate" :areaId="areaId"></SingleAreaMap>
</template>

<script setup lang="ts">
import SingleAreaMap from "../SingleAreaMap.vue";
import {FrontEndConfig} from "../../interfaces";
import {ref} from "vue";

declare const pteroisConfig: FrontEndConfig;

const frontendConfig = ref(pteroisConfig);

const props = defineProps<{
  areaIds: number[]
}>()


</script>
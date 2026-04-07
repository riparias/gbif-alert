<script setup lang="ts">
import NavBar from "./components/layout/NavBar.vue";
import ConfirmDialog from "primevue/confirmdialog";
import Toast from "primevue/toast";
</script>

<template>
    <NavBar />
    <ConfirmDialog />
    <Toast />
    <RouterView />
</template>

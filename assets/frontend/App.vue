<script setup lang="ts">
import NavBar from "./components/layout/NavBar.vue";
import ConfirmDialog from "primevue/confirmdialog";
import Toast from "primevue/toast";
</script>

<template>
    <NavBar />
    <ConfirmDialog />
    <Toast />
    <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
            <component :is="Component" />
        </Transition>
    </RouterView>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>

<script setup lang="ts">
import NavBar from "./components/layout/NavBar.vue";
</script>

<template>
    <NavBar />
    <!-- RouterView renders nothing in Phase 1 (no routes defined yet).
         In Phase 2+ each migrated page registers a route and renders here. -->
    <RouterView />
</template>

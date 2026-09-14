<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppAside from "@/components/app-aside.vue";

defineOptions({
  name: "DefaultLayout",
});

const route = useRoute();
const showAside = computed(() => route.meta.inMenu !== false);
const fullPage = computed(() => route.meta.fullPage === true || route.path === "/");
</script>

<template>
  <div class="flex h-screen bg-[#f1f5f9]">
    <AppAside v-if="showAside" />
    <main
      class="flex-1 min-w-0 overflow-auto p-6"
      :class="{ '!p-0 !overflow-hidden': !showAside || fullPage }"
    >
      <RouterView />
    </main>
  </div>
</template>

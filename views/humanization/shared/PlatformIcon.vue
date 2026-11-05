<script setup>
import { ref } from 'vue';
import { mdiRobotOutline } from '@mdi/js';
defineProps({ src:String, name:String });
const failed = ref('');
</script>
<template>
  <img v-if="src && failed !== src" :src="src" :alt="name || '适配器'" width="24" height="24" class="platform-icon" @error="failed = src" />
  <v-icon v-else :icon="mdiRobotOutline" :aria-label="name || '未知适配器'" size="24" />
</template>
<style scoped>
.platform-icon { object-fit:contain; flex-shrink:0; }
</style>

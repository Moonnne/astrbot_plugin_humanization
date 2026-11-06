<script setup>
import { computed, watch } from 'vue';
const props = defineProps({ model:Object, schema:Object });
const levels = computed(() => props.schema.level.options.filter(level => level !== 'TRACK' || props.model.debug));
watch(() => props.model.debug, enabled => {
  if (!enabled && props.model.level === 'TRACK') props.model.level = 'INFO';
});
</script>
<template>
  <v-select v-model="model.level" label="日志等级" aria-label="日志等级" :items="levels" :hint="schema.level.hint" persistent-hint class="mb-5" />
  <v-text-field v-model.number="model.max_mb" label="humanization.log 大小上限（MB）" type="number" min="0" step="any" :hint="schema.max_mb.hint" persistent-hint class="mb-5" />
  <v-switch v-model="model.debug" label="调试模式" :hint="schema.debug.hint" persistent-hint color="primary" inset />
  <v-expand-transition>
    <v-card v-if="model.debug" aria-label="调试日志选项" class="pa-4 mt-4">
      <v-switch v-model="model.mask" label="数据脱敏" :hint="schema.mask.hint" persistent-hint color="primary" inset class="mb-3" />
      <v-switch v-model="model.echo" label="日志回显" :hint="schema.echo.hint" persistent-hint color="primary" inset />
    </v-card>
  </v-expand-transition>
</template>

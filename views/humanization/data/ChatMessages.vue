<script setup>
import ChatMedia from './ChatMedia.vue';
import {mdiEyeOutline, mdiDeleteOutline} from '@mdi/js';
import {computed} from 'vue';
const props = defineProps({rows:Array, time:Function, modelValue:Array});
const emit = defineEmits(['detail','remove','update:modelValue']);
const selected = computed({get:()=>props.modelValue, set:value=>emit('update:modelValue',value)});
</script>
<template>
  <article v-for="row in rows" :key="row.key" class="d-flex align-start ga-2 pa-3" :class="{'flex-row-reverse':row.direction==='out'}">
    <v-checkbox-btn v-model="selected" :value="row.key" :aria-label="'选择消息 '+row.seq" class="flex-grow-0" />
    <div class="bubble">
      <small>{{ row.sender_name || row.sender_id }} · {{ time(row.timestamp) }}</small>
      <v-card class="pa-3 mt-1" :color="row.direction === 'out' ? 'primary' : undefined" variant="tonal">
        <template v-for="(part,i) in row.segments" :key="i">
          <ChatMedia v-if="part.resource_id && row.resources.some(r=>r.id===part.resource_id)" :resource="row.resources.find(r=>r.id===part.resource_id)" />
          <span v-else>{{ part.text || (part.type === 'at' ? '@'+part.id : '['+part.type+']') }}</span>
        </template>
        <span v-if="!row.segments.length">{{ row.text }}</span>
      </v-card>
      <v-btn size="x-small" variant="text" :icon="mdiEyeOutline" aria-label="查看详情" @click="$emit('detail', row)" />
      <v-btn size="x-small" variant="text" :icon="mdiDeleteOutline" aria-label="删除消息" @click="$emit('remove', row)" />
    </div>
  </article>
</template>
<style scoped>
.bubble { max-width: min(80%, 48rem); white-space: pre-wrap; overflow-wrap: anywhere; }
</style>

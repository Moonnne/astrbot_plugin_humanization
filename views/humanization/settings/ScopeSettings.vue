<script setup>
import { computed } from 'vue';
import SchemaFields from './SchemaFields.vue';
const props = defineProps({ schema:Object, model:Object, choices:Object });
const fields = computed(() => Object.fromEntries(
  (props.model.all_sessions ? ['blacklist_sessions','blacklist_manual_sessions','blacklist_action'] : ['sessions','manual_sessions','outside_action']).map(key => [key,props.schema[key]])
));
</script>
<template>
  <SchemaFields :schema="{all_sessions:schema.all_sessions}" :model="model" :choices="choices" />
  <v-card tag="section" :aria-label="model.all_sessions ? '会话黑名单' : '会话白名单'" rounded="lg">
    <v-card-title class="text-subtitle-1 font-weight-bold pa-4">{{ model.all_sessions ? '会话黑名单' : '会话白名单' }}</v-card-title>
    <v-card-text>
      <p class="text-body-2 text-medium-emphasis mb-4">{{ model.all_sessions ? '未命中黑名单的会话正常启用插件；命中时使用下方策略。' : '白名单中的会话正常启用插件；范围外使用下方策略。' }} 已匹配的插件指令及其 LLM 请求不受范围策略限制。</p>
      <SchemaFields :schema="fields" :model="model" :choices="choices" />
    </v-card-text>
  </v-card>
</template>

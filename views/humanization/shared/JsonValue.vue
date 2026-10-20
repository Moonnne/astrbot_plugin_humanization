<script setup>
import { computed } from 'vue';
const props = defineProps({ value: { default: null } });
const parsed = computed(() => {
  if (typeof props.value === 'string' && /^[\[{]/.test(props.value.trim())) {
    try { return JSON.parse(props.value); } catch { /* A normal string remains text. */ }
  }
  return props.value;
});
const labels = { sender_id:'发送者ID', target_id:'目标ID', target_is_self:'目标是本机器人', type:'类型', text:'正文', reply:'回应', reason:'原因', emotion:'情绪', primary:'主情绪', intensity:'强度', plan:'计划', participation:'参与方式', target_message_id:'目标消息', topic_id:'话题ID', intent:'意图', style:'风格', guidance:'回复指导', topic:'主题', interact:'参与行为', reaction:'用户反应', day:'日期', topic_time:'话题时间' };
</script>
<template>
  <div v-if="parsed === null" class="text-medium-emphasis">—</div>
  <div v-else-if="Array.isArray(parsed)" class="d-flex flex-column ga-2">
    <span v-if="!parsed.length" class="text-medium-emphasis">无</span>
    <v-card v-for="(item,index) in parsed" :key="index" class="pa-3"><JsonValue :value="item" /></v-card>
  </div>
  <v-table v-else-if="typeof parsed === 'object'" density="compact">
    <tbody><tr v-for="(item,key) in parsed" :key="key">
      <td class="text-medium-emphasis text-no-wrap align-top py-2">{{ labels[key] || key }}</td>
      <td class="text-break py-2"><JsonValue :value="item" /></td>
    </tr></tbody>
  </v-table>
  <div v-else class="text-body-2 text-pre-wrap text-break">{{ parsed === true ? '是' : parsed === false ? '否' : parsed }}</div>
</template>

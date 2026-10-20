<script setup>
import { ref, computed, watch, inject, onBeforeUnmount } from 'vue';
import { mdiMagnify, mdiDeleteOutline, mdiEyeOutline } from '@mdi/js';
import JsonValue from '../shared/JsonValue.vue';
const props = defineProps({ category: String, scope: String, refresh: Number, timezone: String });
const emit = defineEmits(['changed']);
const bridge = inject('bridge');
const q = ref(''), start = ref(''), end = ref(''), kind = ref('');
const page = ref(1), limit = ref(25), sort = ref([{ key:'timestamp', order:'desc' }]);
const rows = ref([]), total = ref(0), selected = ref([]), loading = ref(false), error = ref('');
const detail = ref(null), confirm = ref(false), deleting = ref(false), success = ref('');
let generation = 0, timer;
const titles = { messages:'聊天记录', decisions:'最近反应', topics:'话题', diaries:'日记' };
const kinds = computed(() => ({
  messages:[['in','收到的消息'],['out','机器人回复']],
  decisions:[['pending','待执行'],['processed','发送流程完成'],['observed','保持沉默'],['failed','失败'],['superseded','已被取代'],['unconfirmed','结果未确认']],
  topics:[], diaries:[['0','未封存'],['1','已封存']],
}[props.category].map(([value,title]) => ({value,title}))));
const headers = computed(() => [
  { title:'时间', key:'timestamp', width:180 }, { title:'会话', key:'conversation', sortable:false, width:220 },
  { title:props.category === 'decisions' ? '规划原因' : '内容', key:'headline' },
  { title:props.category === 'messages' ? '发送者' : '状态', key:'state', sortable:false, width:150 },
  { title:'操作', key:'actions', sortable:false, width:120 },
]);
function time(value) { return new Date(value * 1000).toLocaleString('zh-CN', { timeZone:props.timezone, hour12:false }); }
async function load() {
  const current = ++generation;
  loading.value = true; error.value = ''; selected.value = [];
  try {
    const data = await bridge.apiGet('records', {category:props.category, scope:props.scope, q:q.value, start:start.value, end:end.value, kind:kind.value, page:page.value, limit:limit.value, sort:sort.value[0]?.key || 'timestamp', order:sort.value[0]?.order || 'desc'});
    if (current !== generation) return;
    rows.value = data.items; total.value = data.total;
    const lastPage = Math.max(1, Math.ceil(data.total / limit.value));
    if (page.value > lastPage) page.value = lastPage;
  } catch (e) { if (current === generation) error.value = e.message; }
  finally { if (current === generation) loading.value = false; }
}
function queue() { clearTimeout(timer); timer = setTimeout(load, 200); }
watch([q,start,end,kind,() => props.scope], () => { page.value = 1; queue(); });
watch([page,limit,sort,() => props.refresh], queue, {deep:true});
queue();
onBeforeUnmount(() => { clearTimeout(timer); generation++; });
function removeOne(row) { selected.value = [row.key]; confirm.value = true; }
async function remove() {
  deleting.value = true; error.value = '';
  try {
    const result = await bridge.apiPost('records/delete', {category:props.category, keys:[...selected.value]});
    confirm.value = false; detail.value = null;
    success.value = `已删除 ${result.deleted} 条${titles[props.category]}`;
    await load(); emit('changed');
  } catch (e) { error.value = e.message; confirm.value = false; }
  finally { deleting.value = false; }
}
const detailFields = computed(() => {
  if (!detail.value) return {};
  const result = { ...detail.value };
  for (const key of ['key','search','headline','timestamp','kind','scope']) delete result[key];
  return result;
});
</script>
<template>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
  <v-alert v-if="success" type="success" variant="tonal" closable class="mb-4" @click:close="success = ''">{{ success }}</v-alert>
  <v-row>
    <v-col cols="12" md="4"><v-text-field v-model="q" label="搜索正文、用户或规划内容" :prepend-inner-icon="mdiMagnify" clearable hide-details @click:clear="q = ''" /></v-col>
    <v-col cols="6" md="3"><v-text-field v-model="start" type="date" label="开始日期" hide-details /></v-col>
    <v-col cols="6" md="3"><v-text-field v-model="end" type="date" label="结束日期" hide-details /></v-col>
    <v-col v-if="kinds.length" cols="12" md="2"><v-select v-model="kind" label="类型 / 状态" :items="[{title:'全部',value:''},...kinds]" hide-details /></v-col>
  </v-row>
  <div class="d-flex align-center flex-wrap ga-3 my-4">
    <div class="text-body-2 text-medium-emphasis flex-grow-1">共 {{ total }} 条 · 已选 {{ selected.length }} 条（当前页） · {{ timezone }}</div>
    <v-btn color="error" :prepend-icon="mdiDeleteOutline" :disabled="!selected.length || loading" @click="confirm = true">删除所选</v-btn>
  </div>
  <v-card>
    <v-data-table-server v-model="selected" v-model:page="page" v-model:items-per-page="limit" v-model:sort-by="sort" :headers="headers" :items="rows" :items-length="total" :loading="loading" :items-per-page-options="[10,25,50,100]" item-value="key" show-select select-strategy="page" must-sort hover>
      <template #item.timestamp="{item}">{{ time(item.timestamp) }}</template>
      <template #item.conversation="{item}"><span class="text-caption text-break">{{ item.conversation }}</span></template>
      <template #item.headline="{item}"><span class="text-body-2 text-break">{{ item.headline?.slice(0,180) }}{{ item.headline?.length > 180 ? '…' : '' }}</span></template>
      <template #item.state="{item}">
        <span v-if="category === 'messages'" class="text-caption">{{ item.sender_name }}<br>{{ item.direction === 'out' ? '机器人回复' : item.sender_id }}</span>
        <div v-else-if="category === 'decisions'" class="d-flex flex-wrap ga-1">
          <v-chip size="small" :color="item.decision_json.reply ? 'primary' : undefined">{{ item.decision_json.reply ? '回复' : '观望' }}</v-chip>
          <span class="text-caption">{{ item.decision_json.emotion.primary }} · {{ item.outcome }}</span>
        </div>
        <span v-else-if="category === 'diaries'">{{ item.sealed ? '已封存' : '未封存' }} · {{ item.topic_count }} 个话题</span>
        <span v-else class="text-caption">{{ item.day }}</span>
      </template>
      <template #item.actions="{item}">
        <v-btn :icon="mdiEyeOutline" aria-label="查看详情" size="small" variant="text" @click="detail = item" />
        <v-btn :icon="mdiDeleteOutline" aria-label="删除记录" size="small" variant="text" color="error" @click="removeOne(item)" />
      </template>
    </v-data-table-server>
  </v-card>
  <v-dialog :model-value="!!detail" max-width="1000" scrollable @update:model-value="!$event && (detail = null)">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">{{ titles[category] }}详情</v-card-title>
      <v-card-text><JsonValue :value="detailFields" /></v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="detail = null">关闭</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog v-model="confirm" max-width="540" :persistent="deleting">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">确认删除</v-card-title>
      <v-card-text>
        将永久删除所选 {{ selected.length }} 条{{ titles[category] }}。
        <p v-if="category === 'diaries'" class="mt-3">这些日期下的话题会一并删除。</p>
        <p v-if="category === 'messages'" class="mt-3">已有日记仍保留，消息累计序号不回退。当前群聊消息不足门槛时，会重新进入观察期。</p>
        <p class="mt-3">仅处理插件数据，不清除 AstrBot 原生对话。正在回复或整理时会拒绝删除，请稍后重试。</p>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="deleting" @click="confirm = false">取消</v-btn><v-btn color="error" :loading="deleting" @click="remove">确认删除</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>

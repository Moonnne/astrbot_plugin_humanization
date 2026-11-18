<script setup>
import { ref, reactive, computed, watch, inject, nextTick, onBeforeUnmount } from 'vue';
import { mdiArrowLeft, mdiFilterVariant, mdiDeleteOutline, mdiEyeOutline } from '@mdi/js';
import JsonValue from '../shared/JsonValue.vue';
import ChatMessages from './ChatMessages.vue';
import MediaViewer from './MediaViewer.vue';
import FilterPanel from './FilterPanel.vue';
import ResizableHeaders from './ResizableHeaders.vue';
import { sessionLabel } from '../shared/session.js';
import { outcomes, emotions } from './options.js';
const props = defineProps({ category:String, sessions:Array, refresh:Number, timezone:String });
const emit = defineEmits(['changed']);
const bridge = inject('bridge');
const defaults = {q:'', sessions:[], chat_type:'', start:'', end:'', kind:'', sender:'', component:'', reply:'', emotion:'', required:'', trigger:'', participant:'', bot_reply:'', coverage_gap:'', sort:'timestamp:desc'};
const filters = reactive({...defaults, sessions:[]});
const filterToggle = ref(null);
const smallWindow = window.matchMedia('(max-width: 960px)');
const compact = ref(smallWindow.matches);
const desktopFilters = ref(true), mobileFilters = ref(false);
const filtersOpen = computed({
  get: () => compact.value ? mobileFilters.value : desktopFilters.value,
  set: value => { (compact.value ? mobileFilters : desktopFilters).value = value; },
});
function resizeLayout(event) { compact.value = event.matches; mobileFilters.value = false; }
smallWindow.addEventListener('change', resizeLayout);
async function closeFilters() {
  filtersOpen.value = false;
  await nextTick();
  filterToggle.value?.$el.focus({preventScroll:true});
}
const currentChat = ref(null);
const grouped = computed(() => props.category === 'messages' && !currentChat.value);
const nextCursor = ref(null);
const sentinel = ref(null);
let observer;
watch(sentinel, element => {
  observer?.disconnect();
  if (element) {
    observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting) && !loading.value) load(true);
    }, {rootMargin:'160px'});
    observer.observe(element);
  }
}, {flush:'post'});
function openChat(chat) {
  currentChat.value = chat;
  if (chat && !filters.sort.startsWith('timestamp:')) filters.sort = 'timestamp:desc';
  page.value = 1;
  rows.value = []; selected.value = []; total.value = 0;
  queue(0);
}
const sessionTitles = computed(() => Object.fromEntries(props.sessions.map(item => [item.umo,item.title !== item.umo ? item.title : item.umo.split(':').slice(2).join(':')])));
const defaultWidths = {
  timestamp:168, conversation:172, headline:216, state:props.category === 'topics' ? 96 : 132, day:128, message_count:120, actions:88,
  ...(props.category === 'decisions' && {timestamp:152, conversation:144, headline:172, decision:84, emotion:84, state:124}),
};
const widths = reactive({...defaultWidths});
const page = ref(1), limit = ref(25);
const sort = computed({
  get() { const [key,order] = filters.sort.split(':'); return [{key,order}]; },
  set(value) { filters.sort = value[0] ? `${value[0].key}:${value[0].order}` : 'timestamp:desc'; },
});
const rows = ref([]), total = ref(0), selected = ref([]), loading = ref(false), error = ref('');
const detail = ref(null), confirm = ref(false), deleting = ref(false), success = ref('');
const mediaPreview = ref(null);
let generation = 0, timer;
const titles = { messages:'聊天记录', decisions:'最近反应', topics:'话题', diaries:'日记' };
const headers = computed(() => grouped.value ? [
  {title:'会话', key:'conversation', width:widths.conversation},
  {title:'消息数', key:'message_count', width:widths.message_count},
  {title:'最近消息', key:'timestamp', width:widths.timestamp},
] : [
  { title:'时间', key:'timestamp', width:widths.timestamp }, { title:'会话', key:'conversation', width:widths.conversation },
  { title:props.category === 'decisions' ? '规划原因' : '内容', key:'headline', width:widths.headline },
  ...(props.category === 'decisions' ? [
    { title:'决定', key:'decision', width:widths.decision },
    { title:'情绪', key:'emotion', width:widths.emotion },
  ] : []),
  { title:'状态', key:'state', width:widths.state },
  ...(props.category === 'topics' ? [{title:'日记日期', key:'day', width:widths.day}] : []),
  { title:'操作', key:'actions', sortable:false, width:widths.actions, cellProps:{class:'record-actions'} },
]);
const tableWidth = computed(() => headers.value.reduce((sum, column) => sum + column.width, 48));
const sortChoices = computed(() => {
  const columns = currentChat.value ? headers.value.slice(0,1) : headers.value.filter(col => col.sortable !== false);
  return columns.flatMap(({title,key}) => {
    const [asc,desc] = key === 'timestamp' ? ['从旧到新','从新到旧'] : ['正序','倒序'];
    return [{value:`${key}:desc`,title:`${title}：${desc}`}, {value:`${key}:asc`,title:`${title}：${asc}`}];
  });
});
function time(value) { return new Date(value * 1000).toLocaleString('zh-CN', { timeZone:props.timezone, hour12:false }); }
async function load(append = false) {
  const current = ++generation;
  loading.value = true; error.value = '';
  if (!append) { selected.value = []; nextCursor.value = null; }
  try {
    const [key,order] = filters.sort.split(':');
    const data = await bridge.apiGet('records', {...filters, sessions:JSON.stringify(filters.sessions), category:props.category, grouped:grouped.value ? '1':'0', scope:currentChat.value?.scope || '', page:page.value, limit:currentChat.value ? 50 : limit.value, feed:currentChat.value ? '1' : '0', cursor:append ? nextCursor.value : '', sort:key, order});
    if (current !== generation) return;
    rows.value = append ? [...rows.value,...data.items] : data.items;
    if (!append) total.value = data.total;
    nextCursor.value = data.cursor || null;
    if (currentChat.value) return;
    const lastPage = Math.max(1, Math.ceil(data.total / limit.value));
    if (page.value > lastPage) page.value = lastPage;
  } catch (e) { if (current === generation) error.value = e.message; }
  finally { if (current === generation) loading.value = false; }
}
function queue(delay = 200) {
  ++generation; loading.value = true; nextCursor.value = null;
  clearTimeout(timer); timer = setTimeout(load, delay);
}
watch(filters, () => { page.value = 1; queue(); }, {deep:true});
watch([page,limit,() => props.refresh], () => queue());
queue();
onBeforeUnmount(() => { smallWindow.removeEventListener('change', resizeLayout); observer?.disconnect(); clearTimeout(timer); generation++; });
function removeOne(row) { selected.value = [row.key]; confirm.value = true; }
async function remove() {
  deleting.value = true; error.value = '';
  try {
    const result = await bridge.apiPost('records/delete', {category:grouped.value ? 'sessions' : props.category, keys:[...selected.value]});
    confirm.value = false; detail.value = null;
    success.value = grouped.value ? `已删除 ${result.deleted} 个会话` : `已删除 ${result.deleted} 条${titles[props.category]}`;
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
  <section>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
  <v-alert v-if="success" type="success" variant="tonal" closable class="mb-4" @click:close="success = ''">{{ success }}</v-alert>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <v-btn ref="filterToggle" :prepend-icon="mdiFilterVariant" :aria-expanded="filtersOpen" aria-controls="record-filters" @click="filtersOpen = !filtersOpen">{{ filtersOpen ? '隐藏筛选' : '显示筛选' }}</v-btn>
    <div class="text-body-2 text-medium-emphasis flex-grow-1">共 {{ total }} {{ grouped ? "个会话" : "条" }} <span>· 已选 {{ selected.length }} {{ grouped ? "个" : "条" }}（{{ currentChat ? "已加载" : "当前页" }}）</span></div>
    <v-btn color="error" :prepend-icon="mdiDeleteOutline" :disabled="!selected.length || loading" @click="confirm = true">{{ grouped ? '删除所选会话' : '删除所选' }}</v-btn>
  </div>
  <div class="records-layout" :class="{'compact-layout':compact,'show-filters':filtersOpen}">
    <v-expand-x-transition>
      <div v-show="compact || filtersOpen" id="record-filters" class="filter-column" :inert="!filtersOpen ? '' : null" :aria-hidden="!filtersOpen">
        <FilterPanel :category="category" :model="filters" :sessions="sessions" :sort-choices="sortChoices" :active="filtersOpen" @collapse="closeFilters" @reset="Object.assign(filters, defaults, {sessions:[]})" />
      </div>
    </v-expand-x-transition>
    <v-card class="records-list" rounded="xl" :inert="compact && filtersOpen ? '' : null" :aria-hidden="compact && filtersOpen">
    <template v-if="currentChat">
      <header class="d-flex flex-wrap align-center ga-2 pa-3">
        <v-btn variant="text" :prepend-icon="mdiArrowLeft" @click="openChat(null)">返回会话</v-btn>
        <strong class="session-name">{{ sessionTitles[currentChat.conversation] || currentChat.conversation.split(':').slice(2).join(':') }}</strong>
        <small class="chat-umo text-medium-emphasis">{{ currentChat.conversation }}</small>
      </header>
      <v-divider />
      <ChatMessages v-model="selected" :rows="rows" :time="time" @detail="detail = $event" @preview="mediaPreview = $event" @remove="removeOne" />
      <v-progress-linear v-if="loading" indeterminate />
      <v-btn v-else-if="error" variant="text" @click="load(!!nextCursor)">重新加载</v-btn>
      <div v-else-if="nextCursor" ref="sentinel" style="height:1px"></div>
      <p v-else-if="!rows.length" class="pa-4 text-medium-emphasis">没有符合条件的记录</p>
    </template>
    <v-data-table-server v-else v-model="selected" v-model:page="page" v-model:items-per-page="limit" v-model:sort-by="sort" class="records-table" :style="{'--records-width':`${tableWidth}px`}" :headers="headers" :items="rows" :items-length="total" :loading="loading" :items-per-page-options="[10,25,50,100]" :mobile="false" :item-value="grouped ? 'scope' : 'key'" show-select select-strategy="page" must-sort hover>
      <template #headers="controls"><ResizableHeaders v-bind="controls" :widths="widths" :defaults="defaultWidths" @resize="widths[$event.key] = $event.width" /></template>
      <template #item.timestamp="{item}">{{ time(item.timestamp) }}</template>
      <template #item.conversation="{item}">
        <button v-if="grouped" type="button" class="text-start w-100 py-1" @click="openChat(item)">
          <strong>{{ sessionTitles[item.conversation] || item.conversation.split(':').slice(2).join(':') }}</strong>
          <small class="d-block text-medium-emphasis">{{ item.conversation }}</small>
        </button>
        <div v-else class="text-body-2 text-truncate session-name" :title="`${sessionLabel(item.conversation,sessionTitles[item.conversation])}\n${item.conversation}`">{{ sessionTitles[item.conversation] || item.conversation.split(':').slice(2).join(':') }}</div>
      </template>
      <template #item.headline="{item}"><div class="text-body-2 text-truncate record-headline" :title="item.headline">{{ item.headline }}</div></template>
      <template #item.decision="{item}">
        <v-chip size="small" :color="item.decision ? 'primary' : undefined">{{ item.decision ? '回复' : '观望' }}</v-chip>
      </template>
      <template #item.emotion="{item}">{{ emotions.find(e => e.value === item.emotion)?.title || item.emotion || '—' }}</template>
      <template #item.state="{item}">
        <span v-if="category === 'decisions'">{{ outcomes.find(o => o.value === item.outcome)?.title || item.outcome }}</span>
        <span v-else-if="category === 'topics'">{{ item.sealed ? '已归档' : '未归档' }}</span>
        <span v-else>{{ item.sealed ? '已封存' : '未封存' }} · {{ item.topic_count }} 个话题</span>
      </template>
      <template #item.actions="{item}">
        <v-btn :icon="mdiEyeOutline" aria-label="查看详情" size="small" variant="text" @click="detail = item" />
        <v-btn :icon="mdiDeleteOutline" aria-label="删除记录" size="small" variant="text" color="error" @click="removeOne(item)" />
      </template>
    </v-data-table-server>
    </v-card>
  </div>
  <v-dialog :model-value="!!detail" max-width="1000" scrollable @update:model-value="!$event && (detail = null)">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">{{ titles[category] }}详情</v-card-title>
      <v-card-text>
        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-btn v-for="resource in (detail?.resources || []).filter(r => r.path && ['image','record','video'].includes(r.kind))" :key="resource.id" size="small" @click="mediaPreview = resource">查看 {{ resource.name }}</v-btn>
        </div>
        <JsonValue :value="detailFields" />
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="detail = null">关闭</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  <MediaViewer v-if="mediaPreview" :resource="mediaPreview" @close="mediaPreview = null" />
  <v-dialog v-model="confirm" max-width="540" :persistent="deleting">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">确认删除</v-card-title>
      <v-card-text>
        <p v-if="grouped">将永久删除所选 {{ selected.length }} 个会话的全部聊天、媒体文件、反应、回复记录、话题和日记，包括未命中当前筛选的内容。</p>
        <p v-else>将永久删除所选 {{ selected.length }} 条{{ titles[category] }}。</p>
        <p v-if="category === 'diaries'" class="mt-3">这些日期下的话题会一并删除。</p>
          <p v-if="currentChat" class="mt-3">关联媒体文件及转述记录一并删除。已有日记仍保留，消息累计序号不回退。文件被占用时后台继续清理。当前群聊消息不足门槛时，会重新进入观察期。</p>
        <p class="mt-3">仅处理插件数据，不清除 AstrBot 原生对话。正在回复或整理时会拒绝删除，请稍后重试。</p>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="deleting" @click="confirm = false">取消</v-btn><v-btn color="error" :loading="deleting" @click="remove">确认删除</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  </section>
</template>

<style scoped>
.records-layout { display: flex; align-items: flex-start; min-width: 0; }
/* Animate the occupied width, including the gutter; keep controls at full width. */
.filter-column { position: sticky; top: 8px; max-height: calc(100dvh - 16px); overflow-y: auto; scrollbar-width: thin; flex: 0 0 auto; width: 296px; min-width: 0; }
.filter-column :deep(.filter-panel) { width: 280px; }
.filter-column.expand-x-transition-enter-active,
.filter-column.expand-x-transition-leave-active { transition-duration: 180ms !important; }
.records-list { flex: 1 1 0; min-width: 0; }
.records-table :deep(tbody td) { height: auto !important; padding: 14px 16px !important; vertical-align: middle; }
.records-table :deep(table) { table-layout: fixed; width: var(--records-width); min-width: 100%; }
.records-table :deep(td.record-actions), .records-table :deep(th.record-actions) { position: sticky !important; right: 0; z-index: 2 !important; padding-inline: 8px !important; white-space: nowrap; background: rgb(var(--v-theme-surface)) !important; box-shadow: -1px 0 rgba(var(--v-theme-on-surface),0.1); }
.records-table :deep(th.record-actions) { z-index: 3 !important; }
.chat-umo, header .session-name { overflow-wrap: anywhere; }
.compact-layout { display: block; position: relative; overflow: clip; }
.compact-layout > .filter-column, .compact-layout > .records-list {
  width: 100%; top: 0; max-height: none; transition: transform 180ms ease, visibility 180ms;
}
.compact-layout .filter-column :deep(.filter-panel) { width: 100%; }
.compact-layout .filter-column { overflow: visible; }
.compact-layout.show-filters > .filter-column, .compact-layout:not(.show-filters) > .records-list { position: relative; transform: translateX(0); }
.compact-layout:not(.show-filters) > .filter-column, .compact-layout.show-filters > .records-list { position: absolute; visibility: hidden; pointer-events: none; }
.compact-layout:not(.show-filters) > .filter-column { transform: translateX(100%); }
.compact-layout.show-filters > .records-list { transform: translateX(-100%); }
@media (prefers-reduced-motion: reduce) {
  .compact-layout > .filter-column, .compact-layout > .records-list { transition: none; }
  .filter-column.expand-x-transition-enter-active,
  .filter-column.expand-x-transition-leave-active { transition-duration: 0ms !important; }
}
</style>

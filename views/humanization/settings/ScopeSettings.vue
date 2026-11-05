<script setup>
import { computed, ref, watch } from 'vue';
import { mdiPlus, mdiDeleteOutline, mdiMagnify, mdiCheck } from '@mdi/js';
import PlatformIcon from '../shared/PlatformIcon.vue';
const props = defineProps({ schema:Object, model:Object, choices:Object });
const picker = ref(false), search = ref(''), kind = ref(''), manual = ref(''), error = ref(''), selected = ref([]);
const mode = computed(() => props.model.all_sessions ? 'blacklist' : 'whitelist');
const listKey = computed(() => props.model.all_sessions ? 'blacklist_sessions' : 'sessions');
const manualKey = computed(() => props.model.all_sessions ? 'blacklist_manual_sessions' : 'manual_sessions');
const defaultKey = computed(() => props.model.all_sessions ? 'blacklist_action' : 'outside_action');
const actions = [
  {value:'active',title:'正常',hint:'Recorder 记录并整理，Controller 规划、主模型回复'},
  {value:'ignore',title:'跳过',hint:'交由 AstrBot 原生处理'},
  {value:'listen',title:'监听',hint:'只记录聊天，不调用模型'},
  {value:'observe',title:'旁观',hint:'记录聊天、整理话题和日记，不回复'},
  {value:'drop',title:'丢弃',hint:'不记录，阻断普通消息处理'},
];
const options = computed(() => props.choices.sessions || []);
const names = computed(() => new Map(options.value.map(item => [item.value,item.title])));
const platforms = computed(() => new Map(options.value.map(item => [item.value,item])));
const listed = computed(() => [...new Set([
  ...props.model[listKey.value], ...props.model[manualKey.value],
  ...props.model.rules.filter(rule => rule.mode === mode.value).map(rule => rule.umo),
])]);
const candidates = computed(() => options.value.filter(item =>
  (!kind.value || item.value.includes(`:${kind.value}:`)) &&
  `${item.title} ${item.value}`.toLocaleLowerCase().includes((search.value || '').toLocaleLowerCase())
));
function label(umo) { return names.value.get(umo) || umo.split(':').slice(2).join(':'); }
function detail(umo) {
  const platform = platforms.value.get(umo);
  const adapter = platform?.adapter_name || platform?.adapter_type || '适配器未知';
  const status = platform?.supported === false ? ' · 当前插件不支持处理' : platform?.supported == null ? ' · 支持状态待确认' : '';
  return `${umo.split(':')[0]} · ${adapter} · ${umo.includes(':GroupMessage:') ? '群聊' : '私聊'} · ${umo.split(':').slice(2).join(':')}${status}`;
}
function action(umo) {
  return props.model.rules.find(rule => rule.mode === mode.value && rule.umo === umo)?.action
    || (props.model.all_sessions ? props.model.blacklist_action : 'active');
}
function setAction(umo, value) {
  const rule = props.model.rules.find(rule => rule.mode === mode.value && rule.umo === umo);
  if (rule) rule.action = value;
  else props.model.rules.push({__template_key:'session',mode:mode.value,umo,action:value});
}
function add(umos) {
  props.model[listKey.value] = [...new Set([...props.model[listKey.value], ...umos])];
  picker.value = false;
}
function addManual() {
  const umo = manual.value.trim();
  if (!/^[^:\s]+:(GroupMessage|FriendMessage):[^:\s]+$/.test(umo)) {
    error.value = '请输入有效 UMO，例如 QQ实例:GroupMessage:123456；可用 /sid 获取';
    return;
  }
  add([umo]); manual.value = ''; error.value = '';
}
function remove(umo) {
  props.model[listKey.value] = props.model[listKey.value].filter(value => value !== umo);
  props.model[manualKey.value] = props.model[manualKey.value].filter(value => value !== umo);
  props.model.rules = props.model.rules.filter(rule => rule.mode !== mode.value || rule.umo !== umo);
}
watch(picker, value => { if (value) { selected.value = []; search.value = ''; kind.value = ''; } });
watch(mode, () => { picker.value = false; });
</script>
<template>
  <v-switch v-model="model.enabled" label="监听会话" :hint="schema.enabled.hint" persistent-hint color="primary" inset class="mb-5" />
  <div class="text-subtitle-1 font-weight-bold mb-2">工作模式</div>
  <div class="d-flex ga-2 mb-4" role="group" aria-label="会话工作模式">
    <v-btn v-for="[value,title] in [[false,'白名单模式'],[true,'黑名单模式']]" :key="title" :color="model.all_sessions === value ? 'primary' : undefined" :aria-pressed="model.all_sessions === value" :prepend-icon="model.all_sessions === value ? mdiCheck : undefined" :disabled="!model.enabled" @click="model.all_sessions = value">{{ title }}</v-btn>
  </div>
  <v-card tag="section" :aria-label="model.all_sessions ? '会话黑名单' : '会话白名单'" rounded="lg">
    <v-card-title class="text-subtitle-1 font-weight-bold pa-4">{{ model.all_sessions ? '会话黑名单' : '会话白名单' }}</v-card-title>
    <v-card-text>
      <p class="text-body-2 text-medium-emphasis mb-4">{{ model.all_sessions ? '名单外正常工作；名单内可逐会话设置处理方式。' : '名单内默认正常工作；名单外使用下方默认方式。' }} 插件指令及其 LLM 请求始终不受会话策略限制。正常、旁观仍需开启 Recorder 并配置摘要模型才会整理日记。</p>
      <v-select v-model="model[defaultKey]" :items="actions.slice(1)" :label="model.all_sessions ? '名单内默认处理方式' : '范围外默认处理方式'" :aria-label="model.all_sessions ? '名单内默认处理方式' : '范围外默认处理方式'" :disabled="!model.enabled" :hint="actions.find(item => item.value === model[defaultKey])?.hint" persistent-hint class="mb-4" />
      <v-btn :prepend-icon="mdiPlus" :disabled="!model.enabled" class="mb-4" @click="picker = true">选择或添加会话</v-btn>
      <p v-if="!listed.length" class="text-body-2 text-medium-emphasis">尚未添加会话</p>
      <v-list v-else class="pa-0" aria-label="已添加会话">
        <v-list-item v-for="umo in listed" :key="umo" class="px-0 py-3 scope-entry">
          <template #prepend><PlatformIcon :src="platforms.get(umo)?.logo_url" :name="platforms.get(umo)?.adapter_name" class="mr-3" /></template>
          <div class="scope-entry-content">
            <div class="scope-entry-name">
              <div class="font-weight-medium text-truncate" :title="label(umo)">{{ label(umo) }}</div>
              <div class="text-caption text-medium-emphasis">{{ detail(umo) }}</div>
              <div class="text-caption text-medium-emphasis text-truncate" :title="umo">{{ umo }}</div>
            </div>
            <v-select :model-value="action(umo)" :aria-label="`${label(umo)}处理方式`" :items="actions" density="compact" hide-details :disabled="!model.enabled" @update:model-value="setAction(umo,$event)" />
            <v-btn :icon="mdiDeleteOutline" :aria-label="`移除${label(umo)}`" variant="text" size="small" color="error" :disabled="!model.enabled" @click="remove(umo)" />
          </div>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
  <v-dialog v-model="picker" max-width="760" scrollable>
    <v-card>
      <v-card-title class="text-h3 pa-4 pb-0 pl-6">选择或添加会话</v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">展示各适配器的已有会话；当前处理能力仍仅支持 OneBot（含 SnowLuma），其他平台会标明不支持。未知会话可用 /sid 获取 UMO 后手工添加。</p>
        <v-text-field v-model="search" label="搜索会话名称或 ID" :prepend-inner-icon="mdiMagnify" hide-details clearable @click:clear="search = ''" />
        <div class="d-flex ga-2 my-3" role="group" aria-label="会话类型">
          <v-btn v-for="[value,title] in [['','全部'],['GroupMessage','群聊'],['FriendMessage','私聊']]" :key="title" size="small" :color="kind === value ? 'primary' : undefined" :aria-pressed="kind === value" @click="kind = value">{{ title }}</v-btn>
        </div>
        <v-list max-height="320" class="overflow-y-auto" aria-label="可选会话">
          <v-list-item v-for="item in candidates" :key="item.value" :title="item.title" :subtitle="`${detail(item.value)} · ${item.value}`" :disabled="listed.includes(item.value)" @click="selected = selected.includes(item.value) ? selected.filter(value => value !== item.value) : [...selected,item.value]">
            <template #prepend><v-checkbox-btn :model-value="selected.includes(item.value) || listed.includes(item.value)" :aria-label="`选择${item.title}`" :disabled="listed.includes(item.value)" @click.stop @update:model-value="value => selected = value ? [...selected,item.value] : selected.filter(umo => umo !== item.value)" /><PlatformIcon :src="item.logo_url" :name="item.adapter_name" class="mx-3" /></template>
          </v-list-item>
          <p v-if="!candidates.length" class="text-body-2 pa-3">没有匹配的已有会话，可在下方补充 UMO</p>
        </v-list>
        <v-divider class="my-4" />
        <v-text-field v-model="manual" label="补充未知会话 UMO" placeholder="QQ实例:GroupMessage:123456" :error-messages="error" @keydown.enter.prevent="addManual" />
        <v-btn :disabled="!manual.trim()" @click="addManual">添加 UMO</v-btn>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn variant="text" @click="picker = false">取消</v-btn><v-btn color="primary" :disabled="!selected.length" @click="add(selected)">添加所选（{{ selected.length }}）</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
<style scoped>
.scope-entry-content { display:grid; grid-template-columns:minmax(0,1fr) 130px auto; gap:12px; align-items:center; }
.scope-entry-name { min-width:0; }
.scope-entry + .scope-entry { border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity)); }
@media (max-width:600px) { .scope-entry-content { grid-template-columns:minmax(0,1fr) auto; } .scope-entry-name { grid-column:1 / -1; } }
</style>

<script setup>
import { ref, watch } from 'vue';
import { mdiMagnify, mdiChevronLeft, mdiFilterRemoveOutline } from '@mdi/js';
import { emotions, outcomes } from './options.js';
import { sessionLabel } from '../shared/session.js';
const props = defineProps({ category:String, model:Object, sessions:Array, active:Boolean });
const sessionMenu = ref(false);
watch(() => props.active, active => { if (!active) sessionMenu.value = false; });
defineEmits(['collapse','reset']);
const all = {title:'全部',value:''};
const components = [['text','文字'],['at','@ 提及'],['image','图片'],['video','视频'],['record','语音'],['file','文件'],['poke','戳一戳']].map(([value,title])=>({value,title}));
const sorts = [['timestamp:desc','时间：从新到旧'],['timestamp:asc','时间：从旧到新'],['headline:asc','内容：正序'],['headline:desc','内容：倒序']].map(([value,title])=>({value,title}));
function toggle(key,value) {
  props.model[key] = props.model[key] === value ? '' : value;
}
function matchSession(value, query, item) {
  const search = query.toLocaleLowerCase();
  return `${sessionLabel(item.raw.umo,item.raw.title)} ${item.raw.umo}`.toLocaleLowerCase().includes(search);
}
</script>
<template>
  <v-card tag="aside" aria-label="数据筛选" class="filter-panel" :border="false" rounded="xl">
    <div class="d-flex align-center ga-1 mb-4">
      <span class="text-subtitle-1 font-weight-bold flex-grow-1">筛选</span>
      <v-btn :icon="mdiFilterRemoveOutline" aria-label="重置筛选" size="small" variant="text" @click="$emit('reset')" />
      <v-btn :icon="mdiChevronLeft" aria-label="折叠筛选栏" size="small" variant="text" @click="$emit('collapse')" />
    </div>
    <v-text-field v-model="model.q" label="搜索关键词" placeholder="搜索聊天、话题或记录" :prepend-inner-icon="mdiMagnify" clearable hide-details @click:clear="model.q = ''" />
    <v-divider class="my-5" />
    <v-autocomplete v-model="model.sessions" v-model:menu="sessionMenu" class="session-select" label="会话" placeholder="搜索名称或 UMO，多选" :items="sessions" item-title="title" :custom-filter="matchSession" :menu-props="{maxWidth:520}" density="compact" multiple chips closable-chips hide-details>
      <template #chip="{props,item}"><v-chip v-bind="props" class="text-truncate" max-width="100%" :title="item.raw.umo">{{ item.raw.title }}</v-chip></template>
      <template #item="{props,item}">
        <v-list-item v-bind="props" role="option" :title="sessionLabel(item.raw.umo,item.raw.title)" :subtitle="item.raw.umo">
          <template #prepend="{isSelected}"><v-checkbox-btn :model-value="isSelected" :ripple="false" tabindex="-1" /></template>
        </v-list-item>
      </template>
    </v-autocomplete>
    <p v-if="!sessions.length" class="text-caption text-medium-emphasis mt-2">尚无已启用的会话</p>
    <p class="filter-label mt-5">对话类型</p>
    <div class="type-options">
      <button v-for="[value,title] in [['group','群聊'],['private','私聊']]" :key="value" type="button" class="type-option" :class="{'type-option--selected':model.chat_type === value}" :aria-pressed="model.chat_type === value" @click="toggle('chat_type',value)">{{ title }}</button>
    </div>
    <v-divider class="my-5" />
    <template v-if="category === 'messages'">
      <p class="filter-label">消息方向</p>
      <div class="type-options mb-4">
        <button v-for="[value,title] in [['in','收到消息'],['out','发出回复']]" :key="value" type="button" class="type-option" :class="{'type-option--selected':model.kind === value}" :aria-pressed="model.kind === value" @click="toggle('kind',value)">{{ title }}</button>
      </div>
      <v-text-field v-model="model.sender" label="发送者昵称或 ID" hide-details class="mb-4" />
      <v-select v-model="model.component" label="消息内容类型" :items="[all,...components]" hide-details />
    </template>
    <template v-else-if="category === 'decisions'">
      <p class="filter-label">回复决定</p>
      <div class="type-options mb-4">
        <button v-for="[value,title] in [['1','回复'],['0','观望']]" :key="value" type="button" class="type-option" :class="{'type-option--selected':model.reply === value}" :aria-pressed="model.reply === value" @click="toggle('reply',value)">{{ title }}</button>
      </div>
      <v-select v-model="model.kind" label="执行状态" :items="[all,...outcomes]" hide-details class="mb-4" />
      <v-select v-model="model.emotion" label="规划情绪" :items="[all,...emotions]" hide-details class="mb-4" />
      <v-select v-model="model.trigger" label="触发来源" :items="[all,{title:'聊天消息',value:'message'},{title:'空闲主动',value:'idle'}]" hide-details class="mb-4" />
      <v-select v-model="model.required" label="是否必回复" :items="[all,{title:'必回复',value:'1'},{title:'普通评估',value:'0'}]" hide-details />
    </template>
    <template v-else-if="category === 'topics'">
      <v-text-field v-model="model.participant" label="参与者或参与行为" hide-details class="mb-4" />
      <v-text-field v-model="model.bot_reply" label="我的行为关键词" hide-details />
    </template>
    <template v-else>
      <v-select v-model="model.kind" label="日记状态" :items="[all,{title:'未封存',value:'0'},{title:'已封存',value:'1'}]" hide-details class="mb-4" />
      <v-select v-model="model.coverage_gap" label="消息覆盖" :items="[all,{title:'无缺口标记',value:'0'},{title:'存在缺口',value:'1'}]" hide-details />
    </template>
    <v-divider class="my-5" />
    <v-text-field v-model="model.start" type="date" label="开始日期" hide-details class="mb-4" />
    <v-text-field v-model="model.end" type="date" label="结束日期" hide-details class="mb-4" />
    <v-select v-model="model.sort" label="排序" :items="sorts" hide-details />
  </v-card>
</template>
<style scoped>
/* Reuse the current conversation workspace's filter surface and spacing. */
.filter-panel { background: #f5f6f7; padding: 18px; min-width: 0; }
.filter-panel.v-theme--dark { background: rgba(var(--v-theme-on-surface), 0.06); }
.type-options { display: grid; gap: 7px; grid-template-columns: 1fr 1fr; }
.type-option { align-items: center; background: rgb(var(--v-theme-surface)); border: 0; border-radius: 9px; color: rgba(var(--v-theme-on-surface), 0.7); cursor: pointer; display: flex; font-size: 0.76rem; gap: 5px; height: 34px; justify-content: center; }
.type-option:hover { color: rgb(var(--v-theme-on-surface)); }
.type-option--selected { background: rgba(var(--v-theme-primary), 0.11); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.type-option:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); }
.filter-label { color: rgba(var(--v-theme-on-surface), 0.76); font-size: 0.75rem; font-weight: 600; margin-bottom: 8px; }
/* Grow only for selected chips, with a bounded scroll area for many sessions. */
.session-select :deep(.v-field__input) { max-height: 80px; overflow-y: auto; align-content: flex-start; }
</style>

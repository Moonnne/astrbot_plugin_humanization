<script setup>
import { ref, inject, watch } from 'vue';
import { mdiFileDocumentOutline, mdiFileCompare, mdiRestore } from '@mdi/js';
import ResourceSelector from '../shared/ResourceSelector.vue';
const props = defineProps({ model:Object, schema:Object, defaults:Object, personas:Array });
const bridge = inject('bridge');
const names = [['behavior','行为规划'],['expression','表达风格'],['group','群聊'],['private','私聊']];
const viewer = ref(null), lines = ref([]), loading = ref(false), error = ref('');
const drafts = ref({});
// Keep displayed defaults separate from the empty values saved in configuration.
watch(() => props.model, model => {
  drafts.value = Object.fromEntries(names.map(([name]) => [name,model[name].trim() ? model[name] : props.defaults[name]]));
}, {immediate:true});
// Same character weights as AstrBot EstimateTokenCounter; this is not billing usage.
function statistics(text) {
  const chars = Array.from(text), chinese = chars.filter(c => /[\u4e00-\u9fff]/u.test(c)).length;
  const emoji = chars.filter(c => /[\u200d\u2600-\u27bf\ufe00-\ufe0f\u{1f000}-\u{1faff}]/u.test(c)).length;
  return `${chars.length} 字 · 估算 ${Math.trunc(chinese * 0.6 + emoji * 2 + (chars.length - chinese - emoji) * 0.3)} Token`;
}
function reset(name) { drafts.value[name] = props.defaults[name]; props.model[name] = ''; props.model[`${name}_persona`] = ''; }
async function view(name, mode) {
  viewer.value = {name,mode}; lines.value = []; error.value = '';
  if (mode !== 'diff') return;
  loading.value = true;
  try { lines.value = (await bridge.apiPost('prompts/diff',{name,text:props.model[name]})).lines; }
  catch (e) { error.value = e.message; }
  finally { loading.value = false; }
}
function lineClass(line) {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) return 'diff-header';
  return line.startsWith('+') ? 'diff-add' : line.startsWith('-') ? 'diff-remove' : '';
}
</script>
<template>
  <p class="text-body-2 text-medium-emphasis mb-5">主人格仍由 AstrBot 管理。以下四层分别控制规划、表达和聊天场景；选择人格时优先使用其正文，未选择人格且文本留空时自动读取内置默认 TXT。</p>
  <div class="prompt-grid">
    <v-card v-for="[name,title] in names" :key="name" tag="section" :aria-label="`${title}提示词`" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5">{{ title }}</v-card-title>
      <v-card-text>
        <ResourceSelector v-model="model[`${name}_persona`]" kind="select_persona" :label="schema[`${name}_persona`].description" :items="personas" />
        <p class="text-caption text-medium-emphasis my-3">当前来源：{{ model[`${name}_persona`] ? '已选人格正文（下方文本暂不生效）' : model[name].trim() ? '自定义文本' : '内置默认 TXT' }}</p>
        <v-textarea v-model="drafts[name]" :label="schema[name].description" auto-grow rows="8" max-rows="18" hide-details @update:model-value="model[name] = $event" @blur="!drafts[name].trim() && (drafts[name] = defaults[name], model[name] = '')" />
        <p class="text-caption text-medium-emphasis mt-1" :aria-label="`${title}字数和Token估算`">{{ statistics(drafts[name]) }}</p>
        <div class="d-flex flex-wrap ga-2 mt-4">
          <v-btn size="small" :prepend-icon="mdiFileDocumentOutline" @click="view(name,'default')">查看默认</v-btn>
          <v-btn size="small" :prepend-icon="mdiFileCompare" @click="view(name,'diff')">查看差异</v-btn>
          <v-btn size="small" variant="text" :prepend-icon="mdiRestore" @click="reset(name)">使用默认</v-btn>
        </div>
      </v-card-text>
    </v-card>
  </div>
  <p class="text-caption text-medium-emphasis mt-4">Token 使用 AstrBot 的字符权重估算，不调用模型，不代表提供商实际计费。未自定义时直接显示默认正文，可在输入框中修改；点击“使用默认”后保存即可恢复，单纯浏览不会将默认内容写回配置。</p>
  <v-dialog :model-value="!!viewer" max-width="1000" scrollable @update:model-value="!$event && (viewer = null)">
    <v-card>
      <v-card-title class="text-h6 pa-5">{{ viewer?.mode === 'diff' ? '与默认提示词的差异' : '内置默认提示词' }} · {{ names.find(item => item[0] === viewer?.name)?.[1] }}</v-card-title>
      <v-card-text>
        <v-progress-linear v-if="loading" indeterminate color="primary" />
        <v-alert v-if="error" type="error" variant="tonal">{{ error }}</v-alert>
        <template v-if="viewer?.mode === 'diff'">
          <p v-if="!loading && !error && !lines.length" class="text-medium-emphasis">与默认内容相同；空白文本会自动使用默认提示词。</p>
          <pre v-else class="prompt-text diff"><span v-for="(line,index) in lines" :key="index" :class="lineClass(line)">{{ line }}</span></pre>
        </template>
        <pre v-else-if="viewer" class="prompt-text">{{ defaults[viewer.name] }}</pre>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn v-if="viewer?.mode === 'default'" color="primary" @click="drafts[viewer.name] = defaults[viewer.name]; model[viewer.name] = defaults[viewer.name]; viewer = null">复制到输入框</v-btn><v-btn @click="viewer = null">关闭</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
<style scoped>
.prompt-grid { display: grid; gap: 20px; grid-template-columns: repeat(2,minmax(0,1fr)); align-items: start; }
.prompt-text { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.7; }
.diff { font-family: ui-monospace, monospace; font-size: 0.85rem; }
.diff > span { display: block; }
.diff-add { background: rgba(var(--v-theme-success),0.12); color: rgb(var(--v-theme-success)); }
.diff-remove { background: rgba(var(--v-theme-error),0.12); color: rgb(var(--v-theme-error)); }
.diff-header { color: rgb(var(--v-theme-primary)); }
@media (max-width: 1100px) { .prompt-grid { grid-template-columns: minmax(0,1fr); } }
</style>

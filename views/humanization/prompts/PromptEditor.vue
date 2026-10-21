<script setup>
import { ref, watch } from 'vue';
import { mdiFileCompare, mdiRestore } from '@mdi/js';
import ResourceSelector from '../shared/ResourceSelector.vue';
import PromptCompare from './PromptCompare.vue';
import { statistics } from './metrics.js';
const props = defineProps({ model:Object, schema:Object, defaults:Object, personas:Array });
const names = [['behavior','行为规划'],['expression','表达风格'],['group','群聊'],['private','私聊']];
const viewer = ref(null);
const drafts = ref({});
// Keep displayed defaults separate from the empty values saved in configuration.
watch(() => props.model, model => {
  drafts.value = Object.fromEntries(names.map(([name]) => [name,model[name].trim() ? model[name] : props.defaults[name]]));
}, {immediate:true});
function reset(name) { drafts.value[name] = props.defaults[name]; props.model[name] = ''; props.model[`${name}_persona`] = ''; }
</script>
<template>
  <p class="text-body-2 text-medium-emphasis mb-5">主人格仍由 AstrBot 管理。以下四层分别控制规划、表达和聊天场景；选择人格时优先使用其正文，未选择人格且文本留空时自动读取内置默认 TXT。</p>
  <div class="prompt-grid">
    <v-card v-for="[name,title] in names" :key="name" tag="section" :aria-label="`${title}提示词`" class="prompt-card" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5">{{ title }}</v-card-title>
      <v-card-text class="prompt-body">
        <ResourceSelector v-model="model[`${name}_persona`]" kind="select_persona" :label="schema[`${name}_persona`].description" :items="personas" />
        <p class="text-caption text-medium-emphasis text-truncate my-3">当前来源：{{ model[`${name}_persona`] ? '已选人格正文（下方文本暂不生效）' : model[name].trim() ? '自定义文本' : '内置默认 TXT' }}</p>
        <v-textarea v-model="drafts[name]" :label="schema[name].description" rows="12" no-resize hide-details @update:model-value="model[name] = $event" @blur="!drafts[name].trim() && (drafts[name] = defaults[name], model[name] = '')" />
        <p class="text-caption text-medium-emphasis mt-1" :aria-label="`${title}字数和Tokens估计`">{{ statistics(drafts[name]) }}</p>
        <div class="d-flex flex-wrap ga-2 prompt-actions">
          <v-btn size="small" :prepend-icon="mdiFileCompare" @click="viewer = name">对比默认</v-btn>
          <v-btn size="small" variant="text" :prepend-icon="mdiRestore" @click="reset(name)">使用默认</v-btn>
        </div>
      </v-card-text>
    </v-card>
  </div>
  <p class="text-caption text-medium-emphasis mt-4">Tokens 使用 AstrBot 的字符权重估计，不调用模型，不代表提供商实际计费。未自定义时直接显示默认正文，可在输入框中修改；点击“使用默认”后保存即可恢复，单纯浏览不会将默认内容写回配置。</p>
  <v-dialog :model-value="!!viewer" max-width="1440" scrollable @update:model-value="!$event && (viewer = null)">
    <PromptCompare v-if="viewer" :name="viewer" :title="names.find(item => item[0] === viewer)[1]" :text="drafts[viewer]" :original="defaults[viewer]" @update:text="drafts[viewer] = $event; model[viewer] = $event" @copy="drafts[viewer] = defaults[viewer]; model[viewer] = defaults[viewer]" @close="viewer = null" />
  </v-dialog>
</template>
<style scoped>
.prompt-grid { display: grid; gap: 20px; grid-template-columns: repeat(2,minmax(0,1fr)); align-items: stretch; }
.prompt-card, .prompt-body { display: flex; flex-direction: column; min-width: 0; }
.prompt-body { flex: 1; }
.prompt-body :deep(.resource-field) { min-height: 48px; }
.prompt-actions { margin-top: auto; padding-top: 16px; }
@media (max-width: 1100px) { .prompt-grid { grid-template-columns: minmax(0,1fr); } }
</style>

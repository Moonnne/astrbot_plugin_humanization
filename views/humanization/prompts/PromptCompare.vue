<script setup>
import { ref, watch, inject, onBeforeUnmount } from 'vue';
import { mdiFileCompare, mdiClose } from '@mdi/js';
import { statistics } from './metrics.js';
const props = defineProps({ name:String, title:String, text:String, original:String });
const emit = defineEmits(['update:text','copy','close']);
const bridge = inject('bridge');
const showDiff = ref(false), rows = ref([]), loading = ref(false), error = ref(''), identical = ref(false);
let generation = 0;
watch([showDiff,() => props.text], async ([enabled,text]) => {
  const current = ++generation;
  error.value = ''; loading.value = false;
  if (!enabled) return;
  loading.value = true;
  try {
    const result = await bridge.apiPost('prompts/diff',{name:props.name,text});
    if (current === generation) { rows.value = result.rows; identical.value = result.identical; }
  } catch (e) { if (current === generation) error.value = e.message; }
  finally { if (current === generation) loading.value = false; }
});
onBeforeUnmount(() => generation++);
</script>
<template>
  <v-card class="compare-card">
    <v-card-title class="text-h6 pa-4 pl-6 d-flex align-center flex-wrap ga-3">
      <span class="flex-grow-1 text-wrap">对比默认提示词 · {{ title }}</span>
      <v-btn size="small" :prepend-icon="mdiFileCompare" :aria-pressed="showDiff" :color="showDiff ? 'primary' : undefined" @click="showDiff = !showDiff">{{ showDiff ? '返回编辑' : '显示差异' }}</v-btn>
      <v-btn :icon="mdiClose" aria-label="关闭提示词对比" variant="text" size="small" @click="emit('close')" />
    </v-card-title>
    <v-card-text class="compare-body">
      <div class="compare-columns compare-labels mb-3"><h3 class="text-subtitle-1">自定义提示词</h3><h3 class="text-subtitle-1">系统默认提示词（只读）</h3></div>
      <template v-if="showDiff">
        <v-progress-linear v-if="loading" indeterminate color="primary" />
        <v-alert v-if="error" type="error" variant="tonal" class="mb-3">{{ error }}</v-alert>
        <p v-if="!loading && !error && identical" class="text-body-2 text-medium-emphasis mb-3">与默认内容相同。</p>
        <div v-if="!loading && !error" class="diff-scroll" role="region" aria-label="提示词差异对比" tabindex="0">
          <div v-for="(row,index) in rows" :key="index" class="compare-columns diff-row">
            <div v-for="side in ['left','right']" :key="side" class="diff-cell" :class="{'diff-empty':!row[side], 'diff-add':side === 'left' && row.kind !== 'equal' && row.left, 'diff-remove':side === 'right' && row.kind !== 'equal' && row.right}">
              <span class="diff-number">{{ row[side]?.number }}</span>
              <span class="diff-sign">{{ row.kind === 'equal' || !row[side] ? ' ' : side === 'left' ? '+' : '−' }}</span>
              <code><span v-for="(part,partIndex) in row[side]?.segments" :key="partIndex" :class="{'diff-change':part.changed}">{{ part.text }}</span></code>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="compare-columns">
        <v-textarea :model-value="text" label="自定义提示词正文" rows="16" no-resize hide-details @update:model-value="emit('update:text',$event)" />
        <v-textarea :model-value="original" label="系统默认提示词正文" rows="16" no-resize readonly hide-details />
      </div>
      <div class="compare-columns mt-2 text-caption text-medium-emphasis">
        <p aria-label="自定义提示词字数和Tokens估计">{{ statistics(text) }}</p>
        <p aria-label="默认提示词字数和Tokens估计">{{ statistics(original) }}</p>
      </div>
    </v-card-text>
    <v-card-actions><v-spacer /><v-btn color="primary" @click="showDiff = false; emit('copy')">复制默认到输入框</v-btn><v-btn @click="emit('close')">关闭</v-btn></v-card-actions>
  </v-card>
</template>
<style scoped>
.compare-body { overflow: auto; }
.compare-columns { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 20px; min-width: 560px; }
.compare-labels { position: sticky; left: 0; }
.diff-scroll { max-height: 58vh; overflow: auto; border: 1px solid rgba(var(--v-theme-on-surface),0.12); border-radius: 8px; }
.diff-row { gap: 0; align-items: stretch; }
.diff-cell { display: flex; min-width: 0; min-height: 1.65em; padding-block: 3px; font: 0.8125rem/1.65 ui-monospace, monospace; }
.diff-cell + .diff-cell { border-left: 1px solid rgba(var(--v-theme-on-surface),0.12); }
.diff-cell code { white-space: pre-wrap; overflow-wrap: anywhere; flex: 1; padding-inline-end: 10px; }
.diff-number { width: 40px; flex-shrink: 0; text-align: end; color: rgba(var(--v-theme-on-surface),0.45); user-select: none; }
.diff-sign { width: 24px; flex-shrink: 0; text-align: center; user-select: none; opacity: 0.6; }
.diff-add { background: rgba(88,140,103,0.10); }
.diff-remove { background: rgba(177,110,110,0.10); }
.diff-add .diff-change { background: rgba(88,140,103,0.14); }
.diff-remove .diff-change { background: rgba(177,110,110,0.14); }
.diff-empty { background: rgba(var(--v-theme-on-surface),0.035); }
</style>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount, watch } from 'vue';
import { mdiContentSaveOutline, mdiRefresh, mdiAlertCircleOutline, mdiDeleteAlertOutline, mdiChevronLeft, mdiMenu, mdiViewColumnOutline, mdiViewStreamOutline, mdiAccountGroupOutline, mdiEyeOutline, mdiHeadCogOutline, mdiMessageTextOutline, mdiShieldAccountOutline, mdiTextBoxOutline } from '@mdi/js';
import SchemaFields from './SchemaFields.vue';
import PromptEditor from '../prompts/PromptEditor.vue';
const props = defineProps({ promptsOnly:Boolean });
const bridge = inject('bridge');
const emit = defineEmits(['changed']);
const data = ref(null), model = ref(null), baseline = ref('');
const loading = ref(false), saving = ref(false), confirm = ref(false), error = ref(''), success = ref('');
const dirty = computed(() => model.value && JSON.stringify(model.value) !== baseline.value);
const resetDialog = ref(false), confirmation = ref(''), resetting = ref(false), resetError = ref('');
const busy = computed(() => saving.value || resetting.value);
const content = ref(null), navOpen = ref(true), manualSingle = ref(false), contentWidth = ref(0), active = ref('scope');
const sections = computed(() => Object.entries(data.value?.schema || {}).filter(([key]) => key !== 'prompts'));
const canDouble = computed(() => contentWidth.value >= 1000);
const double = computed(() => canDouble.value && !manualSingle.value);
const navTitles = {scope:'会话范围',recorder:'聊天感知',controller:'行为规划',proactive:'主动发言',management:'管理指令',logging:'日志设置',danger:'危险操作'};
const navIcons = {scope:mdiAccountGroupOutline,recorder:mdiEyeOutline,controller:mdiHeadCogOutline,proactive:mdiMessageTextOutline,management:mdiShieldAccountOutline,logging:mdiTextBoxOutline,danger:mdiDeleteAlertOutline};
let scrollFrame = 0, preferredSection = '';
const observer = new ResizeObserver(entries => { contentWidth.value = entries[0].contentRect.width; trackSection(); });
watch(content, element => { observer.disconnect(); if (element) { observer.observe(element); trackSection(); } });
watch(double, trackSection, {flush:'post'});
function trackSection() {
  if (scrollFrame) return;
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = 0;
    if (!content.value) return;
    const blocks = Array.from(content.value.querySelectorAll('section[id^="setting-"]')).map(element => ({key:element.id.slice(8),top:element.getBoundingClientRect().top}));
    if (!blocks.length) return;
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
      active.value = blocks.at(-1).key;
      return;
    }
    const passed = blocks.filter(block => block.top <= 80);
    const rowTop = passed.length ? Math.max(...passed.map(block => block.top)) : blocks[0].top;
    const row = blocks.filter(block => Math.abs(block.top - rowTop) < 2);
    // Cards on the same grid row share a scroll position; keep the clicked section.
    active.value = (row.find(block => block.key === preferredSection) || row.find(block => block.key === active.value) || row[0]).key;
  });
}
onBeforeUnmount(() => {
  observer.disconnect();
  cancelAnimationFrame(scrollFrame);
  window.removeEventListener('scroll', trackSection);
  window.removeEventListener('resize', trackSection);
});
function jump(key) {
  active.value = key; preferredSection = key;
  content.value.querySelector(`#setting-${key}`)?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',block:'start'});
  trackSection();
}
async function load() {
  loading.value = true; error.value = '';
  try {
    data.value = await bridge.apiGet('settings');
    model.value = JSON.parse(JSON.stringify(data.value.config));
    baseline.value = JSON.stringify(model.value);
  } catch (e) { error.value = e.message; }
  finally { loading.value = false; }
}
async function save() {
  saving.value = true; error.value = '';
  try {
    await bridge.apiPost('settings/save', {config:JSON.parse(JSON.stringify(model.value)), revision:data.value.revision});
    success.value = '配置已保存，插件已重载';
    await load();
    return true;
  } catch (e) { error.value = e.message; return false; }
  finally { saving.value = false; confirm.value = false; }
}
async function resetAll() {
  resetting.value = true; resetError.value = ''; success.value = '';
  try {
    const result = await bridge.apiPost('data/reset-all', {confirmation:confirmation.value});
    resetDialog.value = false; confirmation.value = '';
    success.value = `已清除 ${result.conversations} 个会话的数据，并为主模型开启空白对话`;
    emit('changed');
  } catch (e) { resetError.value = e.message; }
  finally { resetting.value = false; }
}
onMounted(() => {
  window.addEventListener('scroll', trackSection, {passive:true});
  window.addEventListener('resize', trackSection, {passive:true});
  load();
});
defineExpose({dirty,saving:busy,save});
</script>
<template>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
  <v-alert v-if="success" type="success" variant="tonal" class="mb-4">{{ success }}</v-alert>
  <v-alert type="info" variant="tonal" class="mb-4">配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。</v-alert>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <span class="text-body-2 flex-grow-1">{{ dirty ? '有未保存的修改' : '配置已同步' }}</span>
    <v-btn :prepend-icon="mdiRefresh" :loading="loading" :disabled="busy || !!dirty" @click="load">重新载入</v-btn>
    <v-btn color="primary" :prepend-icon="mdiContentSaveOutline" :disabled="!dirty || loading || resetting" :loading="saving" @click="confirm = true">保存并重载</v-btn>
  </div>
  <v-progress-linear v-if="loading" indeterminate color="primary" />
  <template v-if="data && model">
    <PromptEditor v-if="promptsOnly" :model="model.prompts" :schema="data.schema.prompts.items" :defaults="data.prompt_defaults" :personas="data.choices.select_persona" />
    <div v-else class="settings-layout">
      <aside class="settings-nav" :class="{'settings-nav--closed':!navOpen}" aria-label="设置快速导航">
        <v-btn :icon="navOpen ? mdiChevronLeft : mdiMenu" :aria-label="navOpen ? '收起设置导航' : '展开设置导航'" variant="text" size="small" @click="navOpen = !navOpen" />
        <nav v-show="navOpen" class="mt-2" aria-label="设置分区">
          <v-list nav bg-color="transparent" density="compact" class="pa-0">
            <v-list-item v-for="[key,section] in sections" :key="key" tag="button" type="button" role="button" class="settings-nav-item" :active="active === key" :prepend-icon="navIcons[key]" :title="navTitles[key] || section.description" :aria-current="active === key ? 'location' : undefined" @click="jump(key)" />
            <v-list-item tag="button" type="button" role="button" class="settings-nav-item settings-nav-danger" :active="active === 'danger'" :prepend-icon="navIcons.danger" title="危险操作" :aria-current="active === 'danger' ? 'location' : undefined" @click="jump('danger')" />
          </v-list>
        </nav>
      </aside>
      <div ref="content" class="settings-content">
        <div class="d-flex align-center justify-end ga-3 mb-3">
          <span v-if="!canDouble" class="text-caption text-medium-emphasis">当前宽度自动使用单列</span>
          <v-btn size="small" :prepend-icon="double ? mdiViewStreamOutline : mdiViewColumnOutline" :disabled="!canDouble" @click="manualSingle = !manualSingle">{{ double ? '切换为单列' : '切换为双列' }}</v-btn>
        </div>
        <div class="settings-grid" :class="{'settings-grid--double':double}">
    <v-card v-for="[key,section] in sections" :key="key" :id="`setting-${key}`" tag="section" :aria-label="section.description" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5 text-wrap">{{ section.description }}</v-card-title>
      <v-card-text><SchemaFields :schema="section.items" :model="model[key]" :choices="data.choices" /></v-card-text>
    </v-card>
        </div>
    <v-card id="setting-danger" tag="section" aria-label="危险操作区" color="error" variant="outlined" class="my-6" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5 d-flex align-center ga-2"><v-icon :icon="mdiDeleteAlertOutline" />危险操作区</v-card-title>
      <v-card-text>
        <p class="mb-4">清除全部 Humanization 会话的聊天记录、话题、日记、最近反应、辅助模型进度与计数，并为对应主模型开启空白对话。包含当前未启用的历史会话，删除后无法撤销。</p>
        <v-btn color="error" variant="flat" :prepend-icon="mdiDeleteAlertOutline" :disabled="busy || loading" @click="confirmation = ''; resetError = ''; resetDialog = true">清除所有会话数据</v-btn>
      </v-card-text>
    </v-card>
      </div>
    </div>
  </template>
  <v-dialog v-model="confirm" max-width="540" :persistent="saving">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">保存配置</v-card-title>
      <v-card-text>
        保存后将重载 Humanization，进行中的回复可能中断。
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="saving" @click="confirm = false">取消</v-btn><v-btn color="primary" :loading="saving" @click="save">确认保存</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog v-model="resetDialog" max-width="600" :persistent="resetting">
    <v-card>
      <v-card-title class="text-h6 pa-4 pb-0 pl-6 text-error">清除所有会话数据</v-card-title>
      <v-card-text>
        <v-alert type="error" variant="tonal" class="mb-4">此操作会立即执行，无法撤销。正在生成的回复和日记整理会中断。AstrBot 原生旧对话与日志文件保留。</v-alert>
        <p class="mb-4">请输入 <strong>{{ data?.reset_confirmation }}</strong> 确认清除；不会保存当前未提交的设置。</p>
        <v-text-field v-model="confirmation" label="确认信息" autocomplete="off" :disabled="resetting" hide-details />
        <v-alert v-if="resetError" type="error" variant="tonal" class="mt-4">{{ resetError }}</v-alert>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn variant="text" :disabled="resetting" @click="resetDialog = false">取消</v-btn><v-btn color="error" variant="tonal" :loading="resetting" :disabled="confirmation !== data?.reset_confirmation" @click="resetAll">确认清除</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  <v-snackbar :model-value="!!dirty" :timeout="-1" location="bottom left" color="surface" rounded="pill">
    <v-icon :icon="mdiAlertCircleOutline" size="20" class="mr-2" />Humanization {{ promptsOnly ? '提示词' : '配置' }}尚未保存，请点击“保存并重载”。
  </v-snackbar>
</template>
<style scoped>
.settings-layout { display: flex; align-items: flex-start; gap: 16px; min-width: 0; }
.settings-nav { flex: 0 0 auto; width: 144px; position: sticky; top: 12px; max-height: calc(100vh - 24px); overflow-y: auto; transition: width 180ms ease; }
.settings-nav--closed { width: 36px; }
/* Match the host's VerticalSidebar navigation, including its primary active fill. */
.settings-nav-item { width: 100%; min-height: 36px; margin-bottom: 2px; padding-inline: 10px; border-radius: 8px; text-align: start; color: rgba(var(--v-theme-on-surface),0.76); }
.settings-nav-item:hover { background: rgba(var(--v-theme-on-surface),0.05); color: rgb(var(--v-theme-on-surface)); }
.settings-nav-item.v-list-item--active { background: rgba(var(--v-theme-primary),0.08); color: rgb(var(--v-theme-primary)); }
.settings-nav-item :deep(.v-list-item__prepend) { margin-inline-end: 10px; }
.settings-nav-item :deep(.v-list-item__spacer) { width: 0; }
.settings-nav-item :deep(.v-icon) { font-size: 20px; }
.settings-nav-item :deep(.v-list-item-title) { font-size: 0.8125rem; }
.settings-nav-danger { color: rgb(var(--v-theme-error)); }
.settings-content { flex: 1 1 0; min-width: 0; }
.settings-grid { display: grid; grid-template-columns: minmax(0,1fr); align-items: start; gap: 20px; }
.settings-grid--double { grid-template-columns: repeat(2,minmax(0,1fr)); }
.settings-content :deep(section) { scroll-margin-top: 16px; min-width: 0; }
@media (max-width: 700px) { .settings-layout { gap: 8px; } .settings-nav { width: 96px; } .settings-nav--closed { width: 36px; } .settings-nav-item :deep(.v-list-item__prepend) { display: none; } }
@media (prefers-reduced-motion: reduce) { .settings-nav { transition: none; } }
</style>

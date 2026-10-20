<script setup>
import { ref, inject, onMounted, watch } from 'vue';
import { mdiChartBar, mdiMessageTextOutline, mdiHeartOutline, mdiForumOutline, mdiBookOpenPageVariantOutline, mdiCogOutline, mdiRefresh, mdiClose } from '@mdi/js';
import Overview from './overview/Overview.vue';
import Records from './data/Records.vue';
import Settings from './settings/Settings.vue';

const bridge = inject('bridge');
const tab = ref('overview');
const settings = ref(null);
const pendingTab = ref(null);
const switching = ref(false);
const scope = ref('');
const overview = ref({ stats: {}, sessions: [], timezone: 'Asia/Shanghai' });
const error = ref('');
const loading = ref(false);
const refresh = ref(0);
let generation = 0;
const tabs = [
  ['overview', '统计', mdiChartBar], ['messages', '聊天', mdiMessageTextOutline],
  ['decisions', '最近反应', mdiHeartOutline], ['topics', '话题', mdiForumOutline],
  ['diaries', '日记', mdiBookOpenPageVariantOutline], ['settings', '设置', mdiCogOutline],
];
async function load() {
  const current = ++generation;
  loading.value = true;
  error.value = '';
  try {
    const data = await bridge.apiGet('overview', { scope: scope.value });
    if (current === generation) overview.value = data;
  } catch (e) { if (current === generation) error.value = e.message; }
  finally { if (current === generation) loading.value = false; }
}
function reload() { refresh.value++; load(); }
function navigate(value) {
  if (value === tab.value || switching.value || settings.value?.saving) return;
  if (tab.value === 'settings' && settings.value?.dirty) pendingTab.value = value;
  else tab.value = value;
}
async function leaveSettings(save) {
  switching.value = true;
  try {
    if (!save || await settings.value.save()) tab.value = pendingTab.value;
  } finally { pendingTab.value = null; switching.value = false; }
}
watch(scope, load);
onMounted(load);
</script>

<template>
  <v-app>
    <v-main>
      <v-container fluid class="pa-4 pa-md-6">
        <div class="d-flex align-center flex-wrap ga-3 mb-4">
          <div class="flex-grow-1">
            <h1 class="text-h5 font-weight-bold">Humanization</h1>
            <p class="text-body-2 text-medium-emphasis mt-1">聊天感知、行为规划与话题日记</p>
          </div>
          <v-btn :prepend-icon="mdiRefresh" :loading="loading" @click="reload">刷新数据</v-btn>
        </div>
        <div class="data-tabs-scroll mb-4">
          <nav class="data-tabs" role="tablist" aria-label="Humanization 功能">
            <button v-for="[value,title,icon] in tabs" :key="value" type="button" role="tab" class="data-tab" :class="{'data-tab--active':tab === value}" :aria-selected="tab === value" :disabled="switching || settings?.saving" @click="navigate(value)">
              <v-icon :icon="icon" size="17" /><span>{{ title }}</span>
            </button>
          </nav>
        </div>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-autocomplete v-if="tab === 'overview'" v-model="scope" :items="[{ title: '全部会话', value: '' }, ...overview.sessions]" label="统计会话范围" hide-details class="mb-5" />
        <Overview v-if="tab === 'overview'" :stats="overview.stats" @browse="navigate" />
        <Settings v-else-if="tab === 'settings'" ref="settings" @changed="load" />
        <Records v-else :key="tab" :category="tab" :sessions="overview.sessions" :refresh="refresh" :timezone="overview.timezone" @changed="load" />
      </v-container>
      <v-dialog :model-value="pendingTab !== null" persistent max-width="540">
        <v-card>
          <v-card-title class="text-h6 pa-4 pb-0 pl-6 d-flex align-center justify-space-between">
            <span>未保存的更改</span><v-btn :icon="mdiClose" aria-label="继续编辑" variant="text" :disabled="switching" @click="pendingTab = null" />
          </v-card-title>
          <v-card-text>
            <p class="font-weight-bold mb-2">Humanization 配置有未保存的更改，切换前是否保存？</p>
            <p class="text-body-2 text-medium-emphasis">确定：保存并重载插件后切换；取消：放弃更改并切换；关闭弹窗：继续编辑。</p>
          </v-card-text>
          <v-card-actions><v-spacer /><v-btn variant="text" :disabled="switching" @click="leaveSettings(false)">取消</v-btn><v-btn color="error" variant="tonal" :loading="switching" @click="leaveSettings(true)">确定</v-btn></v-card-actions>
        </v-card>
      </v-dialog>
    </v-main>
  </v-app>
</template>

<style scoped>
/* Match the host's current DataPage navigation. */
.data-tabs-scroll { overflow-x: auto; padding: 4px 0 8px; scrollbar-width: none; }
.data-tabs-scroll::-webkit-scrollbar { display: none; }
.data-tabs { align-items: center; display: inline-flex; gap: 2px; min-width: max-content; }
.data-tab { align-items: center; border-radius: 8px; color: rgba(var(--v-theme-on-surface), 0.58); display: inline-flex; font-size: 0.8125rem; font-weight: 500; gap: 6px; height: 34px; padding: 0 12px; }
.data-tab:hover { background: rgba(var(--v-theme-on-surface), 0.045); color: rgba(var(--v-theme-on-surface), 0.78); }
.data-tab--active { background: rgba(var(--v-theme-on-surface), 0.065); color: rgba(var(--v-theme-on-surface), 0.86); }
.data-tab--active:hover { background: rgba(var(--v-theme-on-surface), 0.09); color: rgba(var(--v-theme-on-surface), 0.9); }
.data-tab:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
</style>

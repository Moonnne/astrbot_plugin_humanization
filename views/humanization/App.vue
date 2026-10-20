<script setup>
import { ref, inject, onMounted, watch } from 'vue';
import { mdiChartBar, mdiMessageTextOutline, mdiHeartOutline, mdiForumOutline, mdiBookOpenPageVariantOutline, mdiCogOutline, mdiRefresh } from '@mdi/js';
import Overview from './overview/Overview.vue';
import Records from './data/Records.vue';
import Settings from './settings/Settings.vue';

const bridge = inject('bridge');
const tab = ref('overview');
const settingsOpened = ref(false);
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
watch(scope, load);
watch(tab, value => { if (value === 'settings') settingsOpened.value = true; });
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
        <v-tabs v-model="tab" color="primary" show-arrows class="mb-5">
          <v-tab v-for="[value, title, icon] in tabs" :key="value" :value="value" :prepend-icon="icon">{{ title }}</v-tab>
        </v-tabs>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-autocomplete v-if="tab !== 'settings'" v-model="scope" :items="[{ title: '全部会话', value: '' }, ...overview.sessions]" label="会话范围" hide-details class="mb-5" />
        <Overview v-if="tab === 'overview'" :stats="overview.stats" @browse="tab = $event" />
        <Settings v-if="settingsOpened" v-show="tab === 'settings'" />
        <Records v-if="!['overview','settings'].includes(tab)" :key="tab" :category="tab" :scope="scope" :refresh="refresh" :timezone="overview.timezone" @changed="load" />
      </v-container>
    </v-main>
  </v-app>
</template>

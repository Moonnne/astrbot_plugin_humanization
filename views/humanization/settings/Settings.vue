<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue';
import { mdiContentSaveOutline, mdiRefresh } from '@mdi/js';
import SchemaFields from './SchemaFields.vue';
const bridge = inject('bridge');
const data = ref(null), model = ref(null), baseline = ref('');
const loading = ref(false), saving = ref(false), confirm = ref(false), error = ref(''), success = ref('');
const dirty = computed(() => model.value && JSON.stringify(model.value) !== baseline.value);
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
  } catch (e) { error.value = e.message; }
  finally { saving.value = false; confirm.value = false; }
}
function beforeLeave(event) { if (dirty.value) { event.preventDefault(); event.returnValue = ''; } }
onMounted(() => { load(); window.addEventListener('beforeunload', beforeLeave); });
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeLeave));
</script>
<template>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
  <v-alert v-if="success" type="success" variant="tonal" class="mb-4">{{ success }}</v-alert>
  <v-alert type="info" variant="tonal" class="mb-4">配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。</v-alert>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <span class="text-body-2 flex-grow-1">{{ dirty ? '有未保存的修改' : '配置已同步' }}</span>
    <v-btn :prepend-icon="mdiRefresh" :loading="loading" :disabled="saving || !!dirty" @click="load">重新载入</v-btn>
    <v-btn color="primary" :prepend-icon="mdiContentSaveOutline" :disabled="!dirty || loading" :loading="saving" @click="confirm = true">保存并重载</v-btn>
  </div>
  <v-progress-linear v-if="loading" indeterminate color="primary" />
  <v-expansion-panels v-if="data && model" multiple variant="accordion">
    <v-expansion-panel v-for="(section,key) in data.schema" :key="key" :title="section.description">
      <v-expansion-panel-text><div class="pt-3"><SchemaFields :schema="section.items" :model="model[key]" :choices="data.choices" /></div></v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
  <v-dialog v-model="confirm" max-width="540" :persistent="saving">
    <v-card><v-card-title class="text-h6 pa-4 pb-0 pl-6">保存配置</v-card-title>
      <v-card-text>
        保存后将重载 Humanization，进行中的回复可能中断。
        <v-alert v-if="model?.danger.clear_all_data" type="error" variant="tonal" class="mt-3">已启用“清除所有会话数据”，重载时会执行清理。请核对危险操作区的确认文字。</v-alert>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="saving" @click="confirm = false">取消</v-btn><v-btn color="primary" :loading="saving" @click="save">确认保存</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>

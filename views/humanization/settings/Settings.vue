<script setup>
import { ref, computed, inject, onMounted } from 'vue';
import { mdiContentSaveOutline, mdiRefresh, mdiAlertCircleOutline, mdiDeleteAlertOutline } from '@mdi/js';
import SchemaFields from './SchemaFields.vue';
const bridge = inject('bridge');
const emit = defineEmits(['changed']);
const data = ref(null), model = ref(null), baseline = ref('');
const loading = ref(false), saving = ref(false), confirm = ref(false), error = ref(''), success = ref('');
const dirty = computed(() => model.value && JSON.stringify(model.value) !== baseline.value);
const resetDialog = ref(false), confirmation = ref(''), resetting = ref(false), resetError = ref('');
const busy = computed(() => saving.value || resetting.value);
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
onMounted(load);
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
    <v-card v-for="(section,key) in data.schema" :key="key" tag="section" :aria-label="section.description" class="mb-5" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5 text-wrap">{{ section.description }}</v-card-title>
      <v-card-text><SchemaFields :schema="section.items" :model="model[key]" :choices="data.choices" /></v-card-text>
    </v-card>
    <v-card tag="section" aria-label="危险操作区" color="error" variant="outlined" class="my-6" rounded="xl">
      <v-card-title tag="h2" class="text-h6 pa-5 d-flex align-center ga-2"><v-icon :icon="mdiDeleteAlertOutline" />危险操作区</v-card-title>
      <v-card-text>
        <p class="mb-4">清除全部 Humanization 会话的聊天记录、话题、日记、最近反应、辅助模型进度与计数，并为对应主模型开启空白对话。包含当前未启用的历史会话，删除后无法撤销。</p>
        <v-btn color="error" variant="flat" :prepend-icon="mdiDeleteAlertOutline" :disabled="busy || loading" @click="confirmation = ''; resetError = ''; resetDialog = true">清除所有会话数据</v-btn>
      </v-card-text>
    </v-card>
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
    <v-icon :icon="mdiAlertCircleOutline" size="20" class="mr-2" />Humanization 配置尚未保存，请点击“保存并重载”。
  </v-snackbar>
</template>

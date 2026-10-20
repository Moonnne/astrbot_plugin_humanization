<script setup>
import { ref, computed } from 'vue';
import { mdiChevronDown, mdiMagnify } from '@mdi/js';
const props = defineProps({ modelValue:String, label:String, hint:String, kind:String, items:Array });
const emit = defineEmits(['update:modelValue']);
const open = ref(false), search = ref(''), draft = ref('');
const current = computed(() => props.items.find(item => item.value === props.modelValue));
const matches = computed(() => props.items.filter(item => `${item.title} ${item.description || ''}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())));
function show() { search.value = ''; draft.value = props.modelValue; open.value = true; }
function choose(value) { emit('update:modelValue',value); open.value = false; }
</script>
<template>
  <div class="resource-field">
    <div class="resource-row">
      <span class="text-subtitle-2">{{ label }}</span>
      <v-menu v-if="kind === 'select_provider'" v-model="open" :close-on-content-click="false" location="bottom end" :offset="10">
        <template #activator="{props}">
          <button v-bind="props" type="button" class="provider-trigger" :aria-label="label" @click="search = ''">
            <span class="text-truncate">{{ current?.title || modelValue || '未选择' }}</span><v-icon :icon="mdiChevronDown" size="18" />
          </button>
        </template>
        <v-card class="provider-menu-card pa-3" rounded="xl">
          <v-text-field v-model="search" label="搜索模型" :prepend-inner-icon="mdiMagnify" density="compact" clearable hide-details @click:clear="search = ''" />
          <v-list role="listbox" class="resource-options mt-2" density="compact">
            <v-list-item role="option" title="未选择" :active="!modelValue" @click="choose('')" />
            <v-list-item v-for="item in matches" :key="item.value" role="option" :title="item.title" :active="item.value === modelValue" @click="choose(item.value)" />
            <v-list-item v-if="!matches.length" title="没有匹配的模型" disabled />
          </v-list>
        </v-card>
      </v-menu>
      <div v-else class="persona-trigger">
        <span class="text-body-2 text-truncate">{{ current?.title || modelValue || '未选择' }}</span>
        <v-btn size="small" color="primary" variant="tonal" :aria-label="label" @click="show">选择人格</v-btn>
      </div>
    </div>
    <p v-if="hint" class="text-caption text-medium-emphasis mt-2">{{ hint }}</p>
    <v-dialog v-if="kind === 'select_persona'" v-model="open" max-width="900" scrollable>
      <v-card>
        <v-card-title class="text-h6 pa-5">选择人格 · {{ label }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="search" label="搜索人格" :prepend-inner-icon="mdiMagnify" clearable hide-details class="mb-3" @click:clear="search = ''" />
          <v-list role="listbox" class="resource-options">
            <v-list-item role="option" title="未选择人格" :active="!draft" @click="draft = ''" />
            <v-list-item v-for="item in matches" :key="item.value" role="option" :title="item.title" :subtitle="item.description || '无提示词正文'" :active="draft === item.value" @click="draft = item.value" />
          </v-list>
          <v-divider class="my-3" />
          <p class="text-caption text-medium-emphasis mb-2">人格提示词预览</p>
          <pre class="persona-preview">{{ items.find(item => item.value === draft)?.description || '未选择人格，将使用文本或默认提示词' }}</pre>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="open = false">取消</v-btn><v-btn color="primary" @click="choose(draft)">确定</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
<style scoped>
.resource-row { align-items: center; display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; min-width: 0; }
.resource-row > span { flex: 1 1 140px; }
/* Match the host ProviderSelectMenu config trigger and menu surface. */
.provider-trigger { align-items: center; border-radius: 8px; display: inline-flex; gap: 10px; justify-content: space-between; max-width: 100%; min-height: 36px; min-width: 0; padding: 6px 8px; font-size: 0.88rem; font-weight: 500; }
.provider-trigger:hover { background: rgba(var(--v-theme-on-surface), 0.045); }
.provider-menu-card { width: min(420px, calc(100vw - 24px)); border: 1px solid rgba(var(--v-theme-on-surface), 0.09); box-shadow: 0 6px 16px rgba(0,0,0,0.07) !important; }
.resource-options { max-height: 340px; overflow-y: auto; }
.persona-trigger { align-items: center; display: flex; gap: 12px; min-width: 0; max-width: 100%; }
.persona-preview { font: inherit; font-size: 0.82rem; max-height: 200px; overflow: auto; overflow-wrap: anywhere; white-space: pre-wrap; }
</style>

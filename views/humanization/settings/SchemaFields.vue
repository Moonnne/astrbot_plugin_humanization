<script setup>
import { mdiPlus, mdiDeleteOutline } from '@mdi/js';
const props = defineProps({ schema:Object, model:Object, choices:Object });
function visible(field) { return Object.entries(field.condition || {}).every(([key,value]) => props.model[key] === value); }
function options(field) {
  if (field._special) return [{title:'未选择',value:''}, ...(props.choices[field._special] || [])];
  return (field.options || []).map((value,index) => ({value,title:field.labels?.[index] || value}));
}
function add(key, field, templateKey) {
  const value = {__template_key:templateKey};
  for (const [name,item] of Object.entries(field.templates[templateKey].items)) value[name] = JSON.parse(JSON.stringify(item.default));
  props.model[key].push(value);
}
function updateNumber(key, value) { props.model[key] = value === '' ? '' : Number(value); }
</script>
<template>
  <template v-for="(field,key) in schema" :key="key">
    <div v-if="visible(field)" class="mb-5">
      <template v-if="field.type === 'template_list'">
        <div class="d-flex align-center flex-wrap ga-2 mb-3">
          <span class="text-subtitle-1 font-weight-bold flex-grow-1">{{ field.description }}</span>
          <v-btn v-for="(template,id) in field.templates" :key="id" :prepend-icon="mdiPlus" size="small" @click="add(key,field,id)">添加{{ template.name }}</v-btn>
        </div>
        <v-card v-for="(item,index) in model[key]" :key="index" class="pa-4 mb-3">
          <div class="d-flex justify-space-between align-center mb-3">
            <span>{{ item.name || `条目 ${index + 1}` }}</span>
            <v-btn :icon="mdiDeleteOutline" aria-label="移除时段" variant="text" size="small" color="error" @click="model[key].splice(index,1)" />
          </div>
          <SchemaFields :schema="field.templates[item.__template_key || Object.keys(field.templates)[0]].items" :model="item" :choices="choices" />
        </v-card>
        <p class="text-caption text-medium-emphasis">{{ field.hint }}</p>
      </template>
      <v-switch v-else-if="field.type === 'bool'" v-model="model[key]" :label="field.description" :hint="field.hint" persistent-hint color="primary" inset />
      <v-textarea v-else-if="field.type === 'text'" v-model="model[key]" :label="field.description" :hint="field.hint" persistent-hint variant="outlined" auto-grow rows="3" />
      <template v-else-if="field.slider">
        <div class="text-subtitle-2 mb-2">{{ field.description }}</div>
        <v-slider v-model="model[key]" :min="field.slider.min" :max="field.slider.max" :step="field.slider.step" color="primary" thumb-label hide-details>
          <template #append><v-text-field :model-value="model[key]" :aria-label="field.description" type="number" :min="field.slider.min" :max="field.slider.max" :step="field.slider.step" width="110" hide-details @update:model-value="updateNumber(key,$event)" /></template>
        </v-slider>
        <p class="text-caption text-medium-emphasis">{{ field.hint }}</p>
      </template>
      <v-autocomplete v-else-if="field.options || field._special" v-model="model[key]" :label="field.description" :hint="field.hint" persistent-hint :items="options(field)" :multiple="field.type === 'list'" :chips="field.type === 'list'" :closable-chips="field.type === 'list'" />
      <v-combobox v-else-if="field.type === 'list'" v-model="model[key]" :label="field.description" :hint="field.hint" persistent-hint multiple chips closable-chips />
      <v-text-field v-else-if="['int','float'].includes(field.type)" :model-value="model[key]" :label="field.description" :hint="field.hint" persistent-hint type="number" :step="field.type === 'int' ? 1 : 'any'" @update:model-value="updateNumber(key,$event)" />
      <v-text-field v-else v-model="model[key]" :label="field.description" :hint="field.hint" persistent-hint />
    </div>
  </template>
</template>

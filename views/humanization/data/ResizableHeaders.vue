<script setup>
import { onBeforeUnmount } from 'vue';
import { mdiArrowUpDown } from '@mdi/js';
defineOptions({inheritAttrs:false});
const props = defineProps({ columns:Array, widths:Object, defaults:Object, sortBy:Array, isSorted:Function, toggleSort:Function, getSortIcon:Function, allSelected:Boolean, someSelected:Boolean, selectAll:Function });
const emit = defineEmits(['resize']);
const minimum = key => ({timestamp:144,conversation:128,headline:160,state:112,actions:88}[key] || 48);
let dragging;
function resize(key, width) { emit('resize',{key,width:Math.max(minimum(key),Math.round(width))}); }
function move(event) { if (dragging) resize(dragging.key,dragging.width + event.clientX - dragging.x); }
function stop() { dragging = null; window.removeEventListener('pointermove',move); window.removeEventListener('pointerup',stop); window.removeEventListener('pointercancel',stop); }
function start(event, key) {
  event.preventDefault(); stop();
  dragging = {key,x:event.clientX,width:event.currentTarget.closest('th').getBoundingClientRect().width};
  window.addEventListener('pointermove',move); window.addEventListener('pointerup',stop); window.addEventListener('pointercancel',stop);
}
onBeforeUnmount(stop);
</script>
<template>
  <tr>
    <th v-for="column in columns" :key="column.key" scope="col" :class="{'record-actions':column.key === 'actions','sortable':column.sortable}" :style="{width:`${widths[column.key] || 48}px`,minWidth:`${widths[column.key] || 48}px`}" :aria-sort="column.sortable ? isSorted(column) ? sortBy.find(item => item.key === column.key)?.order === 'desc' ? 'descending' : 'ascending' : 'none' : undefined" @click="column.sortable && toggleSort(column)">
      <v-checkbox-btn v-if="column.key === 'data-table-select'" :model-value="allSelected" :indeterminate="someSelected && !allSelected" aria-label="选择当前页" @update:model-value="selectAll" />
      <template v-else>
        <button v-if="column.sortable" type="button" class="sort-heading" :aria-label="`按${column.title}排序`" @click.stop="toggleSort(column)">{{ column.title }}<v-icon :icon="isSorted(column) ? getSortIcon(column) : mdiArrowUpDown" :class="{'sort-idle':!isSorted(column)}" size="16" /></button>
        <span v-else>{{ column.title }}</span>
        <span v-if="column.key !== 'actions'" role="separator" aria-orientation="vertical" :aria-label="`调整${column.title}列宽`" :aria-valuenow="widths[column.key]" :aria-valuemin="minimum(column.key)" tabindex="0" class="resize-handle" @pointerdown.stop="start($event,column.key)" @click.stop @dblclick.stop="resize(column.key,defaults[column.key])" @keydown.left.prevent="resize(column.key,widths[column.key]-16)" @keydown.right.prevent="resize(column.key,widths[column.key]+16)" />
      </template>
    </th>
  </tr>
</template>
<style scoped>
th { position: relative; padding: 0 16px; white-space: nowrap; height: 56px; text-align: start; font-weight: 500; }
.sort-heading { display: inline-flex; align-items: center; gap: 4px; }
.sortable { cursor: pointer; }
.sort-idle { opacity: 0.35; }
.sort-heading:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 3px; }
.resize-handle { position: absolute; right: 0; top: 8px; bottom: 8px; width: 9px; cursor: col-resize; touch-action: none; }
.resize-handle::after { content: ''; position: absolute; right: 3px; top: 0; bottom: 0; width: 1px; background: rgba(var(--v-theme-on-surface),0.15); }
.resize-handle:hover::after, .resize-handle:focus-visible::after { background: rgb(var(--v-theme-primary)); width: 2px; }
</style>

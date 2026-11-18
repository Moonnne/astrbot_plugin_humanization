<script setup>
import {inject,ref,watch} from 'vue';
import {formatBytes} from '../shared/size.js';
const props=defineProps({resource:Object});
const emit=defineEmits(['preview']);
const bridge=inject('bridge'), url=ref('');
watch([() => props.resource.id, () => props.resource.path], async ([id,path], _, onCleanup) => {
  let active=true; onCleanup(()=>{active=false;}); url.value='';
  if (!path || props.resource.kind !== 'image') return;
  try { const data=await bridge.apiGet('resource',{id}); if(active) url.value=data.url; }
  catch { /* The cached file may have expired. Its database metadata remains. */ }
}, {immediate:true});
</script>
<template>
  <div>
    <button v-if="resource.path && ['image','video','record'].includes(resource.kind)" type="button" class="media-target"
      :aria-label="'查看媒体 '+resource.name" title="双击查看媒体"
      @dblclick="emit('preview',resource)" @click="($event.detail === 0 || $event.pointerType === 'touch') && emit('preview',resource)">
      <img v-if="url" :src="url" :alt="resource.name" @error="url=''" />
      <span v-else>{{ {video:'查看视频',record:'播放语音',image:'查看图片'}[resource.kind] }} · {{ resource.name }}</span>
    </button>
    <div class="text-caption">{{ resource.kind }} · {{ resource.name }}<template v-if="resource.kind !== 'link'"> · {{ formatBytes(resource.size) }}</template></div>
    <v-card v-if="resource.description && (resource.status === 'ready' || resource.description !== resource.name)" variant="outlined" class="mt-1 pa-2 text-body-2">{{ resource.description }}</v-card>
  </div>
</template>
<style scoped>
.media-target { display:block; max-width:100%; cursor:zoom-in; text-align:start; touch-action:manipulation; }
img { display:block; max-width:100%; max-height:22rem; object-fit:contain; }
</style>

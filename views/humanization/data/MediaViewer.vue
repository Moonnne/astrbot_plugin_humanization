<script setup>
import { computed, inject, onMounted, ref } from 'vue';
import { mdiClose, mdiInformationOutline, mdiMagnifyMinusOutline, mdiMagnifyPlusOutline } from '@mdi/js';
import { formatBytes } from '../shared/size.js';

const props = defineProps({resource:Object});
const emit = defineEmits(['close']);
const bridge = inject('bridge');
const url = ref(''), error = ref(''), info = ref(false);
const zoom = ref(1), dimensions = ref(null);
const imageStyle = computed(() => {
  if (!dimensions.value) return {};
  const {width,height} = dimensions.value;
  return {width:`calc(min(100cqw, ${width / height * 100}cqh, ${width}px) * ${zoom.value})`};
});
function measure(event) {
  const media = event.target;
  const width = media.naturalWidth || media.videoWidth;
  if (width) dimensions.value = {width, height:media.naturalHeight || media.videoHeight};
}
function playbackError() { error.value = '媒体加载失败，文件可能已过期，或浏览器无法解码此格式'; }
onMounted(async () => {
  try {
    // A thumbnail's short-lived file token may have expired while the user was reading.
    url.value = (await bridge.apiGet('resource',{id:props.resource.id})).url;
  } catch (e) { error.value = e.message; }
});
</script>
<template>
  <v-dialog :model-value="true" fullscreen :aria-label="'媒体查看器 · '+resource.name" @update:model-value="!$event && emit('close')">
    <div class="viewer">
      <div class="stage">
        <p v-if="error" role="alert">{{ error }}</p>
        <v-progress-linear v-else-if="!url" indeterminate aria-label="加载媒体" />
        <img v-else-if="resource.kind === 'image'" :src="url" :alt="resource.name" :style="imageStyle" @load="measure" @error="playbackError" />
        <video v-else-if="resource.kind === 'video'" :src="url" controls playsinline @loadedmetadata="measure" @error="playbackError" />
        <audio v-else :src="url" controls @error="playbackError" />
      </div>
      <div class="viewer-tools">
        <v-btn :icon="mdiInformationOutline" aria-label="媒体信息" :aria-expanded="info" @click="info = !info" />
        <v-btn :icon="mdiClose" aria-label="关闭媒体查看器" @click="emit('close')" />
      </div>
      <aside v-if="info" class="media-info" aria-label="媒体信息">
        <strong>{{ resource.name }}</strong>
        <p>{{ resource.mime || resource.kind }} · {{ formatBytes(resource.size) }}</p>
        <p v-if="dimensions">{{ dimensions.width }} × {{ dimensions.height }} px</p>
        <p v-if="resource.created_at">{{ new Date(resource.created_at * 1000).toLocaleString() }}</p>
        <p class="mt-2">{{ resource.description || '暂无转述' }}</p>
      </aside>
      <div v-if="resource.kind === 'image' && dimensions && !error" class="zoom-tools">
        <v-btn :icon="mdiMagnifyMinusOutline" aria-label="缩小图片" :disabled="zoom <= 0.5" @click="zoom -= 0.5" />
        <span aria-live="polite">{{ zoom * 100 }}%</span>
        <v-btn :icon="mdiMagnifyPlusOutline" aria-label="放大图片" :disabled="zoom >= 5" @click="zoom += 0.5" />
      </div>
    </div>
  </v-dialog>
</template>
<style scoped>
.viewer { position:relative; height:100%; width:100%; background:#181818; color:white; }
.stage { position:absolute; inset:0; overflow:auto; display:flex; container-type:size; }
.stage > * { flex:none; margin:auto; }
.stage img { display:block; }
.stage video { max-width:100%; max-height:100%; }
.stage audio { max-width:100%; }
.viewer-tools, .zoom-tools { position:absolute; display:flex; align-items:center; gap:8px; }
.viewer-tools { right:12px; top:12px; }
.viewer-tools .v-btn, .zoom-tools, .media-info { background:rgba(0,0,0,.72); color:white; }
.viewer-tools .v-btn { border-radius:50%; }
.zoom-tools { bottom:12px; left:50%; transform:translateX(-50%); border-radius:32px; }
.media-info { position:absolute; right:12px; top:68px; width:min(22rem,calc(100% - 24px)); max-height:65%; overflow:auto; border-radius:12px; padding:16px; overflow-wrap:anywhere; white-space:pre-wrap; }
</style>

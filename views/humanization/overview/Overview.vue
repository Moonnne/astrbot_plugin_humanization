<script setup>
defineProps({ stats: Object });
defineEmits(['browse']);
const cards = [['sessions','会话',null],['messages','聊天记录','messages'],['topics','话题','topics'],['diaries','日记日期','diaries'],['decisions','近期决策','decisions'],['planned_replies','决定回复','decisions']];
</script>
<template>
  <v-row>
    <v-col v-for="[key,label,target] in cards" :key="key" cols="12" sm="6" lg="4">
      <v-card class="pa-5 h-100" :link="!!target" @click="target && $emit('browse',target)">
        <div class="text-body-2 text-medium-emphasis mb-3">{{ label }}</div>
        <div class="text-h4 font-weight-bold">{{ (stats[key] || 0).toLocaleString() }}</div>
      </v-card>
    </v-col>
  </v-row>
  <v-alert variant="tonal" type="info" class="mt-5">
    统计来自当前插件数据库。聊天条数会随保留上限滚动；最近反应每个会话最多保留10条。决定回复表示规划结果，不代表已经发送，实际结果请在详情中查看。
  </v-alert>
</template>

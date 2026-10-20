import { r as resolveComponent, o as openBlock, c as createElementBlock, a as createVNode, w as withCtx, F as Fragment, b as renderList, d as createBaseVNode, t as toDisplayString, e as createTextVNode, f as computed, g as createCommentVNode, h as createBlock, i as ref, j as watch, u as unref, m as mdiFilterRemoveOutline, k as mdiChevronLeft, l as mdiMagnify, n as mergeProps, p as normalizeClass, q as pushScopeId, s as popScopeId, v as inject, x as reactive, y as onBeforeUnmount, z as mdiFilterVariant, A as mdiDeleteOutline, B as withDirectives, C as vShow, D as mdiEyeOutline, E as mdiPlus, G as onMounted, H as mdiRefresh, I as mdiContentSaveOutline, J as mdiDeleteAlertOutline, K as mdiAlertCircleOutline, L as mdiChartBar, M as mdiMessageTextOutline, N as mdiHeartOutline, O as mdiForumOutline, P as mdiBookOpenPageVariantOutline, Q as mdiCogOutline, R as mdiClose, S as createVuetify, T as createApp, U as zhHans, V as mdi, W as aliases, X as VExpandXTransition, Y as VTextarea, Z as VTextField, _ as VTable, $ as VSwitch, a0 as VSnackbar, a1 as VSlider, a2 as VSelect, a3 as VSpacer, a4 as VCol, a5 as VRow, a6 as VContainer, a7 as VProgressLinear, a8 as VListItem, a9 as VMain, aa as VIcon, ab as VDivider, ac as VDialog, ad as VDataTableServer, ae as VCombobox, af as VCheckboxBtn, ag as VChip, ah as VCardTitle, ai as VCardText, aj as VCardActions, ak as VCard, al as VBtn, am as VAutocomplete, an as VAlert, ao as VApp } from "./assets/vendor.js";
const _hoisted_1$6 = { class: "text-body-2 text-medium-emphasis mb-3" };
const _hoisted_2$6 = { class: "text-h4 font-weight-bold" };
const _sfc_main$6 = {
  __name: "Overview",
  props: { stats: Object },
  emits: ["browse"],
  setup(__props) {
    const cards = [["sessions", "会话", null], ["messages", "聊天记录", "messages"], ["topics", "话题", "topics"], ["diaries", "日记日期", "diaries"], ["decisions", "近期决策", "decisions"], ["planned_replies", "决定回复", "decisions"]];
    return (_ctx, _cache) => {
      const _component_v_card = resolveComponent("v-card");
      const _component_v_col = resolveComponent("v-col");
      const _component_v_row = resolveComponent("v-row");
      const _component_v_alert = resolveComponent("v-alert");
      return openBlock(), createElementBlock(Fragment, null, [
        createVNode(_component_v_row, null, {
          default: withCtx(() => [
            (openBlock(), createElementBlock(Fragment, null, renderList(cards, ([key, label, target]) => {
              return createVNode(_component_v_col, {
                key,
                cols: "12",
                sm: "6",
                lg: "4"
              }, {
                default: withCtx(() => [
                  createVNode(_component_v_card, {
                    class: "pa-5 h-100",
                    link: !!target,
                    onClick: ($event) => target && _ctx.$emit("browse", target)
                  }, {
                    default: withCtx(() => [
                      createBaseVNode("div", _hoisted_1$6, toDisplayString(label), 1),
                      createBaseVNode("div", _hoisted_2$6, toDisplayString((__props.stats[key] || 0).toLocaleString()), 1)
                    ]),
                    _: 2
                  }, 1032, ["link", "onClick"])
                ]),
                _: 2
              }, 1024);
            }), 64))
          ]),
          _: 1
        }),
        createVNode(_component_v_alert, {
          variant: "tonal",
          type: "info",
          class: "mt-5"
        }, {
          default: withCtx(() => [
            createTextVNode(" 统计来自当前插件数据库。聊天条数会随保留上限滚动；最近反应每个会话最多保留10条。决定回复表示规划结果，不代表已经发送，实际结果请在详情中查看。 ")
          ]),
          _: 1
        })
      ], 64);
    };
  }
};
const _hoisted_1$5 = {
  key: 0,
  class: "text-medium-emphasis"
};
const _hoisted_2$5 = {
  key: 1,
  class: "d-flex flex-column ga-2"
};
const _hoisted_3$5 = {
  key: 0,
  class: "text-medium-emphasis"
};
const _hoisted_4$5 = { class: "text-medium-emphasis text-no-wrap align-top py-2" };
const _hoisted_5$4 = { class: "text-break py-2" };
const _hoisted_6$4 = {
  key: 3,
  class: "text-body-2 text-pre-wrap text-break"
};
const _sfc_main$5 = {
  __name: "JsonValue",
  props: { value: { default: null } },
  setup(__props) {
    const props = __props;
    const parsed = computed(() => {
      if (typeof props.value === "string" && /^[\[{]/.test(props.value.trim())) {
        try {
          return JSON.parse(props.value);
        } catch {
        }
      }
      return props.value;
    });
    const labels = { sender_id: "发送者ID", target_id: "目标ID", target_is_self: "目标是本机器人", type: "类型", text: "正文", reply: "回应", reason: "原因", emotion: "情绪", primary: "主情绪", intensity: "强度", plan: "计划", participation: "参与方式", target_message_id: "目标消息", topic_id: "话题ID", intent: "意图", style: "风格", guidance: "回复指导", topic: "主题", interact: "参与行为", reaction: "用户反应", day: "日期", topic_time: "话题时间" };
    return (_ctx, _cache) => {
      const _component_JsonValue = resolveComponent("JsonValue", true);
      const _component_v_card = resolveComponent("v-card");
      const _component_v_table = resolveComponent("v-table");
      return parsed.value === null ? (openBlock(), createElementBlock("div", _hoisted_1$5, "—")) : Array.isArray(parsed.value) ? (openBlock(), createElementBlock("div", _hoisted_2$5, [
        !parsed.value.length ? (openBlock(), createElementBlock("span", _hoisted_3$5, "无")) : createCommentVNode("", true),
        (openBlock(true), createElementBlock(Fragment, null, renderList(parsed.value, (item, index) => {
          return openBlock(), createBlock(_component_v_card, {
            key: index,
            class: "pa-3"
          }, {
            default: withCtx(() => [
              createVNode(_component_JsonValue, { value: item }, null, 8, ["value"])
            ]),
            _: 2
          }, 1024);
        }), 128))
      ])) : typeof parsed.value === "object" ? (openBlock(), createBlock(_component_v_table, {
        key: 2,
        density: "compact"
      }, {
        default: withCtx(() => [
          createBaseVNode("tbody", null, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(parsed.value, (item, key) => {
              return openBlock(), createElementBlock("tr", { key }, [
                createBaseVNode("td", _hoisted_4$5, toDisplayString(labels[key] || key), 1),
                createBaseVNode("td", _hoisted_5$4, [
                  createVNode(_component_JsonValue, { value: item }, null, 8, ["value"])
                ])
              ]);
            }), 128))
          ])
        ]),
        _: 1
      })) : (openBlock(), createElementBlock("div", _hoisted_6$4, toDisplayString(parsed.value === true ? "是" : parsed.value === false ? "否" : parsed.value), 1));
    };
  }
};
const outcomes = [
  ["pending", "待执行"],
  ["processed", "发送流程完成"],
  ["observed", "保持沉默"],
  ["failed", "失败"],
  ["superseded", "已被取代"],
  ["unconfirmed", "结果未确认"]
].map(([value, title]) => ({ value, title }));
const emotions = [
  ["NEUTRAL", "平静"],
  ["JOY", "高兴"],
  ["AFFECTION", "亲近"],
  ["PRIDE", "自豪"],
  ["ANTICIPATION", "期待"],
  ["SURPRISE", "惊讶"],
  ["UNCERTAINTY", "不确定"],
  ["SADNESS", "难过"],
  ["ANGER", "生气"],
  ["AVERSION", "反感"],
  ["FEAR", "害怕"],
  ["SELF_CONSCIOUS", "难为情"],
  ["LOW_ENERGY", "低落／疲倦"],
  ["ENVY", "羡慕"]
].map(([value, title]) => ({ value, title }));
const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};
const _withScopeId$2 = (n) => (pushScopeId("data-v-3baa6c1c"), n = n(), popScopeId(), n);
const _hoisted_1$4 = { class: "d-flex align-center ga-1 mb-4" };
const _hoisted_2$4 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("span", { class: "text-subtitle-1 font-weight-bold flex-grow-1" }, "筛选", -1));
const _hoisted_3$4 = {
  key: 0,
  class: "text-caption text-medium-emphasis mt-2"
};
const _hoisted_4$4 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label mt-5" }, "对话类型", -1));
const _hoisted_5$3 = { class: "type-options" };
const _hoisted_6$3 = ["aria-pressed", "onClick"];
const _hoisted_7$3 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label" }, "消息方向", -1));
const _hoisted_8$2 = { class: "type-options mb-4" };
const _hoisted_9$1 = ["aria-pressed", "onClick"];
const _hoisted_10$1 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label" }, "回复决定", -1));
const _hoisted_11$1 = { class: "type-options mb-4" };
const _hoisted_12$1 = ["aria-pressed", "onClick"];
const _sfc_main$4 = {
  __name: "FilterPanel",
  props: { category: String, model: Object, sessions: Array, active: Boolean },
  emits: ["collapse", "reset"],
  setup(__props) {
    const props = __props;
    const sessionMenu = ref(false);
    watch(() => props.active, (active) => {
      if (!active) sessionMenu.value = false;
    });
    const all = { title: "全部", value: "" };
    const components = [["text", "文字"], ["at", "@ 提及"], ["image", "图片"], ["video", "视频"], ["record", "语音"], ["file", "文件"], ["poke", "戳一戳"]].map(([value, title]) => ({ value, title }));
    const sorts = [["timestamp:desc", "时间：从新到旧"], ["timestamp:asc", "时间：从旧到新"], ["headline:asc", "内容：正序"], ["headline:desc", "内容：倒序"]].map(([value, title]) => ({ value, title }));
    function toggle(key, value) {
      props.model[key] = props.model[key] === value ? "" : value;
    }
    function matchSession(value, query, item) {
      const search = query.toLocaleLowerCase();
      return [item.raw.title, item.raw.umo].some((text) => text.toLocaleLowerCase().includes(search));
    }
    return (_ctx, _cache) => {
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_text_field = resolveComponent("v-text-field");
      const _component_v_divider = resolveComponent("v-divider");
      const _component_v_chip = resolveComponent("v-chip");
      const _component_v_checkbox_btn = resolveComponent("v-checkbox-btn");
      const _component_v_list_item = resolveComponent("v-list-item");
      const _component_v_autocomplete = resolveComponent("v-autocomplete");
      const _component_v_select = resolveComponent("v-select");
      const _component_v_card = resolveComponent("v-card");
      return openBlock(), createBlock(_component_v_card, {
        tag: "aside",
        "aria-label": "数据筛选",
        class: "filter-panel",
        border: false,
        rounded: "xl"
      }, {
        default: withCtx(() => [
          createBaseVNode("div", _hoisted_1$4, [
            _hoisted_2$4,
            createVNode(_component_v_btn, {
              icon: unref(mdiFilterRemoveOutline),
              "aria-label": "重置筛选",
              size: "small",
              variant: "text",
              onClick: _cache[0] || (_cache[0] = ($event) => _ctx.$emit("reset"))
            }, null, 8, ["icon"]),
            createVNode(_component_v_btn, {
              icon: unref(mdiChevronLeft),
              "aria-label": "折叠筛选栏",
              size: "small",
              variant: "text",
              onClick: _cache[1] || (_cache[1] = ($event) => _ctx.$emit("collapse"))
            }, null, 8, ["icon"])
          ]),
          createVNode(_component_v_text_field, {
            modelValue: __props.model.q,
            "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => __props.model.q = $event),
            label: "搜索关键词",
            placeholder: "搜索聊天、话题或记录",
            "prepend-inner-icon": unref(mdiMagnify),
            clearable: "",
            "hide-details": "",
            "onClick:clear": _cache[3] || (_cache[3] = ($event) => __props.model.q = "")
          }, null, 8, ["modelValue", "prepend-inner-icon"]),
          createVNode(_component_v_divider, { class: "my-5" }),
          createVNode(_component_v_autocomplete, {
            modelValue: __props.model.sessions,
            "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => __props.model.sessions = $event),
            menu: sessionMenu.value,
            "onUpdate:menu": _cache[5] || (_cache[5] = ($event) => sessionMenu.value = $event),
            class: "session-select",
            label: "会话",
            placeholder: "搜索名称或 UMO，多选",
            items: __props.sessions,
            "item-title": "title",
            "custom-filter": matchSession,
            "menu-props": { maxWidth: 520 },
            density: "compact",
            multiple: "",
            chips: "",
            "closable-chips": "",
            "hide-details": ""
          }, {
            chip: withCtx(({ props: props2, item }) => [
              createVNode(_component_v_chip, mergeProps(props2, {
                class: "text-truncate",
                "max-width": "100%",
                title: item.raw.umo
              }), {
                default: withCtx(() => [
                  createTextVNode(toDisplayString(item.raw.title), 1)
                ]),
                _: 2
              }, 1040, ["title"])
            ]),
            item: withCtx(({ props: props2, item }) => [
              createVNode(_component_v_list_item, mergeProps(props2, {
                role: "option",
                title: item.raw.title,
                subtitle: item.raw.umo
              }), {
                prepend: withCtx(({ isSelected }) => [
                  createVNode(_component_v_checkbox_btn, {
                    "model-value": isSelected,
                    ripple: false,
                    tabindex: "-1"
                  }, null, 8, ["model-value"])
                ]),
                _: 2
              }, 1040, ["title", "subtitle"])
            ]),
            _: 1
          }, 8, ["modelValue", "menu", "items"]),
          !__props.sessions.length ? (openBlock(), createElementBlock("p", _hoisted_3$4, "尚无已启用的会话")) : createCommentVNode("", true),
          _hoisted_4$4,
          createBaseVNode("div", _hoisted_5$3, [
            (openBlock(), createElementBlock(Fragment, null, renderList([["group", "群聊"], ["private", "私聊"]], ([value, title]) => {
              return createBaseVNode("button", {
                key: value,
                type: "button",
                class: normalizeClass(["type-option", { "type-option--selected": __props.model.chat_type === value }]),
                "aria-pressed": __props.model.chat_type === value,
                onClick: ($event) => toggle("chat_type", value)
              }, toDisplayString(title), 11, _hoisted_6$3);
            }), 64))
          ]),
          createVNode(_component_v_divider, { class: "my-5" }),
          __props.category === "messages" ? (openBlock(), createElementBlock(Fragment, { key: 1 }, [
            _hoisted_7$3,
            createBaseVNode("div", _hoisted_8$2, [
              (openBlock(), createElementBlock(Fragment, null, renderList([["in", "收到消息"], ["out", "发出回复"]], ([value, title]) => {
                return createBaseVNode("button", {
                  key: value,
                  type: "button",
                  class: normalizeClass(["type-option", { "type-option--selected": __props.model.kind === value }]),
                  "aria-pressed": __props.model.kind === value,
                  onClick: ($event) => toggle("kind", value)
                }, toDisplayString(title), 11, _hoisted_9$1);
              }), 64))
            ]),
            createVNode(_component_v_text_field, {
              modelValue: __props.model.sender,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => __props.model.sender = $event),
              label: "发送者昵称或 ID",
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue"]),
            createVNode(_component_v_select, {
              modelValue: __props.model.component,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => __props.model.component = $event),
              label: "消息内容类型",
              items: [all, ...unref(components)],
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ], 64)) : __props.category === "decisions" ? (openBlock(), createElementBlock(Fragment, { key: 2 }, [
            _hoisted_10$1,
            createBaseVNode("div", _hoisted_11$1, [
              (openBlock(), createElementBlock(Fragment, null, renderList([["1", "回复"], ["0", "观望"]], ([value, title]) => {
                return createBaseVNode("button", {
                  key: value,
                  type: "button",
                  class: normalizeClass(["type-option", { "type-option--selected": __props.model.reply === value }]),
                  "aria-pressed": __props.model.reply === value,
                  onClick: ($event) => toggle("reply", value)
                }, toDisplayString(title), 11, _hoisted_12$1);
              }), 64))
            ]),
            createVNode(_component_v_select, {
              modelValue: __props.model.kind,
              "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => __props.model.kind = $event),
              label: "执行状态",
              items: [all, ...unref(outcomes)],
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue", "items"]),
            createVNode(_component_v_select, {
              modelValue: __props.model.emotion,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => __props.model.emotion = $event),
              label: "规划情绪",
              items: [all, ...unref(emotions)],
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue", "items"]),
            createVNode(_component_v_select, {
              modelValue: __props.model.trigger,
              "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => __props.model.trigger = $event),
              label: "触发来源",
              items: [all, { title: "聊天消息", value: "message" }, { title: "空闲主动", value: "idle" }],
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue", "items"]),
            createVNode(_component_v_select, {
              modelValue: __props.model.required,
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => __props.model.required = $event),
              label: "是否必回复",
              items: [all, { title: "必回复", value: "1" }, { title: "普通评估", value: "0" }],
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ], 64)) : __props.category === "topics" ? (openBlock(), createElementBlock(Fragment, { key: 3 }, [
            createVNode(_component_v_text_field, {
              modelValue: __props.model.participant,
              "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => __props.model.participant = $event),
              label: "参与者或参与行为",
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue"]),
            createVNode(_component_v_text_field, {
              modelValue: __props.model.bot_reply,
              "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => __props.model.bot_reply = $event),
              label: "我的行为关键词",
              "hide-details": ""
            }, null, 8, ["modelValue"])
          ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 4 }, [
            createVNode(_component_v_select, {
              modelValue: __props.model.kind,
              "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => __props.model.kind = $event),
              label: "日记状态",
              items: [all, { title: "未封存", value: "0" }, { title: "已封存", value: "1" }],
              "hide-details": "",
              class: "mb-4"
            }, null, 8, ["modelValue", "items"]),
            createVNode(_component_v_select, {
              modelValue: __props.model.coverage_gap,
              "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => __props.model.coverage_gap = $event),
              label: "消息覆盖",
              items: [all, { title: "无缺口标记", value: "0" }, { title: "存在缺口", value: "1" }],
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ], 64)),
          createVNode(_component_v_divider, { class: "my-5" }),
          createVNode(_component_v_text_field, {
            modelValue: __props.model.start,
            "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => __props.model.start = $event),
            type: "date",
            label: "开始日期",
            "hide-details": "",
            class: "mb-4"
          }, null, 8, ["modelValue"]),
          createVNode(_component_v_text_field, {
            modelValue: __props.model.end,
            "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => __props.model.end = $event),
            type: "date",
            label: "结束日期",
            "hide-details": "",
            class: "mb-4"
          }, null, 8, ["modelValue"]),
          createVNode(_component_v_select, {
            modelValue: __props.model.sort,
            "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => __props.model.sort = $event),
            label: "排序",
            items: unref(sorts),
            "hide-details": ""
          }, null, 8, ["modelValue", "items"])
        ]),
        _: 1
      });
    };
  }
};
const FilterPanel = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-3baa6c1c"]]);
const _withScopeId$1 = (n) => (pushScopeId("data-v-1f89cea8"), n = n(), popScopeId(), n);
const _hoisted_1$3 = { class: "d-flex align-center flex-wrap ga-3 mb-4" };
const _hoisted_2$3 = { class: "text-body-2 text-medium-emphasis flex-grow-1" };
const _hoisted_3$3 = { class: "records-layout" };
const _hoisted_4$3 = ["inert", "aria-hidden"];
const _hoisted_5$2 = {
  key: 0,
  class: "text-body-2 text-break"
};
const _hoisted_6$2 = { class: "text-caption text-break" };
const _hoisted_7$2 = { class: "text-body-2 text-break" };
const _hoisted_8$1 = {
  key: 0,
  class: "text-caption"
};
const _hoisted_9 = /* @__PURE__ */ _withScopeId$1(() => /* @__PURE__ */ createBaseVNode("br", null, null, -1));
const _hoisted_10 = {
  key: 1,
  class: "decision-state d-flex flex-column align-start ga-1 py-1"
};
const _hoisted_11 = { class: "text-caption text-break" };
const _hoisted_12 = { class: "text-caption text-break" };
const _hoisted_13 = { key: 2 };
const _hoisted_14 = {
  key: 3,
  class: "text-caption"
};
const _hoisted_15 = {
  key: 0,
  class: "mt-3"
};
const _hoisted_16 = {
  key: 1,
  class: "mt-3"
};
const _hoisted_17 = /* @__PURE__ */ _withScopeId$1(() => /* @__PURE__ */ createBaseVNode("p", { class: "mt-3" }, "仅处理插件数据，不清除 AstrBot 原生对话。正在回复或整理时会拒绝删除，请稍后重试。", -1));
const _sfc_main$3 = {
  __name: "Records",
  props: { category: String, sessions: Array, refresh: Number, timezone: String },
  emits: ["changed"],
  setup(__props, { emit }) {
    const props = __props;
    const bridge2 = inject("bridge");
    const defaults = { q: "", sessions: [], chat_type: "", start: "", end: "", kind: "", sender: "", component: "", reply: "", emotion: "", required: "", trigger: "", participant: "", bot_reply: "", coverage_gap: "", sort: "timestamp:desc" };
    const filters = reactive({ ...defaults, sessions: [] });
    const filtersOpen = ref(true);
    const sessionTitles = computed(() => Object.fromEntries(props.sessions.map((item) => [item.umo, item.title])));
    const page = ref(1), limit = ref(25);
    const sort = computed({
      get() {
        const [key, order] = filters.sort.split(":");
        return [{ key, order }];
      },
      set(value) {
        filters.sort = value[0] ? `${value[0].key}:${value[0].order}` : "timestamp:desc";
      }
    });
    const rows = ref([]), total = ref(0), selected = ref([]), loading = ref(false), error = ref("");
    const detail = ref(null), confirm = ref(false), deleting = ref(false), success = ref("");
    let generation = 0, timer;
    const titles = { messages: "聊天记录", decisions: "最近反应", topics: "话题", diaries: "日记" };
    const headers = computed(() => [
      { title: "时间", key: "timestamp", width: 180 },
      { title: "会话", key: "conversation", sortable: false, width: 220 },
      { title: props.category === "decisions" ? "规划原因" : "内容", key: "headline" },
      { title: props.category === "messages" ? "发送者" : "状态", key: "state", sortable: false, width: 180 },
      { title: "操作", key: "actions", sortable: false, width: 120 }
    ]);
    function time(value) {
      return new Date(value * 1e3).toLocaleString("zh-CN", { timeZone: props.timezone, hour12: false });
    }
    async function load() {
      const current = ++generation;
      loading.value = true;
      error.value = "";
      selected.value = [];
      try {
        const [key, order] = filters.sort.split(":");
        const data = await bridge2.apiGet("records", { ...filters, sessions: JSON.stringify(filters.sessions), category: props.category, page: page.value, limit: limit.value, sort: key, order });
        if (current !== generation) return;
        rows.value = data.items;
        total.value = data.total;
        const lastPage = Math.max(1, Math.ceil(data.total / limit.value));
        if (page.value > lastPage) page.value = lastPage;
      } catch (e) {
        if (current === generation) error.value = e.message;
      } finally {
        if (current === generation) loading.value = false;
      }
    }
    function queue() {
      clearTimeout(timer);
      timer = setTimeout(load, 200);
    }
    watch(filters, () => {
      page.value = 1;
      queue();
    }, { deep: true });
    watch([page, limit, () => props.refresh], queue);
    queue();
    onBeforeUnmount(() => {
      clearTimeout(timer);
      generation++;
    });
    function removeOne(row) {
      selected.value = [row.key];
      confirm.value = true;
    }
    async function remove() {
      deleting.value = true;
      error.value = "";
      try {
        const result = await bridge2.apiPost("records/delete", { category: props.category, keys: [...selected.value] });
        confirm.value = false;
        detail.value = null;
        success.value = `已删除 ${result.deleted} 条${titles[props.category]}`;
        await load();
        emit("changed");
      } catch (e) {
        error.value = e.message;
        confirm.value = false;
      } finally {
        deleting.value = false;
      }
    }
    const detailFields = computed(() => {
      if (!detail.value) return {};
      const result = { ...detail.value };
      for (const key of ["key", "search", "headline", "timestamp", "kind", "scope"]) delete result[key];
      return result;
    });
    return (_ctx, _cache) => {
      const _component_v_alert = resolveComponent("v-alert");
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_expand_x_transition = resolveComponent("v-expand-x-transition");
      const _component_v_chip = resolveComponent("v-chip");
      const _component_v_data_table_server = resolveComponent("v-data-table-server");
      const _component_v_card = resolveComponent("v-card");
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_spacer = resolveComponent("v-spacer");
      const _component_v_card_actions = resolveComponent("v-card-actions");
      const _component_v_dialog = resolveComponent("v-dialog");
      return openBlock(), createElementBlock("section", null, [
        error.value ? (openBlock(), createBlock(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          class: "mb-4"
        }, {
          default: withCtx(() => [
            createTextVNode(toDisplayString(error.value), 1)
          ]),
          _: 1
        })) : createCommentVNode("", true),
        success.value ? (openBlock(), createBlock(_component_v_alert, {
          key: 1,
          type: "success",
          variant: "tonal",
          closable: "",
          class: "mb-4",
          "onClick:close": _cache[0] || (_cache[0] = ($event) => success.value = "")
        }, {
          default: withCtx(() => [
            createTextVNode(toDisplayString(success.value), 1)
          ]),
          _: 1
        })) : createCommentVNode("", true),
        createBaseVNode("div", _hoisted_1$3, [
          createVNode(_component_v_btn, {
            "prepend-icon": unref(mdiFilterVariant),
            "aria-expanded": filtersOpen.value,
            "aria-controls": "record-filters",
            onClick: _cache[1] || (_cache[1] = ($event) => filtersOpen.value = !filtersOpen.value)
          }, {
            default: withCtx(() => [
              createTextVNode(toDisplayString(filtersOpen.value ? "隐藏筛选" : "显示筛选"), 1)
            ]),
            _: 1
          }, 8, ["prepend-icon", "aria-expanded"]),
          createBaseVNode("div", _hoisted_2$3, "共 " + toDisplayString(total.value) + " 条 · 已选 " + toDisplayString(selected.value.length) + " 条（当前页） · " + toDisplayString(__props.timezone), 1),
          createVNode(_component_v_btn, {
            color: "error",
            "prepend-icon": unref(mdiDeleteOutline),
            disabled: !selected.value.length || loading.value,
            onClick: _cache[2] || (_cache[2] = ($event) => confirm.value = true)
          }, {
            default: withCtx(() => [
              createTextVNode("删除所选")
            ]),
            _: 1
          }, 8, ["prepend-icon", "disabled"])
        ]),
        createBaseVNode("div", _hoisted_3$3, [
          createVNode(_component_v_expand_x_transition, null, {
            default: withCtx(() => [
              withDirectives(createBaseVNode("div", {
                id: "record-filters",
                class: "filter-column",
                inert: !filtersOpen.value,
                "aria-hidden": !filtersOpen.value
              }, [
                createVNode(FilterPanel, {
                  category: __props.category,
                  model: filters,
                  sessions: __props.sessions,
                  active: filtersOpen.value,
                  onCollapse: _cache[3] || (_cache[3] = ($event) => filtersOpen.value = false),
                  onReset: _cache[4] || (_cache[4] = ($event) => Object.assign(filters, defaults, { sessions: [] }))
                }, null, 8, ["category", "model", "sessions", "active"])
              ], 8, _hoisted_4$3), [
                [vShow, filtersOpen.value]
              ])
            ]),
            _: 1
          }),
          createVNode(_component_v_card, {
            class: "records-list",
            rounded: "xl"
          }, {
            default: withCtx(() => [
              createVNode(_component_v_data_table_server, {
                modelValue: selected.value,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => selected.value = $event),
                page: page.value,
                "onUpdate:page": _cache[6] || (_cache[6] = ($event) => page.value = $event),
                "items-per-page": limit.value,
                "onUpdate:itemsPerPage": _cache[7] || (_cache[7] = ($event) => limit.value = $event),
                "sort-by": sort.value,
                "onUpdate:sortBy": _cache[8] || (_cache[8] = ($event) => sort.value = $event),
                class: "records-table",
                headers: headers.value,
                items: rows.value,
                "items-length": total.value,
                loading: loading.value,
                "items-per-page-options": [10, 25, 50, 100],
                "item-value": "key",
                "show-select": "",
                "select-strategy": "page",
                "must-sort": "",
                hover: ""
              }, {
                "item.timestamp": withCtx(({ item }) => [
                  createTextVNode(toDisplayString(time(item.timestamp)), 1)
                ]),
                "item.conversation": withCtx(({ item }) => [
                  sessionTitles.value[item.conversation] && sessionTitles.value[item.conversation] !== item.conversation ? (openBlock(), createElementBlock("div", _hoisted_5$2, toDisplayString(sessionTitles.value[item.conversation]), 1)) : createCommentVNode("", true),
                  createBaseVNode("span", _hoisted_6$2, toDisplayString(item.conversation), 1)
                ]),
                "item.headline": withCtx(({ item }) => {
                  var _a, _b;
                  return [
                    createBaseVNode("span", _hoisted_7$2, toDisplayString((_a = item.headline) == null ? void 0 : _a.slice(0, 180)) + toDisplayString(((_b = item.headline) == null ? void 0 : _b.length) > 180 ? "…" : ""), 1)
                  ];
                }),
                "item.state": withCtx(({ item }) => {
                  var _a, _b;
                  return [
                    __props.category === "messages" ? (openBlock(), createElementBlock("span", _hoisted_8$1, [
                      createTextVNode(toDisplayString(item.sender_name), 1),
                      _hoisted_9,
                      createTextVNode(toDisplayString(item.direction === "out" ? "机器人回复" : item.sender_id), 1)
                    ])) : __props.category === "decisions" ? (openBlock(), createElementBlock("div", _hoisted_10, [
                      createVNode(_component_v_chip, {
                        size: "small",
                        color: item.decision_json.reply ? "primary" : void 0
                      }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(item.decision_json.reply ? "回复" : "观望"), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      createBaseVNode("span", _hoisted_11, toDisplayString(((_a = unref(emotions).find((e) => e.value === item.decision_json.emotion.primary)) == null ? void 0 : _a.title) || item.decision_json.emotion.primary), 1),
                      createBaseVNode("span", _hoisted_12, toDisplayString(((_b = unref(outcomes).find((o) => o.value === item.outcome)) == null ? void 0 : _b.title) || item.outcome), 1)
                    ])) : __props.category === "diaries" ? (openBlock(), createElementBlock("span", _hoisted_13, toDisplayString(item.sealed ? "已封存" : "未封存") + " · " + toDisplayString(item.topic_count) + " 个话题", 1)) : (openBlock(), createElementBlock("span", _hoisted_14, toDisplayString(item.day), 1))
                  ];
                }),
                "item.actions": withCtx(({ item }) => [
                  createVNode(_component_v_btn, {
                    icon: unref(mdiEyeOutline),
                    "aria-label": "查看详情",
                    size: "small",
                    variant: "text",
                    onClick: ($event) => detail.value = item
                  }, null, 8, ["icon", "onClick"]),
                  createVNode(_component_v_btn, {
                    icon: unref(mdiDeleteOutline),
                    "aria-label": "删除记录",
                    size: "small",
                    variant: "text",
                    color: "error",
                    onClick: ($event) => removeOne(item)
                  }, null, 8, ["icon", "onClick"])
                ]),
                _: 1
              }, 8, ["modelValue", "page", "items-per-page", "sort-by", "headers", "items", "items-length", "loading"])
            ]),
            _: 1
          })
        ]),
        createVNode(_component_v_dialog, {
          "model-value": !!detail.value,
          "max-width": "1000",
          scrollable: "",
          "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => !$event && (detail.value = null))
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card, null, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, { class: "text-h6 pa-4 pb-0 pl-6" }, {
                  default: withCtx(() => [
                    createTextVNode(toDisplayString(titles[__props.category]) + "详情", 1)
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => [
                    createVNode(_sfc_main$5, { value: detailFields.value }, null, 8, ["value"])
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => [
                    createVNode(_component_v_spacer),
                    createVNode(_component_v_btn, {
                      onClick: _cache[9] || (_cache[9] = ($event) => detail.value = null)
                    }, {
                      default: withCtx(() => [
                        createTextVNode("关闭")
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["model-value"]),
        createVNode(_component_v_dialog, {
          modelValue: confirm.value,
          "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => confirm.value = $event),
          "max-width": "540",
          persistent: deleting.value
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card, null, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, { class: "text-h6 pa-4 pb-0 pl-6" }, {
                  default: withCtx(() => [
                    createTextVNode("确认删除")
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => [
                    createTextVNode(" 将永久删除所选 " + toDisplayString(selected.value.length) + " 条" + toDisplayString(titles[__props.category]) + "。 ", 1),
                    __props.category === "diaries" ? (openBlock(), createElementBlock("p", _hoisted_15, "这些日期下的话题会一并删除。")) : createCommentVNode("", true),
                    __props.category === "messages" ? (openBlock(), createElementBlock("p", _hoisted_16, "已有日记仍保留，消息累计序号不回退。当前群聊消息不足门槛时，会重新进入观察期。")) : createCommentVNode("", true),
                    _hoisted_17
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => [
                    createVNode(_component_v_spacer),
                    createVNode(_component_v_btn, {
                      disabled: deleting.value,
                      onClick: _cache[11] || (_cache[11] = ($event) => confirm.value = false)
                    }, {
                      default: withCtx(() => [
                        createTextVNode("取消")
                      ]),
                      _: 1
                    }, 8, ["disabled"]),
                    createVNode(_component_v_btn, {
                      color: "error",
                      loading: deleting.value,
                      onClick: remove
                    }, {
                      default: withCtx(() => [
                        createTextVNode("确认删除")
                      ]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue", "persistent"])
      ]);
    };
  }
};
const Records = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-1f89cea8"]]);
const _hoisted_1$2 = {
  key: 0,
  class: "mb-5"
};
const _hoisted_2$2 = { class: "d-flex align-center flex-wrap ga-2 mb-3" };
const _hoisted_3$2 = { class: "text-subtitle-1 font-weight-bold flex-grow-1" };
const _hoisted_4$2 = { class: "d-flex justify-space-between align-center mb-3" };
const _hoisted_5$1 = { class: "text-caption text-medium-emphasis" };
const _hoisted_6$1 = { class: "text-subtitle-2 mb-2" };
const _hoisted_7$1 = { class: "text-caption text-medium-emphasis" };
const _sfc_main$2 = {
  __name: "SchemaFields",
  props: { schema: Object, model: Object, choices: Object },
  setup(__props) {
    const props = __props;
    function visible(field) {
      return Object.entries(field.condition || {}).every(([key, value]) => props.model[key] === value);
    }
    function options(field) {
      if (field._special) return [{ title: "未选择", value: "" }, ...props.choices[field._special] || []];
      return (field.options || []).map((value, index) => {
        var _a;
        return { value, title: ((_a = field.labels) == null ? void 0 : _a[index]) || value };
      });
    }
    function add(key, field, templateKey) {
      const value = { __template_key: templateKey };
      for (const [name, item] of Object.entries(field.templates[templateKey].items)) value[name] = JSON.parse(JSON.stringify(item.default));
      props.model[key].push(value);
    }
    function updateNumber(key, value) {
      props.model[key] = value === "" ? "" : Number(value);
    }
    return (_ctx, _cache) => {
      const _component_v_btn = resolveComponent("v-btn");
      const _component_SchemaFields = resolveComponent("SchemaFields", true);
      const _component_v_card = resolveComponent("v-card");
      const _component_v_switch = resolveComponent("v-switch");
      const _component_v_textarea = resolveComponent("v-textarea");
      const _component_v_text_field = resolveComponent("v-text-field");
      const _component_v_slider = resolveComponent("v-slider");
      const _component_v_autocomplete = resolveComponent("v-autocomplete");
      const _component_v_combobox = resolveComponent("v-combobox");
      return openBlock(true), createElementBlock(Fragment, null, renderList(__props.schema, (field, key) => {
        return openBlock(), createElementBlock(Fragment, { key }, [
          visible(field) ? (openBlock(), createElementBlock("div", _hoisted_1$2, [
            field.type === "template_list" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
              createBaseVNode("div", _hoisted_2$2, [
                createBaseVNode("span", _hoisted_3$2, toDisplayString(field.description), 1),
                (openBlock(true), createElementBlock(Fragment, null, renderList(field.templates, (template, id) => {
                  return openBlock(), createBlock(_component_v_btn, {
                    key: id,
                    "prepend-icon": unref(mdiPlus),
                    size: "small",
                    onClick: ($event) => add(key, field, id)
                  }, {
                    default: withCtx(() => [
                      createTextVNode("添加" + toDisplayString(template.name), 1)
                    ]),
                    _: 2
                  }, 1032, ["prepend-icon", "onClick"]);
                }), 128))
              ]),
              (openBlock(true), createElementBlock(Fragment, null, renderList(__props.model[key], (item, index) => {
                return openBlock(), createBlock(_component_v_card, {
                  key: index,
                  class: "pa-4 mb-3"
                }, {
                  default: withCtx(() => [
                    createBaseVNode("div", _hoisted_4$2, [
                      createBaseVNode("span", null, toDisplayString(item.name || `条目 ${index + 1}`), 1),
                      createVNode(_component_v_btn, {
                        icon: unref(mdiDeleteOutline),
                        "aria-label": "移除时段",
                        variant: "text",
                        size: "small",
                        color: "error",
                        onClick: ($event) => __props.model[key].splice(index, 1)
                      }, null, 8, ["icon", "onClick"])
                    ]),
                    createVNode(_component_SchemaFields, {
                      schema: field.templates[item.__template_key || Object.keys(field.templates)[0]].items,
                      model: item,
                      choices: __props.choices
                    }, null, 8, ["schema", "model", "choices"])
                  ]),
                  _: 2
                }, 1024);
              }), 128)),
              createBaseVNode("p", _hoisted_5$1, toDisplayString(field.hint), 1)
            ], 64)) : field.type === "bool" ? (openBlock(), createBlock(_component_v_switch, {
              key: 1,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              color: "primary",
              inset: ""
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint"])) : field.type === "text" ? (openBlock(), createBlock(_component_v_textarea, {
              key: 2,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              variant: "outlined",
              "auto-grow": "",
              rows: "3"
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint"])) : field.slider ? (openBlock(), createElementBlock(Fragment, { key: 3 }, [
              createBaseVNode("div", _hoisted_6$1, toDisplayString(field.description), 1),
              createVNode(_component_v_slider, {
                modelValue: __props.model[key],
                "onUpdate:modelValue": ($event) => __props.model[key] = $event,
                min: field.slider.min,
                max: field.slider.max,
                step: field.slider.step,
                color: "primary",
                "thumb-label": "",
                "hide-details": ""
              }, {
                append: withCtx(() => [
                  createVNode(_component_v_text_field, {
                    "model-value": __props.model[key],
                    "aria-label": field.description,
                    type: "number",
                    min: field.slider.min,
                    max: field.slider.max,
                    step: field.slider.step,
                    width: "110",
                    "hide-details": "",
                    "onUpdate:modelValue": ($event) => updateNumber(key, $event)
                  }, null, 8, ["model-value", "aria-label", "min", "max", "step", "onUpdate:modelValue"])
                ]),
                _: 2
              }, 1032, ["modelValue", "onUpdate:modelValue", "min", "max", "step"]),
              createBaseVNode("p", _hoisted_7$1, toDisplayString(field.hint), 1)
            ], 64)) : field.options || field._special ? (openBlock(), createBlock(_component_v_autocomplete, {
              key: 4,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              items: options(field),
              multiple: field.type === "list",
              chips: field.type === "list",
              "closable-chips": field.type === "list"
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint", "items", "multiple", "chips", "closable-chips"])) : field.type === "list" ? (openBlock(), createBlock(_component_v_combobox, {
              key: 5,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              multiple: "",
              chips: "",
              "closable-chips": ""
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint"])) : ["int", "float"].includes(field.type) ? (openBlock(), createBlock(_component_v_text_field, {
              key: 6,
              "model-value": __props.model[key],
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              type: "number",
              step: field.type === "int" ? 1 : "any",
              "onUpdate:modelValue": ($event) => updateNumber(key, $event)
            }, null, 8, ["model-value", "label", "hint", "step", "onUpdate:modelValue"])) : (openBlock(), createBlock(_component_v_text_field, {
              key: 7,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": ""
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint"]))
          ])) : createCommentVNode("", true)
        ], 64);
      }), 128);
    };
  }
};
const _hoisted_1$1 = { class: "d-flex align-center flex-wrap ga-3 mb-4" };
const _hoisted_2$1 = { class: "text-body-2 flex-grow-1" };
const _hoisted_3$1 = /* @__PURE__ */ createBaseVNode("p", { class: "mb-4" }, "清除全部 Humanization 会话的聊天记录、话题、日记、最近反应、辅助模型进度与计数，并为对应主模型开启空白对话。包含当前未启用的历史会话，删除后无法撤销。", -1);
const _hoisted_4$1 = { class: "mb-4" };
const _sfc_main$1 = {
  __name: "Settings",
  emits: ["changed"],
  setup(__props, { expose: __expose, emit }) {
    const bridge2 = inject("bridge");
    const data = ref(null), model = ref(null), baseline = ref("");
    const loading = ref(false), saving = ref(false), confirm = ref(false), error = ref(""), success = ref("");
    const dirty = computed(() => model.value && JSON.stringify(model.value) !== baseline.value);
    const resetDialog = ref(false), confirmation = ref(""), resetting = ref(false), resetError = ref("");
    const busy = computed(() => saving.value || resetting.value);
    async function load() {
      loading.value = true;
      error.value = "";
      try {
        data.value = await bridge2.apiGet("settings");
        model.value = JSON.parse(JSON.stringify(data.value.config));
        baseline.value = JSON.stringify(model.value);
      } catch (e) {
        error.value = e.message;
      } finally {
        loading.value = false;
      }
    }
    async function save() {
      saving.value = true;
      error.value = "";
      try {
        await bridge2.apiPost("settings/save", { config: JSON.parse(JSON.stringify(model.value)), revision: data.value.revision });
        success.value = "配置已保存，插件已重载";
        await load();
        return true;
      } catch (e) {
        error.value = e.message;
        return false;
      } finally {
        saving.value = false;
        confirm.value = false;
      }
    }
    async function resetAll() {
      resetting.value = true;
      resetError.value = "";
      success.value = "";
      try {
        const result = await bridge2.apiPost("data/reset-all", { confirmation: confirmation.value });
        resetDialog.value = false;
        confirmation.value = "";
        success.value = `已清除 ${result.conversations} 个会话的数据，并为主模型开启空白对话`;
        emit("changed");
      } catch (e) {
        resetError.value = e.message;
      } finally {
        resetting.value = false;
      }
    }
    onMounted(load);
    __expose({ dirty, saving: busy, save });
    return (_ctx, _cache) => {
      const _component_v_alert = resolveComponent("v-alert");
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_progress_linear = resolveComponent("v-progress-linear");
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_card = resolveComponent("v-card");
      const _component_v_icon = resolveComponent("v-icon");
      const _component_v_spacer = resolveComponent("v-spacer");
      const _component_v_card_actions = resolveComponent("v-card-actions");
      const _component_v_dialog = resolveComponent("v-dialog");
      const _component_v_text_field = resolveComponent("v-text-field");
      const _component_v_snackbar = resolveComponent("v-snackbar");
      return openBlock(), createElementBlock(Fragment, null, [
        error.value ? (openBlock(), createBlock(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          class: "mb-4"
        }, {
          default: withCtx(() => [
            createTextVNode(toDisplayString(error.value), 1)
          ]),
          _: 1
        })) : createCommentVNode("", true),
        success.value ? (openBlock(), createBlock(_component_v_alert, {
          key: 1,
          type: "success",
          variant: "tonal",
          class: "mb-4"
        }, {
          default: withCtx(() => [
            createTextVNode(toDisplayString(success.value), 1)
          ]),
          _: 1
        })) : createCommentVNode("", true),
        createVNode(_component_v_alert, {
          type: "info",
          variant: "tonal",
          class: "mb-4"
        }, {
          default: withCtx(() => [
            createTextVNode("配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。")
          ]),
          _: 1
        }),
        createBaseVNode("div", _hoisted_1$1, [
          createBaseVNode("span", _hoisted_2$1, toDisplayString(dirty.value ? "有未保存的修改" : "配置已同步"), 1),
          createVNode(_component_v_btn, {
            "prepend-icon": unref(mdiRefresh),
            loading: loading.value,
            disabled: busy.value || !!dirty.value,
            onClick: load
          }, {
            default: withCtx(() => [
              createTextVNode("重新载入")
            ]),
            _: 1
          }, 8, ["prepend-icon", "loading", "disabled"]),
          createVNode(_component_v_btn, {
            color: "primary",
            "prepend-icon": unref(mdiContentSaveOutline),
            disabled: !dirty.value || loading.value || resetting.value,
            loading: saving.value,
            onClick: _cache[0] || (_cache[0] = ($event) => confirm.value = true)
          }, {
            default: withCtx(() => [
              createTextVNode("保存并重载")
            ]),
            _: 1
          }, 8, ["prepend-icon", "disabled", "loading"])
        ]),
        loading.value ? (openBlock(), createBlock(_component_v_progress_linear, {
          key: 2,
          indeterminate: "",
          color: "primary"
        })) : createCommentVNode("", true),
        data.value && model.value ? (openBlock(), createElementBlock(Fragment, { key: 3 }, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(data.value.schema, (section, key) => {
            return openBlock(), createBlock(_component_v_card, {
              key,
              tag: "section",
              "aria-label": section.description,
              class: "mb-5",
              rounded: "xl"
            }, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, {
                  tag: "h2",
                  class: "text-h6 pa-5 text-wrap"
                }, {
                  default: withCtx(() => [
                    createTextVNode(toDisplayString(section.description), 1)
                  ]),
                  _: 2
                }, 1024),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => [
                    createVNode(_sfc_main$2, {
                      schema: section.items,
                      model: model.value[key],
                      choices: data.value.choices
                    }, null, 8, ["schema", "model", "choices"])
                  ]),
                  _: 2
                }, 1024)
              ]),
              _: 2
            }, 1032, ["aria-label"]);
          }), 128)),
          createVNode(_component_v_card, {
            tag: "section",
            "aria-label": "危险操作区",
            color: "error",
            variant: "outlined",
            class: "my-6",
            rounded: "xl"
          }, {
            default: withCtx(() => [
              createVNode(_component_v_card_title, {
                tag: "h2",
                class: "text-h6 pa-5 d-flex align-center ga-2"
              }, {
                default: withCtx(() => [
                  createVNode(_component_v_icon, { icon: unref(mdiDeleteAlertOutline) }, null, 8, ["icon"]),
                  createTextVNode("危险操作区")
                ]),
                _: 1
              }),
              createVNode(_component_v_card_text, null, {
                default: withCtx(() => [
                  _hoisted_3$1,
                  createVNode(_component_v_btn, {
                    color: "error",
                    variant: "flat",
                    "prepend-icon": unref(mdiDeleteAlertOutline),
                    disabled: busy.value || loading.value,
                    onClick: _cache[1] || (_cache[1] = ($event) => {
                      confirmation.value = "";
                      resetError.value = "";
                      resetDialog.value = true;
                    })
                  }, {
                    default: withCtx(() => [
                      createTextVNode("清除所有会话数据")
                    ]),
                    _: 1
                  }, 8, ["prepend-icon", "disabled"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ], 64)) : createCommentVNode("", true),
        createVNode(_component_v_dialog, {
          modelValue: confirm.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => confirm.value = $event),
          "max-width": "540",
          persistent: saving.value
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card, null, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, { class: "text-h6 pa-4 pb-0 pl-6" }, {
                  default: withCtx(() => [
                    createTextVNode("保存配置")
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => [
                    createTextVNode(" 保存后将重载 Humanization，进行中的回复可能中断。 ")
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => [
                    createVNode(_component_v_spacer),
                    createVNode(_component_v_btn, {
                      disabled: saving.value,
                      onClick: _cache[2] || (_cache[2] = ($event) => confirm.value = false)
                    }, {
                      default: withCtx(() => [
                        createTextVNode("取消")
                      ]),
                      _: 1
                    }, 8, ["disabled"]),
                    createVNode(_component_v_btn, {
                      color: "primary",
                      loading: saving.value,
                      onClick: save
                    }, {
                      default: withCtx(() => [
                        createTextVNode("确认保存")
                      ]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue", "persistent"]),
        createVNode(_component_v_dialog, {
          modelValue: resetDialog.value,
          "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => resetDialog.value = $event),
          "max-width": "600",
          persistent: resetting.value
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card, null, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, { class: "text-h6 pa-4 pb-0 pl-6 text-error" }, {
                  default: withCtx(() => [
                    createTextVNode("清除所有会话数据")
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => {
                    var _a;
                    return [
                      createVNode(_component_v_alert, {
                        type: "error",
                        variant: "tonal",
                        class: "mb-4"
                      }, {
                        default: withCtx(() => [
                          createTextVNode("此操作会立即执行，无法撤销。正在生成的回复和日记整理会中断。AstrBot 原生旧对话与日志文件保留。")
                        ]),
                        _: 1
                      }),
                      createBaseVNode("p", _hoisted_4$1, [
                        createTextVNode("请输入 "),
                        createBaseVNode("strong", null, toDisplayString((_a = data.value) == null ? void 0 : _a.reset_confirmation), 1),
                        createTextVNode(" 确认清除；不会保存当前未提交的设置。")
                      ]),
                      createVNode(_component_v_text_field, {
                        modelValue: confirmation.value,
                        "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => confirmation.value = $event),
                        label: "确认信息",
                        autocomplete: "off",
                        disabled: resetting.value,
                        "hide-details": ""
                      }, null, 8, ["modelValue", "disabled"]),
                      resetError.value ? (openBlock(), createBlock(_component_v_alert, {
                        key: 0,
                        type: "error",
                        variant: "tonal",
                        class: "mt-4"
                      }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(resetError.value), 1)
                        ]),
                        _: 1
                      })) : createCommentVNode("", true)
                    ];
                  }),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => {
                    var _a;
                    return [
                      createVNode(_component_v_spacer),
                      createVNode(_component_v_btn, {
                        variant: "text",
                        disabled: resetting.value,
                        onClick: _cache[5] || (_cache[5] = ($event) => resetDialog.value = false)
                      }, {
                        default: withCtx(() => [
                          createTextVNode("取消")
                        ]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_v_btn, {
                        color: "error",
                        variant: "tonal",
                        loading: resetting.value,
                        disabled: confirmation.value !== ((_a = data.value) == null ? void 0 : _a.reset_confirmation),
                        onClick: resetAll
                      }, {
                        default: withCtx(() => [
                          createTextVNode("确认清除")
                        ]),
                        _: 1
                      }, 8, ["loading", "disabled"])
                    ];
                  }),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue", "persistent"]),
        createVNode(_component_v_snackbar, {
          "model-value": !!dirty.value,
          timeout: -1,
          location: "bottom left",
          color: "surface",
          rounded: "pill"
        }, {
          default: withCtx(() => [
            createVNode(_component_v_icon, {
              icon: unref(mdiAlertCircleOutline),
              size: "20",
              class: "mr-2"
            }, null, 8, ["icon"]),
            createTextVNode("Humanization 配置尚未保存，请点击“保存并重载”。 ")
          ]),
          _: 1
        }, 8, ["model-value"])
      ], 64);
    };
  }
};
const _withScopeId = (n) => (pushScopeId("data-v-ebacd770"), n = n(), popScopeId(), n);
const _hoisted_1 = { class: "d-flex align-center flex-wrap ga-3 mb-4" };
const _hoisted_2 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("div", { class: "flex-grow-1" }, [
  /* @__PURE__ */ createBaseVNode("h1", { class: "text-h5 font-weight-bold" }, "Humanization"),
  /* @__PURE__ */ createBaseVNode("p", { class: "text-body-2 text-medium-emphasis mt-1" }, "聊天感知、行为规划与话题日记")
], -1));
const _hoisted_3 = { class: "data-tabs-scroll mb-4" };
const _hoisted_4 = {
  class: "data-tabs",
  role: "tablist",
  "aria-label": "Humanization 功能"
};
const _hoisted_5 = ["aria-selected", "disabled", "onClick"];
const _hoisted_6 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("span", null, "未保存的更改", -1));
const _hoisted_7 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("p", { class: "font-weight-bold mb-2" }, "Humanization 配置有未保存的更改，切换前是否保存？", -1));
const _hoisted_8 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("p", { class: "text-body-2 text-medium-emphasis" }, "确定：保存并重载插件后切换；取消：放弃更改并切换；关闭弹窗：继续编辑。", -1));
const _sfc_main = {
  __name: "App",
  setup(__props) {
    const bridge2 = inject("bridge");
    const tab = ref("overview");
    const settings = ref(null);
    const pendingTab = ref(null);
    const switching = ref(false);
    const scope = ref("");
    const overview = ref({ stats: {}, sessions: [], timezone: "Asia/Shanghai" });
    const error = ref("");
    const loading = ref(false);
    const refresh = ref(0);
    let generation = 0;
    const tabs = [
      ["overview", "统计", mdiChartBar],
      ["messages", "聊天", mdiMessageTextOutline],
      ["decisions", "最近反应", mdiHeartOutline],
      ["topics", "话题", mdiForumOutline],
      ["diaries", "日记", mdiBookOpenPageVariantOutline],
      ["settings", "设置", mdiCogOutline]
    ];
    async function load() {
      const current = ++generation;
      loading.value = true;
      error.value = "";
      try {
        const data = await bridge2.apiGet("overview", { scope: scope.value });
        if (current === generation) overview.value = data;
      } catch (e) {
        if (current === generation) error.value = e.message;
      } finally {
        if (current === generation) loading.value = false;
      }
    }
    function reload() {
      refresh.value++;
      load();
    }
    function navigate(value) {
      var _a, _b;
      if (value === tab.value || switching.value || ((_a = settings.value) == null ? void 0 : _a.saving)) return;
      if (tab.value === "settings" && ((_b = settings.value) == null ? void 0 : _b.dirty)) pendingTab.value = value;
      else tab.value = value;
    }
    async function leaveSettings(save) {
      switching.value = true;
      try {
        if (!save || await settings.value.save()) tab.value = pendingTab.value;
      } finally {
        pendingTab.value = null;
        switching.value = false;
      }
    }
    watch(scope, load);
    onMounted(load);
    return (_ctx, _cache) => {
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_icon = resolveComponent("v-icon");
      const _component_v_alert = resolveComponent("v-alert");
      const _component_v_autocomplete = resolveComponent("v-autocomplete");
      const _component_v_container = resolveComponent("v-container");
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_spacer = resolveComponent("v-spacer");
      const _component_v_card_actions = resolveComponent("v-card-actions");
      const _component_v_card = resolveComponent("v-card");
      const _component_v_dialog = resolveComponent("v-dialog");
      const _component_v_main = resolveComponent("v-main");
      const _component_v_app = resolveComponent("v-app");
      return openBlock(), createBlock(_component_v_app, null, {
        default: withCtx(() => [
          createVNode(_component_v_main, null, {
            default: withCtx(() => [
              createVNode(_component_v_container, {
                fluid: "",
                class: "pa-4 pa-md-6"
              }, {
                default: withCtx(() => [
                  createBaseVNode("div", _hoisted_1, [
                    _hoisted_2,
                    createVNode(_component_v_btn, {
                      "prepend-icon": unref(mdiRefresh),
                      loading: loading.value,
                      onClick: reload
                    }, {
                      default: withCtx(() => [
                        createTextVNode("刷新数据")
                      ]),
                      _: 1
                    }, 8, ["prepend-icon", "loading"])
                  ]),
                  createBaseVNode("div", _hoisted_3, [
                    createBaseVNode("nav", _hoisted_4, [
                      (openBlock(), createElementBlock(Fragment, null, renderList(tabs, ([value, title, icon]) => {
                        var _a;
                        return createBaseVNode("button", {
                          key: value,
                          type: "button",
                          role: "tab",
                          class: normalizeClass(["data-tab", { "data-tab--active": tab.value === value }]),
                          "aria-selected": tab.value === value,
                          disabled: switching.value || ((_a = settings.value) == null ? void 0 : _a.saving),
                          onClick: ($event) => navigate(value)
                        }, [
                          createVNode(_component_v_icon, {
                            icon,
                            size: "17"
                          }, null, 8, ["icon"]),
                          createBaseVNode("span", null, toDisplayString(title), 1)
                        ], 10, _hoisted_5);
                      }), 64))
                    ])
                  ]),
                  error.value ? (openBlock(), createBlock(_component_v_alert, {
                    key: 0,
                    type: "error",
                    variant: "tonal",
                    class: "mb-4"
                  }, {
                    default: withCtx(() => [
                      createTextVNode(toDisplayString(error.value), 1)
                    ]),
                    _: 1
                  })) : createCommentVNode("", true),
                  tab.value === "overview" ? (openBlock(), createBlock(_component_v_autocomplete, {
                    key: 1,
                    modelValue: scope.value,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => scope.value = $event),
                    items: [{ title: "全部会话", value: "" }, ...overview.value.sessions],
                    label: "统计会话范围",
                    "hide-details": "",
                    class: "mb-5"
                  }, null, 8, ["modelValue", "items"])) : createCommentVNode("", true),
                  tab.value === "overview" ? (openBlock(), createBlock(_sfc_main$6, {
                    key: 2,
                    stats: overview.value.stats,
                    onBrowse: navigate
                  }, null, 8, ["stats"])) : tab.value === "settings" ? (openBlock(), createBlock(_sfc_main$1, {
                    key: 3,
                    ref_key: "settings",
                    ref: settings,
                    onChanged: load
                  }, null, 512)) : (openBlock(), createBlock(Records, {
                    key: tab.value,
                    category: tab.value,
                    sessions: overview.value.sessions,
                    refresh: refresh.value,
                    timezone: overview.value.timezone,
                    onChanged: load
                  }, null, 8, ["category", "sessions", "refresh", "timezone"]))
                ]),
                _: 1
              }),
              createVNode(_component_v_dialog, {
                "model-value": pendingTab.value !== null,
                persistent: "",
                "max-width": "540"
              }, {
                default: withCtx(() => [
                  createVNode(_component_v_card, null, {
                    default: withCtx(() => [
                      createVNode(_component_v_card_title, { class: "text-h6 pa-4 pb-0 pl-6 d-flex align-center justify-space-between" }, {
                        default: withCtx(() => [
                          _hoisted_6,
                          createVNode(_component_v_btn, {
                            icon: unref(mdiClose),
                            "aria-label": "继续编辑",
                            variant: "text",
                            disabled: switching.value,
                            onClick: _cache[1] || (_cache[1] = ($event) => pendingTab.value = null)
                          }, null, 8, ["icon", "disabled"])
                        ]),
                        _: 1
                      }),
                      createVNode(_component_v_card_text, null, {
                        default: withCtx(() => [
                          _hoisted_7,
                          _hoisted_8
                        ]),
                        _: 1
                      }),
                      createVNode(_component_v_card_actions, null, {
                        default: withCtx(() => [
                          createVNode(_component_v_spacer),
                          createVNode(_component_v_btn, {
                            variant: "text",
                            disabled: switching.value,
                            onClick: _cache[2] || (_cache[2] = ($event) => leaveSettings(false))
                          }, {
                            default: withCtx(() => [
                              createTextVNode("取消")
                            ]),
                            _: 1
                          }, 8, ["disabled"]),
                          createVNode(_component_v_btn, {
                            color: "error",
                            variant: "tonal",
                            loading: switching.value,
                            onClick: _cache[3] || (_cache[3] = ($event) => leaveSettings(true))
                          }, {
                            default: withCtx(() => [
                              createTextVNode("确定")
                            ]),
                            _: 1
                          }, 8, ["loading"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["model-value"])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
};
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-ebacd770"]]);
const vuetify = createVuetify({
  components: {
    VApp,
    VAlert,
    VAutocomplete,
    VBtn,
    VCard,
    VCardActions,
    VCardText,
    VCardTitle,
    VChip,
    VCheckboxBtn,
    VCombobox,
    VDataTableServer,
    VDialog,
    VDivider,
    VIcon,
    VMain,
    VListItem,
    VProgressLinear,
    VContainer,
    VRow,
    VCol,
    VSpacer,
    VSelect,
    VSlider,
    VSnackbar,
    VSwitch,
    VTable,
    VTextField,
    VTextarea,
    VExpandXTransition
  },
  icons: { defaultSet: "mdi", aliases, sets: { mdi } },
  locale: { locale: "zhHans", messages: { zhHans } },
  theme: {
    defaultTheme: "light",
    themes: {
      light: { colors: { primary: "#3c96ca", secondary: "#2f86bd", background: "#ffffff", surface: "#ffffff", error: "#f44336" } },
      dark: { dark: true, colors: { primary: "#5ba4d4", secondary: "#4a95c4", background: "#1a1a1a", surface: "#242424", "on-background": "#e8eaed", "on-surface": "#e8eaed", error: "#ff4d4f" } }
    }
  },
  defaults: {
    VBtn: { variant: "tonal" },
    VTextField: { variant: "outlined", density: "comfortable" },
    VSelect: { variant: "outlined", density: "comfortable" },
    VAutocomplete: { variant: "outlined", density: "comfortable" },
    VCombobox: { variant: "outlined", density: "comfortable" },
    VCard: { variant: "flat", border: true, rounded: "lg" }
  }
});
const bridge = window.AstrBotPluginView;
if (bridge) {
  bridge.ready().then((context) => {
    const setTheme = (ctx) => {
      vuetify.theme.global.name.value = ctx.isDark ? "dark" : "light";
    };
    setTheme(context);
    const off = bridge.onContext(setTheme);
    window.addEventListener("beforeunload", off, { once: true });
    createApp(App).provide("bridge", bridge).use(vuetify).mount("#app");
  }).catch((error) => {
    document.getElementById("app").textContent = error.message;
  });
} else {
  document.getElementById("app").textContent = "请从 AstrBot 控制面板打开 Humanization 视图";
}

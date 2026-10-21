import { r as resolveComponent, o as openBlock, c as createElementBlock, a as createVNode, w as withCtx, F as Fragment, b as renderList, d as createBaseVNode, t as toDisplayString, e as createTextVNode, f as computed, g as createCommentVNode, h as createBlock, i as ref, j as watch, u as unref, m as mdiFilterRemoveOutline, k as mdiChevronLeft, l as mdiMagnify, n as mergeProps, p as normalizeClass, q as pushScopeId, s as popScopeId, v as onBeforeUnmount, x as normalizeStyle, y as withModifiers, z as mdiArrowUpDown, A as withKeys, B as inject, C as reactive, D as mdiFilterVariant, E as mdiDeleteOutline, G as withDirectives, H as vShow, I as mdiEyeOutline, J as mdiChevronDown, K as mdiPlus, L as mdiFileCompare, M as mdiClose, N as mdiRestore, O as onMounted, P as mdiRefresh, Q as mdiContentSaveOutline, R as mdiMenu, S as mdiDeleteAlertOutline, T as mdiTextBoxOutline, U as mdiShieldAccountOutline, V as mdiMessageTextOutline, W as mdiHeadCogOutline, X as mdiAccountGroupOutline, Y as mdiAlertCircleOutline, Z as mdiChartBar, _ as mdiHeartOutline, $ as mdiForumOutline, a0 as mdiBookOpenPageVariantOutline, a1 as mdiCogOutline, a2 as createVuetify, a3 as createApp, a4 as zhHans, a5 as mdi, a6 as aliases, a7 as VExpandXTransition, a8 as VTextarea, a9 as VTextField, aa as VTable, ab as VSwitch, ac as VSnackbar, ad as VSlider, ae as VSelect, af as VSpacer, ag as VCol, ah as VRow, ai as VContainer, aj as VProgressLinear, ak as VMenu, al as VListItem, am as VList, an as VMain, ao as VIcon, ap as VDivider, aq as VDialog, ar as VDataTableServer, as as VCombobox, at as VCheckboxBtn, au as VChip, av as VCardTitle, aw as VCardText, ax as VCardActions, ay as VCard, az as VBtn, aA as VAutocomplete, aB as VAlert, aC as VApp } from "./assets/vendor.js";
const _hoisted_1$b = { class: "text-body-2 text-medium-emphasis mb-3" };
const _hoisted_2$a = { class: "text-h4 font-weight-bold" };
const _sfc_main$b = {
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
                      createBaseVNode("div", _hoisted_1$b, toDisplayString(label), 1),
                      createBaseVNode("div", _hoisted_2$a, toDisplayString((__props.stats[key] || 0).toLocaleString()), 1)
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
const _hoisted_1$a = {
  key: 0,
  class: "text-medium-emphasis"
};
const _hoisted_2$9 = {
  key: 1,
  class: "d-flex flex-column ga-2"
};
const _hoisted_3$9 = {
  key: 0,
  class: "text-medium-emphasis"
};
const _hoisted_4$9 = { class: "text-medium-emphasis text-no-wrap align-top py-2" };
const _hoisted_5$8 = { class: "text-break py-2" };
const _hoisted_6$8 = {
  key: 3,
  class: "text-body-2 text-pre-wrap text-break"
};
const _sfc_main$a = {
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
      return parsed.value === null ? (openBlock(), createElementBlock("div", _hoisted_1$a, "—")) : Array.isArray(parsed.value) ? (openBlock(), createElementBlock("div", _hoisted_2$9, [
        !parsed.value.length ? (openBlock(), createElementBlock("span", _hoisted_3$9, "无")) : createCommentVNode("", true),
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
                createBaseVNode("td", _hoisted_4$9, toDisplayString(labels[key] || key), 1),
                createBaseVNode("td", _hoisted_5$8, [
                  createVNode(_component_JsonValue, { value: item }, null, 8, ["value"])
                ])
              ]);
            }), 128))
          ])
        ]),
        _: 1
      })) : (openBlock(), createElementBlock("div", _hoisted_6$8, toDisplayString(parsed.value === true ? "是" : parsed.value === false ? "否" : parsed.value), 1));
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
function sessionLabel(umo, name) {
  const [platform, kind, ...parts] = umo.split(":");
  const id = parts.join(":");
  const label = name && name !== umo ? name : id;
  return `${platform} · ${kind === "GroupMessage" ? "群聊" : "私聊"} · ${label}`;
}
const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};
const _withScopeId$6 = (n) => (pushScopeId("data-v-92641de0"), n = n(), popScopeId(), n);
const _hoisted_1$9 = { class: "d-flex align-center ga-1 mb-4" };
const _hoisted_2$8 = /* @__PURE__ */ _withScopeId$6(() => /* @__PURE__ */ createBaseVNode("span", { class: "text-subtitle-1 font-weight-bold flex-grow-1" }, "筛选", -1));
const _hoisted_3$8 = {
  key: 0,
  class: "text-caption text-medium-emphasis mt-2"
};
const _hoisted_4$8 = /* @__PURE__ */ _withScopeId$6(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label mt-5" }, "对话类型", -1));
const _hoisted_5$7 = { class: "type-options" };
const _hoisted_6$7 = ["aria-pressed", "onClick"];
const _hoisted_7$6 = /* @__PURE__ */ _withScopeId$6(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label" }, "消息方向", -1));
const _hoisted_8$4 = { class: "type-options mb-4" };
const _hoisted_9$3 = ["aria-pressed", "onClick"];
const _hoisted_10$3 = /* @__PURE__ */ _withScopeId$6(() => /* @__PURE__ */ createBaseVNode("p", { class: "filter-label" }, "回复决定", -1));
const _hoisted_11$1 = { class: "type-options mb-4" };
const _hoisted_12$1 = ["aria-pressed", "onClick"];
const _sfc_main$9 = {
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
      return `${sessionLabel(item.raw.umo, item.raw.title)} ${item.raw.umo}`.toLocaleLowerCase().includes(search);
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
          createBaseVNode("div", _hoisted_1$9, [
            _hoisted_2$8,
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
                title: unref(sessionLabel)(item.raw.umo, item.raw.title),
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
          !__props.sessions.length ? (openBlock(), createElementBlock("p", _hoisted_3$8, "尚无已启用的会话")) : createCommentVNode("", true),
          _hoisted_4$8,
          createBaseVNode("div", _hoisted_5$7, [
            (openBlock(), createElementBlock(Fragment, null, renderList([["group", "群聊"], ["private", "私聊"]], ([value, title]) => {
              return createBaseVNode("button", {
                key: value,
                type: "button",
                class: normalizeClass(["type-option", { "type-option--selected": __props.model.chat_type === value }]),
                "aria-pressed": __props.model.chat_type === value,
                onClick: ($event) => toggle("chat_type", value)
              }, toDisplayString(title), 11, _hoisted_6$7);
            }), 64))
          ]),
          createVNode(_component_v_divider, { class: "my-5" }),
          __props.category === "messages" ? (openBlock(), createElementBlock(Fragment, { key: 1 }, [
            _hoisted_7$6,
            createBaseVNode("div", _hoisted_8$4, [
              (openBlock(), createElementBlock(Fragment, null, renderList([["in", "收到消息"], ["out", "发出回复"]], ([value, title]) => {
                return createBaseVNode("button", {
                  key: value,
                  type: "button",
                  class: normalizeClass(["type-option", { "type-option--selected": __props.model.kind === value }]),
                  "aria-pressed": __props.model.kind === value,
                  onClick: ($event) => toggle("kind", value)
                }, toDisplayString(title), 11, _hoisted_9$3);
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
            _hoisted_10$3,
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
const FilterPanel = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-92641de0"]]);
const _hoisted_1$8 = ["aria-sort", "onClick"];
const _hoisted_2$7 = ["aria-label", "onClick"];
const _hoisted_3$7 = { key: 1 };
const _hoisted_4$7 = ["aria-label", "aria-valuenow", "aria-valuemin", "onPointerdown", "onDblclick", "onKeydown"];
const _sfc_main$8 = /* @__PURE__ */ Object.assign({ inheritAttrs: false }, {
  __name: "ResizableHeaders",
  props: { columns: Array, widths: Object, defaults: Object, sortBy: Array, isSorted: Function, toggleSort: Function, getSortIcon: Function, allSelected: Boolean, someSelected: Boolean, selectAll: Function },
  emits: ["resize"],
  setup(__props, { emit }) {
    const minimum = (key) => ({ timestamp: 144, conversation: 128, headline: 160, state: 112, actions: 88 })[key] || 48;
    let dragging;
    function resize(key, width) {
      emit("resize", { key, width: Math.max(minimum(key), Math.round(width)) });
    }
    function move(event) {
      if (dragging) resize(dragging.key, dragging.width + event.clientX - dragging.x);
    }
    function stop() {
      dragging = null;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    }
    function start(event, key) {
      event.preventDefault();
      stop();
      dragging = { key, x: event.clientX, width: event.currentTarget.closest("th").getBoundingClientRect().width };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    }
    onBeforeUnmount(stop);
    return (_ctx, _cache) => {
      const _component_v_checkbox_btn = resolveComponent("v-checkbox-btn");
      const _component_v_icon = resolveComponent("v-icon");
      return openBlock(), createElementBlock("tr", null, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(__props.columns, (column) => {
          var _a;
          return openBlock(), createElementBlock("th", {
            key: column.key,
            scope: "col",
            class: normalizeClass({ "record-actions": column.key === "actions", "sortable": column.sortable }),
            style: normalizeStyle({ width: `${__props.widths[column.key] || 48}px`, minWidth: `${__props.widths[column.key] || 48}px` }),
            "aria-sort": column.sortable ? __props.isSorted(column) ? ((_a = __props.sortBy.find((item) => item.key === column.key)) == null ? void 0 : _a.order) === "desc" ? "descending" : "ascending" : "none" : void 0,
            onClick: ($event) => column.sortable && __props.toggleSort(column)
          }, [
            column.key === "data-table-select" ? (openBlock(), createBlock(_component_v_checkbox_btn, {
              key: 0,
              "model-value": __props.allSelected,
              indeterminate: __props.someSelected && !__props.allSelected,
              "aria-label": "选择当前页",
              "onUpdate:modelValue": __props.selectAll
            }, null, 8, ["model-value", "indeterminate", "onUpdate:modelValue"])) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
              column.sortable ? (openBlock(), createElementBlock("button", {
                key: 0,
                type: "button",
                class: "sort-heading",
                "aria-label": `按${column.title}排序`,
                onClick: withModifiers(($event) => __props.toggleSort(column), ["stop"])
              }, [
                createTextVNode(toDisplayString(column.title), 1),
                createVNode(_component_v_icon, {
                  icon: __props.isSorted(column) ? __props.getSortIcon(column) : unref(mdiArrowUpDown),
                  class: normalizeClass({ "sort-idle": !__props.isSorted(column) }),
                  size: "16"
                }, null, 8, ["icon", "class"])
              ], 8, _hoisted_2$7)) : (openBlock(), createElementBlock("span", _hoisted_3$7, toDisplayString(column.title), 1)),
              column.key !== "actions" ? (openBlock(), createElementBlock("span", {
                key: 2,
                role: "separator",
                "aria-orientation": "vertical",
                "aria-label": `调整${column.title}列宽`,
                "aria-valuenow": __props.widths[column.key],
                "aria-valuemin": minimum(column.key),
                tabindex: "0",
                class: "resize-handle",
                onPointerdown: withModifiers(($event) => start($event, column.key), ["stop"]),
                onClick: _cache[0] || (_cache[0] = withModifiers(() => {
                }, ["stop"])),
                onDblclick: withModifiers(($event) => resize(column.key, __props.defaults[column.key]), ["stop"]),
                onKeydown: [
                  withKeys(withModifiers(($event) => resize(column.key, __props.widths[column.key] - 16), ["prevent"]), ["left"]),
                  withKeys(withModifiers(($event) => resize(column.key, __props.widths[column.key] + 16), ["prevent"]), ["right"])
                ]
              }, null, 40, _hoisted_4$7)) : createCommentVNode("", true)
            ], 64))
          ], 14, _hoisted_1$8);
        }), 128))
      ]);
    };
  }
});
const ResizableHeaders = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-fa463a85"]]);
const _withScopeId$5 = (n) => (pushScopeId("data-v-c20e06de"), n = n(), popScopeId(), n);
const _hoisted_1$7 = { class: "d-flex align-center flex-wrap ga-3 mb-4" };
const _hoisted_2$6 = { class: "text-body-2 text-medium-emphasis flex-grow-1" };
const _hoisted_3$6 = { class: "records-layout" };
const _hoisted_4$6 = ["inert", "aria-hidden"];
const _hoisted_5$6 = ["title"];
const _hoisted_6$6 = ["title"];
const _hoisted_7$5 = {
  key: 0,
  class: "text-caption"
};
const _hoisted_8$3 = ["title"];
const _hoisted_9$2 = { class: "text-truncate" };
const _hoisted_10$2 = {
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
const _hoisted_17 = /* @__PURE__ */ _withScopeId$5(() => /* @__PURE__ */ createBaseVNode("p", { class: "mt-3" }, "仅处理插件数据，不清除 AstrBot 原生对话。正在回复或整理时会拒绝删除，请稍后重试。", -1));
const _sfc_main$7 = {
  __name: "Records",
  props: { category: String, sessions: Array, refresh: Number, timezone: String },
  emits: ["changed"],
  setup(__props, { emit }) {
    const props = __props;
    const bridge2 = inject("bridge");
    const defaults = { q: "", sessions: [], chat_type: "", start: "", end: "", kind: "", sender: "", component: "", reply: "", emotion: "", required: "", trigger: "", participant: "", bot_reply: "", coverage_gap: "", sort: "timestamp:desc" };
    const filters = reactive({ ...defaults, sessions: [] });
    const filtersOpen = ref(true);
    const sessionTitles = computed(() => Object.fromEntries(props.sessions.map((item) => [item.umo, item.title !== item.umo ? item.title : item.umo.split(":").slice(2).join(":")])));
    const defaultWidths = { timestamp: 168, conversation: 172, headline: 216, state: 132, actions: 88 };
    const widths = reactive({ ...defaultWidths });
    const tableWidth = computed(() => Object.values(widths).reduce((sum, width) => sum + width, 48));
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
      { title: "时间", key: "timestamp", width: widths.timestamp },
      { title: "会话", key: "conversation", width: widths.conversation },
      { title: props.category === "decisions" ? "规划原因" : "内容", key: "headline", width: widths.headline },
      { title: props.category === "messages" ? "发送者" : "状态", key: "state", width: widths.state },
      { title: "操作", key: "actions", sortable: false, width: widths.actions, cellProps: { class: "record-actions" } }
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
        createBaseVNode("div", _hoisted_1$7, [
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
          createBaseVNode("div", _hoisted_2$6, "共 " + toDisplayString(total.value) + " 条 · 已选 " + toDisplayString(selected.value.length) + " 条（当前页）", 1),
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
        createBaseVNode("div", _hoisted_3$6, [
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
              ], 8, _hoisted_4$6), [
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
                "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => selected.value = $event),
                page: page.value,
                "onUpdate:page": _cache[7] || (_cache[7] = ($event) => page.value = $event),
                "items-per-page": limit.value,
                "onUpdate:itemsPerPage": _cache[8] || (_cache[8] = ($event) => limit.value = $event),
                "sort-by": sort.value,
                "onUpdate:sortBy": _cache[9] || (_cache[9] = ($event) => sort.value = $event),
                class: "records-table",
                style: normalizeStyle({ "--records-width": `${tableWidth.value}px` }),
                headers: headers.value,
                items: rows.value,
                "items-length": total.value,
                loading: loading.value,
                "items-per-page-options": [10, 25, 50, 100],
                mobile: false,
                "item-value": "key",
                "show-select": "",
                "select-strategy": "page",
                "must-sort": "",
                hover: ""
              }, {
                headers: withCtx((controls) => [
                  createVNode(ResizableHeaders, mergeProps(controls, {
                    widths,
                    defaults: defaultWidths,
                    onResize: _cache[5] || (_cache[5] = ($event) => widths[$event.key] = $event.width)
                  }), null, 16, ["widths"])
                ]),
                "item.timestamp": withCtx(({ item }) => [
                  createTextVNode(toDisplayString(time(item.timestamp)), 1)
                ]),
                "item.conversation": withCtx(({ item }) => [
                  createBaseVNode("div", {
                    class: "text-body-2 text-truncate session-name",
                    title: `${unref(sessionLabel)(item.conversation, sessionTitles.value[item.conversation])}
${item.conversation}`
                  }, toDisplayString(sessionTitles.value[item.conversation] || item.conversation.split(":").slice(2).join(":")), 9, _hoisted_5$6)
                ]),
                "item.headline": withCtx(({ item }) => [
                  createBaseVNode("div", {
                    class: "text-body-2 text-truncate record-headline",
                    title: item.headline
                  }, toDisplayString(item.headline), 9, _hoisted_6$6)
                ]),
                "item.state": withCtx(({ item }) => {
                  var _a, _b;
                  return [
                    __props.category === "messages" ? (openBlock(), createElementBlock("div", _hoisted_7$5, [
                      createBaseVNode("div", {
                        class: "text-truncate",
                        title: item.sender_name
                      }, toDisplayString(item.sender_name), 9, _hoisted_8$3),
                      createBaseVNode("div", _hoisted_9$2, toDisplayString(item.direction === "out" ? "机器人回复" : item.sender_id), 1)
                    ])) : __props.category === "decisions" ? (openBlock(), createElementBlock("div", _hoisted_10$2, [
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
              }, 8, ["modelValue", "page", "items-per-page", "sort-by", "style", "headers", "items", "items-length", "loading"])
            ]),
            _: 1
          })
        ]),
        createVNode(_component_v_dialog, {
          "model-value": !!detail.value,
          "max-width": "1000",
          scrollable: "",
          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => !$event && (detail.value = null))
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
                    createVNode(_sfc_main$a, { value: detailFields.value }, null, 8, ["value"])
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => [
                    createVNode(_component_v_spacer),
                    createVNode(_component_v_btn, {
                      onClick: _cache[10] || (_cache[10] = ($event) => detail.value = null)
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
          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => confirm.value = $event),
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
                      onClick: _cache[12] || (_cache[12] = ($event) => confirm.value = false)
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
const Records = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-c20e06de"]]);
const _withScopeId$4 = (n) => (pushScopeId("data-v-0b84bc79"), n = n(), popScopeId(), n);
const _hoisted_1$6 = { class: "resource-field" };
const _hoisted_2$5 = { class: "resource-row" };
const _hoisted_3$5 = { class: "text-subtitle-2" };
const _hoisted_4$5 = ["aria-label"];
const _hoisted_5$5 = { class: "text-truncate" };
const _hoisted_6$5 = {
  key: 1,
  class: "persona-trigger"
};
const _hoisted_7$4 = { class: "text-body-2 text-truncate" };
const _hoisted_8$2 = {
  key: 0,
  class: "text-caption text-medium-emphasis mt-2"
};
const _hoisted_9$1 = /* @__PURE__ */ _withScopeId$4(() => /* @__PURE__ */ createBaseVNode("p", { class: "text-caption text-medium-emphasis mb-2" }, "人格提示词预览", -1));
const _hoisted_10$1 = { class: "persona-preview" };
const _sfc_main$6 = {
  __name: "ResourceSelector",
  props: { modelValue: String, label: String, hint: String, kind: String, items: Array },
  emits: ["update:modelValue"],
  setup(__props, { emit }) {
    const props = __props;
    const open = ref(false), search = ref(""), draft = ref("");
    const current = computed(() => props.items.find((item) => item.value === props.modelValue));
    const matches = computed(() => props.items.filter((item) => `${item.title} ${item.description || ""}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())));
    function show() {
      search.value = "";
      draft.value = props.modelValue;
      open.value = true;
    }
    function choose(value) {
      emit("update:modelValue", value);
      open.value = false;
    }
    return (_ctx, _cache) => {
      var _a;
      const _component_v_icon = resolveComponent("v-icon");
      const _component_v_text_field = resolveComponent("v-text-field");
      const _component_v_list_item = resolveComponent("v-list-item");
      const _component_v_list = resolveComponent("v-list");
      const _component_v_card = resolveComponent("v-card");
      const _component_v_menu = resolveComponent("v-menu");
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_divider = resolveComponent("v-divider");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_spacer = resolveComponent("v-spacer");
      const _component_v_card_actions = resolveComponent("v-card-actions");
      const _component_v_dialog = resolveComponent("v-dialog");
      return openBlock(), createElementBlock("div", _hoisted_1$6, [
        createBaseVNode("div", _hoisted_2$5, [
          createBaseVNode("span", _hoisted_3$5, toDisplayString(__props.label), 1),
          __props.kind === "select_provider" ? (openBlock(), createBlock(_component_v_menu, {
            key: 0,
            modelValue: open.value,
            "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => open.value = $event),
            "close-on-content-click": false,
            location: "bottom end",
            offset: 10
          }, {
            activator: withCtx(({ props: props2 }) => {
              var _a2;
              return [
                createBaseVNode("button", mergeProps(props2, {
                  type: "button",
                  class: "provider-trigger",
                  "aria-label": __props.label,
                  onClick: _cache[0] || (_cache[0] = ($event) => search.value = "")
                }), [
                  createBaseVNode("span", _hoisted_5$5, toDisplayString(((_a2 = current.value) == null ? void 0 : _a2.title) || __props.modelValue || "未选择"), 1),
                  createVNode(_component_v_icon, {
                    icon: unref(mdiChevronDown),
                    size: "18"
                  }, null, 8, ["icon"])
                ], 16, _hoisted_4$5)
              ];
            }),
            default: withCtx(() => [
              createVNode(_component_v_card, {
                class: "provider-menu-card pa-3",
                rounded: "xl"
              }, {
                default: withCtx(() => [
                  createVNode(_component_v_text_field, {
                    modelValue: search.value,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => search.value = $event),
                    label: "搜索模型",
                    "prepend-inner-icon": unref(mdiMagnify),
                    density: "compact",
                    clearable: "",
                    "hide-details": "",
                    "onClick:clear": _cache[2] || (_cache[2] = ($event) => search.value = "")
                  }, null, 8, ["modelValue", "prepend-inner-icon"]),
                  createVNode(_component_v_list, {
                    role: "listbox",
                    class: "resource-options mt-2",
                    density: "compact"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_v_list_item, {
                        role: "option",
                        title: "未选择",
                        active: !__props.modelValue,
                        onClick: _cache[3] || (_cache[3] = ($event) => choose(""))
                      }, null, 8, ["active"]),
                      (openBlock(true), createElementBlock(Fragment, null, renderList(matches.value, (item) => {
                        return openBlock(), createBlock(_component_v_list_item, {
                          key: item.value,
                          role: "option",
                          title: item.title,
                          active: item.value === __props.modelValue,
                          onClick: ($event) => choose(item.value)
                        }, null, 8, ["title", "active", "onClick"]);
                      }), 128)),
                      !matches.value.length ? (openBlock(), createBlock(_component_v_list_item, {
                        key: 0,
                        title: "没有匹配的模型",
                        disabled: ""
                      })) : createCommentVNode("", true)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])) : (openBlock(), createElementBlock("div", _hoisted_6$5, [
            createBaseVNode("span", _hoisted_7$4, toDisplayString(((_a = current.value) == null ? void 0 : _a.title) || __props.modelValue || "未选择"), 1),
            createVNode(_component_v_btn, {
              size: "small",
              color: "primary",
              variant: "tonal",
              "aria-label": __props.label,
              onClick: show
            }, {
              default: withCtx(() => [
                createTextVNode("选择人格")
              ]),
              _: 1
            }, 8, ["aria-label"])
          ]))
        ]),
        __props.hint ? (openBlock(), createElementBlock("p", _hoisted_8$2, toDisplayString(__props.hint), 1)) : createCommentVNode("", true),
        __props.kind === "select_persona" ? (openBlock(), createBlock(_component_v_dialog, {
          key: 1,
          modelValue: open.value,
          "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => open.value = $event),
          "max-width": "900",
          scrollable: ""
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card, null, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, { class: "text-h6 pa-5" }, {
                  default: withCtx(() => [
                    createTextVNode("选择人格 · " + toDisplayString(__props.label), 1)
                  ]),
                  _: 1
                }),
                createVNode(_component_v_card_text, null, {
                  default: withCtx(() => {
                    var _a2;
                    return [
                      createVNode(_component_v_text_field, {
                        modelValue: search.value,
                        "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => search.value = $event),
                        label: "搜索人格",
                        "prepend-inner-icon": unref(mdiMagnify),
                        clearable: "",
                        "hide-details": "",
                        class: "mb-3",
                        "onClick:clear": _cache[6] || (_cache[6] = ($event) => search.value = "")
                      }, null, 8, ["modelValue", "prepend-inner-icon"]),
                      createVNode(_component_v_list, {
                        role: "listbox",
                        class: "resource-options"
                      }, {
                        default: withCtx(() => [
                          createVNode(_component_v_list_item, {
                            role: "option",
                            title: "未选择人格",
                            active: !draft.value,
                            onClick: _cache[7] || (_cache[7] = ($event) => draft.value = "")
                          }, null, 8, ["active"]),
                          (openBlock(true), createElementBlock(Fragment, null, renderList(matches.value, (item) => {
                            return openBlock(), createBlock(_component_v_list_item, {
                              key: item.value,
                              role: "option",
                              title: item.title,
                              subtitle: item.description || "无提示词正文",
                              active: draft.value === item.value,
                              onClick: ($event) => draft.value = item.value
                            }, null, 8, ["title", "subtitle", "active", "onClick"]);
                          }), 128))
                        ]),
                        _: 1
                      }),
                      createVNode(_component_v_divider, { class: "my-3" }),
                      _hoisted_9$1,
                      createBaseVNode("pre", _hoisted_10$1, toDisplayString(((_a2 = __props.items.find((item) => item.value === draft.value)) == null ? void 0 : _a2.description) || "未选择人格，将使用文本或默认提示词"), 1)
                    ];
                  }),
                  _: 1
                }),
                createVNode(_component_v_card_actions, null, {
                  default: withCtx(() => [
                    createVNode(_component_v_spacer),
                    createVNode(_component_v_btn, {
                      onClick: _cache[8] || (_cache[8] = ($event) => open.value = false)
                    }, {
                      default: withCtx(() => [
                        createTextVNode("取消")
                      ]),
                      _: 1
                    }),
                    createVNode(_component_v_btn, {
                      color: "primary",
                      onClick: _cache[9] || (_cache[9] = ($event) => choose(draft.value))
                    }, {
                      default: withCtx(() => [
                        createTextVNode("确定")
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
        }, 8, ["modelValue"])) : createCommentVNode("", true)
      ]);
    };
  }
};
const ResourceSelector = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-0b84bc79"]]);
const _hoisted_1$5 = {
  key: 0,
  class: "mb-5"
};
const _hoisted_2$4 = { class: "d-flex align-center flex-wrap ga-2 mb-3" };
const _hoisted_3$4 = { class: "text-subtitle-1 font-weight-bold flex-grow-1" };
const _hoisted_4$4 = { class: "d-flex justify-space-between align-center mb-3" };
const _hoisted_5$4 = { class: "text-caption text-medium-emphasis" };
const _hoisted_6$4 = { class: "text-subtitle-2 mb-2" };
const _hoisted_7$3 = { class: "text-caption text-medium-emphasis" };
const _sfc_main$5 = {
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
          visible(field) ? (openBlock(), createElementBlock("div", _hoisted_1$5, [
            field.type === "template_list" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
              createBaseVNode("div", _hoisted_2$4, [
                createBaseVNode("span", _hoisted_3$4, toDisplayString(field.description), 1),
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
                    createBaseVNode("div", _hoisted_4$4, [
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
              createBaseVNode("p", _hoisted_5$4, toDisplayString(field.hint), 1)
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
              createBaseVNode("div", _hoisted_6$4, toDisplayString(field.description), 1),
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
              createBaseVNode("p", _hoisted_7$3, toDisplayString(field.hint), 1)
            ], 64)) : ["select_provider", "select_persona"].includes(field._special) ? (openBlock(), createBlock(ResourceSelector, {
              key: 4,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              kind: field._special,
              label: field.description,
              hint: field.hint,
              items: __props.choices[field._special] || []
            }, null, 8, ["modelValue", "onUpdate:modelValue", "kind", "label", "hint", "items"])) : field.options || field._special ? (openBlock(), createBlock(_component_v_autocomplete, {
              key: 5,
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
              key: 6,
              modelValue: __props.model[key],
              "onUpdate:modelValue": ($event) => __props.model[key] = $event,
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              multiple: "",
              chips: "",
              "closable-chips": ""
            }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint"])) : ["int", "float"].includes(field.type) ? (openBlock(), createBlock(_component_v_text_field, {
              key: 7,
              "model-value": __props.model[key],
              label: field.description,
              hint: field.hint,
              "persistent-hint": "",
              type: "number",
              step: field.type === "int" ? 1 : "any",
              "onUpdate:modelValue": ($event) => updateNumber(key, $event)
            }, null, 8, ["model-value", "label", "hint", "step", "onUpdate:modelValue"])) : (openBlock(), createBlock(_component_v_text_field, {
              key: 8,
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
const _hoisted_1$4 = { class: "text-body-2 text-medium-emphasis mb-4" };
const _sfc_main$4 = {
  __name: "ScopeSettings",
  props: { schema: Object, model: Object, choices: Object },
  setup(__props) {
    const props = __props;
    const fields = computed(() => Object.fromEntries(
      (props.model.all_sessions ? ["blacklist_sessions", "blacklist_manual_sessions", "blacklist_action"] : ["sessions", "manual_sessions", "outside_action"]).map((key) => [key, props.schema[key]])
    ));
    return (_ctx, _cache) => {
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_card = resolveComponent("v-card");
      return openBlock(), createElementBlock(Fragment, null, [
        createVNode(_sfc_main$5, {
          schema: { all_sessions: __props.schema.all_sessions },
          model: __props.model,
          choices: __props.choices
        }, null, 8, ["schema", "model", "choices"]),
        createVNode(_component_v_card, {
          tag: "section",
          "aria-label": __props.model.all_sessions ? "会话黑名单" : "会话白名单",
          rounded: "lg"
        }, {
          default: withCtx(() => [
            createVNode(_component_v_card_title, { class: "text-subtitle-1 font-weight-bold pa-4" }, {
              default: withCtx(() => [
                createTextVNode(toDisplayString(__props.model.all_sessions ? "会话黑名单" : "会话白名单"), 1)
              ]),
              _: 1
            }),
            createVNode(_component_v_card_text, null, {
              default: withCtx(() => [
                createBaseVNode("p", _hoisted_1$4, toDisplayString(__props.model.all_sessions ? "未命中黑名单的会话正常启用插件；命中时使用下方策略。" : "白名单中的会话正常启用插件；范围外使用下方策略。") + " 已匹配的插件指令及其 LLM 请求不受范围策略限制。", 1),
                createVNode(_sfc_main$5, {
                  schema: fields.value,
                  model: __props.model,
                  choices: __props.choices
                }, null, 8, ["schema", "model", "choices"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["aria-label"])
      ], 64);
    };
  }
};
function statistics(text) {
  const chars = Array.from(text), chinese = chars.filter((c) => /[\u4e00-\u9fff]/u.test(c)).length;
  const emoji = chars.filter((c) => /[\u200d\u2600-\u27bf\ufe00-\ufe0f\u{1f000}-\u{1faff}]/u.test(c)).length;
  return `${chars.length} 字 · 估计 ${Math.trunc(chinese * 0.6 + emoji * 2 + (chars.length - chinese - emoji) * 0.3)} Tokens`;
}
const _withScopeId$3 = (n) => (pushScopeId("data-v-50ed991a"), n = n(), popScopeId(), n);
const _hoisted_1$3 = { class: "flex-grow-1 text-wrap" };
const _hoisted_2$3 = /* @__PURE__ */ _withScopeId$3(() => /* @__PURE__ */ createBaseVNode("div", { class: "compare-columns compare-labels mb-3" }, [
  /* @__PURE__ */ createBaseVNode("h3", { class: "text-subtitle-1" }, "自定义提示词"),
  /* @__PURE__ */ createBaseVNode("h3", { class: "text-subtitle-1" }, "系统默认提示词（只读）")
], -1));
const _hoisted_3$3 = {
  key: 2,
  class: "text-body-2 text-medium-emphasis mb-3"
};
const _hoisted_4$3 = {
  key: 3,
  class: "diff-scroll",
  role: "region",
  "aria-label": "提示词差异对比",
  tabindex: "0"
};
const _hoisted_5$3 = { class: "diff-number" };
const _hoisted_6$3 = { class: "diff-sign" };
const _hoisted_7$2 = {
  key: 1,
  class: "compare-columns"
};
const _hoisted_8$1 = { class: "compare-columns mt-2 text-caption text-medium-emphasis" };
const _hoisted_9 = { "aria-label": "自定义提示词字数和Tokens估计" };
const _hoisted_10 = { "aria-label": "默认提示词字数和Tokens估计" };
const _sfc_main$3 = {
  __name: "PromptCompare",
  props: { name: String, title: String, text: String, original: String },
  emits: ["update:text", "copy", "close"],
  setup(__props, { emit }) {
    const props = __props;
    const bridge2 = inject("bridge");
    const showDiff = ref(false), rows = ref([]), loading = ref(false), error = ref(""), identical = ref(false);
    let generation = 0;
    watch([showDiff, () => props.text], async ([enabled, text]) => {
      const current = ++generation;
      error.value = "";
      loading.value = false;
      if (!enabled) return;
      loading.value = true;
      try {
        const result = await bridge2.apiPost("prompts/diff", { name: props.name, text });
        if (current === generation) {
          rows.value = result.rows;
          identical.value = result.identical;
        }
      } catch (e) {
        if (current === generation) error.value = e.message;
      } finally {
        if (current === generation) loading.value = false;
      }
    });
    onBeforeUnmount(() => generation++);
    return (_ctx, _cache) => {
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_progress_linear = resolveComponent("v-progress-linear");
      const _component_v_alert = resolveComponent("v-alert");
      const _component_v_textarea = resolveComponent("v-textarea");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_spacer = resolveComponent("v-spacer");
      const _component_v_card_actions = resolveComponent("v-card-actions");
      const _component_v_card = resolveComponent("v-card");
      return openBlock(), createBlock(_component_v_card, { class: "compare-card" }, {
        default: withCtx(() => [
          createVNode(_component_v_card_title, { class: "text-h6 pa-4 pl-6 d-flex align-center flex-wrap ga-3" }, {
            default: withCtx(() => [
              createBaseVNode("span", _hoisted_1$3, "对比默认提示词 · " + toDisplayString(__props.title), 1),
              createVNode(_component_v_btn, {
                size: "small",
                "prepend-icon": unref(mdiFileCompare),
                "aria-pressed": showDiff.value,
                color: showDiff.value ? "primary" : void 0,
                onClick: _cache[0] || (_cache[0] = ($event) => showDiff.value = !showDiff.value)
              }, {
                default: withCtx(() => [
                  createTextVNode(toDisplayString(showDiff.value ? "返回编辑" : "显示差异"), 1)
                ]),
                _: 1
              }, 8, ["prepend-icon", "aria-pressed", "color"]),
              createVNode(_component_v_btn, {
                icon: unref(mdiClose),
                "aria-label": "关闭提示词对比",
                variant: "text",
                size: "small",
                onClick: _cache[1] || (_cache[1] = ($event) => emit("close"))
              }, null, 8, ["icon"])
            ]),
            _: 1
          }),
          createVNode(_component_v_card_text, { class: "compare-body" }, {
            default: withCtx(() => [
              _hoisted_2$3,
              showDiff.value ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                loading.value ? (openBlock(), createBlock(_component_v_progress_linear, {
                  key: 0,
                  indeterminate: "",
                  color: "primary"
                })) : createCommentVNode("", true),
                error.value ? (openBlock(), createBlock(_component_v_alert, {
                  key: 1,
                  type: "error",
                  variant: "tonal",
                  class: "mb-3"
                }, {
                  default: withCtx(() => [
                    createTextVNode(toDisplayString(error.value), 1)
                  ]),
                  _: 1
                })) : createCommentVNode("", true),
                !loading.value && !error.value && identical.value ? (openBlock(), createElementBlock("p", _hoisted_3$3, "与默认内容相同。")) : createCommentVNode("", true),
                !loading.value && !error.value ? (openBlock(), createElementBlock("div", _hoisted_4$3, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row, index) => {
                    return openBlock(), createElementBlock("div", {
                      key: index,
                      class: "compare-columns diff-row"
                    }, [
                      (openBlock(), createElementBlock(Fragment, null, renderList(["left", "right"], (side) => {
                        var _a, _b;
                        return createBaseVNode("div", {
                          key: side,
                          class: normalizeClass(["diff-cell", { "diff-empty": !row[side], "diff-add": side === "left" && row.kind !== "equal" && row.left, "diff-remove": side === "right" && row.kind !== "equal" && row.right }])
                        }, [
                          createBaseVNode("span", _hoisted_5$3, toDisplayString((_a = row[side]) == null ? void 0 : _a.number), 1),
                          createBaseVNode("span", _hoisted_6$3, toDisplayString(row.kind === "equal" || !row[side] ? " " : side === "left" ? "+" : "−"), 1),
                          createBaseVNode("code", null, [
                            (openBlock(true), createElementBlock(Fragment, null, renderList((_b = row[side]) == null ? void 0 : _b.segments, (part, partIndex) => {
                              return openBlock(), createElementBlock("span", {
                                key: partIndex,
                                class: normalizeClass({ "diff-change": part.changed })
                              }, toDisplayString(part.text), 3);
                            }), 128))
                          ])
                        ], 2);
                      }), 64))
                    ]);
                  }), 128))
                ])) : createCommentVNode("", true)
              ], 64)) : (openBlock(), createElementBlock("div", _hoisted_7$2, [
                createVNode(_component_v_textarea, {
                  "model-value": __props.text,
                  label: "自定义提示词正文",
                  rows: "16",
                  "no-resize": "",
                  "hide-details": "",
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => emit("update:text", $event))
                }, null, 8, ["model-value"]),
                createVNode(_component_v_textarea, {
                  "model-value": __props.original,
                  label: "系统默认提示词正文",
                  rows: "16",
                  "no-resize": "",
                  readonly: "",
                  "hide-details": ""
                }, null, 8, ["model-value"])
              ])),
              createBaseVNode("div", _hoisted_8$1, [
                createBaseVNode("p", _hoisted_9, toDisplayString(unref(statistics)(__props.text)), 1),
                createBaseVNode("p", _hoisted_10, toDisplayString(unref(statistics)(__props.original)), 1)
              ])
            ]),
            _: 1
          }),
          createVNode(_component_v_card_actions, null, {
            default: withCtx(() => [
              createVNode(_component_v_spacer),
              createVNode(_component_v_btn, {
                color: "primary",
                onClick: _cache[3] || (_cache[3] = ($event) => {
                  showDiff.value = false;
                  emit("copy");
                })
              }, {
                default: withCtx(() => [
                  createTextVNode("复制默认到输入框")
                ]),
                _: 1
              }),
              createVNode(_component_v_btn, {
                onClick: _cache[4] || (_cache[4] = ($event) => emit("close"))
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
      });
    };
  }
};
const PromptCompare = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-50ed991a"]]);
const _withScopeId$2 = (n) => (pushScopeId("data-v-aade2360"), n = n(), popScopeId(), n);
const _hoisted_1$2 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("p", { class: "text-body-2 text-medium-emphasis mb-5" }, "主人格仍由 AstrBot 管理。以下四层分别控制规划、表达和聊天场景；选择人格时优先使用其正文，未选择人格且文本留空时自动读取内置默认 TXT。", -1));
const _hoisted_2$2 = { class: "prompt-grid" };
const _hoisted_3$2 = { class: "text-caption text-medium-emphasis text-truncate my-3" };
const _hoisted_4$2 = ["aria-label"];
const _hoisted_5$2 = { class: "d-flex flex-wrap ga-2 prompt-actions" };
const _hoisted_6$2 = /* @__PURE__ */ _withScopeId$2(() => /* @__PURE__ */ createBaseVNode("p", { class: "text-caption text-medium-emphasis mt-4" }, "Tokens 使用 AstrBot 的字符权重估计，不调用模型，不代表提供商实际计费。未自定义时直接显示默认正文，可在输入框中修改；点击“使用默认”后保存即可恢复，单纯浏览不会将默认内容写回配置。", -1));
const _sfc_main$2 = {
  __name: "PromptEditor",
  props: { model: Object, schema: Object, defaults: Object, personas: Array },
  setup(__props) {
    const props = __props;
    const names = [["behavior", "行为规划"], ["expression", "表达风格"], ["group", "群聊"], ["private", "私聊"]];
    const viewer = ref(null);
    const drafts = ref({});
    watch(() => props.model, (model) => {
      drafts.value = Object.fromEntries(names.map(([name]) => [name, model[name].trim() ? model[name] : props.defaults[name]]));
    }, { immediate: true });
    function reset(name) {
      drafts.value[name] = props.defaults[name];
      props.model[name] = "";
      props.model[`${name}_persona`] = "";
    }
    return (_ctx, _cache) => {
      const _component_v_card_title = resolveComponent("v-card-title");
      const _component_v_textarea = resolveComponent("v-textarea");
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_card_text = resolveComponent("v-card-text");
      const _component_v_card = resolveComponent("v-card");
      const _component_v_dialog = resolveComponent("v-dialog");
      return openBlock(), createElementBlock(Fragment, null, [
        _hoisted_1$2,
        createBaseVNode("div", _hoisted_2$2, [
          (openBlock(), createElementBlock(Fragment, null, renderList(names, ([name, title]) => {
            return createVNode(_component_v_card, {
              key: name,
              tag: "section",
              "aria-label": `${title}提示词`,
              class: "prompt-card",
              rounded: "xl"
            }, {
              default: withCtx(() => [
                createVNode(_component_v_card_title, {
                  tag: "h2",
                  class: "text-h6 pa-5"
                }, {
                  default: withCtx(() => [
                    createTextVNode(toDisplayString(title), 1)
                  ]),
                  _: 2
                }, 1024),
                createVNode(_component_v_card_text, { class: "prompt-body" }, {
                  default: withCtx(() => [
                    createVNode(ResourceSelector, {
                      modelValue: __props.model[`${name}_persona`],
                      "onUpdate:modelValue": ($event) => __props.model[`${name}_persona`] = $event,
                      kind: "select_persona",
                      label: __props.schema[`${name}_persona`].description,
                      items: __props.personas
                    }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "items"]),
                    createBaseVNode("p", _hoisted_3$2, "当前来源：" + toDisplayString(__props.model[`${name}_persona`] ? "已选人格正文（下方文本暂不生效）" : __props.model[name].trim() ? "自定义文本" : "内置默认 TXT"), 1),
                    createVNode(_component_v_textarea, {
                      modelValue: drafts.value[name],
                      "onUpdate:modelValue": [($event) => drafts.value[name] = $event, ($event) => __props.model[name] = $event],
                      label: __props.schema[name].description,
                      rows: "12",
                      "no-resize": "",
                      "hide-details": "",
                      onBlur: ($event) => !drafts.value[name].trim() && (drafts.value[name] = __props.defaults[name], __props.model[name] = "")
                    }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "onBlur"]),
                    createBaseVNode("p", {
                      class: "text-caption text-medium-emphasis mt-1",
                      "aria-label": `${title}字数和Tokens估计`
                    }, toDisplayString(unref(statistics)(drafts.value[name])), 9, _hoisted_4$2),
                    createBaseVNode("div", _hoisted_5$2, [
                      createVNode(_component_v_btn, {
                        size: "small",
                        "prepend-icon": unref(mdiFileCompare),
                        onClick: ($event) => viewer.value = name
                      }, {
                        default: withCtx(() => [
                          createTextVNode("对比默认")
                        ]),
                        _: 2
                      }, 1032, ["prepend-icon", "onClick"]),
                      createVNode(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        "prepend-icon": unref(mdiRestore),
                        onClick: ($event) => reset(name)
                      }, {
                        default: withCtx(() => [
                          createTextVNode("使用默认")
                        ]),
                        _: 2
                      }, 1032, ["prepend-icon", "onClick"])
                    ])
                  ]),
                  _: 2
                }, 1024)
              ]),
              _: 2
            }, 1032, ["aria-label"]);
          }), 64))
        ]),
        _hoisted_6$2,
        createVNode(_component_v_dialog, {
          "model-value": !!viewer.value,
          "max-width": "1440",
          scrollable: "",
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => !$event && (viewer.value = null))
        }, {
          default: withCtx(() => [
            viewer.value ? (openBlock(), createBlock(PromptCompare, {
              key: 0,
              name: viewer.value,
              title: names.find((item) => item[0] === viewer.value)[1],
              text: drafts.value[viewer.value],
              original: __props.defaults[viewer.value],
              "onUpdate:text": _cache[0] || (_cache[0] = ($event) => {
                drafts.value[viewer.value] = $event;
                __props.model[viewer.value] = $event;
              }),
              onCopy: _cache[1] || (_cache[1] = ($event) => {
                drafts.value[viewer.value] = __props.defaults[viewer.value];
                __props.model[viewer.value] = __props.defaults[viewer.value];
              }),
              onClose: _cache[2] || (_cache[2] = ($event) => viewer.value = null)
            }, null, 8, ["name", "title", "text", "original"])) : createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["model-value"])
      ], 64);
    };
  }
};
const PromptEditor = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-aade2360"]]);
const _withScopeId$1 = (n) => (pushScopeId("data-v-c5e96c54"), n = n(), popScopeId(), n);
const _hoisted_1$1 = { class: "d-flex align-center flex-wrap ga-3 mb-4" };
const _hoisted_2$1 = { class: "text-body-2 flex-grow-1" };
const _hoisted_3$1 = {
  key: 1,
  class: "settings-layout"
};
const _hoisted_4$1 = {
  class: "mt-2",
  "aria-label": "设置分区"
};
const _hoisted_5$1 = { class: "settings-grid" };
const _hoisted_6$1 = /* @__PURE__ */ _withScopeId$1(() => /* @__PURE__ */ createBaseVNode("p", { class: "mb-4" }, "清除全部 Humanization 会话的聊天记录、话题、日记、最近反应、辅助模型进度与计数，并为对应主模型开启空白对话。包含当前未启用的历史会话，删除后无法撤销。", -1));
const _hoisted_7$1 = { class: "mb-4" };
const _sfc_main$1 = {
  __name: "Settings",
  props: { promptsOnly: Boolean },
  emits: ["changed"],
  setup(__props, { expose: __expose, emit }) {
    const bridge2 = inject("bridge");
    const data = ref(null), model = ref(null), baseline = ref("");
    const loading = ref(false), saving = ref(false), confirm = ref(false), error = ref(""), success = ref("");
    const dirty = computed(() => model.value && JSON.stringify(model.value) !== baseline.value);
    const resetDialog = ref(false), confirmation = ref(""), resetting = ref(false), resetError = ref("");
    const busy = computed(() => saving.value || resetting.value);
    const content = ref(null), navOpen = ref(true), active = ref("scope");
    const sections = computed(() => {
      var _a;
      return Object.entries(((_a = data.value) == null ? void 0 : _a.schema) || {}).filter(([key]) => key !== "prompts");
    });
    const navTitles = { scope: "会话范围", recorder: "聊天感知", controller: "行为规划", proactive: "主动发言", management: "管理指令", logging: "日志设置", danger: "危险操作" };
    const navIcons = { scope: mdiAccountGroupOutline, recorder: mdiEyeOutline, controller: mdiHeadCogOutline, proactive: mdiMessageTextOutline, management: mdiShieldAccountOutline, logging: mdiTextBoxOutline, danger: mdiDeleteAlertOutline };
    let scrollFrame = 0;
    watch(content, trackSection, { flush: "post" });
    function trackSection() {
      if (scrollFrame) return;
      scrollFrame = requestAnimationFrame(() => {
        scrollFrame = 0;
        if (!content.value) return;
        const blocks = Array.from(content.value.querySelectorAll('section[id^="setting-"]')).map((element) => ({ key: element.id.slice(8), top: element.getBoundingClientRect().top }));
        if (!blocks.length) return;
        if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
          active.value = blocks.at(-1).key;
          return;
        }
        const passed = blocks.filter((block) => block.top <= 80);
        active.value = (passed.at(-1) || blocks[0]).key;
      });
    }
    onBeforeUnmount(() => {
      cancelAnimationFrame(scrollFrame);
      window.removeEventListener("scroll", trackSection);
      window.removeEventListener("resize", trackSection);
    });
    function jump(key) {
      var _a;
      active.value = key;
      (_a = content.value.querySelector(`#setting-${key}`)) == null ? void 0 : _a.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
      trackSection();
    }
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
    onMounted(() => {
      window.addEventListener("scroll", trackSection, { passive: true });
      window.addEventListener("resize", trackSection, { passive: true });
      load();
    });
    __expose({ dirty, saving: busy, save });
    return (_ctx, _cache) => {
      const _component_v_alert = resolveComponent("v-alert");
      const _component_v_btn = resolveComponent("v-btn");
      const _component_v_progress_linear = resolveComponent("v-progress-linear");
      const _component_v_list_item = resolveComponent("v-list-item");
      const _component_v_list = resolveComponent("v-list");
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
          __props.promptsOnly ? (openBlock(), createBlock(PromptEditor, {
            key: 0,
            model: model.value.prompts,
            schema: data.value.schema.prompts.items,
            defaults: data.value.prompt_defaults,
            personas: data.value.choices.select_persona
          }, null, 8, ["model", "schema", "defaults", "personas"])) : (openBlock(), createElementBlock("div", _hoisted_3$1, [
            createBaseVNode("aside", {
              class: normalizeClass(["settings-nav", { "settings-nav--closed": !navOpen.value }]),
              "aria-label": "设置快速导航"
            }, [
              createVNode(_component_v_btn, {
                icon: navOpen.value ? unref(mdiChevronLeft) : unref(mdiMenu),
                "aria-label": navOpen.value ? "收起设置导航" : "展开设置导航",
                variant: "text",
                size: "small",
                onClick: _cache[1] || (_cache[1] = ($event) => navOpen.value = !navOpen.value)
              }, null, 8, ["icon", "aria-label"]),
              withDirectives(createBaseVNode("nav", _hoisted_4$1, [
                createVNode(_component_v_list, {
                  nav: "",
                  "bg-color": "transparent",
                  density: "compact",
                  class: "pa-0"
                }, {
                  default: withCtx(() => [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(sections.value, ([key, section]) => {
                      return openBlock(), createBlock(_component_v_list_item, {
                        key,
                        tag: "button",
                        type: "button",
                        role: "button",
                        class: "settings-nav-item",
                        active: active.value === key,
                        "prepend-icon": navIcons[key],
                        title: navTitles[key] || section.description,
                        "aria-current": active.value === key ? "location" : void 0,
                        onClick: ($event) => jump(key)
                      }, null, 8, ["active", "prepend-icon", "title", "aria-current", "onClick"]);
                    }), 128)),
                    createVNode(_component_v_list_item, {
                      tag: "button",
                      type: "button",
                      role: "button",
                      class: "settings-nav-item settings-nav-danger",
                      active: active.value === "danger",
                      "prepend-icon": navIcons.danger,
                      title: "危险操作",
                      "aria-current": active.value === "danger" ? "location" : void 0,
                      onClick: _cache[2] || (_cache[2] = ($event) => jump("danger"))
                    }, null, 8, ["active", "prepend-icon", "aria-current"])
                  ]),
                  _: 1
                })
              ], 512), [
                [vShow, navOpen.value]
              ])
            ], 2),
            createBaseVNode("div", {
              ref_key: "content",
              ref: content,
              class: "settings-content"
            }, [
              createBaseVNode("div", _hoisted_5$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sections.value, ([key, section]) => {
                  return openBlock(), createBlock(_component_v_card, {
                    key,
                    id: `setting-${key}`,
                    tag: "section",
                    "aria-label": section.description,
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
                          key === "scope" ? (openBlock(), createBlock(_sfc_main$4, {
                            key: 0,
                            schema: section.items,
                            model: model.value[key],
                            choices: data.value.choices
                          }, null, 8, ["schema", "model", "choices"])) : (openBlock(), createBlock(_sfc_main$5, {
                            key: 1,
                            schema: section.items,
                            model: model.value[key],
                            choices: data.value.choices
                          }, null, 8, ["schema", "model", "choices"]))
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["id", "aria-label"]);
                }), 128))
              ]),
              createVNode(_component_v_card, {
                id: "setting-danger",
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
                      _hoisted_6$1,
                      createVNode(_component_v_btn, {
                        color: "error",
                        variant: "flat",
                        "prepend-icon": unref(mdiDeleteAlertOutline),
                        disabled: busy.value || loading.value,
                        onClick: _cache[3] || (_cache[3] = ($event) => {
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
            ], 512)
          ]))
        ], 64)) : createCommentVNode("", true),
        createVNode(_component_v_dialog, {
          modelValue: confirm.value,
          "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => confirm.value = $event),
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
                      onClick: _cache[4] || (_cache[4] = ($event) => confirm.value = false)
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
          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => resetDialog.value = $event),
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
                      createBaseVNode("p", _hoisted_7$1, [
                        createTextVNode("请输入 "),
                        createBaseVNode("strong", null, toDisplayString((_a = data.value) == null ? void 0 : _a.reset_confirmation), 1),
                        createTextVNode(" 确认清除；不会保存当前未提交的设置。")
                      ]),
                      createVNode(_component_v_text_field, {
                        modelValue: confirmation.value,
                        "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => confirmation.value = $event),
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
                        onClick: _cache[7] || (_cache[7] = ($event) => resetDialog.value = false)
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
            createTextVNode("Humanization " + toDisplayString(__props.promptsOnly ? "提示词" : "配置") + "尚未保存，请点击“保存并重载”。 ", 1)
          ]),
          _: 1
        }, 8, ["model-value"])
      ], 64);
    };
  }
};
const Settings = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-c5e96c54"]]);
const _withScopeId = (n) => (pushScopeId("data-v-b9e4d79a"), n = n(), popScopeId(), n);
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
const _hoisted_7 = { class: "font-weight-bold mb-2" };
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
      ["prompts", "提示词", mdiTextBoxOutline],
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
      if (["settings", "prompts"].includes(tab.value) && ((_b = settings.value) == null ? void 0 : _b.dirty)) pendingTab.value = value;
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
                  tab.value === "overview" ? (openBlock(), createBlock(_sfc_main$b, {
                    key: 2,
                    stats: overview.value.stats,
                    onBrowse: navigate
                  }, null, 8, ["stats"])) : ["settings", "prompts"].includes(tab.value) ? (openBlock(), createBlock(Settings, {
                    key: tab.value,
                    ref_key: "settings",
                    ref: settings,
                    "prompts-only": tab.value === "prompts",
                    onChanged: load
                  }, null, 8, ["prompts-only"])) : (openBlock(), createBlock(Records, {
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
                          createBaseVNode("p", _hoisted_7, "Humanization " + toDisplayString(tab.value === "prompts" ? "提示词" : "配置") + "有未保存的更改，切换前是否保存？", 1),
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
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-b9e4d79a"]]);
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
    VList,
    VListItem,
    VMenu,
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

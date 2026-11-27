/* 编辑触发器、条件、操作和候选点。 */

const conditionTypes = [
  ["confidence", "OCR 置信度"],
  ["text", "OCR 文字"],
  ["color", "像素颜色"],
];
const actionTypes = [
  ["ocr", "额外 OCR"],
  ["click", "条件随机点击"],
  ["wait", "等待"],
];

/** 创建使用文本节点的表单元素。 */
function node(tag, className, ...children) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.append(...children);
  return element;
}

/** 绑定按钮操作。 */
function button(text, click, className = "quiet", title = "") {
  const element = node("button", className, text);
  element.type = "button";
  element.title = title;
  if (title) element.setAttribute("aria-label", title);
  element.addEventListener("click", () => click(element));
  return element;
}

/** 创建输入控件及对应的可点击标签。 */
function field(label, input) {
  return node("label", "field stack", label, input);
}

/** 绑定数字、颜色或文本输入的当前值。 */
function input(type, value, update, constraints = {}) {
  const element = document.createElement("input");
  element.type = type;
  element.value = value ?? "";
  Object.assign(element, constraints);
  element.addEventListener("input", () => update(
    type === "number" ? (Number.isFinite(element.valueAsNumber) ? element.valueAsNumber : null) : element.value,
  ));
  return element;
}

/** 建立可以由键盘操作的下拉菜单。 */
function options(label, choices, value, update) {
  const select = document.createElement("select");
  select.setAttribute("aria-label", label);
  for (const [key, text] of choices) select.add(new Option(text, key));
  select.value = value;
  select.addEventListener("change", () => update(select.value));
  return select;
}

/** 创建某种条件的默认字段。 */
function newCondition(type, ctx) {
  const region = ctx.program.regions[0]?.name ?? "";
  if (type === "confidence") return {type, region, threshold: 0.8};
  if (type === "text") return {type, region, text: "", match: "contains"};
  return {type, point: {x: null, y: null}, reference: "#000000", tolerance: 12};
}

/** 创建一个带额外判定的点击候选点。 */
function newCandidate(ctx) {
  return {point: {x: null, y: null}, conditions: [newCondition("color", ctx)]};
}

/** 创建某种操作的默认字段。 */
function newAction(type, ctx) {
  if (type === "ocr") return {type, region: ctx.program.regions[0]?.name ?? ""};
  if (type === "click") return {type, candidates: [newCandidate(ctx)]};
  return {type, seconds: 1};
}

/** 更新字段后保存浏览器草稿。 */
function setter(model, key, ctx) {
  return value => {
    model[key] = value;
    ctx.save();
  };
}

/** 为条件和操作提供相同的区域选择。 */
function regionField(model, ctx) {
  const choices = [["", "选择区域"], ...ctx.program.regions.map(region => [region.name, region.name])];
  return field("识别区域", options("识别区域", choices, model.region, setter(model, "region", ctx)));
}

/** 绑定坐标输入和从截图取点的按钮。 */
function pointField(point, ctx, onColor = null) {
  const x = input("number", point.x, setter(point, "x", ctx), {min: 0, step: 1});
  const y = input("number", point.y, setter(point, "y", ctx), {min: 0, step: 1});
  const pick = button(onColor ? "从截图取色" : "从截图取点", target => {
    ctx.pick(target, onColor ? "color" : "point", (position, color) => {
      Object.assign(point, position);
      x.value = point.x;
      y.value = point.y;
      if (onColor) onColor(color);
      ctx.save();
    });
  }, "secondary");
  return node("div", "point", field("X", x), field("Y", y), pick);
}

/** 提供列表项排序和删除。 */
function listButtons(items, index, ctx, label, ordered = false) {
  const controls = node("div", "actions");
  if (ordered) {
    const earlier = button("↑", () => ctx.edit(() => {
      [items[index - 1], items[index]] = [items[index], items[index - 1]];
    }), "quiet", `上移${label}`);
    earlier.disabled = index === 0;
    const later = button("↓", () => ctx.edit(() => {
      [items[index + 1], items[index]] = [items[index], items[index + 1]];
    }), "quiet", `下移${label}`);
    later.disabled = index === items.length - 1;
    controls.append(earlier, later);
  }
  controls.append(button("删除", () => ctx.edit(() => items.splice(index, 1)), "danger", `删除${label}`));
  return controls;
}

/** 编辑像素参考值与容差。 */
function colorFields(condition, ctx) {
  const hex = node("span", "pixel-position", condition.reference);
  const color = input("color", condition.reference, value => {
    condition.reference = hex.textContent = value;
    ctx.save();
  });
  const point = pointField(condition.point, ctx, value => {
    condition.reference = hex.textContent = color.value = value;
  });
  const tolerance = input("number", condition.tolerance, setter(condition, "tolerance", ctx), {
    min: 0, max: 255, step: 1,
  });
  return node("div", "color-fields",
    point,
    node("div", "color-inputs", field("参考色", color), hex),
    field("每通道容差", tolerance),
  );
}

/** 编辑单个触发器条件或候选点条件。 */
function conditionRow(conditions, index, ctx) {
  const condition = conditions[index];
  const type = options("条件类型", conditionTypes, condition.type, value =>
    ctx.edit(() => { conditions[index] = newCondition(value, ctx); }));
  type.className = "rule-type";
  const head = node("div", "rule-head", type, listButtons(conditions, index, ctx, "条件"));
  if (condition.type === "color") return node("div", "rule-row", head, colorFields(condition, ctx));
  const fields = node("div", "rule-fields", regionField(condition, ctx));
  if (condition.type === "confidence") {
    fields.append(field("置信度高于", input("number", condition.threshold, setter(condition, "threshold", ctx), {
      min: 0, max: 1, step: "any",
    })));
  } else {
    fields.append(
      field("匹配方式", options("匹配方式", [["contains", "包含"], ["equals", "完全相同"]], condition.match, setter(condition, "match", ctx))),
      field("目标文字", input("text", condition.text, setter(condition, "text", ctx))),
    );
  }
  return node("div", "rule-row", head, fields);
}

/** 编辑一个点击点及其全部额外条件。 */
function candidateRow(candidates, index, ctx) {
  const candidate = candidates[index];
  const head = node("div", "rule-head",
    node("span", "rule-label", `候选点 ${index + 1}`),
    listButtons(candidates, index, ctx, "候选点"),
  );
  const conditions = node("div", "rule-body",
    ...candidate.conditions.map((_, i) => conditionRow(candidate.conditions, i, ctx)),
  );
  if (!candidate.conditions.length) conditions.append(node("span", "meta", "需要至少一个条件"));
  return node("div", "candidate", head, pointField(candidate.point, ctx),
    conditions,
    node("div", "actions", button("＋ 候选条件", () => ctx.edit(() => {
      candidate.conditions.push(newCondition("color", ctx));
    }), "secondary")),
  );
}

/** 编辑单个操作及其参数。 */
function actionRow(actions, index, ctx) {
  const action = actions[index];
  const type = options("操作类型", actionTypes, action.type, value =>
    ctx.edit(() => { actions[index] = newAction(value, ctx); }));
  type.className = "rule-type";
  const row = node("div", "rule-row", node("div", "rule-head", type, listButtons(actions, index, ctx, "操作", true)));
  if (action.type === "ocr") {
    row.append(node("div", "rule-fields", regionField(action, ctx)));
  } else if (action.type === "wait") {
    row.append(field("暂停秒数", input("number", action.seconds, setter(action, "seconds", ctx), {min: 0, step: "any"})));
  } else {
    row.append(...action.candidates.map((_, i) => candidateRow(action.candidates, i, ctx)));
    row.append(node("div", "actions", button("＋ 候选点", () => ctx.edit(() => {
      action.candidates.push(newCandidate(ctx));
    }), "secondary")));
  }
  return row;
}

/** 绘制单个触发器的有序条件和操作组。 */
function triggerCard(trigger, index, ctx) {
  const show = document.createElement("input");
  show.type = "checkbox";
  show.checked = trigger.show ?? true;
  show.addEventListener("change", () => setter(trigger, "show", ctx)(show.checked));
  const visibility = node("label", "check", show, "显示");
  visibility.title = "在截图编辑区显示该触发器引用的 OCR 框";
  const head = node("div", "trigger-head",
    field("触发器名称", input("text", trigger.name, setter(trigger, "name", ctx))),
    visibility,
    listButtons(ctx.program.triggers, index, ctx, "触发器", true),
  );
  const conditions = node("section", "rule-section",
    node("div", "rule-section-head",
      node("h3", "", "条件", node("span", "meta", trigger.conditions.length ? "全部满足时执行" : "每轮执行")),
      button("＋ 条件", () => ctx.edit(() => trigger.conditions.push(newCondition("confidence", ctx))), "secondary"),
    ),
    ...trigger.conditions.map((_, i) => conditionRow(trigger.conditions, i, ctx)),
  );
  const actions = node("section", "rule-section",
    node("div", "rule-section-head",
      node("h3", "", "操作", node("span", "meta", "按顺序执行")),
      button("＋ 操作", () => ctx.edit(() => trigger.actions.push(newAction("ocr", ctx))), "secondary"),
    ),
    ...trigger.actions.map((_, i) => actionRow(trigger.actions, i, ctx)),
  );
  return node("article", "trigger", head, conditions, actions);
}

/** 绘制触发器列表，并向应用提供新建操作。 */
export function rulesEditor(container, getProgram, save, pick) {
  const ctx = {
    get program() { return getProgram(); },
    save,
    pick,
    edit(callback) {
      callback();
      ctx.save();
      render();
    },
  };

  /** 重新绘制列表结构。 */
  function render() {
    const triggers = ctx.program.triggers;
    container.replaceChildren(...triggers.map((trigger, i) => triggerCard(trigger, i, ctx)));
    if (!triggers.length) container.append(node("p", "empty-text", "设定满足条件后要执行的操作。"));
  }

  return {
    render,
    add() {
      const used = new Set(ctx.program.triggers.map(trigger => trigger.name));
      let number = 1;
      while (used.has(`触发器 ${number}`)) number++;
      ctx.edit(() => ctx.program.triggers.push({
        name: `触发器 ${number}`,
        show: true,
        conditions: [],
        actions: [newAction("ocr", ctx)],
      }));
      container.lastElementChild.querySelector("input").focus();
    },
  };
}

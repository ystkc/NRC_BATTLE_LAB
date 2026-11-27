/* 在截图坐标系中绘制、拖动和旋转选区。 */

const radians = angle => angle * Math.PI / 180;
const clamp = (value, low, high) => Math.max(low, Math.min(value, high));

/** 计算旋转矩形的水平和垂直半径。 */
function extents(region) {
  const c = Math.abs(Math.cos(radians(region.angle)));
  const s = Math.abs(Math.sin(radians(region.angle)));
  return {
    x: (c * region.width + s * region.height) / 2,
    y: (s * region.width + c * region.height) / 2,
  };
}

/** 将鼠标拖拽两端换算为中心和整数宽高。 */
function bounds(a, b) {
  const left = Math.round(Math.min(a.x, b.x));
  const right = Math.round(Math.max(a.x, b.x));
  const top = Math.round(Math.min(a.y, b.y));
  const bottom = Math.round(Math.max(a.y, b.y));
  return {x: (left + right) / 2, y: (top + bottom) / 2, width: right - left, height: bottom - top, angle: 0};
}

/** 将光标变换到区域局部坐标后做命中测试。 */
function contains(region, point) {
  const x = point.x - region.x;
  const y = point.y - region.y;
  const a = radians(region.angle);
  return Math.abs(x * Math.cos(a) + y * Math.sin(a)) <= region.width / 2
    && Math.abs(-x * Math.sin(a) + y * Math.cos(a)) <= region.height / 2;
}

export class SelectionCanvas {
  /** 绑定截图舞台和编辑事件。 */
  constructor({viewport, stage, overlay, image, empty, select, create, change, position}) {
    Object.assign(this, {viewport, stage, overlay, image, empty, select, create, change, position});
    this.context = overlay.getContext("2d");
    this.regions = [];
    this.selected = null;
    this.mode = "select";
    this.enabled = true;
    this.drag = null;
    this.picker = null;
    this.redrawTarget = null;
    this.imageUrl = null;
    this.pixels = document.createElement("canvas");
    this.pixelContext = this.pixels.getContext("2d", {willReadFrequently: true});
    new ResizeObserver(() => this.fit()).observe(viewport);
    overlay.addEventListener("pointerdown", event => this.down(event));
    overlay.addEventListener("pointermove", event => this.move(event));
    overlay.addEventListener("pointerup", event => this.up(event));
    overlay.addEventListener("pointercancel", () => this.cancelDrag());
    overlay.addEventListener("pointerleave", () => this.position(null));
  }

  /** 表示截图是否已加载。 */
  get ready() {
    return this.imageUrl !== null;
  }

  /** 加载截图，并建立取色用的原始像素副本。 */
  async load(blob) {
    const url = URL.createObjectURL(blob);
    const next = new Image();
    next.src = url;
    try {
      await next.decode();
    } catch (error) {
      URL.revokeObjectURL(url);
      throw error;
    }
    this.clear();
    this.imageUrl = url;
    this.image.src = url;
    this.overlay.width = this.pixels.width = next.naturalWidth;
    this.overlay.height = this.pixels.height = next.naturalHeight;
    this.pixelContext.drawImage(next, 0, 0);
    this.stage.hidden = false;
    this.empty.hidden = true;
    this.fit();
  }

  /** 移除旧截图，避免在旧显示器上取点。 */
  clear() {
    if (this.imageUrl) URL.revokeObjectURL(this.imageUrl);
    this.imageUrl = null;
    this.image.removeAttribute("src");
    this.stage.hidden = true;
    this.empty.hidden = false;
    this.position(null);
  }

  /** 切换选择、框选、重画或取点。 */
  tool(mode, {target = null, picker = null} = {}) {
    this.mode = mode;
    this.picker = picker;
    this.redrawTarget = target;
    this.overlay.dataset.mode = mode;
    this.paint();
  }

  /** 在视口中按原比例放置截图。 */
  fit() {
    if (!this.ready) return;
    const scale = Math.min(this.viewport.clientWidth / this.overlay.width, this.viewport.clientHeight / this.overlay.height);
    this.stage.style.width = `${this.overlay.width * scale}px`;
    this.stage.style.height = `${this.overlay.height * scale}px`;
    this.paint();
  }

  /** 绘制校正到水平方向后的选区。 */
  preview(canvas, region) {
    const scale = Math.min(1, 620 / region.width, 160 / region.height);
    canvas.width = Math.max(1, Math.round(region.width * scale));
    canvas.height = Math.max(1, Math.round(region.height * scale));
    const context = canvas.getContext("2d");
    context.translate(canvas.width / 2, canvas.height / 2);
    context.scale(canvas.width / region.width, canvas.height / region.height);
    context.rotate(-radians(region.angle));
    context.drawImage(this.pixels, -region.x, -region.y);
  }

  /** 按屏幕缩放比例绘制选区轮廓、名称和旋转手柄。 */
  paint() {
    if (!this.ready || !this.stage.clientWidth) return;
    const ctx = this.context;
    const width = this.overlay.width;
    const height = this.overlay.height;
    this.unit = width / this.stage.clientWidth;
    ctx.clearRect(0, 0, width, height);
    for (const region of this.regions) {
      if (this.drag?.kind === "draw" && region === this.redrawTarget) continue;
      if (region !== this.selected) this.drawBox(region, false);
    }
    if (this.selected && !(this.drag?.kind === "draw" && this.selected === this.redrawTarget)) {
      this.drawBox(this.selected, true);
    }
    if (this.drag?.draft) this.drawBox(this.drag.draft, false);
  }

  /** 绘制单个旋转矩形。 */
  drawBox(region, selected) {
    const ctx = this.context;
    const unit = this.unit;
    const half = region.height / 2;
    const corners = extents(region);
    const contained = region.x - corners.x >= -1e-6 && region.x + corners.x <= this.overlay.width + 1e-6
      && region.y - corners.y >= -1e-6 && region.y + corners.y <= this.overlay.height + 1e-6;
    ctx.save();
    ctx.translate(region.x, region.y);
    ctx.rotate(radians(region.angle));
    ctx.strokeStyle = contained ? (selected ? "#5affe1" : "#f3d388") : "#ffa195";
    ctx.fillStyle = selected ? "#46f6b931" : "#ffdb901f";
    ctx.lineWidth = (selected ? 2 : 1.5) * unit;
    ctx.fillRect(-region.width / 2, -half, region.width, region.height);
    ctx.strokeRect(-region.width / 2, -half, region.width, region.height);
    if (region.name) {
      ctx.font = `600 ${12 * unit}px "Microsoft YaHei UI", sans-serif`;
      ctx.textBaseline = "middle";
      const textWidth = Math.min(ctx.measureText(region.name).width, 180 * unit);
      const labelY = -half + 4 * unit;
      ctx.fillStyle = "#142521e8";
      ctx.fillRect(-region.width / 2, labelY, textWidth + 10 * unit, 19 * unit);
      ctx.fillStyle = "#fff";
      ctx.fillText(region.name, -region.width / 2 + 5 * unit, labelY + 9.5 * unit, 180 * unit);
    }
    if (selected && this.mode === "select") {
      const handle = -half - 23 * unit;
      ctx.beginPath();
      ctx.moveTo(0, -half);
      ctx.lineTo(0, handle);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, handle, 5 * unit, 0, 2 * Math.PI);
      ctx.fillStyle = "#142521";
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  /** 转换浏览器坐标与截图物理像素坐标。 */
  point(event) {
    const rect = this.overlay.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * this.overlay.width / rect.width,
      y: (event.clientY - rect.top) * this.overlay.height / rect.height,
    };
  }

  /** 把位置限制在截图边界内。 */
  clipped(point) {
    return {x: clamp(point.x, 0, this.overlay.width), y: clamp(point.y, 0, this.overlay.height)};
  }

  /** 返回实际像素和该点的 RGB 颜色。 */
  sample(point) {
    const x = clamp(Math.floor(point.x), 0, this.overlay.width - 1);
    const y = clamp(Math.floor(point.y), 0, this.overlay.height - 1);
    const rgba = this.pixelContext.getImageData(x, y, 1, 1).data;
    const color = "#" + Array.from(rgba.slice(0, 3), channel => channel.toString(16).padStart(2, "0")).join("");
    return {x, y, color};
  }

  /** 确认光标是否在当前区域的旋转手柄上。 */
  hitsHandle(point) {
    if (!this.selected) return false;
    const r = this.selected;
    const arm = r.height / 2 + 23 * this.unit;
    const angle = radians(r.angle);
    const x = r.x + arm * Math.sin(angle);
    const y = r.y - arm * Math.cos(angle);
    return Math.hypot(point.x - x, point.y - y) <= 11 * this.unit;
  }

  /** 启动一次框选、旋转或位置拖动。 */
  down(event) {
    if (!this.enabled || !this.ready || this.drag || event.button !== 0) return;
    if (document.activeElement instanceof HTMLInputElement) document.activeElement.blur();
    const point = this.point(event);
    if (this.mode === "pick") {
      const {x, y, color} = this.sample(point);
      this.picker({x, y}, color);
      return;
    }
    if (this.mode === "draw") {
      this.drag = {kind: "draw", start: this.clipped(point)};
    } else if (this.hitsHandle(point)) {
      const r = this.selected;
      const startAngle = Math.atan2(point.y - r.y, point.x - r.x);
      this.drag = {kind: "rotate", region: r, startAngle, original: {...r}};
    } else {
      const region = [this.selected, ...this.regions.slice().reverse()].find(r => r && contains(r, point));
      this.select(region ?? null);
      if (!region) return;
      this.drag = {kind: "move", region, start: point, original: {...region}};
    }
    this.drag.pointer = event.pointerId;
    this.overlay.setPointerCapture(event.pointerId);
  }

  /** 根据鼠标移动更新拖拽和旋转预览。 */
  move(event) {
    if (!this.enabled || !this.ready) return;
    const point = this.point(event);
    if (this.mode === "pick") {
      this.position(this.sample(point));
      return;
    }
    const clipped = this.clipped(point);
    this.position({x: Math.floor(clipped.x), y: Math.floor(clipped.y)});
    const drag = this.drag;
    if (!drag) {
      this.overlay.style.cursor = this.mode === "select" && this.hitsHandle(point) ? "grab" : "";
      return;
    }
    if (event.pointerId !== drag.pointer) return;
    if (drag.kind === "draw") {
      drag.draft = bounds(drag.start, clipped);
    } else if (drag.kind === "rotate") {
      const delta = Math.atan2(point.y - drag.region.y, point.x - drag.region.x) - drag.startAngle;
      const angle = drag.original.angle + delta * 180 / Math.PI;
      drag.region.angle = Math.round((((angle + 540) % 360) - 180) * 10) / 10;
      this.change(false);
    } else {
      const extent = extents(drag.region);
      const x = Math.min(extent.x, this.overlay.width / 2);
      const y = Math.min(extent.y, this.overlay.height / 2);
      const nextX = Math.round((drag.original.x + point.x - drag.start.x) * 1000) / 1000;
      const nextY = Math.round((drag.original.y + point.y - drag.start.y) * 1000) / 1000;
      drag.region.x = clamp(nextX, x, this.overlay.width - x);
      drag.region.y = clamp(nextY, y, this.overlay.height - y);
      this.change(false);
    }
    this.paint();
  }

  /** 提交或放弃当前拖拽。 */
  up(event) {
    const drag = this.drag;
    if (!drag || event.pointerId !== drag.pointer) return;
    this.move(event);
    this.drag = null;
    if (drag.kind === "draw") {
      if (drag.draft?.width && drag.draft?.height) this.create(drag.draft, this.redrawTarget);
    } else {
      this.change(true);
    }
    this.paint();
  }

  /** 拖拽中断时恢复已经存在的区域。 */
  cancelDrag() {
    if (this.drag?.original) {
      Object.assign(this.drag.region, this.drag.original);
      this.change(false);
    }
    this.drag = null;
    this.paint();
  }
}

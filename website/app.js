"use strict";
const I18N = {
  "en": {
    "meta.title": "TacStack — Cross-sensor tactile semantics for robotics",
    "meta.desc": "An open tactile layer for robotics. Explore an interactive touch simulation, then build with shared sensor interfaces, contact and slip events.",
    "nav.principles": "Principles",
    "nav.pipeline": "Pipeline",
    "nav.sensors": "Sensors",
    "nav.roadmap": "Roadmap",
    "nav.quickstart": "Quick start",
    "hero.eyebrow": "THE TACTILE LAYER FOR ROBOTICS",
    "hero.h1": "Intelligence.<br>At your<br><span class=\"grad\">fingertips.</span>",
    "hero.lede": "Give robot applications a common language for touch. From raw sensor signals to contact and slip events — open, local and built to connect.",
    "hero.cta1": "Build with TacStack ↗",
    "hero.cta2": "View source",
    "hero.stat1": "sensor protocol layers",
    "hero.stat2": "input modalities",
    "hero.stat3": "cloud required",
    "hero.chip1": "<b>Image</b> · vision tactile",
    "hero.chip2": "<b>Array</b> · taxels",
    "hero.chip3": "<b>Wrench</b> · force / torque",
    "hero.chip4": "<b>PX3Q</b> · torque",
    "hero.hubsub": "raw-first · one contract",
    "hero.pill3": "<b>TactileEvent</b> → timeline",
    "sec.principles.h": "Principles that hold the stack together",
    "sec.principles.p": "Four commitments, applied to every adapter, model and integration decision.",
    "pr.raw.h": "Raw-first",
    "pr.raw.p": "Keep source payloads and metadata alongside derived representations, so processing remains traceable.",
    "pr.sem.h": "Semantics-first",
    "pr.sem.p": "One Observation and Event contract spans sensors and modalities — images, taxel matrices, force/torque.",
    "pr.edge.h": "Edge-first",
    "pr.edge.p": "Core depends on neither ROS2, cloud services nor training frameworks. Runs where the robot runs.",
    "pr.int.h": "Integration-first",
    "pr.int.p": "Record with MCAP, inspect with Rerun and exchange datasets with LeRobot. ROS2 support is on the roadmap.",
    "sec.pipeline.h": "From a raw signal to a useful event.",
    "sec.pipeline.p": "An offline workflow for developing and evaluating tactile applications, with the original data kept alongside derived outputs.",
    "st1.h": "Dataset",
    "st1.p": "Open-X-Tactile tar / zarr episodes; MCAP replay for recorded runs.",
    "st2.h": "Observation",
    "st2.p": "<code>TactileObservation</code> — shared metadata, sensor-specific arrays and raw payloads.",
    "st3.h": "Runtime",
    "st3.p": "Contact / slip baselines via builtin scorers or ONNX artifacts.",
    "st4.h": "Events",
    "st4.p": "<code>TactileEvent</code>s marked on a synchronized Rerun timeline, annotatable.",
    "st5.h": "Benchmark",
    "st5.p": "Reproducible per-episode reports with quality and calibration tracking.",
    "sec.sensors.h": "Five sensors. One tactile interface.",
    "sec.sensors.p": "Five sensor protocol layers — serial matrix, six-axis F/T, joint torque and vision-based tactile — fully tested offline with unit tests pinned to vendor documentation.",
    "sn.th1": "Sensor",
    "sn.th2": "Output",
    "sn.th3": "Link",
    "sn.th4": "Status",
    "sn.r1name": "M0404S<span>resistive matrix kit</span>",
    "sn.r1out": "4×4 matrix · 16 taxels",
    "sn.r1link": "UART 115200, active push",
    "sn.r2name": "PaXini PX-6AX GEN3<span>tactile skin</span>",
    "sn.r2out": "per-point 3-axis force + resultant",
    "sn.r2link": "UART 921600, req–resp",
    "sn.r3name": "PaXini PX6D<span>six-axis F/T</span>",
    "sn.r3out": "Fx, Fy, Fz, Mx, My, Mz · float32",
    "sn.r3link": "USB / RS485 · 1 kHz",
    "sn.r4name": "PaXini PX3Q<span>joint torque</span>",
    "sn.r4out": "Mx, My, Mz · N·m · 30/50/100 FS",
    "sn.r4link": "USB / RS485 · 921600",
    "sn.ok": "● ready",
    "sn.r5name": "Meta DIGIT<span>vision-based tactile</span>",
    "sn.r5out": "320×240 RGB gel image",
    "sn.r5link": "USB UVC · QVGA 60fps",
    "sn.okDigit": "● ready",
    "sec.roadmap.h": "Milestones",
    "sec.roadmap.p": "From core contracts to cross-sensor semantics — delivered milestone by milestone.",
    "ph1.tag": "PHASE 0–2",
    "ph1.h": "Contracts, data path, replay",
    "ph1.p": "Package and core contracts; Open-X-Tactile adapter for image / matrix / F/T streams; MCAP export and Rerun replay with C/S/U annotation.",
    "ph2.tag": "PHASE 3",
    "ph2.h": "Runtime & benchmark",
    "ph2.p": "Builtin and ONNX scoring backends, temporal contact / slip baselines and repeatable reports. Model-quality evaluation requires labeled data.",
    "ph3.tag": "PHASE 4",
    "ph3.h": "Quality & calibration",
    "ph3.p": "Two-level capability validation, dataset quality health reports, calibration provenance, per-stream benchmark grouping.",
    "ph4.tag": "PHASE 5",
    "ph4.h": "First live sensor",
    "ph4.p": "Live serial adapter, live record / replay / inference, device reconnect handling and a 30-minute stability run.",
    "ph5.tag": "PHASE 6",
    "ph5.h": "v0.1 release",
    "ph5.p": "External-user Quickstart, English documentation and the v0.1 release.",
    "sec.qs.h": "Start with a working offline demo.",
    "sec.qs.p": "Python 3.12+. Install the alpha from <a href=\"https://pypi.org/project/tacstack/\">PyPI</a>, or clone from source for the full offline tour. No sensor or dataset download needed.",
    "qs.copy": "copy",
    "qs.copied": "copied ✓",
    "qs.terminal": "<span class=\"tok-c\"># install the alpha from PyPI (Python 3.12+)</span>\npip install --pre tacstack\n\n<span class=\"tok-c\"># verify offline — no data download, no hardware</span>\ntacstack version\ntacstack contract-demo\n\n<span class=\"tok-c\"># from source: guided demo + bundled fixture + Rerun replay</span>\ngit clone https://github.com/mailes/TacStack.git && cd TacStack\nuv sync --extra rerun\n<span class=\"tok-p\">uv run</span> tacstack demo",
    "foot.desc": "Cross-sensor tactile semantics and runtime for robotics. Raw-first · Semantics-first · Edge-first · Integration-first.",
    "foot.col1": "Project",
    "foot.l1": "GitHub repository",
    "foot.l2": "Roadmap",
    "foot.col2": "Docs",
    "foot.l4": "Architecture",
    "foot.l5": "Adapter guide",
    "foot.l6": "Contributing",
    "foot.bottom1": "© <span id=\"year\">2026</span> TacStack contributors · Apache-2.0",
    "foot.bottom2": "Built for robots that feel.",
    "hero.status": "End-to-end offline pipeline · PyPI alpha available",
    "visual.title": "SIGNAL → SEMANTICS",
    "visual.label": "Illustrative taxel input",
    "visual.sub": "Different inputs. A shared observation contract.",
    "visual.output": "Example event · not a live reading",
    "qs.note": "The bundled fixture and the event below are synthetic. Use your own recordings to evaluate model behavior. PyPI hosts the alpha (0.1.0a1); the guided demo needs a repository checkout.",
    "qs.failed": "Select & copy",
    "qs.manual": "Clipboard unavailable. The code is selected; use your system copy command.",
    "nav.menu": "Menu",
    "nav.close": "Close",
    "skip": "Skip to content",
    "touch.lab": "TACTILE LAB / INTERACTIVE CONCEPT",
    "touch.prompt": "Touch to connect",
    "touch.output": "TACTILE RESPONSE",
    "touch.simulated": "SIMULATION",
    "touch.pressure": "Signal intensity",
    "touch.hint": "Press to make contact. Drag to simulate slip. Keyboard: Enter or Space.",
    "touch.pause": "Pause effects",
    "touch.resume": "Resume effects",
    "touch.announcement": "Simulated event: "
  },
  "zh": {
    "meta.title": "TacStack — 面向机器人的跨传感器触觉语义与运行时",
    "meta.desc": "面向机器人的开放触觉层。体验交互触碰模拟，使用统一传感器接口、接触与滑移事件构建应用。",
    "nav.principles": "原则",
    "nav.pipeline": "管线",
    "nav.sensors": "传感器",
    "nav.roadmap": "路线图",
    "nav.quickstart": "快速开始",
    "hero.eyebrow": "面向机器人的触觉基础设施",
    "hero.h1": "让智能，<br>触手<span class=\"grad\">可及。</span>",
    "hero.lede": "为机器人应用建立共同的触觉语言。从传感器原始信号，到接触与滑移事件——开放接口，本地运行，连接感知与行动。",
    "hero.cta1": "开始构建 ↗",
    "hero.cta2": "查看源码",
    "hero.stat1": "个传感器协议层",
    "hero.stat2": "类输入模态",
    "hero.stat3": "云端依赖",
    "hero.chip1": "<b>图像</b> · 视触觉",
    "hero.chip2": "<b>阵列</b> · 触点",
    "hero.chip3": "<b>力 / 扭矩</b> · Wrench",
    "hero.chip4": "<b>PX3Q</b> · 关节扭矩",
    "hero.hubsub": "原始优先 · 一套契约",
    "hero.pill3": "<b>TactileEvent</b> → 时间轴",
    "sec.principles.h": "支撑整个技术栈的四条原则",
    "sec.principles.p": "四项承诺，贯穿每一个 Adapter、模型与集成决策。",
    "pr.raw.h": "原始优先",
    "pr.raw.p": "保留源数据与元数据，同时提供派生表示，让每一步处理都有据可查。",
    "pr.sem.h": "语义优先",
    "pr.sem.p": "一套 Observation 与事件契约横跨传感器与模态——图像、触点矩阵、力/扭矩。",
    "pr.edge.h": "边缘优先",
    "pr.edge.p": "Core 不依赖 ROS2、云服务或训练框架。机器人跑在哪里，它就跑在哪里。",
    "pr.int.h": "集成优先",
    "pr.int.p": "使用 MCAP 记录、Rerun 查看，LeRobot 数据集互通。ROS2 支持在路线图中。",
    "sec.pipeline.h": "从原始信号，到可用的事件。",
    "sec.pipeline.p": "面向触觉应用开发与评估的离线工作流。原始数据与处理结果一并保留，每一步都可以回溯。",
    "st1.h": "数据集",
    "st1.p": "Open-X-Tactile tar / zarr episode；录制数据可经 MCAP 回放。",
    "st2.h": "观测",
    "st2.p": "<code>TactileObservation</code>：共享元数据，保留各传感器的数组表示与原始载荷。",
    "st3.h": "运行时",
    "st3.p": "内置打分器或 ONNX 工件驱动 contact / slip 基线。",
    "st4.h": "事件",
    "st4.p": "<code>TactileEvent</code> 标记到同步的 Rerun 时间轴，支持人工标注。",
    "st5.h": "基准",
    "st5.p": "可复现的逐 episode 报告，含质量与标定追踪。",
    "sec.sensors.h": "五款传感器，一套触觉接口。",
    "sec.sensors.p": "五款传感器协议层——串口矩阵、六维力/扭矩、关节扭矩与视觉触觉——全部通过离线验证，单元测试与厂商文档逐字节对齐。",
    "sn.th1": "传感器",
    "sn.th2": "输出",
    "sn.th3": "链路",
    "sn.th4": "状态",
    "sn.r1name": "M0404S<span>压阻矩阵套件</span>",
    "sn.r1out": "4×4 矩阵 · 16 触点",
    "sn.r1link": "UART 115200，主动上报",
    "sn.r2name": "帕西尼 PX-6AX GEN3<span>触觉皮肤</span>",
    "sn.r2out": "逐点三轴力 + 合力",
    "sn.r2link": "UART 921600，请求-应答",
    "sn.r3name": "帕西尼 PX6D<span>六维力/扭矩</span>",
    "sn.r3out": "Fx, Fy, Fz, Mx, My, Mz · float32",
    "sn.r3link": "USB / RS485 · 1 kHz",
    "sn.r4name": "帕西尼 PX3Q<span>关节扭矩</span>",
    "sn.r4out": "Mx, My, Mz · N·m · 满量程 30/50/100",
    "sn.r4link": "USB / RS485 · 921600",
    "sn.ok": "● 就绪",
    "sn.r5name": "Meta DIGIT<span>视觉触觉</span>",
    "sn.r5out": "320×240 RGB 凝胶图像",
    "sn.r5link": "USB UVC · QVGA 60fps",
    "sn.okDigit": "● 就绪",
    "sec.roadmap.h": "构建里程碑",
    "sec.roadmap.p": "从核心契约到跨传感器语义，按里程碑交付。",
    "ph1.tag": "PHASE 0–2",
    "ph1.h": "契约、数据通路与回放",
    "ph1.p": "Package 与核心契约；Open-X-Tactile 适配器覆盖图像 / 矩阵 / F/T 流；MCAP 导出与 Rerun 回放，支持 C/S/U 标注。",
    "ph2.tag": "PHASE 3",
    "ph2.h": "运行时与基准",
    "ph2.p": "内置与 ONNX 打分后端、时序 contact / slip 基线及可复现报告。模型质量评估仍需带标注的数据。",
    "ph3.tag": "PHASE 4",
    "ph3.h": "质量与标定",
    "ph3.p": "两级 capability 校验、数据集质量健康报告、标定溯源、按 stream 分组的基准。",
    "ph4.tag": "PHASE 5",
    "ph4.h": "首块实时传感器",
    "ph4.p": "实时串口适配器、实时 record / replay / inference、断连重连处理与 30 分钟稳定性运行。",
    "ph5.tag": "PHASE 6",
    "ph5.h": "v0.1 发布",
    "ph5.p": "面向外部用户的 Quickstart、英文文档与 v0.1 正式版。",
    "sec.qs.h": "先跑通一个离线演示。",
    "sec.qs.p": "需要 Python 3.12+。从 <a href=\"https://pypi.org/project/tacstack/\">PyPI</a> 安装 alpha 版，或克隆源码获得完整离线导览。无需传感器或下载数据集。",
    "qs.copy": "复制",
    "qs.copied": "已复制 ✓",
    "qs.terminal": "<span class=\"tok-c\"># 从 PyPI 安装 alpha 版（需要 Python 3.12+）</span>\npip install --pre tacstack\n\n<span class=\"tok-c\"># 离线验证——不下载、不连硬件</span>\ntacstack version\ntacstack contract-demo\n\n<span class=\"tok-c\"># 源码方式：引导式演示 + 内置样本 + Rerun 回放</span>\ngit clone https://github.com/mailes/TacStack.git && cd TacStack\nuv sync --extra rerun\n<span class=\"tok-p\">uv run</span> tacstack demo",
    "foot.desc": "面向机器人的跨传感器触觉语义与运行时。Raw-first · Semantics-first · Edge-first · Integration-first。",
    "foot.col1": "项目",
    "foot.l1": "GitHub 仓库",
    "foot.l2": "开发路线",
    "foot.col2": "文档",
    "foot.l4": "架构",
    "foot.l5": "Adapter 指南",
    "foot.l6": "贡献指南",
    "foot.bottom1": "© <span id=\"year\">2026</span> TacStack 贡献者 · Apache-2.0",
    "foot.bottom2": "为有触觉的机器人而造。",
    "hero.status": "离线链路端到端打通 · PyPI alpha 已发布",
    "visual.title": "信号 → 语义",
    "visual.label": "触点阵列输入示意",
    "visual.sub": "不同输入，共用一套观测契约。",
    "visual.output": "事件示例 · 非实时读数",
    "qs.note": "内置样本与下方事件均为合成示例。模型效果需要使用实际数据评估。PyPI 已发布 alpha 版（0.1.0a1）；引导式 demo 需要源码仓库。",
    "qs.failed": "选中并复制",
    "qs.manual": "剪贴板不可用，代码已选中，请使用系统复制操作。",
    "nav.menu": "菜单",
    "nav.close": "收起",
    "skip": "跳转到正文",
    "touch.lab": "触觉实验室 / 交互概念演示",
    "touch.prompt": "触碰，建立连接",
    "touch.output": "触觉响应",
    "touch.simulated": "交互模拟",
    "touch.pressure": "信号强度",
    "touch.hint": "按住模拟接触，拖动模拟滑移。键盘可使用回车或空格。",
    "touch.pause": "暂停特效",
    "touch.resume": "开启特效",
    "touch.announcement": "模拟事件："
  }
};
let lang = "en";
const t = key => I18N[lang][key] ?? I18N.en[key] ?? "";
const menu = document.querySelector(".menu-toggle");
const navigation = document.getElementById("nav-links");
const status = document.getElementById("copy-status");
function setMenu(open) {
  navigation.classList.toggle("is-open", open);
  menu.setAttribute("aria-expanded", String(open));
  menu.textContent = t(open ? "nav.close" : "nav.menu");
}
function setLang(next) {
  lang = next === "zh" ? "zh" : "en";
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = t("meta.title");
  document.querySelector('meta[name="description"]').content = t("meta.desc");
  document.querySelector('meta[property="og:title"]').content = t("meta.title");
  document.querySelector('meta[property="og:description"]').content = t("meta.desc");
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (key in I18N.en) el.innerHTML = t(key);
  });
  document.querySelectorAll("[data-lang]").forEach(button => {
    const active = button.dataset.lang === lang;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.getElementById("year").textContent = new Date().getFullYear();
  setMenu(navigation.classList.contains("is-open"));
  document.dispatchEvent(new Event("tacstack:language"));
  try { localStorage.setItem("tacstack-lang", lang); } catch { /* Storage is optional. */ }
}
let saved;
try { saved = localStorage.getItem("tacstack-lang"); } catch { /* Storage is optional. */ }
const preferred = (navigator.languages?.[0] || navigator.language || "en").toLowerCase();
setLang(["en", "zh"].includes(saved) ? saved : preferred.startsWith("zh") ? "zh" : "en");
document.querySelectorAll("[data-lang]").forEach(button => {
  button.addEventListener("click", () => setLang(button.dataset.lang));
});
menu.addEventListener("click", () => setMenu(menu.getAttribute("aria-expanded") !== "true"));
navigation.querySelectorAll("a").forEach(link => link.addEventListener("click", () => setMenu(false)));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
    setMenu(false);
    menu.focus();
  }
});
document.querySelectorAll(".copy").forEach(button => {
  let timeout;
  button.addEventListener("click", async () => {
    clearTimeout(timeout);
    const code = document.getElementById(button.dataset.copy);
    button.disabled = true;
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = t("qs.copied");
      status.textContent = t("qs.copied");
    } catch {
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = t("qs.failed");
      status.textContent = t("qs.manual");
    } finally {
      button.disabled = false;
      timeout = setTimeout(() => { button.textContent = t("qs.copy"); }, 2000);
    }
  });
});
// Only collapse mobile navigation after its handlers are ready; content is always visible.
document.documentElement.classList.add("js");

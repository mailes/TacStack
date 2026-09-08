"use strict";
const I18N = {
  "en": {
    "meta.title": "TacStack — Cross-sensor tactile semantics for robotics",
    "meta.desc": "TacStack keeps raw tactile data intact and layers a unified Observation, model interface and Event contract on top — one contract for every tactile sensor.",
    "nav.principles": "Principles",
    "nav.pipeline": "Pipeline",
    "nav.sensors": "Sensors",
    "nav.roadmap": "Roadmap",
    "nav.quickstart": "Quick start",
    "hero.eyebrow": "Open source · Apache-2.0 · Python 3.12+",
    "hero.h1": "One interface.<br>Many sensors.<br><span class=\"grad\">A sense of touch.</span>",
    "hero.lede": "Build with tactile images, taxel arrays and force/torque data through a shared interface. Preserve the raw signal. Run contact and slip baselines. Replay, inspect and benchmark locally.",
    "hero.cta1": "Get started",
    "hero.cta2": "View source",
    "hero.stat1": "sensor protocol codecs",
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
    "pr.int.p": "Record with MCAP, inspect with Rerun and connect to existing tools. ROS2 and LeRobot integrations are planned.",
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
    "sec.sensors.h": "Software ready. Hardware is next.",
    "sec.sensors.p": "Four protocol codecs have tests based on vendor manual examples. Live acquisition and real-world stability will be verified when the sensors arrive.",
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
    "sn.ok": "● codec ready",
    "sn.note": "PX6D / PX3Q response CRC validation remains open until hardware captures are available. Protocol tests do not establish live sensor performance.",
    "sn.badgeSoon": "Hardware testing pending",
    "sec.roadmap.h": "Where the project stands",
    "sec.roadmap.p": "Phase 0–4 are complete. The next milestone is the first live sensor.",
    "ph1.tag": "PHASE 0–2 · DONE",
    "ph1.h": "Contracts, data path, replay",
    "ph1.p": "Package and core contracts; Open-X-Tactile adapter for image / matrix / F/T streams; MCAP export and Rerun replay with C/S/U annotation.",
    "ph2.tag": "PHASE 3 · DONE",
    "ph2.h": "Runtime & benchmark",
    "ph2.p": "Builtin and ONNX scoring backends, temporal contact / slip baselines and repeatable reports. Model-quality evaluation requires labeled data.",
    "ph3.tag": "PHASE 4 · DONE",
    "ph3.h": "Quality & calibration",
    "ph3.p": "Two-level capability validation, dataset quality health reports, calibration provenance, per-stream benchmark grouping.",
    "ph4.tag": "PHASE 5 · IN PROGRESS",
    "ph4.h": "First live sensor",
    "ph4.p": "Live serial adapter, live record / replay / inference, device reconnect handling and a 30-minute stability run. Codecs are ready; hardware is on the way.",
    "ph5.tag": "PHASE 6 · PLANNED",
    "ph5.h": "v0.1 release",
    "ph5.p": "External-user Quickstart, English documentation and the first tagged release.",
    "sec.qs.h": "Start with a working offline demo.",
    "sec.qs.p": "Python 3.12+ and <a href=\"https://docs.astral.sh/uv/\">uv</a>. Install from source, then explore the bundled synthetic fixture. No sensor or dataset download needed.",
    "qs.copy": "copy",
    "qs.copied": "copied ✓",
    "qs.terminal": "<span class=\"tok-c\"># clone and install (uv manages everything)</span>\ngit clone https://github.com/mailes/TacStack.git\ncd TacStack\nuv sync --extra rerun\n\n<span class=\"tok-c\"># guided tour — no data download, no hardware</span>\n<span class=\"tok-p\">uv run</span> tacstack demo\n\n<span class=\"tok-c\"># replay the bundled synthetic fixture in Rerun</span>\n<span class=\"tok-p\">uv run</span> tacstack replay \\\n  tests/fixtures/open_x_tactile/demo_wipe.tar --viewer",
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
    "hero.status": "Offline pipeline ready · Hardware validation next",
    "visual.title": "SIGNAL → SEMANTICS",
    "visual.label": "Illustrative taxel input",
    "visual.sub": "Different inputs. A shared observation contract.",
    "visual.output": "Example event · not a live reading",
    "qs.note": "The bundled fixture and the event below are synthetic. Use your own recordings to evaluate model behavior. Not yet published on PyPI.",
    "qs.failed": "Select & copy",
    "qs.manual": "Clipboard unavailable. The code is selected; use your system copy command.",
    "nav.menu": "Menu",
    "nav.close": "Close",
    "skip": "Skip to content"
  },
  "zh": {
    "meta.title": "TacStack — 面向机器人的跨传感器触觉语义与运行时",
    "meta.desc": "TacStack 原样保留触觉原始数据，并在其上构建统一的 Observation、模型接口与事件契约——一套契约，贯通所有触觉传感器。",
    "nav.principles": "原则",
    "nav.pipeline": "管线",
    "nav.sensors": "传感器",
    "nav.roadmap": "路线图",
    "nav.quickstart": "快速开始",
    "hero.eyebrow": "开源 · Apache-2.0 · Python 3.12+",
    "hero.h1": "多种传感器。<br>统一接口。<br><span class=\"grad\">让机器人感知触碰。</span>",
    "hero.lede": "通过统一接口使用触觉图像、触点阵列和力 / 扭矩数据。保留原始信号，运行接触与滑移基线，在本地完成回放、调试与评估。",
    "hero.cta1": "快速开始",
    "hero.cta2": "查看源码",
    "hero.stat1": "款传感器协议 codec",
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
    "pr.int.p": "使用 MCAP 记录、Rerun 查看，接入现有工具生态。ROS2 与 LeRobot 集成仍在规划中。",
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
    "sec.sensors.h": "软件已就绪，下一步走向真实硬件。",
    "sec.sensors.p": "四款协议 codec 已基于厂商手册示例编写测试。传感器到位后，将验证实时采集与真实环境下的运行稳定性。",
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
    "sn.ok": "● codec 就绪",
    "sn.note": "PX6D / PX3Q 响应帧 CRC 校验仍待硬件抓包确认。协议测试不等于真实设备性能验证。",
    "sn.badgeSoon": "等待硬件实测",
    "sec.roadmap.h": "项目当前进展",
    "sec.roadmap.p": "Phase 0–4 已完成。下一个里程碑是第一块实时传感器。",
    "ph1.tag": "PHASE 0–2 · 已完成",
    "ph1.h": "契约、数据通路与回放",
    "ph1.p": "Package 与核心契约；Open-X-Tactile 适配器覆盖图像 / 矩阵 / F/T 流；MCAP 导出与 Rerun 回放，支持 C/S/U 标注。",
    "ph2.tag": "PHASE 3 · 已完成",
    "ph2.h": "运行时与基准",
    "ph2.p": "内置与 ONNX 打分后端、时序 contact / slip 基线及可复现报告。模型质量评估仍需带标注的数据。",
    "ph3.tag": "PHASE 4 · 已完成",
    "ph3.h": "质量与标定",
    "ph3.p": "两级 capability 校验、数据集质量健康报告、标定溯源、按 stream 分组的基准。",
    "ph4.tag": "PHASE 5 · 进行中",
    "ph4.h": "首块实时传感器",
    "ph4.p": "实时串口适配器、实时 record / replay / inference、断连重连处理与 30 分钟稳定性运行。Codec 已就绪，硬件在途。",
    "ph5.tag": "PHASE 6 · 规划中",
    "ph5.h": "v0.1 发布",
    "ph5.p": "面向外部用户的 Quickstart、英文文档与首个正式版本。",
    "sec.qs.h": "先跑通一个离线演示。",
    "sec.qs.p": "需要 Python 3.12+ 和 <a href=\"https://docs.astral.sh/uv/\">uv</a>。从源码安装，使用随项目提供的合成样本，无需传感器或下载数据集。",
    "qs.copy": "复制",
    "qs.copied": "已复制 ✓",
    "qs.terminal": "<span class=\"tok-c\"># 克隆并安装（uv 管理一切依赖）</span>\ngit clone https://github.com/mailes/TacStack.git\ncd TacStack\nuv sync --extra rerun\n\n<span class=\"tok-c\"># 引导式演示——不下载、不连硬件</span>\n<span class=\"tok-p\">uv run</span> tacstack demo\n\n<span class=\"tok-c\"># 将内置合成样本回放到 Rerun</span>\n<span class=\"tok-p\">uv run</span> tacstack replay \\\n  tests/fixtures/open_x_tactile/demo_wipe.tar --viewer",
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
    "hero.status": "离线链路已打通 · 即将进行真实硬件验证",
    "visual.title": "信号 → 语义",
    "visual.label": "触点阵列输入示意",
    "visual.sub": "不同输入，共用一套观测契约。",
    "visual.output": "事件示例 · 非实时读数",
    "qs.note": "内置样本与下方事件均为合成示例。模型效果需要使用实际数据评估；项目尚未发布到 PyPI。",
    "qs.failed": "选中并复制",
    "qs.manual": "剪贴板不可用，代码已选中，请使用系统复制操作。",
    "nav.menu": "菜单",
    "nav.close": "收起",
    "skip": "跳转到正文"
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

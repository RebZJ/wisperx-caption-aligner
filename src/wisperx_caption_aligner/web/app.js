const state = {
  project: null,
  captions: [],
  selected: new Set(),
  durationMs: 0,
  pixelsPerMs: 0.11,
  audioBuffer: null,
  drag: null,
  marquee: null,
  raf: null,
};

const els = {
  audio: document.getElementById("audio"),
  playButton: document.getElementById("playButton"),
  timeReadout: document.getElementById("timeReadout"),
  projectMeta: document.getElementById("projectMeta"),
  selectionReadout: document.getElementById("selectionReadout"),
  status: document.getElementById("status"),
  timelineScroll: document.getElementById("timelineScroll"),
  timeline: document.getElementById("timeline"),
  waveform: document.getElementById("waveform"),
  ruler: document.getElementById("ruler"),
  captionLayer: document.getElementById("captionLayer"),
  scrubber: document.getElementById("scrubber"),
  marquee: document.getElementById("marquee"),
  nudgeInput: document.getElementById("nudgeInput"),
  nudgeLeft: document.getElementById("nudgeLeft"),
  nudgeRight: document.getElementById("nudgeRight"),
  zoomInput: document.getElementById("zoomInput"),
  saveButton: document.getElementById("saveButton"),
  downloadButton: document.getElementById("downloadButton"),
};

const MIN_DURATION_MS = 24;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function captionStart(caption) {
  return Math.max(0, Math.round(Number(caption.startMs ?? caption.timestampMs ?? 0)));
}

function captionEnd(caption) {
  const start = captionStart(caption);
  return Math.max(start + MIN_DURATION_MS, Math.round(Number(caption.endMs ?? start + 120)));
}

function normalizeCaptions(captions) {
  return captions
    .map((caption, index) => {
      const startMs = captionStart(caption);
      const endMs = captionEnd(caption);
      return {
        ...caption,
        text: String(caption.text ?? ""),
        startMs,
        endMs,
        timestampMs: startMs,
        _id: crypto.randomUUID ? crypto.randomUUID() : `caption-${index}-${Date.now()}`,
      };
    })
    .sort((a, b) => a.startMs - b.startMs);
}

function publicCaptions() {
  return state.captions
    .slice()
    .sort((a, b) => a.startMs - b.startMs)
    .map(({ _id, ...caption }) => ({
      ...caption,
      startMs: Math.round(caption.startMs),
      endMs: Math.round(caption.endMs),
      timestampMs: Math.round(caption.startMs),
    }));
}

function formatTime(ms) {
  const safe = Math.max(0, ms);
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const millis = Math.floor(safe % 1000);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function setStatus(message) {
  els.status.textContent = message;
}

function selectedIndexes() {
  return [...state.selected].sort((a, b) => a - b);
}

function px(ms) {
  return ms * state.pixelsPerMs;
}

function msFromClientX(clientX) {
  const rect = els.timeline.getBoundingClientRect();
  return clamp((clientX - rect.left) / state.pixelsPerMs, 0, state.durationMs);
}

async function init() {
  setStatus("loading");
  const response = await fetch("/api/project");
  state.project = await response.json();
  state.captions = normalizeCaptions(state.project.captions);
  els.audio.src = state.project.audioUrl;
  els.projectMeta.textContent = `${state.project.audioFileName} -> ${state.project.outputPath}`;

  await Promise.all([loadAudioBuffer(), waitForAudioMetadata()]);
  state.durationMs = Math.max(
    Math.ceil(els.audio.duration * 1000),
    ...state.captions.map((caption) => caption.endMs),
    1000,
  );
  layoutTimeline();
  renderAll();
  bindEvents();
  tick();
  setStatus("ready");
}

async function waitForAudioMetadata() {
  if (Number.isFinite(els.audio.duration) && els.audio.duration > 0) {
    return;
  }
  await new Promise((resolve) => {
    els.audio.addEventListener("loadedmetadata", resolve, { once: true });
  });
}

async function loadAudioBuffer() {
  const audioContext = new AudioContext();
  const response = await fetch(state.project.audioUrl);
  const bytes = await response.arrayBuffer();
  state.audioBuffer = await audioContext.decodeAudioData(bytes.slice(0));
  await audioContext.close();
}

function bindEvents() {
  els.playButton.addEventListener("click", togglePlayback);
  els.audio.addEventListener("play", () => {
    els.playButton.textContent = "Pause";
  });
  els.audio.addEventListener("pause", () => {
    els.playButton.textContent = "Play";
  });
  els.zoomInput.addEventListener("input", () => {
    const currentMs = els.audio.currentTime * 1000;
    state.pixelsPerMs = Number(els.zoomInput.value);
    layoutTimeline();
    renderAll();
    els.timelineScroll.scrollLeft = Math.max(0, px(currentMs) - els.timelineScroll.clientWidth * 0.35);
  });
  els.nudgeLeft.addEventListener("click", () => nudgeSelected(-nudgeAmount()));
  els.nudgeRight.addEventListener("click", () => nudgeSelected(nudgeAmount()));
  els.saveButton.addEventListener("click", saveCaptions);
  els.downloadButton.addEventListener("click", downloadCaptions);
  els.timeline.addEventListener("pointerdown", onTimelinePointerDown);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("keydown", onKeyDown);
}

function togglePlayback() {
  if (els.audio.paused) {
    els.audio.play();
  } else {
    els.audio.pause();
  }
}

function nudgeAmount() {
  return Math.max(1, Math.round(Number(els.nudgeInput.value) || 20));
}

function layoutTimeline() {
  const width = Math.ceil(px(state.durationMs) + 480);
  els.timeline.style.width = `${width}px`;
  els.captionLayer.style.height = `${Math.max(390, state.captions.length * 25 + 80)}px`;
}

function renderAll() {
  renderWaveform();
  renderRuler();
  renderCaptions();
  updateSelectionReadout();
  updateScrubber();
}

function renderWaveform() {
  const canvas = els.waveform;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);

  ctx.fillStyle = "#0a0d0b";
  ctx.fillRect(0, 0, rect.width, rect.height);

  if (!state.audioBuffer) {
    return;
  }

  const samples = state.audioBuffer.getChannelData(0);
  const width = Math.floor(rect.width);
  const height = Math.floor(rect.height);
  const mid = height * 0.52;
  const step = Math.max(1, Math.floor(samples.length / width));

  ctx.strokeStyle = "rgba(76, 255, 131, 0.18)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, mid);
  ctx.lineTo(width, mid);
  ctx.stroke();

  for (let x = 0; x < width; x += 1) {
    let min = 1;
    let max = -1;
    const start = x * step;
    for (let i = 0; i < step; i += 1) {
      const sample = samples[start + i] || 0;
      min = Math.min(min, sample);
      max = Math.max(max, sample);
    }
    const amp = Math.max(Math.abs(min), Math.abs(max));
    const hue = 125 + amp * 45;
    ctx.strokeStyle = `hsla(${hue}, 100%, 66%, ${0.32 + amp * 0.5})`;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, mid + min * height * 0.42);
    ctx.lineTo(x + 0.5, mid + max * height * 0.42);
    ctx.stroke();
  }
}

function renderRuler() {
  els.ruler.innerHTML = "";
  const major = 1000;
  const minor = 250;
  for (let ms = 0; ms <= state.durationMs; ms += minor) {
    const tick = document.createElement("div");
    tick.className = ms % major === 0 ? "tick major" : "tick";
    tick.style.left = `${px(ms)}px`;
    if (ms % major === 0) {
      const label = document.createElement("span");
      label.textContent = formatTime(ms).slice(0, 5);
      tick.appendChild(label);
    }
    els.ruler.appendChild(tick);
  }
}

function renderCaptions() {
  els.captionLayer.innerHTML = "";
  state.captions.forEach((caption, index) => {
    const block = document.createElement("div");
    block.className = "caption-block";
    block.dataset.index = String(index);
    block.style.left = `${px(caption.startMs)}px`;
    block.style.top = `${(index % 11) * 54}px`;
    block.style.width = `${Math.max(10, px(caption.endMs - caption.startMs))}px`;
    if (state.selected.has(index)) {
      block.classList.add("selected");
    }

    const left = document.createElement("div");
    left.className = "handle left";
    left.dataset.side = "left";
    const label = document.createElement("div");
    label.className = "caption-label";
    label.textContent = caption.text;
    const right = document.createElement("div");
    right.className = "handle right";
    right.dataset.side = "right";

    block.append(left, label, right);
    els.captionLayer.appendChild(block);
  });
}

function onTimelinePointerDown(event) {
  const block = event.target.closest(".caption-block");
  const handle = event.target.closest(".handle");
  if (block) {
    const index = Number(block.dataset.index);
    if (handle) {
      state.selected = new Set([index]);
      state.drag = {
        type: "resize",
        index,
        side: handle.dataset.side,
        startClientX: event.clientX,
        original: { ...state.captions[index] },
      };
      renderCaptions();
      event.preventDefault();
      return;
    }

    if (event.shiftKey) {
      if (state.selected.has(index)) {
        state.selected.delete(index);
      } else {
        state.selected.add(index);
      }
    } else if (!state.selected.has(index)) {
      state.selected = new Set([index]);
    }

    state.drag = {
      type: "move",
      startClientX: event.clientX,
      originals: selectedIndexes().map((selectedIndex) => ({
        index: selectedIndex,
        startMs: state.captions[selectedIndex].startMs,
        endMs: state.captions[selectedIndex].endMs,
      })),
    };
    renderCaptions();
    event.preventDefault();
    return;
  }

  const ms = msFromClientX(event.clientX);
  els.audio.currentTime = ms / 1000;
  state.selected.clear();
  const rect = els.timeline.getBoundingClientRect();
  state.marquee = {
    startX: event.clientX - rect.left,
    startY: event.clientY - rect.top,
    currentX: event.clientX - rect.left,
    currentY: event.clientY - rect.top,
  };
  updateMarquee();
  renderCaptions();
}

function onPointerMove(event) {
  if (state.drag?.type === "move") {
    const dx = event.clientX - state.drag.startClientX;
    let deltaMs = Math.round(dx / state.pixelsPerMs);
    const minStart = Math.min(...state.drag.originals.map((item) => item.startMs));
    deltaMs = Math.max(deltaMs, -minStart);
    state.drag.originals.forEach((item) => {
      state.captions[item.index].startMs = item.startMs + deltaMs;
      state.captions[item.index].endMs = item.endMs + deltaMs;
      state.captions[item.index].timestampMs = item.startMs + deltaMs;
    });
    renderCaptions();
    return;
  }

  if (state.drag?.type === "resize") {
    const dx = event.clientX - state.drag.startClientX;
    const deltaMs = Math.round(dx / state.pixelsPerMs);
    const caption = state.captions[state.drag.index];
    if (state.drag.side === "left") {
      caption.startMs = clamp(state.drag.original.startMs + deltaMs, 0, caption.endMs - MIN_DURATION_MS);
    } else {
      caption.endMs = Math.max(caption.startMs + MIN_DURATION_MS, state.drag.original.endMs + deltaMs);
    }
    caption.timestampMs = caption.startMs;
    state.durationMs = Math.max(state.durationMs, caption.endMs);
    layoutTimeline();
    renderAll();
    return;
  }

  if (state.marquee) {
    const rect = els.timeline.getBoundingClientRect();
    state.marquee.currentX = event.clientX - rect.left;
    state.marquee.currentY = event.clientY - rect.top;
    updateMarquee();
    selectFromMarquee();
  }
}

function onPointerUp() {
  if (state.drag || state.marquee) {
    state.drag = null;
    state.marquee = null;
    els.marquee.classList.add("hidden");
    renderCaptions();
    updateSelectionReadout();
  }
}

function updateMarquee() {
  const marquee = state.marquee;
  if (!marquee) {
    return;
  }
  const left = Math.min(marquee.startX, marquee.currentX);
  const top = Math.min(marquee.startY, marquee.currentY);
  const width = Math.abs(marquee.currentX - marquee.startX);
  const height = Math.abs(marquee.currentY - marquee.startY);
  els.marquee.classList.remove("hidden");
  els.marquee.style.left = `${left}px`;
  els.marquee.style.top = `${top}px`;
  els.marquee.style.width = `${width}px`;
  els.marquee.style.height = `${height}px`;
}

function selectFromMarquee() {
  const marqueeRect = els.marquee.getBoundingClientRect();
  const next = new Set();
  els.captionLayer.querySelectorAll(".caption-block").forEach((block) => {
    const blockRect = block.getBoundingClientRect();
    const intersects =
      blockRect.left <= marqueeRect.right &&
      blockRect.right >= marqueeRect.left &&
      blockRect.top <= marqueeRect.bottom &&
      blockRect.bottom >= marqueeRect.top;
    if (intersects) {
      next.add(Number(block.dataset.index));
    }
  });
  state.selected = next;
  renderCaptions();
  updateSelectionReadout();
}

function nudgeSelected(deltaMs) {
  if (state.selected.size === 0) {
    setStatus("select captions first");
    return;
  }
  const indexes = selectedIndexes();
  const minStart = Math.min(...indexes.map((index) => state.captions[index].startMs));
  const safeDelta = Math.max(deltaMs, -minStart);
  indexes.forEach((index) => {
    state.captions[index].startMs += safeDelta;
    state.captions[index].endMs += safeDelta;
    state.captions[index].timestampMs = state.captions[index].startMs;
  });
  renderCaptions();
  setStatus(`nudged ${safeDelta}ms`);
}

function updateSelectionReadout() {
  els.selectionReadout.textContent = `${state.selected.size} selected`;
}

function updateScrubber() {
  const currentMs = els.audio.currentTime * 1000;
  els.scrubber.style.left = `${px(currentMs)}px`;
  els.timeReadout.textContent = `${formatTime(currentMs)} / ${formatTime(state.durationMs)}`;
  const activeIndex = state.captions.findIndex(
    (caption) => currentMs >= caption.startMs && currentMs <= caption.endMs,
  );
  els.captionLayer.querySelectorAll(".caption-block").forEach((block) => {
    block.classList.toggle("active", Number(block.dataset.index) === activeIndex);
  });

  if (!els.audio.paused) {
    const x = px(currentMs);
    const rightEdge = els.timelineScroll.scrollLeft + els.timelineScroll.clientWidth * 0.82;
    if (x > rightEdge) {
      els.timelineScroll.scrollLeft = x - els.timelineScroll.clientWidth * 0.45;
    }
  }
}

function tick() {
  updateScrubber();
  state.raf = requestAnimationFrame(tick);
}

function onKeyDown(event) {
  if (event.target.tagName === "INPUT") {
    return;
  }
  if (event.code === "Space") {
    event.preventDefault();
    togglePlayback();
  }
  if (event.code === "ArrowLeft") {
    event.preventDefault();
    nudgeSelected(event.shiftKey ? -1 : -nudgeAmount());
  }
  if (event.code === "ArrowRight") {
    event.preventDefault();
    nudgeSelected(event.shiftKey ? 1 : nudgeAmount());
  }
  if ((event.metaKey || event.ctrlKey) && event.code === "KeyS") {
    event.preventDefault();
    saveCaptions();
  }
}

function validateForBrowser(captions) {
  for (const [index, caption] of captions.entries()) {
    if (caption.startMs < 0 || caption.endMs < caption.startMs) {
      return `caption ${index} has invalid timing`;
    }
    if (index > 0 && caption.startMs < captions[index - 1].startMs) {
      return `caption ${index} starts before the previous caption`;
    }
  }
  return null;
}

async function saveCaptions() {
  const captions = publicCaptions();
  const error = validateForBrowser(captions);
  if (error) {
    setStatus(error);
    return;
  }

  setStatus("saving");
  const response = await fetch("/api/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ captions }),
  });
  const payload = await response.json();
  if (!payload.ok) {
    setStatus(payload.error || "save failed");
    return;
  }
  setStatus(`saved ${payload.count}`);
}

function downloadCaptions() {
  const blob = new Blob([JSON.stringify(publicCaptions(), null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "captions.edited.json";
  link.click();
  URL.revokeObjectURL(link.href);
  setStatus("exported");
}

init().catch((error) => {
  console.error(error);
  setStatus(error.message || "failed");
});

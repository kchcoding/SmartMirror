// 스마트미러 화면 로직. 프레임워크 없이 순수 JS (빌드 과정 없음).
// 흐름: 서버 /api/state 를 1분마다 가져와서 → 각 위젯을 다시 그린다.

const $ = (sel) => document.querySelector(sel);
const pad = (n) => String(n).padStart(2, "0");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const DAYS = ["일", "월", "화", "수", "목", "금", "토"];

const STATE_EVERY_MS = 60_000;
const BRIEFING_EVERY_MS = 30 * 60_000;
const OUTFIT_ROTATE_MS = 20_000;

let state = null;
let candIdx = 0;
let lastSelection = "";

// ── 시계 (서버 없이 브라우저에서 1초마다) ──
function tickClock() {
  const n = new Date();
  $("#time").textContent = `${pad(n.getHours())}:${pad(n.getMinutes())}`;
  $("#date").textContent = `${n.getMonth() + 1}월 ${n.getDate()}일 ${DAYS[n.getDay()]}요일`;
}

// ── 알림 ──
function renderAlerts() {
  $("#alerts").innerHTML = state.alerts
    .map((a) => `<div class="alert ${esc(a.level)}"><span>${a.icon}</span><span>${esc(a.message)}</span></div>`)
    .join("");
}

// ── 날씨 + 대기질 ──
function renderWeather() {
  const w = state.weather;
  if (!w) {
    $("#weather").innerHTML = `<div class="muted">날씨 정보를 불러오지 못했어요</div>`;
    return;
  }
  const hours = w.hourly.filter((_, i) => i % 3 === 0).slice(0, 4)
    .map((h) => `<div class="hour"><span>${h.hour}시</span><span>${Math.round(h.temp)}°</span><span class="pop">${h.pop}%</span></div>`)
    .join("");
  const air = state.air ? ` · 초미세먼지 ${esc(state.air.pm25_grade)}` : "";
  $("#weather").innerHTML = `
    <div class="w-main"><span class="w-icon">${w.icon}</span><span class="w-temp">${Math.round(w.temp)}°</span></div>
    <div class="w-sub">${esc(w.city)} · ${esc(w.summary)} · 체감 ${Math.round(w.feels_like)}°</div>
    <div class="w-sub">최저 ${Math.round(w.temp_min)}° / 최고 ${Math.round(w.temp_max)}°${air}</div>
    <div class="hours">${hours}</div>`;
}

// ── 실내 환경 ──
function renderIndoor() {
  const i = state.indoor;
  if (i.temp == null) {
    $("#indoor").innerHTML = `<div class="muted">실내 센서 연결 중…</div>`;
    return;
  }
  $("#indoor").innerHTML = `
    <h3>실내</h3>
    <div class="in-big">${i.temp.toFixed(1)}° · ${Math.round(i.humidity)}%</div>
    <div class="in-sub">습도 ${esc(i.humidity_label)} · 불쾌지수 ${esc(i.discomfort_label)}</div>`;
}

// ── 일정 + 할 일 ──
function renderAgenda() {
  const events = state.events.map((e) =>
    `<div class="row"><span class="when">${esc(e.start)}</span><span>${esc(e.title)}</span></div>`).join("");
  const todos = state.todos.map((t) =>
    `<div class="row ${t.done ? "done" : ""}"><span class="when">${t.done ? "✓" : "○"}</span><span>${esc(t.text)}</span></div>`).join("");
  $("#agenda").innerHTML = `
    <h3>오늘 일정</h3>${events || `<div class="muted">일정이 없어요</div>`}
    <div class="agenda-gap"></div>
    <h3>할 일</h3>${todos || `<div class="muted">할 일이 없어요</div>`}`;
}

// ── 코디 추천 ──
function renderOutfit() {
  const box = $("#outfit");
  const o = state.outfit;
  if (!o) { box.innerHTML = `<div class="muted">코디는 날씨 정보가 있어야 계산할 수 있어요</div>`; return; }
  if (!o.candidates.length) { box.innerHTML = `<div class="muted">${esc(o.message)}</div>`; return; }

  const c = o.candidates[candIdx % o.candidates.length];
  const items = ["top", "bottom", "outer"].filter((k) => c[k])
    .map((k) => `<figure><img src="${c[k].cutout_url}" alt=""><figcaption>${esc(c[k].name)}</figcaption></figure>`).join("");
  const dots = o.candidates.map((_, i) => `<i class="${i === candIdx % o.candidates.length ? "on" : ""}"></i>`).join("");
  box.innerHTML = `
    <h3>오늘의 코디<small>체감 ${Math.round(o.feels_like)}°</small></h3>
    <div class="items">${items}</div>
    <ul class="reasons">${c.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
    <div class="dots">${dots}</div>`;
  applyTryOn(c);
}

// 현재 코디를 시착 엔진에 알려준다 (바뀐 경우에만)
async function applyTryOn(c) {
  const sel = { top: c.top?.id ?? null, bottom: c.bottom?.id ?? null, outer: c.outer?.id ?? null };
  const key = JSON.stringify(sel);
  if (key === lastSelection) return;
  lastSelection = key;
  fetch("/api/tryon/select", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sel) }).catch(() => {});
}

// ── 시착 카메라 (켜져 있을 때만 표시) ──
async function checkTryOn() {
  try {
    const s = await (await fetch("/api/tryon/status")).json();
    const box = $("#tryon");
    if (s.available && box.hidden) {
      box.innerHTML = `<img src="/api/tryon/stream" alt="가상 시착">`;
      box.hidden = false;
    }
  } catch { /* 서버 연결 실패는 loadState 에서 처리 */ }
}

// ── 데이터 로드 ──
async function loadState() {
  try {
    state = await (await fetch("/api/state")).json();
    $("#link-status").classList.remove("down");
    document.body.classList.toggle("asleep", state.indoor.presence === false);  // PIR 센서: 사람 없으면 화면 끔
    renderAlerts(); renderWeather(); renderIndoor(); renderAgenda(); renderOutfit();
  } catch {
    $("#link-status").classList.add("down");
  }
}

async function loadBriefing() {
  try {
    const b = await (await fetch("/api/briefing")).json();
    $("#briefing").textContent = b.text;
  } catch { /* 이전 문구 유지 */ }
}

// 코디 후보를 20초마다 돌려가며 보여준다
setInterval(() => { if (state?.outfit?.candidates?.length > 1) { candIdx++; renderOutfit(); } }, OUTFIT_ROTATE_MS);

tickClock(); setInterval(tickClock, 1000);
loadState().then(() => { checkTryOn(); loadBriefing(); });
setInterval(loadState, STATE_EVERY_MS);
setInterval(loadBriefing, BRIEFING_EVERY_MS);
setInterval(checkTryOn, STATE_EVERY_MS);

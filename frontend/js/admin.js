// 폰에서 쓰는 관리 페이지: 옷 업로드 / 할 일 / AI 대화
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CAT = { top: "상의", bottom: "하의", outer: "아우터" };

// ── 옷장 ──
async function loadWardrobe() {
  const list = await (await fetch("/api/wardrobe")).json();
  $("#count").textContent = `(${list.length}벌)`;
  $("#wardrobe").innerHTML = list.map((c) => `
    <div class="card">
      <img src="${c.cutout_url}" alt="">
      <b>${esc(c.name)}</b>
      <span>${CAT[c.category]} · ${esc(c.color)} · 두께 ${c.warmth}${c.waterproof ? " · 방수" : ""}</span>
      <button class="ghost" data-del="${c.id}">삭제</button>
    </div>`).join("") || `<p class="hint">아직 등록한 옷이 없어요. 위에서 첫 옷을 등록해 보세요.</p>`;
}

$("#cloth-form").elements.warmth.addEventListener("input", (e) => ($("#warmth-out").textContent = e.target.value));

$("#cloth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target, msg = $("#form-msg"), btn = form.querySelector("button");
  const fd = new FormData(form);
  fd.set("waterproof", form.elements.waterproof.checked ? "true" : "false");
  btn.disabled = true; msg.textContent = "올리는 중… (배경 제거에 몇 초 걸려요)";
  const res = await fetch("/api/wardrobe", { method: "POST", body: fd });
  btn.disabled = false;
  if (res.ok) { msg.textContent = "등록했어요!"; form.reset(); $("#warmth-out").textContent = "3"; loadWardrobe(); }
  else { msg.textContent = (await res.json()).detail || "등록에 실패했어요"; }
});

$("#wardrobe").addEventListener("click", async (e) => {
  const id = e.target.dataset.del;
  if (id && confirm("이 옷을 삭제할까요?")) { await fetch(`/api/wardrobe/${id}`, { method: "DELETE" }); loadWardrobe(); }
});

// ── 할 일 ──
async function loadTodos() {
  const list = await (await fetch("/api/todos")).json();
  $("#todos").innerHTML = list.map((t) => `
    <li class="${t.done ? "done" : ""}"><span data-toggle="${t.id}">${t.done ? "✓" : "○"} ${esc(t.text)}</span>
    <button class="ghost" data-rm="${t.id}">삭제</button></li>`).join("");
}
$("#todo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = e.target.elements.text.value.trim();
  await fetch("/api/todos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  e.target.reset(); loadTodos();
});
$("#todos").addEventListener("click", async (e) => {
  if (e.target.dataset.toggle) await fetch(`/api/todos/${e.target.dataset.toggle}/toggle`, { method: "POST" });
  if (e.target.dataset.rm) await fetch(`/api/todos/${e.target.dataset.rm}`, { method: "DELETE" });
  loadTodos();
});

// ── AI 비서 ──
const history = [];
function addMsg(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`; div.textContent = content;
  $("#chat-log").appendChild(div);
  return div;
}
$("#chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.elements.message, message = input.value.trim();
  if (!message) return;
  input.value = ""; addMsg("user", message);
  const pending = addMsg("assistant", "…");
  const res = await fetch("/api/assistant/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  const reply = res.ok ? (await res.json()).reply : "응답을 받지 못했어요.";
  pending.textContent = reply;
  history.push({ role: "user", content: message }, { role: "assistant", content: reply });
});

loadWardrobe(); loadTodos();

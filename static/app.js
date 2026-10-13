/* Smart Campus Hub - dependency-free SPA. Talks to the same-origin Flask API. */
const $ = (id) => document.getElementById(id);
let session = JSON.parse(sessionStorage.getItem("session") || "null");

// ---------- tiny helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (t) => new Date(t * 1000).toLocaleString();
const say = (el, text, ok) => { el.textContent = text; el.className = "msg " + (ok ? "ok" : "err"); };
function isAdmin() { return !!(session && session.user.isAdmin); }

// ---------- API ----------
async function api(method, path, body, isForm) {
  const headers = {};
  if (session) headers.Authorization = "Bearer " + session.token;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  const r = await fetch("/api" + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && session) { sessionStorage.clear(); location.reload(); }
  if (!r.ok) throw new Error(data.message || `Error ${r.status}`);
  return data;
}
async function authCall(path, body) {
  const r = await fetch("/api/auth/" + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.message || "Request failed");
  session = data;
  sessionStorage.setItem("session", JSON.stringify(session));
}

// ---------- auth UI ----------
document.querySelectorAll("[data-show]").forEach((a) => a.addEventListener("click", (e) => {
  e.preventDefault();
  ["loginForm", "signupForm"].forEach((id) => $(id).classList.toggle("hidden", id !== a.dataset.show));
  $("authMsg").textContent = "";
}));
$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try { await authCall("login", { email: $("loginEmail").value.trim(), password: $("loginPass").value }); startApp(); }
  catch (err) { say($("authMsg"), err.message); }
});
$("signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try { await authCall("signup", { name: $("suName").value.trim(), email: $("suEmail").value.trim(), password: $("suPass").value }); startApp(); }
  catch (err) { say($("authMsg"), err.message); }
});
$("logout").addEventListener("click", () => { sessionStorage.clear(); location.reload(); });

// ---------- navigation ----------
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("hidden", t.id !== "tab-" + name));
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (name === "notices") loadNotices();
  if (name === "mine") loadMine();
  if (name === "admin") loadAdmin();
}
document.querySelectorAll("#nav button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

function startApp() {
  $("auth").classList.add("hidden"); $("app").classList.remove("hidden");
  $("whoami").textContent = session.user.name || session.user.email;
  if (isAdmin()) $("adminTab").classList.remove("hidden");
  showTab("notices");
}

// ---------- notices ----------
async function loadNotices() {
  const el = $("noticeList"); el.innerHTML = "<p class='muted'>Loading…</p>";
  try {
    const { items } = await api("GET", "/notices");
    el.innerHTML = items.length ? items.map((n) => `
      <article class="card"><h3>${esc(n.title)}</h3>
      <div class="meta"><span class="badge cat">${esc(n.audience)}</span>${esc(n.postedBy)} · ${fmt(n.createdAt)}</div>
      <p>${esc(n.content)}</p>
      ${isAdmin() ? `<button class="btn small ghost" data-del="${esc(n.sk)}">Delete</button>` : ""}</article>`).join("")
      : "<p class='muted'>No notices yet.</p>";
    el.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
      if (!confirm("Delete this notice?")) return;
      await api("DELETE", "/notices/" + encodeURIComponent(b.dataset.del)); loadNotices();
    }));
  } catch (err) { el.innerHTML = `<p class="msg err">${esc(err.message)}</p>`; }
}

// ---------- complaints ----------
const complaintCard = (c, admin) => `
  <article class="card">
    <h3>${esc(c.title)}</h3>
    <div class="meta">
      <span class="badge b-${esc(c.priority)}">${esc(c.priority)}</span>
      <span class="badge s-${esc(c.status)}">${esc(c.status.replace("_", " "))}</span>
      <span class="badge cat">${esc(c.category)}</span><br>
      ${admin ? esc(c.userName) + " · " : ""}${esc(c.location || "—")} · ${fmt(c.createdAt)}
    </div>
    <p>${esc(c.description)}</p>
    ${c.adminNote ? `<div class="note">Admin note: ${esc(c.adminNote)}</div>` : ""}
    ${c.attachmentKey ? `<button class="btn small ghost" data-att="${esc(c.attachmentKey)}">View attachment</button>` : ""}
    ${admin ? ["IN_PROGRESS", "RESOLVED", "REJECTED"].map((s) =>
      `<button class="btn small ghost" data-set="${esc(c.complaintId)}|${s}">${s.replace("_", " ")}</button>`).join("") : ""}
  </article>`;

function wireCardButtons(root, reload) {
  root.querySelectorAll("[data-att]").forEach((b) => b.addEventListener("click", async () => {
    const r = await fetch("/api/attachments/" + b.dataset.att, { headers: { Authorization: "Bearer " + session.token } });
    if (!r.ok) return alert("Could not load attachment");
    window.open(URL.createObjectURL(await r.blob()), "_blank", "noopener");
  }));
  root.querySelectorAll("[data-set]").forEach((b) => b.addEventListener("click", async () => {
    const [id, status] = b.dataset.set.split("|");
    const adminNote = prompt(`Add a note for the student (optional) - status → ${status}`) || "";
    await api("PATCH", "/complaints/" + id, { status, adminNote }); reload();
  }));
}

$("complaintForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("complaintMsg"); say(msg, "Submitting…", true);
  try {
    let attachmentKey;
    const file = $("cFile").files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) throw new Error("File is larger than 5 MB");
      const fd = new FormData();
      fd.append("file", file);
      const { key } = await api("POST", "/uploads", fd, true);
      attachmentKey = key;
    }
    const c = await api("POST", "/complaints", {
      title: $("cTitle").value, description: $("cDesc").value, location: $("cLocation").value, attachmentKey });
    say(msg, `Submitted! Auto-tagged as ${c.category} · ${c.priority} priority.`, true);
    e.target.reset();
  } catch (err) { say(msg, err.message); }
});

async function loadMine() {
  const el = $("myList"); el.innerHTML = "<p class='muted'>Loading…</p>";
  try {
    const { items } = await api("GET", "/complaints");
    el.innerHTML = items.length ? items.map((c) => complaintCard(c, false)).join("") : "<p class='muted'>You have not filed any complaints.</p>";
    wireCardButtons(el, loadMine);
  } catch (err) { el.innerHTML = `<p class="msg err">${esc(err.message)}</p>`; }
}

// ---------- admin ----------
async function loadAdmin() {
  const el = $("adminList"); el.innerHTML = "<p class='muted'>Loading…</p>";
  try {
    const f = $("statusFilter").value;
    const { items } = await api("GET", "/complaints?scope=all" + (f ? "&status=" + f : ""));
    const count = (k, v) => items.filter((i) => i[k] === v).length;
    $("stats").innerHTML = `<span class="badge s-OPEN">Open ${count("status", "OPEN")}</span>
      <span class="badge b-HIGH">High ${count("priority", "HIGH")}</span><span class="badge cat">Total ${items.length}</span>`;
    el.innerHTML = items.length ? items.map((c) => complaintCard(c, true)).join("") : "<p class='muted'>Nothing here 🎉</p>";
    wireCardButtons(el, loadAdmin);
  } catch (err) { el.innerHTML = `<p class="msg err">${esc(err.message)}</p>`; }
}
$("refreshAdmin").addEventListener("click", loadAdmin);
$("statusFilter").addEventListener("change", loadAdmin);
$("postNotice").addEventListener("click", async () => {
  try {
    await api("POST", "/notices", { title: $("nTitle").value, content: $("nContent").value, audience: $("nAudience").value });
    say($("noticeMsg"), "Notice published.", true);
    $("nTitle").value = ""; $("nContent").value = "";
  } catch (err) { say($("noticeMsg"), err.message); }
});

if (session) { try { startApp(); } catch { sessionStorage.clear(); } }

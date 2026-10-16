/* Tủ Lạnh Nấu Gì — logic giao diện (vanilla JS, không build step). */
"use strict";

const TASTES = ["mặn", "ngọt", "cay", "chua", "béo ngậy", "thanh đạm", "chay"];
const SERVINGS = [
  { v: "1", label: "1 người" },
  { v: "2", label: "2 người" },
  { v: "3-4", label: "3–4 người" },
  { v: "5+", label: "5+ người" },
];
const SRC_LABEL = { instagram: "Instagram", facebook: "Facebook", news: "Tin tức" };

const $ = (id) => document.getElementById(id);
const state = {
  foods: [], categories: [],
  fridge: new Set(),
  tastes: new Set(),
  servings: "",
  lastKw: "",
};

/* ---------- chuyển tab ---------- */
document.querySelectorAll("nav.tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "suggest") loadSuggestions();
    if (btn.dataset.tab === "explore") loadTopics();
  });
});

/* ---------- TAB TỦ LẠNH ---------- */
function stripAccents(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

async function loadFoods() {
  const res = await fetch("/api/foods");
  const data = await res.json();
  state.foods = data.foods || [];
  state.categories = data.categories || [];
  const fr = await fetch("/api/fridge").then((r) => r.json());
  state.fridge = new Set(fr.items || []);
  renderFoods("");
  updateFridgeCount();
}

function renderFoods(filter) {
  const box = $("food-list");
  box.innerHTML = "";
  const f = stripAccents(filter.trim());
  for (const cat of state.categories) {
    const items = state.foods.filter(
      (x) => x.category === cat && (!f || stripAccents(x.name).includes(f))
    );
    if (!items.length) continue;
    const g = document.createElement("div");
    g.className = "food-group";
    g.innerHTML = `<h3>${cat}</h3>`;
    const wrap = document.createElement("div");
    wrap.className = "food-items";
    for (const it of items) {
      const c = document.createElement("span");
      c.className = "chip" + (state.fridge.has(it.name) ? " on" : "");
      c.textContent = it.name;
      c.addEventListener("click", () => {
        if (state.fridge.has(it.name)) state.fridge.delete(it.name);
        else state.fridge.add(it.name);
        c.classList.toggle("on");
        updateFridgeCount();
      });
      wrap.appendChild(c);
    }
    g.appendChild(wrap);
    box.appendChild(g);
  }
  if (!box.children.length) box.innerHTML = `<div class="empty">Không tìm thấy nguyên liệu.</div>`;
}

function updateFridgeCount() {
  $("fridge-count").textContent = `Đã chọn ${state.fridge.size} nguyên liệu`;
}

$("food-filter").addEventListener("input", (e) => renderFoods(e.target.value));
$("fridge-save").addEventListener("click", async () => {
  const res = await fetch("/api/fridge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: [...state.fridge] }),
  });
  const data = await res.json();
  $("fridge-count").textContent = data.ok
    ? `Đã lưu ${data.items.length} nguyên liệu ✓`
    : "Lưu thất bại, thử lại nhé.";
});

/* ---------- TAB TÌM MÓN ---------- */
function renderPickers() {
  const tc = $("taste-chips");
  tc.innerHTML = "";
  for (const t of TASTES) {
    const c = document.createElement("span");
    c.className = "chip";
    c.textContent = t;
    c.addEventListener("click", () => {
      if (state.tastes.has(t)) state.tastes.delete(t);
      else state.tastes.add(t);
      c.classList.toggle("on");
    });
    tc.appendChild(c);
  }
  const sc = $("serving-chips");
  sc.innerHTML = "";
  for (const s of SERVINGS) {
    const c = document.createElement("span");
    c.className = "chip single";
    c.textContent = s.label;
    c.addEventListener("click", () => {
      state.servings = state.servings === s.v ? "" : s.v;
      sc.querySelectorAll(".chip").forEach((x) => x.classList.remove("on"));
      if (state.servings) c.classList.add("on");
    });
    sc.appendChild(c);
  }
}

function matchBadges(matched_in) {
  const map = { title: "Khớp tiêu đề", caption: "Khớp phụ đề" };
  return (matched_in || []).map((m) => `<span class="badge match">${map[m] || m}</span>`).join("");
}

function shortTitle(t, n) {
  t = t || "";
  return t.length > n ? t.slice(0, n).trim() + "…" : t;
}

function reelCard(r, cached) {
  const badges = [
    cached ? `<span class="badge cached">Đã lưu</span>` : "",
    `<span class="badge src-${r.source}">${SRC_LABEL[r.source] || r.source}</span>`,
    matchBadges(r.matched_in),
  ].join("");
  const dish = shortTitle(r.title, 42);
  return `
  <div class="card reel-card">
    <a href="${r.url}" target="_blank" rel="noopener" class="img-link">
      <img src="${r.image_url}" alt="${escapeHtml(dish)}" loading="lazy"
           onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22400%22 height=%22300%22><rect width=%22400%22 height=%22300%22 fill=%22%23f3e8d3%22/><text x=%22200%22 y=%22160%22 font-size=%2272%22 text-anchor=%22middle%22>🍲</text></svg>'">
    </a>
    <div class="body">
      <p class="dish" title="${escapeHtml(r.title)}">${escapeHtml(dish)}</p>
      <div class="badges">${badges}</div>
      <p class="summary">${escapeHtml(r.summary)}</p>
    </div>
  </div>`;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function doSearch(rescan) {
  const kw = $("kw").value.trim();
  if (!kw) { $("search-status").textContent = "Nhập từ khóa món ăn trước nhé."; return; }
  state.lastKw = kw;
  $("btn-search").disabled = true;
  $("search-status").textContent = "Đang quét…";
  $("search-results").innerHTML = `<div class="spinner">Đang tìm reels công khai…</div>`;
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        keyword: kw,
        tastes: [...state.tastes],
        servings: state.servings,
        rescan: !!rescan,
      }),
    });
    const data = await res.json();
    $("search-note").innerHTML = data.note ? `<div class="note">${escapeHtml(data.note)}</div>` : "";
    $("search-results").innerHTML = (data.results || []).map((r) => reelCard(r, data.cached)).join("")
      || `<div class="empty">Chưa có kết quả. Thử từ khóa khác nhé.</div>`;
    $("search-status").textContent = data.cached
      ? `Hiển thị ${data.results.length} kết quả đã lưu.`
      : `Tìm thấy ${data.results.length} kết quả.`;
    $("btn-rescan").style.display = "inline-block";
  } catch (e) {
    $("search-results").innerHTML = `<div class="empty">Lỗi kết nối tới server. Thử lại nhé.</div>`;
  }
  $("btn-search").disabled = false;
}
$("btn-search").addEventListener("click", () => doSearch(false));
$("btn-rescan").addEventListener("click", () => doSearch(true));
$("kw").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(false); });

/* ---------- TAB GỢI Ý TỪ TỦ ---------- */
function suggestCard(r, near) {
  const miss = near
    ? `<p><span class="missing">Thiếu: ${r.missing.map(escapeHtml).join(", ")}</span></p>` : "";
  const steps = (r.steps || []).map((s, i) => `<li>${escapeHtml(s)}</li>`).join("");
  return `
  <div class="card suggest-card">
    <p class="dish" style="font-weight:700;font-size:16px;margin:0">${escapeHtml(r.name)}</p>
    <p class="muted" style="margin:4px 0">${escapeHtml(r.description || "")}</p>
    <div class="badges">
      ${(r.tastes || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join("")}
      ${r.servings ? `<span class="badge">${escapeHtml(r.servings)} người</span>` : ""}
      <span class="badge have">Có ${r.have.length}/${r.ingredients.length} nguyên liệu</span>
    </div>
    ${miss}
    ${steps ? `<ul>${steps}</ul>` : ""}
  </div>`;
}

async function loadSuggestions() {
  $("suggest-ready").innerHTML = `<div class="spinner">Đang gợi ý…</div>`;
  $("suggest-near").innerHTML = "";
  const data = await fetch("/api/suggestions").then((r) => r.json());
  $("suggest-info").textContent =
    `Dựa trên ${data.fridge_count} nguyên liệu trong tủ lạnh của bạn.`;
  $("suggest-ready").innerHTML = (data.ready || []).map((r) => suggestCard(r, false)).join("")
    || `<div class="empty">Chưa có món nào đủ nguyên liệu — thêm đồ vào tủ lạnh nhé.</div>`;
  $("suggest-near").innerHTML = (data.near || []).map((r) => suggestCard(r, true)).join("")
    || `<div class="empty">Không có món gần đủ.</div>`;
}
$("btn-suggest").addEventListener("click", loadSuggestions);

/* ---------- TAB KHÁM PHÁ ---------- */
async function loadTopics() {
  const data = await fetch("/api/explore/topics").then((r) => r.json());
  const box = $("topic-list");
  const topics = data.topics || [];
  if (!topics.length) { box.innerHTML = `<p class="muted">Chưa có chủ đề nào.</p>`; return; }
  box.innerHTML = "";
  for (const t of topics) {
    const row = document.createElement("div");
    row.className = "topic-row";
    row.innerHTML = `<span class="t">${escapeHtml(t.topic)}</span>`;
    const acts = document.createElement("span");
    acts.className = "row";
    const bq = document.createElement("button");
    bq.className = "ghost"; bq.textContent = "Quét";
    bq.addEventListener("click", () => { $("topic-kw").value = t.topic; doExplore(false); });
    const bd = document.createElement("button");
    bd.className = "ghost danger"; bd.textContent = "Xóa";
    bd.addEventListener("click", async () => {
      await fetch("/api/explore/topics/" + t.id, { method: "DELETE" });
      loadTopics();
    });
    acts.appendChild(bq); acts.appendChild(bd);
    row.appendChild(acts);
    box.appendChild(row);
  }
}

$("btn-topic-save").addEventListener("click", async () => {
  const topic = $("topic-kw").value.trim();
  if (!topic) return;
  await fetch("/api/explore/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  loadTopics();
});

async function doExplore(rescan) {
  const topic = $("topic-kw").value.trim();
  if (!topic) return;
  const source = $("topic-source").value;
  $("btn-explore").disabled = true;
  $("explore-results").innerHTML = `<div class="spinner">Đang quét…</div>`;
  try {
    const res = await fetch("/api/explore/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, source, rescan: !!rescan }),
    });
    const data = await res.json();
    $("explore-note").innerHTML = data.note ? `<div class="note">${escapeHtml(data.note)}</div>` : "";
    $("explore-results").innerHTML = (data.results || []).map((r) => reelCard(r, data.cached)).join("")
      || `<div class="empty">Chưa quét được gì. Thử chủ đề khác nhé.</div>`;
    $("btn-explore-rescan").style.display = "inline-block";
    $("btn-explore-rescan").onclick = () => doExplore(true);
  } catch (e) {
    $("explore-results").innerHTML = `<div class="empty">Lỗi kết nối tới server.</div>`;
  }
  $("btn-explore").disabled = false;
}
$("btn-explore").addEventListener("click", () => doExplore(false));

/* ---------- khởi động ---------- */
renderPickers();
loadFoods();

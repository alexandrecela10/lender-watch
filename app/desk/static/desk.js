// Analyst Desk: the workbook and the assistant beside it. All facts come from the server; this file only shows them.
"use strict";

const COLS = 10, ROWS = 26;
const WIDTHS = [130, 175, 140, 165, 190, 175, 110, 95, 90, 90];
const SPILL_HEADERS = ["Flag", "Lenders call it", "Value (% of amount owed)", "Change (points)", "Source"];
const $ = (id) => document.getElementById(id);
const letter = (c) => String.fromCharCode(65 + c);
const addr = (r, c) => letter(c) + (r + 1);

const state = {
  sheets: {}, active: "", sel: { r: 0, c: 0 }, formulas: {}, spills: {},
  results: {}, chat: [], failed: 0, claude: false, original: null, offerShown: false,
};

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).error || "Something went wrong.");
  return res.json();
}

// --- Sheet model ------------------------------------------------------------------------------

function grid() { return state.sheets[state.active]; }
function cell(r, c, sheet = state.active) { const row = state.sheets[sheet][r]; return row ? row[c] ?? null : null; }
function setCell(r, c, v, sheet = state.active) {
  const rows = state.sheets[sheet];
  while (rows.length <= r) rows.push([]);
  rows[r][c] = v;
}
function plainSheets() {
  const out = {};
  for (const [name, rows] of Object.entries(state.sheets)) {
    out[name] = rows.map((row) => row.map((v) => (v && typeof v === "object" ? v.text : v ?? null)));
  }
  return out;
}
function text(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return v.text;
  if (typeof v === "number") return v >= 1000 ? v.toLocaleString("en-US") : String(v);
  return String(v);
}
function parseRange(s) {
  const m = s.trim().match(/^([A-Z])(\d+)(?::([A-Z])(\d+))?$/i);
  if (!m) return null;
  const c = m[1].toUpperCase().charCodeAt(0) - 65, r = +m[2] - 1;
  const c2 = m[3] ? m[3].toUpperCase().charCodeAt(0) - 65 : c, r2 = m[4] ? +m[4] - 1 : r;
  const out = [];
  for (let i = r; i <= r2; i++) for (let j = c; j <= c2; j++) out.push({ r: i, c: j });
  return out;
}
function parseColumnRef(s) {
  const m = s.trim().match(/^(?:'([^']+)'|([A-Za-z0-9_]+))!([A-Z]):([A-Z])$/i);
  if (!m) return null;
  return { sheet: m[1] || m[2], col: m[3].toUpperCase().charCodeAt(0) - 65, col2: m[4].toUpperCase().charCodeAt(0) - 65 };
}
function splitArgs(s) {
  const out = []; let cur = "", quoted = false;
  for (const ch of s) {
    if (ch === "'") quoted = !quoted;
    if (ch === "," && !quoted) { out.push(cur); cur = ""; } else cur += ch;
  }
  out.push(cur);
  return out;
}

// --- Formulas --------------------------------------------------------------------------------

function clearSpill(key) {
  const spill = state.spills[key];
  if (!spill) return;
  for (const p of spill.cells) setCell(p.r, p.c, null, spill.sheet);
  delete state.spills[key];
}

async function commit(r, c, raw) {
  const key = state.active + "!" + addr(r, c);
  clearSpill(key);
  delete state.formulas[key];
  if (raw === "") { setCell(r, c, null); render(); return; }
  if (!raw.startsWith("=")) {
    const n = Number(raw);
    setCell(r, c, raw.trim() !== "" && !Number.isNaN(n) ? n : raw);
    render();
    return;
  }
  state.formulas[key] = raw;
  const m = raw.match(/^=\s*([A-Za-z]+)\((.*)\)\s*$/);
  const fn = m ? m[1].toUpperCase() : "";
  if (fn === "RECONCILE") await formulaReconcile(key, r, c, m[2]);
  else if (fn === "XLOOKUP") formulaLookup(key, r, c, m[2], false);
  else if (fn === "VLOOKUP") formulaLookup(key, r, c, m[2], true);
  else { setCell(r, c, "#NAME?"); render(); }
}

function formulaLookup(key, r, c, args, isV) {
  const parts = splitArgs(args);
  const range = parseRange(parts[0] || "");
  const from = parseColumnRef(parts[1] || "");
  if (!range || !from || !state.sheets[from.sheet]) { setCell(r, c, "#REF!"); render(); return; }
  const answerCol = isV ? from.col + Number(parts[2]) - 1 : parseColumnRef(parts[2] || "")?.col;
  const lookupRows = state.sheets[from.sheet];
  const cells = [];
  let failed = 0;
  range.forEach((p, i) => {
    const wanted = String(cell(p.r, p.c) ?? "").trim().toLowerCase();
    const hit = lookupRows.find((row) => String(row[from.col] ?? "").trim().toLowerCase() === wanted);
    const value = hit ? hit[answerCol] ?? null : "#N/A";
    if (!hit) failed++;
    setCell(r + i, c, value);
    if (i > 0) cells.push({ r: r + i, c });
  });
  state.spills[key] = { sheet: state.active, cells };
  state.failed = failed;
  render();
  if (failed) noticeFailedLookup(failed, range.length);
}

async function formulaReconcile(key, r, c, args) {
  const range = parseRange(args.split(",")[0]);
  if (!range) { setCell(r, c, "#REF!"); render(); return; }
  const names = range.map((p) => cell(p.r, p.c)).filter(Boolean);
  setCell(r, c, "Linking…"); render();
  const out = await api("/api/reconcile", { sheets: plainSheets(), sheet: state.active, names });
  placeResults(out, r, c, key, range[0].r);
  summarise(out);
  queueConfirmations();
}

function resultCells(row) {
  const needs = row.to_confirm.length > 0;
  const noLoans = row.loans.length === 0;
  const flag = noLoans ? row.result : (needs ? row.flag + " · confirm" : row.flag);
  const cls = noLoans ? (needs ? "confirm" : "fine") : needs && !row.flag.startsWith("Flag") ? "confirm"
    : row.flag === "Flagged" ? "flagged" : row.flag === "Worth a look" ? "look" : "fine";
  return [
    { text: flag, cls, name: row.name },
    { text: row.listed_as || "", cls: "spill", name: row.name },
    { text: row.value_pct === null ? "" : row.value_pct.toFixed(1) + "%", cls: "spill num", name: row.name },
    { text: row.change === null ? "" : (row.change > 0 ? "+" : "") + row.change.toFixed(1), cls: "spill num", name: row.name },
    { text: row.filing_url ? "Open filing" : "", cls: "spill link", name: row.name, url: row.filing_url },
  ];
}

function placeResults(out, r, c, key, firstListRow) {
  // A formula in the header row writes headers first. Otherwise rows start at the formula's own row.
  const atHeader = r === 0;
  const start = atHeader ? 1 : r;
  const cells = [];
  if (atHeader) SPILL_HEADERS.forEach((h, j) => { setCell(0, c + j, { text: h, cls: "head" }); if (j) cells.push({ r: 0, c: c + j }); });
  out.rows.forEach((row, i) => {
    state.results[row.name] = row;
    resultCells(row).forEach((v, j) => { setCell(start + i, c + j, v); cells.push({ r: start + i, c: c + j }); });
  });
  state.spills[key] = { sheet: state.active, cells, start, col: c, names: out.rows.map((x) => x.name), listRow: firstListRow };
  $("export-btn").disabled = false;
  render();
}

function refreshSpill(name) {
  for (const spill of Object.values(state.spills)) {
    if (!spill.names) continue;
    const i = spill.names.indexOf(name);
    if (i >= 0) resultCells(state.results[name]).forEach((v, j) => setCell(spill.start + i, spill.col + j, v, spill.sheet));
  }
  render();
}

function fillFromAssistant(out) {
  // The assistant ran the tool: add results beside the list, starting in the first free column.
  const rows = grid();
  const width = Math.max(...rows.map((row) => row.reduce((last, v, i) => (v === null || v === undefined ? last : i + 1), 0)));
  const c = Math.min(width, COLS - 5);
  placeResults(out, 0, c, state.active + "!" + addr(0, c), 1);
}

// --- Rendering --------------------------------------------------------------------------------

function render() {
  const rows = grid();
  let html = "<colgroup><col style='width:40px'>" + WIDTHS.map((w) => `<col style='width:${w}px'>`).join("") + "</colgroup>";
  html += "<thead><tr><th class='row-head corner'></th>" + WIDTHS.map((_, c) => `<th>${letter(c)}</th>`).join("") + "</tr></thead><tbody>";
  for (let r = 0; r < Math.max(ROWS, rows.length); r++) {
    html += `<tr><th class="row-head">${r + 1}</th>`;
    for (let c = 0; c < COLS; c++) {
      const v = rows[r] ? rows[r][c] ?? null : null;
      const shown = text(v);
      const classes = [];
      if (v && typeof v === "object") classes.push(v.cls);
      else if (r === 0 && v !== null) classes.push("head");
      if (typeof v === "number") classes.push("num");
      if (typeof v === "string" && /^#(N\/A|REF!|NAME\?)$/.test(v)) classes.push("err");
      if (state.sel.r === r && state.sel.c === c) classes.push("selected");
      html += `<td data-r="${r}" data-c="${c}" class="${classes.join(" ")}" title="${escapeHtml(shown)}">${escapeHtml(shown)}</td>`;
    }
    html += "</tr>";
  }
  $("grid").innerHTML = html + "</tbody>";
  $("tabs").innerHTML = Object.keys(state.sheets).map((n) =>
    `<button data-tab="${escapeHtml(n)}" class="${n === state.active ? "on" : ""}">${escapeHtml(n)}</button>`).join("");
  syncFormulaBar();
}

function syncFormulaBar() {
  const { r, c } = state.sel;
  $("cell-name").textContent = addr(r, c);
  const key = state.active + "!" + addr(r, c);
  if (document.activeElement !== $("formula")) $("formula").value = state.formulas[key] || text(cell(r, c));
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
}

function bubble(html, who = "bot") {
  const el = document.createElement("div");
  el.className = "msg " + who;
  el.innerHTML = html;
  $("chat").appendChild(el);
  $("chat").scrollTop = $("chat").scrollHeight;
  return el;
}

function inline(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// Claude's replies use short paragraphs and dash lists. Everything else stays plain text.
function richText(source) {
  let html = "", open = false;
  for (const line of source.split(/\n+/)) {
    const item = line.match(/^\s*[-*]\s+(.*)/);
    if (item && !open) { html += "<ul>"; open = true; }
    if (!item && open) { html += "</ul>"; open = false; }
    html += item ? `<li>${inline(item[1])}</li>` : `<p>${inline(line)}</p>`;
  }
  return html + (open ? "</ul>" : "");
}

function list(items, tag = "ul") {
  return items && items.length ? `<${tag}>${items.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</${tag}>` : "";
}

// --- The three ways in ------------------------------------------------------------------------

function summarise(out) {
  const c = out.counts;
  bubble(`<p>${c.flagged} of ${c.names} companies are flagged. ${c.to_confirm ? `${c.to_confirm} ${c.to_confirm === 1 ? "match needs" : "matches need"} your answer.` : "Nothing needs your answer."}</p><p class="note">Click any result to see the filing behind it.</p>`);
}

function offerCard(lead, facts) {
  const el = bubble(`<div class="card"><p class="lead">${escapeHtml(lead)}</p>${list(facts)}<div class="row"><button class="primary" data-act="link">Link them</button><button data-act="dismiss">Not now</button></div></div>`);
  el.querySelector("[data-act=link]").onclick = () => { el.querySelector(".row").remove(); runOnList(); };
  el.querySelector("[data-act=dismiss]").onclick = () => el.remove();
}

async function noticeFailedLookup(failed) {
  if (state.offerShown) return;
  const out = await api("/api/inspect", { sheets: plainSheets(), failed_lookups: failed });
  if (out.should_offer) { state.offerShown = true; offerCard(out.message, out.facts); }
}

async function runOnList() {
  const sheet = Object.keys(state.sheets).find((n) => cell(0, 0, n) === "Company") || state.active;
  if (state.active !== sheet) { state.active = sheet; render(); }
  // Clear any failed lookups first, so results land where the analyst was looking.
  for (const [key, formula] of Object.entries(state.formulas)) {
    if (/LOOKUP/i.test(formula) && key.startsWith(sheet + "!")) {
      const parsed = parseRange(key.split("!")[1])[0];
      clearSpill(key); delete state.formulas[key]; setCell(parsed.r, parsed.c, null, sheet);
    }
  }
  const names = grid().slice(1).map((row) => row[0]).filter(Boolean);
  const out = await api("/api/reconcile", { sheets: plainSheets(), sheet, names });
  fillFromAssistant(out);
  summarise(out);
  queueConfirmations();
}

async function ask(message) {
  bubble(escapeHtml(message), "me");
  state.chat.push({ role: "user", text: message });
  const wait = bubble(`<span class="thinking">Working…</span>`);
  try {
    const reply = await api("/api/ask", {
      message, sheets: plainSheets(), sheet: state.active, failed_lookups: state.failed,
      use_claude: state.claude, history: state.chat.slice(0, -1),
    });
    wait.remove();
    showReply(reply);
    state.chat.push({ role: "assistant", text: reply.text });
  } catch (e) {
    wait.remove();
    bubble(`<p>${escapeHtml(e.message)}</p>`);
  }
}

function showReply(reply) {
  const paragraphs = richText(reply.text);
  const used = reply.tools_used && reply.tools_used.length ? `<div class="tools-used">used ${reply.tools_used.join(", ")}</div>` : "";
  const note = reply.note ? `<p class="note">${escapeHtml(reply.note)}</p>` : "";
  const el = bubble(used + paragraphs + list(reply.facts, "ol") + note + (reply.offer === "run" ? `<div class="row"><button class="primary" data-act="run">Run it on this list</button></div>` : ""));
  const runButton = el.querySelector("[data-act=run]");
  if (runButton) runButton.onclick = () => { runButton.parentElement.remove(); runOnList(); };
  if (reply.reconciled) { fillFromAssistant(reply.reconciled); queueConfirmations(); }
}

// --- Source and confirmations ---------------------------------------------------------------

function showSource(name) {
  const row = state.results[name];
  if (!row) return;
  const linked = row.linked_because[0];
  const loans = [...row.loans].sort((a, b) => a.value_pct - b.value_pct).slice(0, 3).map((l) => `
    <div class="loan">
      <div class="top-line"><span>${escapeHtml(l.lender)}</span><span class="pct">${l.value_pct.toFixed(1)}%${l.change === null ? "" : ` (${l.change > 0 ? "+" : ""}${l.change.toFixed(1)})`}</span></div>
      <div class="row-text">${escapeHtml(l.filing_row.slice(0, 150))}</div>
      <a href="${escapeHtml(l.filing_url)}" target="_blank" rel="noopener">Open the SEC filing</a>
    </div>`).join("");
  $("source").hidden = false;
  $("source").innerHTML = `<button class="close" aria-label="Close">×</button>
    <h3>${escapeHtml(name)}</h3>
    <p class="line">${linked ? `Lenders call it ${escapeHtml(linked.listed_as)}. ${escapeHtml(linked.how)}.` : escapeHtml(row.result)}</p>
    <p class="shows">${escapeHtml(row.what_it_shows)}</p>
    ${row.loans.length ? `<p class="line">Lowest of ${row.loans.length} loans:</p>` : ""}${loans}`;
  $("source").querySelector(".close").onclick = () => { $("source").hidden = true; };
}

function queueConfirmations() {
  document.querySelectorAll(".confirm-card").forEach((n) => n.closest(".msg").remove());
  for (const row of Object.values(state.results)) {
    for (const item of row.to_confirm) {
      const el = bubble(`<div class="confirm-card">
        <p class="q">Is "${escapeHtml(item.listed_as)}" your ${escapeHtml(row.name)}?</p>
        <p class="quote">${escapeHtml(item.filing_row.slice(0, 120))}</p>
        <div class="row"><button data-same="1">Same company</button><button data-same="0">Different</button></div>
      </div>`);
      el.querySelectorAll("button").forEach((b) => {
        b.onclick = async () => {
          const updated = await api("/api/answer", { name: row.name, mention_key: item.mention_key, same: b.dataset.same === "1" });
          state.results[row.name] = updated;
          el.remove();
          refreshSpill(row.name);
          bubble(`<p class="note">Saved. ${escapeHtml(item.listed_as)} ${b.dataset.same === "1" ? "now counts as" : "no longer counts toward"} ${escapeHtml(row.name)}, and you won't be asked again.</p>`);
        };
      });
    }
  }
}

// --- Events ----------------------------------------------------------------------------------

$("grid").addEventListener("click", (e) => {
  const td = e.target.closest("td");
  if (!td) return;
  state.sel = { r: +td.dataset.r, c: +td.dataset.c };
  const v = cell(state.sel.r, state.sel.c);
  render();
  if (v && typeof v === "object" && v.name) {
    showSource(v.name);
    if (v.url && e.target.classList.contains("link")) window.open(v.url, "_blank", "noopener");
  }
});
$("tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { state.active = b.dataset.tab; state.sel = { r: 0, c: 0 }; render(); }
});
$("formula").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    const { r, c } = state.sel;
    const raw = $("formula").value;
    $("formula").blur();
    commit(r, c, raw);
  }
  if (e.key === "Escape") { $("formula").blur(); syncFormulaBar(); }
});
document.addEventListener("keydown", (e) => {
  if (document.activeElement && ["INPUT", "BUTTON"].includes(document.activeElement.tagName)) return;
  if (e.key.length === 1 && !e.metaKey && !e.ctrlKey) { $("formula").value = ""; $("formula").focus(); }
  const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
  if (moves[e.key]) {
    e.preventDefault();
    state.sel = { r: Math.max(0, state.sel.r + moves[e.key][0]), c: Math.max(0, Math.min(COLS - 1, state.sel.c + moves[e.key][1])) };
    render();
  }
});
$("ask").addEventListener("submit", (e) => {
  e.preventDefault();
  const message = $("ask-input").value.trim();
  if (message) { $("ask-input").value = ""; ask(message); }
});
$("use-claude").addEventListener("change", (e) => {
  state.claude = e.target.checked;
  $("mode-note").textContent = state.claude
    ? "Claude answers. This workbook's company names go to Anthropic."
    : "Local answers. No company name leaves this computer.";
});
$("reset-btn").addEventListener("click", start);
$("open-btn").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const res = await fetch("/api/open", { method: "POST", headers: { "X-Filename": encodeURIComponent(file.name) }, body: await file.arrayBuffer() });
  const out = await res.json();
  if (!res.ok) { bubble(`<p>${escapeHtml(out.error)}</p>`); return; }
  load(out.sheets, out.name);
  if (out.inspection.should_offer) { state.offerShown = true; offerCard(out.inspection.message, out.inspection.facts); }
  e.target.value = "";
});
$("export-btn").addEventListener("click", async () => {
  const res = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sheets: plainSheets(), sheet: state.active }) });
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: "reconciled.xlsx" });
  a.click();
  URL.revokeObjectURL(url);
});

function load(sheets, name) {
  Object.assign(state, { sheets, active: Object.keys(sheets)[0], sel: { r: 0, c: 0 }, formulas: {}, spills: {}, results: {}, chat: [], failed: 0, offerShown: false });
  $("book-name").textContent = name;
  $("chat").innerHTML = "";
  $("source").hidden = true;
  $("export-btn").disabled = true;
  render();
}

async function start() {
  const [status, book] = await Promise.all([api("/api/status"), api("/api/workbook")]);
  $("mode-label").hidden = !status.claude_available;
  $("data-note").textContent = status.data === "public sample" ? "Public SEC sample" : "SEC filings";
  load(book.sheets, book.name);
}

start();

// The Lender Watch panel inside Excel. It reads the workbook, asks the local server, and writes results beside the list.
"use strict";

const pane = { claude: false, written: null, offerShown: false, history: [], timer: null };
const el = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);

function say(html, cls = "") {
  const box = document.createElement("div");
  box.className = cls;
  box.innerHTML = html;
  el("chat").appendChild(box);
  box.scrollIntoView({ block: "nearest" });
  return box;
}

async function post(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}

const bullets = (items, tag = "ul") => (items && items.length ? `<${tag}>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</${tag}>` : "");

function offer(result) {
  pane.offerShown = true;
  const box = say(`<p class="lead">${esc(result.message)}</p>${bullets(result.facts)}<div class="row"><button class="primary" data-act="run">Link them</button><button data-act="no">Not now</button></div>`, "card");
  box.querySelector("[data-act=run]").onclick = () => { box.querySelector(".row").remove(); run(); };
  box.querySelector("[data-act=no]").onclick = () => box.remove();
}

async function inspect(announceIfFine) {
  const book = await Excel.run((context) => ErmExcel.readWorkbook(context));
  const result = await post("/api/inspect", { sheets: book.sheets, failed_lookups: book.failedLookups });
  if (result.should_offer) offer(result);
  else if (announceIfFine) say(`<p>${esc(result.message)}</p>`);
}

function watchForFailedLookups() {
  Excel.run(async (context) => {
    context.workbook.worksheets.onCalculated.add(() => {
      clearTimeout(pane.timer);
      pane.timer = setTimeout(async () => {
        if (pane.offerShown) return;
        const book = await Excel.run((c) => ErmExcel.readWorkbook(c));
        if (book.failedLookups > 0) await inspect(false);
      }, 800);
    });
    await context.sync();
  }).catch(() => { el("status").textContent = "Can't watch for failed lookups in this version of Excel."; });
}

async function activeSheetName() {
  return Excel.run(async (context) => {
    const sheet = context.workbook.worksheets.getActiveWorksheet();
    sheet.load("name");
    await context.sync();
    return sheet.name;
  });
}

async function place(out, book, list) {
  pane.written = await Excel.run((context) => ErmExcel.writeResults(context, list, out.rows, book.sheets));
  showConfirmations(out.rows);
}

async function run() {
  const book = await Excel.run((context) => ErmExcel.readWorkbook(context));
  const list = ErmExcel.chooseList(book.sheets, await activeSheetName());
  if (!list) { say("<p>I can't find a column of company names. Name its header Company.</p>"); return; }
  const names = [...new Set(list.names.filter(Boolean))];
  const wait = say('<p class="note">Linking…</p>');
  const out = await post("/api/reconcile", { sheets: book.sheets, sheet: list.sheet, names });
  wait.remove();
  await place(out, book, list);
  const c = out.counts;
  say(`<p>${c.flagged} of ${c.names} companies are flagged. ${c.to_confirm ? `${c.to_confirm} ${c.to_confirm === 1 ? "match needs" : "matches need"} your answer.` : "Nothing needs your answer."}</p><p class="note">Results are beside your list, and each loan is on a new tab with its filing.</p>`);
}

function showConfirmations(rows) {
  for (const row of rows) {
    for (const item of row.to_confirm) {
      const box = say(`<p class="lead">Is "${esc(item.listed_as)}" your ${esc(row.name)}?</p><p class="quote">${esc(item.filing_row.slice(0, 120))}</p><div class="row"><button data-same="1">Same company</button><button data-same="0">Different</button></div>`, "card confirm");
      box.querySelectorAll("button").forEach((button) => {
        button.onclick = async () => {
          const updated = await post("/api/answer", { name: row.name, mention_key: item.mention_key, same: button.dataset.same === "1" });
          await Excel.run((context) => ErmExcel.updateResult(context, pane.written, updated));
          box.innerHTML = `<p class="note">Saved. You won't be asked about ${esc(item.listed_as)} again.</p>`;
          box.className = "";
        };
      });
    }
  }
}

async function ask(message) {
  say(esc(message), "me");
  const wait = say('<p class="note">Working…</p>');
  try {
    const book = await Excel.run((context) => ErmExcel.readWorkbook(context));
    const sheet = await activeSheetName();
    const reply = await post("/api/ask", { message, sheets: book.sheets, sheet, failed_lookups: book.failedLookups, use_claude: pane.claude, history: pane.history });
    wait.remove();
    const body = reply.text.split(/\n+/).map((line) => `<p>${esc(line.replace(/\*\*/g, "").replace(/^\s*[-*]\s+/, ""))}</p>`).join("");
    const box = say(body + bullets(reply.facts, "ol") + (reply.note ? `<p class="note">${esc(reply.note)}</p>` : "") + (reply.offer === "run" ? '<div class="row"><button class="primary">Run it on this list</button></div>' : ""));
    const button = box.querySelector("button");
    if (button) button.onclick = () => { button.parentElement.remove(); run(); };
    pane.history.push({ role: "user", text: message }, { role: "assistant", text: reply.text });
    if (reply.reconciled) {
      const list = ErmExcel.chooseList(book.sheets, sheet);
      if (list) await place(reply.reconciled, book, list);
    }
  } catch (error) {
    wait.remove();
    say(`<p>${esc(error.message)}</p>`);
  }
}

Office.onReady(async (info) => {
  if (info.host !== Office.HostType.Excel) { el("status").textContent = "Open this inside Excel."; return; }
  const status = await (await fetch("/api/status")).json();
  el("mode-label").hidden = !status.claude_available;
  el("status").textContent = "Local answers. No company name leaves this computer.";
  el("check").onclick = () => inspect(true).catch((e) => say(`<p>${esc(e.message)}</p>`));
  el("use-claude").onchange = (e) => {
    pane.claude = e.target.checked;
    el("status").textContent = pane.claude ? "Claude answers. This workbook's company names go to Anthropic." : "Local answers. No company name leaves this computer.";
  };
  el("ask").onsubmit = (e) => {
    e.preventDefault();
    const message = el("ask-input").value.trim();
    if (message) { el("ask-input").value = ""; ask(message); }
  };
  watchForFailedLookups();
  inspect(false).catch(() => {});
});

// Runs the add-in's workbook code against a stand-in for Excel's objects. Called by tests/test_excel_addin.py.
const assert = require("node:assert");
const core = require("../app/desk/excel/core.js");

const row = (name, extra = {}) => ({
  name, result: "Found", flag: "Flagged", listed_as: `${name} Inc.`, value_pct: 78, change: -11.3,
  filing_url: "https://www.sec.gov/f", to_confirm: [],
  loans: [{ lender: "L", type: "First", due: "2030", amount_owed: 5, value_pct: 78, last_quarter_pct: 89, change: -11, filing_row: "row", filing_url: "https://www.sec.gov/f" }],
  ...extra,
});

function fakeWorkbook(tabs) {
  const writes = [];
  const made = [];
  const sheet = (name) => ({
    name,
    getUsedRangeOrNullObject: () => {
      const rows = tabs[name];
      return { isNullObject: !rows, values: rows, formulas: rows, load() {} };
    },
    getRangeByIndexes: (r, c, h, w) => {
      const range = {
        format: { font: {}, fill: { clear() { range.cleared = true; } } },
        set values(v) { writes.push({ sheet: name, r, c, h, w, values: v }); },
        set hyperlink(v) { writes.push({ sheet: name, r, c, hyperlink: v }); },
      };
      return range;
    },
  });
  return {
    writes, made,
    sync: async () => {},
    workbook: { worksheets: {
      items: Object.keys(tabs).map(sheet),
      load() {},
      getItem: sheet,
      getItemOrNullObject: (n) => ({ isNullObject: !tabs[n], load() {} }),
      add: (n) => { made.push(n); return sheet(n); },
    } },
  };
}

(async () => {
  // Formula output keeps one row per input cell, blanks included.
  const spilled = core.spillRows(["KnowBe4", "", "Other"], [row("KnowBe4")]);
  assert.strictEqual(spilled.length, 3);
  assert.deepStrictEqual(spilled[0], ["Flagged", "KnowBe4 Inc.", 78, -11.3, "https://www.sec.gov/f"]);
  assert.deepStrictEqual(spilled[1], ["", "", "", "", ""]);

  // An unclear match is visible, and a company with no loans shows no numbers.
  assert.strictEqual(core.resultRow(row("A", { to_confirm: [{}] }))[0], "Flagged, confirm match");
  assert.deepStrictEqual(core.resultRow(row("B", { loans: [], result: "No public lender found", listed_as: null, filing_url: null })), ["No public lender found", "", "", "", ""]);

  // Only #N/A from a lookup counts as a failed lookup.
  assert.strictEqual(core.countFailedLookups([["#N/A"], ["#N/A"]], [["=XLOOKUP(A2,B:B,C:C)"], ["#N/A"]]), 2);
  assert.strictEqual(core.countFailedLookups([["#N/A"]], [["=A1/0"]]), 0);

  assert.strictEqual(core.findNameColumn([["Owner", "Company"]]), 1);
  assert.strictEqual(core.findNameColumn([["Lender", "Amount"]]), -1);

  // Reading a workbook passes values and the failed-lookup count.
  const book = fakeWorkbook({ Portfolio: [["Company", "Owner"], ["KnowBe4", "V"], ["Other", "W"]] });
  const read = await core.readWorkbook(book);
  assert.strictEqual(read.sheets.Portfolio.length, 3);

  // Results land in the first free column, never over the analyst's cells, and loans go on a new tab.
  const list = core.chooseList(read.sheets, "Portfolio");
  assert.deepStrictEqual(list, { sheet: "Portfolio", column: 0, names: ["KnowBe4", "Other"] });
  const written = await core.writeResults(book, list, [row("KnowBe4")], read.sheets);
  assert.strictEqual(written.startColumn, 2);
  assert.ok(book.writes.every((w) => w.sheet !== "Portfolio" || w.c >= 2));
  assert.deepStrictEqual(book.made, ["Lender loans"]);
  const loanWrite = book.writes.find((w) => w.sheet === "Lender loans");
  assert.strictEqual(loanWrite.values[1][9], "https://www.sec.gov/f");
  assert.ok(book.writes.some((w) => w.hyperlink && w.hyperlink.address.startsWith("https://www.sec.gov/")));

  // A person's answer updates that company's row only.
  book.writes.length = 0;
  await core.updateResult(book, written, row("KnowBe4", { flag: "Not flagged" }));
  assert.strictEqual(book.writes[0].r, 1);
  assert.strictEqual(book.writes[0].c, 2);

  // Sign-in: PKCE with S256, the state is checked, and the token stays in memory only.
  await (async () => {
    const stored = [];
    globalThis.localStorage = { setItem: (k) => stored.push(k), getItem: () => null };
    globalThis.OfficeRuntime = { storage: { setItem: async (k) => stored.push(k) } };
    globalThis.location = { origin: "https://lw.example", href: "https://lw.example/excel/taskpane.html" };
    const jwt = (claims) => `h.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.s`;
    let opened = null;
    let sent = null;
    let reply = { state: null };
    globalThis.Office = {
      AsyncResultStatus: { Succeeded: "ok" },
      EventType: { DialogMessageReceived: "msg", DialogEventReceived: "evt" },
      context: { ui: { displayDialogAsync: (url, _opts, done) => {
        opened = new URL(url);
        const authorize = new URL(opened.searchParams.get("go"));
        const handlers = {};
        done({ status: "ok", value: { close() {}, addEventHandler: (k, f) => { handlers[k] = f; } } });
        const msg = reply.state === null ? { code: "c1", state: authorize.searchParams.get("state") } : reply;
        handlers.msg({ message: JSON.stringify(msg) });
      } } },
    };
    globalThis.fetch = async (path, init) => {
      sent = { path, body: new URLSearchParams(init.body) };
      const exp = Math.floor(Date.now() / 1000) + 3600;
      return { ok: true, json: async () => ({ access_token: jwt({ aud: "https://lw.example/mcp", exp }), refresh_token: "r1" }) };
    };
    const auth = require("../app/desk/excel/auth.js");
    auth.configure({ auth_required: true, authorize_url: "https://auth.example/oauth2/authorize", client_id: "client_1", resource: "https://lw.example/mcp", token_path: "/excel/token", callback_path: "/excel/signin-callback.html" });
    assert.strictEqual(await auth.accessToken(), null);

    const who = await auth.signIn();
    const authorize = new URL(opened.searchParams.get("go"));
    assert.strictEqual(opened.pathname, "/excel/signin.html");
    assert.strictEqual(authorize.searchParams.get("code_challenge_method"), "S256");
    assert.strictEqual(authorize.searchParams.get("redirect_uri"), "https://lw.example/excel/signin-callback.html");
    assert.strictEqual(authorize.searchParams.get("resource"), "https://lw.example/mcp");
    const verifier = sent.body.get("code_verifier");
    assert.strictEqual(authorize.searchParams.get("code_challenge"), await auth.challengeFor(verifier));
    assert.strictEqual(sent.path, "/excel/token");
    assert.strictEqual(sent.body.get("grant_type"), "authorization_code");
    assert.deepStrictEqual([who.signed_in, who.audience], [true, "https://lw.example/mcp"]);
    assert.ok(!("token" in who));
    assert.ok((await auth.accessToken()).startsWith("h."));
    assert.deepStrictEqual(stored, []);

    // An expired token is renewed in memory with the refresh token.
    auth._state.expires = 0;
    await auth.accessToken();
    assert.strictEqual(sent.body.get("grant_type"), "refresh_token");

    // A reply with someone else's state is refused.
    auth.signOut();
    reply = { code: "c2", state: "not-ours" };
    await assert.rejects(auth.signIn(), /didn't match/);
    assert.strictEqual(auth.describe().signed_in, false);

    // signin.html only forwards to the provider's own sign-in page.
    assert.ok(auth.allowedStart("https://auth.example/oauth2/authorize?x=1", "https://auth.example/oauth2/authorize"));
    assert.ok(!auth.allowedStart("https://evil.example/oauth2/authorize", "https://auth.example/oauth2/authorize"));
    assert.ok(!auth.allowedStart("http://auth.example/oauth2/authorize", "https://auth.example/oauth2/authorize"));
    assert.ok(!auth.allowedStart("javascript:alert(1)", "https://auth.example/oauth2/authorize"));
  })();

  console.log("excel add-in checks passed");
})().catch((error) => { console.error(error); process.exit(1); });

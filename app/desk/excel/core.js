// What the add-in does to a workbook. No page code here, so it can be tested without Excel.
"use strict";

(function (root) {
  const RESULT_HEADERS = ["Flag", "Lenders call it", "Value (% of amount owed)", "Change (points)", "Filing"];
  const LOAN_HEADERS = ["Company", "Lender", "Loan type", "Due", "Amount owed ($)", "Value this quarter (%)", "Value last quarter (%)", "Change (points)", "Filing row", "Filing"];
  const LOOKUP = /\b(X?LOOKUP|VLOOKUP|HLOOKUP|X?MATCH)\s*\(/i;
  const NAME_HEADER = /company|companies|borrower|issuer|entity|portfolio|\bname\b/i;
  const NOT_NAME_HEADER = /owner|sponsor|manager|lender/i;
  const FILLS = { Flagged: "#FBE9E6", "Worth a look": "#FBF1DA" };
  const MAX_ROWS = 5000;

  function flagLabel(row) {
    if (!row.loans.length) return row.result;
    return row.to_confirm.length ? row.flag + ", confirm match" : row.flag;
  }

  function resultRow(row) {
    return [
      flagLabel(row),
      row.listed_as || "",
      row.loans.length ? row.value_pct : "",
      row.loans.length && row.change !== null ? row.change : "",
      row.filing_url || "",
    ];
  }

  function namesFromRange(values) {
    return values.flat().map((v) => String(v ?? "").trim());
  }

  // Keeps one output row per input cell, so results stay beside the names they belong to.
  function spillRows(names, rows) {
    const byName = new Map(rows.map((r) => [r.name, r]));
    return names.map((n) => (byName.has(n) ? resultRow(byName.get(n)) : ["", "", "", "", ""]));
  }

  function countFailedLookups(values, formulas) {
    const usesLookup = formulas.some((row) => row.some((f) => typeof f === "string" && LOOKUP.test(f)));
    if (!usesLookup) return 0;
    return values.reduce((n, row) => n + row.filter((v) => v === "#N/A").length, 0);
  }

  function findNameColumn(values) {
    if (!values.length) return -1;
    return values[0].findIndex((h) => typeof h === "string" && NAME_HEADER.test(h) && !NOT_NAME_HEADER.test(h));
  }

  // Results go in the first column to the right of everything on the sheet, so nothing the analyst wrote is overwritten.
  function firstFreeColumn(values) {
    let last = -1;
    for (const row of values) row.forEach((v, c) => { if (v !== "" && v !== null && c > last) last = c; });
    return last + 1;
  }

  function loanRows(rows) {
    return rows.flatMap((r) => r.loans.map((l) => [
      r.name, l.lender, l.type ?? "", l.due ?? "", l.amount_owed, l.value_pct,
      l.last_quarter_pct ?? "", l.change ?? "", l.filing_row, l.filing_url,
    ]));
  }

  async function readWorkbook(context) {
    const sheets = context.workbook.worksheets;
    sheets.load("items/name");
    await context.sync();
    const used = sheets.items.map((s) => {
      const range = s.getUsedRangeOrNullObject(true);
      range.load("values,formulas");
      return { name: s.name, range };
    });
    await context.sync();
    const book = {}, failed = {};
    for (const { name, range } of used) {
      if (range.isNullObject) continue;
      book[name] = range.values.slice(0, MAX_ROWS);
      failed[name] = countFailedLookups(range.values.slice(0, MAX_ROWS), range.formulas.slice(0, MAX_ROWS));
    }
    return { sheets: book, failedLookups: Object.values(failed).reduce((a, b) => a + b, 0) };
  }

  function chooseList(book, preferred) {
    const order = [preferred, ...Object.keys(book)];
    for (const sheet of order) {
      if (!book[sheet]) continue;
      const column = findNameColumn(book[sheet]);
      if (column >= 0) return { sheet, column, names: book[sheet].slice(1).map((r) => String(r[column] ?? "").trim()) };
    }
    return null;
  }

  function writeResultCells(sheet, startRow, startColumn, rows) {
    const range = sheet.getRangeByIndexes(startRow, startColumn, rows.length, RESULT_HEADERS.length);
    range.values = rows.map(resultRow);
    rows.forEach((row, i) => {
      const flagCell = sheet.getRangeByIndexes(startRow + i, startColumn, 1, 1);
      if (FILLS[row.flag] && row.loans.length) flagCell.format.fill.color = FILLS[row.flag];
      else flagCell.format.fill.clear();
      if (row.filing_url) {
        sheet.getRangeByIndexes(startRow + i, startColumn + 4, 1, 1).hyperlink = { address: row.filing_url, textToDisplay: "Open filing" };
      }
    });
  }

  async function freeSheetName(context, base) {
    for (let i = 1; i < 100; i++) {
      const name = i === 1 ? base : `${base} ${i}`;
      const found = context.workbook.worksheets.getItemOrNullObject(name);
      found.load("name");
      await context.sync();
      if (found.isNullObject) return name;
    }
    throw new Error("Too many Lender loans tabs. Please delete one.");
  }

  // Adds result columns beside the list and one new tab of loans. Returns where they went, for later updates.
  async function writeResults(context, list, rows, book) {
    const sheet = context.workbook.worksheets.getItem(list.sheet);
    const startColumn = firstFreeColumn(book[list.sheet]);
    const header = sheet.getRangeByIndexes(0, startColumn, 1, RESULT_HEADERS.length);
    header.values = [RESULT_HEADERS];
    header.format.font.bold = true;

    const byName = new Map(rows.map((r) => [r.name, r]));
    const placed = [];
    list.names.forEach((name, i) => {
      const row = byName.get(name);
      if (row) { writeResultCells(sheet, i + 1, startColumn, [row]); placed.push({ name, rowIndex: i + 1 }); }
    });

    const loans = loanRows(rows);
    if (loans.length) {
      const name = await freeSheetName(context, "Lender loans");
      const tab = context.workbook.worksheets.add(name);
      tab.getRangeByIndexes(0, 0, loans.length + 1, LOAN_HEADERS.length).values = [LOAN_HEADERS, ...loans];
      tab.getRangeByIndexes(0, 0, 1, LOAN_HEADERS.length).format.font.bold = true;
    }
    await context.sync();
    return { sheet: list.sheet, startColumn, placed };
  }

  async function updateResult(context, written, row) {
    const hit = written.placed.find((p) => p.name === row.name);
    if (!hit) return;
    writeResultCells(context.workbook.worksheets.getItem(written.sheet), hit.rowIndex, written.startColumn, [row]);
    await context.sync();
  }

  const api = { RESULT_HEADERS, LOAN_HEADERS, resultRow, namesFromRange, spillRows, countFailedLookups, findNameColumn, firstFreeColumn, loanRows, readWorkbook, chooseList, writeResults, updateResult };
  if (typeof module !== "undefined") module.exports = api;
  root.ErmExcel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

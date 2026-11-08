// The Excel formula =ERM.RECONCILE(A2:A6). It runs inside the add-in and only talks to the server on this computer.
"use strict";

async function reconcile(companies) {
  const names = ErmExcel.namesFromRange(companies);
  const wanted = [...new Set(names.filter(Boolean))];
  if (!wanted.length) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, "Select cells with company names.");
  }
  let response;
  try {
    response = await fetch("/api/reconcile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sheets: {}, names: wanted }),
    });
  } catch (error) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, "Lender Watch isn't running. Run make excel.");
  }
  if (!response.ok) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, "Lender Watch couldn't read that list.");
  }
  const out = await response.json();
  return ErmExcel.spillRows(names, out.rows);
}

CustomFunctions.associate("RECONCILE", reconcile);

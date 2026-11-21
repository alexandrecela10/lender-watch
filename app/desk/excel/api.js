// Calls from the add-in to the Lender Watch service: the formula and the panel use this, so they send the same thing.
// The sign-in token comes from LwAuth, in memory. Messages are written for the person reading the cell or the panel.
"use strict";

(function (root) {
  const SIGN_IN = "Sign in from the Lender Watch panel.";

  async function post(path, body) {
    const headers = { "Content-Type": "application/json" };
    if (root.LwAuth && LwAuth.required()) {
      const token = await LwAuth.accessToken();
      if (!token) throw new Error(SIGN_IN);
      headers.Authorization = `Bearer ${token}`;
    }
    let response;
    try {
      response = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
    } catch (error) {
      throw new Error("Lender Watch can't be reached.");
    }
    if (response.status === 401) throw new Error(SIGN_IN);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Lender Watch couldn't read that list.");
    return data;
  }

  // Up to 50 names per call, joined in order. `extra` adds the sheet so owner and sector columns can help.
  function check(names, asOf, extra = {}) {
    const items = names.map((name) => ({ name }));
    return ErmExcel.checkInBatches((batch) => post("/api/check", { companies: batch, as_of: asOf || null, ...extra }), items);
  }

  const api = { post, check, SIGN_IN };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.LwApi = api;
})(typeof window !== "undefined" ? window : globalThis);

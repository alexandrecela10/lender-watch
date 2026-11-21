// Sign-in for the Lender Watch add-in. One provider, PKCE, no client secret.
// The access token lives in this module's memory only, inside the add-in's shared runtime, so the formula and the
// panel see the same token. Nothing is written to localStorage or Office storage: closing Excel signs the person out.
"use strict";

(function (root) {
  const MARGIN_SECONDS = 60; // renew a token this long before it expires
  const state = { config: null, token: null, refresh: null, expires: 0, pending: null };

  function base64url(bytes) {
    let s = "";
    for (const b of bytes) s += String.fromCharCode(b);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function randomString(n = 32) {
    const bytes = new Uint8Array(n);
    crypto.getRandomValues(bytes);
    return base64url(bytes);
  }

  async function challengeFor(verifier) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
    return base64url(new Uint8Array(digest));
  }

  // Reads the middle part of a JWT for display: audience and expiry. Never shown or logged whole.
  function claims(token) {
    try {
      const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(atob(part + "===".slice((part.length + 3) % 4)));
    } catch (error) {
      return {};
    }
  }

  function now() {
    return Math.floor(Date.now() / 1000);
  }

  // `config` comes from /api/status: { auth_required, authorize_url, client_id, resource, token_path, callback_path }.
  function configure(config) {
    state.config = config;
  }

  function required() {
    return Boolean(state.config && state.config.auth_required);
  }

  function callbackUrl() {
    return new URL(state.config.callback_path, root.location.origin).href;
  }

  function authorizeUrl(challenge, nonce) {
    const c = state.config;
    const url = new URL(c.authorize_url);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", c.client_id);
    url.searchParams.set("redirect_uri", callbackUrl());
    url.searchParams.set("code_challenge", challenge);
    url.searchParams.set("code_challenge_method", "S256");
    url.searchParams.set("state", nonce);
    if (c.resource) url.searchParams.set("resource", c.resource);
    return url.href;
  }

  function keep(reply) {
    if (!reply.access_token) throw new Error("Sign-in didn't return a token.");
    state.token = reply.access_token;
    state.refresh = reply.refresh_token || null;
    const exp = claims(reply.access_token).exp;
    state.expires = exp || now() + Number(reply.expires_in || 300);
  }

  async function tokenRequest(fields) {
    const c = state.config;
    const body = new URLSearchParams({ client_id: c.client_id, ...fields });
    if (c.resource) body.set("resource", c.resource);
    // Our own server passes the request to the provider, so the browser needs no cross-site permission.
    const response = await fetch(c.token_path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!response.ok) throw new Error("Sign-in was refused.");
    keep(await response.json());
  }

  // Opens the provider's sign-in in an Office dialog. The dialog's first page and its callback page are on the
  // add-in's own address, which Office requires for the callback to hand the result back.
  function openDialog(url) {
    return new Promise((resolve, reject) => {
      const start = new URL("signin.html", root.location.href);
      start.searchParams.set("go", url);
      Office.context.ui.displayDialogAsync(start.href, { height: 60, width: 30, promptBeforeOpen: false }, (opened) => {
        if (opened.status !== Office.AsyncResultStatus.Succeeded) {
          reject(new Error("Excel couldn't open the sign-in window."));
          return;
        }
        const dialog = opened.value;
        dialog.addEventHandler(Office.EventType.DialogMessageReceived, (arg) => {
          dialog.close();
          try {
            resolve(JSON.parse(arg.message));
          } catch (error) {
            reject(new Error("Sign-in returned something unexpected."));
          }
        });
        dialog.addEventHandler(Office.EventType.DialogEventReceived, () => reject(new Error("Sign-in window closed.")));
      });
    });
  }

  async function signIn() {
    const verifier = randomString(48);
    const nonce = randomString(16);
    const result = await openDialog(authorizeUrl(await challengeFor(verifier), nonce));
    if (result.error) throw new Error("Sign-in was refused.");
    if (result.state !== nonce) throw new Error("Sign-in didn't match this window. Try again.");
    await tokenRequest({ grant_type: "authorization_code", code: result.code, code_verifier: verifier, redirect_uri: callbackUrl() });
    return describe();
  }

  // A valid token, renewed in memory when it's about to expire. Null means the person must sign in.
  async function accessToken() {
    if (!required()) return null;
    if (state.token && state.expires - MARGIN_SECONDS > now()) return state.token;
    if (!state.refresh) return null;
    if (!state.pending) {
      state.pending = tokenRequest({ grant_type: "refresh_token", refresh_token: state.refresh })
        .catch(() => signOut())
        .finally(() => { state.pending = null; });
    }
    await state.pending;
    return state.token;
  }

  function signOut() {
    state.token = null;
    state.refresh = null;
    state.expires = 0;
  }

  // What the panel may show: who the token is for and when it ends. Never the token itself.
  function describe() {
    if (!state.token) return { signed_in: false };
    const c = claims(state.token);
    return { signed_in: true, audience: c.aud || null, expires: state.expires };
  }

  // Only the provider's own sign-in page may be opened from signin.html, so it can't be used to send people elsewhere.
  function allowedStart(go, authorizeUrlFromStatus) {
    try {
      const target = new URL(go);
      const allowed = new URL(authorizeUrlFromStatus);
      return target.protocol === "https:" && target.origin === allowed.origin && target.pathname === allowed.pathname;
    } catch (error) {
      return false;
    }
  }

  const api = { configure, required, signIn, accessToken, signOut, describe, allowedStart, authorizeUrl, challengeFor, claims, _state: state };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.LwAuth = api;
})(typeof window !== "undefined" ? window : globalThis);

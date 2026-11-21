// Dev playground: talks to the API on the same origin, so the session cookie just works.
const $ = (id) => document.getElementById(id);
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
let signedIn = false;

$("tz").textContent = timezone;

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, body };
}

// ---- messages ---------------------------------------------------------------

function addMessage(who, text, meta = []) {
  const li = document.createElement("li");
  li.className = `msg ${who}`;
  const p = document.createElement("p");
  p.textContent = text;
  li.append(p);
  if (meta.length) {
    const row = document.createElement("div");
    row.className = "meta";
    row.append(...meta);
    li.append(row);
  }
  $("messages").append(li);
  li.scrollIntoView({ behavior: "smooth", block: "end" });
}

function badge(label, kind) {
  const span = document.createElement("span");
  span.className = `badge ${kind}`;
  span.textContent = label.replace("_", " ");
  return span;
}

function link(href, label) {
  const a = document.createElement("a");
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener";
  a.textContent = label;
  return a;
}

function plain(text) {
  const span = document.createElement("span");
  span.textContent = text;
  return span;
}

// ---- assistant --------------------------------------------------------------

async function send(text) {
  addMessage("user", text);
  $("send").disabled = true;
  try {
    const { ok, status, body } = await api("/api/v1/assistant", {
      method: "POST",
      body: JSON.stringify({ text, timezone, request_id: crypto.randomUUID() }),
    });

    if (status === 401) {
      addMessage("bot", "You're not signed in. Use “Sign in with Google” at the top.", [
        badge("error", "error"),
      ]);
      return;
    }
    if (!ok) {
      addMessage("bot", body?.detail ?? `Request failed (${status}).`, [badge("error", "error")]);
      return;
    }

    const meta = [badge(body.outcome, body.outcome), plain(body.intent)];
    const result = body.result ?? {};
    if (result.link) meta.push(link(result.link, "Open in Calendar"));
    if (result.meet_link) meta.push(link(result.meet_link, "Meet link"));
    addMessage("bot", body.reply, meta);

    if (body.outcome === "done" && result.note_id) loadNotes();
  } catch {
    addMessage("bot", "Could not reach the API. Is it running?", [badge("error", "error")]);
  } finally {
    $("send").disabled = false;
    $("text").focus();
  }
}

$("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = $("text").value.trim();
  if (!text) return;
  $("text").value = "";
  send(text);
});

$("chips").addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") send(event.target.textContent);
});

// ---- account ----------------------------------------------------------------

async function loadAccount() {
  const box = $("account");
  box.replaceChildren();
  const { ok, body } = await api("/auth/me").catch(() => ({ ok: false }));
  signedIn = ok;

  if (!ok) {
    const signIn = link("/auth/google/start", "Sign in with Google");
    signIn.target = "_self";
    signIn.className = "btn";
    box.append(signIn);
    return;
  }

  if (body.picture_url) {
    const img = document.createElement("img");
    img.src = body.picture_url;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    box.append(img);
  }
  box.append(plain(body.email));

  const out = document.createElement("button");
  out.className = "ghost";
  out.type = "button";
  out.textContent = "Sign out";
  out.addEventListener("click", async () => {
    await api("/auth/logout", { method: "POST" });
    location.reload();
  });
  box.append(out);
}

// ---- notes ------------------------------------------------------------------

async function loadNotes() {
  const list = $("notes");
  if (!signedIn) {
    list.innerHTML = '<li class="muted">Sign in to see notes.</li>';
    return;
  }
  const { ok, body } = await api("/api/v1/notes");
  list.replaceChildren();
  if (!ok || body.length === 0) {
    list.innerHTML = `<li class="muted">${ok ? "No notes yet." : "Could not load notes."}</li>`;
    return;
  }
  for (const note of body) {
    const li = document.createElement("li");
    const time = document.createElement("time");
    time.dateTime = note.created_at;
    time.textContent = new Date(note.created_at).toLocaleString();
    li.append(plain(note.content), time);
    list.append(li);
  }
}

$("refresh").addEventListener("click", loadNotes);

// ---- start ------------------------------------------------------------------

const authError = new URLSearchParams(location.search).get("auth_error");
if (authError) {
  $("banner").textContent = `Sign-in failed: ${authError}`;
  $("banner").hidden = false;
  history.replaceState(null, "", location.pathname);
}

loadAccount().then(loadNotes);
$("text").focus();

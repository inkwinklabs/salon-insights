// Shared parts of the page: helpers, tabs, settings, and the Real/Demo switch.
// visit-form.js and customers.js use the helpers defined here.
// Plain JavaScript, no framework, so every line can be read and understood.

// The salon settings (services, staff, currency), filled in by loadSettings().
const app = { settings: null, currency: "₹" };

// ================================================================ helpers

// Ask the server for JSON.
async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Server replied ${response.status} for ${url}`);
  return response.json();
}

// Send a change to the server as JSON.
// (The server only accepts changes sent as JSON, which blocks other websites.)
// Returns { ok, status, data } so callers can show the server's messages.
async function postJSON(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, data };
}

// Turn text into safe HTML, so a name like "<b>" shows as text, not as code.
// Quotes are escaped too, so text is also safe inside attributes like value="...".
function escapeHTML(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ₹1,41,330 (Indian-style commas).
function money(amount) {
  return app.currency + Number(amount).toLocaleString("en-IN");
}

// "2026-05-09" → "9 May 2026"
function niceDate(isoDate) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
}

// Today as "YYYY-MM-DD" in the laptop's own time zone.
function todayISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

// 0 → "today", 1 → "yesterday", 12 → "12 days ago"
function daysAgo(days) {
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

function showError(message) {
  const box = document.getElementById("error");
  box.textContent = message;
  box.hidden = !message;
}

// ================================================================ tabs

// Other files register what to do when their tab opens, e.g. reload the list.
const onTabOpen = {};

function openTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.screen === name));
  document.querySelectorAll(".screen").forEach((s) => (s.hidden = s.id !== "screen-" + name));
  if (onTabOpen[name]) onTabOpen[name]();
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => openTab(tab.dataset.screen));
});

// ================================================================ theme (light / dark)

// Auto → Light → Dark → Auto. "Auto" follows the laptop's own setting.
const THEMES = ["auto", "light", "dark"];
function currentTheme() {
  return document.documentElement.dataset.theme || "auto";
}
function applyTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try {
    if (theme === "auto") localStorage.removeItem("theme");
    else localStorage.setItem("theme", theme);
  } catch (e) { /* storage blocked: the choice just won't be remembered */ }
  const label = { auto: "Auto", light: "Light", dark: "Dark" }[theme];
  document.getElementById("theme-btn").textContent = "Theme: " + label;
  // Charts are drawn on a canvas, so they must be redrawn in the new colours.
  document.dispatchEvent(new Event("themechange"));
}
document.getElementById("theme-btn").addEventListener("click", () => {
  const next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
  applyTheme(next);
});
document.getElementById("theme-btn").textContent =
  "Theme: " + { auto: "Auto", light: "Light", dark: "Dark" }[currentTheme()];
// If the laptop itself switches between light and dark, redraw too.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  document.dispatchEvent(new Event("themechange"));
});

// ================================================================ settings

async function loadSettings() {
  app.settings = await getJSON("/api/settings");
  const { salon } = app.settings;
  app.currency = salon.currency;

  document.getElementById("salon-name").textContent = salon.name;
  document.getElementById("salon-city").textContent = salon.city ? " · " + salon.city : "";
  document.title = salon.name + " · Insights";
  document.getElementById("ai-model").textContent = app.settings.ai_model;
  document.querySelectorAll(".currency").forEach((el) => (el.textContent = salon.currency));
}

// ================================================================ Real / Demo and the Data card

// Ask the server which mode is active and what data it holds, then update
// the switch, the DEMO MODE banner, the buttons and the summary line.
async function refreshSummary() {
  const s = await getJSON("/api/summary");
  const isDemo = s.mode === "demo";
  app.mode = s.mode;

  document.querySelectorAll(".mode-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === s.mode);
    b.setAttribute("aria-pressed", b.dataset.mode === s.mode);
  });
  document.getElementById("demo-banner").hidden = !isDemo;
  document.getElementById("demo-actions").hidden = !isDemo;

  const summary = document.getElementById("data-summary");
  if (s.visits === 0) {
    summary.textContent = isDemo
      ? "Demo data is empty. Press “Load demo data” to fill it with sample customers."
      : "No visits logged yet. Use the form below to log the first one.";
  } else {
    summary.textContent =
      `${s.customers} customers · ${s.visits} services logged · ${money(s.revenue)} revenue · ` +
      `${niceDate(s.first_visit)} to ${niceDate(s.last_visit)}`;
  }
}

// Called whenever the data changes (visit saved, mode switched, demo loaded).
// Other files add their own refresh steps to this list.
const dataChangedListeners = [refreshSummary];
async function dataChanged() {
  for (const listener of dataChangedListeners) await listener();
}

// Clicking Real or Demo switches the data the whole app uses.
document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const result = await postJSON("/api/mode", { mode: btn.dataset.mode });
    if (!result.ok) return showError("Could not switch mode.");
    await dataChanged();
  });
});

// Run an action while its button shows it's busy (stops double clicks).
async function withBusyButton(button, action) {
  button.disabled = true;
  try {
    await action();
    showError("");
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
  }
}

document.getElementById("btn-load-demo").addEventListener("click", (e) => {
  if (!confirm("Replace the demo data with fresh sample data? (Real data is not affected.)")) return;
  withBusyButton(e.currentTarget, async () => {
    await postJSON("/api/demo/load");
    await dataChanged();
  });
});

document.getElementById("btn-clear-demo").addEventListener("click", (e) => {
  if (!confirm("Empty all demo data? (Real data is not affected.)")) return;
  withBusyButton(e.currentTarget, async () => {
    await postJSON("/api/demo/clear");
    await dataChanged();
  });
});

// ================================================================ start-up

// Other files put their start-up steps here; they run once settings are loaded.
const startUpSteps = [];

loadSettings()
  .then(refreshSummary)
  .then(() => Promise.all(startUpSteps.map((step) => step())))
  .catch((err) => showError("Could not load the app: " + err.message));

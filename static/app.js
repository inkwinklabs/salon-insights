// The page's behaviour: switching tabs and loading data from the server.
// Plain JavaScript, no framework, so every line can be read and understood.

// ---- Tabs: show one screen, hide the others ----
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".screen").forEach((s) => (s.hidden = true));
    document.getElementById("screen-" + tab.dataset.screen).hidden = false;
  });
});

// ---- Small helper: ask the server for JSON ----
async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Server replied ${response.status} for ${url}`);
  return response.json();
}

// ---- Safety helper: turn text into safe HTML (stops odd names breaking the page) ----
function escapeHTML(text) {
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

// ---- Load the salon settings and fill in the page ----
async function loadSettings() {
  const settings = await getJSON("/api/settings");
  const { salon, services } = settings;
  currency = salon.currency;

  document.getElementById("salon-name").textContent = salon.name;
  document.getElementById("salon-city").textContent = salon.city ? " · " + salon.city : "";
  document.title = salon.name + " · Insights";
  document.getElementById("ai-model").textContent = settings.ai_model;
  document.getElementById("staff-list").textContent = salon.staff.join(", ");

  document.getElementById("services-body").innerHTML = services
    .map(
      (s) => `<tr>
        <td>${escapeHTML(s.name)}</td>
        <td class="num">${escapeHTML(salon.currency)}${s.price.toLocaleString("en-IN")}</td>
        <td class="num">${s.typical_gap_days} days</td>
      </tr>`
    )
    .join("");
}

// ---- Send a change to the server as JSON ----
// (The server only accepts changes sent as JSON, which blocks other websites.)
async function postJSON(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Server replied ${response.status} for ${url}`);
  return response.json();
}

function showError(message) {
  const box = document.getElementById("error");
  box.textContent = message;
  box.hidden = !message;
}

// Turn "2026-05-09" into "9 May 2026" (Indian-style day-month order).
function niceDate(isoDate) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
}

// ---- Demo / Real mode and the Data card ----
// Ask the server which mode is active and what data it holds, then update
// the switch, the DEMO MODE banner, the buttons and the summary line.
async function refreshData() {
  const s = await getJSON("/api/summary");
  const isDemo = s.mode === "demo";

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
      : "No visits logged yet. Real data starts empty; the visit form arrives in stage 3.";
  } else {
    summary.textContent =
      `${s.customers} customers · ${s.visits} visits · ` +
      `${currency}${s.revenue.toLocaleString("en-IN")} revenue · ` +
      `${niceDate(s.first_visit)} to ${niceDate(s.last_visit)}`;
  }
}

// Clicking Real or Demo switches the data the whole app uses.
document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try {
      await postJSON("/api/mode", { mode: btn.dataset.mode });
      await refreshData();
    } catch (err) {
      showError("Could not switch mode: " + err.message);
    }
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
    await refreshData();
  });
});

document.getElementById("btn-clear-demo").addEventListener("click", (e) => {
  if (!confirm("Empty all demo data? (Real data is not affected.)")) return;
  withBusyButton(e.currentTarget, async () => {
    await postJSON("/api/demo/clear");
    await refreshData();
  });
});

// ---- Start-up: load settings first (for the ₹ sign), then the data card ----
let currency = "₹";
loadSettings()
  .then(refreshData)
  .catch((err) => showError("Could not load the app: " + err.message));

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

loadSettings().catch((err) => {
  const box = document.getElementById("error");
  box.textContent = "Could not load settings: " + err.message;
  box.hidden = false;
});

// The "Customers" list: search, filter by status, sort, and click a row to
// see that customer's visit history. All the maths happens on the server
// (analysis.py); this file only shows the results.

const customersView = {
  all: [],             // every customer from the server
  rules: null,         // the regular/overdue rules from settings.toml
  search: "",
  filter: "all",       // all | regular | overdue | occasional | one-time
  sortBy: "days_since",
  sortAscending: true, // most recent visit first
  openId: null,        // which customer's history is showing
};

const STATUS_LABELS = {
  regular: "Regular",
  overdue: "Overdue",
  occasional: "Occasional",
  "one-time": "One-time",
};

// ---- Load from the server ----
async function loadCustomers() {
  const result = await getJSON("/api/customers");
  customersView.all = result.customers;
  customersView.rules = result.rules;
  renderCustomers();
}
// Reload when the tab opens, and when data changes while it's open.
onTabOpen.customers = loadCustomers;
dataChangedListeners.push(async () => {
  if (!document.getElementById("screen-customers").hidden) await loadCustomers();
});

// ---- Search, filter, sort ----
document.getElementById("cust-search").addEventListener("input", (e) => {
  customersView.search = e.target.value.trim().toLowerCase();
  renderCustomers();
});

document.querySelectorAll(".sort").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.sort;
    if (customersView.sortBy === key) {
      customersView.sortAscending = !customersView.sortAscending; // click again to flip
    } else {
      customersView.sortBy = key;
      // Names A→Z and recent first feel natural; numbers biggest first.
      customersView.sortAscending = key === "name" || key === "days_since";
    }
    renderCustomers();
  });
});

function matchesSearch(c) {
  const q = customersView.search;
  if (!q) return true;
  const digits = q.replace(/\D/g, "");
  return c.name.toLowerCase().includes(q) || (digits && c.phone.includes(digits));
}

function sortCustomers(list) {
  const { sortBy, sortAscending } = customersView;
  const statusOrder = { overdue: 0, regular: 1, occasional: 2, "one-time": 3 };
  const value = (c) => (sortBy === "status" ? statusOrder[c.status] : c[sortBy]);
  return [...list].sort((a, b) => {
    const x = value(a), y = value(b);
    const result = typeof x === "string" ? x.localeCompare(y) : x - y;
    return sortAscending ? result : -result;
  });
}

// ---- Draw the filter buttons (with counts) ----
function renderFilters(searched) {
  const counts = { all: searched.length };
  for (const c of searched) counts[c.status] = (counts[c.status] || 0) + 1;
  const options = [["all", "All"], ...Object.entries(STATUS_LABELS)];
  document.getElementById("cust-filters").innerHTML = options
    .map(
      ([key, label]) => `<button class="chip ${customersView.filter === key ? "active" : ""}"
         data-filter="${key}" aria-pressed="${customersView.filter === key}">
         ${label} <span class="chip-count">${counts[key] || 0}</span></button>`
    )
    .join("");
}

document.getElementById("cust-filters").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  customersView.filter = chip.dataset.filter;
  renderCustomers();
});

// ---- Draw the table ----
function renderCustomers() {
  const { rules } = customersView;
  document.getElementById("cust-rule").textContent = rules
    ? `Regular = ${rules.min_visits_for_regular}+ visits. Overdue = a regular whose last visit is ` +
      `more than ${rules.overdue_factor}× their usual gap ago. Change these in settings.toml.`
    : "";

  const searched = customersView.all.filter(matchesSearch);
  renderFilters(searched);
  const shown = sortCustomers(
    searched.filter((c) => customersView.filter === "all" || c.status === customersView.filter)
  );

  // Show which column is sorted, and which way.
  document.querySelectorAll(".sort").forEach((btn) => {
    const active = btn.dataset.sort === customersView.sortBy;
    btn.classList.toggle("sorted", active);
    btn.dataset.arrow = active ? (customersView.sortAscending ? "▲" : "▼") : "";
  });

  const empty = document.getElementById("cust-empty");
  empty.hidden = shown.length > 0;
  empty.textContent = customersView.all.length === 0
    ? "No customers yet. Log a visit to add the first one."
    : "No customers match.";

  document.getElementById("cust-body").innerHTML = shown
    .map(
      (c) => `
      <tr class="cust-row ${customersView.openId === c.id ? "open" : ""}" data-id="${c.id}"
          tabindex="0" aria-expanded="${customersView.openId === c.id}">
        <td class="cust-name">${escapeHTML(c.name)}</td>
        <td class="phone">${escapeHTML(c.phone)}</td>
        <td class="num">${c.visits}</td>
        <td>${daysAgo(c.days_since)}<div class="sub">${niceDate(c.last_visit)}</div></td>
        <td class="num">${money(c.avg_spend)}</td>
        <td>${escapeHTML(c.usual_service)}</td>
        <td><span class="badge badge-${c.status}">${STATUS_LABELS[c.status]}</span></td>
      </tr>
      ${customersView.openId === c.id ? `<tr class="history-row"><td colspan="7" id="history-${c.id}">Loading…</td></tr>` : ""}`
    )
    .join("");

  if (customersView.openId !== null) loadHistory(customersView.openId);
}

// ---- Click a customer to open or close their history ----
function toggleRow(row) {
  const id = Number(row.dataset.id);
  customersView.openId = customersView.openId === id ? null : id;
  renderCustomers();
}
document.getElementById("cust-body").addEventListener("click", (e) => {
  const row = e.target.closest(".cust-row");
  if (row) toggleRow(row);
});
document.getElementById("cust-body").addEventListener("keydown", (e) => {
  const row = e.target.closest(".cust-row");
  if (row && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    toggleRow(row);
  }
});

async function loadHistory(id) {
  const c = customersView.all.find((x) => x.id === id);
  const { visits } = await getJSON(`/api/customers/${id}/visits`);
  const cell = document.getElementById("history-" + id);
  if (!cell || !c) return; // the list changed while we were waiting

  const pattern = c.avg_gap
    ? `Usually comes every <strong>${c.avg_gap} days</strong>; last came <strong>${c.days_since} days</strong> ago.`
    : "Only one visit so far.";
  cell.innerHTML = `
    <div class="history">
      <p>${pattern} Customer since ${niceDate(c.first_visit)} · total spent ${money(c.total_spent)}.</p>
      <table class="table table-compact">
        <thead><tr><th>Date</th><th>Service</th><th class="num">Price</th><th>Staff</th></tr></thead>
        <tbody>${visits
          .map(
            (v) => `<tr><td>${niceDate(v.visit_date)}</td><td>${escapeHTML(v.service)}</td>
                    <td class="num">${money(v.price)}</td><td>${escapeHTML(v.staff)}</td></tr>`
          )
          .join("")}</tbody>
      </table>
    </div>`;
}

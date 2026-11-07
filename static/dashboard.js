// The Dashboard: headline numbers, three charts, and a table under each chart.
//
// All the maths happens on the server (analysis.py → /api/dashboard).
// This file only draws what comes back, using Chart.js.

const dash = {
  period: "all",          // which period is chosen
  measure: "revenue",     // how services are ranked: revenue | count | avg_price
  data: null,             // the last answer from the server
  charts: {},             // the Chart.js charts, so we can replace them
};

const SERVICE_MEASURES = {
  revenue: { label: "Revenue", hint: "What each service earned in total.", money: true },
  count: { label: "Times done", hint: "How many times each service was done.", money: false },
  avg_price: { label: "Avg per visit", hint: "What each service earns, on average, each time it's done.", money: true },
};
const DAY_NAMES = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday",
                    Fri: "Friday", Sat: "Saturday", Sun: "Sunday" };

// ================================================================ chart look

// Colours come from style.css (--chart-*), so the look is set in one place.
function cssColour(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function setChartDefaults() {
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cssColour("--muted");            // axis text
  Chart.defaults.plugins.legend.display = false;          // one series per chart: the title names it
  Chart.defaults.maintainAspectRatio = false;             // fill the box's height
  // Calm or no animation (no animation at all if the laptop asks for reduced motion).
  Chart.defaults.animation.duration =
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 250;

  const tip = Chart.defaults.plugins.tooltip;
  tip.backgroundColor = cssColour("--text");
  tip.padding = 10;
  tip.cornerRadius = 6;
  tip.displayColors = false;
  tip.titleFont = { weight: "normal" };                   // the label is secondary...
  tip.bodyFont = { weight: "bold", size: 13 };            // ...the value leads
  tip.footerFont = { weight: "normal" };
}

// Shared settings for every bar: thin, 4px rounded end, square at the baseline.
function barStyle(colours) {
  return {
    backgroundColor: colours,
    hoverBackgroundColor: cssColour("--chart-hover"),
    borderRadius: 4,
    borderSkipped: "start",     // keep the baseline end square
    maxBarThickness: 24,
  };
}

// Axis settings: hairline grid on the value axis only, nothing on the other.
function valueAxis(formatTick) {
  return {
    beginAtZero: true,
    grid: { color: cssColour("--chart-grid"), lineWidth: 1 },
    border: { display: false },
    ticks: { callback: formatTick, maxTicksLimit: 6 },
  };
}
function categoryAxis() {
  return { grid: { display: false }, border: { color: cssColour("--chart-axis") } };
}

// ₹12K, ₹1.2L (lakh): short money for axis ticks, Indian-style.
const compact = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });
const compactMoney = (v) => app.currency + compact.format(v);
const plainNumber = (v) => Number(v).toLocaleString("en-IN");

// A tiny Chart.js plugin: write a few chosen values next to their bars.
// We label only a few bars on purpose (busiest, quietest, top...), because a
// number on every bar is hard to read. The rest are in the tooltip and table.
const valueLabels = {
  id: "valueLabels",
  afterDatasetsDraw(chart, _args, options) {
    const labels = options.labels || {}; // { barIndex: "text" }
    const { ctx } = chart;
    const horizontal = chart.options.indexAxis === "y";
    ctx.save();
    ctx.fillStyle = cssColour("--text");
    ctx.font = `600 12px ${Chart.defaults.font.family}`;
    chart.getDatasetMeta(0).data.forEach((bar, i) => {
      if (!(i in labels)) return;
      if (horizontal) {
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(labels[i], bar.x + 6, bar.y);
      } else {
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillText(labels[i], bar.x, bar.y - 4);
      }
    });
    ctx.restore();
  },
};

function drawChart(key, canvasId, config) {
  if (dash.charts[key]) dash.charts[key].destroy(); // replace the old chart
  config.plugins = [valueLabels];
  config.options.interaction = { mode: "index", intersect: false }; // hover anywhere in the bar's column
  dash.charts[key] = new Chart(document.getElementById(canvasId), config);
}

// Build a simple HTML table: the "Show as table" view under each chart.
function tableHTML(headers, rows, numericColumns = []) {
  const th = headers
    .map((h, i) => `<th class="${numericColumns.includes(i) ? "num" : ""}">${escapeHTML(h)}</th>`).join("");
  const body = rows
    .map((r) => "<tr>" + r.map((cell, i) =>
      `<td class="${numericColumns.includes(i) ? "num" : ""}">${escapeHTML(cell)}</td>`).join("") + "</tr>")
    .join("");
  return `<table class="table table-compact"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
}

// ================================================================ loading

async function loadDashboard() {
  const body = document.getElementById("dash-body");
  body.classList.add("refreshing"); // keep the old charts, faded, while loading
  try {
    dash.data = await getJSON("/api/dashboard?period=" + dash.period);
    renderDashboard();
  } catch (err) {
    showError("Could not load the dashboard: " + err.message);
  } finally {
    body.classList.remove("refreshing");
  }
}
onTabOpen.dashboard = loadDashboard;
dataChangedListeners.push(async () => {
  if (!document.getElementById("screen-dashboard").hidden) await loadDashboard();
});
startUpSteps.push(async () => setChartDefaults());

// The period buttons (built from the server's list, so they always match).
document.getElementById("dash-periods").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip || chip.dataset.period === dash.period) return;
  dash.period = chip.dataset.period;
  loadDashboard();
});

document.getElementById("service-measures").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  dash.measure = chip.dataset.measure;
  renderServices();
});

// The overdue tile jumps to the customer list, showing only overdue customers.
document.getElementById("kpi-overdue").addEventListener("click", () => {
  customersView.filter = "overdue";
  customersView.search = "";
  document.getElementById("cust-search").value = "";
  openTab("customers");
});

function chipsHTML(items, activeKey, dataName) {
  return items
    .map(({ key, label }) => `<button class="chip ${key === activeKey ? "active" : ""}"
        data-${dataName}="${key}" aria-pressed="${key === activeKey}">${escapeHTML(label)}</button>`)
    .join("");
}

// ================================================================ drawing

function renderDashboard() {
  const d = dash.data;
  document.getElementById("dash-periods").innerHTML = chipsHTML(d.periods, dash.period, "period");
  document.getElementById("dash-range").textContent =
    `${d.period.label}: ${niceDate(d.period.start)} to ${niceDate(d.period.end)}`;

  const empty = d.kpis.visits === 0;
  document.getElementById("dash-body").hidden = empty;
  const emptyNote = document.getElementById("dash-empty");
  emptyNote.hidden = !empty;
  emptyNote.textContent = "No visits in this period yet. Log some visits, or load the demo data.";
  if (empty) return;

  renderKpis(d.kpis);
  renderWeekdays(d.weekdays);
  renderMonths(d.months);
  renderServices();
}

function renderKpis(k) {
  const isAllTime = dash.data.period.key === "all";
  document.getElementById("kpi-customers").textContent = plainNumber(k.customers);
  document.getElementById("kpi-customers-sub").textContent = isAllTime
    ? `${plainNumber(k.visits)} visits in total`
    : `${k.new_customers} new · ${plainNumber(k.visits)} visits`;

  const repeatShare = k.customers ? Math.round((100 * k.repeat_customers) / k.customers) : 0;
  document.getElementById("kpi-repeat").textContent = repeatShare + "%";
  document.getElementById("kpi-repeat-sub").innerHTML =
    `<span class="key-swatch key-main"></span>${k.repeat_customers} came 2+ times ` +
    `<span class="key-swatch key-light"></span>${k.one_time_customers} once`;
  const bar = document.getElementById("kpi-repeat-bar");
  bar.innerHTML =
    `<span class="split-part key-main" style="flex-grow:${k.repeat_customers}"></span>` +
    `<span class="split-part key-light" style="flex-grow:${k.one_time_customers}"></span>`;
  bar.setAttribute("aria-label", `${k.repeat_customers} repeat customers, ${k.one_time_customers} one-time`);

  document.getElementById("kpi-revenue").textContent = money(k.revenue);
  document.getElementById("kpi-revenue-sub").textContent = dash.data.period.label.toLowerCase();
  document.getElementById("kpi-avg").textContent = money(k.avg_spend_per_visit);
  document.getElementById("kpi-overdue-value").textContent = k.overdue_now;
}

// Index of the biggest and smallest value (first one wins a tie).
function extremes(values) {
  let hi = 0, lo = 0;
  values.forEach((v, i) => {
    if (v > values[hi]) hi = i;
    if (v < values[lo]) lo = i;
  });
  return { hi, lo };
}

function renderWeekdays(weekdays) {
  const visits = weekdays.map((w) => w.visits);
  const { hi, lo } = extremes(visits);
  // Just the number above the bar (words don't fit above a thin bar on a phone);
  // the caption under the chart says which is busiest and quietest.
  const labels = { [hi]: plainNumber(visits[hi]) };
  if (lo !== hi) labels[lo] = plainNumber(visits[lo]);
  document.getElementById("caption-weekdays").textContent =
    `Busiest: ${DAY_NAMES[weekdays[hi].day]} (${visits[hi]} visits) · ` +
    `Quietest: ${DAY_NAMES[weekdays[lo].day]} (${visits[lo]} visits)`;

  drawChart("weekdays", "chart-weekdays", {
    type: "bar",
    data: {
      labels: weekdays.map((w) => w.day),
      datasets: [{ data: visits, ...barStyle(cssColour("--chart-main")) }],
    },
    options: {
      layout: { padding: { top: 20 } }, // room for the labels above the bars
      scales: { x: categoryAxis(), y: valueAxis(plainNumber) },
      plugins: {
        valueLabels: { labels },
        tooltip: {
          callbacks: {
            title: (items) => DAY_NAMES[weekdays[items[0].dataIndex].day],
            label: (item) => `${item.raw} visits`,
            footer: (items) => `${money(weekdays[items[0].dataIndex].revenue)} revenue`,
          },
        },
      },
    },
  });
  document.getElementById("chart-weekdays").setAttribute("aria-label",
    `Visits by day of the week. Busiest: ${DAY_NAMES[weekdays[hi].day]} (${visits[hi]}). ` +
    `Quietest: ${DAY_NAMES[weekdays[lo].day]} (${visits[lo]}). Full numbers in the table below.`);

  document.getElementById("table-weekdays").innerHTML = tableHTML(
    ["Day", "Visits", "Revenue"],
    weekdays.map((w) => [DAY_NAMES[w.day], plainNumber(w.visits), money(w.revenue)]),
    [1, 2]
  );
}

// "2026-11" → "Nov" (or "Nov 2026" when the period spans more than one year)
function monthName(key, withYear) {
  return new Date(key + "-01T00:00:00").toLocaleDateString("en-IN",
    withYear ? { month: "short", year: "numeric" } : { month: "short" });
}

function renderMonths(months) {
  const years = new Set(months.map((m) => m.month.slice(0, 4)));
  const withYear = years.size > 1;
  const revenue = months.map((m) => m.revenue);
  const colours = months.map((m) => cssColour(m.partial ? "--chart-light" : "--chart-main"));

  // Label the best complete month only (part-months can't fairly be "best").
  const complete = months.map((m, i) => (m.partial ? -1 : m.revenue));
  const best = complete.indexOf(Math.max(...complete));
  const hasBest = best >= 0 && complete[best] > 0;
  const labels = hasBest ? { [best]: compactMoney(revenue[best]) } : {};
  document.getElementById("caption-months").textContent = hasBest
    ? `Best complete month: ${monthName(months[best].month, true)} (${money(revenue[best])})`
    : "No complete month in this period yet.";

  // "1–7 Nov" (part-months are always inside one month)
  const coverage = (m) => {
    const from = new Date(m.covered_from + "T00:00:00"), to = new Date(m.covered_to + "T00:00:00");
    return `${from.getDate()}–${to.getDate()} ${monthName(m.month, false)}`;
  };
  drawChart("months", "chart-months", {
    type: "bar",
    data: {
      // A second line under part-months says so on the axis itself.
      labels: months.map((m) => (m.partial ? [monthName(m.month, withYear), "part"] : monthName(m.month, withYear))),
      datasets: [{ data: revenue, ...barStyle(colours) }],
    },
    options: {
      layout: { padding: { top: 20 } },
      scales: { x: categoryAxis(), y: valueAxis(compactMoney) },
      plugins: {
        valueLabels: { labels },
        tooltip: {
          callbacks: {
            title: (items) => monthName(months[items[0].dataIndex].month, true),
            label: (item) => money(item.raw),
            footer: (items) => {
              const m = months[items[0].dataIndex];
              return [`${m.visits} visits`].concat(m.partial ? [`Part month: ${coverage(m)}`] : []);
            },
          },
        },
      },
    },
  });
  document.getElementById("chart-months").setAttribute("aria-label",
    "Monthly revenue. " + months.map((m) => `${monthName(m.month, true)}: ${money(m.revenue)}` +
      (m.partial ? " (part month)" : "")).join("; ") + ".");

  document.getElementById("table-months").innerHTML = tableHTML(
    ["Month", "Revenue", "Visits", "Covers"],
    months.map((m) => [monthName(m.month, true), money(m.revenue), plainNumber(m.visits),
                       m.partial ? "part: " + coverage(m) : "whole month"]),
    [1, 2]
  );
}

function renderServices() {
  const measure = SERVICE_MEASURES[dash.measure];
  document.getElementById("service-measures").innerHTML = chipsHTML(
    Object.entries(SERVICE_MEASURES).map(([key, m]) => ({ key, label: m.label })), dash.measure, "measure");
  document.getElementById("service-hint").textContent = measure.hint;

  // Rank by the chosen measure, biggest first.
  const services = [...dash.data.services].sort((a, b) => b[dash.measure] - a[dash.measure]);
  const values = services.map((s) => s[dash.measure]);
  const format = measure.money ? money : plainNumber;

  // Height grows with the number of services, so bars never get squashed.
  document.getElementById("services-box").style.height = `${services.length * 34 + 40}px`;

  drawChart("services", "chart-services", {
    type: "bar",
    data: {
      labels: services.map((s) => s.service),
      datasets: [{ data: values, ...barStyle(cssColour("--chart-main")) }],
    },
    options: {
      indexAxis: "y", // horizontal bars: long service names stay readable
      layout: { padding: { right: 70 } }, // room for the top bar's label
      scales: {
        y: { grid: { display: false }, border: { color: cssColour("--chart-axis") },
             ticks: { color: cssColour("--text") } },
        x: valueAxis(measure.money ? compactMoney : plainNumber),
      },
      plugins: {
        valueLabels: { labels: { 0: format(values[0]) } }, // label the leader only
        tooltip: {
          callbacks: {
            label: (item) => format(item.raw) + (dash.measure === "count" ? " times" : ""),
            footer: (items) => {
              const s = services[items[0].dataIndex];
              return [`${money(s.revenue)} total`, `${s.count} times`, `${money(s.avg_price)} average`]
                .filter((_, i) => ["revenue", "count", "avg_price"][i] !== dash.measure);
            },
          },
        },
      },
    },
  });
  document.getElementById("chart-services").setAttribute("aria-label",
    `Services ranked by ${measure.label.toLowerCase()}. Top: ${services[0].service} (${format(values[0])}). ` +
    "Full numbers in the table below.");

  document.getElementById("table-services").innerHTML = tableHTML(
    ["Service", "Revenue", "Times done", "Avg per visit"],
    services.map((s) => [s.service, money(s.revenue), plainNumber(s.count), money(s.avg_price)]),
    [1, 2, 3]
  );
}

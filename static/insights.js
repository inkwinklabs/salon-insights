// The "AI Insights" tab: the insights button, the "what will be sent" preview,
// and WhatsApp reminders for overdue regulars.
//
// PRIVACY: the server only sends NUMBERS to the AI. Customer names are put
// into the reminder message right here in the browser, on this laptop.

const ins = {
  reminders: null,        // answer from /api/reminders
  savedTemplate: "",      // the template before the owner's edits
};

const PRIORITY_LABELS = { high: "High priority", medium: "Worth doing", low: "Good to know" };

// ================================================================ insights

function showInsightsStatus(text, kind) {
  const box = document.getElementById("insights-status");
  box.textContent = text;
  box.className = "form-message " + (kind || "");
  box.hidden = !text;
}

function renderInsights(result) {
  const box = document.getElementById("insights-result");
  box.hidden = !result;
  if (!result) return;
  document.getElementById("insights-headline").textContent = result.headline;
  document.getElementById("insights-list").innerHTML = result.insights
    .map(
      (i) => `<li class="insight insight-${escapeHTML(i.priority)}">
        <div class="insight-top">
          <h3>${escapeHTML(i.title)}</h3>
          <span class="badge badge-priority-${escapeHTML(i.priority)}">${escapeHTML(PRIORITY_LABELS[i.priority] || i.priority)}</span>
        </div>
        <p>${escapeHTML(i.finding)}</p>
        <p class="insight-action"><strong>Try this:</strong> ${escapeHTML(i.action)}</p>
      </li>`
    )
    .join("");
  const when = new Date(result.generated_at).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
  });
  document.getElementById("insights-meta").textContent =
    `Written by ${result.model} on ${when}, from ${result.summary_characters_sent.toLocaleString("en-IN")} ` +
    `characters of numbers. AI can make mistakes, so check anything important against the Dashboard.`;
}

async function loadInsightsTab() {
  const [{ result }] = await Promise.all([getJSON("/api/insights"), loadReminders()]);
  renderInsights(result);
  if (!result) showInsightsStatus("No insights yet. Press “Get AI insights” to ask for some.", "");
  else showInsightsStatus("", "");
}
onTabOpen.insights = loadInsightsTab;
dataChangedListeners.push(async () => {
  if (!document.getElementById("screen-insights").hidden) await loadInsightsTab();
});

document.getElementById("btn-insights").addEventListener("click", (e) => {
  const button = e.currentTarget;
  withBusyButton(button, async () => {
    const label = button.textContent;
    button.textContent = "Thinking…";
    showInsightsStatus("Sending the numbers-only summary to the AI…", "");
    try {
      const r = await postJSON("/api/insights");
      if (!r.ok) {
        showInsightsStatus(r.data.error || "Something went wrong. Please try again.", "bad");
        return;
      }
      renderInsights(r.data.result);
      showInsightsStatus(
        r.data.result.template_note || "Done. The AI also wrote a new WhatsApp message below.",
        r.data.result.template_note ? "" : "good"
      );
      await loadReminders(); // pick up the AI's new message template
    } finally {
      button.textContent = label;
    }
  });
});

// "Show exactly what will be sent": fetched fresh each time it's opened.
document.getElementById("preview-box").addEventListener("toggle", async (e) => {
  if (!e.target.open) return;
  const body = document.getElementById("preview-body");
  body.textContent = "Loading…";
  const p = await getJSON("/api/insights/preview");
  body.innerHTML = `
    <p class="${p.passed_privacy_check ? "hint-good" : "field-error"}">
      ${p.passed_privacy_check
        ? "✓ Privacy check passed: no customer names or phone numbers found."
        : "✗ Privacy check failed: this would NOT be sent."}</p>
    <p><strong>Model:</strong> ${escapeHTML(p.model)}</p>
    <p><strong>Instructions sent with it:</strong></p>
    <pre>${escapeHTML(p.instructions)}</pre>
    <p><strong>The salon summary (${p.summary.length.toLocaleString("en-IN")} characters):</strong></p>
    <pre>${escapeHTML(p.summary)}</pre>`;
});

// ================================================================ WhatsApp reminders

async function loadReminders() {
  ins.reminders = await getJSON("/api/reminders");
  ins.savedTemplate = ins.reminders.template;
  document.getElementById("rem-template").value = ins.reminders.template;
  document.getElementById("rem-source").textContent =
    ins.reminders.template_source === "ai" ? "Written by the AI." : "The default message (from settings.toml).";
  document.getElementById("rem-safety").textContent = ins.reminders.mode === "demo"
    ? "Demo mode: these phone numbers start with 5, which no Indian mobile does, so WhatsApp will say " +
      "the number isn't on WhatsApp. No real person can be messaged."
    : "Only message customers who have agreed to hear from the salon on WhatsApp. " +
      "Each link opens WhatsApp with the message filled in; you still press Send yourself.";
  renderReminders();
}

// Fill the blanks for one customer. This runs in the browser: names never go to the AI.
function fillTemplate(template, customer) {
  const blanks = {
    name: customer.name.split(" ")[0],                  // first name only, friendlier
    service: customer.usual_service.toLowerCase(),
    salon: ins.reminders.salon,
    days: String(customer.days_since),
  };
  return template.replace(/\{(\w+)\}/g, (whole, key) => (key in blanks ? blanks[key] : whole));
}

// WhatsApp's click-to-chat link: wa.me/<country code + number>?text=<message>
function whatsappLink(phone, message) {
  return `https://wa.me/91${phone}?text=${encodeURIComponent(message)}`;
}

function templateWarning(template) {
  const blanks = [...template.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
  const unknown = blanks.filter((b) => !["name", "service", "salon", "days"].includes(b));
  if (!template.trim()) return "The message is empty.";
  if (unknown.length) return `Unknown blank: {${unknown[0]}}. It will be sent as typed.`;
  if (!blanks.includes("name")) return "Tip: add {name} so each message greets the customer by name.";
  return "";
}

function renderReminders() {
  const { customers } = ins.reminders;
  const template = document.getElementById("rem-template").value;
  document.getElementById("rem-template-warning").textContent = templateWarning(template);
  document.getElementById("rem-reset").hidden = template === ins.savedTemplate;
  document.getElementById("rem-count").textContent = customers.length ? `(${customers.length} overdue)` : "";
  document.getElementById("rem-empty").hidden = customers.length > 0;

  document.getElementById("rem-list").innerHTML = customers
    .map((c) => {
      const message = fillTemplate(template, c);
      const sent = c.last_reminder
        ? `<span class="badge badge-regular">WhatsApp opened ${escapeHTML(niceDate(c.last_reminder.slice(0, 10)))}</span>`
        : "";
      return `<li class="rem-item">
        <div class="rem-head">
          <div>
            <strong>${escapeHTML(c.name)}</strong> <span class="phone muted">${escapeHTML(c.phone)}</span>
            <div class="sub">${escapeHTML(c.usual_service)} · last came ${c.days_since} days ago
              (usually every ${c.avg_gap} days) · ${c.visits} visits</div>
          </div>
          <div class="rem-buttons">
            ${sent}
            <a class="btn btn-whatsapp" href="${escapeHTML(whatsappLink(c.phone, message))}"
               target="_blank" rel="noopener noreferrer" data-id="${c.id}">Open WhatsApp</a>
          </div>
        </div>
        <p class="rem-message">${escapeHTML(message)}</p>
      </li>`;
    })
    .join("");
}

document.getElementById("rem-template").addEventListener("input", renderReminders);
document.getElementById("rem-reset").addEventListener("click", () => {
  document.getElementById("rem-template").value = ins.savedTemplate;
  renderReminders();
});

// When a WhatsApp link is opened, remember it (the link itself still opens normally).
document.getElementById("rem-list").addEventListener("click", async (e) => {
  const link = e.target.closest(".btn-whatsapp");
  if (!link) return;
  await postJSON(`/api/reminders/${link.dataset.id}/opened`);
  const customer = ins.reminders.customers.find((c) => c.id === Number(link.dataset.id));
  if (customer) customer.last_reminder = new Date().toISOString().slice(0, 10);
  renderReminders();
});

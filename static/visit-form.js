// The "Log visit" form.
//
// Flow: type the phone → we check if they're a returning customer → pick a
// service (price fills in) → Save. The server checks everything again.

const form = document.getElementById("visit-form");
const phoneInput = document.getElementById("f-phone");
const nameInput = document.getElementById("f-name");
const serviceSelect = document.getElementById("f-service");
const priceInput = document.getElementById("f-price");
const dateInput = document.getElementById("f-date");
const staffSelect = document.getElementById("f-staff");
const phoneHint = document.getElementById("phone-hint");
const formMessage = document.getElementById("form-message");

// ---- Fill the dropdowns from settings.toml ----
function setUpForm() {
  const { services, salon } = app.settings;
  serviceSelect.innerHTML =
    `<option value="">Choose a service…</option>` +
    services
      .map((s) => `<option value="${escapeHTML(s.name)}">${escapeHTML(s.name)} (${money(s.price)})</option>`)
      .join("");
  staffSelect.innerHTML =
    `<option value="">Who did it?</option>` +
    salon.staff.map((name) => `<option>${escapeHTML(name)}</option>`).join("");
  dateInput.value = todayISO();
  dateInput.max = todayISO(); // no future dates
  updatePhonePlaceholder();
}
startUpSteps.push(setUpForm);

// In demo mode, remind people to use a fake number starting with 5.
function updatePhonePlaceholder() {
  phoneInput.placeholder = app.mode === "demo" ? "Demo: 10 digits starting with 5" : "10-digit mobile";
}
dataChangedListeners.push(async () => {
  updatePhonePlaceholder();
  await lookUpPhone(); // the same number may or may not exist in the other mode
});

// ---- Picking a service fills in its usual price ----
serviceSelect.addEventListener("change", () => {
  const service = app.settings.services.find((s) => s.name === serviceSelect.value);
  if (service) {
    priceInput.value = service.price;
    // The price is now filled in, so its old message no longer applies.
    priceInput.dispatchEvent(new Event("input", { bubbles: true }));
  }
});

// ---- Returning customer? Check once 10 digits are typed ----
// Keep only digits, and drop a +91 or leading 0, just like the server does.
function phoneDigits(raw) {
  let digits = raw.replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return digits;
}

let lastLookup = "";
async function lookUpPhone() {
  const digits = phoneDigits(phoneInput.value);
  if (digits.length !== 10) {
    lastLookup = "";
    setReturningCustomer(null);
    return;
  }
  lastLookup = digits;
  const result = await getJSON("/api/customers/lookup?phone=" + digits);
  if (lastLookup !== digits) return; // they kept typing; ignore this old answer
  setReturningCustomer(result.found ? result : null, true);
}
phoneInput.addEventListener("input", lookUpPhone);

// A returning customer's name is filled in and locked, so a mistyped number
// can't rename someone else. A new customer's name can be typed.
function setReturningCustomer(customer, checked = false) {
  const wasLocked = nameInput.readOnly;
  if (customer) {
    nameInput.value = customer.name;
    nameInput.readOnly = true;
    nameInput.dispatchEvent(new Event("input", { bubbles: true })); // clears an old "enter name" message
    phoneHint.textContent =
      `Returning customer · ${customer.visits} visit${customer.visits === 1 ? "" : "s"} · ` +
      `last ${niceDate(customer.last_visit)}. Not them? Check the number.`;
    phoneHint.className = "hint hint-good";
  } else {
    if (wasLocked) nameInput.value = ""; // clear the other customer's name
    nameInput.readOnly = false;
    phoneHint.textContent = checked ? "New customer: type their name." : "";
    phoneHint.className = "hint";
  }
}

// ---- Messages next to each field ----
function showFieldErrors(errors = {}) {
  form.querySelectorAll(".field-error").forEach((el) => {
    const message = errors[el.dataset.errorFor] || "";
    el.textContent = message;
    el.closest(".field").classList.toggle("has-error", Boolean(message));
  });
  // Put the cursor on the first field with a problem.
  const first = form.querySelector(".has-error input, .has-error select");
  if (first) first.focus();
}

// As soon as someone fixes a field, remove its old message.
function clearFieldError(event) {
  const field = event.target.closest(".field");
  if (!field) return;
  field.classList.remove("has-error");
  const error = field.querySelector(".field-error");
  if (error) error.textContent = "";
  // Everything fixed? Then the "please fix" box can go too.
  if (!form.querySelector(".has-error") && formMessage.classList.contains("bad")) {
    showFormMessage("", "");
  }
}
form.addEventListener("input", clearFieldError);
form.addEventListener("change", clearFieldError);

function showFormMessage(text, kind) {
  formMessage.textContent = text;
  formMessage.className = "form-message " + kind;
  formMessage.hidden = !text;
}

// ---- Save ----
form.addEventListener("submit", async (event) => {
  event.preventDefault(); // stay on this page; we'll send the data ourselves
  showFormMessage("", "");
  const button = form.querySelector("button[type=submit]");

  const visit = Object.fromEntries(new FormData(form)); // {phone, name, service, ...}
  await withBusyButton(button, async () => {
    const result = await postJSON("/api/visits", visit);
    if (!result.ok) {
      showFieldErrors(result.data.errors || {});
      showFormMessage("Please fix the highlighted fields.", "bad");
      return;
    }
    showFieldErrors({});
    const r = result.data;
    showFormMessage(
      `Saved: ${visit.service} for ${r.name}, ${money(visit.price)}` +
        (r.new_customer ? " (new customer added)." : "."),
      "good"
    );
    // Clear the customer details but keep date and staff, since several
    // visits are often logged in a row.
    phoneInput.value = "";
    nameInput.value = "";
    serviceSelect.value = "";
    priceInput.value = "";
    setReturningCustomer(null);
    phoneInput.focus();
    await dataChanged();
  });
});

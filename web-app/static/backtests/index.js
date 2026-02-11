function setCookie(name, value, days) {
  const expires = days
    ? "; expires=" + new Date(Date.now() + days * 864e5).toUTCString()
    : "";
  document.cookie = name + "=" + encodeURIComponent(value) + expires + "; path=/";
}

function getCookie(name) {
  const prefix = name + "=";
  const parts = document.cookie.split(";").map(s => s.trim());
  for (const p of parts) {
    if (p.startsWith(prefix)) return decodeURIComponent(p.slice(prefix.length));
  }
  return null;
}

function formToValues(form) {
  const values = {};
  const fd = new FormData(form);
  for (const [k, v] of fd.entries()) {
    if (k === "csrfmiddlewaretoken") continue;
    values[k] = v;
  }

  // Ensure unchecked checkboxes are recorded as false
  form.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    values[cb.name] = cb.checked;
  });
  return values;
}

function applyValuesToForm(form, values) {
  if (!values) return;
  for (const [k, v] of Object.entries(values)) {
    const el = form.elements.namedItem(k);
    if (!el) continue;

    if (el.type === "checkbox") {
      el.checked = !!v;
    } else {
      el.value = v;
    }
  }
}

async function fetchJson(url, opts) {
  const method = (opts && opts.method ? String(opts.method) : "GET").toUpperCase();
  const csrfToken = getCookie("csrftoken");
  const headers = { "Accept": "application/json", ...(opts && opts.headers ? opts.headers : {}) };
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS" && csrfToken) {
    headers["X-CSRFToken"] = csrfToken;
  }
  const res = await fetch(url, {
    headers,
    credentials: "same-origin",
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function loadPresetNames(selectEl) {
  const data = await fetchJson("/api/presets/");
  const names = data.presets || [];
  selectEl.innerHTML = `<option value="">(select preset)</option>` + names.map(n => `<option value="${n}">${n}</option>`).join("");
}

async function main() {
  const form = document.getElementById("backtestForm");
  const presetSelect = document.getElementById("presetSelect");
  const presetNameInput = document.getElementById("presetName");
  const saveBtn = document.getElementById("savePresetBtn");
  const loadBtn = document.getElementById("loadPresetBtn");

  // Cookie restore (overrides server-side initial values)
  try {
    const raw = getCookie("bt_params");
    if (raw) {
      const values = JSON.parse(raw);
      applyValuesToForm(form, values);
    }
  } catch (e) {
    // ignore
  }

  // Presets
  await loadPresetNames(presetSelect);

  loadBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    const name = presetSelect.value;
    if (!name) return;
    const data = await fetchJson(`/api/presets/${encodeURIComponent(name)}/`);
    applyValuesToForm(form, data.values);
  });

  saveBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    const name = (presetNameInput.value || "").trim();
    if (!name) return;
    const values = formToValues(form);
    await fetchJson("/api/presets/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, values }),
    });
    presetNameInput.value = "";
    await loadPresetNames(presetSelect);
    presetSelect.value = name;
  });

  // Save current values to cookie when user runs backtest
  form.addEventListener("submit", () => {
    const values = formToValues(form);
    try {
      setCookie("bt_params", JSON.stringify(values), 30);
    } catch (e) {
      // ignore cookie size errors
    }
  });
}

main().catch((e) => {
  const el = document.getElementById("presetError");
  if (el) el.textContent = String(e);
});


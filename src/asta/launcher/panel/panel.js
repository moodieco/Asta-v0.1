const $ = (sel) => document.querySelector(sel);
const MARKETS = ["forex", "crypto", "stock"];
const MARKET_LABEL = { forex: "Forex", crypto: "Crypto", stock: "Stocks" };
const STEP_TITLE = [
  "Step 1 of 5 · Discord channels",
  "Step 2 of 5 · Data providers",
  "Step 3 of 5 · Markets & scanners",
  "Step 4 of 5 · Local system",
  "Step 5 of 5 · Validate & save",
];

let setupContext = null;
let step = 0;
let webhookValues = { forex: "", crypto: "", stock: "" };
let scannerState = {};
let providerResults = null;

async function api(path, body) {
  const options = { headers: { "X-ASTA-Panel": "1" } };
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function fmtUptime(seconds) {
  if (!seconds) return "—";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${s}s`;
}

/* ---------------- status ---------------- */
async function refresh() {
  try {
    const data = await api("/api/launcher/status");
    const sup = data.supervisor || {};
    const health = sup.health || {};
    const running = Boolean(sup.running);

    const pill = $("#state-pill");
    pill.textContent = running ? "● Running" : "● Stopped";
    pill.className = "pill " + (running ? "up" : "down");

    $("#s-pid").textContent = sup.pid || health.pid || "—";
    $("#s-url").textContent = sup.url || "—";
    $("#s-uptime").textContent = fmtUptime(health.uptimeSeconds);
    $("#s-scanners").textContent = health.scanners
      ? `${health.enabledScanners ?? "—"} enabled / ${health.scanners}`
      : "—";
    const signals = (health.database || {}).signals ?? "—";
    const records = (health.storage || {}).records ?? "—";
    $("#s-signals").textContent = `${signals} (${records} records)`;
    $("#s-cycle").textContent = health.lastCycleAt
      ? `${String(health.lastCycleAt).slice(0, 19).replace("T", " ")} · ${health.cycles ?? "—"} cycles`
      : "—";

    $("#btn-start").disabled = running;
    $("#btn-stop").disabled = !running;
    $("#btn-restart").disabled = !running;
    $("#btn-open").disabled = !running;
    $("#btn-setup").textContent = data.setupComplete ? "⚙ Settings" : "⚙ Quick Setup";
    $("#footer").textContent = `config ${data.config.root}/config · log ${data.config.logPath || "—"}`;
  } catch (error) {
    $("#state-pill").textContent = "● Panel error";
    $("#state-pill").className = "pill down";
    $("#footer").textContent = String(error);
  }
  refreshLog();
}

async function refreshLog() {
  try {
    const data = await api("/api/launcher/log");
    const lines = data.lines || [];
    const log = $("#log");
    const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 4;
    log.textContent = lines.length ? lines.join("\n") : "no dashboard log yet";
    if (atBottom) log.scrollTop = log.scrollHeight;
  } catch {
    /* panel keeps running on log errors */
  }
}

async function action(path, button) {
  if (button) button.disabled = true;
  $("#state-pill").textContent = "● Working…";
  $("#state-pill").className = "pill busy";
  try {
    const data = await api(path, {});
    const result = data.result || data;
    if (result && result.started === false && result.error) {
      alert(`Start failed: ${result.error}`);
    }
  } catch (error) {
    alert(String(error));
  } finally {
    if (button) button.disabled = false;
    refresh();
  }
}

/* ---------------- wizard ---------------- */
function openSetup() {
  $("#setup").classList.remove("hidden");
  loadSetup();
}

function closeSetup() {
  $("#setup").classList.add("hidden");
}

async function loadSetup() {
  $("#setup-status").textContent = "loading…";
  setupContext = await api("/api/launcher/setup");
  $("#setup-title").textContent = setupContext.state.complete ? "Settings" : "Quick Setup";
  webhookValues = { forex: "", crypto: "", stock: "" };
  renderWebhooks();
  renderProviders();
  renderScanners();
  renderSystem();
  $("#review").textContent = "";
  step = 0;
  showStep(0);
  $("#setup-status").textContent = "";
}

function renderWebhooks() {
  const host = $("#webhook-rows");
  host.innerHTML = "";
  MARKETS.forEach((market) => {
    const info = setupContext.webhooks[market] || {};
    const row = document.createElement("div");
    row.className = "webhook-row";
    row.innerHTML = `
      <div class="row-head">
        <strong>${MARKET_LABEL[market]}</strong>
        <div class="row-actions">
          <button class="btn" data-test="${market}">Test</button>
        </div>
      </div>
      <input type="password" data-webhook="${market}" placeholder="${
        info.configured ? `saved ${info.masked} — leave empty to keep` : "https://discord.com/api/webhooks/…"
      }" />
      <div class="state ${info.configured ? "ok" : ""}" data-state="${market}">${
        info.configured ? `✓ saved ${info.masked}` : "not configured"
      }</div>`;
    host.appendChild(row);
  });
  host.querySelectorAll("[data-test]").forEach((button) => {
    button.addEventListener("click", () => testWebhook(button.dataset.test));
  });
  host.querySelectorAll("[data-webhook]").forEach((input) => {
    input.addEventListener("input", () => {
      webhookValues[input.dataset.webhook] = input.value.trim();
    });
  });
}

async function testWebhook(market) {
  const state = document.querySelector(`[data-state="${market}"]`);
  state.textContent = "testing…";
  state.className = "state";
  try {
    const payload = await api("/api/launcher/setup/validate", {
      webhooks: { [market]: webhookValues[market] },
      system: { port: Number($("#port").value || 4310) },
    });
    const item = (payload.results.webhooks || []).find((entry) =>
      entry.label.toLowerCase().includes(MARKET_LABEL[market].toLowerCase()) ||
      (market === "stock" && entry.label.toLowerCase().includes("discord")),
    );
    const result = item || (payload.results.webhooks || [])[0];
    state.textContent = `${result.ok ? "✓" : "✗"} ${result.detail}`;
    state.className = "state " + (result.ok ? "ok" : "bad");
  } catch (error) {
    state.textContent = `✗ ${error}`;
    state.className = "state bad";
  }
}

function renderProviders() {
  const grid = $("#provider-grid");
  grid.innerHTML = "";
  ["forex", "crypto", "stock"].forEach((market) => {
    const info = setupContext.providers[market] || {};
    const row = document.createElement("div");
    row.className = "provider-row";
    row.innerHTML = `<div><strong>${MARKET_LABEL[market]}</strong></div><span class="type">${info.type || "—"}</span>`;
    grid.appendChild(row);
  });
  $("#mt5-url").value = setupContext.providers.forex.terminalUrl || "";
  $("#mt5-token").value = "";
  $("#mt5-token").placeholder = setupContext.providers.forex.tokenConfigured
    ? "saved — leave empty to keep"
    : "optional";
  $("#provider-results").innerHTML = "";
}

async function testProviders() {
  const list = $("#provider-results");
  list.innerHTML = "<li>testing…</li>";
  try {
    const payload = await api("/api/launcher/setup/validate", {
      mt5: { url: $("#mt5-url").value.trim(), token: $("#mt5-token").value.trim() },
      system: { port: Number($("#port").value || 4310), dbPath: $("#db-path").value.trim() },
    });
    list.innerHTML = "";
    (payload.results.providers || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = item.ok ? "ok" : "bad";
      li.textContent = `${item.ok ? "✓" : "✗"} ${item.label} — ${item.detail}`;
      list.appendChild(li);
    });
  } catch (error) {
    list.innerHTML = `<li class="bad">✗ ${error}</li>`;
  }
}

function renderScanners() {
  const host = $("#scanner-list");
  host.innerHTML = "";
  scannerState = {};
  (setupContext.scanners || []).forEach((scanner) => {
    scannerState[scanner.id] = scanner.enabled;
    const row = document.createElement("label");
    row.className = "scanner-row";
    row.innerHTML = `
      <input type="checkbox" ${scanner.enabled ? "checked" : ""} data-scanner="${scanner.id}" />
      <span>${scanner.name}</span>
      <small>${scanner.id} · ${scanner.timeframe}</small>`;
    row.querySelector("input").addEventListener("change", (event) => {
      scannerState[scanner.id] = event.target.checked;
    });
    host.appendChild(row);
  });
}

function renderSystem() {
  $("#db-path").value = setupContext.system.dbPath || "";
  $("#host").value = setupContext.system.host || "127.0.0.1";
  $("#port").value = setupContext.system.port || 4310;
  $("#open-browser").checked = Boolean(setupContext.system.openBrowser);
}

function showStep(next) {
  step = Math.max(0, Math.min(4, next));
  document.querySelectorAll(".step").forEach((el) => {
    el.classList.toggle("hidden", Number(el.dataset.step) !== step);
  });
  $("#setup-step").textContent = STEP_TITLE[step];
  $("#setup-back").disabled = step === 0;
  $("#setup-next").classList.toggle("hidden", step === 4);
  $("#setup-save").classList.toggle("hidden", step !== 4);
}

async function validateAll() {
  const review = $("#review");
  review.textContent = "running checks…";
  try {
    const payload = await api("/api/launcher/setup/validate", {
      webhooks: webhookValues,
      mt5: { url: $("#mt5-url").value.trim(), token: $("#mt5-token").value.trim() },
      system: {
        dbPath: $("#db-path").value.trim(),
        host: $("#host").value.trim(),
        port: Number($("#port").value || 4310),
      },
    });
    providerResults = payload.results;
    const lines = [];
    const groups = [
      ["webhooks", "Discord"],
      ["providers", "Providers"],
      ["local", "Local system"],
    ];
    groups.forEach(([key, label]) => {
      lines.push(label);
      (payload.results[key] || []).forEach((item) => {
        const mark = item.ok ? "✓" : item.optional ? "–" : "✗";
        lines.push(`   ${mark} ${item.label} — ${item.detail}`);
      });
      lines.push("");
    });
    const configured = Object.entries(webhookValues)
      .filter(([, value]) => value)
      .map(([market]) => market);
    lines.push("Saving:");
    lines.push(`   webhooks: ${configured.length ? configured.join(", ") : "unchanged"}`);
    lines.push(`   scanners enabled: ${Object.values(scannerState).filter(Boolean).length}`);
    lines.push(`   port: ${$("#port").value}`);
    lines.push(`   database: ${$("#db-path").value}`);
    review.textContent = lines.join("\n");
  } catch (error) {
    review.textContent = `validation failed: ${error}`;
  }
}

async function saveSetup() {
  $("#setup-status").textContent = "saving…";
  try {
    const payload = await api("/api/launcher/setup/save", {
      webhooks: webhookValues,
      mt5: { url: $("#mt5-url").value.trim(), token: $("#mt5-token").value.trim() },
      scanners: scannerState,
      system: {
        dbPath: $("#db-path").value.trim(),
        host: $("#host").value.trim(),
        port: Number($("#port").value || 4310),
        openBrowser: $("#open-browser").checked,
      },
      startAfter: $("#start-after").checked,
    });
    $("#setup-status").textContent = "saved";
    closeSetup();
    refresh();
    if (payload.started && payload.started.error) {
      alert(`Saved, but ASTA did not start: ${payload.started.error}`);
    }
  } catch (error) {
    $("#setup-status").textContent = String(error);
  }
}

/* ---------------- wiring ---------------- */
$("#btn-start").addEventListener("click", (e) => action("/api/launcher/start", e.currentTarget));
$("#btn-stop").addEventListener("click", (e) => {
  if (confirm("Stop the scanner and the dashboard?")) action("/api/launcher/stop", e.currentTarget);
});
$("#btn-restart").addEventListener("click", (e) => action("/api/launcher/restart", e.currentTarget));
$("#btn-open").addEventListener("click", async () => {
  try {
    const data = await api("/api/launcher/open", {});
    if (!data.opened) alert("The dashboard is not answering yet.");
  } catch (error) {
    alert(String(error));
  }
});
$("#btn-refresh").addEventListener("click", refresh);
$("#btn-setup").addEventListener("click", openSetup);
$("#setup-close").addEventListener("click", closeSetup);
$("#setup-back").addEventListener("click", () => showStep(step - 1));
$("#setup-next").addEventListener("click", () => showStep(step + 1));
$("#btn-validate-providers").addEventListener("click", testProviders);
$("#btn-validate").addEventListener("click", validateAll);
$("#setup-save").addEventListener("click", saveSetup);

refresh();
setInterval(refresh, 2500);
if (new URLSearchParams(location.search).has("setup")) openSetup();

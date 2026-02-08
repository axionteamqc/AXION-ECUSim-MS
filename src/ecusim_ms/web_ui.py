"""Minimal local web UI for Android/Termux (Flask)."""

from __future__ import annotations

from flask import Flask, jsonify, render_template_string, request

from ecusim_ms.ui_backend import UiBackend

app = Flask(__name__)
backend = UiBackend()


INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>ECU Simulator (Web)</title>
    <style>
      :root {
        --bg: #0f1218;
        --panel: #161b22;
        --text: #f2f4f8;
        --muted: #9aa4b2;
        --accent: #4da3ff;
      }
      body { margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }
      header { position: sticky; top: 0; background: var(--panel); padding: 12px 16px; z-index: 10; }
      h1 { font-size: 18px; margin: 0 0 6px 0; }
      .row { display: flex; gap: 8px; flex-wrap: wrap; }
      select, input, button { font-size: 16px; padding: 10px; border-radius: 8px; border: 1px solid #2b3442; background: #0f141c; color: var(--text); }
      button { background: var(--accent); border: none; color: #0b0f14; font-weight: 600; flex: 1; min-width: 120px; }
      .btn-secondary { background: #2b3442; color: var(--text); }
      .btn-start { background: #1fbf75; color: #08150f; }
      .btn-stop { background: #ff4d4f; color: #1b0c0c; }
      .btn-disabled { background: #2b3442; color: var(--text); opacity: 0.7; }
      button:disabled { cursor: not-allowed; }
      .container { padding: 12px 16px 80px 16px; }
      .card { background: var(--panel); border: 1px solid #222a35; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
      .meta { color: var(--muted); font-size: 12px; }
      .signals { display: grid; gap: 8px; }
      .signal { display: grid; gap: 6px; }
      .signal-controls { display: grid; gap: 8px; }
      .range-row { display: grid; grid-template-columns: 1fr 96px; gap: 8px; align-items: center; }
      .range-row input[type="range"] { width: 100%; }
      .toggle-row { display: flex; align-items: center; gap: 6px; }
      .unit { font-size: 12px; color: var(--muted); }
      .sticky-actions { position: sticky; bottom: 0; background: var(--bg); padding: 10px 16px; border-top: 1px solid #222a35; }
      .status { font-size: 13px; color: var(--muted); margin-top: 6px; }
      .status-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
      .badge { font-size: 12px; padding: 4px 8px; border-radius: 999px; font-weight: 600; }
      .badge-running { background: #1fbf75; color: #08150f; }
      .badge-stopped { background: #2b3442; color: var(--text); }
      .badge-disconnected { background: #ff9f1c; color: #241200; }
      .badge-apply-ok { background: #1fbf75; color: #08150f; }
      .badge-apply-fail { background: #ff4d4f; color: #1b0c0c; }
      .apply-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
      .apply-note { font-size: 12px; color: var(--muted); }
      .apply-note-warn { color: #ff9f1c; }
      .last-action { font-size: 12px; color: var(--muted); margin-top: 4px; }
      .connection-message { font-size: 12px; color: #ff9f1c; }
      .badge-ok { background: #1fbf75; color: #08150f; }
      .badge-warn { background: #ff9f1c; color: #241200; }
      .badge-bad { background: #ff4d4f; color: #1b0c0c; }
      .badge-idle { background: #2b3442; color: var(--text); }
      .live-panel { background: var(--panel); border: 1px solid #222a35; border-radius: 10px; padding: 8px; margin-top: 10px; }
      .live-header { display: grid; gap: 6px; }
      .live-title { font-size: 14px; font-weight: 600; }
      .live-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
      .live-table { display: grid; gap: 4px; max-height: 220px; overflow-y: auto; }
      .live-row { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 0.7fr); gap: 6px; align-items: center; }
      .live-cell { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
      .live-header-row .live-cell { color: var(--muted); font-weight: 600; }
      .badge-ready { background: #1fbf75; color: #08150f; }
      .badge-not-detected { background: #ff4d4f; color: #1b0c0c; }
      .badge-not-ready { background: #ff9f1c; color: #241200; }
      .device-status { margin-top: 8px; display: grid; gap: 4px; }
      .device-row { display: flex; align-items: center; gap: 8px; }
      .device-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
      .device-error { color: #ff9f1c; font-size: 12px; }
    </style>
  </head>
  <body>
    <header>
      <h1>ECU Simulator (Web)</h1>
      <div class="row">
        <select id="mode"></select>
        <input id="filter" placeholder="Filter signals"/>
      </div>
      <div class="device-status">
        <div class="device-row">
          <span class="device-label">Device status</span>
          <span id="deviceBadge" class="badge badge-not-ready">USB: ...</span>
        </div>
        <div id="deviceMeta" class="meta">Backend: ... | Port: ...</div>
        <div id="deviceError" class="device-error"></div>
        <div id="connectionMessage" class="connection-message"></div>
      </div>
    </header>
    <div class="container">
      <div id="signals" class="signals"></div>
    </div>
    <div class="sticky-actions">
      <div class="row">
        <button id="applyBtn" class="btn-secondary">Apply Custom</button>
        <button id="applyRestartBtn" class="btn-secondary" style="display:none;">Apply & Restart</button>
      </div>
      <div class="row">
        <button id="startBtn" class="btn-start">Start</button>
        <button id="stopBtn" class="btn-stop">Stop</button>
      </div>
      <div class="status-row">
        <span id="runBadge" class="badge badge-stopped">● STOPPED</span>
        <span id="status" class="status">Status: ...</span>
      </div>
      <div class="apply-row">
        <span id="applyBadge" class="badge badge-stopped">Apply status: idle</span>
        <span id="applyNote" class="apply-note"></span>
      </div>
      <div class="last-action">
        <span id="lastAction" class="status">Last action: -</span>
      </div>
      <div class="live-panel">
        <div class="live-header">
          <div class="live-title">Live Data</div>
          <div class="live-meta">
            <span id="telemetryErrors" class="meta">Errors: 0</span>
            <span id="telemetryConnected" class="badge badge-idle">Connected</span>
            <span id="telemetryReady" class="badge badge-idle">Ready</span>
            <span id="telemetryRunning" class="badge badge-idle">Running</span>
          </div>
        </div>
        <div id="telemetryTable" class="live-table"></div>
        <div id="telemetryUnavailable" class="meta" style="display:none;">Telemetry unavailable</div>
      </div>
    </div>
    <script>
      let signals = [];
      const currentValues = {};
      const schemaByKey = {};
      let applyTimer = null;
      const modeEl = document.getElementById("mode");
      const filterEl = document.getElementById("filter");
      const signalsEl = document.getElementById("signals");
      const statusEl = document.getElementById("status");
      const badgeEl = document.getElementById("runBadge");
      const applyBadgeEl = document.getElementById("applyBadge");
      const applyBtn = document.getElementById("applyBtn");
      const startBtn = document.getElementById("startBtn");
      const stopBtn = document.getElementById("stopBtn");
      const deviceBadgeEl = document.getElementById("deviceBadge");
      const deviceMetaEl = document.getElementById("deviceMeta");
      const deviceErrorEl = document.getElementById("deviceError");
      const connectionMessageEl = document.getElementById("connectionMessage");
      const applyRestartBtn = document.getElementById("applyRestartBtn");
      const applyNoteEl = document.getElementById("applyNote");
      const lastActionEl = document.getElementById("lastAction");
      const telemetryErrorsEl = document.getElementById("telemetryErrors");
      const telemetryConnectedEl = document.getElementById("telemetryConnected");
      const telemetryReadyEl = document.getElementById("telemetryReady");
      const telemetryRunningEl = document.getElementById("telemetryRunning");
      const telemetryTableEl = document.getElementById("telemetryTable");
      const telemetryUnavailableEl = document.getElementById("telemetryUnavailable");
      let controlsDisabled = false;
      let lastRunning = false;
      let lastStatus = null;

      function fetchJson(url, opts) {
        return fetch(url, opts).then(r => r.json());
      }

      function setControlsDisabled(disabled) {
        controlsDisabled = disabled;
        modeEl.disabled = disabled;
        filterEl.disabled = disabled;
        applyBtn.disabled = disabled;
        applyRestartBtn.disabled = disabled;
        startBtn.disabled = disabled;
        stopBtn.disabled = disabled;
        renderSignals();
      }

      function setLastAction(action, ok, detail) {
        const ts = new Date().toLocaleTimeString();
        const suffix = detail ? ` - ${detail}` : "";
        lastActionEl.textContent = `Last action: ${action} @ ${ts}${suffix}`;
      }

      function setBadge(el, text, state) {
        el.textContent = text;
        if (state === "ok") {
          el.className = "badge badge-ok";
        } else if (state === "warn") {
          el.className = "badge badge-warn";
        } else if (state === "bad") {
          el.className = "badge badge-bad";
        } else {
          el.className = "badge badge-idle";
        }
      }

      function truncateText(text, maxLen) {
        if (!text) {
          return "";
        }
        if (text.length <= maxLen) {
          return text;
        }
        const ellipsis = "...";
        return text.slice(0, Math.max(0, maxLen - ellipsis.length)) + ellipsis;
      }

      function formatRaw(raw) {
        if (!raw) {
          return "";
        }
        const clean = String(raw).replace(/\s+/g, "").toUpperCase();
        const parts = clean.match(/.{1,2}/g) || [];
        return parts.join(" ");
      }

      function formatHumanValue(value) {
        if (typeof value === "number" && Number.isFinite(value)) {
          const abs = Math.abs(value);
          if (abs >= 1000) {
            return value.toFixed(0);
          }
          if (abs >= 100) {
            return value.toFixed(1);
          }
          return value.toFixed(2);
        }
        return "";
      }

      function renderTelemetryRows(items) {
        telemetryTableEl.innerHTML = "";
        const header = document.createElement("div");
        header.className = "live-row live-header-row";
        header.innerHTML = "<div class='live-cell'>Signal</div><div class='live-cell'>Value</div><div class='live-cell'>Age ms</div>";
        telemetryTableEl.appendChild(header);
        const rows = (items || []).slice(0, 20);
        for (const row of rows) {
          const line = document.createElement("div");
          line.className = "live-row";
          const name = document.createElement("div");
          name.className = "live-cell";
          const key = row.key || row.name || "";
          const schema = schemaByKey[key] || {};
          const unit = schema.unit || "";
          name.textContent = row.name || key || "";
          const value = document.createElement("div");
          value.className = "live-cell";
          const humanValue = formatHumanValue(row.value);
          const humanFull = humanValue ? (unit ? `${humanValue} ${unit}` : humanValue) : "--";
          const rawText = formatRaw(row.raw);
          const display = unit && humanValue ? humanFull : (rawText || "--");
          value.textContent = truncateText(display, 16);
          const age = document.createElement("div");
          age.className = "live-cell";
          age.textContent = Number.isFinite(row.age_ms) ? String(Math.round(row.age_ms)) : "--";
          line.appendChild(name);
          line.appendChild(value);
          line.appendChild(age);
          const idText = row.arbitration_id || "n/a";
          const tooltipRaw = rawText || "--";
          line.title = `ID: ${idText} | Value: ${humanFull} | Raw: ${tooltipRaw}`;
          telemetryTableEl.appendChild(line);
        }
      }

      function refreshTelemetry() {
        fetchJson("/api/telemetry")
          .then(t => {
            telemetryUnavailableEl.style.display = "none";
            const total = t.error_count_total ?? 0;
            const send = t.errors_send ?? 0;
            const apply = t.errors_apply ?? 0;
            const parse = t.errors_parse ?? 0;
            const device = t.errors_device ?? 0;
            telemetryErrorsEl.textContent = `Errors: ${total} (send ${send}, apply ${apply}, parse ${parse}, device ${device})`;
            renderTelemetryRows(t.signals || []);
            setBadge(telemetryConnectedEl, "Connected", "ok");
            const ready = lastStatus ? !!lastStatus.device_ready : false;
            const running = lastStatus ? !!lastStatus.running : !!t.running;
            setBadge(telemetryReadyEl, "Ready", ready ? "ok" : "warn");
            setBadge(telemetryRunningEl, "Running", running ? "ok" : "idle");
          })
          .catch(() => {
            telemetryTableEl.innerHTML = "";
            telemetryUnavailableEl.style.display = "";
            telemetryErrorsEl.textContent = "Errors: --";
            setBadge(telemetryConnectedEl, "Disconnected", "bad");
            setBadge(telemetryReadyEl, "Ready", "idle");
            setBadge(telemetryRunningEl, "Running", "idle");
          });
      }

      function renderSignals() {
        const q = (filterEl.value || "").toLowerCase();
        signalsEl.innerHTML = "";
        let items = signals.filter(s => !q || s.name.toLowerCase().includes(q));
        for (const s of items) {
          const card = document.createElement("div");
          card.className = "card signal";
          const key = s.key || s.name;
          const title = document.createElement("div");
          title.textContent = s.name || key;
          const meta = document.createElement("div");
          meta.className = "meta";
          const unitText = s.unit ? ` | Unit: ${s.unit}` : "";
          meta.textContent = `CAN ID: ${s.frame_id ? "0x"+s.frame_id.toString(16).toUpperCase() : "n/a"} | Period: ${s.default_period_ms?.toFixed(1) || "n/a"} ms${unitText}`;

          const controls = document.createElement("div");
          controls.className = "signal-controls";

          const minVal = Number.isFinite(s.min) ? s.min : 0;
          const maxVal = Number.isFinite(s.max) ? s.max : 100;
          const stepVal = Number.isFinite(s.step) ? s.step : 1;
          const stored = currentValues[key];
          let value = stored && Number.isFinite(stored.value) ? stored.value : s.default;
          if (!Number.isFinite(value)) {
            value = minVal;
          }
          if (value < minVal) value = minVal;
          if (value > maxVal) value = maxVal;
          const enabled = stored ? !!stored.enabled : true;
          currentValues[key] = {value: value, enabled: enabled};

          const rangeRow = document.createElement("div");
          rangeRow.className = "range-row";
          const slider = document.createElement("input");
          slider.type = "range";
          slider.min = String(minVal);
          slider.max = String(maxVal);
          slider.step = String(stepVal);
          slider.value = String(value);
          const number = document.createElement("input");
          number.type = "number";
          number.min = String(minVal);
          number.max = String(maxVal);
          number.step = String(stepVal);
          number.value = String(value);
          rangeRow.appendChild(slider);
          rangeRow.appendChild(number);

          const toggleRow = document.createElement("div");
          toggleRow.className = "toggle-row";
          const toggle = document.createElement("input");
          toggle.type = "checkbox";
          toggle.checked = enabled;
          toggle.disabled = controlsDisabled;
          const toggleLabel = document.createElement("span");
          toggleLabel.textContent = "Enable";
          toggleRow.appendChild(toggle);
          toggleRow.appendChild(toggleLabel);

          function pushValue(rawVal) {
            if (!Number.isFinite(rawVal)) {
              return;
            }
            let nextVal = rawVal;
            if (nextVal < minVal) nextVal = minVal;
            if (nextVal > maxVal) nextVal = maxVal;
            slider.value = String(nextVal);
            number.value = String(nextVal);
            currentValues[key] = {value: nextVal, enabled: toggle.checked};
            submitUpdate(key, nextVal, toggle.checked);
          }

          slider.addEventListener("input", () => pushValue(parseFloat(slider.value)));
          number.addEventListener("input", () => pushValue(parseFloat(number.value)));
          toggle.addEventListener("change", () => {
            const enabled = toggle.checked;
            slider.disabled = controlsDisabled || !enabled;
            number.disabled = controlsDisabled || !enabled;
            currentValues[key] = {value: parseFloat(number.value), enabled: enabled};
            submitUpdate(key, parseFloat(number.value), enabled);
          });

          slider.disabled = controlsDisabled || !enabled;
          number.disabled = controlsDisabled || !enabled;

          controls.appendChild(rangeRow);
          controls.appendChild(toggleRow);

          card.appendChild(title);
          card.appendChild(meta);
          card.appendChild(controls);
          signalsEl.appendChild(card);
        }
      }

      function submitUpdate(name, value, enabled) {
        fetchJson("/api/updates", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({[name]: {value: value, enabled: enabled}})
        }).then(refreshStatus);
      }

      function showApplyStatus(message, ok) {
        if (applyTimer) {
          clearTimeout(applyTimer);
        }
        applyBadgeEl.textContent = message;
        applyBadgeEl.className = `badge ${ok ? "badge-apply-ok" : "badge-apply-fail"}`;
        applyTimer = setTimeout(() => {
          applyBadgeEl.textContent = "Apply status: idle";
          applyBadgeEl.className = "badge badge-stopped";
        }, 2000);
      }

      function applyAll(restart) {
        if (controlsDisabled) {
          showApplyStatus("Apply failed (disconnected)", false);
          setLastAction("apply", false, "disconnected");
          return;
        }
        applyBadgeEl.textContent = "Applying...";
        applyBadgeEl.className = "badge badge-stopped";
        const wantsRestart = !!restart && lastRunning;
        fetchJson("/api/custom/apply", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(currentValues)
        })
          .then(res => {
            if (!res.ok) {
              const msg = res.error ? `Apply failed: ${res.error}` : "Apply failed";
              showApplyStatus(msg, false);
              setLastAction("apply", false, res.error || "failed");
              return;
            }
            if (!wantsRestart) {
              showApplyStatus("Applied ✓", true);
              setLastAction("apply", true);
              return;
            }
            fetchJson("/api/stop", {method: "POST"})
              .then(() => fetchJson("/api/start", {method: "POST"}))
              .then(() => {
                showApplyStatus("Applied ✓", true);
                setLastAction("apply+restart", true);
                refreshStatus();
              })
              .catch(() => {
                showApplyStatus("Apply failed (restart)", false);
                setLastAction("apply+restart", false, "restart failed");
              });
          })
          .catch(() => {
            showApplyStatus("Apply failed (disconnected)", false);
            setLastAction("apply", false, "disconnected");
          });
      }

      function refreshStatus() {
        fetchJson("/api/status")
          .then(s => {
            if (controlsDisabled) {
              setControlsDisabled(false);
            }
            connectionMessageEl.textContent = "";
            lastStatus = s;
            const running = !!s.running;
            lastRunning = running;
            const statusText = running ? "running" : "stopped";
            statusEl.textContent = `Status: ${statusText} | backend=${s.backend} port=${s.port} bitrate=${s.bitrate}`;
            badgeEl.className = `badge ${running ? "badge-running" : "badge-stopped"}`;
            badgeEl.textContent = running ? "● RUNNING" : "● STOPPED";
            const devicePresent = !!s.device_present;
            const deviceReady = !!s.device_ready;
            if (!devicePresent) {
              deviceBadgeEl.className = "badge badge-not-detected";
              deviceBadgeEl.textContent = "USB: NOT DETECTED";
            } else if (!deviceReady) {
              deviceBadgeEl.className = "badge badge-not-ready";
              deviceBadgeEl.textContent = "USB: DETECTED / NOT READY";
            } else {
              deviceBadgeEl.className = "badge badge-ready";
              deviceBadgeEl.textContent = "USB: READY";
            }
            deviceMetaEl.textContent = `Backend: ${s.backend} | Port: ${s.port}`;
            deviceErrorEl.textContent = s.last_error ? String(s.last_error) : "";
            const canStart = !running && deviceReady;
            startBtn.disabled = !canStart;
            stopBtn.disabled = !running;
            startBtn.classList.toggle("btn-disabled", !canStart);
            stopBtn.classList.toggle("btn-disabled", !running);
            const hotApply = s.hot_apply_supported !== false;
            if (running && !hotApply) {
              applyBtn.disabled = true;
              applyRestartBtn.style.display = "";
              applyRestartBtn.disabled = !deviceReady;
              applyNoteEl.textContent = "Requires restart";
              applyNoteEl.className = "apply-note apply-note-warn";
            } else {
              applyBtn.disabled = false;
              applyRestartBtn.style.display = "none";
              applyNoteEl.textContent = "";
              applyNoteEl.className = "apply-note";
            }
          })
          .catch(() => {
            setControlsDisabled(true);
            connectionMessageEl.textContent = "Backend disconnected";
            statusEl.textContent = "Status: disconnected";
            badgeEl.className = "badge badge-disconnected";
            badgeEl.textContent = "● DISCONNECTED";
            deviceBadgeEl.className = "badge badge-disconnected";
            deviceBadgeEl.textContent = "USB: DISCONNECTED";
            deviceMetaEl.textContent = "Backend: -- | Port: --";
            deviceErrorEl.textContent = "";
            startBtn.disabled = true;
            stopBtn.disabled = true;
            applyBtn.disabled = true;
            applyRestartBtn.disabled = true;
            applyRestartBtn.style.display = "none";
            applyNoteEl.textContent = "";
            applyNoteEl.className = "apply-note";
            startBtn.classList.add("btn-disabled");
            stopBtn.classList.add("btn-disabled");
          });
      }

      fetchJson("/api/modes").then(modes => {
        modeEl.innerHTML = "";
        for (const m of modes) {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = m;
          modeEl.appendChild(opt);
        }
      });
      modeEl.addEventListener("change", () => {
        fetchJson("/api/mode", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({mode: modeEl.value})
        }).then(refreshStatus);
      });
      filterEl.addEventListener("input", renderSignals);
      applyBtn.addEventListener("click", () => applyAll(false));
      applyRestartBtn.addEventListener("click", () => applyAll(true));
      startBtn.addEventListener("click", () => {
        fetchJson("/api/start", {method: "POST"})
          .then(res => {
            if (res.ok) {
              setLastAction("start", true);
            } else {
              setLastAction("start", false, res.error || "failed");
            }
            refreshStatus();
          })
          .catch(() => setLastAction("start", false, "disconnected"));
      });
      stopBtn.addEventListener("click", () => {
        fetchJson("/api/stop", {method: "POST"})
          .then(res => {
            if (res.ok) {
              setLastAction("stop", true);
            } else {
              setLastAction("stop", false, res.error || "failed");
            }
            refreshStatus();
          })
          .catch(() => setLastAction("stop", false, "disconnected"));
      });

      fetchJson("/api/custom/schema").then(data => {
        signals = data;
        for (const s of signals) {
          const key = s.key || s.name;
          if (key) {
            schemaByKey[key] = s;
          }
        }
        for (const s of signals) {
          const key = s.key || s.name;
          if (!Object.prototype.hasOwnProperty.call(currentValues, key)) {
            const minVal = Number.isFinite(s.min) ? s.min : 0;
            const maxVal = Number.isFinite(s.max) ? s.max : 100;
            let value = Number.isFinite(s.default) ? s.default : minVal;
            if (value < minVal) value = minVal;
            if (value > maxVal) value = maxVal;
            currentValues[key] = {value: value, enabled: true};
          }
        }
        renderSignals();
      });
      refreshStatus();
      refreshTelemetry();
      setInterval(refreshStatus, 1000);
      setInterval(refreshTelemetry, 1000);
    </script>
  </body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.get("/api/modes")
def api_modes():
    return jsonify(backend.get_available_modes())


@app.post("/api/mode")
def api_mode():
    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode")
    if mode:
        backend.set_mode(str(mode))
    return jsonify({"ok": True})


@app.get("/api/signals")
def api_signals():
    return jsonify(backend.get_custom_signals_schema_ui())


@app.get("/api/custom/schema")
def api_custom_schema():
    return jsonify(backend.get_custom_signals_schema_ui())


@app.post("/api/updates")
def api_updates():
    updates = request.get_json(silent=True) or {}
    backend.apply_custom_signal_updates(updates)
    return jsonify({"ok": True})


@app.post("/api/custom/apply")
def api_custom_apply():
    updates = request.get_json(silent=True) or {}
    ok, error = backend.apply_custom_payload(updates)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": error})


@app.post("/api/start")
def api_start():
    backend.start()
    return jsonify({"ok": True})


@app.post("/api/stop")
def api_stop():
    backend.stop()
    return jsonify({"ok": True})


@app.get("/api/status")
def api_status():
    return jsonify(backend.get_status())


@app.get("/api/telemetry")
def api_telemetry():
    return jsonify(backend.get_telemetry())


def main() -> None:
    app.run(host="127.0.0.1", port=8000, debug=False)


if __name__ == "__main__":
    main()

class RemkoTimeprogramCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._timeprogram = null;
    this._original_timeprogram = null;
    this._dirty = false;
    this._new_slots = {};
    this._new_time_ranges = {};
    this._collapsed = false;
  }

  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getTheme() {
    const s = getComputedStyle(document.documentElement);
    const g = (v, f) => s.getPropertyValue(v)?.trim() || f;
    return {
      bg: g("--card-background-color", "#fff"),
      text: g("--primary-text-color", "#111"),
      divider: g("--divider-color", "#ccc"),
      primary: g("--primary-color", "#2196F3"),
      success: g("--success-color", "#4CAF50"),
      error: g("--error-color", "#E53935"),
      radius: g("--ha-card-border-radius", "12px"),
      shadow: g("--ha-card-box-shadow", "var(--mdc-elevation-z2)"),
    };
  }

  getCardTitle() {
    if (this.config?.title) {
      return this.config.title;
    }
    if (!this._hass || !this.config?.entity) return "Remko Zeitplan";
    const entity = this._hass.states[this.config.entity];
    return entity?.attributes?.friendly_name || this.config.entity;
  }

  render() {
    if (!this._hass || !this.config?.entity) return;
    const entity = this._hass.states[this.config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = `<ha-card>Entity ${this.config.entity} nicht gefunden.</ha-card>`;
      return;
    }

    if (!this._timeprogram) {
      this._timeprogram = structuredClone(entity.attributes.timeprogram || {});
      this._original_timeprogram = structuredClone(this._timeprogram);
      for (let d of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
        this._new_slots[d] = [];
        this._new_time_ranges[d] = [];
      }
    }

    const theme = this.getTheme();
    const cardTitle = this.getCardTitle();

    this.shadowRoot.innerHTML = `
      <ha-card>
        <style>
          :host {
            display: block;
            color: ${theme.text};
            font-family: "Roboto", sans-serif;
          }
          h2 { margin: 0; font-size: 20px; }
          h3 { margin: 0; font-size: 16px; }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
          }
          .header-title {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
          }
          .collapse-btn {
            background: none;
            border: none;
            cursor: pointer;
            color: var(--secondary-text-color, #999);
            font-size: 20px;
            padding: 4px 8px;
            display: flex;
            align-items: center;
            transition: transform 0.3s ease, color 0.3s ease;
          }
          .collapse-btn:hover {
            color: ${theme.primary};
          }
          .collapse-btn.collapsed {
            transform: rotate(180deg);
          }
          .timeprogram {
            padding: 0 16px 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
          }
          .day {
            background: ${theme.bg};
            border: 1px solid ${theme.divider};
            border-radius: ${theme.radius};
            box-shadow: ${theme.shadow};
            padding: 12px;
            transition: max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease;
            max-height: 1000px;
            opacity: 1;
            overflow: hidden;
          }
          .day.collapsed {
            padding: 8px 12px;
            max-height: 60px;
            opacity: 0.8;
          }
          .day-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            transition: margin-bottom 0.3s ease;
          }
          .day.collapsed .day-header {
            margin-bottom: 0;
          }
          .day-title { flex: 1; }
          .day-count {
            font-size: 12px;
            color: var(--secondary-text-color, #999);
            margin-right: 12px;
          }
          .bar {
            display: flex;
            height: 8px;
            background: ${theme.divider};
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
            transition: margin 0.3s ease;
          }
          .day.collapsed .bar {
            margin: 4px 0;
          }
          .slot { flex: 1; }
          .slot.on { background: ${theme.primary}; }
          .slot.off { background: ${theme.error}; }
          .timeslot {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--ha-card-background, ${theme.bg});
            border: 2px solid ${theme.divider};
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 13px;
            margin-bottom: 6px;
          }
          .timeslot.new-on {
            border-color: ${theme.success};
            background: var(--ha-card-background, ${theme.bg});
          }
          .timeslot.new-off {
            border-color: ${theme.error};
            background: var(--ha-card-background, ${theme.bg});
          }
          .timeslot-content {
            display: flex;
            align-items: center;
            flex: 1;
            gap: 8px;
          }
          .timeslot-time {
            flex: 1;
          }
          .timeslot-actions {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .status {
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            color: white;
          }
          .status.on { background: ${theme.success}; }
          .status.off { background: ${theme.error}; }
          .footer {
            display: flex;
            justify-content: flex-end;
            gap: 8px;
            padding: 8px 16px 16px;
          }
          ha-icon {
            color: var(--secondary-text-color);
            cursor: pointer;
            font-size: 22px;
          }
          ha-icon:hover {
            color: ${theme.primary};
          }
          ha-icon.delete {
            font-size: 20px;
          }
          .day-content {
            display: block;
          }
          .day.collapsed .day-content {
            display: none;
          }
        </style>

        <div class="header">
          <div class="header-title">
            <h2>${cardTitle}</h2>
            ${this._dirty ? `<span style="color: var(--warning-color, orange); font-size: 14px;">● Änderungen</span>` : ""}
          </div>
          <button class="collapse-btn ${this._collapsed ? 'collapsed' : ''}" id="collapse-btn">${this._collapsed ? '▼' : '▲'}</button>
        </div>

        <div class="timeprogram" id="timeprogram">
          ${this.renderDays()}
        </div>

        <div class="footer">
          <ha-button variant="brand" appearance="plain" id="cancel">Abbrechen</ha-button>
          <ha-button variant="brand" appearance="accent" id="save">Speichern</ha-button>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector("#save").addEventListener("click", () => this.saveTimeprogram());
    this.shadowRoot.querySelector("#cancel").addEventListener("click", () => this.cancelTimeprogram());
    this.shadowRoot.querySelector("#collapse-btn").addEventListener("click", () => this.toggleCollapse());
    this.shadowRoot.querySelectorAll(".add").forEach(btn =>
      btn.addEventListener("click", e => this.addTimeslot(e.target.dataset.day))
    );
    this.shadowRoot.querySelectorAll(".delete").forEach(btn =>
      btn.addEventListener("click", e => this.deleteTimeslot(e.target.dataset.day, parseInt(e.target.dataset.index)))
    );
  }

  toggleCollapse() {
    this._collapsed = !this._collapsed;
    const timeprogram = this.shadowRoot.querySelector("#timeprogram");
    const btn = this.shadowRoot.querySelector("#collapse-btn");

    timeprogram.querySelectorAll(".day").forEach(day => {
      if (this._collapsed) {
        day.classList.add("collapsed");
      } else {
        day.classList.remove("collapsed");
      }
    });

    btn.classList.toggle("collapsed");
    btn.textContent = this._collapsed ? '▼' : '▲';
  }

  renderDays() {
    const days = { mon: "Montag", tue: "Dienstag", wed: "Mittwoch", thu: "Donnerstag", fri: "Freitag", sat: "Samstag", sun: "Sonntag" };
    return Object.entries(days)
      .map(([key, label]) => {
        const data = this._timeprogram[key] || { timeslots: [] };
        const sorted = (data.timeslots || []).slice().sort((a, b) => this.timeToMinutes(a.start) - this.timeToMinutes(b.start));

        return `
          <div class="day ${this._collapsed ? 'collapsed' : ''}">
            <div class="day-header">
              <h3 class="day-title">${label}</h3>
              <span class="day-count">${sorted.length}</span>
              <ha-icon icon="mdi:plus-circle-outline" class="add" data-day="${key}"></ha-icon>
            </div>
            <div class="bar">${this.renderBar(sorted)}</div>
            <div class="day-content">
              ${sorted.length > 0
                ? sorted.map((ts, i) => {
                    const isNew = this.isTimeslotNew(key, ts);
                    const borderClass = isNew ? (ts.on ? 'new-on' : 'new-off') : '';
                    return `
                      <div class="timeslot ${borderClass}">
                        <div class="timeslot-content">
                          <span class="timeslot-time">${ts.start} - ${ts.stop}${isNew ? ' 🟢 NEU' : ''}</span>
                        </div>
                        <div class="timeslot-actions">
                          <span class="status ${ts.on ? 'on' : 'off'}">${ts.on ? "ON" : "OFF"}</span>
                          <ha-icon icon="mdi:delete-outline" class="delete" data-day="${key}" data-index="${i}"></ha-icon>
                        </div>
                      </div>
                    `;
                  }).join("")
                : '<div style="color: var(--secondary-text-color, #999); font-size: 13px;">Keine Zeitabschnitte</div>'
              }
            </div>
          </div>`;
      })
      .join("");
  }

  renderBar(timeslots) {
    const slots = Array.from({ length: 96 }, (_, i) => {
      const active = timeslots.find(ts => {
        const s = this.getSlotFromTime(ts.start);
        let e = this.getSlotFromTime(ts.stop);
        if (e === 0) e = 96;
        return i >= s && i < e;
      });
      return `<div class="slot ${active ? (active.on ? "on" : "off") : ""}"></div>`;
    });
    return slots.join("");
  }

  getSlotFromTime(time) {
    const [h, m] = time.split(":").map(Number);
    return h * 4 + m / 15;
  }

  getTimeFromSlot(slot) {
    const hours = Math.floor(slot / 4);
    const minutes = (slot % 4) * 15;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
  }

  isTimeslotNew(day, slot) {
    if (!this._new_slots[day]) return false;
    return this._new_slots[day].some(s =>
      s.start === slot.start && s.stop === slot.stop && s.on === slot.on
    );
  }

  trackNewSlots(day, slot) {
    if (!this._new_slots[day]) this._new_slots[day] = [];
    const exists = this._new_slots[day].some(s =>
      s.start === slot.start && s.stop === slot.stop && s.on === slot.on
    );
    if (!exists) {
      this._new_slots[day].push({ start: slot.start, stop: slot.stop, on: slot.on });
    }
  }

  timeToMinutes(t) {
    const [h, m] = t.split(":").map(Number);
    return h * 60 + m;
  }

  async addTimeslot(day) {
    const start = await this.showTimeDialog("Startzeit wählen", "08:00");
    if (!start) return;
    const stop = await this.showTimeDialog("Endzeit wählen", "12:00", start);
    if (!stop) return;
    const on = await this.showOnOffDialog();
    if (on === null) return;

    if (!this._timeprogram[day]) this._timeprogram[day] = { timeslots: [] };

    const newSlot = { start, stop, on };
    this.trackNewSlots(day, newSlot);

    this._timeprogram[day].timeslots.push(newSlot);
    this._timeprogram[day].timeslots = this.cleanAndMergeTimeprogram(this._timeprogram[day].timeslots);

    this._dirty = true;
    this.render();
  }

  cleanAndMergeTimeprogram(timeslots) {
    if (!timeslots || timeslots.length === 0) return [];

    let sorted = [...timeslots].sort((a, b) => {
      return this.timeToMinutes(a.start) - this.timeToMinutes(b.start);
    });

    let result = [];
    for (let slot of sorted) {
      if (slot.on) {
        result.push(slot);
      } else {
        result = this.applyCut(result, slot);
        result.push(slot);
      }
    }

    result = this.mergeOnlyOn(result);

    result.sort((a, b) => {
      const aStart = this.timeToMinutes(a.start);
      const bStart = this.timeToMinutes(b.start);
      if (aStart === bStart) {
        const aStop = a.stop === "00:00" ? 1440 : this.timeToMinutes(a.stop);
        const bStop = b.stop === "00:00" ? 1440 : this.timeToMinutes(b.stop);
        return aStop - bStop;
      }
      return aStart - bStart;
    });

    return result;
  }

  applyCut(slots, cutSlot) {
    const cutStart = this.timeToMinutes(cutSlot.start);
    const cutStop = this.timeToMinutes(cutSlot.stop);
    const result = [];

    for (let slot of slots) {
      if (!slot.on) {
        result.push(slot);
        continue;
      }

      const slotStart = this.timeToMinutes(slot.start);
      const slotStop = this.timeToMinutes(slot.stop);

      if (slotStop <= cutStart || slotStart >= cutStop) {
        result.push(slot);
        continue;
      }

      if (slotStart < cutStart) {
        result.push({
          start: slot.start,
          stop: cutSlot.start,
          on: true
        });
      }

      if (slotStop > cutStop) {
        result.push({
          start: cutSlot.stop,
          stop: slot.stop,
          on: true
        });
      }
    }

    return result;
  }

  mergeOnlyOn(slots) {
    const merged = [];
    let current = null;

    for (let slot of slots) {
      if (!slot.on) {
        if (current) {
          merged.push(current);
          current = null;
        }
        merged.push(slot);
        continue;
      }

      if (!current) {
        current = { ...slot };
        continue;
      }

      const currentStop = this.timeToMinutes(current.stop);
      const nextStart = this.timeToMinutes(slot.start);
      const adjustedCurrentStop = current.stop === "00:00" ? 1440 : currentStop;

      if (nextStart <= adjustedCurrentStop) {
        const nextStop = this.timeToMinutes(slot.stop);
        const currentStopMinutes = current.stop === "00:00" ? 1440 : this.timeToMinutes(current.stop);

        if (nextStop > currentStopMinutes) {
          current.stop = slot.stop;
        }
      } else {
        merged.push(current);
        current = { ...slot };
      }
    }

    if (current) {
      merged.push(current);
    }

    return merged;
  }

  async showTimeDialog(title, defaultTime = "08:00", minStart = null) {
    return new Promise(resolve => {
      const dialog = document.createElement("ha-dialog");
      dialog.open = true;
      dialog.heading = title;
      dialog.style.setProperty("--mdc-dialog-min-width", "330px");
      dialog.style.setProperty("--mdc-dialog-max-width", "360px");
      dialog.style.setProperty("--mdc-dialog-max-height", "420px");

      const [defH, defM] = defaultTime.split(":").map(Number);
      let minHour = 0;
      let minMinute = 0;
      if (minStart) {
        const [minH, minM] = minStart.split(":").map(Number);
        minHour = minH;
        minMinute = minM;
      }

      const wrapper = document.createElement("div");
      wrapper.innerHTML = `
        <style>
          .time-picker-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 16px;
            margin: 16px 0;
            padding: 0 16px;
          }
          .time-unit {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
          }
          .time-input {
            width: 60px;
            padding: 8px;
            font-size: 36px;
            text-align: center;
            font-family: 'Courier New', monospace;
            color: var(--primary-text-color, #111);
            background: var(--ha-card-background, #fff);
            border: 1px solid var(--divider-color, #ccc);
            border-radius: 6px;
          }
          .time-input::-webkit-outer-spin-button,
          .time-input::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
          }
          .time-input[type=number] {
            -moz-appearance: textfield;
          }
          .chevron-button {
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: var(--primary-color, #2196F3);
            background: transparent;
            border: none;
            padding: 0;
            font-size: 28px;
          }
          .chevron-button:hover {
            opacity: 0.7;
          }
          .chevron-button:disabled {
            opacity: 0.3;
            cursor: not-allowed;
          }
          .separator {
            font-size: 36px;
            font-weight: 300;
            height: 48px;
            display: flex;
            align-items: center;
            margin: 0 8px;
          }
          .button-row {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 8px;
            padding: 0;
          }
        </style>
        <div class="time-picker-container">
          <div class="time-unit">
            <button class="chevron-button" id="hour-up">▲</button>
            <input class="time-input" id="hour-input" type="number" min="0" max="23" value="${String(defH).padStart(2, "0")}" />
            <button class="chevron-button" id="hour-down">▼</button>
          </div>
          <div class="separator">:</div>
          <div class="time-unit">
            <button class="chevron-button" id="minute-up">▲</button>
            <input class="time-input" id="minute-input" type="number" min="0" max="59" step="15" value="${String(defM).padStart(2, "0")}" />
            <button class="chevron-button" id="minute-down">▼</button>
          </div>
        </div>
        <div class="button-row">
          <ha-button variant="brand" appearance="plain" id="cancel">Abbrechen</ha-button>
          <ha-button variant="brand" appearance="accent" id="ok">OK</ha-button>
        </div>
      `;
      dialog.appendChild(wrapper);
      dialog.setAttribute("slot", "primaryAction");
      document.body.appendChild(dialog);

      const hourInput = wrapper.querySelector("#hour-input");
      const minuteInput = wrapper.querySelector("#minute-input");
      const hourUpBtn = wrapper.querySelector("#hour-up");
      const hourDownBtn = wrapper.querySelector("#hour-down");
      const minuteUpBtn = wrapper.querySelector("#minute-up");
      const minuteDownBtn = wrapper.querySelector("#minute-down");

      const updateButtonStates = () => {
        const currentHour = parseInt(hourInput.value) || 0;
        const currentMinute = parseInt(minuteInput.value) || 0;
        const currentTimeMinutes = currentHour * 60 + currentMinute;
        const minTimeMinutes = minHour * 60 + minMinute;

        // Disable hour down if it would make time <= minStart
        const oneHourBack = (currentHour - 1 + 24) % 24;
        const oneHourBackMinutes = oneHourBack * 60 + currentMinute;
        hourDownBtn.disabled = minStart && oneHourBackMinutes <= minTimeMinutes;

        // Disable minute down if it would make time <= minStart
        let oneMinuteBackMinutes = currentTimeMinutes - 15;
        if (oneMinuteBackMinutes < 0) oneMinuteBackMinutes += 24 * 60;
        minuteDownBtn.disabled = minStart && oneMinuteBackMinutes <= minTimeMinutes;
      };

      // Hour up/down
      hourUpBtn.addEventListener("click", () => {
        let h = parseInt(hourInput.value) || 0;
        h = (h + 1) % 24;
        hourInput.value = String(h).padStart(2, "0");
        updateButtonStates();
      });

      hourDownBtn.addEventListener("click", () => {
        let h = parseInt(hourInput.value) || 0;
        h = h === 0 ? 23 : h - 1;
        hourInput.value = String(h).padStart(2, "0");
        updateButtonStates();
      });

      // Minute up/down
      minuteUpBtn.addEventListener("click", () => {
        let m = parseInt(minuteInput.value) || 0;
        if (m === 45) {
          m = 0;
          let h = parseInt(hourInput.value) || 0;
          h = (h + 1) % 24;
          hourInput.value = String(h).padStart(2, "0");
        } else {
          m += 15;
        }
        minuteInput.value = String(m).padStart(2, "0");
        updateButtonStates();
      });

      minuteDownBtn.addEventListener("click", () => {
        let m = parseInt(minuteInput.value) || 0;
        let h = parseInt(hourInput.value) || 0;
        if (m === 0) {
          m = 45;
          h = h === 0 ? 23 : h - 1;
        } else {
          m -= 15;
        }
        hourInput.value = String(h).padStart(2, "0");
        minuteInput.value = String(m).padStart(2, "0");
        updateButtonStates();
      });

      // Input change listeners
      hourInput.addEventListener("change", updateButtonStates);
      minuteInput.addEventListener("change", updateButtonStates);

      // Initialize button states
      updateButtonStates();

      wrapper.querySelector("#ok").addEventListener("click", () => {
        const h = hourInput.value;
        const m = minuteInput.value;
        const time = `${h}:${m}`;
        if (minStart && this.timeToMinutes(time) <= this.timeToMinutes(minStart)) {
          alert("Endzeit muss nach der Startzeit liegen!");
          return;
        }
        dialog.close();
        resolve(time);
      });

      wrapper.querySelector("#cancel").addEventListener("click", () => {
        dialog.close();
        resolve(null);
      });

      dialog.addEventListener("closed", () => {
        dialog.remove();
      });
    });
  }

  async showOnOffDialog() {
    return new Promise(resolve => {
      const dialog = document.createElement("ha-dialog");
      dialog.open = true;
      dialog.heading = "Status wählen";
      dialog.style.setProperty("--mdc-dialog-min-width", "300px");
      dialog.style.setProperty("--mdc-dialog-max-width", "330px");
      dialog.style.setProperty("--mdc-dialog-max-height", "280px");

      const wrapper = document.createElement("div");
      wrapper.innerHTML = `
        <style>
          .status-options {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin: 16px auto;
            max-width: 150px;
          }
          .status-button {
            padding: 14px 20px;
            font-size: 16px;
            border: 2px solid var(--divider-color, #ccc);
            border-radius: 6px;
            background: var(--ha-card-background, #fff);
            color: var(--primary-text-color, #111);
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
          }
          .status-button:hover {
            border-color: var(--primary-color, #2196F3);
            background: rgba(33, 150, 243, 0.05);
          }
          .status-button.on {
            background: var(--success-color, #4CAF50);
            color: white;
            border-color: var(--success-color, #4CAF50);
          }
          .status-button.off {
            background: var(--error-color, #E53935);
            color: white;
            border-color: var(--error-color, #E53935);
          }
          .button-row {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 8px;
            padding: 0;
          }
        </style>
        <div class="status-options">
          <button class="status-button on" id="btn-on">AN</button>
          <button class="status-button off" id="btn-off">AUS</button>
        </div>
        <div class="button-row">
          <ha-button variant="brand" appearance="plain" id="cancel">Abbrechen</ha-button>
          <ha-button variant="brand" appearance="accent" id="ok">OK</ha-button>
        </div>
      `;
      dialog.appendChild(wrapper);
      dialog.setAttribute("slot", "primaryAction");
      document.body.appendChild(dialog);

      wrapper.querySelector("#btn-on").addEventListener("click", () => {
        dialog.close();
        resolve(true);
      });

      wrapper.querySelector("#btn-off").addEventListener("click", () => {
        dialog.close();
        resolve(false);
      });

      wrapper.querySelector("#ok").addEventListener("click", () => {
        dialog.close();
        resolve(true); // Default to "on"
      });

      wrapper.querySelector("#cancel").addEventListener("click", () => {
        dialog.close();
        resolve(null);
      });

      dialog.addEventListener("closed", () => {
        dialog.remove();
      });
    });
  }

  deleteTimeslot(day, index) {
    if (this._timeprogram[day]) {
      this._timeprogram[day].timeslots.splice(index, 1);
      this._dirty = true;
      this.render();
    }
  }

  saveTimeprogram() {
    let cleanedTimeprogram = {};
    for (let day in this._timeprogram) {
      cleanedTimeprogram[day] = {
        timeslots: this._timeprogram[day].timeslots.filter(slot => slot.on)
      };
    }

    this._hass.callService("remko_mqtt", "update_timeprogram", {
      entity_id: this.config.entity,
      timeprogram: cleanedTimeprogram,
    });
    this._original_timeprogram = structuredClone(this._timeprogram);
    for (let day of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
      this._new_slots[day] = [];
      this._new_time_ranges[day] = [];
    }
    this._dirty = false;
    this.render();
  }

  cancelTimeprogram() {
    this._timeprogram = structuredClone(this._original_timeprogram);
    for (let day of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
      this._new_slots[day] = [];
      this._new_time_ranges[day] = [];
    }
    this._dirty = false;
    this.render();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {
      entity: "sensor.remko_mqtt_timeprogram_dhw_a",
      title: "Remko Heizungs-Zeitplan"
    };
  }
}

customElements.define("remko-timeprogram-card", RemkoTimeprogramCard);
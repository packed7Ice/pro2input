import { wsConnection, SettingsMessage } from "./ws";

type SettingsData = Record<string, any>;

const FH6_FIELDS: { key: string; label: string; step?: string; kind: "checkbox" | "number" }[] = [
  { key: "fh6_udp.enabled", label: "有効", kind: "checkbox" },
  { key: "fh6_udp.port", label: "ポート", kind: "number" },
  { key: "fh6_udp.strength", label: "強度", step: "0.05", kind: "number" },
  { key: "fh6_udp.smashable_threshold", label: "衝突しきい値 (m/s)", step: "0.1", kind: "number" },
  { key: "fh6_udp.slip_scale", label: "スリップスケール", step: "0.05", kind: "number" },
  { key: "fh6_udp.surface_scale", label: "路面スケール", step: "0.05", kind: "number" },
  { key: "fh6_udp.timeout_ms", label: "タイムアウト (ms)", kind: "number" },
  { key: "fh6_udp.hold_ms", label: "ホールド時間 (ms)", kind: "number" },
];

const STICK_FIELDS = [
  { path: "stick.left.invert_x", label: "左スティック X反転" },
  { path: "stick.left.invert_y", label: "左スティック Y反転" },
  { path: "stick.right.invert_x", label: "右スティック X反転" },
  { path: "stick.right.invert_y", label: "右スティック Y反転" },
];

const KEYBOARD_KEYS = ["Capture", "CButton", "GRButton", "GLButton"];

function getPath(data: SettingsData, path: string): unknown {
  return path.split(".").reduce<any>((acc, key) => (acc == null ? undefined : acc[key]), data);
}

export function initSettingsPanel() {
  const saveBtn = document.getElementById("settings-save") as HTMLButtonElement;
  const resetBtn = document.getElementById("settings-reset") as HTMLButtonElement;
  const statusMsg = document.getElementById("settings-status-msg") as HTMLSpanElement;

  const appContainer = document.getElementById("settings-app") as HTMLDivElement;
  const buttonMappingContainer = document.getElementById("settings-button-mapping") as HTMLDivElement;
  const sticksContainer = document.getElementById("settings-sticks") as HTMLDivElement;
  const rumbleContainer = document.getElementById("settings-rumble") as HTMLDivElement;
  const fh6Container = document.getElementById("settings-fh6") as HTMLDivElement;
  const keyboardContainer = document.getElementById("settings-keyboard") as HTMLDivElement;

  let latestData: SettingsData = {};
  let xboxButtonCodes: string[] = [];
  let switchButtonNames: string[] = [];
  let pendingValues: Record<string, unknown> = {};

  function addCaption(container: HTMLElement, text: string) {
    const p = document.createElement("p");
    p.className = "settings-caption";
    p.textContent = text;
    container.appendChild(p);
  }

  function markDirty(path: string, value: unknown) {
    pendingValues[path] = value;
    saveBtn.disabled = false;
    statusMsg.textContent = "未保存の変更があります";
  }

  function renderApp() {
    appContainer.innerHTML = "";
    const current = String(getPath(latestData, "app.close_action") ?? "minimize");
    const options: { value: string; label: string }[] = [
      { value: "minimize", label: "トレイに最小化する（コントローラーはバックグラウンドで動作継続）" },
      { value: "quit", label: "完全に終了する" },
    ];
    for (const opt of options) {
      const row = document.createElement("label");
      row.className = "settings-checkbox-row";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "close-action";
      input.value = opt.value;
      input.checked = current === opt.value;
      input.addEventListener("change", () => {
        if (input.checked) markDirty("app.close_action", opt.value);
      });
      row.appendChild(input);
      row.appendChild(document.createTextNode(opt.label));
      appContainer.appendChild(row);
    }
    addCaption(appContainer, "ウィンドウを閉じる（×）ボタンを押したときの動作です。次回閉じるときから反映されます。");
  }

  function renderButtonMapping() {
    buttonMappingContainer.innerHTML = "";
    const mapping: Record<string, string | null> = { ...(latestData.button_mapping || {}) };
    for (const switchName of switchButtonNames) {
      const row = document.createElement("div");
      row.className = "settings-row";

      const label = document.createElement("span");
      label.className = "settings-label";
      label.textContent = switchName;

      const select = document.createElement("select");
      const noneOpt = document.createElement("option");
      noneOpt.value = "";
      noneOpt.textContent = "(なし)";
      select.appendChild(noneOpt);
      for (const code of xboxButtonCodes) {
        const opt = document.createElement("option");
        opt.value = code;
        opt.textContent = code;
        select.appendChild(opt);
      }
      select.value = mapping[switchName] ?? "";
      select.addEventListener("change", () => {
        mapping[switchName] = select.value || null;
        markDirty("button_mapping", { ...mapping });
      });

      row.appendChild(label);
      row.appendChild(select);
      buttonMappingContainer.appendChild(row);
    }
    addCaption(buttonMappingContainer, "変更は次の入力フレームから即時反映されます。");
  }

  function renderSticks() {
    sticksContainer.innerHTML = "";
    for (const { path, label } of STICK_FIELDS) {
      const row = document.createElement("label");
      row.className = "settings-checkbox-row";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(getPath(latestData, path));
      input.addEventListener("change", () => markDirty(path, input.checked));
      row.appendChild(input);
      row.appendChild(document.createTextNode(label));
      sticksContainer.appendChild(row);
    }
    addCaption(sticksContainer, "変更は即時反映されます。");
  }

  function renderRumble() {
    rumbleContainer.innerHTML = "";

    const enabledRow = document.createElement("label");
    enabledRow.className = "settings-checkbox-row";
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.checked = Boolean(getPath(latestData, "rumble.enabled"));
    enabledInput.addEventListener("change", () => markDirty("rumble.enabled", enabledInput.checked));
    enabledRow.appendChild(enabledInput);
    enabledRow.appendChild(document.createTextNode("振動を有効化 (要再起動)"));
    rumbleContainer.appendChild(enabledRow);

    const strengthRow = document.createElement("div");
    strengthRow.className = "settings-row";
    const strengthLabel = document.createElement("span");
    strengthLabel.className = "settings-label";
    strengthLabel.textContent = "強度";
    const strengthInput = document.createElement("input");
    strengthInput.type = "range";
    strengthInput.min = "0";
    strengthInput.max = "2";
    strengthInput.step = "0.05";
    strengthInput.value = String(getPath(latestData, "rumble.strength") ?? 1.0);
    const strengthValue = document.createElement("span");
    strengthValue.className = "settings-value";
    strengthValue.textContent = strengthInput.value;
    strengthInput.addEventListener("input", () => {
      strengthValue.textContent = strengthInput.value;
      markDirty("rumble.strength", parseFloat(strengthInput.value));
    });
    strengthRow.appendChild(strengthLabel);
    strengthRow.appendChild(strengthInput);
    strengthRow.appendChild(strengthValue);
    rumbleContainer.appendChild(strengthRow);

    addCaption(rumbleContainer, "強度は即時反映されます。有効/無効の切り替えはコア再起動が必要です。");
  }

  function renderFh6() {
    fh6Container.innerHTML = "";
    for (const field of FH6_FIELDS) {
      const row = document.createElement("div");
      row.className = "settings-row";
      const label = document.createElement("span");
      label.className = "settings-label";
      label.textContent = field.label;
      row.appendChild(label);

      const currentValue = getPath(latestData, field.key);
      if (field.kind === "checkbox") {
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(currentValue);
        input.addEventListener("change", () => markDirty(field.key, input.checked));
        row.appendChild(input);
      } else {
        const input = document.createElement("input");
        input.type = "number";
        if (field.step) input.step = field.step;
        input.value = String(currentValue ?? 0);
        input.addEventListener("change", () => {
          const num = field.step ? parseFloat(input.value) : parseInt(input.value, 10);
          if (!Number.isNaN(num)) markDirty(field.key, num);
        });
        row.appendChild(input);
      }
      fh6Container.appendChild(row);
    }
    addCaption(fh6Container, "この項目の変更はコア再起動後に反映されます。");
  }

  function renderKeyboard() {
    keyboardContainer.innerHTML = "";
    for (const key of KEYBOARD_KEYS) {
      const path = `keyboard_mapping.${key}`;
      const row = document.createElement("div");
      row.className = "settings-row";
      const label = document.createElement("span");
      label.className = "settings-label";
      label.textContent = key;
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = "例: win+alt+prtsc";
      input.value = String(getPath(latestData, path) ?? "");
      input.addEventListener("change", () => {
        markDirty(path, input.value.trim() || null);
      });
      row.appendChild(label);
      row.appendChild(input);
      keyboardContainer.appendChild(row);
    }
    addCaption(keyboardContainer, "変更は即時反映されます。");
  }

  function render(msg: SettingsMessage) {
    latestData = msg.data;
    xboxButtonCodes = msg.meta.xbox_button_codes;
    switchButtonNames = msg.meta.switch_button_names;
    pendingValues = {};
    saveBtn.disabled = true;
    statusMsg.textContent = "";

    renderApp();
    renderButtonMapping();
    renderSticks();
    renderRumble();
    renderFh6();
    renderKeyboard();
  }

  saveBtn.addEventListener("click", () => {
    if (Object.keys(pendingValues).length === 0) return;
    wsConnection.send({ type: "set_settings", values: pendingValues });
    statusMsg.textContent = "保存中...";
  });

  resetBtn.addEventListener("click", () => {
    if (!confirm("すべての設定を初期値に戻しますか？")) return;
    wsConnection.send({ type: "reset_settings" });
  });

  wsConnection.onSettings(render);

  saveBtn.disabled = true;
}

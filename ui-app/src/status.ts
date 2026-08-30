import { wsConnection, StatusMessage } from "./ws";

const BUTTON_KEYS = [
  "Y", "X", "B", "A", "R", "ZR",
  "Minus", "Plus", "RStick", "LStick", "Home", "Capture", "CButton",
  "Down", "Up", "Right", "Left", "L", "ZL",
  "GRButton", "GLButton",
];

export function initStatusPanel() {
  const connBadge = document.getElementById("conn-badge") as HTMLDivElement;
  const rumbleLargeFill = document.getElementById("rumble-large-fill") as HTMLDivElement;
  const rumbleSmallFill = document.getElementById("rumble-small-fill") as HTMLDivElement;
  const rumbleLargePct = document.getElementById("rumble-large-pct") as HTMLSpanElement;
  const rumbleSmallPct = document.getElementById("rumble-small-pct") as HTMLSpanElement;
  const stallBadge = document.getElementById("stall-badge") as HTMLSpanElement;
  const suspendBadge = document.getElementById("suspend-badge") as HTMLSpanElement;
  const lstickDot = document.getElementById("lstick-dot") as HTMLDivElement;
  const rstickDot = document.getElementById("rstick-dot") as HTMLDivElement;
  const buttonGrid = document.getElementById("button-grid") as HTMLDivElement;

  const buttonPills = new Map<string, HTMLDivElement>();
  for (const key of BUTTON_KEYS) {
    const pill = document.createElement("div");
    pill.className = "button-pill";
    pill.textContent = key;
    buttonGrid.appendChild(pill);
    buttonPills.set(key, pill);
  }

  function setConnBadge(state: "unknown" | "connected" | "searching") {
    connBadge.classList.remove("badge-unknown", "badge-on-good", "badge-on-bad");
    if (state === "connected") {
      connBadge.classList.add("badge-on-good");
      connBadge.textContent = "コントローラー接続中";
    } else if (state === "searching") {
      connBadge.classList.add("badge-on-bad");
      connBadge.textContent = "コントローラー未接続";
    } else {
      connBadge.classList.add("badge-unknown");
      connBadge.textContent = "接続確認中...";
    }
  }

  function setFlagBadge(el: HTMLSpanElement, on: boolean, kind: "bad" = "bad") {
    el.classList.remove("badge-off", "badge-on-bad");
    el.classList.add(on ? `badge-on-${kind}` : "badge-off");
  }

  // Stick square is 96px with a 12px dot; clamp so the dot center never leaves the box.
  function placeDot(dot: HTMLDivElement, x: number, y: number) {
    const clampedX = Math.max(-1, Math.min(1, x));
    const clampedY = Math.max(-1, Math.min(1, y));
    const pct = (v: number) => 50 + v * 42; // 42% radius keeps the dot inside the box
    dot.style.left = `${pct(clampedX)}%`;
    // Screen Y grows downward; stick +Y (up) should move the dot up.
    dot.style.top = `${pct(-clampedY)}%`;
  }

  function applyStatus(msg: StatusMessage) {
    setConnBadge(msg.connected ? "connected" : "searching");

    const largePct = Math.round(msg.rumble.large * 100);
    const smallPct = Math.round(msg.rumble.small * 100);
    rumbleLargeFill.style.width = `${largePct}%`;
    rumbleSmallFill.style.width = `${smallPct}%`;
    rumbleLargePct.textContent = `${largePct}%`;
    rumbleSmallPct.textContent = `${smallPct}%`;

    setFlagBadge(stallBadge, msg.rumble.stalled);
    setFlagBadge(suspendBadge, msg.rumble.suspended);

    placeDot(lstickDot, msg.input.sticks.lx, msg.input.sticks.ly);
    placeDot(rstickDot, msg.input.sticks.rx, msg.input.sticks.ry);

    for (const [key, pill] of buttonPills) {
      pill.classList.toggle("pressed", Boolean(msg.input.buttons[key]));
    }
  }

  wsConnection.onStatus(applyStatus);
  wsConnection.onClose(() => setConnBadge("unknown"));
}

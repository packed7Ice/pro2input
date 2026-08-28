import { wsConnection } from "./ws";
import { initStatusPanel } from "./status";
import { initSettingsPanel } from "./settings";

function initTabs() {
  const tabButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".tab-button"));
  const panels: Record<string, HTMLElement> = {
    status: document.getElementById("status-panel-root") as HTMLElement,
    settings: document.getElementById("settings-panel-root") as HTMLElement,
  };
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab as string;
      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      for (const [name, panel] of Object.entries(panels)) {
        panel.classList.toggle("hidden", name !== target);
      }
    });
  });
}

initTabs();
initStatusPanel();
initSettingsPanel();
wsConnection.connect();

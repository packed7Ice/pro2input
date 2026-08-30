export const WS_URL = "ws://127.0.0.1:8765";

export interface StatusMessage {
  type: "status";
  ts: number;
  connected: boolean;
  rumble: {
    large: number;
    small: number;
    stalled: boolean;
    suspended: boolean;
  };
  input: {
    buttons: Record<string, boolean>;
    sticks: { lx: number; ly: number; rx: number; ry: number };
  };
}

export interface SettingsMessage {
  type: "settings";
  data: Record<string, any>;
  meta: {
    xbox_button_codes: string[];
    switch_button_names: string[];
  };
}

type InboundMessage = StatusMessage | SettingsMessage | { type: string };

class WsConnection {
  private ws: WebSocket | null = null;
  private statusListeners: ((msg: StatusMessage) => void)[] = [];
  private settingsListeners: ((msg: SettingsMessage) => void)[] = [];
  private openListeners: (() => void)[] = [];
  private closeListeners: (() => void)[] = [];

  connect() {
    const ws = new WebSocket(WS_URL);
    this.ws = ws;

    ws.onopen = () => {
      for (const listener of this.openListeners) listener();
    };

    ws.onmessage = (event) => {
      let msg: InboundMessage;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return; // ignore malformed frames
      }
      if (msg.type === "status") {
        for (const listener of this.statusListeners) listener(msg as StatusMessage);
      } else if (msg.type === "settings") {
        for (const listener of this.settingsListeners) listener(msg as SettingsMessage);
      }
    };

    ws.onclose = () => {
      this.ws = null;
      for (const listener of this.closeListeners) listener();
      setTimeout(() => this.connect(), 1000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  send(msg: Record<string, unknown>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  onStatus(listener: (msg: StatusMessage) => void) {
    this.statusListeners.push(listener);
  }

  onSettings(listener: (msg: SettingsMessage) => void) {
    this.settingsListeners.push(listener);
  }

  onOpen(listener: () => void) {
    this.openListeners.push(listener);
  }

  onClose(listener: () => void) {
    this.closeListeners.push(listener);
  }
}

export const wsConnection = new WsConnection();

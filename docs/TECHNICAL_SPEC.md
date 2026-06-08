# pro2input 技術仕様書

Switch 2 Pro Controller (VID `0x057E` / PID `0x2069`) の USB プロトコルおよび
HD Rumble 2 実装の確定仕様をまとめたリファレンスドキュメント。

---

## 1. USB デバイス構成

### デバイス識別子

| 項目 | 値 |
|------|-----|
| VID | `0x057E` (Nintendo) |
| PID | `0x2069` (Switch 2 Pro Controller) |
| 必要ドライバー | **libusbK**（Interface 0・1 両方） |

### インターフェースとエンドポイント

| Interface | ep | 方向 | 種別 | 用途 |
|-----------|----|------|------|------|
| 0 | `0x81` | IN | Interrupt | HID 入力レポート（ボタン・スティック） |
| 0 | `0x01` | OUT | Interrupt | **振動パケット送信** |
| 1 | `0x02` | OUT | Bulk | 初期化コマンド送信（起動時のみ） |
| 1 | `0x82` | IN | Bulk | 初期化コマンドへの ACK 受信 |

> **重要**: 振動は Interface 0 Interrupt OUT (`0x01`) へ送る。
> Interface 1 Bulk OUT (`0x02`) は初期化専用であり、振動には使用しない。

### Zadig 設定

Interface 0・1 の**両方**を libusbK に設定すること。
片方でも Windows 標準 HID（HidUsb）が残っていると、libusb との競合で振動が断続的に失敗する。

---

## 2. 初期化シーケンス

`initialize_hid_mode()` (`core/controller_usb.py`) が起動時に一度だけ実行する。
全コマンドは Interface 1 Bulk OUT (`0x02`) へ送信し、都度 Bulk IN (`0x82`) で ACK を受信する。

### パケット長の計算規則（SDL 準拠）

```
送信長 = cmd[5] + 8
```

例: `0x0A` コマンドは `cmd[5] = 0x14 = 20` → 送信長 28 バイト。

### ステップ 1: ReadFlashBlock コマンド（× 5）

INIT_COMMANDS より先に送信する（SDL の順序）。

| アドレス | 内容 |
|---------|------|
| `0x13000` | シリアル番号 |
| `0x13040` | ジャイロバイアス |
| `0x13080` | 左スティックキャリブレーション |
| `0x130C0` | 右スティックキャリブレーション |
| `0x13100` | 加速度センサーバイアス |

コマンド構造（16 バイト）:
```
[0]=0x02  [1]=0x91  [2]=0x00  [3]=0x01  [4]=0x00  [5]=0x08
[12..15] = address (little-endian u32)
```

### ステップ 2: INIT_COMMANDS（順序厳守）

```python
[0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]
[0x0C, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]  # feature output bitmask
[0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]
[0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, ...]   # ★ Set rumble data（28バイト）
[0x0C, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]  # feature output bits enable
[0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]
[0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]  # ★ Enable rumble
[0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]  # charging grip
[0x03, 0x91, 0x00, 0x0A, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00]  # set report format
[0x03, 0x91, 0x00, 0x0D, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xFF, ...]   # ★ Start output（必ず最後）
```

`Start output (0x03/0x0D)` は必ず最後に送ること。順序を変えると振動が有効にならない。

### ステップ 3: LED コマンド

```python
[0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
```

SDL の `UpdateSlotLED`（player_index=-1 → pattern `0x06`）に相当。

---

## 3. HID 入力レポート

Interface 0 Interrupt IN (`0x81`) から 64 バイトで届く。
先頭バイト（Report ID）を除いた 63 バイトをパースする。

### ボタン配置（`core/input_parser.py` 参照）

| バイト | ビット | ボタン |
|-------|-------|-------|
| `payload[1]` | `& 0x04` | Y |
| `payload[1]` | `& 0x08` | X |
| `payload[1]` | `& 0x01` | B |
| `payload[1]` | `& 0x02` | A |
| `payload[1]` | `& 0x40` | R |
| `payload[1]` | `& 0x80` | ZR |
| `payload[2]` | `& 0x02` | Minus |
| `payload[2]` | `& 0x01` | Plus |
| `payload[2]` | `& 0x08` | RStick |
| `payload[2]` | `& 0x04` | LStick |
| `payload[2]` | `& 0x20` | Home |
| `payload[2]` | `& 0x10` | Capture |
| `payload[2]` | `& 0x40` | CButton |
| `payload[3]` | `& 0x01` | Down |
| `payload[3]` | `& 0x02` | Up |
| `payload[3]` | `& 0x08` | Right |
| `payload[3]` | `& 0x04` | Left |
| `payload[3]` | `& 0x40` | L |
| `payload[3]` | `& 0x80` | ZL |
| `payload[7]` | `& 0x01` | GRButton（右背面） |
| `payload[7]` | `& 0x02` | GLButton（左背面） |

### スティック

12 ビット値（0–4095）、中央 = 2047.5。
`payload[4..8]` に左右スティック X/Y が packed で格納される（`core/input_parser.py` 参照）。

---

## 4. 振動パケット仕様

### パケット構造（64 バイト）

```
[0]       = 0x02           Report ID（固定）
[1]       = 0x50 | (seq & 0x0F)   シーケンス番号（0x0〜0xF でローテーション）
[2:7]     = actuator[0:5]  左アクチュエータ（5 バイト、EncodeHDRumble）
[7:17]    = 0x00 × 10      パディング
[17:23]   = report[1:7]    右アクチュエータ（左と同一、[1:7] をそのままコピー）
[23:64]   = 0x00 × 41      パディング
```

SDL ソース: `memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)`
`0x11` は **16進数 = 10進数 17**（decimal 11 ではない）。

### EncodeHDRumble（5 バイト）

SDL `SDL_hidapi_switch2.c` の `EncodeHDRumble` 関数そのまま:

```python
data[0] = high_freq & 0xFF
data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
data[4] = (low_amp >> 8) & 0xFF
```

### デフォルト周波数・振幅

| 定数 | 値 | 意味 |
|------|-----|------|
| `RUMBLE_HF_FREQ` | `0x0187` | 高周波デフォルト（~600 Hz） |
| `RUMBLE_LF_FREQ` | `0x0112` | 低周波デフォルト（~260 Hz） |
| `RUMBLE_AMP_MAX` | `29000` | SDL の safe maximum（UINT16_MAX = 65535 の約 44%） |
| `RUMBLE_NEUTRAL_ACTUATOR` | `[0x87, 0x01, 0x20, 0x11, 0x00]` | 無振動（EncodeHDRumble(0x187, 0, 0x112, 0)） |

### 連続送信の必須要件

コントローラーのモーターはパケットをラッチしない。
**パケットが止まると ~100ms 以内にモーターが停止する。**
値が変わらなくても 12ms ごとに送り続けること（SDL の `RUMBLE_INTERVAL` 準拠）。

---

## 5. Windows / libusbK エンドポイント挙動

### STALL（Pipe Error）

- errno 32 (`EPIPE`): デバイスが STALL ハンドシェイクを返した（エンドポイント停止）
- 対処: `usb.util.clear_halt(device, ep)` で CLEAR_FEATURE(ENDPOINT_HALT) を送信して回復

### clear_halt の注意点

**STALL していないエンドポイントに `clear_halt` を呼んではならない。**

Windows + libusbK では、スタールしていないエンドポイントへの `clear_halt` がデータトグルをデsync させ、
以降のすべての書き込みが errno 10060（タイムアウト）で失敗するようになる。

```python
# 正しい使い方: errno 32 のときだけ呼ぶ
if exc.errno == 32:
    usb.util.clear_halt(device, ep0_out)
```

### STALL のセッション間持続

前のセッションで発生した STALL は Windows/libusbK ドライバー内部に残存する。
次回セッションの最初の書き込みで errno 32 ではなく errno 10060（タイムアウト）として現れる。

**物理的な USB ケーブルの抜き差しでドライバー状態がリセットされる。**
ソフトウェアリコネクト（`dispose_resources` → `find`) ではドライバー状態は完全にリセットされない。

### 振動失敗時の挙動（`send_rumble_bulk`）

| 失敗回数 | 挙動 |
|---------|------|
| 1〜3 回 | ログ出力 |
| 4〜49 回 | サイレント継続 |
| 50 回目 | `[USB] Rumble suspended` を出力し、以降の送信をスキップ |

振動の失敗は**リコネクトを引き起こさない**。
物理切断（errno 5・19）のみがリコネクトをトリガーする（入力スレッドが検出）。

---

## 6. FH6 UDP テレメトリ仕様

Forza Horizon 6 の Data Out（Settings → HUD & Gameplay → Data Out）が送信する。

### 接続設定

| 項目 | 値 |
|------|-----|
| 宛先 IP | `127.0.0.1` |
| ポート | `5301` |
| 方向 | ゲーム → pro2input（一方向 UDP） |
| パケットサイズ | 324 バイト（固定）、リトルエンディアン |
| 送信条件 | レース中のみ（メニュー・ポーズ中は無送信） |

### 振動に使うフィールド

| オフセット | 型 | フィールド名 | 用途 |
|-----------|-----|-------------|------|
| 0 | S32 | IsRaceOn | レース中 = 1、それ以外 = 0 |
| 148 | F32 | SurfaceRumbleFL | 路面振動（左前）→ 低周波モーター |
| 152 | F32 | SurfaceRumbleFR | 路面振動（右前） |
| 156 | F32 | SurfaceRumbleRL | 路面振動（左後） |
| 160 | F32 | SurfaceRumbleRR | 路面振動（右後） |
| 180 | F32 | TireCombinedSlipFL | タイヤスリップ（左前）→ 高周波モーター |
| 184 | F32 | TireCombinedSlipFR | タイヤスリップ（右前） |
| 188 | F32 | TireCombinedSlipRL | タイヤスリップ（左後） |
| 192 | F32 | TireCombinedSlipRR | タイヤスリップ（右後） |
| 236 | F32 | SmashableVelDiff | 衝突速度差 m/s（FH6 追加フィールド） |

### 振動強度計算（優先度順）

```
1. 衝突（最高優先）: SmashableVelDiff > smashable_threshold (default 3.0 m/s)
      large = small = clamp(velDiff / 15.0, 0, 1) × 255 × strength

2. スリップ → 高周波モーター (small):
      slip = clamp(max(|TireCombinedSlip×4|), 0, 1) × slip_scale × 255 × strength

3. 路面振動 → 低周波モーター (large):
      surface = clamp(max(SurfaceRumble×4), 0, 1) × surface_scale × 255 × strength
```

### hold_ms

値がゼロになった直後も `hold_ms`（デフォルト 150ms）の間は直前の非ゼロ値を維持する。
短い振動の途切れを補間し、ドライブ中の連続感を保つ。

---

## 7. 参考リンク

| リソース | URL |
|---------|-----|
| SDL hidapi switch2 実装 | https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_switch2.c |
| NSW2-controller-enabler | https://github.com/ikz87/NSW2-controller-enabler |
| Nintendo Switch Reverse Engineering | https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering |
| HorizonHaptics（FH5/FH6 振動参照） | https://github.com/haritha99ch/HorizonHaptics |

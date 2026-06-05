# pro2input: 現状の問題と実装コンテキスト

## 現在の状態（2026-06-06 時点）

| 項目 | 状態 |
|------|------|
| UDP 受信（FH6 Data Out） | ✅ 正常受信中 |
| ランブル値計算（UDP → large/small 変換） | ✅ 正常 |
| Bulk OUT 書き込み | ✅ エラーなし（pywinusb 排除後） |
| **コントローラー振動** | ❌ **未解決** |
| **入力遅延** | ⚠️ **起動後数分で再発** |

---

## リポジトリ構造（確認済み）

```
pro2input/
├── config.json              # ルートに存在 → UDP ポートをここに追加
├── main.py                  # エントリーポイント（要編集）
├── start.bat / settings.bat
├── config/                  # 詳細未確認
├── core/
│   ├── constants.py         # デバイスID・初期化コマンド・振動定数
│   ├── controller_usb.py    # USB接続とHID I/O
│   ├── input_parser.py      # ボタン・スティック・トリガー解析
│   └── rumble_manager.py    # XInput → Switch 2 Pro 振動変換
├── mapping/
│   └── xbox360_mapper.py
├── tools/
│   ├── fh6_rumble_debug.py
│   ├── xinput_rumble_test.py
│   └── rumble_hid_control_test.py
└── ui/                      # 詳細未確認
```

---

## 問題A：振動しない

### 根本原因の仮説（優先度順）

**仮説1: init_sequence に必須コマンドが欠落している**

SDL（`SDL_hidapi_switch2.c`）の init_sequence を確認済み。以下の順序が必須：

```
① ReadFlashBlock × 5（アドレス順）
   0x13000  → シリアル番号
   0x13040  → ジャイロバイアス
   0x13080  → 左スティックキャリブレーション
   0x130C0  → 右スティックキャリブレーション
   0x13100  → 加速度センサーバイアス

② init_sequence（各コマンド送信後に必ず RecvBulkData でACK受信）
   [0x07, 0x91, 0x00, 0x01, ...]          # 不明
   [0x0c, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]  # feature output bitmask set
   [0x11, 0x91, 0x00, 0x01, ...]          # 不明
   [0x0a, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00,   # ★ Set rumble data
    0x01, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00]
   [0x0c, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]  # feature output bits enable
   [0x01, 0x91, 0x00, 0x0c, ...]          # 不明
   [0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]   # ★ Enable rumble
   [0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]  # charging grip
   [0x03, 0x91, 0x00, 0x0a, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00]  # set report format
   [0x03, 0x91, 0x00, 0x0d, 0x00, 0x08, 0x00, 0x00,   # ★ Start output
    0x01, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]
```

SDL のパケット長の計算規則: `init_sequence[i][5] + 8` バイトを送信
（例: `0x0a` コマンドは `data[5]=0x14=20` → 送信長 28 バイト）

**確認箇所**: `core/constants.py` の init_sequence と上記を1バイト単位で比較すること。
特に `ReadFlashBlock` の有無と `0x0a`（Set rumble data）・`0x01`（Enable rumble）の存在を確認。

---

**仮説2: rumble パケットのシーケンス番号が更新されていない**

SDL では `rumble_seq` を毎回インクリメント（0x0〜0xF でローテーション）しており、
シーケンス番号が変化しないパケットはコントローラー側で無視される可能性がある。

**確認箇所**: `rumble_manager.py` の `_build_report()` でシーケンス番号を毎回更新しているか。

---

**仮説3: rumble パケットのフォーマット不正**

SDL の `UpdateRumble` は以下の構造でパケットを構築する：

```
rumble_data[0x00] = コマンドID（rumble専用は 0x10）
rumble_data[0x01] = シーケンス番号（0x0〜0xF）
rumble_data[0x02..0x09] = 左スティック rumble（4バイト）+ 右スティック rumble（4バイト）
```

HD Rumble 2 の4バイト構造（Switch 1 Pro から変更あり）:
```
[0] high_freq_amp  (low byte)
[1] high_freq      (encoded)  = (hi_freq >> 8) | (hi_amp >> 8) << ... （SDL の RUMBLE_MAX=29000 基準）
[2] low_freq_amp   (low byte)
[3] low_freq       (encoded)
```
SDL ソースの正確なエンコードは `SDL_hidapi_switch2.c` の `UpdateRumble` 関数（1000行以降）を直接参照すること。

**確認箇所**: `rumble_manager.py` の `_build_report()` のバイト列を `test_bulk_rumble.py` で実際に送信し、物理振動を確認（最小検証）。

---

### 推奨アクション（振動問題、優先順）

1. `test_bulk_rumble.py` を単独実行 → 物理振動するか確認（現状ベースライン）
2. `core/constants.py` の init_sequence と上記 SDL の init_sequence をバイト比較
3. `ReadFlashBlock` が init 前に送信されていなければ追加
4. `rumble_manager.py` のシーケンス番号インクリメントを確認・修正
5. rumble パケットのバイト列を SDL の `UpdateRumble` と比較

---

## 問題B：入力遅延

### 原因

`controller_usb.py` の入力読み取りが `dev.read(64, timeout=100)` のブロッキング呼び出しで、
UDP パケット処理・vgamepad 更新・rumble 送信と同一ループで動いている。
pywinusb のコールバック方式がノンブロッキングだったのに対し、pyusb-only になってこの問題が顕在化。

### 修正方針

入力読み取りを専用スレッドに分離し、Queue 経由でメインループに渡す：

```python
# input_thread（専用スレッド、ブロッキングOK）
def _input_thread(self):
    while self._running:
        data = self.dev.read(64, timeout=100)  # ブロックしても構わない
        if data:
            self._input_queue.put(bytes(data))

# メインループ（ノンブロッキング）
while running:
    try:
        raw = input_queue.get_nowait()
        process_input(raw)
    except Empty:
        pass
    update_vgamepad()
    send_rumble_if_needed()
    time.sleep(0.001)
```

この修正は振動問題と独立しているため、先に対応可能。

---

## タスク：FH6 UDP テレメトリ振動対応（問題A が解決した後）

### 概要

FH6（Game Pass 版）は ViGEmBus 仮想デバイスに振動を送らない（GameInput API の制限、回避不可）。
FH6 の公式 UDP テレメトリ（Data Out）を振動入力源として使う。

### FH6 Data Out 仕様

| 項目 | 値 |
|------|-----|
| 設定箇所 | Settings → HUD and Gameplay → Data Out → ON |
| 宛先 IP | 127.0.0.1 |
| ポート | **5301 以降を推奨**（5200〜5300 はゲームが使用） |
| 方向 | ゲーム → 外部の一方向 UDP のみ |
| 送信条件 | 運転中のみ（メニュー・ポーズ中は無送信） |
| パケット | 固定 324 バイト、リトルエンディアン、パディングなし |

### 振動に使うフィールド

| オフセット | 型  | フィールド名 | 用途 |
|-----------|-----|-------------|------|
| 0 | S32 | IsRaceOn | 運転中=1、それ以外=0 |
| 148 | F32 | SurfaceRumbleFL | ★ 路面振動（force feedback 生値） |
| 152 | F32 | SurfaceRumbleFR | ★ |
| 156 | F32 | SurfaceRumbleRL | ★ |
| 160 | F32 | SurfaceRumbleRR | ★ |
| 180 | F32 | TireCombinedSlipFL | ★ 総合スリップ（0=グリップ、\|x\|>1=ロス） |
| 184 | F32 | TireCombinedSlipFR | ★ |
| 188 | F32 | TireCombinedSlipRL | ★ |
| 192 | F32 | TireCombinedSlipRR | ★ |
| 116 | S32 | WheelOnRumbleStripFL | ランブルストリップ上=1 |
| 236 | F32 | SmashableVelDiff | ★ 衝突速度差 m/s（FH6 追加フィールド） |
| 315 | U8  | Accel | 0〜255 |
| 316 | U8  | Brake | 0〜255 |
| 318 | U8  | HandBrake | |

### 新規: `core/rumble_udp_listener.py`

```
処理フロー:
  1. socket.bind(("0.0.0.0", port)) で UDP 待受（別スレッド）
  2. 324 バイト以外は無視
  3. IsRaceOn == 0 → rumble_manager に 0, 0 を送信してリターン
  4. 振動強度を計算（優先度順）:
       衝突    : SmashableVelDiff > 3.0 m/s → low=1.0, high=0.8 を 200ms
       スリップ : max(abs(TireCombinedSlip×4)) > 0.5 → high_freq に反映
       路面    : max(SurfaceRumble×4) を low_freq の主信号に使用
  5. rumble_manager の API を呼び出す（API は実装前にコード確認）
  6. タイムアウト: 最後のパケットから 1 秒以上経過したら 0, 0 を送信

インターフェース（rumble_manager.py の API 確認後に合わせること）:
  class RumbleUdpListener(threading.Thread):
      def __init__(self, rumble_manager, port: int): ...
      def stop(self): ...
```

### 編集: `main.py`

- `RumbleUdpListener` スレッドを起動・停止
- `config.json` の `"fh6_udp_port"` キーからポート読み取り（デフォルト: 5301）
- `--no-fh6-rumble` フラグで無効化

### 編集: `config.json`

```json
{
  "fh6_udp_port": 5301
}
```

### 参考実装

HorizonHaptics（https://github.com/haritha99ch/HorizonHaptics）
- `GameParsers/` : 324 バイトパーサー（Python）
- `worker.py` : SurfaceRumble・TireCombinedSlip を使った振動計算ロジック

FH5 との差異（オフセットがずれるので流用不可）:
`NumCylinders` の直後に `CarGroup`(U32)・`SmashableVelDiff`(F32)・`SmashableMass`(F32) が挿入されている

---

## 作業優先順序

```
1. test_bulk_rumble.py で物理振動確認（問題A ベースライン）
2. constants.py の init_sequence を SDL と比較・修正（問題A）
3. 入力スレッド分離（問題B、問題A と独立して対応可）
4. rumble_udp_listener.py 実装（問題A が解決してから）
5. main.py への統合
```

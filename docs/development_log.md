# pro2input FH6 UDP Rumble 開発記録

## 最終状態（2026-06-06 解決済み）

| 項目 | 状態 |
|------|------|
| UDP 受信（FH6 Data Out） | ✅ 正常（324-byte パケット受信中） |
| ランブル値計算 | ✅ 正常（Slip/Surface/Smash → large/small 変換） |
| コントローラー振動 | ✅ **解決済み** |
| ボタン入力 | ✅ 正常（遅延なし） |
| USB 安定性 | ✅ Interface 0/1 ともに libusbK |

---

## 解決した問題と根本原因

### 問題A: 振動が全くしなかった

**根本原因（2つ）:**

1. **誤ったエンドポイント**: 振動パケットを Interface 1 Bulk OUT（ep 0x02）に送っていた。
   正しいエンドポイントは **Interface 0 Interrupt OUT（ep 0x01）**。

2. **パケットオフセットのバグ**: `_build_report()` で SDL の `memcpy(&rumble_data[0x11], ...)` の
   `0x11`（16進 = 10進で **17**）を `11`（10進）と誤解し、右アクチュエータのコピー先が
   6バイトずれていた（`report[11:17]` → `report[17:23]` に修正）。

**発見方法:** `tools/rumble_comprehensive_test.py` で全エンドポイント・全フォーマットを網羅テスト。
Test 5（Interface 0 Interrupt OUT）で初めて物理振動を確認。

### 問題B: 振動がすぐ止まった

**根本原因（2つ）:**

1. **重複送信防止ロジック**: `send_rumble()` に「値が変わらなければパケットを作らない」
   チェックがあった。Switch 2 Pro のモーターは **継続的にパケットを受け取らないと停止する**
   ため、値が一定でも 12ms ごとに送り続ける必要がある。

2. **Interface 0 のドライバー競合**: Windows HID ドライバーと libusb が Interface 0 を
   共有していたため、USB 書き込みが断続的に失敗していた。
   → Zadig で Interface 0/1 ともに libusbK に統一して解決。

### 問題C: 入力遅延（副次的に解決）

pywinusb のコールバック方式から pyusb 専用スレッド方式に切り替えたことで解消。
ブロッキング `dev.read()` をデーモンスレッドに分離し、メインループはノンブロッキングで動作。

---

## 最終アーキテクチャ

```
Switch 2 Pro Controller (USB)
  │
  ├─ Interface 0 (libusbK via Zadig)
  │   ├─ ep 0x81  Interrupt IN  ← HID 入力レポート  [専用スレッド: USB-InputReader]
  │   └─ ep 0x01  Interrupt OUT ← 振動パケット送信   [メインループから 12ms ごと]
  │
  └─ Interface 1 (libusbK via Zadig)
      ├─ ep 0x02  Bulk OUT ← 初期化コマンド（起動時のみ）
      └─ ep 0x82  Bulk IN  ← 初期化レスポンス

Python プロセス
  ├─ main.py               メインループ（1ms tick）
  ├─ core/controller_usb.py  pyusb 通信（入力スレッド管理・振動送信）
  ├─ core/rumble_manager.py  振動状態管理（12ms 周期で継続送信）
  └─ core/rumble_udp_listener.py  FH6 UDP テレメトリ受信（専用スレッド）

FH6 → UDP port 5301 → rumble_udp_listener → rumble_manager → controller_usb → ep 0x01
```

---

## 振動パケット仕様（確定）

```
64バイト HID Output Report
  [0]     = 0x02  (Report ID)
  [1]     = 0x50 | (seq & 0x0F)  (シーケンス番号)
  [2:7]   = 左アクチュエータ 5バイト  (SDL EncodeHDRumble)
  [7:17]  = ゼロパディング
  [17:23] = [1:7] のコピー  (SDL: memcpy(&rumble_data[0x11], &rumble_data[0x01], 6))
  [23:64] = ゼロパディング
```

アクチュエータエンコーディング（SDL `EncodeHDRumble`）:
```python
data[0] = high_freq & 0xFF
data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
data[4] = (low_amp >> 8) & 0xFF
```

デフォルト周波数: HF = 0x0187（~600Hz）、LF = 0x0112（~260Hz）
振幅上限: 29000（SDL の safe maximum）

---

## Zadig 設定（必須）

| Interface | ドライバー | 用途 |
|-----------|-----------|------|
| Interface 0 | **libusbK** | 入力読み取り + 振動送信 |
| Interface 1 | **libusbK** | 初期化コマンド |

> ⚠️ Interface 0 を Windows HID（HidUsb）のままにすると、libusb との競合で
> 振動が断続的に停止する。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | エントリーポイント。UDP リスナー統合、`timeBeginPeriod(1)` |
| `core/constants.py` | デバイス定数、初期化コマンド、振動パラメータ |
| `core/controller_usb.py` | pyusb 通信。入力スレッド・振動送信（ep 0x01） |
| `core/rumble_manager.py` | 振動状態管理。12ms 周期継続送信 |
| `core/rumble_udp_listener.py` | FH6 UDP 受信・振動値計算。150ms ホールドタイム |
| `core/input_parser.py` | HID レポートのボタン・スティック解析 |
| `mapping/xbox360_mapper.py` | Switch → Xbox 360 ボタンマッピング |
| `tools/rumble_comprehensive_test.py` | 全エンドポイント振動テスト（診断用） |
| `tools/rumble_packet_test.py` | パケットオフセット検証テスト |

---

## 技術的な教訓

1. **エンドポイントの確認が最優先**: 振動は Interface 0 Interrupt OUT（ep 0x01）。
   Interface 1 Bulk OUT（ep 0x02）は初期化専用。`rumble_comprehensive_test.py` で
   全パターンをテストして判明。

2. **16進数と10進数の混同に注意**: SDL の `0x11` は 17（10進）。
   コメントや変数名に hex を書く場合は `0x` プレフィックスを必ずつける。

3. **Switch 2 Pro モーターは継続送信が必要**: パケットが止まると 100ms 以内にモーター停止。
   XInput の force-feedback と同じ動作。値が変わらなくても 12ms ごとに送り続ける。

4. **pyusb のみで完結可能**: pywinusb は不要。Interface 0/1 を libusbK で統一することで
   入力・振動・初期化すべてを pyusb で安定して処理できる。

5. **入力スレッド分離**: pyusb の blocking `dev.read()` をデーモンスレッドに移動し、
   メインループはキューからノンブロッキングで取得することで入力遅延を防ぐ。

---

---

## セッション 2（2026-06-08）: USB エンドポイント安定性

### 発生した問題

振動が動作中に突然停止し、その後のセッションでは最初の書き込みから errno 10060（タイムアウト）が発生して一切振動しなくなった。

### 原因の特定

**原因1: errno 32 後の errno 10060**

1. ep 0x01 が STALL する（errno 32 / EPIPE）
2. `clear_halt` を呼んでも STALL が完全に解消されず
3. 以降の書き込みが errno 10060 でタイムアウト

**原因2: `clear_halt` を非スタールエンドポイントに呼ぶと壊れる**

Windows + libusbK では、スタールしていないエンドポイントに `clear_halt` を呼ぶと
データトグルがデsync され、以降の全書き込みが errno 10060 でタイムアウトになる。

初期化時に「前セッションの STALL を解消しようとして」呼んだ `clear_halt` が
スタールしていない場合にエンドポイントを壊していた。

**原因3: STALL のセッション間持続**

前セッションで発生した STALL は Windows/libusbK ドライバー内部に残存する。
ソフトウェアリコネクト（`dispose_resources` → `find`）だけではリセットされない。
物理的な USB 抜き差しが必要。

**原因4: 振動失敗でのリコネクトが入力遅延を引き起こす**

振動失敗をトリガーにしたリコネクトが `mapper.reset()` を呼び、
仮想コントローラーの入力が毎 1.3 秒リセットされていた（入力遅延の原因）。

### 最終的な修正

1. `initialize_hid_mode()` から `clear_halt` を完全削除（非スタール時に破壊的）
2. 振動失敗でのリコネクトトリガーを削除
3. 50 回連続失敗でその session の振動を停止（入力には影響しない）
4. 物理切断（errno 5・19）のみがリコネクトをトリガー
5. 振動 write タイムアウトを 50ms → 15ms に短縮（失敗時のブロック時間削減）

### 得られた教訓

- `clear_halt` は errno 32 が発生した場合のみ呼ぶ
- ドライバーレベルの STALL 持続は物理 replug でのみリセットできる
- 振動の障害と入力の障害を切り離す（振動が壊れても入力を維持する）

---

## 参考リンク

- SDL ソース: https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_switch2.c
- HorizonHaptics（FH5/FH6 振動参照）: https://github.com/haritha99ch/HorizonHaptics
- NSW2-controller-enabler: https://github.com/ikz87/NSW2-controller-enabler

# pro2input FH6 UDP Rumble 開発記録

## 現在の状態（2026-06-06）

| 項目 | 状態 |
|------|------|
| UDP 受信（FH6 Data Out） | ✅ 正常（324-byte パケット受信中） |
| ランブル値計算 | ✅ 正常（Slip/Surface/Smash → large/small 変換） |
| Bulk OUT 書き込み | ✅ エラーなし（200ms タイムアウト設定） |
| ボタン入力 | ✅ 正常（遅延解消） |
| **コントローラー振動** | ❌ **未解決（物理的に感じない）** |

---

## 実装済みの変更

### 1. FH6 UDP テレメトリ リスナー (`core/rumble_udp_listener.py`)

- 324-byte UDP パケットをパース
- `RaceOn`, `SurfaceRumble`, `TireCombinedSlip`, `SmashableVelDiff` を抽出
- 優先度順: 衝突 > スリップ > サーフェス
- `RumbleManager.send_rumble(large, small)` に送信

### 2. ランブル送信方法の変更

**変更前:** pywinusb HID Output Report → Write timed out
**変更後:** pyusb Interface 1 Bulk OUT → エラーなし

`controller_usb.py` のアーキテクチャ変更:
- pywinusb: Interface 0 HID 入力読み取り（コールバック方式）
- pyusb: Interface 1 Bulk OUT（init + rumble）
- Interface 1 は claim したまま保持（解放しない）

### 3. SDL 準拠の初期化シーケンス

`core/constants.py` に追加:
- `READ_FLASH_COMMANDS`: 5 つのアドレス（0x13000〜0x13100）
- `INIT_COMMANDS`: SDL の 10 コマンド順序
- パケット送信長: `cmd[5] + 8` バイト（SDL 規則）

### 4. 入力遅延解消

- `timeBeginPeriod(1)` で Windows タイマー解像度を 1ms に設定
- `time.sleep(0.001)` で CPU yield（pywinusb コールバック用）
- pywinusb のコールバック方式はノンブロッキングで遅延なし

### 5. ボタンビットマスク修正

`core/input_parser.py`:
- SDL の `HandleSwitchProState` と一致するオフセット（payload[4:8]）
- 正しいビットマスク（bit0=Y, bit1=X, bit2=B, bit3=A）
- 文字ベースマッピング（Switch の文字配置をそのまま Xbox に渡す）

---

## 未解決の問題

### 問題A: 振動が全くしない

**症状:**
- UDP からランブル値は計算されている（`small=204` 等）
- Bulk OUT 書き込みは成功を示唆（エラーなし）
- コントローラー物理的に振動しない

**検証済み:**
- `test_bulk_rumble.py`（旧スクリプト）は現在実行不可（デバイス状態変化のため）
- pywinusb 排除後、Bulk OUT はエラーなしに変更
- ReadFlashBlock + SDL init シーケンス追加済み
- パケット送信長 `cmd[5]+8` 対応済み

**残存の仮説:**
1. **パケットフォーマット不正**: `RumbleManager._build_report()` のバイトレイアウトが SDL と異なる
   - SDL: `memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)` でシーケンス番号コピー
   - 現在: `[11:17] = [1:7]` に変更済みだが、実際の振動未確認
2. **Actuator エンコーディング**: `EncodeHDRumble` の 5 バイト構造が SDL と異なる可能性
3. **コントローラー側の rumble 無効化**: Init シーケンス中の rumble 有効化コマンドが不十分
4. **Zadig 設定**: Interface 1 のドライバーが libusbK ではなく WinUSB の可能性

### 問題B: テストスクリプトの再現性

**症状:**
- `test_bulk_rumble.py`（一時ファイル）が現在は `Operation timed out` で失敗
- 原因: `main.py` 実行後のデバイス状態（Interface 1 claim 状態）が影響

**解決策:**
- コントローラー物理的に再接続してからテスト実行が必要

---

## 推奨される次のアクション

### 優先度 1: 振動の最小検証

```bash
# 1. コントローラーを物理的に再接続（USB 抜き差し）
# 2. test_bulk_rumble.py を再実行して、物理振動を確認
python "C:\Users\zutuu\AppData\Local\Temp\opencode\test_bulk_rumble.py"
```

**確認項目:**
- コントローラーが手に持って振動を感じるか
- 成功すればパケットフォーマットは OK → `main.py` 側の問題
- 失敗すればパケットフォーマット or init シーケンスの問題

### 優先度 2: Zadig 設定確認

1. Zadig を開く
2. Options → List All Devices
3. "Switch Pro Controller" を選択
4. Interface 1 が **libusbK** になっているか確認（WinUSB ではなく）
5. 必要に応じて libusbK に再インストール

### 優先度 3: SDL パケットダンプ

SDL の `UpdateRumble` 関数の実際の出力バイト列をキャプチャ：

```c
// SDL_hidapi_switch2.c の UpdateRumble 関数
// rumble_data[0..63] の実際の値を確認
```

Python 側の `_build_report()` と比較して差異を特定。

### 優先度 4: 代替アプローチ

SDL の hidapi C ライブラリを Python から直接呼び出す：

```bash
pip install hidapi
```

`hidapi` パッケージは SDL と同じ libusb/hidapi バックエンドを使用し、Switch 2 Pro の rumble を正しく動作させる可能性がある。

---

## ファイル変更一覧

| ファイル | 変更内容 |
|---|---|
| `core/constants.py` | SDL init シーケンス、ReadFlashBlock、LED_COMMAND、RUMBLE_NEUTRAL_ACTUATOR |
| `core/controller_usb.py` | pyusb Bulk OUT + pywinusb HID 入力ハイブリッド |
| `core/input_parser.py` | SDL 準拠のボタンオフセットとビットマスク |
| `core/rumble_manager.py` | 12ms 間引き、Bulk OUT 送信、エラー抑制 |
| `core/rumble_udp_listener.py` | 新規: FH6 UDP パケットパースと振動計算 |
| `main.py` | UDP リスナー統合、`timeBeginPeriod(1)`、`--no-udp` フラグ |
| `config/settings.py` | `fh6_udp` デフォルト設定追加 |
| `config.json` | `fh6_udp` 設定保存 |
| `start.bat` | `%*` 引数対応 |
| `start_no_udp.bat` | 新規: UDP 無効で起動 |
| `README.md` | FH6 UDP 振動機能のドキュメント追加 |
| `docs/rumble_debug.md` | デバッグレポート v1 |
| `docs/rumble_debug_v2.md` | デバッグレポート v2 |
| `docs/fh6_rumble_udp_context.md` | ユーザーの詳細レポート |
| `docs/development_log.md` | **本ファイル** |

---

## 技術的な教訓

1. **pywinusb + pyusb 共存**: pywinusb が HID デバイスを開くと pyusb の Bulk OUT が無効化される。ハイブリッド方式では Interface 1 を claim したままにする必要がある。
2. **SDL のパケット長規則**: `cmd[5] + 8` バイトで送信。固定長送信では不十分。
3. **ReadFlashBlock の重要性**: SDL は init 前に 5 つのフラッシュ読み取りを行う。これが rumble 有効化の前提条件の可能性がある。
4. **Windows タイマー解像度**: `timeBeginPeriod(1)` がないと `time.sleep(0.001)` が 15ms になって入力遅延を生む。
5. **ブロッキング vs コールバック**: pyusb の Interrupt IN はブロッキングで遅延を生む。pywinusb のコールバック方式が最適。

---

## 参考リンク

- SDL ソース: https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_switch2.c
- HorizonHaptics（FH5/FH6 振動参照）: https://github.com/haritha99ch/HorizonHaptics
- NSW2-controller-enabler: https://github.com/ikz87/NSW2-controller-enabler

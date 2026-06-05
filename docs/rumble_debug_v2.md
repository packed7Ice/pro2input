# FH6 UDP Rumble デバッグレポート v2

## テスト日時
2026-06-06

## 現在の状態

| 項目 | 状態 |
|---|---|
| UDP 受信 | ✅ 正常（FH6 からパケット受信中） |
| ランブル値計算 | ✅ 正常（Slip/Surface/Collision → large/small 変換） |
| Bulk OUT 書き込み | ✅ エラーなし（pywinusb 排除後、タイムアウト解消） |
| コントローラー振動 | ❌ **依然なし** |
| ボタン入力 | ⚠️ 初期正常 → **後半で遅延再発** |

## 変更履歴と結果

### 変更 1: pywinusb → pyusb-only

**変更内容:**
- pywinusb を完全に排除
- Interface 0 (HID) も pyusb で直接読み取り（Interrupt IN）
- `auto_detach_kernel_driver=True` で両インターフェース claim

**結果:**
- ✅ Bulk OUT タイムアウトが完全に消滅
- ❌ 振動は依然としてしない
- ❌ 入力遅延が再発（ログ後半で顕著）

## 未解決の問題

### 1. 振動が全くしない

**症状:**
- UDP からランブル値は計算されている（`small=204` 等）
- Bulk OUT 書き込みはエラーなし（成功を示唆）
- コントローラー物理的に振動しない

**仮説:**
1. **パケットフォーマット不正**: SDL の `memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)` と `RumbleManager` の実装が異なる
2. **初期化不足**: SDL は `ReadFlashBlock`（キャリブレーション読み取り）等を送信。これらが rumble 有効化の前提条件か
3. **コントローラー側の rumble 無効化**: Init シーケンス中に rumble を有効にするコマンドが欠落している可能性
4. **パワー管理**: コントローラーが low-power モードで振動を無視している可能性

### 2. 入力遅延

**症状:**
- 起動直後は入力が正常
- 数分経過後、ボタン反応が遅くなる

**原因分析:**
- pyusb の `read()` はブロッキング呼び出し（100ms タイムアウト）
- pywinusb のコールバック方式はノンブロッキングだった
- `drain_and_send()` + `read()` + `time.sleep(0.001)` のループが、UDP パケット処理と vgamepad 更新の競合を生じている可能性

## 検証が必要な項目

- [ ] `test_bulk_rumble.py` を再実行し、物理的な振動を確認（pywinusb なしの状態で）
- [ ] SDL の `UpdateRumble` パケットと `RumbleManager._build_report()` をバイトレベルで比較
- [ ] `ReadFlashBlock`（0x13000, 0x13040 等）を Init シーケンスに追加
- [ ] 振動有効化コマンド（`0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00`）が正しい位置に含まれているか確認
- [ ] 入力遅延: `read_input` をスレッド化または非同期化

## 根底の問題

Switch 2 Pro Controller の rumble プロトコルは以下の複雑さがある：

1. **Dual-path 初期化**: Interface 1 (Bulk) で init → Interface 0 (HID) で rumble report
2. **HID Output Report 書き込み失敗**: Windows HID ドライバーが Switch 2 Pro の特定 report を拒否
3. **Bulk OUT 制限**: pywinusb 共存で無効化される、または pyusb-only でも別の要因で無効
4. **SDL の挙動**: SDL は hidapi 層から libusb デバイスハンドルを取得して Bulk OUT を使用。これは pyusb 単体とは異なる

## 次のアクション案

1. **最小構成テスト**: `test_bulk_rumble.py` を再実行（振動するか確認）
2. **パケットダンプ**: SDL の実際の Bulk OUT パケットをキャプチャして比較
3. **ReadFlashBlock 追加**: SDL の完全な init シーケンスを再現
4. **別アプローチ検討**: SDL の hidapi C ライブラリを Python から直接呼び出す（`hidapi` Python パッケージ等）

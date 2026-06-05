# FH6 UDP Rumble Debug Report

## 現在の状態

| 項目 | 状態 |
|---|---|
| UDP 受信 | ✅ 正常（FH6 から 324-byte パケット受信中） |
| ランブル値計算 | ✅ 正常（Slip/Surface/Collision → large/small 変換） |
| Bulk OUT 書き込み | ✅ エラーなし（200ms タイムアウト、静かに失敗） |
| コントローラー振動 | ❌ **なし**（物理的に感じない） |
| ボタン入力 | ✅ 正常（遅延解消済み） |

## 問題の切り分け履歴

### テスト済みパターン

| テスト | 結果 | 備考 |
|---|---|---|
| `test_bulk_rumble.py` (pyusb のみ) | Bulk 書き込み成功 | **振動したか不明**（"SUCCESS" は転送成功のみ） |
| `main.py` + pywinusb + pyusb | Bulk 書き込み成功 | **振動なし** |

### 仮説

1. **pyusb/pywinusb 共存問題**: pywinusb が HID デバイスを開くと、pyusb の Bulk OUT が「成功」を返しても実際にはコントローラーに届いていない可能性
2. **パケットフォーマット**: SDL の `memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)` と RumbleManager の実装に差異がある可能性
3. **Init シーケンス不足**: SDL は `ReadFlashBlock` 等の追加コマンドを送信している

## 検証項目

- [ ] pyusb のみで振動するか（pywinusb 完全排除）
- [ ] パケットコピー位置を SDL 厳密一致に変更
- [ ] Interface 0 も libusbK にして pyusb 統一の検討

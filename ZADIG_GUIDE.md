# Zadig セットアップガイド（Switch 2 Pro Controller）

## 状況

現在の Windows 標準 HID ドライバーでは、Switch 2 Pro Controller (VID 0x057E / PID 0x2069) への書き込み（Output Report / Feature Report）が拒否されています。

- `WriteFile` → `Error 87` (ERROR_INVALID_PARAMETER)
- `HidD_SetFeature` → `Error 1` (ERROR_INVALID_FUNCTION)

このため、**Zadig** を使用して該当インターフェースのドライバーを **WinUSB** に置き換える必要があります。

---

## 手順

### 1. Zadig をダウンロード

https://zadig.akeo.ie

「Zadig 2.8」または最新版をダウンロードして実行してください。

### 2. デバイスリストの表示

Zadig を開いたら、メニューから以下を選択：

```
Options -> List All Devices
```

（チェックが入ると、すべてのデバイスがリストに表示されます）

### 3. 対象デバイスの選択

ドロップダウンリストから以下のいずれかを探して選択してください：

- `Nintendo Switch Pro Controller`
- `Nintendo Co., Ltd. Pro Controller`
- `HID-compliant vendor-defined device` (VID_057E&PID_2069)

**注意：** 選択したデバイスの **USB ID** が右側に表示されます。  
必ず `057E` / `2069` になっていることを確認してください。

### 4. インターフェースの確認

Zadig のウィンドウ下部に **Interface 0**、**Interface 1** などの表示がある場合：

- **Interface 0**: 通常は標準 HID（Windows が自動的に管理）
- **Interface 1** 以降: ベンダー固有の生プロトコル（こちらを置き換えたい）

**今回の診断結果** (`mi_00` のみ検出) から、おそらく **Interface 0** のみが有効になっています。

### 5. ドライバーの置き換え

1. **Driver** の欄を `WinUSB` に変更（デフォルトが `HidUsb` になっているはず）
2. **Replace Driver** ボタンをクリック
3. 処理が完了するまで待つ（1〜2分かかる場合あり）

### 6. 確認

置き換え後、デバイスマネージャー (`devmgmt.msc`) を開いて確認：

- `Nintendo Switch Pro Controller` の下に `WinUSB Device` と表示されるはず
- （もし `libusbK` を選んだ場合は `libusbK Device` と表示される）

### 7. スクリプトの再実行

Zadig 完了後、以下を再実行：

```powershell
python switch2_procon_init_test.py
```

または：

```powershell
python feature_init_test.py
```

今度は WriteFile / HidD_SetFeature が成功し、コントローラーからデータが流れてくるはずです。

---

## 注意事項・トラブルシューティング

### A. Zadig でデバイスが見つからない
- `Options -> List All Devices` がオンになっているか確認
- コントローラーの USB ケーブルを一度抜き差しする
- 別の USB ポートを試す

### B. 「Access is denied」や「System cannot find the file specified」
- Zadig を**管理者として実行**し直す
- 他のアプリ（Steam、BetterJoy等）をすべて終了する

### C. ドライバー置き換え後、コントローラーがゲームで使えなくなった
- Zadig で `Options -> List All Devices` をオンにし、該当デバイスを選択
- **Reinstall Driver** をクリックして元の `HidUsb` に戻すことができる

### D. 複数のインターフェースがある場合
- Nintendo コントローラーは通常 **2つの HID インターフェース** を持ちます
- `Interface 0` と `Interface 1` の両方を **WinUSB** に置き換える必要がある場合もあります
- 片方だけ置き換えてもう片方が `HidUsb` のままだと、競合が起きることがあります

---

## 次のステップ

Zadig 完了後、再度 `switch2_procon_init_test.py` を実行してください。

結果として以下が期待されます：

```
[OK ] WriteFile succeeded (64 bytes)
RECV [64]: 30 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ...  <-- CHANGE
```

初期化成功のダンプが流れたら、次の **フェーズ2（パケット解析・マッピング）** に進みます。

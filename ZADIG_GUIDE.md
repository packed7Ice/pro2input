# Zadig セットアップガイド（Switch 2 Pro Controller）

## 状況

現在の Windows 標準 HID ドライバーでは、Switch 2 Pro Controller (VID 0x057E / PID 0x2069) への書き込み（Output Report / Feature Report）が拒否されています。

- `WriteFile` → `Error 87` (ERROR_INVALID_PARAMETER)
- `HidD_SetFeature` → `Error 1` (ERROR_INVALID_FUNCTION)

このため、**Zadig** を使用して該当インターフェースのドライバーを **libusbK** に置き換える必要があります。

**なぜ libusbK を選ぶのか？**

- WinUSB に置き換えても、Windows 標準の `WriteFile` / `ReadFile` ではなく **WinUSB API** が必要になります
- libusbK は **WinUSB 互換 API** を提供し、さらに `UsbK_ReadPipe` / `UsbK_WritePipe` など使いやすい関数を持っています
- Nintendo Switch コミュニティでは libusbK が広く使用されています

---

## 手順

### 1. Zadig をダウンロード

https://zadig.akeo.ie

「Zadig 2.8」または最新版をダウンロードして実行してください。

### 2. Zadig を管理者として実行

Zadig を**右クリック →「管理者として実行」**してください。

### 3. デバイスリストの表示

Zadig を開いたら、メニューから以下を選択：

```
Options -> List All Devices
```

（チェックが入ると、すべてのデバイスがリストに表示されます）

### 4. 対象デバイスの選択

ドロップダウンリストから以下のいずれかを探して選択してください：

- `Nintendo Switch Pro Controller`
- `Nintendo Co., Ltd. Pro Controller`
- `HID-compliant vendor-defined device` (VID_057E&PID_2069)

**注意：** 選択したデバイスの **USB ID** が右側に表示されます。  
必ず `057E` / `2069` になっていることを確認してください。

### 5. インターフェースの確認

Zadig のウィンドウ下部に **Interface 0**、**Interface 1** などの表示がある場合：

- **Interface 0**: 通常は標準 HID（Windows が自動的に管理）
- **Interface 1** 以降: ベンダー固有の生プロトコル（こちらを置き換えたい）

**今回の診断結果** (`mi_00` と `mi_01` が検出) から、**両方のインターフェース** を libusbK に置き換える必要があります。

### 6. ドライバーを libusbK に変更

1. **Driver** の欄をクリックし、**`libusbK (v3.0.7.0)`** を選択
   - デフォルトは `HidUsb` または `WinUSB` になっているはず
   - ドロップダウンリストから `libusbK` を選ぶ
2. **Replace Driver** ボタンをクリック
3. 処理が完了するまで待つ（1〜2分かかる場合あり）
4. **もう1つのインターフェース（Interface 1）も同様に libusbK に置き換える**

> ⚠️ **重要**：Interface 0 と Interface 1 の **両方** を libusbK に置き換えてください。片方だけだとうまく動作しない場合があります。

### 7. 確認

置き換え後、デバイスマネージャー (`devmgmt.msc`) を開いて確認：

- `Nintendo Switch Pro Controller` の下に `libusbK Device` と表示されるはず
- `Interface 0` と `Interface 1` の両方が `libusbK` になっていることを確認

### 8. USB ケーブルの抜き差し

ドライバー置き換え後、**USB ケーブルを一度抜いてから再接続**してください。
これにより、新しいドライバーが正しく読み込まれます。

### 9. スクリプトの実行

```powershell
python libusbk_init_test.py
```

---

## 注意事項・トラブルシューティング

### A. Zadig でデバイスが見つからない
- `Options -> List All Devices` がオンになっているか確認
- コントローラーの USB ケーブルを一度抜き差しする
- 別の USB ポートを試す
- **管理者として実行**しているか確認

### B. 「Access is denied」や「System cannot find the file specified」
- Zadig を**管理者として実行**し直す
- 他のアプリ（Steam、BetterJoy等）をすべて終了する

### C. ドライバー置き換え後、コントローラーがゲームで使えなくなった
- Zadig で `Options -> List All Devices` をオンにし、該当デバイスを選択
- **Reinstall Driver** をクリックして元の `HidUsb` に戻すことができる
- 元に戻すと、今回のスクリプトは動作しなくなります（ゲームだけで使いたい場合）

### D. WinUSB から libusbK への変更
- 既に WinUSB に置き換えている場合は、同じデバイスを選択して Driver を `libusbK` に変更するだけ
- **Replace Driver** をクリックすると、WinUSB が libusbK に上書きされます
- 問題があれば、**Reinstall Driver** または **Delete Driver** を使って元に戻せます

### E. 複数のインターフェースがある場合
- Nintendo コントローラーは通常 **2つの HID インターフェース** を持ちます
- `Interface 0` と `Interface 1` の**両方**を libusbK に置き換える必要があります
- 片方だけ置き換えてもう片方が `HidUsb` のままだと、競合が起きることがあります

---

## 次のステップ

libusbK への置き換えが完了し、USB ケーブルを抜き差しした後、以下を実行してください：

```powershell
python libusbk_init_test.py
```

結果として以下が期待されます：

```
[OK ] UsbK_WritePipe succeeded (64 bytes)
RECV [64]: 30 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ...  <-- CHANGE
```

初期化成功のダンプが流れたら、次の **フェーズ2（パケット解析・マッピング）** に進みます。

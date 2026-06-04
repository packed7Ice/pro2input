# Switch 2 Pro Controller to XInput Converter

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![GitHub stars](https://img.shields.io/github/stars/packed7Ice/pro2input?style=social)](https://github.com/packed7Ice/pro2input/stargazers)

[English](#english) | [日本語](#japanese)

---

<a id="english"></a>
## English

A Python-based USB input converter that maps **Nintendo Switch 2 Pro Controller** inputs to a virtual **Xbox 360 (XInput)** gamepad on Windows.

### Features

- **Full Button Mapping** — Face buttons, shoulder buttons, D-Pad, system buttons
- **Analog Stick Support** — Both left and right sticks with correct axis polarity
- **Trigger Synthesis** — ZL/ZR digital buttons mapped to analog LT/RT triggers
- **HD Rumble Feedback** — Experimental force-feedback support via SDL-derived protocol
- **Modular Architecture** — Clean separation of USB transport, input parsing, and mapping layers

### Requirements

- Windows 10/11
- Python 3.10+
- Nintendo Switch 2 Pro Controller (USB connection)
- [ViGEmBus Driver](https://github.com/nefarius/ViGEmBus) (for virtual Xbox 360 controller)
- [libusb-1.0.dll](https://libusb.info/) (placed in `C:\\Windows\\System32`)
- [Zadig](https://zadig.akeo.ie/) (to install libusbK driver for Interface 1)

### Installation

```bash
# Clone the repository
git clone https://github.com/packed7Ice/pro2input.git
cd pro2input

# Install Python dependencies
pip install pyusb vgamepad
```

### Driver Setup (Zadig)

1. Connect your Switch 2 Pro Controller via USB.
2. Open Zadig, go to **Options → List All Devices**.
3. Select **"Switch Pro Controller"** (or similar).
4. For **Interface 1**, install the **libusbK** driver.
5. **Keep Interface 0 on the Windows HID driver** (`HidUsb`) for rumble support.

### Usage

Run the main converter:

```bash
python main.py
```

The script will:
1. Create a virtual Xbox 360 controller
2. Find and initialize the Switch 2 Pro Controller
3. Start the input loop with rumble feedback enabled

#### Rumble Test

To verify rumble is working:

```bash
# Terminal 1: start the converter
python main.py

# Terminal 2: send test vibration
python tools/xinput_rumble_test.py
```

### Project Structure

```
pro2input/
├── main.py                      # Entry point
├── core/
│   ├── constants.py             # Device IDs, init commands, rumble constants
│   ├── controller_usb.py        # USB connection and HID I/O
│   ├── input_parser.py           # Button/stick/trigger parsing
│   └── rumble_manager.py         # XInput → Switch 2 Pro rumble conversion
├── mapping/
│   └── xbox360_mapper.py        # Virtual Xbox 360 gamepad mapping
├── tools/                       # Test & diagnostic scripts
├── docs/                        # Setup guides
└── LICENSE                      # Apache 2.0
```

### Tools

| Script | Purpose |
|--------|---------|
| `tools/button_test.py` | Verify button mapping |
| `tools/stick_raw_diagnostic.py` | Inspect raw stick values |
| `tools/xinput_rumble_test.py` | Test XInput force-feedback |
| `tools/rumble_hid_control_test.py` | Direct USB rumble debug |

### Troubleshooting

**Controller not found**
- Ensure the controller is powered on and connected via USB.
- Verify the libusbK driver is installed for Interface 1 via Zadig.

**No input in games**
- Make sure `main.py` is running. The virtual controller only exists while the script is active.
- Check that ViGEmBus is installed correctly.

**Rumble not working**
- Ensure Interface 0 remains on the Windows HID driver (`HidUsb`).
- Run `tools/xinput_rumble_test.py` while `main.py` is active.

### Acknowledgments

- Rumble protocol derived from the official **SDL** implementation (`SDL_hidapi_switch2.c`).
- USB initialization sequence based on **NSW2-controller-enabler** by ikz87.

### License

This project is licensed under the **Apache License 2.0**.
See [LICENSE](LICENSE) for details.

---

<a id="japanese"></a>
## 日本語

**Nintendo Switch 2 Pro コントローラー**の入力を Windows 上で仮想 **Xbox 360（XInput）** ゲームパッドとして動作させる Python 製 USB 入力変換ツールです。

### 機能

- **フルボタンマッピング** — フェイスボタン、ショルダーボタン、十字キー、システムボタン
- **アナログスティック対応** — 左右スティックともに正しい軸方向で動作
- **トリガー合成** — ZL/ZR のデジタルボタンをアナログ LT/RT トリガーに変換
- **HD 振動フィードバック** — SDL 導出プロトコルによる実験的な振動対応
- **モジュール化アーキテクチャ** — USB 通信、入力解析、マッピングを明確に分離

### 必要条件

- Windows 10/11
- Python 3.10 以降
- Nintendo Switch 2 Pro コントローラー（USB 接続）
- [ViGEmBus ドライバー](https://github.com/nefarius/ViGEmBus)（仮想 Xbox 360 コントローラー用）
- [libusb-1.0.dll](https://libusb.info/)（`C:\\Windows\\System32` に配置）
- [Zadig](https://zadig.akeo.ie/)（Interface 1 用 libusbK ドライバーインストール）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/packed7Ice/pro2input.git
cd pro2input

# Python 依存関係をインストール
pip install pyusb vgamepad
```

### ドライバー設定（Zadig）

1. Switch 2 Pro コントローラーを USB で接続します。
2. Zadig を開き、**Options → List All Devices** を選択します。
3. **"Switch Pro Controller"**（または類似の名前）を選択します。
4. **Interface 1** に対して **libusbK** ドライバーをインストールします。
5. **Interface 0 は Windows 標準 HID ドライバー（`HidUsb`）のままにします** — 振動機能のため必要です。

### 使い方

メインの変換スクリプトを実行します：

```bash
python main.py
```

実行すると以下が行われます：
1. 仮想 Xbox 360 コントローラーの作成
2. Switch 2 Pro コントローラーの検出と初期化
3. 振動フィードバック付き入力ループの開始

#### 振動テスト

振動が動作するか確認するには：

```bash
# ターミナル 1: 変換スクリプトを起動
python main.py

# ターミナル 2: テスト振動を送信
python tools/xinput_rumble_test.py
```

### プロジェクト構成

```
pro2input/
├── main.py                      # エントリーポイント
├── core/
│   ├── constants.py             # デバイスID、初期化コマンド、振動定数
│   ├── controller_usb.py        # USB接続とHID入出力
│   ├── input_parser.py           # ボタン・スティック・トリガー解析
│   └── rumble_manager.py         # XInput → Switch 2 Pro 振動変換
├── mapping/
│   └── xbox360_mapper.py        # 仮想 Xbox 360 ゲームパッドマッピング
├── tools/                       # テスト・診断スクリプト群
├── docs/                        # セットアップガイド
└── LICENSE                      # Apache 2.0
```

### ツール一覧

| スクリプト | 用途 |
|------------|------|
| `tools/button_test.py` | ボタンマッピングの確認 |
| `tools/stick_raw_diagnostic.py` | スティック生値の確認 |
| `tools/xinput_rumble_test.py` | XInput 振動のテスト |
| `tools/rumble_hid_control_test.py` | USB 直振動デバッグ |

### トラブルシューティング

**コントローラーが認識されない**
- コントローラーの電源が入り、USB で接続されていることを確認してください。
- Zadig で Interface 1 に libusbK ドライバーがインストールされているか確認してください。

**ゲーム内で入力が効かない**
- `main.py` が実行中であることを確認してください。仮想コントローラーはスクリプト実行中のみ存在します。
- ViGEmBus が正しくインストールされているか確認してください。

**振動しない**
- Interface 0 が Windows 標準 HID ドライバー（`HidUsb`）のままであることを確認してください。
- `main.py` 実行中に `tools/xinput_rumble_test.py` を実行してみてください。

### 謝辞

- 振動プロトコルは公式 **SDL** 実装（`SDL_hidapi_switch2.c`）から導出しました。
- USB 初期化シーケンスは ikz87 氏の **NSW2-controller-enabler** を参考にしました。

### ライセンス

このプロジェクトは **Apache License 2.0** の下でライセンスされています。
詳細は [LICENSE](LICENSE) をご覧ください。

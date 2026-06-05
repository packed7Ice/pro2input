# pro2input: FH6 UDP テレメトリ振動対応 — コーディングコンテキスト

## 目的

`core/rumble_udp_listener.py` を新規作成し、`main.py` に組み込む。
FH6 の Data Out（UDP テレメトリ）を受信して `rumble_manager.py` の既存 API を呼び出す。

---

## リポジトリ

`https://github.com/packed7Ice/pro2input`

```
pro2input/
├── main.py                  # エントリーポイント（要編集）
├── core/
│   ├── constants.py
│   ├── controller_usb.py
│   ├── input_parser.py
│   └── rumble_manager.py    # 既存の振動送信モジュール（要調査）
├── mapping/
│   └── xbox360_mapper.py
└── tools/
    └── fh6_rumble_debug.py  # 既存デバッグツール（参考）
```

作業前に `rumble_manager.py` の公開 API（関数名・引数・型）を必ず確認すること。

---

## 背景（要約）

- pro2input は Switch 2 Pro コントローラーを ViGEmBus 仮想 Xbox 360 として PC に認識させる Python ツール
- FH6（Game Pass 版）は ViGEmBus 仮想デバイスに振動データを送信しない（GameInput API の制限）
- FH6 には公式の UDP テレメトリ出力（Data Out）機能があり、ローカル送信（127.0.0.1）に対応している
- この UDP パケットには路面振動値・スリップ値・衝突値が含まれており、これを振動の入力源として使う

---

## FH6 Data Out 仕様

- **設定箇所**: Settings → HUD and Gameplay → Data Out → ON  
- **IP**: `127.0.0.1`（ユーザーが設定）  
- **ポート**: デフォルト `5300`（ユーザーが設定）  
  ⚠️ ゲーム側が 5200〜5300 を送信ソケットに使うため、**5301 以降を推奨**
- **方向**: ゲーム → 外部アプリの一方向 UDP のみ
- **送信タイミング**: プレイヤーが運転中のみ（メニュー・ポーズ中は送信なし）
- **パケットサイズ**: 固定 324 バイト、エンディアン: リトルエンディアン

### 振動に使えるフィールド（バイトオフセット・型・説明）

全フィールドのオフセットは先頭から順番に積み上げる（パディングなし）。
主要フィールドのオフセット一覧（先頭から）:

| オフセット | 型   | フィールド名 | 説明 |
|-----------|------|-------------|------|
| 0         | S32  | IsRaceOn | レース中=1, メニュー=0 |
| 4         | U32  | TimestampMS | タイムスタンプ |
| 8         | F32  | EngineMaxRpm | |
| 12        | F32  | EngineIdleRpm | |
| 16        | F32  | CurrentEngineRpm | |
| 20        | F32  | AccelerationX | |
| 24        | F32  | AccelerationY | |
| 28        | F32  | AccelerationZ | |
| 32        | F32  | VelocityX | |
| 36        | F32  | VelocityY | |
| 40        | F32  | VelocityZ | |
| 44        | F32  | AngularVelocityX | |
| 48        | F32  | AngularVelocityY | |
| 52        | F32  | AngularVelocityZ | |
| 56        | F32  | Yaw | |
| 60        | F32  | Pitch | |
| 64        | F32  | Roll | |
| 68        | F32  | NormalizedSuspensionTravelFL | |
| 72        | F32  | NormalizedSuspensionTravelFR | |
| 76        | F32  | NormalizedSuspensionTravelRL | |
| 80        | F32  | NormalizedSuspensionTravelRR | |
| 84        | F32  | TireSlipRatioFL | 0=グリップ, \|x\|>1=ロス |
| 88        | F32  | TireSlipRatioFR | |
| 92        | F32  | TireSlipRatioRL | |
| 96        | F32  | TireSlipRatioRR | |
| 100       | F32  | WheelRotationSpeedFL | |
| 104       | F32  | WheelRotationSpeedFR | |
| 108       | F32  | WheelRotationSpeedRL | |
| 112       | F32  | WheelRotationSpeedRR | |
| 116       | S32  | WheelOnRumbleStripFL | 1=ランブルストリップ上 |
| 120       | S32  | WheelOnRumbleStripFR | |
| 124       | S32  | WheelOnRumbleStripRL | |
| 128       | S32  | WheelOnRumbleStripRR | |
| 132       | S32  | WheelInPuddleFL | |
| 136       | S32  | WheelInPuddleFR | |
| 140       | S32  | WheelInPuddleRL | |
| 144       | S32  | WheelInPuddleRR | |
| 148       | F32  | **SurfaceRumbleFL** | ★ force feedback 用路面振動値 |
| 152       | F32  | **SurfaceRumbleFR** | ★ |
| 156       | F32  | **SurfaceRumbleRL** | ★ |
| 160       | F32  | **SurfaceRumbleRR** | ★ |
| 164       | F32  | TireSlipAngleFL | |
| 168       | F32  | TireSlipAngleFR | |
| 172       | F32  | TireSlipAngleRL | |
| 176       | F32  | TireSlipAngleRR | |
| 180       | F32  | TireCombinedSlipFL | 総合スリップ, 0=グリップ |
| 184       | F32  | TireCombinedSlipFR | |
| 188       | F32  | TireCombinedSlipRL | |
| 192       | F32  | TireCombinedSlipRR | |
| 196       | F32  | SuspensionTravelMetersFL | |
| 200       | F32  | SuspensionTravelMetersFR | |
| 204       | F32  | SuspensionTravelMetersRL | |
| 208       | F32  | SuspensionTravelMetersRR | |
| 212       | S32  | CarOrdinal | |
| 216       | S32  | CarClass | |
| 220       | S32  | CarPerformanceIndex | |
| 224       | S32  | DrivetrainType | |
| 228       | S32  | NumCylinders | |
| 232       | U32  | CarGroup | ★ FH6 追加フィールド |
| 236       | F32  | **SmashableVelDiff** | ★ 衝突速度差(m/s) FH6追加 |
| 240       | F32  | SmashableMass | FH6追加 |
| 244       | F32  | PositionX | |
| 248       | F32  | PositionY | |
| 252       | F32  | PositionZ | |
| 256       | F32  | Speed | m/s |
| 260       | F32  | Power | W |
| 264       | F32  | Torque | Nm |
| 268       | F32  | TireTempFL | |
| 272       | F32  | TireTempFR | |
| 276       | F32  | TireTempRL | |
| 280       | F32  | TireTempRR | |
| 284       | F32  | Boost | PSI |
| 288       | F32  | Fuel | 0.0〜1.0 |
| 292       | F32  | DistanceTraveled | |
| 296       | F32  | BestLap | |
| 300       | F32  | LastLap | |
| 304       | F32  | CurrentLap | |
| 308       | F32  | CurrentRaceTime | |
| 312       | U16  | LapNumber | |
| 314       | U8   | RacePosition | |
| 315       | U8   | **Accel** | 0〜255 |
| 316       | U8   | **Brake** | 0〜255 |
| 317       | U8   | Clutch | |
| 318       | U8   | **HandBrake** | |
| 319       | U8   | Gear | |
| 320       | S8   | Steer | -127〜127 |
| 321       | S8   | NormalizedDrivingLine | |
| 322       | S8   | NormalizedAIBrakeDifference | |
| (323)     | —    | (合計 323 バイト消費、324 バイトパケット) | |

---

## 実装方針

### 新規ファイル: `core/rumble_udp_listener.py`

- `socket` + `struct` で UDP 受信（別スレッド）
- `IsRaceOn == 0` の場合は振動を送らない（停止）
- 振動強度の計算ロジック（優先度順）:
  1. **衝突**: `SmashableVelDiff > 閾値`（例: 3.0 m/s）→ 大きい振動を短時間
  2. **スリップ**: `max(abs(TireCombinedSlip*))` が高い → high_freq モーターに反映
  3. **路面**: `max(SurfaceRumble*)` をそのまま low_freq に使う（これが主信号）
- 出力は `rumble_manager` の既存 API に渡す（引数は事前確認必須）
- `config.json` にポート番号を追加（デフォルト `5301`）

### `main.py` への統合

- 既存の入力ループと並列で UDP リスナースレッドを起動
- `--no-udp` フラグで無効化できると望ましい

### 参考実装

HorizonHaptics（`https://github.com/haritha99ch/HorizonHaptics`）が同じパケット仕様を Python で実装している。`GameParsers/` ディレクトリのパーサーと `worker.py` の振動計算ロジックが参考になる。

---

## 制約・注意事項

- `rumble_manager.py` の API は **コード確認後に合わせる**（仮定しない）
- UDP はゲームからの一方向のみ。ゲームへの送信は不可
- パケットは運転中のみ届く。無音時のフォールバック（振動ゼロ送信）を忘れずに
- FH5 以前のパケットとの違い: `CarGroup`・`SmashableVelDiff`・`SmashableMass` が `NumCylinders` の直後に追加されている（オフセットがずれるので注意）

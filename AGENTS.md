# AGENTS.md

## 概要
本ドキュメントは、本リポジトリ（Unreal Engine 4.27 テスト環境）で作業するAIエージェント向けの運用指針および手順を定義する。

## 運用ルール

### 1. コマンド実行手順
- 直接コンソールへコマンドを打たず、必ずルート直下の `run_cmd.ps1` を編集した上で実行すること。
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\run_cmd.ps1
  ```

### 2. ノードグラフキャプチャ運用
- **実行スクリプト**: [`Script/export_and_capture.py`](file:///c:/Users/matoi/Documents/Unreal%20Projects/BP_View_test_env/Script/export_and_capture.py)
- **依存環境**:
  - Chrome Headless (`C:\Program Files\Google\Chrome\Application\chrome.exe`)
  - BlueprintUE レンダラ (`https://blueprintue.com/bue-render/render.js`, `render.css`)
- **制約事項**:
  - 縮小表示（ズームアウト）は厳禁。1:1等倍表示を維持すること。
  - 1画面（1920x1080）に収まらない大規模グラフは座標・クラスタ分割して撮影すること。
  - MBP（Material / MaterialFunction）および AnimGraph内部ステートマシンは、BlueprintUE レンダラの仕様制限（ピン定義不一致・構文未対応）により描画不可。
- **出力先**:
  - `screenshots/{AssetName}/{GraphId}.png`
  - `capture_manifest.json` に全メタデータを記録。

### 3. ドキュメント自己評価・更新基準
- 新規スクリプトやキャプチャパイプライン追加時は、[`README.md`](file:///c:/Users/matoi/Documents/Unreal%20Projects/BP_View_test_env/README.md) のアセット一覧・キャプチャ結果および本ドキュメントの記載を同期更新すること。

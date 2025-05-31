# Gemini UI Chat

最新のVertex AI Gemini APIを使用したチャットインターフェース。thinking機能とファイル処理をサポート。

## 機能

- 最新のGoogle Gen AI SDK使用
- Gemini 2.5モデル対応（Flash/Pro preview）
- Thinking機能のON/OFF切り替え
- Thinking budgetの調整（0-24576トークン）
- **8種類の汎用システムプロンプトテンプレート**
- ファイル選択とコンテンツ送信
- リアルタイムストリーミング
- コスト推定表示

## システムプロンプトテンプレート

thinking機能を最大限活用するため、以下のテンプレートを用意しています：

### 📊 **専門分析家**
段階的思考で問題を分析し、専門知識を基に根拠ある結論を導出

### 💻 **プログラミング講師**
実行可能なコード例と分かりやすい説明を提供する親切な講師

### 🔍 **検証・反省型**
情報の正確性を検証し、推論過程を見直して慎重に回答

### 🔧 **段階的問題解決**
複雑な問題を5段階に分けて構造化された解決アプローチを実行

### 💡 **創造的思考**
従来とは異なる視点から創造的な解決方法やアイデアを提案

### 📋 **詳細レポート作成**
体系的な構造で詳細な分析レポートを作成

### 🔄 **多角的分析**
技術・経済・社会・環境など複数の視点から総合的に分析

## セットアップ

1. 依存関係のインストール:
```bash
pip install -r requirements.txt
```

2. `config.json`でプロジェクト設定:
```json
{
  "vertex_ai_project_id": "your-project-id",
  "vertex_ai_location": "us-central1",
  "root_directory": "/path/to/your/project"
}
```

3. 環境変数設定:
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=True
```

## ログレベル制御

環境変数`LOG_LEVEL`でコンソール出力のレベルを制御できます：

```bash
# 最小限の出力（エラーのみ）
export LOG_LEVEL=ERROR

# 通常の情報出力（デフォルト）
export LOG_LEVEL=INFO

# 詳細な情報出力
export LOG_LEVEL=DEBUG
```

ファイルには常にDEBUGレベルの詳細ログが保存されます（`app.log`）。

## 使用方法

```bash
python main.py
```

### UI操作

- **Model**: 使用するGeminiモデルを選択
- **Thinking**: thinking機能のON/OFF
- **Budget**: thinking用トークン予算（Flashモデルで有効）
- **テンプレート**: システムプロンプトテンプレートを選択
- **🤔 Thinking Process**: 展開可能なthinking表示パネル

### テンプレート使用例

1. **プログラミング質問**: "プログラミング講師"テンプレートを選択
2. **複雑な問題**: "段階的問題解決"テンプレートで構造化
3. **創造的アイデア**: "創造的思考"テンプレートで発想拡張
4. **情報検証**: "検証・反省型"テンプレートで信頼性確保 
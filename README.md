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
- コスト推定表示（入力・出力統合表示）
- **エラー時の自動リトライ機能（最大3回）**
- **セッション管理機能**
- **会話のアーカイブ機能**
- **プロジェクトパス変更UI**
- **選択ファイル表示機能**

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

### 1. uvのインストール

uvがインストールされていない場合、以下のコマンドでインストールします：

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 依存関係のインストール

uvを使用する場合（推奨）：
```bash
uv sync
```

これにより、`pyproject.toml`に記載された依存関係が自動的にインストールされます。

**注意**: このプロジェクトはuvを使用することを前提としています。pipを使用する場合は、`requirements.txt`を参照してください。

### 3. 設定ファイルの準備

`config.json`でプロジェクト設定を行います：

```json
{
  "vertex_ai_project_id": "your-project-id",
  "vertex_ai_location": "us-central1",
  "root_directory": "/path/to/your/project",
  "default_model": "gemini-2.5-pro",
  "default_temperature": 0.1,
  "default_max_output_tokens": 65535
}
```

#### 必須設定項目
- `vertex_ai_project_id`: Google Cloud プロジェクトID
- `vertex_ai_location`: Vertex AI のリージョン（例: `us-central1`, `global`）

#### オプション設定項目
- `root_directory`: プロジェクトのルートディレクトリパス（UIからも変更可能）
- `default_model`: デフォルトで使用するモデル
- `default_temperature`: デフォルトの温度設定
- `default_max_output_tokens`: デフォルトの最大出力トークン数
- `excluded_dirs`: ファイルエクスプローラーで除外するディレクトリ

### 4. Google Cloud認証

Google Cloud認証を設定します：

```bash
# Application Default Credentialsを使用する場合
gcloud auth application-default login

# または、サービスアカウントキーを使用する場合
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

## 起動方法

### Windows

```bash
# 方法1: batファイルを使用（推奨）
launch_gemini.bat

# 方法2: uvで直接実行
uv run python main.py
```

### Linux/macOS

```bash
# 方法1: shファイルを使用（推奨）
chmod +x launch_gemini.sh
./launch_gemini.sh

# 方法2: uvで直接実行
uv run python main.py
```

**注意**: 初回実行時は、uvが自動的に依存関係をインストールします。これには少し時間がかかる場合があります。

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

ファイルには常にDEBUGレベルの詳細ログが保存されます（`app.log`）。ログファイルは最大5MB、3つのバックアップファイルが保持されます。

## 使用方法

### UI操作

#### パラメータ設定
- **Model**: 使用するGeminiモデルを選択
- **Temp**: 温度パラメータ（0.0-1.0）
- **MaxTok**: 最大出力トークン数
- **Budget**: thinking用トークン予算（Flashモデルで有効）
- **自動バジェット**: thinkingバジェットの自動最適化
- **テンプレート**: システムプロンプトテンプレートを選択
- **System Prompt**: システムプロンプトを直接入力

#### セッション管理
- **Session**: 会話セッションを切り替え
- **新規セッション作成**: 新しいセッション名を入力して作成
- **セッション削除**: 現在のセッションをアーカイブ（削除ではなく`conversations/archived/`に移動）

#### ファイル操作
- **プロジェクトパス変更**: 設定セクションからプロジェクトパスを変更
- **ファイル選択**: プロジェクトファイルから送信するファイルを選択
- **選択ファイル表示**: 選択中のファイル一覧を確認
- **ファイルリフレッシュ**: ファイル一覧を再読み込み

#### チャット操作
- **Ctrl+Enter**: メッセージを送信
- **Cancel**: 送信中のリクエストをキャンセル（会話履歴は保持）
- **Reset**: 会話をリセット（システムプロンプトテンプレートは保持）

### エラー時の自動リトライ

API呼び出し時に以下のエラーが発生した場合、自動的に最大3回までリトライします：

- HTTP 443エラー（Connection closed）
- HTTP 429エラー（Rate limit）
- HTTP 503エラー（Service unavailable）
- HTTP 500/502/504エラー（サーバーエラー）
- ネットワークエラー（timeout、connectionなど）

リトライ間隔は指数バックオフ方式（1秒 → 2秒 → 4秒）で調整されます。

### テンプレート使用例

1. **プログラミング質問**: "プログラミング講師"テンプレートを選択
2. **複雑な問題**: "段階的問題解決"テンプレートで構造化
3. **創造的アイデア**: "創造的思考"テンプレートで発想拡張
4. **情報検証**: "検証・反省型"テンプレートで信頼性確保

## データ管理

### 会話履歴

会話履歴は`conversations/`ディレクトリにJSON形式で保存されます：

- `conversations/default.json`: デフォルトセッション
- `conversations/{session_name}.json`: 名前付きセッション
- `conversations/archived/`: アーカイブされたセッション

### 設定ファイル

- `config.json`: アプリケーション設定
- `app.log`: ログファイル

## トラブルシューティング

### 認証エラー

```
Error: Project ID not properly configured in config.json
```

**解決方法**: `config.json`の`vertex_ai_project_id`と`vertex_ai_location`を正しく設定してください。

### ファイルが読み込めない

**解決方法**: 
1. 設定セクションからプロジェクトパスを確認
2. ファイルリフレッシュボタンをクリック
3. `config.json`の`excluded_dirs`を確認

### リトライが失敗する

最大リトライ回数（3回）に達してもエラーが続く場合：

1. ネットワーク接続を確認
2. Google Cloud プロジェクトのクォータを確認
3. ログファイル（`app.log`）で詳細を確認

## 開発

### 依存関係

- `flet>=0.28.3`: UIフレームワーク
- `google-genai>=1.31.0`: Google Gen AI SDK

### プロジェクト構造

```
ui_gemini/
├── main.py                 # メインアプリケーション
├── ui_components.py        # UIコンポーネント定義
├── vertex_ai_client.py     # Gemini API クライアント
├── conversation_manager.py # 会話管理
├── config_manager.py       # 設定管理
├── logger_setup.py         # ログ設定
├── config.json             # 設定ファイル
├── pyproject.toml          # プロジェクト設定（uv用）
├── uv.lock                 # 依存関係ロックファイル（uv用）
├── requirements.txt        # 依存関係（pip用、参考）
├── launch_gemini.bat      # Windows起動スクリプト
├── launch_gemini.sh        # Linux/macOS起動スクリプト
└── conversations/          # 会話履歴ディレクトリ
    └── archived/           # アーカイブディレクトリ
```

## ライセンス

このプロジェクトは個人利用を目的としています。

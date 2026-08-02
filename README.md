# 🌸 新着論文

PubMedから研究テーマに関連する新着論文を毎朝取得し、GitHub Pagesで一覧表示する無料構成です。

## 主な機能

- 毎朝6:10（日本時間）にPubMedを検索
- 今日・昨日・直近7日・指定日で絞り込み
- 英語タイトル／日本語タイトル
- PubMedに登録されたAbstract原文全文
- Abstract全文の日本語訳
- 背景・目的、方法、結果、結論の簡易抽出
- 方法・結果の詳細と数値抽出
- PubMed／DOIリンク
- 複数選択CSV出力
- お気に入り・既読（ブラウザ内保存）
- 保存済み内容への簡易質問
- Slack通知（任意）

## 無料運用について

- GitHub Pages：公開リポジトリで無料
- GitHub Actions：公開リポジトリの標準ランナーは無料
- PubMed E-utilities：無料
- 日本語訳：GitHub Actions上で無料翻訳ライブラリを使用
- OpenAI API：使用しません

> 翻訳は無料の非公式Google翻訳経由です。失敗時は英語を保持します。
> 医学的な精査・論文執筆時には、必ず原文を確認してください。

# 導入手順

## 1. GitHubでリポジトリを作成

1. https://github.com/new を開く
2. Repository name：`shinchaku-ronbun`
3. **Public**を選択
4. `Create repository`

## 2. ZIPをアップロード

1. このZIPを展開
2. GitHubのリポジトリ画面で `uploading an existing file`
3. 展開したフォルダの中身をすべてドラッグ
4. `Commit changes`

アップロード後、リポジトリ直下が次の状態なら正常です。

```text
.github/
docs/
scripts/
requirements.txt
README.md
```

## 3. GitHub Actionsへ書き込み権限を付与

1. リポジトリの `Settings`
2. 左側 `Actions` → `General`
3. 下部 `Workflow permissions`
4. `Read and write permissions`
5. `Save`

## 4. 最初の論文取得

1. 上部 `Actions`
2. 左側 `Update PubMed papers`
3. `Run workflow`
4. 緑色の完了表示まで待つ

完了後、`docs/data/papers.json`が更新されます。

## 5. GitHub Pagesを公開

1. `Settings`
2. 左側 `Pages`
3. `Build and deployment`
4. Source：`Deploy from a branch`
5. Branch：`main`
6. Folder：`/docs`
7. `Save`

数分後にURLが表示されます。

```text
https://あなたのGitHubユーザー名.github.io/shinchaku-ronbun/
```

## 6. Slack通知（任意）

1. リポジトリの `Settings`
2. `Secrets and variables` → `Actions`
3. `New repository secret`
4. Name：`SLACK_WEBHOOK_URL`
5. Secret：Slack Incoming Webhook URL
6. `Add secret`

設定しなくてもアプリ本体は動作します。

## 7. メールアドレスの設定

`.github/workflows/update.yml`の次を、自分のメールアドレスへ変更してください。

```yaml
NCBI_EMAIL: your-email@example.com
```

## 自動実行時刻

毎朝6:10（Asia/Tokyo）に設定しています。GitHub Actionsの混雑により、実行が数分遅れることがあります。

## 注意事項

- リポジトリをPublicにすると、論文一覧データとコードは公開されます。
- Slack Webhookは必ずGitHub Secretsへ保存し、コードへ直接書かないでください。
- お気に入り・既読は利用しているブラウザ内に保存されます。

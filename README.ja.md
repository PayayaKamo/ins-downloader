# Instagram メディアダウンローダー

[instaloader](https://instaloader.github.io/) をベースにした小さなコマンドラインツールです。
公開されている Instagram アカウントをアーカイブするために、各投稿のすべての画像
（複数画像投稿の各フレームを含む）を、キャプション・メタデータ・CSV インデックスと
あわせて保存します。

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

## できること

- 1 つ以上の公開アカウントの画像をすべてダウンロードします（アカウント全体、または期間指定）。
- 複数画像投稿の各フレームを個別のファイルとして保存するので、取りこぼしがありません。
- 投稿ごとに `.txt`（キャプション）と `.json`（メタデータ）を保存します。
- `_index.csv` を維持し、ダウンロード済みの投稿を 1 つの表にまとめます。
- 既に存在するファイルはスキップし、中断後はチェックポイントから再開します。
- レート制限や切断時はバックオフしながら再試行し、進捗が止まったら安全に終了します。
- Windows のシステムプロキシを自動検出します。明示的な指定も可能です。
- オプション：動画、プロフィール画像、ダウンロードせずに一覧表示のみ。

## 動作要件

- Python 3.9 以降
- `instaloader`（`requirements.txt` からインストール）
- オプション：ブラウザのログイン状態を再利用する場合は `browser-cookie3`

## インストール

```bash
git clone https://github.com/PayayaKamo/ins-downloader.git
cd ins-downloader

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 使い方

```bash
# 公開アカウント全体を ./downloads にダウンロード
python ins_downloader.py namoridane

# ユーザー名の代わりにプロフィール URL でも可
python ins_downloader.py https://www.instagram.com/namoridane/

# 出力先を指定し、先頭 50 件だけ、動画も含める
python ins_downloader.py namoridane -o D:/instagram -n 50 --videos

# 投稿日（UTC）で範囲を限定
python ins_downloader.py namoridane --since 2024-01-01 --until 2025-12-31

# 実際にはダウンロードせず、対象を一覧表示
python ins_downloader.py namoridane --dry-run

# プロキシ経由
python ins_downloader.py namoridane --proxy http://127.0.0.1:7890
```

よく使うオプション：

| オプション | 説明 |
| --- | --- |
| `-o, --output` | 出力ルートディレクトリ（既定：`downloads`） |
| `-n, --max-posts` | アカウントごとの最大投稿数。`0` は全件 |
| `--since` / `--until` | 指定した UTC 期間内の投稿のみ |
| `--videos` | 動画もダウンロード（既定は画像のみ） |
| `--profile-pic` | プロフィール画像もダウンロード |
| `--skip-pinned` | 固定された投稿をスキップ |
| `--login USER` | `USER` でログイン（非公開アカウントやレート制限時） |
| `--cookies-from-browser BROWSER` | `chrome`、`edge`、`firefox` などの Cookie を再利用 |
| `--proxy` / `--no-proxy` | プロキシを強制、または直接接続を強制 |
| `--dry-run` | ダウンロード対象を表示するだけ |
| `--post-delay` | 投稿間の待機秒数（既定：`1`） |

全オプションは `python ins_downloader.py --help` を参照してください。

## 認証と環境変数

公開アカウントはログインなしでダウンロードできます。ログインすると、Instagram による
匿名リクエストのレート制限が緩和され、フォロー中の非公開アカウントの取得も可能になります。

認証方法は 3 つあり、優先度の高い順に次のとおりです。

1. `--login USER` とパスワード：
   - パスワードは `--password`、環境変数 `INS_PASSWORD`、または対話入力で指定します。
   - ログイン状態はキャッシュされるため、次回以降はパスワード入力が不要です
     （既定は `~/.instaloader/session-USER`、`--session-file` で変更可能）。
2. `--cookies-from-browser chrome`（`edge`、`firefox`、`brave` なども可）で、
   ブラウザに保存済みの Cookie を再利用します。事前に `pip install browser-cookie3` が必要です。
3. スクリプトと同じディレクトリに置いたローカルの `.env` ファイル。

対応する環境変数：

| 変数 | 用途 |
| --- | --- |
| `INS_USERNAME` | `--login` の既定値 |
| `INS_PASSWORD` | `--password` 未指定時に `--login` が使うパスワード |
| `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` | すべてのリクエストで使うプロキシ |

既に設定されている環境変数は `.env` の値より優先されます。

設定手順：

```bash
cp .env.example .env
# その後 .env を編集して自分の値を入力します
```

> 実際の認証情報がリポジトリに入ることはありません。`.env`、Cookie、セッションファイルは
> すべて `.gitignore` に含まれています。コミットしないでください。実際の Cookie を
> issue に貼り付けるのも避けてください。

## 出力結果

既定ではカレントディレクトリの `downloads/` に、アカウントごとのサブディレクトリを作って保存します。

```text
downloads/
└── namoridane/
    ├── 2025-09-22_09-00-03_DO4jShFklJW.jpg       # 投稿の 1 枚目
    ├── 2025-09-22_09-00-03_DO4jShFklJW_1.jpg     # 複数画像投稿の 2 枚目
    ├── 2025-09-22_09-00-03_DO4jShFklJW.txt       # キャプション
    ├── 2025-09-22_09-00-03_DO4jShFklJW.json      # 完全なメタデータ
    ├── _index.csv                                # 投稿ごとに 1 行
    └── _resume_posts.json                        # 再開用のチェックポイント
```

出力先は `-o` で変更できます。ファイル名は
`{date_local:%Y-%m-%d_%H-%M-%S}_{shortcode}` の形式で、`--filename-pattern` で変更できます。

`_index.csv` の列：`shortcode`、`date_local`、`date_utc`、`type`、`media_count`、
`likes`、`comments`、`local_file`、`url`、`caption`。

## 再開と終了コード

ネットワーク障害や Instagram のスロットリングなどで中断した場合は、同じコマンドを
もう一度実行するだけです。完了済みのファイルはスキップされ、`_resume_posts.json` の
チェックポイントから続きを処理します。

| 終了コード | 意味 |
| --- | --- |
| `0` | すべて処理され、各ダウンロードも成功 |
| `1` | アカウントが存在しない、またはログインが必要だが未ログイン |
| `2` | 一部のみ完了：投稿の一部が失敗、または最後まで走査できていない |
| `3` | `--stall-timeout` 秒間進捗がなく、チェックポイントを保存して終了 |

## 接続チェック

`check_connection.py` は読み取り専用のリクエストを 1 回だけ送り、アカウントの統計情報と
直近の投稿を表示します。何もダウンロードしないため、本番実行前にネットワーク、プロキシ、
ログイン設定を素早く確認できます。

```bash
python check_connection.py namoridane
python check_connection.py namoridane --proxy http://127.0.0.1:7890
```

## 利用にあたって

本ツールはアカウント所有者が公開しているコンテンツのみを読み取ります。個人のアーカイブ、
または所有者の許可を得た用途に使用し、Instagram の利用規約と原作者の著作権を尊重してください。
許可なくダウンロードした素材を再配布しないでください。

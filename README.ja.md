# ai-reset-line

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

Claude Code のステータスラインに、5時間枠と週間枠の使用率とリセットまでの時間を表示するスクリプトです。`--summary` では Codex CLI のローカルセッションファイルも読み取ります。API キー不要、ネットワーク通信なし、テレメトリなし。

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
```

上は `bin/ai-reset-line` の実際の出力です（モデル名は Claude Code が渡す `model.display_name` をそのまま表示します。「Large」はテスト用の仮の名前です）。

## できること

- Claude Code がステータスラインのコマンドに標準入力で渡す JSON を読みます。
- 1行で表示：モデル、5時間枠の使用率とリセットまでの残り時間、7日枠の使用率とリセット時刻、コンテキスト使用率。
- 項目が欠けている場合（API キー利用時、セッション開始直後など）はその部分を省くだけで、エラーは出しません。
- 表示スタイルは `plain`・`bar`・`compact` の3種類。`NO_COLOR` に対応。時刻はローカルタイムゾーンで表示します。
- `--summary` で Claude の最後の読み取り結果と、`~/.codex/sessions` にある Codex CLI の最新のレート制限をまとめて表示します。
- Python 3.9 以上の標準ライブラリのみ。本体は `src/ai_reset_line.py` の1ファイルです。

## インストール

どれか1つを選んでください。

### A. git clone（おすすめ）

```sh
git clone https://github.com/alice51849/ai-reset-line ~/.local/share/ai-reset-line
```

そのあと [設定](#設定) のスニペットを `~/.claude/settings.json` に追加します。

### B. Claude Code プラグイン

Claude Code の中で：

```text
/plugin marketplace add alice51849/ai-reset-line
/plugin install ai-reset-line@ai-reset-line
/ai-reset-line:reset-line-setup
```

セットアップコマンドがスクリプトを `~/.claude/ai-reset-line/ai_reset_line.py` にコピーし、ユーザー設定に `statusLine` を追加します（既に設定がある場合は先に確認します）。スタイルも指定できます：`/ai-reset-line:reset-line-setup bar`

### C. ファイル1つだけ

```sh
mkdir -p ~/.claude/ai-reset-line
curl -fsSL https://raw.githubusercontent.com/alice51849/ai-reset-line/main/src/ai_reset_line.py \
  -o ~/.claude/ai-reset-line/ai_reset_line.py
```

設定では `"command": "python3 ~/.claude/ai-reset-line/ai_reset_line.py"` を使います。

## 設定

`examples/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.local/share/ai-reset-line/bin/ai-reset-line --style plain",
    "padding": 0,
    "refreshInterval": 30
  }
}
```

`refreshInterval` は任意です。N 秒ごとにコマンドを再実行するので、操作していない間もカウントダウンが進みます。

| オプション | 意味 |
|---|---|
| `--style plain` | `Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%`（既定） |
| `--style bar` | 5h／7d に10マス、コンテキストに5マスのバーを追加 |
| `--style compact` | `Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%` |
| `--no-color` | 色なし（`NO_COLOR` に空でない値を設定しても同じ） |
| `--no-cache` | `~/.cache/ai-reset-line/last.json` を書かない |
| `--summary` | 下記の複数行サマリーを表示 |

`AI_RESET_LINE_STYLE` で既定のスタイルを、`XDG_CACHE_HOME` または `AI_RESET_LINE_CACHE` でキャッシュの場所を変えられます。

## 出力の見かた

3つのスタイルの実際の出力：

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
Large · 5h ▓▓▓▓░░░░░░ 42% ↻1h18m · 7d ▓▓▓▓▓▓░░░░ 63% ↻Tue 01:41 · ctx ▓▓░░░ 38%
Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%
```

| 表示 | 元の項目 | 説明 |
|---|---|---|
| モデル | `model.display_name` | |
| `5h 42% ↻1h18m` | `rate_limits.five_hour.used_percentage`、`.resets_at` | 5時間枠。`resets_at`（Unix エポック秒）までの残り時間を表示します。 |
| `7d 63% ↻Tue 01:41` | `rate_limits.seven_day.used_percentage`、`.resets_at` | 週間枠。ローカルの曜日と時刻で表示し、残り24時間を切るとカウントダウンに変わります。 |
| `ctx 38%` | `context_window.used_percentage` | コンテキストウィンドウの使用率。 |
| `↻reset` | | Claude Code がデータを送った後にリセット時刻を過ぎたことを示します。 |

色：50% 未満は緑、50% 以上は黄、80% 以上は赤。

使用量データがないときは短く表示されます：

```text
Medium · ctx 13%          # API キー利用：rate_limits がない
Medium                    # セッション開始直後：コンテキスト情報もまだない
```

### `--summary`

```text
$ ai-reset-line --summary
Claude Code
  last seen <1m ago, Large
  5h    42%  resets in 1h18m (01:36)
  7d    63%  resets in 3d1h (Tue 01:41)

Codex CLI
  last seen 12m ago, codex
  5h    28%  resets in 2h40m (02:59)
  7d    44%  resets in 4d3h (Wed 03:21)

Gemini
  Gemini API requests-per-day quotas reset at midnight Pacific time (next: 16:00, in 15h41m)
  (published schedule, not a live reading)
```

- **Claude Code**：ステータスラインが最後に受け取った値（`~/.cache/ai-reset-line/last.json`）。保存するのは上に表示される数値（モデル名、使用率、リセット時刻）だけで、セッション ID・パス・プロンプトは保存しません。
- **Codex CLI**：`~/.codex/sessions/**/*.jsonl`（または `$CODEX_HOME/sessions`）の中で、`rate_limits` を含む最新の `token_count` イベント。読み取りのみ。`primary`／`secondary` は `window_minutes` からラベルを付けます（300 → `5h`、10080 → `7d`）。
- **Gemini**：Google が公開している Gemini API のクォータのリセット時刻に基づく固定の案内です。問い合わせは一切しません。

## プライバシー

- 実行時のネットワーク通信はありません。ネットワーク関連のモジュールを import していないことをテストで確認しています。
- OAuth トークン、API キー、Cookie、認証情報ファイルは読みません。
- テレメトリ・解析なし。
- 書き込むのは上記の小さなキャッシュファイルだけです。`--no-cache` で無効にできます。

## FAQ

**5h／7d が表示されません。**
Claude Code が `rate_limits` を渡すのは claude.ai のサブスクリプションプランだけで、セッション内で最初の応答が返ってからです。API キー利用時は表示されません。各枠は個別に欠けることがあり、リセット時刻を過ぎた枠は Claude Code が外します。

**席を外している間カウントダウンが止まります。**
ステータスラインはイベントごとに更新されます。`statusLine` に `"refreshInterval": 30`（秒）を追加してください。

**Codex の上限はどう見ますか？**
`ai-reset-line --summary` を実行してください。Codex CLI は応答ごとにレート制限のスナップショットをローカルのセッションファイルに書き込み、このツールは最新のものを読みます。圧縮された `.jsonl.zst` だけの場合は読み飛ばします（追加ツールが必要なため）。

**Windows で使えますか？**
WSL か Git Bash から使うか、設定で Python を直接指定してください：`"command": "python C:/path/to/ai_reset_line.py"`

**`/usage` との違いは？**
`/usage` は実行して確認するコマンドです。このツールは Claude Code がステータスラインに渡すデータだけを使い、同じ種類の数値を常に表示しておきます。

**自分のスクリプトから使えますか？**
はい。`import ai_reset_line` して `parse_status(json_dict)` と `render(status, style)` を呼んでください。

## 開発

```sh
python3 -m unittest discover -s tests
sh -n bin/ai-reset-line && shellcheck bin/ai-reset-line
```

`src/ai_reset_line.py` を編集したら `plugins/ai-reset-line/scripts/` にもコピーしてください（2つが異なるとテストが失敗します）。

## Away from your desk?

UsageNow は、同じ種類の上限とリセットまでのカウントダウン（Claude の5時間上限と週間上限、ChatGPT Codex の5時間枠と週間枠、GitHub Copilot のプレミアムリクエスト、Gemini の1日あたりのリクエスト上限）をホーム画面・ロック画面のウィジェットに表示し、選んだパーセンテージでアラートを送る iPhone・iPad・Apple Watch 向けアプリです。このスクリプトの作者が作っています。
https://apps.apple.com/app/id6818607603?pt=118326163&ct=bm_usagenow_ww_gh&mt=8

## ライセンス

MIT。[LICENSE](LICENSE) を参照してください。

Anthropic、OpenAI、GitHub、Google とは提携していません。Claude と Claude Code は Anthropic の商標です。OpenAI、ChatGPT、Codex は OpenAI の商標です。GitHub と GitHub Copilot は GitHub の商標です。Gemini は Google の商標です。iPhone、iPad、Apple Watch は Apple Inc. の商標です。その他の商標はそれぞれの所有者に帰属します。

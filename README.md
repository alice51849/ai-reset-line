# ai-reset-line

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

A status line for Claude Code that shows your 5-hour and weekly usage with reset countdowns, plus a `--summary` view that also reads Codex CLI's local session files. No API keys, no network calls, no telemetry.

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
```

The line above is real output of `bin/ai-reset-line` (the model name comes from `model.display_name` in the data Claude Code sends; "Large" is a placeholder used in the test fixtures).

## What it does

- Reads the JSON that Claude Code pipes to status line commands on stdin.
- Prints one line: model, 5-hour usage and time until reset, 7-day usage and reset time, context window usage.
- If a field is missing (API key sessions, the first moments of a session), that part is simply left out. It never prints an error into your status line.
- Three styles: `plain`, `bar`, `compact`. Colors follow `NO_COLOR`. Times use your local time zone.
- `--summary` prints the last Claude reading and the latest Codex CLI rate limits found in `~/.codex/sessions`.
- Python 3.9+ standard library only. One file: `src/ai_reset_line.py`.

## Install

Pick one.

### A. git clone (recommended)

```sh
git clone https://github.com/alice51849/ai-reset-line ~/.local/share/ai-reset-line
```

Then add the snippet from [Configure](#configure) to `~/.claude/settings.json`.

### B. Claude Code plugin

Inside Claude Code:

```text
/plugin marketplace add alice51849/ai-reset-line
/plugin install ai-reset-line@ai-reset-line
/ai-reset-line:reset-line-setup
```

The setup command copies the script to `~/.claude/ai-reset-line/ai_reset_line.py` and adds a `statusLine` entry to your user settings (it asks first if you already have one). You can pass a style: `/ai-reset-line:reset-line-setup bar`.

### C. Single file

```sh
mkdir -p ~/.claude/ai-reset-line
curl -fsSL https://raw.githubusercontent.com/alice51849/ai-reset-line/main/src/ai_reset_line.py \
  -o ~/.claude/ai-reset-line/ai_reset_line.py
```

and use `"command": "python3 ~/.claude/ai-reset-line/ai_reset_line.py"` in the settings below.

## Configure

`examples/settings.json`:

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

`refreshInterval` is optional. It re-runs the command every N seconds so the countdown keeps moving while the session is idle.

Options:

| Option | Meaning |
|---|---|
| `--style plain` | `Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%` (default) |
| `--style bar` | adds 10-cell bars for 5h/7d and a 5-cell bar for context |
| `--style compact` | `Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%` |
| `--no-color` | no ANSI colors (setting `NO_COLOR` to any non-empty value does the same) |
| `--no-cache` | do not write `~/.cache/ai-reset-line/last.json` |
| `--summary` | print the multi-line summary described below |

`AI_RESET_LINE_STYLE` sets the default style. `XDG_CACHE_HOME` or `AI_RESET_LINE_CACHE` move the cache file.

## Output reference

Real output for the three styles:

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
Large · 5h ▓▓▓▓░░░░░░ 42% ↻1h18m · 7d ▓▓▓▓▓▓░░░░ 63% ↻Tue 01:41 · ctx ▓▓░░░ 38%
Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%
```

| Part | Source field | Notes |
|---|---|---|
| model | `model.display_name` | |
| `5h 42% ↻1h18m` | `rate_limits.five_hour.used_percentage`, `.resets_at` | The 5-hour window. The countdown is time left until `resets_at` (Unix epoch seconds). |
| `7d 63% ↻Tue 01:41` | `rate_limits.seven_day.used_percentage`, `.resets_at` | The weekly window. Shown as local day and time; switches to a countdown in the last 24 hours. |
| `ctx 38%` | `context_window.used_percentage` | Share of the context window in use. |
| `↻reset` | | The reset time has already passed since Claude Code sent this data. |

Colors: green below 50%, yellow from 50%, red from 80%.

When there is no usage data the line shrinks gracefully:

```text
Medium · ctx 13%          # API key session: no rate_limits field
Medium                    # very start of a session: no context data yet
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

- **Claude Code**: the last reading the status line saw, from `~/.cache/ai-reset-line/last.json`. It only stores the numbers shown above (model name, percentages, reset times), never session IDs, paths or prompts.
- **Codex CLI**: the newest `token_count` event with `rate_limits` in `~/.codex/sessions/**/*.jsonl` (or `$CODEX_HOME/sessions`). Read-only. `primary`/`secondary` windows are labelled from `window_minutes` (300 → `5h`, 10080 → `7d`).
- **Gemini**: a static note based on Google's published Gemini API quota schedule. Nothing is queried.

## Privacy

- No network requests at runtime. The script does not import any networking module (a test checks this).
- It does not read OAuth tokens, API keys, cookies or credential files.
- No telemetry, no analytics.
- The only file it writes is the small cache described above. Use `--no-cache` to disable it.

## FAQ

**Why don't I see 5h / 7d?**
Claude Code only includes `rate_limits` for claude.ai subscription plans, and only after the first API response in a session. API key sessions never have it. Each window can also be absent on its own, and Claude Code drops a window once its reset time passes.

**The countdown doesn't move while I'm away.**
Status lines refresh on events. Add `"refreshInterval": 30` (seconds) to the `statusLine` setting.

**How do I see Codex limits?**
Run `ai-reset-line --summary`. Codex CLI writes rate limit snapshots into its local session files after each response; this tool reads the newest one. If you only see compressed `.jsonl.zst` files, they are skipped (reading them would need extra tools).

**Does it work on Windows?**
Use it from WSL or Git Bash, or point the setting directly at Python: `"command": "python C:/path/to/ai_reset_line.py"`.

**How is this different from `/usage`?**
`/usage` is a command you run; this keeps the same kind of numbers in view all the time, using only the data Claude Code already passes to status lines.

**Can I use it in my own script?**
Yes: `import ai_reset_line` and call `parse_status(json_dict)` and `render(status, style)`.

## Development

```sh
python3 -m unittest discover -s tests
sh -n bin/ai-reset-line && shellcheck bin/ai-reset-line
```

After editing `src/ai_reset_line.py`, copy it to `plugins/ai-reset-line/scripts/` (a test fails if the two differ).

## Away from your desk?

UsageNow is an iPhone app that shows the same kinds of limits and reset countdowns (Claude 5-hour and weekly limits, ChatGPT Codex 5-hour and weekly windows, GitHub Copilot premium requests, Gemini daily request limits) in Home Screen and Lock Screen widgets, with alerts at the percentage you choose, for iPhone, iPad and Apple Watch. It is made by the author of this script.
https://apps.apple.com/app/id6818607603?pt=118326163&ct=bm_usagenow_ww_gh&mt=8

## License

MIT. See [LICENSE](LICENSE).

Not affiliated with Anthropic, OpenAI, GitHub or Google. Claude and Claude Code are trademarks of Anthropic. OpenAI, ChatGPT and Codex are trademarks of OpenAI. GitHub and GitHub Copilot are trademarks of GitHub. Gemini is a trademark of Google. iPhone, iPad and Apple Watch are trademarks of Apple Inc. All other trademarks belong to their respective owners.

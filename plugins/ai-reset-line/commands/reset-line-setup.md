---
description: Install the ai-reset-line status line (5h and 7d usage with reset countdowns) into your user settings
argument-hint: "[plain|bar|compact]"
---

Set up the ai-reset-line status line for this user. Follow these steps exactly.

1. Pick the style from the arguments: `$ARGUMENTS`. If it is empty or not one of `plain`, `bar`, `compact`, use `plain`.
2. Check that `python3 --version` reports 3.9 or later. If Python 3.9+ is missing, stop and tell the user.
3. Copy the script bundled with this plugin to a stable location (the plugin directory changes on updates, so do not point settings at it):
   - Source: `${CLAUDE_PLUGIN_ROOT}/scripts/ai_reset_line.py`
   - Destination: `~/.claude/ai-reset-line/ai_reset_line.py` (create the directory if needed).
4. Read `~/.claude/settings.json` (treat a missing file as `{}`).
   - If it already has a `statusLine` entry, show it to the user and ask before replacing it.
   - Otherwise set only this key and keep every other key unchanged:
     ```json
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.claude/ai-reset-line/ai_reset_line.py --style STYLE",
       "refreshInterval": 30
     }
     ```
     Replace `STYLE` with the chosen style.
5. Test it by piping a sample into the script and show the user the output:
   `echo '{"model":{"display_name":"Test"},"context_window":{"used_percentage":12}}' | python3 ~/.claude/ai-reset-line/ai_reset_line.py --no-cache`
6. Tell the user the 5h and 7d parts appear after the first response in a session, and only for subscription plans (API key sessions show model and context only).

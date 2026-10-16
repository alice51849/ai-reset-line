#!/usr/bin/env python3
"""ai-reset-line: a one-line status for Claude Code (and a summary for Codex CLI).

Reads the Claude Code status line JSON from stdin and prints one line with the
model, 5-hour and 7-day usage with reset times, and context window usage.

Design rules:
  * Standard library only, Python 3.9+.
  * No network requests, no telemetry, never reads tokens or credentials.
  * Missing or malformed fields degrade to a shorter line; the script never
    raises on bad input.
"""

import argparse
import datetime as _dt
import glob
import json
import os
import sys
import tempfile
import time

__version__ = "0.1.0"

SEP = " · "  # middle dot
RESET_MARK = "↻"  # clockwise arrow
BAR_FULL = "▓"
BAR_EMPTY = "░"

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

CODEX_TAIL_BYTES = 4 * 1024 * 1024
CODEX_MAX_FILES = 30


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(value):
    """Return value as float, or None if it is not a usable number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return None
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _epoch(value):
    """Normalise a reset timestamp to epoch seconds.

    Accepts epoch seconds (documented), epoch milliseconds, and ISO 8601
    strings, so a future format change does not break the line.
    """
    n = _num(value)
    if n is not None:
        if n > 1e12:  # milliseconds
            n = n / 1000.0
        return n if n > 0 else None
    if isinstance(value, str) and value:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = _dt.datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed.timestamp()
    return None


def _get(obj, *path):
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def fmt_duration(seconds):
    """1h18m, 45m, 2d4h, <1m."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "<1m"
    minutes = seconds // 60
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    if days:
        return "%dd%dh" % (days, hours)
    if hours:
        return "%dh%02dm" % (hours, mins)
    return "%dm" % mins


def fmt_clock(epoch, now):
    """Local time: 'HH:MM' if today, otherwise 'Thu 09:00'."""
    when = time.localtime(epoch)
    today = time.localtime(now)
    hm = time.strftime("%H:%M", when)
    if (when.tm_year, when.tm_yday) == (today.tm_year, today.tm_yday):
        return hm
    if epoch - now < 6 * 86400:
        return time.strftime("%a", when) + " " + hm
    return time.strftime("%b %d", when) + " " + hm


def fmt_pct(p):
    if p is None:
        return "?"
    return "%d%%" % int(round(p))


def bar(p, width=10):
    if p is None:
        return BAR_EMPTY * width
    filled = int(round(max(0.0, min(100.0, p)) / 100.0 * width))
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)


def use_color(args, env=None):
    env = os.environ if env is None else env
    if getattr(args, "no_color", False):
        return False
    if env.get("NO_COLOR", "") != "":
        return False
    return True


def paint(text, pct, color):
    if not color or pct is None:
        return text
    if pct >= 80:
        code = RED
    elif pct >= 50:
        code = YELLOW
    else:
        code = GREEN
    return code + text + RESET


# ---------------------------------------------------------------------------
# Claude Code status line input
# ---------------------------------------------------------------------------

def parse_window(raw):
    """Return {'used_percentage': float|None, 'resets_at': float|None} or None."""
    if not isinstance(raw, dict):
        return None
    used = _num(raw.get("used_percentage"))
    if used is None:
        used = _num(raw.get("used_percent"))
    resets = raw.get("resets_at")
    if resets is None:
        resets = raw.get("reset_at")
    resets = _epoch(resets)
    if used is None and resets is None:
        return None
    return {"used_percentage": used, "resets_at": resets}


def parse_status(data):
    """Extract only the fields this tool shows. Never raises."""
    if not isinstance(data, dict):
        data = {}
    model = _get(data, "model", "display_name") or _get(data, "model", "id")
    if not isinstance(model, str):
        model = None
    ctx = _num(_get(data, "context_window", "used_percentage"))
    limits = data.get("rate_limits")
    five = seven = None
    if isinstance(limits, dict):
        five = parse_window(limits.get("five_hour"))
        seven = parse_window(limits.get("seven_day"))
    return {
        "model": model,
        "five_hour": five,
        "seven_day": seven,
        "context_used_percentage": ctx,
    }


def _window_text(label, win, now, style, color, weekly):
    pct = win.get("used_percentage")
    resets = win.get("resets_at")
    if resets is not None and resets <= now:
        # The window has rolled over since this data was produced.
        return label + " " + (RESET_MARK if style != "compact" else "") + "reset"
    if style == "bar":
        head = label + " " + paint(bar(pct), pct, color) + " " + fmt_pct(pct)
    elif style == "compact":
        head = label + ":" + paint(fmt_pct(pct), pct, color)
    else:
        head = label + " " + paint(fmt_pct(pct), pct, color)
    if resets is None:
        return head
    if weekly and resets - now > 86400:
        when = fmt_clock(resets, now)
    else:
        when = fmt_duration(resets - now)
    if style == "compact":
        return head + "/" + when.replace(" ", "")
    return head + " " + RESET_MARK + when


def render(status, style="plain", color=False, now=None):
    now = time.time() if now is None else now
    parts = []
    if status.get("model"):
        parts.append(status["model"])
    if status.get("five_hour"):
        parts.append(_window_text("5h", status["five_hour"], now, style, color, False))
    if status.get("seven_day"):
        parts.append(_window_text("7d", status["seven_day"], now, style, color, True))
    ctx = status.get("context_used_percentage")
    if ctx is not None:
        if style == "compact":
            parts.append("ctx:" + fmt_pct(ctx))
        elif style == "bar":
            parts.append("ctx " + bar(ctx, 5) + " " + fmt_pct(ctx))
        else:
            parts.append("ctx " + fmt_pct(ctx))
    if not parts:
        return "ai-reset-line: waiting for data"
    sep = " " if style == "compact" else SEP
    return sep.join(parts)


# ---------------------------------------------------------------------------
# Cache (~/.cache/ai-reset-line/last.json)
# ---------------------------------------------------------------------------

def cache_path(env=None):
    env = os.environ if env is None else env
    override = env.get("AI_RESET_LINE_CACHE")
    if override:
        return override
    base = env.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "ai-reset-line", "last.json")


def write_cache(status, path, now=None):
    """Store the last parsed limits. Only derived numbers, no session data."""
    if not (status.get("five_hour") or status.get("seven_day")):
        return False
    record = {
        "source": "claude-code-statusline",
        "saved_at": int(time.time() if now is None else now),
        "model": status.get("model"),
        "five_hour": status.get("five_hour"),
        "seven_day": status.get("seven_day"),
        "context_used_percentage": status.get("context_used_percentage"),
    }
    try:
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".last-", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def read_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Codex CLI local session files (read-only)
# ---------------------------------------------------------------------------

def codex_home(env=None):
    env = os.environ if env is None else env
    return env.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def _codex_window(raw, line_ts):
    if not isinstance(raw, dict):
        return None
    used = _num(raw.get("used_percent"))
    minutes = _num(raw.get("window_minutes"))
    resets = _epoch(raw.get("resets_at"))
    if resets is None:
        # Older Codex builds stored a relative offset instead.
        rel = _num(raw.get("resets_in_seconds"))
        if rel is not None and line_ts is not None:
            resets = line_ts + rel
    if used is None and resets is None:
        return None
    return {"used_percent": used, "window_minutes": minutes, "resets_at": resets}


def parse_codex_line(line):
    """Return a snapshot dict from one rollout JSONL line, or None."""
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    if not isinstance(obj, dict) or obj.get("type") != "event_msg":
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict):
        return None
    ts = _epoch(obj.get("timestamp"))
    primary = _codex_window(limits.get("primary"), ts)
    secondary = _codex_window(limits.get("secondary"), ts)
    if not (primary or secondary):
        return None
    name = limits.get("limit_name") or limits.get("limit_id")
    plan = limits.get("plan_type")
    return {
        "timestamp": ts,
        "limit_name": name if isinstance(name, str) else None,
        "plan_type": plan if isinstance(plan, str) else None,
        "primary": primary,
        "secondary": secondary,
    }


def _tail_lines(path, max_bytes=CODEX_TAIL_BYTES):
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        start = max(0, size - max_bytes)
        fh.seek(start)
        chunk = fh.read()
    text = chunk.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start > 0 and lines:
        lines = lines[1:]  # first line is probably cut in half
    return lines


def latest_codex_snapshot(home=None):
    """Find the newest token_count event with rate limits.

    Returns (snapshot or None, note string or None).
    """
    home = home or codex_home()
    pattern = os.path.join(home, "sessions", "**", "*.jsonl")
    files = glob.glob(pattern, recursive=True)
    if not files:
        compressed = glob.glob(os.path.join(home, "sessions", "**", "*.jsonl.zst"), recursive=True)
        if compressed:
            return None, "only compressed (.jsonl.zst) session files found; not readable without extra tools"
        return None, "no session files under %s" % os.path.join(home, "sessions")

    def mtime(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0

    files.sort(key=mtime, reverse=True)
    for path in files[:CODEX_MAX_FILES]:
        try:
            lines = _tail_lines(path)
        except OSError:
            continue
        for line in reversed(lines):
            if '"token_count"' not in line:
                continue
            snap = parse_codex_line(line)
            if snap:
                snap["file"] = path
                return snap, None
    return None, "no rate limit events in the newest session files yet"


def codex_label(window_minutes):
    m = window_minutes
    if m is None:
        return "window"
    m = int(m)
    if m == 300:
        return "5h"
    if m == 10080:
        return "7d"
    if m % 1440 == 0:
        return "%dd" % (m // 1440)
    if m % 60 == 0:
        return "%dh" % (m // 60)
    return "%dm" % m


# ---------------------------------------------------------------------------
# --summary
# ---------------------------------------------------------------------------

def _summary_row(label, pct, resets, now, color):
    pct_text = paint(fmt_pct(pct).rjust(4), pct, color)
    if resets is None:
        tail = "reset time unknown"
    elif resets <= now:
        tail = "window has reset since this was recorded"
    else:
        tail = "resets in %s (%s)" % (fmt_duration(resets - now), fmt_clock(resets, now))
    return "  %-4s %s  %s" % (label, pct_text, tail)


def _next_pacific_midnight(now):
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        tz = ZoneInfo("America/Los_Angeles")
    except Exception:  # tz database missing on some systems
        return None
    local = _dt.datetime.fromtimestamp(now, tz)
    nxt = (local + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.timestamp()


def summary(now=None, color=False, cache_file=None, home=None):
    now = time.time() if now is None else now
    out = []

    out.append("Claude Code")
    cached = read_cache(cache_file or cache_path())
    if not cached:
        out.append("  no cached reading yet (shown after the status line has run with usage data)")
    else:
        saved = _num(cached.get("saved_at"))
        age = fmt_duration(now - saved) + " ago" if saved else "unknown time"
        model = cached.get("model") or "unknown model"
        out.append("  last seen %s, %s" % (age, model))
        for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
            win = cached.get(key)
            if isinstance(win, dict):
                out.append(_summary_row(label, _num(win.get("used_percentage")),
                                        _epoch(win.get("resets_at")), now, color))

    out.append("")
    out.append("Codex CLI")
    snap, note = latest_codex_snapshot(home)
    if not snap:
        out.append("  " + note)
    else:
        ts = snap.get("timestamp")
        age = fmt_duration(now - ts) + " ago" if ts else "unknown time"
        extra = ", ".join(x for x in (snap.get("limit_name"), snap.get("plan_type")) if x)
        out.append("  last seen %s%s" % (age, (", " + extra) if extra else ""))
        for key in ("primary", "secondary"):
            win = snap.get(key)
            if win:
                out.append(_summary_row(codex_label(win.get("window_minutes")),
                                        win.get("used_percent"), win.get("resets_at"), now, color))

    out.append("")
    out.append("Gemini")
    nxt = _next_pacific_midnight(now)
    note = "  Gemini API requests-per-day quotas reset at midnight Pacific time"
    if nxt:
        note += " (next: %s, in %s)" % (fmt_clock(nxt, now), fmt_duration(nxt - now))
    out.append(note)
    out.append("  (published schedule, not a live reading)")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="ai-reset-line",
        description="One-line usage and reset countdowns for the Claude Code status line.",
    )
    p.add_argument("--style", choices=("plain", "bar", "compact"),
                   default=os.environ.get("AI_RESET_LINE_STYLE", "plain"))
    p.add_argument("--summary", action="store_true",
                   help="print the last Claude reading plus Codex CLI local session data")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colors (NO_COLOR also works)")
    p.add_argument("--no-cache", action="store_true", help="do not write ~/.cache/ai-reset-line/last.json")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def main(argv=None, stdin=None, stdout=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    args = build_parser().parse_args(argv)
    if args.style not in ("plain", "bar", "compact"):
        args.style = "plain"
    color = use_color(args)

    if args.summary:
        stdout.write(summary(color=color) + "\n")
        return 0

    try:
        raw = stdin.read()
    except (OSError, UnicodeDecodeError):
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    status = parse_status(data)
    if not args.no_cache:
        write_cache(status, cache_path())
    stdout.write(render(status, style=args.style, color=color) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

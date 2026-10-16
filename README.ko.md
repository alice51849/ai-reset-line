# ai-reset-line

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

Claude Code 상태 표시줄(status line)에 5시간 한도와 주간 한도의 사용률, 리셋까지 남은 시간을 보여 주는 스크립트입니다. `--summary`로 Codex CLI의 로컬 세션 파일도 함께 읽습니다. API 키 불필요, 네트워크 통신 없음, 텔레메트리 없음.

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
```

위는 `bin/ai-reset-line`의 실제 출력입니다(모델 이름은 Claude Code가 넘겨주는 `model.display_name`을 그대로 표시하며, "Large"는 테스트용 임시 이름입니다).

## 기능

- Claude Code가 상태 표시줄 명령에 표준 입력으로 넘겨주는 JSON을 읽습니다.
- 한 줄로 표시: 모델, 5시간 사용률과 리셋까지 남은 시간, 7일 사용률과 리셋 시각, 컨텍스트 사용률.
- 값이 없으면(API 키 사용 시, 세션 시작 직후 등) 그 부분만 생략하고 오류를 출력하지 않습니다.
- 스타일 3가지: `plain`, `bar`, `compact`. `NO_COLOR` 지원. 시각은 로컬 시간대로 표시합니다.
- `--summary`는 Claude의 마지막 값과 `~/.codex/sessions`에 있는 Codex CLI 최신 사용 한도를 함께 보여 줍니다.
- Python 3.9 이상 표준 라이브러리만 사용. 본체는 `src/ai_reset_line.py` 파일 하나입니다.

## 설치

하나를 고르세요.

### A. git clone (권장)

```sh
git clone https://github.com/alice51849/ai-reset-line ~/.local/share/ai-reset-line
```

그다음 [설정](#설정)의 스니펫을 `~/.claude/settings.json`에 추가합니다.

### B. Claude Code 플러그인

Claude Code 안에서:

```text
/plugin marketplace add alice51849/ai-reset-line
/plugin install ai-reset-line@ai-reset-line
/ai-reset-line:reset-line-setup
```

설정 명령이 스크립트를 `~/.claude/ai-reset-line/ai_reset_line.py`로 복사하고 사용자 설정에 `statusLine`을 추가합니다(이미 설정이 있으면 먼저 확인합니다). 스타일도 지정할 수 있습니다: `/ai-reset-line:reset-line-setup bar`

### C. 파일 하나만

```sh
mkdir -p ~/.claude/ai-reset-line
curl -fsSL https://raw.githubusercontent.com/alice51849/ai-reset-line/main/src/ai_reset_line.py \
  -o ~/.claude/ai-reset-line/ai_reset_line.py
```

설정에서는 `"command": "python3 ~/.claude/ai-reset-line/ai_reset_line.py"`를 사용합니다.

## 설정

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

`refreshInterval`은 선택 사항입니다. N초마다 명령을 다시 실행하므로 아무 작업을 하지 않을 때도 카운트다운이 갱신됩니다.

| 옵션 | 의미 |
|---|---|
| `--style plain` | `Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%` (기본값) |
| `--style bar` | 5h/7d에 10칸, 컨텍스트에 5칸 막대 추가 |
| `--style compact` | `Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%` |
| `--no-color` | 색 없음 (`NO_COLOR`에 빈 값이 아닌 값을 넣어도 동일) |
| `--no-cache` | `~/.cache/ai-reset-line/last.json`을 쓰지 않음 |
| `--summary` | 아래의 여러 줄 요약 출력 |

`AI_RESET_LINE_STYLE`로 기본 스타일을, `XDG_CACHE_HOME` 또는 `AI_RESET_LINE_CACHE`로 캐시 위치를 바꿀 수 있습니다.

## 출력 설명

세 가지 스타일의 실제 출력:

```text
Large · 5h 42% ↻1h18m · 7d 63% ↻Tue 01:41 · ctx 38%
Large · 5h ▓▓▓▓░░░░░░ 42% ↻1h18m · 7d ▓▓▓▓▓▓░░░░ 63% ↻Tue 01:41 · ctx ▓▓░░░ 38%
Large 5h:42%/1h18m 7d:63%/Tue01:41 ctx:38%
```

| 표시 | 원본 필드 | 설명 |
|---|---|---|
| 모델 | `model.display_name` | |
| `5h 42% ↻1h18m` | `rate_limits.five_hour.used_percentage`, `.resets_at` | 5시간 창. `resets_at`(Unix epoch 초)까지 남은 시간을 표시합니다. |
| `7d 63% ↻Tue 01:41` | `rate_limits.seven_day.used_percentage`, `.resets_at` | 주간 창. 로컬 요일과 시각으로 표시하며, 남은 시간이 24시간 미만이면 카운트다운으로 바뀝니다. |
| `ctx 38%` | `context_window.used_percentage` | 컨텍스트 창 사용률. |
| `↻reset` | | Claude Code가 데이터를 보낸 뒤 리셋 시각이 지났다는 뜻입니다. |

색: 50% 미만 초록, 50% 이상 노랑, 80% 이상 빨강.

사용량 데이터가 없으면 짧게 표시됩니다:

```text
Medium · ctx 13%          # API 키 사용: rate_limits 없음
Medium                    # 세션 시작 직후: 컨텍스트 정보도 아직 없음
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

- **Claude Code**: 상태 표시줄이 마지막으로 받은 값(`~/.cache/ai-reset-line/last.json`). 위에 보이는 숫자(모델 이름, 사용률, 리셋 시각)만 저장하며 세션 ID, 경로, 프롬프트는 저장하지 않습니다.
- **Codex CLI**: `~/.codex/sessions/**/*.jsonl`(또는 `$CODEX_HOME/sessions`)에서 `rate_limits`가 들어 있는 가장 최근 `token_count` 이벤트. 읽기 전용. `primary`/`secondary`는 `window_minutes`로 라벨을 붙입니다(300 → `5h`, 10080 → `7d`).
- **Gemini**: Google이 공개한 Gemini API 할당량 리셋 시각을 바탕으로 한 고정 안내입니다. 아무것도 조회하지 않습니다.

## 개인정보

- 실행 중 네트워크 요청이 없습니다. 네트워크 관련 모듈을 import하지 않는다는 것을 테스트로 확인합니다.
- OAuth 토큰, API 키, 쿠키, 자격 증명 파일을 읽지 않습니다.
- 텔레메트리·분석 없음.
- 쓰는 파일은 위의 작은 캐시 파일뿐입니다. `--no-cache`로 끌 수 있습니다.

## FAQ

**5h / 7d가 보이지 않아요.**
Claude Code는 claude.ai 구독 플랜에만, 그리고 세션에서 첫 응답이 온 뒤에만 `rate_limits`를 넘겨줍니다. API 키 사용 시에는 표시되지 않습니다. 각 창은 따로 빠질 수 있고, 리셋 시각이 지난 창은 Claude Code가 제외합니다.

**자리를 비운 동안 카운트다운이 멈춰요.**
상태 표시줄은 이벤트가 있을 때 갱신됩니다. `statusLine`에 `"refreshInterval": 30`(초)을 추가하세요.

**Codex 한도는 어떻게 보나요?**
`ai-reset-line --summary`를 실행하세요. Codex CLI는 응답마다 사용 한도 스냅샷을 로컬 세션 파일에 기록하고, 이 도구는 가장 최근 것을 읽습니다. 압축된 `.jsonl.zst` 파일만 있으면 건너뜁니다(추가 도구가 필요하기 때문).

**Windows에서 쓸 수 있나요?**
WSL이나 Git Bash에서 사용하거나, 설정에서 Python을 직접 지정하세요: `"command": "python C:/path/to/ai_reset_line.py"`

**`/usage`와 무엇이 다른가요?**
`/usage`는 실행해서 확인하는 명령입니다. 이 도구는 Claude Code가 상태 표시줄에 넘겨주는 데이터만 사용해 같은 종류의 숫자를 항상 보이게 합니다.

**내 스크립트에서 쓸 수 있나요?**
네. `import ai_reset_line` 후 `parse_status(json_dict)`와 `render(status, style)`를 호출하세요.

## 개발

```sh
python3 -m unittest discover -s tests
sh -n bin/ai-reset-line && shellcheck bin/ai-reset-line
```

`src/ai_reset_line.py`를 수정했다면 `plugins/ai-reset-line/scripts/`에도 복사하세요(두 파일이 다르면 테스트가 실패합니다).

## Away from your desk?

UsageNow는 같은 종류의 한도와 리셋 카운트다운(Claude 5시간 한도와 주간 한도, ChatGPT Codex 5시간 창과 주간 창, GitHub Copilot 프리미엄 요청, Gemini 일일 요청 한도)을 홈 화면·잠금 화면 위젯에 보여 주고, 원하는 퍼센트에서 알림을 보내는 iPhone·iPad·Apple Watch용 앱입니다. 이 스크립트의 작성자가 만들었습니다.
https://apps.apple.com/app/id6818607603?pt=118326163&ct=bm_usagenow_ww_gh&mt=8

## 라이선스

MIT. [LICENSE](LICENSE)를 참고하세요.

Anthropic, OpenAI, GitHub, Google과 제휴 관계가 없습니다. Claude와 Claude Code는 Anthropic의 상표입니다. OpenAI, ChatGPT, Codex는 OpenAI의 상표입니다. GitHub와 GitHub Copilot은 GitHub의 상표입니다. Gemini는 Google의 상표입니다. iPhone, iPad, Apple Watch는 Apple Inc.의 상표입니다. 그 밖의 상표는 각 소유자에게 있습니다.

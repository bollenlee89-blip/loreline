<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame`은 **누가** 썼는지 알려줍니다. `loreline`은 **왜**인지 알려줍니다.

어떤 git 저장소든 항상 최신 상태의 지식 베이스로 바꿔 주는 로컬 우선 에이전트입니다.<br>코드 한 줄을 가리키면, 그 뒤에 있는 결정, 풀 리퀘스트, 논의, 관련된 사람을 알려줍니다.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>실제 오픈소스 저장소에서 실행한 웹 UI(<code>loreline serve</code>). "Why it exists" 문장은 연결한 LLM이 작성합니다.</sub>

</div>

---

## 왜 필요한가요?

모든 코드베이스에는 이상해 보이지만 이유가 있는 코드가 있습니다. `sleep(0.3)`, 재시도 3회, 특정 고객만을 위한 이상한 예외 처리. 그 이유는 2021년의 PR 설명, 코드 리뷰 댓글, Slack 스레드, 혹은 누군가의 머릿속에만 있습니다. 이유를 찾지 못하면 아무도 건드리지 못하거나, "정리"하다가 예전 버그를 다시 들여오게 됩니다.

`loreline`은 모든 코드 줄을 그 뒤의 이야기와 연결합니다:

```console
$ loreline why app/upload.py:42

⟡ app/upload.py:42
  │     for attempt in range(3):  # S3 drops ~1% of PUTs

Why it exists
  Uploads are retried three times because S3 intermittently returned 503s under load
  [C1]. The fix came from issue #7 ("Uploads fail randomly") and was merged in [PR#42],
  where a reviewer noted 3 matches the AWS SDK default.
  Decision: retry failed uploads up to 3 times instead of failing the request.

[C1] introduced by 9f2c1e7a Retry uploads three times
     Ada Lovelace · 2024-03-02
     PR #42 Retry flaky uploads  https://github.com/acme/app/pull/42
       issue #7 Uploads fail randomly
       💬 cy: 3 matches the SDK default, approving
```

## 기능

- **어떤 줄, 함수, 파일에도 `why`.** `git blame -w -M -C`와 `git log -L`로 줄의 이력을 따라가며, 코드 이동과 공백 변경은 건너뜁니다(`.git-blame-ignore-revs`도 지원).
- **오프라인에서도 PR을 찾습니다.** 머지 커밋과 squash 커밋에서 PR 번호를 읽고, 해당 커밋을 들여온 머지까지 거슬러 올라갑니다. GitHub 토큰이 있으면 PR 설명, 리뷰 댓글, 연결된 이슈도 가져옵니다.
- **채팅도 기록의 일부입니다.** Slack·Discord 내보내기, JSONL, 텍스트 메모를 가져올 수 있습니다. 커밋, PR, 파일을 언급한 메시지는 자동으로 해당 코드에 연결됩니다.
- **이력에 질문하세요.** `loreline ask "why did we drop Redis?"`는 커밋, PR, 이슈, 채팅을 검색하고(SQLite FTS5) 출처와 함께 답합니다.
- **항상 최신.** `loreline init`이 git hooks를 설치해 커밋, 머지, 리베이스 때마다 인덱스가 갱신됩니다. 폴링을 원하면 `loreline watch`도 있습니다.
- **지식 지도.** `loreline map -o LORE.md`는 파일마다 왜 존재하는지 한 줄씩 씁니다. 파일 단위로 캐시되어 바뀐 파일만 다시 생성합니다.
- **어떤 LLM이든, 없어도 됩니다.** Ollama, LM Studio, llama.cpp, vLLM, OpenAI 호환 API, Anthropic Claude. LLM이 없어도 전체 근거 목록을 볼 수 있습니다.
- **코딩 에이전트와 연동.** `loreline mcp`는 MCP 서버라서 Claude Code, Cursor, Windsurf, Zed 등이 코드를 지우기 전에 "이건 왜 여기 있지?"라고 물어볼 수 있습니다.
- **로컬 우선, 기본값은 비공개.** 모든 데이터는 `.git/loreline/`에 저장됩니다. 호스팅 LLM을 쓰지 않는 한 아무것도 밖으로 나가지 않으며, LLM 프롬프트에서는 작성자 이메일이 가려집니다.
- **의존성 제로.** 순수 Python 표준 라이브러리와 `git`만 사용합니다. 몇 초면 설치됩니다.

## 설치

이미 가진 도구로 명령 하나면 됩니다:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Python 3.9 이상과 git이 필요합니다. `git-why` 명령도 함께 설치되므로 `git why file.py:42`도 쓸 수 있습니다.

## 빠른 시작

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### LLM 연결(선택)

`loreline`은 자동으로 고릅니다: 실행 중인 **Ollama** → `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` 순서. 직접 지정하려면:

```bash
# Local, fully private
ollama pull qwen2.5-coder && loreline config set llm.provider ollama && loreline config set llm.model qwen2.5-coder

# Any OpenAI-compatible server (LM Studio, llama.cpp, vLLM, OpenRouter, Groq...)
loreline config set llm.provider openai
loreline config set llm.base_url http://localhost:1234/v1
loreline config set llm.model your-model

# Anthropic
export ANTHROPIC_API_KEY=...
```

`--global`을 붙이면 모든 저장소에 적용됩니다. `loreline doctor`로 설정을 점검하세요.

### 풀 리퀘스트 맥락(선택)

GitHub 저장소라면 `GITHUB_TOKEN`, `GH_TOKEN` 또는 `gh auth` 로그인을 사용해 PR 설명, 리뷰, 연결된 이슈를 가져오고 로컬에 캐시합니다. 토큰이 없어도 이력에서 PR 번호는 찾아냅니다.

### 팀 채팅(선택)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Claude Code, Cursor 등 에이전트에서 사용하기

```bash
claude mcp add loreline -- loreline mcp
```

Cursor, Windsurf 등 MCP 클라이언트에서는 명령 `loreline`, 인자 `["mcp"]`로 서버를 추가하세요. 에이전트는 `loreline_why`와 `loreline_ask` 두 도구를 쓸 수 있습니다.

## 명령어

| 명령어 | 설명 |
| --- | --- |
| `loreline init` | 저장소를 인덱싱하고 자동 갱신 git hooks 설치 |
| `loreline why <path>[:line\|:symbol]` | 줄, 함수, 파일이 왜 존재하는지 설명 |
| `loreline ask "<question>"` | 프로젝트 이력으로 질문에 답하고 출처 표시 |
| `loreline map [-o LORE.md]` | 모든 파일이 왜 존재하는지 정리한 지식 지도 작성 |
| `loreline serve` | 로컬 웹 UI: 파일을 둘러보고 아무 줄이나 클릭 |
| `loreline import <path...>` | Slack, Discord, JSONL, 텍스트 메모 가져오기 |
| `loreline mcp` | 코딩 에이전트용 MCP 서버로 실행 |
| `loreline index` / `watch` / `hooks` | 수동 인덱싱, 폴링 감시, hooks 관리 |
| `loreline config show\|set` / `doctor` | 설정과 상태 점검 |

## 동작 방식

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **인덱싱:** 커밋, 변경된 파일, PR 번호, PR 논의, 연결된 이슈, 채팅 메시지를 전문 검색이 가능한 로컬 SQLite 데이터베이스에 저장합니다.
2. **추적:** 질문한 줄에 대해 `git blame`이 그 줄을 들여온 커밋을, `git log -L`이 이후 그 줄을 바꾼 모든 커밋을 찾습니다.
3. **연결:** 각 커밋을 PR(커밋 메시지, 머지 커밋 또는 GitHub API에서)에, PR을 이슈·리뷰·채팅에 연결합니다.
4. **설명:** 근거를 그대로 보여주거나, 모든 주장에 출처를 달고 사실을 지어내지 말라는 엄격한 지시와 함께 LLM에 넘깁니다.

## 개인정보 보호

- 데이터베이스는 `.git/` 안에 있으므로 커밋되지 않고 작업 트리에도 나타나지 않습니다.
- 웹 UI는 `127.0.0.1`에만 바인딩되고 다른 호스트 이름의 요청을 거부해 DNS 리바인딩 공격을 막습니다.
- 로컬 모델(Ollama, llama.cpp 등)을 쓰면 아무것도 컴퓨터 밖으로 나가지 않습니다.
- LLM으로 보내는 내용에서 작성자 이메일을 가립니다(`privacy.redact_emails`, 기본 활성화).

## 로드맵

- [ ] GitLab / Gitea / Bitbucket 머지 리퀘스트 지원
- [ ] VS Code·JetBrains 확장(줄에 마우스 올리기 → why)
- [ ] FTS5와 함께 임베딩 검색
- [ ] "이유 만료" 알림: 줄이 존재하는 이유가 더 이상 유효하지 않을 때
- [ ] CI가 커밋하는 공유용 `LORE.md` 지도

아이디어와 PR을 환영합니다. [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고하세요.

## 라이선스

[MIT](../LICENSE)

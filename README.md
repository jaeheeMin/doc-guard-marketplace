# doc-guard-marketplace

빠른 이동: [저장소 소개](#저장소-소개) · [macOS 사용자](#macos-사용자) · [Windows 사용자](#windows-사용자) · [스킬 목록](#스킬-목록) · [Ouroboros 설치](#ouroboros-설치) · [스킬 사용 예제](#스킬-사용-예제)

## 저장소 소개

문서가 정해진 템플릿을 따르는지 검사하고, 맞지 않으면 거절하면서 쓸 템플릿을
안내하는 체계(**doc-guard**)를 만드는 저장소다. 이 저장소는 그 체계의 **원본**
이고, 두 가지를 담는다.

- `checker/` — 검사 엔진. 문서를 읽어 규칙 위반 목록을 낸다.
- `plugins/doc-guard/` — 위 엔진을 부르는 Claude Code 플러그인. 이 저장소
  자체가 플러그인 마켓플레이스 역할을 하므로 팀원은 여기서 설치해 쓴다.

검사 엔진이 플러그인 **밖**에 있는 이유가 중요하다. 같은 엔진을 두 곳에서
부르기 때문이다.

| 진입점 | 도는 곳 | 엔진을 어떻게 얻나 |
|---|---|---|
| 플러그인 훅 | 팀원 PC 의 Claude | 이 마켓플레이스에서 설치 |
| GitHub Actions | GitHub 서버 | 대상 저장소에 번들로 들어가야 함 |

Actions 는 팀원 PC 에 설치된 플러그인을 쓸 수 없다. 그래서 엔진을 플러그인
안에 가두지 않고 따로 두어, 두 진입점이 같은 엔진을 호출하게 한다.

검사 규칙은 코드가 아니라 고객사별 `rules.yaml` 데이터로 둔다. 템플릿 원본과
`rules.yaml` 은 별도의 템플릿 저장소에서 관리한다(아직 만들지 않았다).

### 지금 어디까지 왔나

부트스트랩 단계다. 협업 하네스와 플러그인 뼈대만 있고 검사 엔진은 아직 없다.
다음 할 일은 검사 엔진 MVP(파일명·위치 규칙, md/docx 필수 섹션 규칙,
`rules.yaml` 스키마)다.

## 처음 시작하는 사람이 할 일

이 저장소는 macOS 와 Windows 참여자가 함께 쓴다. 아래에서 자신의 운영체제에
해당하는 절만 따라가면 설치를 마칠 수 있다. 두 절 모두 사전 요구사항 설치,
신뢰 다이얼로그 수락, git hook 설치, gh 인증 확인, 동작 확인의 같은 순서로
진행하지만, 설치 명령과 git hook 설치 방법 일부가 운영체제에 따라 다르다.

### macOS 사용자

#### 사전 요구사항

- git
- GitHub CLI(`gh`)
- jq — 없으면 Claude Code 훅이 git 명령을 모두 거부하고 세션 종료도 막는다
- Claude Code

#### 설치 명령

Homebrew 로 git 과 GitHub CLI 를 설치한다.

```bash
brew install git gh
```

jq 는 최근 macOS 에 기본 포함되어 있는 경우가 있으므로, 먼저 있는지 확인하고
없을 때만 설치한다.

```bash
jq --version || brew install jq
```

Claude Code 는 공식 설치 스크립트로 설치한다.

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Homebrew 를 선호하면 대신 아래 명령으로도 설치할 수 있다.

```bash
brew install --cask claude-code
```

(출처: [Claude Code 공식 설치 문서](https://code.claude.com/docs/en/setup))

#### 신뢰 다이얼로그 수락

**대화형 Claude Code 세션에서 이 폴더의 신뢰 다이얼로그를 수락한다.**
수락하기 전에는 저장소에 커밋된 훅이 실행되지 않아서 아래에서 설명하는
자동 동기화가 동작하지 않는다.

#### git hook 설치

터미널에서 아래 명령으로 git hook 을 설치한다. Claude Code 세션에서는 시작
훅이 이 설치를 자동으로 해 주므로, 이 단계는 터미널에서 직접 작업하는
참여자에게 필요하다.

```bash
bash scripts/install-hooks.sh
```

#### gh 인증 확인

```bash
gh auth status
```

인증되어 있지 않으면 이슈 생성과 PR 생성이 필요한 시점에 막힌다.

#### 동작 확인

아래 명령의 출력이 `.githooks` 이면 설치가 끝난 것이다.

```bash
git config --get core.hooksPath
```

### Windows 사용자

#### 사전 요구사항

- **Git for Windows(Git Bash) — 필수.** Claude Code 는 Windows 에서 Git
  Bash 를 찾지 못하면 PowerShell 로 훅을 실행하는데, 이 저장소의 훅은 bash
  스크립트라 그 경로에서는 실행되지 않고 보호가 조용히 사라진다. Git Bash
  를 표준 위치가 아닌 곳에 설치했다면 사용자 설정 파일
  `~/.claude/settings.json`(Windows 에서는
  `%USERPROFILE%\.claude\settings.json`)의 `env` 에
  `CLAUDE_CODE_GIT_BASH_PATH` 환경변수로 `bash.exe` 경로를 지정한다.
  설치 경로는 참여자마다 다르므로 저장소에 커밋된 `.claude/settings.json`
  에는 넣지 않는다.

  ```json
  {
    "env": {
      "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
    }
  }
  ```

  (근거: [Claude Code 공식 설치 문서](https://code.claude.com/docs/en/setup)
  의 "If Claude Code can't find Git Bash, set the path in your
  settings.json file" 와 위 예시)
- GitHub CLI(`gh`)
- jq — 없으면 Claude Code 훅이 git 명령을 모두 거부하고 세션 종료도 막는다
- Claude Code

#### 설치 명령

winget 으로 Git for Windows, GitHub CLI, jq 를 설치한다.

```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id jqlang.jq -e
```

Claude Code 도 winget 으로 설치한다.

```powershell
winget install Anthropic.ClaudeCode
```

(출처: [Claude Code 공식 설치 문서](https://code.claude.com/docs/en/setup). PowerShell
에서 `irm https://claude.ai/install.ps1 | iex` 로 설치해도 같은 결과다.)

설치가 끝나면 PATH 반영을 위해 터미널을 새로 연다.

#### 신뢰 다이얼로그 수락

**대화형 Claude Code 세션에서 이 폴더의 신뢰 다이얼로그를 수락한다.**
수락하기 전에는 저장소에 커밋된 훅이 실행되지 않아서 아래에서 설명하는
자동 동기화가 동작하지 않는다.

#### git hook 설치

Git Bash 창을 열어 아래 명령을 실행한다.

```bash
bash scripts/install-hooks.sh
```

PowerShell 창에서 그대로 이 명령을 치면, PATH 에 WSL 이 있을 경우 Git Bash
가 아니라 WSL 의 bash 가 대신 실행되거나, WSL 도 없으면 명령을 찾지 못하고
실패할 수 있다. PowerShell 에서만 작업한다면 대신 아래 한 줄로 같은 설정을
할 수 있다.

```powershell
git config core.hooksPath .githooks
```

`scripts/install-hooks.sh` 가 하는 일 중 핵심은 `core.hooksPath` 를
`.githooks` 로 설정하는 것이고, 위 한 줄이 정확히 그 설정과 같은 효과를
낸다. 그 스크립트가 추가로 하는 훅 파일 실행 권한 부여(`chmod`)는 Windows
에는 실행 권한 비트라는 개념 자체가 없어 필요하지 않다.

#### gh 인증 확인

```bash
gh auth status
```

인증되어 있지 않으면 이슈 생성과 PR 생성이 필요한 시점에 막힌다.

#### 동작 확인

아래 명령의 출력이 `.githooks` 이면 설치가 끝난 것이다.

```bash
git config --get core.hooksPath
```

#### Windows 전용 주의사항

- **CRLF 로 남은 스크립트.** `.gitattributes` 가 추가되기 전에 이 저장소를
  clone 했다면 셸 스크립트가 CRLF 줄바꿈으로 남아 있어 Git Bash 나 훅
  실행이 실패할 수 있다. 커밋하지 않은 변경이 없는지 먼저 `git status` 로
  확인한 뒤, Git Bash 에서 아래 명령으로 해당 파일만 다시 체크아웃한다.

  ```bash
  rm .githooks/* .claude/hooks/*.sh scripts/*.sh
  git checkout -- .githooks .claude/hooks scripts
  ```

- **GitHub Desktop.** GitHub Desktop 이 내장한 git 에는 bash 가 없어
  `.githooks` 의 훅이 실행되지 않거나 실패할 수 있다. 커밋과 푸시는 Claude
  Code 세션이나 Git Bash 에서 한다.
- **`/deliver` 의 푸시 접두 문법.** Claude Code 가 git 명령을 PowerShell
  도구로 실행하면 `DELIVER=1 git push ...` 같은 접두 문법이 동작하지 않는다.
  이 저장소에서 원격 푸시는 `/deliver` 스킬이 Bash 도구로 수행하므로, 이
  부분은 참여자가 따로 신경 쓸 필요가 없다.

## 스킬 목록

이 저장소에서 쓸 수 있는 스킬은 다섯 가지다. 이름을 클릭하면 사용 예제로
이동한다.

| 스킬 | 설명 |
|---|---|
| [`/start`](#start) | 새 작업을 시작한다. GitHub 이슈를 만들고 규칙에 맞는 브랜치를 만들어 착수한다. |
| [`/deliver`](#deliver) | 작업을 마무리한다. 커밋·원격 동기화·푸시·PR 생성까지 한 번에 처리한다. |
| [`/release`](#release) | 릴리즈 노트를 작성하고 GitHub Release 를 발행한다. |
| [`/wrapup`](#wrapup) | 세션에서 끝내지 못한 작업을 GitHub 이슈로 등록한다. |
| [`/intake`](#intake) | 기존 작업 디렉터리와 요구사항을 받아 이 저장소를 실제 내용으로 채운다. |

## Ouroboros 설치

Ouroboros 는 요구사항을 Socratic 인터뷰로 구체화하고 실행 결과를 평가하는
별도 플러그인이다(`ooo` 명령으로 호출). 이 저장소의 협업 하네스와는 독립된
도구이며, 실행 환경(Runtime)에 따라 설치 방법이 다르다. 에이전트가 이 절을
참고해 사용자의 실행 환경에 맞는 설치 경로를 안내한다.

### 사전 요구사항 (모든 환경 공통)

- Python 3.12 이상
- `uv`/`uvx` — 권장 방식. 없으면 `pipx`/`pip` 로 대체 설치할 수 있다.

macOS:

```bash
brew install uv
```

Windows:

```powershell
winget install --id astral-sh.uv -e
```

두 OS 모두 아래 대체 명령을 쓸 수 있다(우선순위: pipx > pip > brew > 벤더
설치 스크립트).

```bash
pipx install uv
pip install --user uv
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / WSL, 최후 수단
```

Python 3.12 자체가 없다면 `uv` 설치 후 아래로 받는다.

```bash
uv python install 3.12
```

### Claude Code

이 저장소는 Claude Code 플러그인 마켓플레이스로 Ouroboros 를 설치했다.
플러그인이 `~/.claude/mcp.json` 등록을 소유하므로 참여자가 직접 그 파일을
건드릴 필요는 없다. Claude Code 세션 안에서 아래 명령만 실행하면 된다.

```
ooo setup
```

슬래시 명령 `/ouroboros:setup` 도 동일하게 동작한다.

### Codex

```bash
ouroboros setup --runtime codex
```

### GitHub Copilot CLI

```bash
pipx install 'ouroboros-ai[mcp]'   # 또는: uv tool install 'ouroboros-ai[mcp]'
ouroboros setup --runtime copilot
```

`gh auth token` 으로 GitHub 인증이 되어 있어야 사용 가능한 모델 목록을
조회할 수 있다. 인증이 없으면 내장된 기본 모델 목록으로 대체된다.

## 작업 한 바퀴

작업은 항상 `/start` 로 시작해서 `/deliver` 로 마친다.

```
사용자> /start 온보딩 문서에 예시 하나 추가

Claude> 이슈 #12 "온보딩 문서 예시 추가" 를 만들었습니다.
        브랜치 feat/12-add-onboarding-example 로 이동했습니다.
        작업을 시작하십시오.

(... 파일을 고치는 대화가 이어진다 ...)

사용자> /deliver

Claude> 변경을 확인하고 커밋했습니다.
        origin/main 을 가져와 rebase 했습니다.
        푸시했습니다.
        PR #13 을 열었습니다: https://github.com/.../pull/13
```

이 한 바퀴 사이에는 직접 `git commit` 이나 `git push` 를 칠 필요가 없다. 두
스킬이 브랜치 이름, 커밋 메시지, PR 형식을 규칙에 맞게 알아서 정리한다.

## 자동으로 일어나는 일

- **세션을 시작하면** git hook 설치 상태를 확인해 필요하면 다시 설치하고,
  원격을 `fetch` 한 뒤 **브랜치와 무관하게** `pull --rebase` 까지 실행한다.
  main 에서는 이에 더해 "main 에서는 커밋할 수 없다" 는 안내가 따로
  붙는다. 리베이스가 충돌하면 자동으로 되돌리고 원격과의 차이를 직접
  확인하라고 알려준다. 지난 세션에서 넘어온 경고가 있으면 그것도 함께
  보여준다.
- **세션을 끝낼 때** 커밋되지 않은 변경이 남아 있으면 그대로 끝내지 않고
  `/deliver` 를 실행하도록 되돌려 보낸다. 한 번 되돌려 보냈는데도 변경이
  남아 있으면 그때는 세션을 끝내되, 다음 세션 시작 시 그 사실을 다시
  알려준다.

이 두 동작은 각각 `.claude/hooks/session-start-sync.sh` 와
`.claude/hooks/stop-deliver.sh` 가 수행한다.

## 막혔을 때

훅이 어떤 동작을 거부하면 우회하지 않는다. `--no-verify` 로 git hook 을
건너뛰거나 거부를 피해 가는 다른 명령을 찾지 않는다. 거부 메시지에는 대개
다음에 무엇을 하면 되는지가 함께 안내되어 있으므로 그 안내를 따른다. 안내가
지금 상황과 맞지 않거나 그래도 무엇을 해야 할지 모르겠으면, 판단을 사람에게
맡긴다.

## 적재 절차

이 절은 **에이전트가 읽고 그대로 수행하는 지시서다.** 기존 작업 디렉터리와
요구사항으로 이 저장소를 실제 내용으로 채우는 절차를 정의하며, 전체 절차는
`/intake` 스킬이 수행한다.

1. 사용자에게 두 가지를 받는다.
   - 기존 작업 디렉터리의 경로
   - 이 저장소가 담아야 할 요구사항 설명
2. 원본 디렉터리를 읽고 파일 목록을 파악한다. 각 파일이 규칙 문서인지, 반복
   실행하는 스크립트인지, 설계·계획 문서인지, 그 밖의 실제 작업 내용인지
   성격을 분류한다.
3. `rules/layout.md` 의 기준으로 각 파일의 목적지를 정한다. 규칙에 맞는
   디렉터리가 없는 파일은 저장소의 실제 내용으로 보고 적절한 위치를 새로
   정한다.
4. 원본 경로와 목적지 경로를 나란히 놓은 배치 계획 표를 만들어 사용자에게
   보여주고 승인받는다. 승인받기 전에는 파일을 옮기지 않는다.
5. 승인된 계획대로만 파일을 복사한다. 계획에서 제외한 파일이 있으면 각
   파일마다 제외한 이유를 함께 보고한다. 비밀값, 대용량 이진 파일, 참여자
   개인의 로컬 전용 설정은 이 저장소에 넣지 않는다. 자세한 기준은
   `rules/layout.md` 를 따른다.
6. 요구사항 설명을 읽고 `CLAUDE.md` 의 "이 저장소는 무엇인가" 절과 이 문서의
   "저장소 소개" 절을 실제 내용으로 채운다.
7. 요구사항에서 일감을 뽑아 GitHub 이슈로 쪼갠다. 각 이슈는 한 번의
   `/start` 로 착수할 수 있는 크기여야 한다. 이슈 제목·본문·라벨은
   `rules/issue-and-release.md` 의 형식을 따른다.
8. 배치 결과와 새로 만든 이슈 목록을 사용자에게 보고한다.

## 저장소를 새로 세울 때 할 일

원격은 이미 연결되어 있고 부트스트랩 커밋도 올라가 있다. 남은 설정은 아래와
같다. 이 절의 `git` 과 `gh` 명령은 macOS 와 Windows 에서 동일하다.

1. **(완료) main 최초 푸시.** 부트스트랩 커밋은 하네스 자체를 설치하는
   커밋이라 `.githooks/pre-push` 가 아직 적용되지 않은 상태에서 올라갔다.
   이후의 모든 푸시는 훅의 적용을 받으므로 `/deliver` 를 거쳐야 한다.
   같은 상황이 다시 생기면(새 저장소 부트스트랩) 최초 1회에 한해 아래처럼
   훅을 우회한다.

   ```bash
   git -c core.hooksPath= push -u origin main
   ```

   `core.hooksPath` 를 이 명령 하나에서만 빈 값으로 덮어써 그 순간만
   기본 훅 디렉터리(훅 없음)를 쓰게 하는 것이고, 저장소에 설정된
   `core.hooksPath` 값 자체는 바뀌지 않는다.

2. **이슈 라벨 다섯 개를 만든다.** `rules/issue-and-release.md` 가 정한
   라벨은 저장소에 자동으로 만들어지지 않는다. `gh issue create --label` 은
   라벨이 없으면 그대로 실패하므로, 원격을 연결한 뒤 첫 `/start` 가 이
   단계 없이는 막힌다.

   ```bash
   gh label create "type:feat" --color "0e8a16" --description "새 기능이나 새 문서 추가"
   gh label create "type:fix" --color "d73a4a" --description "잘못된 동작이나 내용 수정"
   gh label create "type:docs" --color "0075ca" --description "문서만 고치는 작업"
   gh label create "type:chore" --color "cfd3d7" --description "설정이나 잡무성 작업"
   gh label create "status:blocked" --color "b60205" --description "다른 작업이나 결정을 기다리는 상태"
   ```

3. **GitHub 저장소 설정에서 main 브랜치 보호 규칙을 켠다.**

   > **주의 — 지금은 이 단계를 할 수 없다.** 이 저장소는 개인 계정의
   > private 저장소이고 요금제가 Free 다. Free 요금제에서는 private
   > 저장소에 브랜치 보호 규칙과 필수 체크를 걸 수 없다. 따라서 현재
   > main 을 지키는 것은 로컬 git hook 과 Claude 훅뿐이고, 훅을 설치하지
   > 않은 clone 에서는 막을 수단이 없다. 서버 쪽 강제가 필요해지면
   > Team 요금제로 올리거나 조직 저장소로 옮긴 뒤 아래 설정을 적용한다.

   로컬
   git hook 은 이 저장소를 clone 한 사람이 `scripts/install-hooks.sh` 를
   실행해야만 작동하는 로컬 방어선일 뿐이다. 훅을 설치하지 않은 clone
   에서는 main 으로의 직접 커밋과 푸시를 막을 수단이 없으므로, 서버 쪽
   강제인 브랜치 보호 규칙이 최종 방어선이 된다. `rules/governance.md` 가
   요구하는 두 가지("작성자 본인이 아닌 사람이 읽은 뒤 병합", "squash
   merge 로 통일")를 실제로 지키게 하려면 아래 설정이 필요하다.

   - **Settings → Branches → `main` 에 branch protection rule 추가**
     - "Require a pull request before merging" 를 켠다.
     - "Require approvals" 를 켜고 최소 승인 수를 1 이상으로 둔다. GitHub
       는 PR 작성자 본인의 승인을 인정하지 않으므로, 이 설정만으로 "본인이
       아닌 사람이 읽은 뒤 병합" 이 강제된다.
   - **Settings → General → Pull Requests**
     - "Allow squash merging" 만 켜고, "Allow merge commits" 와 "Allow
       rebase merging" 은 끈다. 병합 방식을 squash 하나로 좁혀야 다른
       방식으로 병합하는 실수 자체가 불가능해진다.

4. **`/start` 와 `/deliver` 를 한 번 실제로 돌려 확인한다.** 원격이
   없던 동안에는 두 스킬 모두 이슈 생성과 PR 생성 부분이 동작하지 않고
   그 사실만 보고하도록 되어 있었다. 원격 연결 후 실제로 이슈가 만들어지고
   PR 이 열리는지 한 번 실행해서 확인한다.

---

## 스킬 사용 예제

### `/start`

새 작업을 시작할 때 사용한다. 작업 내용을 설명하면 GitHub 이슈를 만들고,
이슈 번호가 들어간 브랜치를 자동으로 만들어 준다.

```
사용자> /start 로그인 페이지에 비밀번호 찾기 링크 추가

Claude> 이슈 #5 "로그인 페이지 비밀번호 찾기 링크 추가" 를 만들었습니다.
        브랜치 feat/5-add-password-reset-link 로 이동했습니다.
        작업을 시작하십시오.
```

기존 이슈 번호를 지정하면 이슈 생성을 건너뛰고 바로 브랜치를 만든다.

```
사용자> /start #5

Claude> 이슈 #5 "로그인 페이지 비밀번호 찾기 링크 추가" 를 읽었습니다.
        브랜치 feat/5-add-password-reset-link 로 이동했습니다.
        작업을 시작하십시오.
```

### `/deliver`

작업을 마칠 때 사용한다. 변경 사항을 커밋하고, 원격과 동기화하고, 푸시하고,
PR 을 만들거나 갱신한다.

```
사용자> /deliver

Claude> 변경 사항을 확인합니다.
        커밋했습니다: "feat: 로그인 페이지에 비밀번호 찾기 링크 추가"
        origin/main 을 가져와 rebase 했습니다. 충돌 없음.
        푸시했습니다.
        PR #6 을 열었습니다: https://github.com/.../pull/6
```

기준 브랜치를 바꾸고 싶으면 `--base` 를 쓴다.

```
사용자> /deliver --base develop
```

### `/release`

릴리즈를 발행할 때 사용한다. 마지막 릴리즈 이후의 PR 과 이슈를 모아 릴리즈
노트를 작성하고, 승인 후 GitHub Release 를 만든다.

```
사용자> /release

Claude> 마지막 릴리즈 이후 병합된 PR 3건을 확인했습니다.
        릴리즈 노트를 작성했습니다.

        ## 2026.09.13

        ### 추가
        - 로그인 페이지 비밀번호 찾기 링크 추가 (#6)
        - 온보딩 문서 예시 추가 (#4)

        ### 수정
        - 메인 배너 깨진 링크 수정 (#8)

        이 내용으로 발행할까요?

사용자> 네

Claude> GitHub Release v2026.09.13 을 발행했습니다.
```

### `/wrapup`

세션에서 다 끝내지 못한 작업을 이슈로 남길 때 사용한다.

```
사용자> /wrapup

Claude> 이번 세션에서 남은 작업을 정리했습니다.

        1. 다크 모드 스타일 적용 미완료
        2. 모바일 반응형 레이아웃 점검 필요

        어떤 항목을 이슈로 등록할까요?

사용자> 둘 다

Claude> 이슈 #9 "다크 모드 스타일 적용" 을 만들었습니다.
        이슈 #10 "모바일 반응형 레이아웃 점검" 을 만들었습니다.
```

### `/intake`

기존 작업 디렉터리의 파일을 이 저장소로 가져올 때 사용한다. 파일을 분류하고
배치 계획을 보여준 뒤, 승인을 받아 복사한다. 요구사항에서 일감을 뽑아 이슈로
쪼개는 것까지 수행한다.

```
사용자> /intake /Users/me/old-project
        이 프로젝트는 고객 포털이고, 로그인·대시보드·알림 기능이 필요합니다.

Claude> 원본 디렉터리에서 파일 12개를 읽었습니다.

        | 원본 경로 | 목적지 | 분류 |
        |---|---|---|
        | src/App.js | src/App.js | 소스 코드 |
        | docs/plan.md | docs/plan.md | 설계 문서 |
        | .env | (제외) | 비밀값 포함 |

        이 계획대로 진행할까요?

사용자> 네

Claude> 파일 11개를 복사했습니다. .env 는 비밀값이 포함되어 제외했습니다.
        CLAUDE.md 의 저장소 소개를 갱신했습니다.

        요구사항에서 일감 3건을 뽑았습니다.
        이슈 #11 "로그인 기능 구현"
        이슈 #12 "대시보드 페이지 구현"
        이슈 #13 "알림 시스템 구현"
```

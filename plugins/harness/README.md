# harness 플러그인

고객사 Project Repository 에 설치해 쓰는 Blueward 하네스다. 새 저장소의 표준
구조를 만들고, 문서가 템플릿을 따르는지 검사하고(doc-guard), 협업 규칙과
`/harness:start` · `/harness:deliver` · `/harness:wrapup` Skill 을 한 번에 제공한다.

```
plugins/harness/
  .claude-plugin/plugin.json   플러그인 정의
  hooks/
    hooks.json                 네 훅을 선언
    pre_write_guard.py         문서 검사(doc-guard) — Write/Edit 직전에 막을지 정한다
    pre-bash-git-guard.sh      push 가드 — 스킬을 거치지 않은 git push 를 막는다
    session-start-sync.sh      세션 시작 때 원격과 동기화하고 남은 경고를 전한다
    stop-deliver.sh            세션 종료 때 커밋 안 된 변경을 알린다
  skills/
    start/SKILL.md             /harness:start — 이슈와 브랜치 생성
    deliver/SKILL.md           /harness:deliver — 커밋·동기화·푸시·PR
    wrapup/SKILL.md            /harness:wrapup — 남은 작업의 이슈화
    scaffold/                  /harness:scaffold — Project Repository 표준 구조 생성
  rules/                       위 Skill 이 참조하는 협업 규칙 5개
```

플러그인 이름은 `harness` 지만, 문서 검사 기능 자체는 여전히 **doc-guard** 라고
부른다. 훅 스크립트 이름(`pre_write_guard.py`), 검사 메시지("doc-guard: ..."),
문서 저장소가 불러 쓰는 재사용 워크플로(`.github/workflows/doc-guard.yml`),
검사 엔진의 CLI 이름(`doc-guard`)은 이름을 바꾸지 않았다. 바뀐 것은 이
플러그인 자체의 이름뿐이다.

실제 검사는 `checker/` 엔진이 한다. 이 플러그인은 껍데기이고, 엔진을 왜
플러그인 밖에 두는지는 `checker/README.md` 를 읽는다.

## 설치

```
/plugin marketplace add jaeheeMin/blueward-harness
/plugin install harness@blueward-harness
```

또는 프로젝트 설정(`.claude/settings.json`)의 `enabledPlugins` 에 추가해도 된다.

```json
{
  "enabledPlugins": ["harness@blueward-harness"]
}
```

플러그인은 저장소가 아니라 **사람** 에게 설치된다. 한 번 설치하면 어느
저장소를 열든 동작한다.

## 제공하는 것

### Skill 4개

플러그인 스킬은 이름 앞에 플러그인 이름이 붙으므로 아래 이름으로 나타난다.

| Skill | 하는 일 |
|---|---|
| `/harness:start` | 작업을 시작한다. 이슈를 만들고 규칙에 맞는 브랜치를 만든다 |
| `/harness:deliver` | 작업을 마무리한다. 커밋·동기화·푸시·PR 생성을 한 번에 |
| `/harness:wrapup` | 세션에서 끝내지 못한 작업을 이슈로 남긴다 |
| `/harness:scaffold` | 새 Project Repository 에 표준 구조를 만든다 |

### 훅 4개

| 훅 | 시점 | 하는 일 |
|---|---|---|
| `pre_write_guard.py` | `PreToolUse` (Write\|Edit) | 문서가 템플릿을 벗어나면 저장을 막는다(doc-guard) |
| `pre-bash-git-guard.sh` | `PreToolUse` (Bash\|PowerShell) | 스킬을 거치지 않은 `git push` 와 main 직접 커밋을 막는다 |
| `session-start-sync.sh` | `SessionStart` | 원격과 동기화하고 지난 세션에서 남은 경고를 전한다 |
| `stop-deliver.sh` | `Stop` | 커밋되지 않은 변경이 남았으면 `/harness:deliver` 를 안내한다 |

### 규칙 5개

`rules/branching.md`, `rules/commit-and-pr.md`, `rules/delegation.md`,
`rules/governance.md`, `rules/issue-and-release.md`. 위 Skill 들이 이 문서를
`<스킬의 base directory>/../../rules/`로 참조한다.

## 주의: 저장소에 같은 훅이 남아 있으면 두 번 돈다

이 플러그인을 설치한 저장소에 `.claude/hooks/` 와 `.claude/settings.json` 에
같은 훅(세션 시작 동기화, 세션 종료 안내, push 가드)이 이미 저장소 자체의
파일로 남아 있으면, 플러그인 훅과 저장소 훅이 **같은 이벤트에서 두 번** 돈다.
플러그인을 설치했다면 저장소 쪽 `.claude/hooks/` 의 같은 항목과
`.claude/settings.json` 의 같은 훅 등록을 지운다.

## 항상 지켜야 할 핵심은 각 저장소 CLAUDE.md 에 짧게 둔다

Plugin 은 세션에 상시 로드되는 지침(CLAUDE.md 같은 것)을 넣을 수 없다. "main
에는 직접 커밋하지 않는다", "푸시는 `/harness:deliver` 로 한다" 처럼 항상
지켜야 할 세 가지 원칙은 이 플러그인이 강제하더라도, 그 사실 자체는 각
Project Repository 의 CLAUDE.md 에 짧게 적어 둬야 세션이 매번 상기한다.

## 한계 — doc-guard 훅으로 잡을 수 없는 것

| 경로 | 훅이 도나 |
|---|---|
| Claude 가 md 문서를 쓰거나 고칠 때 | **돈다** |
| 팀원이 엑셀·워드·파워포인트에서 작업해 폴더에 넣을 때 | 안 돈다 |
| 사람이 편집기로 직접 저장할 때 | 안 돈다 |
| Bash 로 `cp`, `mv`, 리다이렉션을 쓸 때 | 안 돈다 |

**그래서 이 훅만으로는 절반이다.** 나머지는 GitHub Actions 가 커밋 시점에
잡는다. 문서 저장소 쪽에서 `.github/workflows/doc-guard.yml` 로 재사용
워크플로를 부른다.

## Skill: /harness:scaffold

새 고객사 Project Repository 를 처음 만들었을 때, 검사기가 기대하는 표준
구조 — 저장소 루트의 `templates/` 와 `rules/`, `docs/ssot/PRD.md`,
`conventions/`, `audit/`, `env/`, 그리고 PR·main 커밋마다 doc-guard 를
부르는 `.github/workflows/doc-guard.yml` — 를 한 번에 만들어 준다. 자세한
절차는 `skills/scaffold/SKILL.md` 를 읽는다.

## Audit

`/harness:scaffold` 가 `audit/changes/`(변경 기록)와 `audit/ledger/`(진행
원장)의 템플릿과 doc-guard 규칙도 함께 만든다(#43). 변경 기록은
`YYYYMMDD-<요약>.md` 로 기록 하나에 파일 하나를 써 여러 사람이 동시에
기록해도 PR 이 충돌하지 않게 하고, 진행 원장은 프로그램 하나에 파일 하나로
개발 건의 진행 상태를 표로 담는다. `/harness:prd` · `/harness:spec` ·
`/harness:deliver` Skill 이 이 형식으로 기록을 남길 예정이고, 사람이 직접
적어도 된다. 형식에 맞지 않는 기록(파일 이름, 필수 절)은
`rules/audit-changes.yaml` 과 `rules/audit-ledger.yaml` 이 doc-guard 로
검사한다.

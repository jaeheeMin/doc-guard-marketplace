# doc-guard 플러그인

문서를 저장하기 전에 고객사별 템플릿 규칙과 대조하고, 벗어나면 **거절하면서 쓸 템플릿을
안내한다.**

```
plugins/doc-guard/
  .claude-plugin/plugin.json   플러그인 정의
  hooks/
    hooks.json                 Write/Edit 직전에 아래 스크립트를 부르도록 선언
    pre_write_guard.py         회사 폴더를 찾고 엔진을 불러 막을지 정한다
  skills/scaffold/
    SKILL.md                   Project Repository 표준 구조를 만드는 절차
    scaffold.py                실제로 파일을 복사·치환하는 스크립트
    skeleton/                  만들어질 구조의 원본
```

플러그인은 껍데기다. 실제 검사는 저장소 루트의 `checker/` 엔진이 한다.
이유는 `checker/README.md` 를 읽는다.

## 어떻게 도나

```
Claude 가 문서를 저장하려 한다
        │
훅이 가로챈다 (PreToolUse)
        │
이 파일이 어느 회사 폴더 것인가  →  못 찾으면 소관이 아니므로 통과
        │
저장될 최종 모습을 만든다
  Write → 주어진 내용 그대로
  Edit  → 디스크 내용에 치환을 적용
        │
검사 엔진을 부른다
        │
   통과 ─────── 저장됨
   위반 ─────── 막고 위반 목록과 쓸 템플릿을 보여준다
   설정 오류 ── 막고 규칙 담당자에게 알리라고 안내한다
```

막을 수 있는 훅 시점은 `PreToolUse` 뿐이다. `PostToolUse` 는 도구가 이미 실행된 뒤라
되돌릴 수 없다. 대신 이 시점에는 파일이 아직 디스크에 없거나 옛 내용이므로, 저장될 최종
모습을 훅이 직접 만들어 봐야 한다.

위반과 설정 오류를 나눠 말하는 이유는 받는 사람이 다르기 때문이다. 문서를 올리는 팀원은
규칙 파일을 고칠 권한도 지식도 없다. 같은 메시지를 내면 자기 문서를 들여다보며 헤매게 된다.

## 설치

```
/plugin marketplace add jaeheeMin/blueward-harness
/plugin install doc-guard
```

플러그인은 저장소가 아니라 **사람** 에게 설치된다. 한 번 설치하면 어느 저장소를 열든
동작한다. `uv` 가 있어야 한다.

## 한계 — 이 훅으로 잡을 수 없는 것

| 경로 | 훅이 도나 |
|---|---|
| Claude 가 md 문서를 쓰거나 고칠 때 | **돈다** |
| 팀원이 엑셀·워드·파워포인트에서 작업해 폴더에 넣을 때 | 안 돈다 |
| 사람이 편집기로 직접 저장할 때 | 안 돈다 |
| Bash 로 `cp`, `mv`, 리다이렉션을 쓸 때 | 안 돈다 |

두 번째가 특히 중요하다. 실제 고객사 템플릿은 대부분 오피스 형식인데, 그 산출물은 해당
프로그램에서 작업해 폴더에 넣으므로 Claude 를 거치지 않는다. 훅이 불릴 일 자체가 없다.

**그래서 이 훅만으로는 절반이다.** 나머지는 GitHub Actions 가 커밋 시점에 잡는다.
문서 저장소 쪽에서 `.github/workflows/doc-guard.yml` 로 재사용 워크플로를 부른다.

## Skill: /scaffold

새 고객사 Project Repository 를 처음 만들었을 때, 검사기가 기대하는 표준
구조 — 저장소 루트의 `templates/` 와 `rules/`, `docs/ssot/PRD.md`,
`conventions/`, `audit/`, `env/`, 그리고 PR·main 커밋마다 doc-guard 를
부르는 `.github/workflows/doc-guard.yml` — 를 한 번에 만들어 준다.

고객사 이름과 프로젝트 이름을 받아 스켈레톤 파일을 저장소 루트에 복사하고,
파일 안의 자리표시자를 채운다. 이미 있는 파일은 절대 덮어쓰지 않고
건너뛴다. 자세한 절차는 `skills/scaffold/SKILL.md` 를 읽는다.

플러그인 스킬은 이름 앞에 플러그인 이름이 붙으므로, 실제로는
`/doc-guard:scaffold` 로 나타날 수 있다.

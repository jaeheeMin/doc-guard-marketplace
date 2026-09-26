---
name: scaffold
description: 새 고객사 Project Repository 를 처음 만들었을 때 표준 구조(templates/, rules/, docs/ssot/ 등)를 만든다. 사용자가 "스캐폴딩 해줘", "프로젝트 구조 만들어줘", "초기 세팅해줘" 라고 말할 때 사용한다.
---

# /harness:scaffold

새로 만든 Project Repository 에 doc-guard 가 기대하는 표준 구조를 만드는
입구다. `templates/` 와 `rules/` 를 저장소 루트에 두면, 검사 엔진이 문서에서
위로 올라가며 이 둘을 찾아 "여기가 회사 폴더다" 라고 판단한다.

1. 고객사 이름과 프로젝트 이름이 인자로 주어지지 않았으면, 한 번에 같이
   물어본다("어느 고객사, 어느 프로젝트인가요?").
2. `git rev-parse --show-toplevel` 로 현재 위치가 이 Project Repository 의
   루트인지 확인한다. 스캐폴딩은 항상 저장소 루트에서 실행한다.
3. 먼저 `--dry-run` 으로 돌려 무엇을 만들고 무엇을 건너뛸지 보여준 뒤, 문제가
   없으면 `--dry-run` 없이 다시 돌린다.

   ```bash
   uv run --no-project python "<이 스킬의 base directory>/harness:scaffold.py" \
     --client "<고객사>" --project "<프로젝트>" --dry-run
   ```

   `<이 스킬의 base directory>` 는 이 스킬이 로드될 때 위에 표시되는 경로다.
   `uv` 가 없으면 `python` 으로 바로 부른다.
4. 스크립트는 이미 있는 파일을 절대 덮어쓰지 않고 건너뛴다(`skipped`). 만든
   목록(`created`)과 건너뛴 목록을 사용자에게 보고한다.
5. 다음에 할 일을 안내한다.
   - 고객사에게 받은 Template 원본을 `templates/` 에 그대로 넣는다.
   - 그 Template 을 대조할 규칙을 `rules/` 에 추가한다(`rules/README.md`
     예시 참고).
   - 환경별 접속 URL 을 `env/` 에 적는다.
   - `.github/workflows/doc-guard.yml` 이 이제부터 이 저장소의 PR 과 main
     커밋마다 검사를 돌린다.
   - PRD 는 아직 없는 `/prd` Skill 로 만들 예정이다. 지금은
     `docs/ssot/PRD.md` 가 빈 스텁으로만 있다.

## 만들어지는 구조

```
CLAUDE.md                          이 저장소가 무엇인지, 디렉터리와 규칙 요약
docs/ssot/PRD.md                   요구사항의 정본(SSOT). 아직 빈 스텁
templates/README.md                고객사 템플릿 원본을 두는 자리
rules/README.md                    규칙 작성법과 예시
rules/ssot.yaml                    PRD 파일명을 고정하는 실제 동작 규칙
conventions/README.md              이 프로젝트에서만 통하는 Convention
audit/README.md                    Audit log·Program Ledger 가 쌓일 자리
env/README.md                      환경별 접속 URL(Credential 은 안 둠)
.github/workflows/doc-guard.yml    PR·main 커밋마다 doc-guard 를 부르는 워크플로
```

`rules/ssot.yaml` 을 지우지 않는다. `rules/` 에 `*.yaml` 이 하나도 없으면
모든 검사가 설정 오류로 실패한다.

## 안전장치

- 기존 파일을 덮어쓰지 않으므로 이미 세팅된 저장소에 다시 돌려도 안전하다.
- `docs/spec/` 이나 `src/` 처럼 아직 내용이 정해지지 않은 빈 폴더는 만들지
  않는다. git 은 빈 폴더를 추적하지 못하고, 그 구조는 나중 Skill 이 정한다.

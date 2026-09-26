# audit

무엇이 왜 바뀌었고 어디까지 진행됐는지를 남기는 자리다. 세션이 끊겨도 이어서
진행하고, 나중에 "왜 이렇게 됐나" 에 답하기 위해 쓴다. 두 종류를 둔다.

## audit/changes/ — 변경 기록

`YYYYMMDD-<요약>.md` 형식으로, 기록 하나에 파일 하나를 쓴다(예:
`20260926-결재단계추가.md`). 무엇이 왜 바뀌었는지(요구사항 변경 / 설계 변경 /
결정 / 기타, 바뀐 REQ 와 파일, 근거, 영향, 관련 PR)를 담는다. 기록을 파일
하나에 몰아 적지 않는 이유는, 여러 사람이 같은 시각에 각자 기록해도 파일이
겹치지 않아 PR 이 충돌하지 않기 때문이다.

템플릿은 `../templates/harness/audit-change.md` 다.

## audit/ledger/ — 진행 원장

프로그램 하나에 파일 하나를 쓴다(예: `구매요청승인.md`). 그 프로그램에 걸린
REQ 목록과, 개발 건이 어디까지 왔는지(대기 / 진행 / 리뷰 / 완료)를 표로
담는다.

템플릿은 `../templates/harness/audit-ledger.md` 다.

## 누가 쓰나

`/harness:prd`, `/harness:spec`, `/harness:deliver` Skill 이 작업하면서 이
형식으로 기록을 남긴다. 사람이 직접 적어도 된다.

## 검사

`rules/audit-changes.yaml` 과 `rules/audit-ledger.yaml` 이 파일 이름과 필수
절을 doc-guard 로 검사한다. 필수 절 목록은 각 템플릿의 `##` 제목에서 그대로
읽으므로, 템플릿을 고치면 검사 기준도 함께 바뀐다.

# checker — 검사 엔진

아직 비어 있다. 다음 작업에서 만든다.

## 여기에 무엇이 들어가나

문서를 읽어 고객사별 `rules.yaml` 과 대조하고 위반 목록을 내는 엔진이다.

```
checker/
  cli.py            check <파일...> --rules <rules.yaml> 진입점
  engine.py         규칙을 모아 실행하고 위반을 수집
  rules/            규칙 종류별 모듈 (하나가 한 종류를 담당)
    filename.py       파일명 형식
    location.py       파일이 있어야 할 경로
    required_sections.py  필수 섹션·항목
    table_headers.py  표 헤더 (xlsx)
    styles.py         서식·스타일 (docx)
  readers/          형식별 본문 추출 (md, docx, xlsx, pptx, pdf)
```

## 왜 플러그인 밖에 있나

같은 엔진을 두 곳에서 부르기 때문이다.

| 진입점 | 도는 곳 | 엔진을 어떻게 얻나 |
|---|---|---|
| `plugins/doc-guard/` 훅 | 팀원 PC 의 Claude | 마켓플레이스에서 설치 |
| GitHub Actions | GitHub 서버 | 대상 저장소에 번들로 들어가야 함 |

Actions 는 팀원 PC 에 설치된 플러그인을 쓸 수 없다. 엔진을 `plugins/` 안으로
옮기면 Actions 경로가 끊긴다.

## 설계 원칙

**규칙은 코드가 아니라 데이터다.** 규칙 자체는 고객사별 `rules.yaml` 에 적고,
`rules/` 아래 모듈은 규칙 *종류* 를 구현한다. 새 규칙을 추가할 때 엔진 코드를
고치게 된다면 설계가 어긋난 것이다.

## 출력

위반마다 아래를 낸다. 플러그인 훅 출력과 PR 코멘트가 같은 내용을 쓴다.

- 위반한 파일과 규칙
- 기대값과 실제값
- 쓸 템플릿의 경로

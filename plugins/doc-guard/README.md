# doc-guard 플러그인

아직 매니페스트뿐이다. 훅과 스킬은 검사 엔진(`checker/`)이 생긴 뒤에 만든다.

## 여기에 무엇이 들어가나

```
plugins/doc-guard/
  .claude-plugin/plugin.json   플러그인 정의 (작성됨)
  hooks/                       문서를 쓰기 전에 검사하고 위반이면 거절
  skills/doc-new/              템플릿으로 새 문서 만들기
  skills/doc-check/            수동 검사
```

플러그인은 껍데기다. 실제 검사는 저장소 루트의 `checker/` 엔진이 한다.
이유는 `checker/README.md` 를 읽는다.

## 설치 방법 (엔진이 생긴 뒤)

```
/plugin marketplace add jaeheeMin/doc-guard-marketplace
/plugin install doc-guard
```

플러그인은 저장소가 아니라 **사람** 에게 설치된다. 한 번 설치하면 어느
저장소를 열든 동작한다.

## 한계

훅은 Claude 를 쓸 때만 돈다. 팀원이 GitHub 웹이나 터미널 git 으로 올리면
그냥 지나간다. 그쪽은 GitHub Actions 검사가 잡는다.

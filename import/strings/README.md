# 번역 문자열

| 파일 | 내용 |
|---|---|
| `source_strings_complete_ko_draft.csv` | 게임 문자열 번역 |
| `executable_house_names.csv` | 화면에 표시할 가문 이름 번역 |

`translation_ko` 열을 수정합니다. 문자열 번호·원문·서식 지정자(`%s`, `%d`, `%%`)는 유지합니다.

수정한 번역을 게임에 반영하려면 프로젝트 루트에서 실행합니다.

```powershell
python tools/build_game.py
```

원문 추출 결과는 `export/strings/`에 생성됩니다.

# CG 편집과 가문 질문

편집할 PNG는 `import/GFX/images/`에 있다. 원본 PAK와 디코딩 기준 자료를 사용해 변경한 리소스만 최종 PAK에 반영한다. 최신 적용본은 [STATUS](STATUS.md), 최종 빌드 명령은 [BUILD](BUILD.md)를 따른다.

최종 빌드는 없는 CG 기준 자료를 원본 PAK에서 자동 추출한다. `export/GFX/`에 매니페스트와 원본 리소스를, `export/GFX/images/`에 원본 PNG를 만든다. 10리소스·44PNG를 사용하며, `import/GFX/images/`의 편집 PNG를 원본으로 교체하지 않는다.

## 입력과 편집 순서

| 자료 | 경로 |
|---|---|
| 원본 CD에서 추출한 PAK | `export/PAK/DUNE.PAK`, `export/PAK/ENGLISH.PAK` |
| 디코딩 기준 리소스·이미지·대응 정보 | `export/GFX/resources/`, `export/GFX/images/`, `export/GFX/manifest.json` |
| 인코딩할 편집 PNG | `import/GFX/images/PAK명/리소스명/frame_번호.png` |

1. 편집 PNG를 수정해 저장한다.
2. 크기·프레임 번호·원래 팔레트 색 번호·투명색을 유지한다. 색이 같은 팔레트 항목도 번호는 다를 수 있다.
3. 번역과 함께 반영하려면 `python tools/build_game.py`를 실행한 뒤 생성된 게임을 사용자 실행 환경에서 확인한다.
4. PAK만 별도로 인코딩하려면 다음 명령을 사용한다.

```powershell
python tools/edit_cg.py encode
```

별도 인코딩 출력은 `build/cg-encoded-날짜-시간/`이다. 인코더는 원본 PAK의 수정된 멤버만 교체하고 나머지 멤버를 보존한다. 편집 PNG를 고쳐도 `export/GFX/`의 원본 기준 자료를 덮어쓰지 않는다.

다른 게임 사본의 CG를 조사하려면 새 프로젝트와 기준 경로를 함께 지정한다. 추출 도구는 이미 내용이 있는 출력 폴더를 덮어쓰지 않는다.

```powershell
python tools/edit_cg.py export --game "게임 폴더" --project "import/GFX-other" --baseline "export/GFX-other"
python tools/edit_cg.py encode --project "import/GFX-other" --baseline "export/GFX-other"
```

<a id="편집-범위"></a>
<a id="선택한-편집-범위-리소스-10개png-44개"></a>

## 선택한 편집 범위

| PAK | 리소스 | PNG 수 |
|---|---|---:|
| DUNE | CHOAM.CPS, MAPMACH.CPS, SCREEN.CPS | 각 1 |
| ENGLISH | CHOAM.ENG | 18 |
| ENGLISH | BTTN.ENG | 5 |
| ENGLISH | AND.ENG | 1 |
| ENGLISH | MENTAT.ENG | 14 |
| ENGLISH | MISC.ENG, TITLE.ENG, HERALD.ENG | 각 1 |

합계 **10리소스·44PNG**다. DUNE·ENGLISH 두 원본 PAK는 선택하지 않은 멤버를 보존하는 데도 필요하다. FRENCH·GERMAN·FINALE·INTRO·MENTAT PAK의 그림은 편집 범위에서 제외했다. `ENGLISH/MENTAT.ENG`는 언어 UI 버튼 자산이다.

BTTN.ENG와 SCREEN.CPS의 버튼 그림은 각각 편집한다. 한쪽을 수정해도 다른 쪽 픽셀이 자동으로 바뀌지 않는다. 그림에 들어 있는 MENTAT·OPTIONS·BUILD THIS 등의 글자는 문자열 CSV로 교체되지 않는다.

## 가문 가입 질문

질문은 MISC.ENG 그림에서 복사한다. ENG 모드는 완성 문장 세 줄 가운데 선택한 가문의 한 줄을 표시한다. FRE·GER는 원래 두 조각 복사 방식을 유지한다.

현재 PNG의 위→아래 순서는 **아트레이데스·오르도스·하코넨**이다. 게임 내부 가문 ID와 다음처럼 연결한다.

| 게임 ID | 가문 | PNG 행 | source Y |
|---:|---|---:|---:|
| 0 | 하코넨 | 2 | 48 |
| 1 | 아트레이데스 | 0 | 0 |
| 2 | 오르도스 | 1 | 24 |

한 줄은 312×24픽셀이고 전체 CPS는 320×200이다. `tools/runtime_patches.py`의 `3314:1398..13E6` 영역에서 ENG의 source Y를 `(가문 ID+2)%3*24`로 계산한다. 원본 FAR 복사 호출·스택 규약을 유지한다. 최종 빌드는 이 분기가 적용된 EXE와 대응 그림을 함께 반영한다.

## 팔레트와 투명색 오류

| 오류 | 의미와 처리 |
|---|---|
| `colour ... absent or ambiguous; use indexed PNG` | RGB에서 원래 색 번호를 결정할 수 없다. 원래 인덱스 팔레트를 유지한 PNG로 저장한다. |
| `transparency index changed` | 원본과 투명색 메타데이터가 다르다. MENTAT.ENG 버튼은 원래 투명색 0번을 유지한다. |

팔레트와 투명색의 원본 분석은 [HERALD 팔레트 복원](analysis/graphics/herald_palette_repair.md), [MENTAT 투명색 복원](analysis/graphics/mentat_transparency_repair.md)에 있다.

## 보고서와 분석 근거

빌드 보고서의 `cg`는 PNG 해시·변경 리소스·PAK 병합·가문 질문 행 대응을 기록한다. 변경 리소스 수는 편집 PNG에 따라 달라진다.

원본 질문의 [복사 좌표](analysis/graphics/house_question_source.md), [세 줄 시험](analysis/graphics/three_row_house_question.md), [가문별 행 순서 수정](analysis/graphics/house_question_row_order.md)을 원본 기록으로 유지한다. 게임 리소스와 그래픽 형식의 원본 분석은 [엔진·텍스트·CG 기록](analysis/engine/engine_text_graphics.md)을 따른다. CD 이미지와 배포 패치 적용은 [PATCHING](PATCHING.md)에 있다.

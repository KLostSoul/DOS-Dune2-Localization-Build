# 폰트와 메모리

일반 게임 번역에는 **달무리 8×8**, 오프닝·엔딩·황제 중간 영상에는 **Unifont 16×16**을 사용한다. 현재 글자 수·실행본·해시는 [STATUS](STATUS.md)에 기록한다.

## 글꼴 입력과 출력

| 대상 | 입력·생성 자료 |
|---|---|
| 일반 게임 한글 | `font/composed-hangul.hex`의 등록된 완성 음절 → `DUNEHAN.FNT` |
| 한글 번역 구간의 알파벳·숫자·부호 | 같은 HEX의 달무리 글리프. 원래 ASCII 바이트를 유지하며 출력 글리프·폭 선택. 영상에서 수집한 부호는 Unifont 우선 |
| 오프닝·엔딩·황제 중간 영상 | `font/unifont-16.0.04.hex`에서 사용하는 글자만 선택 → `DUNEUNI.FNT` 페이지·`DUNEUNI.MAP` |
| 번역되지 않은 출력 | 기존 듄 FNT와 원래 출력 경로 |

`composed-hangul.hex`에는 한글 11,172음절과 알파벳·숫자·부호 118글리프의 8×8 비트맵이 들어 있다. 빌드는 이 HEX에서 필요한 레코드를 읽는다.

생성한 `DUNEHAN.FNT`, `DUNEUNI.FNT` 페이지와 `DUNEUNI.MAP`은 먼저 `import/fnt/`에 기록하고 그 바이트를 게임 폴더에 적용한다. 생성·적용 과정은 [BUILD](BUILD.md)에 있다.

영상 글리프가 256개를 넘으면 `DUNEUN1.FNT`, `DUNEUN2.FNT` 순서로 페이지를 나눈다. 모든 페이지를 실행용 게임과 CD 이미지·Xdelta에 포함한다. 글리프가 줄면 더 이상 사용하지 않는 번호 페이지를 `import/fnt/`와 최종 게임 폴더에서 정리한다.

## 영구 문자표와 FNT 생성

`import/fnt/glyph_registry.json` version 2의 `syllables` 배열이 전체 등록 한글의 저장 자료다. 현재 740음절을 한 문자표로 관리한다. CSV에서 발견한 새 음절은 성공한 최종 빌드가 문자표에 등록한다.

빌드는 전체 음절을 유니코드 가나다순으로 정렬해 토큰을 지정하고 **완성 `DUNEHAN.FNT`를 한 번 생성**한다. 그 레코드로 폰트 코드 템플릿과 최종 후크를 구성한다.

기존 렌더러와 메모리 배치를 보존하기 위해 고정 부호 33개의 물리 슬롯 **639~671**을 유지한다. 한글과 부호의 모든 비트맵은 HEX에서 완성 FNT로 직접 생성한다. 영상용 유니폰트에는 해당 자막에서 사용하지 않는 글자를 저장하지 않는다.

## 2바이트 토큰과 출력 규약

한글 토큰의 첫 바이트는 `E2..F9`, `FB..FE`, 두 번째 바이트는 `80..FE`다. `FAh`는 원래 가운데점 용도로 둔다. 전체 3,556개 코드 공간에서 비ASCII 부호 23개를 사용하므로 한글 수용량은 3,533음절이다. ASCII는 1바이트를 유지한다.

`%s`·`%d`·`%%`, 단축키 접미사와 숫자의 ASCII 바이트를 보존하면서 한글 번역 구간의 글리프를 달무리로 선택한다. 원본 포맷·폭 계산·문자 루프·픽셀 출력 규약을 유지하며 정방향·역방향 이동과 고정 간격 버퍼도 같은 2바이트 판독기를 사용한다. 자막 전처리는 토큰 두 바이트를 함께 복사한다. 테두리와 화면별 간격은 [RUNTIME](RUNTIME.md)에 정리했다.

## 메모리 배치

달무리 글리프와 한글 처리 코드는 EXE의 **MZ 상주 이미지**에 들어간다. 글리프가 늘면 상주 모듈 뒤의 치트 모듈·스택·재배치 위치도 함께 갱신한다. 별도 DOS 폰트 블록이나 FAR 힙은 만들지 않는다.

유니폰트 FNT·색인표는 **XMS**에 적재하며 실제 데이터 크기를 KiB 단위로 올림해 요청한다. 상주 이미지에 유니폰트 비트맵·전체 색인표를 중복 보관하지 않는다. 사용 글자와 요청 크기는 번역에 따라 재계산하고 `build-report.json`에 기록한다.

치트 화면 백업도 XMS를 사용한다. `FASTBUILD`·`REVEAL`은 기존 치트 모듈을 확장하며 별도 DOS/XMS 할당을 추가하지 않는다. 최종 스택은 보고서의 `extra_cheats.new_stack_segment`를 따른다.

빌더는 MZ 길이·재배치·스택·선언한 오버레이 수정 범위를 검사한다. FBOV는 선언된 수정 구간을 제외한 원본 내용과 연결을 유지한다.

## 구현과 원본 분석 기록

| 자료 | 역할 |
|---|---|
| `tools/fonts.py` | 완성 글리프·토큰·MZ 배치, Unifont FNT/XMS 자료, Latin과 원본 스타일 |
| `tools/scenes.py` | 영상 자막 토큰 보존 |
| `tools/build_game.py`, `tools/translation_data.py` | 사용 음절 수집·게임 문자열 인코딩·등록표 저장 |
| `build/final-build/DUNEHAN.TBL.csv` | 등록 한글의 토큰과 글리프 대응표. 시나리오 패치 인코딩과 최종 빌드 검사에서 사용 |
| `build/final-build/DUNEHAN.LATIN.csv` | 달무리 알파벳·숫자·부호의 입력 코드·슬롯·셀 폭을 기록한 확인용 표 |
| `build/final-build/DUNEUNI.TBL.csv` | 영상 글자의 공통 토큰·물리 슬롯·FNT 페이지 대응표. 최종 빌드 검사에서 사용 |

세 CSV는 빌드가 자동 생성하는 결과다. 게임이 직접 읽는 입력 파일이 아니며, 번역 수정은 `import/strings/`의 CSV에서 한다. 게임 폴더의 `DUNEHAN.TBL`은 `DUNEHAN.TBL.csv`와 바이트가 같은 문자표 사본이며, 현재 출력 후크는 이 파일을 읽지 않는다. 유니폰트 후크가 XMS 글리프 위치를 조회할 때는 별도의 바이너리 `DUNEUNI.MAP`을 사용한다.

원본의 명령·메모리 수명·출력 흐름은 [FNT 엔진](analysis/engine/font_engine.md), [폰트 메모리 수명](analysis/fonts/font_memory_lifecycle.md), [달무리 영문·부호](analysis/fonts/dalmoori_latin_symbols.md), [유니폰트 적용 기록](analysis/fonts/unifont_cinematics.md)에 남긴다.

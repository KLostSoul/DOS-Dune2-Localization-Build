# 도구 안내

최종 게임 빌드는 프로젝트 루트에서 `python tools/build_game.py`로 생성한다. 생성한 게임의 실행 환경 설정과 실행은 사용자가 맡는다. 빌드·사용자 확인 결과는 [현재 상태](../doc/STATUS.md)에 있다.

## 실행 도구

같은 기능의 구현은 아래 파일로 통합했다. 개별 패치별 실행기와 별도 전체 그래픽 미리보기 명령은 두지 않는다.

| 도구 | 역할 |
|---|---|
| `build_game.py` | 저장된 입력 읽기·리소스 인코딩·전체 최종 빌드 명령과 생성 과정 |
| `assembler.py` | `import/asm/JWasm.exe`로 16비트 ASM 조립 |
| `cd_source.py` | 원본 CD 추출·export 입력 검증·폰트 코드 템플릿 재현 |
| `apply_hitsquad107_fix.py` | `import/patches/dune2eng1.07fix/V107UPG/HITSQUAD/`의 공식 Fix 자료 병합 |
| `fonts.py` | 달무리·유니폰트·Latin 글리프·토큰·원본 스타일 패치 |
| `cheats.py` | 최종 치트 확장과 원본 치트 비교판 생성 명령 |
| `runtime_patches.py` | 가문 질문·명예의 전당·지도 문자열·주문서 간격·CG 병합·기능 검사 |
| `scenes.py` | 영상 자막 토큰 보호와 하코넨·오르도스 마지막 자막·입 애니메이션 패치 |
| `translation_data.py` | CSV 입출력·문자열 검증·글리프 메타데이터·화면 분류와 분류 갱신 명령 |
| `resources.py` | PAK·IFF·문자열 압축과 해제, 원본 문자열·EXE 후보 내보내기 명령 |
| `cg_codec.py` | CG 리소스·팔레트·프레임 디코딩과 인코딩 |
| `edit_cg.py` | 선택 CG의 편집 프로젝트 추출과 PNG 재인코딩 명령 |
| `clonecd_xdelta.py` | 원본 IMG에서 한글 BIN/CUE·Xdelta 생성·적용 |
| `check_final_build.py` | 최종 게임·폰트·치트·자막·편집기와 BIN/CUE/Xdelta 통합 검사 |

한글 문자표는 `import/fnt/glyph_registry.json`의 version 2 `syllables` 배열 하나로 저장한다. 현재 등록된 전체 음절을 정렬해 완성 `DUNEHAN.FNT`를 한 번 생성하고 그 결과로 후크를 구성한다. 새 음절은 CSV 저장 또는 성공한 독립 빌드에서 문자표에 영구 등록하며, 이미 등록된 음절을 매번 새로 추가했다고 표시하지 않는다. 초기 음절 CSV와 초기 FNT 생성 단계는 사용하지 않는다.

원본에 치트만 더한 비교판은 다음 명령으로 생성한다. 생성된 게임 파일은 `build/cheat-runtime/source/VIRGIN/DUNE2/`에 두며 실행은 사용자가 맡는다.

```powershell
python tools/cheats.py original
```

에디터의 빌드 버튼은 `editor/build_runner.py`를 통해 `build_game.py`를 새 프로세스로 실행한다. 게임 패치 코드는 빌드 명령이 불러오며, 에디터에는 편집·저장·명령 실행 기능을 둔다.

## 원본을 다시 추출할 때

번역 편집을 위해 매번 원본을 재추출할 필요는 없다. 빌드에 필요한 원본 EXE·세 PAK만 준비하려면 다음 명령을 사용한다. 원본 CD와 대조해 `export/DUNE2.EXE`와 `export/PAK/`에 생성·검사한다.

```powershell
python tools/cd_source.py exports
```

전체 CD 파일과 PAK 내부 파일을 따로 조사할 때는 존재하지 않는 새 출력 폴더를 명시한다. 이 수동 추출은 원본 설정 파일 바이트를 유지하며 로컬 실행 설정을 넣지 않는다.

```powershell
python tools/cd_source.py extract --output "build/original-inspection" --unpack-paks
```

전체 문자열 추출은 기본적으로 `export/PAK/`의 원본 PAK를, EXE 문자열 추출은 `export/DUNE2.EXE`를 읽는다. 두 도구의 기본 출력은 `export/strings/`다. 재조사할 때 현재 기준표를 덮어쓰지 않도록 별도 CSV 경로를 명시할 수 있다.

```powershell
python tools/resources.py strings --output "build/새추출/source_strings_complete.csv"
python tools/resources.py exe --output "build/새추출/executable_strings.csv"
```

EXE 추출표는 ASCII 후보 목록이며 모든 실제 출력 참조를 규명한 결과가 아니다. 현재 CSV의 화면 분류를 갱신하려면 다음 명령을 사용한다.

```powershell
python tools/translation_data.py classify
```

CG 편집은 선택한 리소스만 `edit_cg.py`로 추출·인코딩한다. 공용 디코더는 `cg_codec.py`에 있으며, 전체 게임의 미리보기·접촉 시트를 일괄 생성하는 별도 명령은 정리했다.

```powershell
python tools/edit_cg.py export
python tools/edit_cg.py encode
```

## 최종 빌드 검사

검사 구현은 **`check_final_build.py` 하나**에 통합되어 있다. 기본 대상은 `build/final-build`, 배포 대상은 `output/`이다. 예전 테스트 빌드나 번역 스냅샷은 사용하지 않는다.

프로젝트 루트에서 실행한다.

```powershell
python tools/check_final_build.py
```

기본 실행은 아래 14개 영역을 검사한다. 실제 게임을 실행하거나 최종 산출물을 재생성하지 않는다.

| 영역 | 검사 내용 |
|---|---|
| `package` | 원본 IMG 해시, BIN 내부 파일과 최종 게임 파일 전체 대조, 변경·추가 섹터 EDC/ECC, CUE, 원본 IMG에 Xdelta를 실제 적용한 결과와 BIN의 바이트 일치, 세이브 파일 추가 여부 |
| `structure` | 최종 EXE와 HitSquad 전후 보고서, MZ 재배치·메모리 경계, 후크·페이드·보안 질문 생략, JWasm 기록, 최종 게임 파일 경로 |
| `hangul` | 영구 전체 문자표·완성 FNT 직접 생성, 가나다순 2바이트 토큰·전체 코드 공간, 글리프 비트맵·폭·픽셀·이동, CSV와 게임 리소스, 단축키 |
| `latin` | 번역 구간 달무리 영문·숫자·부호, 원본 printf 서식, 폭·픽셀, 부호 호환 처리와 단축키 |
| `unifont` | 사용 글자 FNT/MAP, 원본 드라이버 픽셀, XMS 적재·해제·재적재·실패 정리, 음절·부호 자동 추가와 페이지 분할 |
| `subtitles` | 자막 전처리의 2바이트 보존, 제자리·별도 버퍼와 기존 단일 바이트 처리 |
| `region` | 지도 INI의 모든 영문 키, 고위 바이트를 공백으로 오인하던 결함 재현·수정 확인 |
| `houses` | 명예의 전당의 가문 이름·12개 계급 문자열과 스택·기록 보존 |
| `question` | 영어 가문 합류 문장 3행과 프랑스어·독일어의 기존 복사 인자 |
| `styles` | 원본·한글·달무리 영문 테두리 픽셀, 원본 스타일 값과 생산 퍼센트 서식 |
| `spacing` | 유닛·건물 정보의 1픽셀 줄 간격과 함수 반환 시 원래 값 복원 |
| `cheats` | 치트 5개, 크레딧 +10,000, 내 가문만 생산 5배, 지도 순회·가문 인자·상태 메시지·입력 상태·스택 |
| `scenes` | 하코넨 #320·오르도스 #308 전용 분기, 기존 장면표·다른 분기·재배치 보존, 원래 WSA 반복과 스택 균형 |
| `editor` | 복사한 CSV에서 항목 왕복·문구 유지·저장·다시 읽기, 새 음절 등록의 저장·재열기·다음 빌드 입력 유지 |

실제 Tk 위젯의 수정 표시·저장·되돌리기·다시 실행·창 재열기도 포함하려면 다음과 같이 실행한다. 검사 창은 숨김 상태로 만든다.

```powershell
python tools/check_final_build.py --editor-gui
```

특정 영역만 실행하거나 목록을 확인할 수도 있다.

```powershell
python tools/check_final_build.py --only package structure cheats
python tools/check_final_build.py --list
```

결과는 `build/checks/final-build-check.json` 하나에 기록한다. 선택 영역과 전체 기본 검사 포함 여부를 함께 기록하며, 하나라도 실패하면 종료 코드 1을 반환한다. `-O`로 assert를 끈 실행은 거부한다.

검사 중 생성한 Xdelta 복원 BIN과 편집기 복사 자료는 `temp/final-check-*`에만 만들고 종료 시 삭제한다. 다른 작업의 임시 파일은 건드리지 않으며 `temp/`가 비었으면 폴더도 삭제한다. 최종 게임·배포본·실제 CSV·에디터 세션의 해시가 검사 전후 동일한지도 확인한다.

기계어 검사는 Unicorn의 제한 실행이다. 지도 엔진·화면 입출력·DOS/XMS 일부 서비스를 모형으로 제공하므로 실제 DOSBox 게임 플레이 확인과는 구분한다. Python 환경에는 Unicorn·Capstone이 필요하며 이 프로젝트의 `build/analysis-deps/`를 우선 사용한다.

## 과거 자료

완료된 과거 단계별 도구는 [도구 보관 안내](../archives/tools/README.md), 기능별 게임 확인본은 [빌드 보관 안내](../archives/builds/verified/README.md)에 있다. `legacy-tools-20261024.zip`은 당시 공용 import와 소스의 원래 경로를 보존한다. 현행 빌드에 과거 실패 후보를 다시 적용하지 않는다. DOSBox-X 디버거 어댑터와 EmuCap 런타임은 게임 빌드 도구와 분리해 `G:\Codex\MCP\emucap`에 둔다.

# 도구 안내

프로젝트 루트에서 아래 명령을 실행합니다.

## 최종 빌드

```powershell
python tools/build_game.py
```

`img/`에서 원본 CD를 해시로 식별하고 번역·PNG·글꼴·ASM·Fix를 반영합니다. 게임 파일은 `build/final-build/`, BIN/CUE·Xdelta·JSON은 `output/`에 생성됩니다.

빌드 개발환경은 Python 3.14.9, Pillow 12.3.0입니다. CD 패치는 포함된 `tools/xdelta3.exe` v3.2.2, ASM 조립은 `import/asm/JWasm.exe` v2.20을 사용합니다.

## 원본 추출

| 명령 | 결과 |
|---|---|
| `python tools/cd_source.py exports` | `export/DUNE2.EXE`와 `export/PAK/`의 원본 파일 |
| `python tools/resources.py strings` | `export/strings/`의 원문 CSV |
| `python tools/resources.py exe` | `export/strings/executable_strings_review.csv` |

CD 전체 파일과 PAK 내부 파일을 조사하려면 새 출력 폴더를 지정합니다.

```powershell
python tools/cd_source.py extract --output "build/original-inspection" --unpack-paks
```

## CG 작업

```powershell
python tools/edit_cg.py export
python tools/edit_cg.py encode
```

추출 명령은 `export/GFX/`에 원본 리소스와 PNG를, `import/GFX/images/`에 편집용 PNG를 생성합니다. 수동 추출의 출력 폴더는 비어 있어야 합니다. 최종 빌드는 필요한 원본 기준 자료를 자동으로 준비합니다.

인코딩 결과는 `build/cg-encoded-날짜-시간/`에 생성됩니다. 대상 리소스와 경로 옵션은 [CG 편집 안내](../doc/GRAPHICS.md)에 있습니다.

## 번역 분류 갱신

```powershell
python tools/translation_data.py classify
```

번역 CSV의 구간·가문·세부 분류를 갱신합니다.

## CD 패치

```powershell
python tools/clonecd_xdelta.py create
python tools/clonecd_xdelta.py apply
```

`create`는 최종 게임 파일로 BIN/CUE·Xdelta·JSON을 생성하고, `apply`는 원본 CD와 배포 패치에서 BIN/CUE를 생성합니다. [패치 적용 안내](../doc/PATCHING.md)에 경로 옵션이 있습니다.

## 원본 게임과 기본 치트

```powershell
python tools/cheats.py original
```

`img/`의 원본 CD에서 게임을 추출하고 HitSquad 1.07 Fix와 치트 ASM을 적용해 `build/cheat-runtime/source/VIRGIN/DUNE2/`에 생성합니다. CREDITS·WIN·LOSE·FASTBUILD·REVEAL과 `import/runtime-settings.json`의 게임 설정을 적용합니다. 출력 폴더가 이미 있으면 덮어쓰지 않고 중단합니다.

## 최종 빌드 검사

검사에는 Capstone과 Unicorn이 필요합니다.

```powershell
python tools/check_final_build.py
```

| 영역 | 검사 대상 |
|---|---|
| `package` | 번역 입력에 필요한 모든 FNT 페이지와 BIN 내부 파일, EDC/ECC, CUE, Xdelta 복원 결과·독립 CD 명령의 실패 복구 |
| `structure` | EXE·MZ 재배치·메모리 경계·HitSquad 패치·저장 실패 시 일괄 복구·원본 치트 빌드와 보고서 대조 |
| `hangul` | 한글 토큰·글리프·폭·단축키 |
| `latin` | 영문·숫자·부호와 서식 |
| `unifont` | 영상 글리프·XMS 적재와 해제 |
| `subtitles` | 자막 토큰 처리 |
| `region` | 지도 INI 문자열 |
| `houses` | 가문 이름과 계급 문자열 |
| `question` | 가문 합류 질문의 이미지 선택 |
| `styles` | 폰트 가장자리와 원본 스타일 |
| `spacing` | 정보창 줄 간격 |
| `cheats` | 치트 명령과 생산·지도 처리 |
| `scenes` | 하코넨·오르도스 영상 자막과 애니메이션 |

`structure` 검사는 원본 CD와 현재 ASM으로 HitSquad Fix·치트 5개·게임 설정을 적용한 원본 치트 빌드를 `temp/`에 임시 생성합니다. `build/cheat-runtime/`이 있으면 전체 게임 파일을 임시 생성본과 바이트 단위로 대조하고, Fix 보고서의 적용 위치·치트 목록·입력 해시와 조립 기록의 소스 해시·모듈 구성을 확인합니다. 기존 실행본은 보존하며 검사 후 임시 자료를 정리합니다.

특정 영역을 선택하거나 검사 목록을 볼 수 있습니다.

```powershell
python tools/check_final_build.py --only package structure cheats
python tools/check_final_build.py --list
```

결과는 `build/final-build-check.json`에 기록됩니다. 실패 시 종료 코드 1을 반환합니다. 기계어 검사는 Unicorn에서 DOS/XMS 서비스를 모형으로 실행합니다.

## 소스 구성

| 파일 | 역할 |
|---|---|
| `build_game.py` | 최종 빌드 |
| `cd_source.py` | 원본 CD 추출·기준 자료 준비·출력 파일 반영과 복구 |
| `assembler.py` | ASM 조립 |
| `apply_hitsquad107_fix.py` | HitSquad 1.07 Fix 반영 |
| `fonts.py` | 폰트·토큰·메모리 배치 |
| `cheats.py` | 치트 패치·원본 CD의 기본 치트 실행본 생성 |
| `runtime_patches.py` | 게임 화면·문자열·CG 패치 |
| `scenes.py` | 영상 자막과 애니메이션 패치 |
| `translation_data.py` | 번역 CSV와 글리프 등록표 |
| `resources.py` | PAK·IFF·문자열 코덱과 추출 |
| `cg_codec.py` | CG 코덱 |
| `edit_cg.py` | CG 추출과 인코딩 |
| `clonecd_xdelta.py` | CD 이미지와 Xdelta |
| `check_final_build.py` | 산출물 검사 |

## Xdelta3 라이선스

포함된 `xdelta3.exe` v3.2.2는 Joshua MacDonald의 Xdelta3입니다. [Apache License 2.0 전문](xdelta3-LICENSE.txt)을 함께 제공합니다. 원본 소스는 [jmacd/xdelta](https://github.com/jmacd/xdelta/tree/v3.2.2)에 있습니다.



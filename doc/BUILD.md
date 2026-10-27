# 최종 게임 빌드

프로젝트 루트에서 다음 명령을 실행한다. 빌드 입력 처리와 리소스·글꼴·게임 패치 생성은 `tools/build_game.py`와 빌드 도구가 맡는다.

```powershell
python tools/build_game.py
```

게임 파일은 `build/final-build/source/VIRGIN/DUNE2/`에 생성한다. 빌드는 게임 파일과 BIN/CUE·Xdelta 생성까지 맡고, 게임 실행 환경의 선택·설정과 실행은 사용자가 맡는다. 현재 실행 파일·산출물 해시는 [STATUS](STATUS.md), 배포 패치 적용은 [PATCHING](PATCHING.md)에 있다.

## 빌드 환경

| 항목 | 요구 사항 |
|---|---|
| Python | Python 3.14 |
| CG 처리 | Pillow |
| ASM 조립 | 프로젝트의 `import/asm/JWasm.exe` v2.20 |
| CD 패치 | 프로젝트의 `tools/xdelta3.exe` |


## 빌드 입력

| 입력 | 위치 |
|---|---|
| 원본 CD | `img/`에서 기준 SHA-256과 일치하는 파일 자동 선택. 파일명·확장자 제한 없음 |
| 원본 실행 파일 | `export/DUNE2.EXE` |
| 원본 PAK | `export/PAK/DUNE.PAK`, `ENGLISH.PAK`, `SCENARIO.PAK` |
| 번역·가문 이름 | `import/strings/source_strings_complete_ko_draft.csv`, `executable_house_names.csv` |
| 달무리·유니폰트 글리프 | `font/composed-hangul.hex`, `font/unifont-16.0.04.hex` |
| 전체 등록 음절 | `import/fnt/glyph_registry.json`의 version 2 `syllables` |
| 편집 CG | `import/GFX/images/` |
| CG 디코딩 기준 | `export/GFX/manifest.json`, `resources/`, `images/` |
| 후크·기능 ASM | `import/asm/` |
| 원본 EXE 바이트 패치 | `import/cd-runtime-base.json` |
| HitSquad 1.07 Fix | `import/patches/dune2eng1.07fix/V107UPG/HITSQUAD/` |
| 게임 자체의 기본 설정 | `import/runtime-settings.json` |

원본 CD는 [PATCHING의 입력 해시](PATCHING.md#패치-입력)와 대조한다. 네 export 원본이 없으면 CD에서 추출하고, 이미 있는 파일도 기록된 원본 해시로 검사한다. 전체 등록 음절은 영구 문자표에서 읽으며 새 음절은 성공한 빌드에서 등록한다. 자세한 글꼴·토큰·메모리 규칙은 [FONTS](FONTS.md), PNG 입력 규칙은 [GRAPHICS](GRAPHICS.md)를 따른다.

최종 빌드 명령은 원본 파일 준비 직후 다음 자료도 자동 생성한다.

- `export/GFX/manifest.json`: 원본 리소스·프레임 대응 정보
- `export/GFX/resources/`: 편집 대상의 원본 CG 리소스
- `export/GFX/images/`: 해당 원본 CG에서 디코딩한 PNG
- `export/strings/executable_strings_review.csv`: 원본 EXE 문자열 후보와 알려진 가문 이름

이미 있는 자료는 유지하고, CG 기준 자료 중 빠진 리소스·원본 PNG는 원본에서 다시 추출한다. 기존 EXE 검토 CSV의 메모와 번역을 덮어쓰지 않으며 `import/GFX/images/`의 편집 PNG도 변경하지 않는다. 생성 중간 자료는 `temp/`에서 정리한다.


네 원본 파일만 준비할 때는 다음 명령을 사용한다.

```powershell
python tools/cd_source.py exports
```

전체 CD와 PAK 내부 파일을 조사하려면 새 출력 폴더를 명시한다. 이 수동 추출은 원본 설정 파일을 그대로 유지한다.

```powershell
python tools/cd_source.py extract --output "build/original-inspection" --unpack-paks
```

## 생성 과정

1. 원본 CD·네 export 원본을 검사하고 없는 CG 기준·원본 PNG·EXE 검토표를 생성한다. 번역 입력을 검사하고 전체 음절에 가나다순 2바이트 토큰을 지정한다.
2. 세 PAK를 메모리에서 풀고 CSV로 일반 문자열, 멘타트 NAME/DESC/INFO와 지도 문구를 생성한다.
3. HEX에서 완성 `DUNEHAN.FNT`를 한 번 생성한다. 원본 EXE에 고정 바이트 패치를 적용하고 완성 FNT의 레코드를 사용해 폰트 코드 템플릿을 조립한다.
4. 편집 PNG를 인코딩해 해당 PAK 멤버에 병합하고, 자막·원본 스타일·유니폰트·치트·영상·간격 패치를 적용한다. 치트 모듈은 최종 폰트 배치 주소에서 조립하며 MZ 이미지·재배치·스택을 계산한다.
5. HitSquad 1.07 Fix를 병합하고 원본 CD에 최종 게임 파일을 반영해 BIN/CUE·Xdelta를 만든다.
6. 성공한 게임 파일과 배포물을 아래 고정 경로에 반영한다.

| 결과 | 위치 |
|---|---|
| 실행용 게임·보고서 | `build/final-build/` |
| 게임 파일 | `build/final-build/source/VIRGIN/DUNE2/` |
| BIN·CUE·Xdelta·CD 구성 JSON | 루트 `output/` |
| 생성 FNT·색인표 | `import/fnt/` |

`DUNEHAN.FNT`와 유니폰트 FNT/MAP은 먼저 `import/fnt/`에 생성한 바이트를 게임 폴더에 적용한다. 게임의 `DUNEHAN.TBL`과 빌드의 `DUNEHAN.TBL.csv`에는 현재 전체 문자표를 기록한다.

조립·CG 인코딩·CD 구성 중간 자료는 `temp/`에만 생성한다. 종료 시 해당 빌드의 임시 자료를 삭제하고 `temp/`가 비었으면 폴더도 제거한다. `build/final-build/`에는 중간 자료와 중복 배포 폴더를 두지 않는다. 게임 자체의 CFG 기본값은 `import/runtime-settings.json`에서 적용하고, CD에는 원본 `DUNE.CFG`를 유지하며 세이브 파일을 추가하지 않는다.

## 고정 코드 패치와 HitSquad Fix

`import/asm/font/dalmoori-base.asm`은 출력 코드의 배치를 보존하는 코드 템플릿이다. `import/cd-runtime-base.json` version 2는 원본 EXE와 템플릿에 적용할 위치·수정 전후 바이트·확인 해시를 담은 입력이다. 완성 FNT 데이터로 후크를 구성한다.

`tools/apply_hitsquad107_fix.py`는 공식 Fix 폴더의 EXE·시나리오·멘타트·VOC·SETUP 자료를 병합한다. 번역과 보안 질문 생략·페이드 수정은 유지한다. 보안 경로의 오버레이 7바이트, SFX-FIX의 Windows 음성 지연 파일과 GUS-FIX 설정은 적용 대상에서 제외한다. 실제 입력 해시·적용·제외 내역은 `build/final-build/hitsquad107-fix-report.json`에 기록한다.

## 검수와 기록

```powershell
python tools/check_final_build.py
```

검사 범위·선택 실행·의존성은 [도구 안내](../tools/README.md#최종-빌드-검사)에 정리했다. 생성 코드·완성 FNT·컴파일러 기록은 `build-report.json`의 `runtime_source`, `font_build`, `assembly_compiler`에 있고, 최신 산출물 식별은 [STATUS](STATUS.md)를 따른다. 원본 역분석 문서는 [원본 분석 목록](README.md#원본-분석-기록)에서 찾는다.

실행용 게임 폴더와 배포물을 교체하지 않고 생성 과정을 검사하려면 다음 명령을 사용한다. 원본 기준 자료 준비와 폰트 생성은 수행한다.

```powershell
python tools/build_game.py --no-publish
```

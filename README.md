# Dune2 Battle for Arrakis Korean v1.01

*Dune II: The Battle for Arrakis*의 한국어 번역과 원본 CD 기반 최종 빌드 도구를 관리하는 Windows 프로젝트입니다. 현재 최종 빌드는 **HitSquad 1.07 Fix를 통합한 한국어판 v1.01**입니다.

기준일은 2026-10-27입니다. 현재 실행 파일·배포물 해시와 사용자 실행 확인 범위는 [최종 빌드 상태](doc/STATUS.md)에서 관리합니다.

## 적용 기능

- 가문 소개, 임무 설명·조언·승리·패배, 멘타트, 메뉴, 유닛·건물 정보와 게임 메시지 번역
- 일반 번역 구간의 달무리 8×8 한글·영문·숫자·부호와 영상 자막의 유니폰트 적용
- 가나다순 2바이트 한글 토큰, 영구 음절표, 사용 글자만 포함하는 FNT 생성과 새 음절 등록
- 원본 출력 스타일에 따른 테두리, 화면별 간격, 번역된 명령·메뉴의 영문 단축키 유지
- 영어 영상의 자막·음성 동시 출력, 하코넨 #320·오르도스 #308 마지막 자막과 입 애니메이션 수정
- 보안 질문 생략과 임무 설명의 페이드 전환, 편집 CG와 영어 가문 합류 질문 3행 적용

게임 진행 중 **Enter**로 다음 치트를 입력합니다. 빈 입력에서 Enter를 누르면 치트창을 닫습니다.

| 명령 | 동작 |
|---|---|
| `CREDITS` | 크레딧 10,000 증가 |
| `WIN` | 임무 승리 |
| `LOSE` | 임무 패배 |
| `FASTBUILD` | 내 가문의 건물·유닛 생산 속도 5배 전환, ON/OFF 메시지 표시 |
| `REVEAL` | 현재 플레이어의 지도·미니맵 공개 |

세부 패치 동작과 적용 범위는 [런타임 안내](doc/RUNTIME.md)에 있습니다.

## 빌드 준비

| 항목 | 현재 구성 |
|---|---|
| Python | 로컬 환경 Python 3.14.9, CG 처리에 Pillow 사용 |
| ASM 조립 | `import/asm/JWasm.exe` v2.20으로 모든 ASM 조립 |
| CD 패치 도구 | `xdelta3.exe`. 검색 경로와 지정 방법은 [패치 안내](doc/PATCHING.md#실행-도구) 참조 |

빌드는 `img/DUNE2CD.img`를 기준으로 합니다. 필요한 원본 `DUNE2.EXE`와 `DUNE.PAK`·`ENGLISH.PAK`·`SCENARIO.PAK`는 `export/`에서 확인하고, 없으면 CD에서 추출합니다. 원본 CD의 기준 해시는 [패치 입력](doc/PATCHING.md#패치-입력)을 따릅니다.

빌드 입력은 다음 위치에서 읽습니다.

| 자료 | 경로 |
|---|---|
| 번역·표시용 가문 이름 CSV | `import/strings/` |
| 달무리·유니폰트 HEX와 라이선스 | `font/` |
| 전체 등록 음절표·생성 FNT/MAP | `import/fnt/` |
| 폰트·자막·치트 ASM과 JWasm | `import/asm/` |
| 원본 EXE 바이트 패치 | `import/cd-runtime-base.json` |
| HitSquad 1.07 Fix | `import/patches/dune2eng1.07fix/V107UPG/HITSQUAD/` |
| 인코딩할 편집 PNG | `import/GFX/images/` |
| 원본 CG 디코딩 기준 | `export/GFX/manifest.json`, `resources/`, `images/` |
| EXE 문자열 검토 CSV | `export/strings/executable_strings_review.csv` |
| 게임 자체의 기본 설정 | `import/runtime-settings.json` |

원본 CD와 커밋 제외된 보조 CSV·CG 기준 자료, 외부 빌드 도구는 로컬 빌드 환경에 별도로 준비해야 합니다. HitSquad 1.07 Fix 파일은 `import/patches/`에 포함합니다.

## 최종 빌드

프로젝트 루트에서 실행합니다.

```powershell
python tools/build_game.py
```

최종 게임 파일은 항상 `build/final-build/source/VIRGIN/DUNE2/`에 생성됩니다. 빌드는 게임 파일과 CD 이미지·패치를 생성하며, 게임 실행 환경의 선택·설정과 실행은 사용자가 맡습니다. DOSBox-X 설치나 실행 설정 파일을 빌드 입력으로 사용하지 않습니다.

배포물은 `output/`에 다음 이름으로 생성합니다.

| 파일 | 용도 |
|---|---|
| `Dune2-Battle-for-Arrakis-Korean-v1.01.bin` | 한글 CD 이미지 |
| `Dune2-Battle-for-Arrakis-Korean-v1.01.cue` | 해당 BIN의 마운트 정보 |
| `Dune2-Battle-for-Arrakis-Korean-v1.01.bin.xdelta` | 원본 IMG에 적용하는 단일 패치 |
| `Dune2-Battle-for-Arrakis-Korean-v1.01.json` | 원본·결과 해시와 CD 구성 기록 |

중간 자료는 `temp/`에 생성한 뒤 빌드 종료 시 정리합니다. 빌드에는 원본 CD와 현재 입력을 사용하며, 사용자 세이브를 배포 이미지에 추가하지 않습니다. 생성 순서와 HitSquad Fix의 적용·제외 범위는 [빌드 안내](doc/BUILD.md)를 따릅니다.

배포받은 Xdelta와 JSON을 `output/`에 준비한 경우에는 다음 명령으로 원본 IMG에서 한글 BIN/CUE를 복원할 수 있습니다.

```powershell
python tools/clonecd_xdelta.py apply
```

마운트할 때는 생성된 BIN과 CUE를 함께 사용합니다. 상세 옵션은 [CD 패치 적용](doc/PATCHING.md)에 있습니다.

## 번역과 CG 편집

번역은 `import/strings/`의 CSV를 수정합니다. `python tools/build_game.py`로 반영한 뒤 사용자가 마련한 DOS 실행 환경에서 확인합니다. 새 한글 음절은 빌드 성공 시 `import/fnt/glyph_registry.json`에 영구 등록하며, 전체 문자표를 정렬해 완성 FNT를 한 번 생성합니다.

편집 CG는 `import/GFX/images/`의 PNG를 읽어 인코딩합니다. 별도 추출·인코딩 명령은 다음과 같습니다.

```powershell
python tools/edit_cg.py export
python tools/edit_cg.py encode
```

크기·팔레트 색 번호·투명색·프레임 번호는 원본 기준을 유지합니다. 대상 리소스와 명령 옵션은 [CG 편집 안내](doc/GRAPHICS.md)를 따릅니다.

## 저장소 구성과 문서

커밋 대상 폴더는 `doc/`, `font/`, `import/`, `tools/`입니다. 루트의 README·라이선스·`.gitignore`도 커밋 대상입니다.

나머지 로컬 폴더와 에뮬레이터 기록은 커밋에서 제외합니다. 원본 CD·추출 게임 파일과 캐시·임시 파일은 [.gitignore](.gitignore)의 제외 규칙을 따릅니다. `import/patches/`의 패치 패키지는 빌드 입력이므로 EXE·PAK도 함께 커밋합니다. 새 clone에는 커밋 제외 자료가 포함되지 않습니다.

`doc/`는 최종 빌드 상태·생성 과정·폰트·CG·런타임 패치·CD 패치 적용을 안내합니다. 전체 구성은 [문서 목차](doc/README.md), 도구별 명령과 검사 범위는 [도구 안내](tools/README.md)에서 찾습니다.

`doc/analysis/`에는 게임 엔진·폰트·메모리·문자열·CG·치트·영상 패치의 원본 분석·시험·검증 기록을 둡니다. 분석 당시의 주소·바이트·해시·검증 근거를 보존하며, 현재 최종 산출물 정보는 [최종 빌드 상태](doc/STATUS.md)를 따릅니다.

## 라이선스

프로젝트용 도구 소스는 [MIT 라이선스](LICENSE-MIT-PROJECT.txt)를 따릅니다. 글꼴 라이선스는 [font/README.md](font/README.md), JWasm 라이선스는 [ASM 입력 안내](import/asm/README.md)에 있습니다. 원본 게임·수정 게임 파일과 리소스, 글꼴 및 제3자 도구에는 각각의 저작권·라이선스가 적용됩니다.

# 최종 빌드 상태

기준일: 2026-10-27. 이 문서에서 현재 실행본·해시·적용 기능·확인 결과를 관리한다. 생성 절차는 [BUILD](BUILD.md), 조작과 패치 동작은 [RUNTIME](RUNTIME.md)을 따른다.

## 실행본과 배포물

| 항목 | 현재 값 |
|---|---|
| DOS 실행 파일 | `build/final-build/source/VIRGIN/DUNE2/DUNE2.EXE` |
| 게임 폴더 | `build/final-build/source/VIRGIN/DUNE2` |
| 실행 파일 | `DUNE2.EXE`, 388,418바이트 |
| EXE SHA-256 | `835e5067944b492b5eafaa8821a77f2cfc8d508c29c5d2cd7fdc282339c1d93c` |
| 배포 이름 | `Dune2-Battle-for-Arrakis-Korean-v1.01` |
| 산출물 | `output/`의 `.bin`, `.cue`, `.bin.xdelta`, `.json` |
| BIN SHA-256 | `d8c4e5025ad35886cd29b164ab69134eb4fce502b507ac3af15fc7e647d263e5` |
| Xdelta SHA-256 | `6f707d5b8f7ec6b6dd3d13cb0c5b27e610f7eb325521222f3c1919891731f82c` |
| 빌드 기록 | [build-report.json](../build/final-build/build-report.json), [hitsquad107-fix-report.json](../build/final-build/hitsquad107-fix-report.json) |
| CD 구성·파일 해시 | [배포 기록](../output/Dune2-Battle-for-Arrakis-Korean-v1.01.json) |

## 현재 데이터와 적용 기능

| 항목 | 현재 상태 |
|---|---|
| 번역 자료 | CSV 1,350행 중 빌드 반영 930행. 보안 질문·DOS 메시지·예약 데이터도 전체 행 수에 포함 |
| 달무리 | 등록 한글 740음절·총 858글리프. 영문·숫자·부호를 번역 구간에 적용 |
| 유니폰트 | 오프닝·엔딩·중간 영상의 사용 글자 247개(한글 243·부호 4) |
| 글리프 등록 | 전체 문자표 version 2를 영구 저장. 새 음절만 저장·등록하고 완성 FNT를 한 번 생성 |
| 출력·입력 | 원본 텍스트 루프·스타일 테두리·단축키 판독을 유지하며 화면 간격과 지도 파서를 수정 |
| 치트 | CREDITS·WIN·LOSE·FASTBUILD·REVEAL 다섯 명령 |
| 영상·임무 | 영어 자막과 음성 동시 출력, 하코넨 #320·오르도스 #308 자막/입 애니메이션, 보안 질문 생략·원본 페이드 유지 |
| CG·Fix | 선택 PNG 반영, 영어 가문 질문 3행 대응, HitSquad 1.07 Fix 통합 |
| 배포 | 원본 IMG에 적용할 단일 Xdelta와 BIN/CUE 생성. 사용자 세이브를 추가하지 않음 |

글리프 형식·MZ/XMS·메모리 경계는 [FONTS](FONTS.md), 화면별 수정값과 치트 동작은 [RUNTIME](RUNTIME.md), 편집 범위는 [GRAPHICS](GRAPHICS.md)에 정리한다. 과거 수량은 해당 원본 분석 기록의 작성 시점 값이다.

## 사용자 실행 확인

사용자는 JWasm 생성본을 엔딩까지 실행하고 기능 이상이 없다고 확인했다. 그 실행 파일의 SHA-256은 위 현재 EXE와 같다. 근거는 [JWasm 통합 대조](../build/analysis/jwasm-editor-integration/integration-verification.json)에 있다.

| 확인한 범위 | 결과 |
|---|---|
| 치트 5개 | CREDITS +10,000, WIN/LOSE, 내 가문 생산 5배 전환·상태 메시지, 지도 공개 모두 정상 |
| 한글·멘타트 | 달무리·2바이트 토큰·치트 적용, 설명 정지 해소, 목록·짧은 설명 간격 정상 |
| 테두리·명령 | 원본 스타일과 정보창 간격, 생산 화면 BUILD THIS(B)·RESUME GAME(R) 정상 |
| 자막·음성 | 동시 출력, 유니폰트와 토큰 보존, 두 가문의 마지막 자막·연장된 입 애니메이션 정상 |
| 임무 전환·Fix | 보안 질문 생략 후 페이드와 임무 설명 정상 진행, HitSquad Fix 통합본 정상 |

## 현재 생성 방식의 검수

전체 740음절 문자표로 이전한 뒤 초기 CSV 없이 완성 FNT를 한 번 생성하는 것을 확인했다. 이미 등록된 음절은 새 등록 0개로 처리되며, 다음 빌드에서도 중복 등록되지 않는다.

EXE·FNT·PAK와 나머지 게임 파일은 사용자 확인본과 같다. `DUNEHAN.TBL`만 전체 문자표로 갱신했고, 그 변경을 반영한 BIN·Xdelta가 위 배포물이다. 실행 코드와 MZ 메모리 배치는 보존됐다.

원본/CD 패치와 제한된 x86 명령 실행 등의 [통합 검사 결과](../build/checks/final-build-check.json)를 기록했다. 게임 실행 확인은 위 사용자 기록을 따른다. 검사를 다시 실행하는 명령과 검사 범위는 [도구 안내](../tools/README.md#최종-빌드-검사)에 있다.

2026-10-27 빌더의 에뮬레이터 설정·실행 BAT 의존성을 제거했다. 루트 BAT와 DOSBox-X 설정이 없는 상태에서 최종 빌드를 생성했으며, 게임 파일·폰트·BIN/CUE·Xdelta와 배포 JSON의 해시는 직전 최종본과 같다. 게임 실행은 사용자가 선택한 환경에서 진행한다.

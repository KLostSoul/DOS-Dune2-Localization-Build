# 최종 빌드 상태

기준일: 2026-10-27. 현재 실행본·해시·적용 기능을 기록한다. 생성 절차는 [BUILD](BUILD.md), 조작과 패치 동작은 [RUNTIME](RUNTIME.md)을 따른다.

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
| Xdelta SHA-256 | `26467e7dad84594deda58faa7e9d2535d5aaa0746f0bce993f9544aefbdd7647` |
| 빌드 기록 | `build/final-build/build-report.json`, `hitsquad107-fix-report.json` |
| CD 구성·파일 해시 | `output/Dune2-Battle-for-Arrakis-Korean-v1.01.json` |

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
| 원본 기준 준비 | 없는 CG 기준 리소스·원본 PNG·매니페스트와 EXE 검토 CSV를 CD 원본에서 자동 생성 |

글리프 형식·MZ/XMS·메모리 경계는 [FONTS](FONTS.md), 화면별 수정값과 치트 동작은 [RUNTIME](RUNTIME.md), 편집 범위는 [GRAPHICS](GRAPHICS.md)에 정리한다.

## 산출물 검사

```powershell
python tools/check_final_build.py
```

결과는 `build/final-build-check.json`에 기록한다. 검사 범위와 요구 패키지는 [도구 안내](../tools/README.md#최종-빌드-검사)를 따른다.

# Dune II 한글 조합 FNT 메뉴 시험 준비

## 현재 상태

2026-10-20 기준, 격리한 게임 시험 사본을 2바이트 한글 조합 인덱스로 다시 빌드했고 메뉴의 다섯 항목을 `가나다라`로 바꿨다. 사용자가 DOSBox-X에서 실행해 출력이 이상 없음을 확인했다. 어시스턴트는 이 확인을 위해 게임을 다시 실행하지 않았다.

## 한글 FNT

`font/dune2-hangul-compose.fnt`는 `D2HFNT1` 조합 FNT다. 24바이트 헤더 뒤에 초성 배치 선택 42바이트, 조합 인덱스 선택표 1,428바이트, 316개 1bpp 10×10 구성 글리프를 저장한다. 파일 크기는 7,874바이트다. 기존 16×16 구성 글리프에서 10×10 비트맵을 만든 것이며, 이전 전수 비교 결과는 표시 품질 검증으로 인정하지 않는다.

각 완성형 음절의 조합 인덱스 `n = 0..11171`은 두 바이트로 저장한다. `lead = 0x80 + floor(n / 127)`, `trail = 1 + (n mod 127)`이며, 가능한 조합은 11,176개다. 꼬리 바이트를 0으로 만들지 않아 NUL 종료 문자열에서 토큰이 잘리지 않는다. 런타임은 값을 다시 `L,V,T`로 분해해 별도 `DUNEHAN.FNT`의 구성 글리프로 합성한다. 원본 게임 폰트는 유지한다.

메뉴 문자열 폭 사전 계산의 `2326:0009`와 출력 직전 폭 조회를 모두 후크한다. `2326:002F`의 메뉴 루프는 문자열 바이트 수를 반복 횟수로 쓰므로, 한글 토큰을 처리할 때 포인터와 바이트 카운터를 한 칸 더 넘긴다. 정방향·역방향 문자열 폭 경로도 각각 토큰의 두 번째 바이트 또는 첫 번째 바이트를 건너뛴다.

## 테스트 사본

`tools/hangul-render-hook.asm`은 한글 토큰의 셀 폭과 구성 글리프 출력을 10×10으로 설정한다. 수정된 게임 파일은 격리된 시험 사본에만 기록했다.

- 게임 사본: `build/hangul-runtime/source/VIRGIN/DUNE2/`
- 한글 FNT: `build/hangul-runtime/source/VIRGIN/DUNE2/DUNEHAN.FNT`
- 실행 파일: `build/hangul-runtime/source/VIRGIN/DUNE2/DUNE2.EXE`
- 메뉴 시험 리소스: `build/hangul-runtime/source/VIRGIN/DUNE2/ENGLISH.PAK`
- DOSBox-X 설정: `build/hangul-runtime/dosbox-x-hangul-test.conf`
- 직접 실행 배치: `build/hangul-runtime/run_hangul_test.bat`
- 빌드 보고서: `build/analysis/cleanup-2026-10-24/evidence/hangul-runtime/patch-report.json`
- 메뉴 토큰 기록: `build/analysis/cleanup-2026-10-24/evidence/hangul-runtime/menu-labels-test.json`

실행 배치는 `C:\DOSBox-X\dosbox-x.exe`를 위 설정 파일로 시작한다. 시험 사본 재생성에는 아래 명령을 쓴다. 재생성은 게임을 실행하지 않는다.

```powershell
& 'C:\Users\LS\AppData\Local\Python\bin\python.exe' tools/build_hangul_runtime_patch.py
```

`patch-report.json`의 `runtime_verified`는 사용자 확인을 반영해 `true`다. 사용자는 현재 2바이트 시험본의 출력이 이상 없다고 확인했다. `menu-labels-test.json`의 `dosbox_x_executed: false`는 어시스턴트가 직접 DOSBox-X를 실행하지 않았다는 뜻이며, 사용자의 별도 실행 확인과 모순되지 않는다.

# Dune II 달무리 완성형 8×8 시험

기록일: 2026-10-21

## 구조

기존 초·중·종성 조합 FNT와 실행 후크는 그대로 두고, `dalmuri-8x8` 빌드 프로필을 추가했다. 이 프로필은 `font/composed-hangul.hex`의 완성형 음절 비트맵을 사용한다. 원본 HEX는 U+AC00..U+D7A3의 11,172개 항목을 갖는다. 각 항목의 두 바이트 접두부는 0이고, 뒤의 8개 리틀엔디안 16비트 값은 상위 바이트가 모두 0이었다. 따라서 각 행의 하위 바이트를 8픽셀 MSB 우선 비트맵으로 저장한다.

시험 메뉴 다섯 항목에 쓰인 한글 24회에서 고유 완성 음절만 뽑아 정렬된 희소 표로 만들었다. 표 레코드는 2바이트 U+AC00 기준 음절 번호와 8바이트 8×8 비트맵으로 구성된다. 이번 시험은 19자, 19개 레코드다.

| 항목 | 값 |
|---|---:|
| FNT 헤더 | 24바이트 |
| 음절 레코드 | 19 × 10 = 190바이트 |
| `DUNEHAN.FNT` | 214바이트 |
| 실행 중 DOS 메모리 할당 | 0바이트 |
| 실행 파일 상주 이미지의 내장 표 | 214바이트 (`3D02:0540`) |
| 기존 전체 완성음절 수 | 11,172자 중 19자만 적재 |

## 좌우 간격 및 메뉴 위치

달무리 비트맵과 잉크 크기는 8×8을 유지한다. 렌더러는 각 음절에 10×8 픽셀 셀을 할당하고, 글리프 시작 좌표를 셀의 x+1, y로 잡는다. 따라서 왼쪽과 오른쪽에 각각 1픽셀 공백이 생긴다. 문자 폭 조회와 문자열 폭 계산도 모두 10픽셀을 반환해 실제 출력 위치와 메뉴 폭 계산이 일치한다. 셀 전체가 화면 안에 들도록 오른쪽 클리핑 기준도 10픽셀 폭에 맞췄다.

게임 메뉴의 원래 위치와 패널 배치 명령은 수정하지 않았다. 새 실행 파일에서 원본 메뉴 줄 간격, 세로 기준, 패널 여백 명령 6곳의 바이트를 대조해 보존 여부를 빌더가 확인한다. 이전 16×16 프로필의 메뉴 배치 변경은 이 달무리 프로필에 적용하지 않는다. 메뉴 문구 폭은 게임의 원래 문자열 폭 계산 흐름을 따라 달라질 수 있지만, 메뉴 위치·패널 배치 코드는 원본 그대로다.

런타임은 기존 2바이트 한글 토큰을 음절 번호로 풀고, 희소 표에서 해당 완성 글리프를 직접 찾아 10×8 셀 안에 8×8로 그린다. 초성·중성·종성 합성은 하지 않는다. 비한글 문자는 원본 FNT 렌더러로 전달한다. 214바이트 글리프 표는 실행 파일의 새 상주 MZ 구간에 내장되어 있어 실행 중 파일 열기나 DOS 메모리 할당을 하지 않는다. 좌우 여백은 출력 좌표만 바꾸므로 FNT 테이블 크기는 같다.

## 빌드 산출물

- 실행용 격리 사본: `build/hangul-runtime-dalmuri-8x8/source/VIRGIN/DUNE2/`
- 실행 파일: `build/hangul-runtime-dalmuri-8x8/source/VIRGIN/DUNE2/DUNE2.EXE`
- 한글 FNT: `build/hangul-runtime-dalmuri-8x8/source/VIRGIN/DUNE2/DUNEHAN.FNT`
- 실행 BAT: `build/hangul-runtime-dalmuri-8x8/run_hangul_test.bat`
- DOSBox-X 설정: `build/hangul-runtime-dalmuri-8x8/dosbox-x-hangul-test.conf`
- 글리프 미리보기: `build/hangul-runtime-dalmuri-8x8/dalmuri-8x8-glyphs.png`
- 글리프·메뉴 토큰 보고서: `build/analysis/cleanup-2026-10-24/evidence/hangul-runtime-dalmuri-8x8/patch-report.json`, `build/analysis/cleanup-2026-10-24/evidence/hangul-runtime-dalmuri-8x8/menu-labels-test.json`

## 정적 확인과 범위

빌더가 MASM 후크를 조립하고 별도 게임 사본을 만들었다. FNT 헤더, 19개 레코드의 정렬과 개수, 각 8바이트 행을 원본 `composed-hangul.hex`에서 추출한 행과 대조했다. 테이블 214바이트는 EXE 상주 이미지의 `3D02:0540`에 내장되며, 실행 시 별도 DOS MCB가 생기지 않는다. 좌우 1픽셀 여백을 적용한 미리보기 셀은 10×8이고 잉크는 8×8이다. EXE의 기존 Borland 오버레이와 메뉴 배치 명령은 그대로 보존됐다. 원본 게임 파일은 수정하지 않았다.

DOSBox-X에서 게임을 실행하지 않았다. 화면 출력과 글리프 가독성은 사용자가 `run_hangul_test.bat`으로 확인해야 한다. 다른 게임 문자열을 한글화하면 그 문자열의 완성 음절도 희소 표에 추가해야 한다. 빌더는 현재 `MENU_TRANSLATIONS`의 다섯 메뉴 항목을 표의 입력으로 사용한다.

## 치트 모듈 통합 빌드

달무리 8×8 폰트 빌드에 기존 치트 입력·실행 모듈을 결합한 별도 사본을 만들었다. 달무리 폰트 훅은 기존 글자 렌더러 진입점을 연결하고, 치트 모듈은 키보드·게임 입력 문맥·승패 분기 진입점을 연결한다. 두 후크의 원본 진입점은 겹치지 않는다. 치트 모듈은 폰트 모듈 뒤 별도 상주 구간에 추가했다.

| 항목 | 값 |
|---|---|
| 실행 BAT | `build/cheat-dalmuri-8x8-runtime/run_cheat_dalmuri_8x8_test.bat` |
| 실행 파일 | `build/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/DUNE2.EXE` |
| DOSBox-X 설정 | `build/cheat-dalmuri-8x8-runtime/dosbox-x-cheat-dalmuri-8x8.conf` |
| 실행 파일 SHA-256 | `cff1fbca859634321b798acbd26ac7f16752fe020d61ba542a888badc108a32c` |
| 치트 모듈 | 세그먼트 `3D64h`, 2,448바이트; 시작 스택 `3DFDh` |
| 한글 폰트 메모리 | 실행 중 별도 DOS 블록 없음; 214바이트 표가 실행 파일 상주 이미지에 내장 |
| 치트 패널 메모리 | XMS 화면 백업 4KiB; 치트 기능에 XMS 필요 |
| 명령 | `CREDITS`, `WIN`, `LOSE` |
| 실행 후 conventional memory | 자유 MCB 45,872바이트 (`94CB`), DUNE2 메인 MCB `074A`의 바로 다음 블록 |

치트 입력은 게임 플레이 문맥에서만 활성화된다. 메뉴와 이름 입력은 원래 키 처리기로 전달한다. 치트 통합으로 MZ 이미지 끝은 기준 폰트판 `0x42240`에서 `0x42BD0`으로 이동했고, 전체 미패치 원본 대비 상주 이미지가 4,016바이트 커졌다. 치트 모듈은 별도 DOS 메모리 블록이 아니라 같은 MZ 상주 이미지에 있으며 스택 기준은 `3DFDh`다. MZ 재배치 수는 4,485에서 4,488로 늘었고, 이동된 Borland 오버레이는 바이트 단위로 보존됐다. 빌더는 달무리 EXE 안의 내장 표와 `DUNEHAN.FNT` 사본을 바이트 단위로 대조하고, 새 실행 파일에서도 원본 메뉴 배치 명령을 유지한다. 통합 보고서는 `build/analysis/cleanup-2026-10-24/evidence/cheat-dalmuri-8x8-runtime/cheat-patch-report.json`이다.

사용자는 SHA-256 `cff1fbca859634321b798acbd26ac7f16752fe020d61ba542a888badc108a32c`인 통합판이 문제없이 작동하며 치트와 한글 폰트가 제대로 적용됐다고 확인했다. 이어 실행 중 `DOS MCBS` 결과에서 DUNE2 메인 MCB `074A`가 579,584바이트이고, 바로 다음 MCB `94CB`가 자유 블록 45,872바이트인 것을 확인했다. 폰트용 별도 MCB는 없다. 실행 파일은 미패치 원본보다 4,016바이트 커져 상주 이미지가 커진다. 이 MCB 수치는 DOSBox-X에서 확인한 값이며 실제 DOS 환경의 여유 메모리는 별도 확인하지 않았다.

이 통합 빌드의 실행 확인은 사용자가 직접 했다. 치트 입력과 한글 폰트의 적용이 정상이라고 보고했다. 개별 치트 명령, 시험 시간, 실행 후 MCB 덤프는 별도로 기록되지 않았다.

## 현재 통합 설계: 원본 FNT 구간별 글꼴 선택 (2026-10-21)

위의 214바이트 희소 표 빌드는 이력이다. 현재 후보는 희소 표를 사용하지 않는다. 렌더러 상태 `20AA:[008A/008C]`가 가리키는 활성 원본 FNT 헤더를 확인해 구간을 선택한다.

| 원본 FNT 구간 | 원본 헤더 판별값 | 한글 글꼴 |
|---|---|---|
| `NEW6P.FNT` | 길이 `0x0CCC`, 최대 높이/너비 `8/8` | 달무리 완성형 8×8 |
| `NEW8P.FNT` | 길이 `0x1646`, 최대 높이/너비 `11/10` | 달무리 완성형 8×8, 기존 시험과 같은 10픽셀 셀 |
| `INTRO.FNT` 및 그 밖의 활성 FNT | NEW6P/NEW8P 헤더와 불일치 | 기존 유니폰트 초·중·종성 조합 FNT, 15×15 잉크/16×16 셀 |

`font/composed-hangul.hex`의 U+AC00..U+D7A3 전체 11,172개 음절을 순서대로 `DUNEHAN.DLM`에 저장한다. 토큰에서 복원한 U+AC00 기준 음절 번호 `n`으로 `n×8` 위치를 직접 읽으므로 음절별 검색표가 없다. 기존 조합 글리프는 별도 `DUNEHAN.FNT`에 그대로 포함한다. 비한글 문자는 원본 Dune FNT 렌더러로 전달한다.

### 메모리 배치

| 구간 | MZ 이미지 끝 | 증가량 |
|---|---:|---:|
| 미패치 원본 | `0x41C20` | — |
| 폰트 후크 포함 | `0x43040` | 5,152바이트 |
| 치트 모듈까지 포함 | `0x439D0` | 추가 2,448바이트 |

전체 증가는 원본 대비 7,600바이트이며 폰트 후크와 치트 모듈이 하나의 MZ 로드 이미지에 연속해 들어간다. 폰트 후크는 원본 이미지 끝의 새 세그먼트 `3D02h`에서 시작해 `3E44h`까지 사용하고, 치트 모듈은 `3E44h`부터 `3EDDh`까지 차지한다. 시작 스택은 치트 모듈 바로 뒤 `3EDDh`로 옮긴다. 폰트 데이터 때문에 DOS `AH=48h` 블록이나 게임 FAR 힙 할당을 추가하지 않는다.

| XMS 핸들 | 크기 |
|---|---:|
| 달무리 비트맵 89,376바이트 | 88KiB |
| 유니폰트 조합 비트맵 9,480바이트 | 10KiB |
| 치트 화면 백업 | 4KiB |
| 합계 요청량 | 102KiB |

1,554바이트 조합 선택자와 256바이트 전송 버퍼는 상주 MZ 이미지 안에 둔다. 조합 글리프는 첫 사용 때, 달무리 비트맵은 첫 사용 때 각각 256바이트 단위로 읽어 XMS에 적재한다. 이 방식은 폰트 전용 MCB를 만들지 않지만, MZ 상주 이미지가 미패치 원본보다 7,600바이트 커진다.

### 산출물과 확인 범위

- 실행 배치: `듄2_치트테스트.bat`
- 직접 실행 배치: `build/cheat-dalmuri-8x8-runtime/run_cheat_dalmuri_8x8_test.bat`
- 실행 파일: `build/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/DUNE2.EXE`
- 달무리 전체 음절 파일: `build/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/DUNEHAN.DLM` (89,400바이트: 24바이트 헤더 + 89,376바이트 비트맵)
- 조합 글꼴: `build/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/DUNEHAN.FNT` (11,034바이트)
- 빌드 보고서: `build/analysis/cleanup-2026-10-24/evidence/hangul-runtime-dalmuri-sections/patch-report.json`, `build/analysis/cleanup-2026-10-24/evidence/cheat-dalmuri-8x8-runtime/cheat-patch-report.json`
- 실행 파일 SHA-256: `a6ee65ff88d2c225157d456abb1a3387114ba5f1196d20cf868df155cc11e146`

이번 빌드에서 Python 구문 확인과 MASM 조립, FNT/DLM 헤더·크기·음절 순서, 메뉴 레이아웃 원본 바이트, MZ 이미지 경계·재배치·Borland 오버레이 보존을 정적으로 확인했다. 새 후보를 게임에서 실행하거나 MCB 덤프를 수집하지는 않았다. 따라서 출력 결과와 실제 DOSBox-X MCB 수치는 사용자의 실행 확인 전이다.

## 재구성 기록

사용자가 실행 정상으로 확인한 이전 치트 빌드 `cff1fbca859634321b798acbd26ac7f16752fe020d61ba542a888badc108a32c`를 달무리 8×8 검증 EXE와 현 치트 후크 소스에서 다시 만들었고, SHA-256이 기록값과 정확히 일치했다. 복구본은 [recovered-verified-dalmuri-cheat-baseline](../../../archives/builds/verified/recovered-verified-dalmuri-cheat-baseline.zip)에 별도 보존했다.

앞서 생성한 구간별 통합 후보의 SHA-256은 `a6ee65ff88d2c225157d456abb1a3387114ba5f1196d20cf868df155cc11e146`이다. 이는 이전에 거부된 후보와 같은 파일이어서 현행 실행본으로 채택하지 않았다. 조합 FNT의 SHA-256은 `2964c09b73ad0d8642516e9cb14fb61a8cbfe7d6ba8e1bbdb93944657aa1525f`로 확인했다.

### 2026-10-21 실행본 복구

실행 경로의 거부된 6ee… 후보를 정상 동작 확인본으로 교체했다. 현재 uild/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/DUNE2.EXE의 SHA-256은 cff1fbca859634321b798acbd26ac7f16752fe020d61ba542a888badc108a32c이고, 짝이 되는 DUNEHAN.FNT는 214바이트다. _SAVE000.DAT와 SAVEFAME.DAT은 덮어쓰지 않았으며 해시가 그대로다. 구간별 달무리/조합 글리프 통합은 현행 실행본에 아직 적용되지 않았다.

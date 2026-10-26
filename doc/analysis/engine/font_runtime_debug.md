> 분석·수정 이력입니다. 빌드명·해시와 당시의 “현재 후보”·“확인 전”은 해당 절 작성 시점의 기록입니다. 최신 실행본·적용 기능·사용자 확인은 [현재 상태](../../STATUS.md)를 따릅니다.

# Dune II 원본 FNT 화면별 디버그 검증

> 2026-10-23 주소 정정: 이 문서의 과거 정적 범위 `3208:...`는 실제 FBOV 모듈 배정이 아니다. 저장된 원시 실행 관측과 파일 오프셋은 유지되며, 브리핑 초기 포맷 호출은 실제 `32DD:0B60`, 공통 본문 호출은 `32DD:0DFF`로 재배정했다. 다른 `3208` 표기도 실제 모듈 주소로 사용하면 안 된다. 재대조 근거와 임무 브리핑의 전체 진입 경로는 [전환 재분석](security_briefing_transition.md)에 기록했다.

## 대상과 결과 범위

설치된 `C:\DOSBox-X\dosbox-x.exe`와 emucap DOSBox-X 외부 디버거 어댑터 0.2.0으로 원본을 실행했다. 원본 EXE SHA-256은 `99f44e83b309dd826f3dbc5068c61679bb68047eed8d738dcef594ba0eef7552`다. 게임은 관리형 실행별 사본에서 실행했다. 이 검증에서 한글 FNT나 게임 패치를 수정하지 않았다.

포맷/문자 루프 진입점에서 **24건**, 정보 패널·메시지 큐 래퍼 진입에서 **2건**, 메시지 큐의 문구 입력 내부 분기에서 **1건**을 확보했다. 24건에는 같은 함수·문자열의 반복 출력과 null 문자열 상태 호출이 포함된다. 서로 다른 함수 24개를 검증했다는 뜻이 아니다. 프레임 진행만 끝나고 중단점에 도달하지 않은 수집 3건은 스택 해석과 검증 건수에서 제외했다.

**전체 정적 참조의 동적 검증이 완료된 것은 아니다.** 아래 확인 범위와 마지막의 미확인 범위를 구분한다.

## 증거 파일

- [원시 레지스터·스택·문자열·호출자 바이트](../../../build/analysis/original-font-engine/runtime-debug/extended/extended-report.json)
- [재계산 요약과 원본 FNT 폭 대조](../../../build/analysis/original-font-engine/runtime-debug/extended/summary.json)
- [화면별 관측 CSV](../../../build/analysis/original-font-engine/runtime-debug/extended/observations.csv)
- [가문 선택 시점 RAM 640 KiB](../../../build/analysis/original-font-engine/runtime-debug/extended/house-selection-ram.bin)
- [증거 요약 재생성 스크립트](../../../archives/tools/README.md)

요약 재생성은 저장된 증거와 원본 EXE/PAK를 읽는다. 게임을 실행하거나 새로운 동적 도달성을 확인하는 명령이 아니다.

```powershell
& 'C:\Users\LS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tools/summarize_font_runtime_debug.mjs
```

## 중단점과 판독 규칙

| 원본 주소 | 실제 실행 주소 | 선형 주소 | 역할 |
|---|---|---|---|
| `0EED:1E65` | `1711:1E65` | `0x18F75` | 공통 포맷 함수 |
| `29C7:0004` | `31EB:0004` | `0x31EB4` | 문자 출력 루프 |
| `0EED:0F1A` | `1711:0F1A` | `0x1802A` | 게임 정보 패널 래퍼 |
| `0EED:09AB` | `1711:09AB` | `0x17ABB` | 메시지 큐 래퍼 |
| `0EED:09C6` | `1711:09C6` | `0x17AD6` | null 검사 통과 후 문구 입력 분기 |

FAR 함수의 첫 명령에서 `SS:SP`를 읽었다. 반환 IP/CS는 `SP+0/+2`, 문자열 FAR 포인터는 `SP+4/+6`, X/Y는 `SP+8/+10`이다. 포맷 함수의 옵션은 `SP+16`이다. 문자 루프의 `SP+16`을 포맷 옵션으로 해석하지 않는다. 정보 패널 래퍼의 인자는 별도 구조이므로 원시 스택만 보존했다.

폰트 메트릭은 `DS:6CF8`에서 읽었다. 수평·수직 간격은 부호 있는 16비트 값, 최대 폭·높이는 각각 바이트, 폭 표는 FAR 포인터다. **포맷 함수 진입 시점의 메트릭은 옵션 적용 전 상태**다. 실제 출력 폰트를 확정할 때는 뒤이어 도달한 문자 루프의 메트릭과 포인터를 사용한다.

## 화면별 실제 관측

아래 정적 호출 주소는 기존 분석기의 코드 범위 표기로, 실행 중 CS 주소와 구분한다. 파일 위치는 실제 호출 명령의 시작이다.

| 화면 / 문자열 | 중단 위치 | X, Y | 포맷 옵션 | 원본 호출 위치 |
|---|---|---|---|---|
| 가문 설명 초기 상태 | 포맷, null 문자열 | 0, 0 | `0x31`, `0x32` | `3208:3901`, `393E` / `0x4E310`, `0x4E34D` |
| `House Ordos` | 포맷 | 4, 1 | `0x32` | `3208:3BA0` / `0x4E5AF` |
| Ordos 설명 본문 | 포맷 | 4, 1 | `0x32` | 같은 호출 위치 |
| 임무 브리핑 초기 상태 | 포맷, null 문자열 | 0, 0 | `0x31` | `3208:3901` / `0x4E310` |
| 게임 메뉴 제목 | 포맷 | 160, 54 | `0x122` | `3208:7A1B` / `0x5242A` |
| `Load a game` | 포맷 | 160, 73 | `0x122` | `3208:8134` / `0x52B43` |
| `Save this game` | 포맷 | 160, 90 | `0x122` | 같은 호출 위치 |
| `Game controls` | 포맷 | 160, 107 | `0x122` | 같은 호출 위치 |
| 저장 설명에 입력한 `a` | 문자 루프 | 32, 110 | 해당 없음 | `0EED:1FEF` / `0x15ABF` |
| 불러오기 목록 저장명 `ab` | 포맷 | 168, 77 | `0x122` | `3208:8134` / `0x52B43` |
| Game controls의 `ON` | 포맷 | 232, 72 | `0x122` | 같은 호출 위치 |
| Mentat의 `Select Subject:` | 포맷 | 144, 50 | `0x12` | `3208:5271` / `0x4FC80` |
| Mentat 목록 전환 상태 | 포맷, null 문자열 | 0, 0 | `0x11` | `3208:528F` / `0x4FC9E` |
| Mentat 목록 `Advice` | 문자 루프 | 152, 72 | 해당 없음 | `2CA0:2357` / `0x4647C` |
| Mentat 조언 본문 | 문자 루프 | 4, 1 | 해당 없음 | `0EED:1FEF` / `0x15ABF` |
| 게임 정보 `Const. Yard` | 포맷 | 288, 43 | `0x111` | `0EED:1308` / `0x14DD8` |
| 같은 `Const. Yard` | 문자 루프 | 261, 43 | 해당 없음 | `0EED:1FEF` / `0x15ABF` |

게임 메뉴의 행 Y는 `73 → 90 → 107`로 17픽셀씩 증가했다. 제목과 선택문의 중앙 X는 160이다. 저장 목록은 중앙 X 168, 설정값 버튼은 X 232로 서로 다르다. 화면마다 UI 영역과 기준점이 다르므로 한 메뉴의 좌표를 전체 창에 적용할 수 없다.

Ordos 본문의 실제 입력에는 `0x0D` 줄바꿈이 포함됐다. 이것은 문자열 입력 증거이며, 줄바꿈 이후 모든 행의 Y나 자동 줄바꿈 경계까지 실측했다는 뜻은 아니다. Mentat 조언은 서로 다른 문장이 `(4, 1)`에서 시작하는 것을 확인했다. 기록의 `mentat-advice-next-line`은 다음 문장의 호출이며, 다음 화면 행의 Y 실측으로 해석하지 않는다.

저장 입력은 격리 실행 사본에서 `ab`로 시험 저장하고, 목록에서 `ab`가 전달되는 것을 확인한 뒤 불러왔다. 입력란이 문자 루프에 도달한 사실은 확인했지만, 이를 곧바로 정적 `3208:FA74` 편집 함수가 실행됐다는 증거로 삼지 않는다.

## 원본 FNT와 실제 배치의 수치 대조

가문 선택 화면의 RAM 전체에서 다음 포인터의 데이터 전체를 `DUNE.PAK`의 자산 전체 바이트와 비교했다.

| 포인터 | 역할 | 일치한 원본 파일 |
|---|---|---|
| `86D5:0005` | 기본·활성·저장된 기본 폰트 | `NEW8P.FNT` |
| `8BAB:0005` | 보조 폰트 | `NEW6P.FNT` |

폰트 이름을 화면 생김새만으로 추측한 결과가 아니다. 초기 RAM의 전체 바이트 대조 결과는 `summary.json`의 `house_selection_full_font_byte_comparisons`에 있다.

게임 정보 패널에서는 포맷 함수와 문자 루프를 연속으로 멈췄다. 실제 문자 루프의 활성 포인터는 `8BAB:0005`, 메트릭은 최대 폭/높이 `8/8`, 수평 간격 `-2`, 수직 간격 `0`, 폭 표 `8BAB:01DD`였다.

`Const. Yard` 11문자에 대한 `NEW6P.FNT` 폭 표 값은 다음과 같다.

```text
C  o  n  s  t  .  공백  Y  a  r  d
6  7  8  7  8  4    7   8  7  7  7
```

```text
폭 표 합계             = 76
수평 간격을 포함한 폭  = 76 + (-2 × 11) = 54
중앙 정렬 시작 X       = 288 - (54 >> 1) = 261
실제 문자 루프 X       = 261  → 일치
```

따라서 게임의 실제 정렬 폭은 단순한 글리프 비트맵 폭 합계가 아니다. 활성 폰트의 폭 표와 현재 수평 간격을 함께 사용한다. 한글 출력에도 폭 조회·실제 전진·정렬 계산에서 같은 규칙을 적용해야 한다.

Mentat 목록 `Advice`의 문자 루프 역시 최대 폭/높이 `8/8`, 수평 간격 `-2`였다. 반면 저장 입력과 조언 본문은 최대 폭/높이 `10/11`, 수평 간격 `-1`이었다. 공통 렌더러를 호출하더라도 화면별 활성 메트릭은 다르다.

## 오버레이 실행 주소를 정적 주소와 연결한 방법

상주 코드의 세그먼트 재배치는 기존 실측과 같은 `+0x824`다. 그러나 오버레이의 CS는 동적으로 배정되므로 이 값을 일괄 더해 중단점을 만들 수 없다. 동일 브리핑 초기 호출의 반환 주소가 첫 화면에서는 `4621:0B65`, 다음 화면에서는 `48A7:0B65`였으며, 두 호출자 모두 원본 파일 `0x4E310`의 호출에 대응했다.

호출자 주변 64바이트를 보존하고 다음 런타임 변경을 허용해 원본 EXE와 대조했다.

- FAR CALL의 재배치된 세그먼트 피연산자.
- 오버레이 로더가 FAR CALL을 `NOP / PUSH CS / near CALL`로 고친 5바이트 구간.
- 캡처 시작이 이전 호출 피연산자의 중간일 수 있으므로 앞 8바이트를 비교에서 제외.

이 규칙으로 24건 모두 원본 파일에서 후보가 하나씩 나왔다. 이 대조는 저장된 호출자와 파일 위치의 연결을 확인한 것이며, 전체 오버레이 로더의 배치 규칙을 완전히 복원한 결과는 아니다. 가문 선택 시점에 `3208`의 12개 함수 서명이 RAM에서 발견되지 않은 초기 스캔도 남겼다. 해당 시점의 부재만으로 함수가 사용되지 않는다고 판단하지 않는다.

## 실행 ID와 재현 순서

1. 첫 실행 `launch-01m5c386zhw6mccpk34geb5eek`: 가문 선택 → Ordos 가입 → 임무 설명 → Proceed → Options → 저장 설명 `ab` 입력·저장 → 불러오기 `ab` → Game controls → Previous → Continue → Mentat → Advice.
2. 둘째 실행 `launch-01m5c5x874wntkz36mpgqgmfw9`: 원본 EXE 새 격리 실행 → 오프닝 건너뛰기 → Load a game → 기존 저장 `11` → 정보 패널 래퍼 → `Const. Yard` 포맷 → 문자 루프.
3. 각 중단점은 선형 게스트 RAM 주소로 설치했고, 진입 PC를 확인한 뒤 레지스터·스택·문자열·메트릭·호출자 코드를 읽었다. 중단점 없는 프레임 진행 결과는 함수 적중으로 계산하지 않았다.

Tracking 실행: `01M5C5NZ6B23EM8JVT24Q7B0JW`.

셋째 실행 `launch-01m5c6ngndg6m4q688e1z2ywvz`에서는 아래 팔레트 페이징 수정을 적용한 브리지로 원본 EXE를 새 격리 실행하고, 기존 저장 `11`을 불러왔다. 작은 콘크리트 생산을 시작하고 중단/재개한 뒤 완료 시점의 메시지 큐를 관측했다.

메시지 큐 진입은 프레임 1146의 null 상태 갱신으로 확인했다. 프레임 1664에는 문구 입력 분기 `1711:09C6`에서 멈췄고, `SS:BP+6/+8` 문자열 포인터가 `Small Concrete Slab is completed and ready to place.`를 가리켰다. 이 분기는 함수 프롤로그 실행 후이므로 함수 진입의 `SS:SP` 규칙을 적용하지 않고 `frame_at_bp`를 따로 저장했다. 내부 출력 호출 위치 `0EED:0AFC/0B20`의 적중은 이 실행에서 확보하지 못했다. **문구 입력 확인과 최종 화면 출력 확인은 구분한다.**

화면 증거:

- [게임 메뉴](../../../build/analysis/original-font-engine/runtime-debug/extended/game-menu.png)
- [불러오기 목록](../../../build/analysis/original-font-engine/runtime-debug/extended/load-list.png)
- [Game controls](../../../build/analysis/original-font-engine/runtime-debug/extended/game-controls.png)
- [Mentat 목록](../../../build/analysis/original-font-engine/runtime-debug/extended/mentat-list.png)
- [Mentat 조언 본문](../../../build/analysis/original-font-engine/runtime-debug/extended/mentat-body.png)
- [게임 정보 패널](../../../build/analysis/original-font-engine/runtime-debug/extended/game-panel.png)

스크린샷은 중단점과 별도의 호출에서 읽은 VGA 메모리 화면이다. 함수 진입에서 아직 그리지 않은 문자열은 직후 스크린샷에 없을 수 있다. 스크린샷과 중단점이 동일한 렌더 완료 시점을 뜻한다고 해석하지 않는다.

## 아직 확인하지 못한 구간과 실제 장애

| 남은 항목 | 현재 상태 |
|---|---|
| 메시지 큐 내부의 최종 그리기 분기 | 래퍼 갱신과 완료 문구 입력은 실측했지만 해당 문구의 최종 그리기 중단점은 미적중 |
| `3208:5A89`, `5B81` 레코드 목록의 실제 화면 | 기존 정적 분류를 유지하며 특정 화면으로 확정하지 않음 |
| `3208:F441`–`FDCD` 텍스트 상자·스크롤·입력 보조 함수의 실제 도달성 | 이번 저장 입력/Mentat 관측만으로 이 함수 실행을 입증할 수 없음 |
| `INTRO.FNT` 로드와 오프닝 전용 선택 분기 전체 | 이번 새 실행에서는 null 포맷 상태 호출만 확보; 오프닝 글자 출력 검증으로 계산하지 않음 |
| 자동 줄바꿈 경계, 스크롤 경계, 승패·점수·종료 화면의 분기 | 별도 실행 상태가 필요하며 이번 실측에 포함되지 않음 |
| 107개 정적 폰트 상태 참조의 개별 동적 적중 | 전수 완료 아님 |

첫 실행의 Mentat 종료 뒤, 둘째 실행의 `BUILD IT` 입력 뒤에 디버거 콘솔 응답이 끊겼다. `MEMDUMPBIN`, `BPDEL *`, `VRT`, `EV ...`가 연속 시간 초과됐다. 프로세스 생존과 콘솔 응답 가능성은 별개다. `pause`가 frozen 상태를 반환한 뒤에도 메모리·레지스터 조회는 실패했으므로 그 반환만으로 복구됐다고 판단하지 않았다.

첫 장애 후 새 실행으로 정보 패널 검증을 완료했지만, 건설 창에서 같은 종류의 콘솔 장애가 재발했다. **현재 증거로 게임 오류인지 어댑터의 정지/콘솔 동기화 오류인지 원인을 확정할 수 없다.** 두 관리형 실행은 각각 정확한 실행 ID로 종료했고 DOSBox-X와 브리지의 프로세스 종료를 확인했다. 정상 응답 시의 중단점은 제거했으며, 응답이 끊긴 뒤의 중단점은 프로세스 종료로 정리했다.

위 내용은 최초 두 실행 종료 시점의 장애 기록이다. 후속 조사와 수정 결과는 다음 절과 같다. `summary.json`의 `coverage_complete`는 전체 미확인 경로가 남아 있으므로 `false`다.

## 후속 조사: 팔레트 페이징 중 확인 명령 재전송 수정

실패 로그를 보존해 조사하니, 마지막 정상 출력은 게임 전환 명령이 아니라 스크린샷에서 실행하는 `VGA DACPAL`이었다. 이후 `ADDLOG ECEND...` 확인 문자열이 입력줄에 이어 붙고 `Debugger command not recognized`가 반복됐다.

- [실패 당시 콘솔 화면 텍스트](../../../build/analysis/original-font-engine/runtime-debug/extended/palette-failure-console.txt)
- [실패 당시 디버거 로그](../../../build/analysis/original-font-engine/runtime-debug/extended/palette-failure-debugger.log)

어댑터 `console.rs`는 빈 프롬프트처럼 보이면 20ms 간격으로 확인 명령을 다시 보냈다. `VGA DACPAL`은 페이지 출력을 시작하기 전에 이전 빈 프롬프트가 잠깐 남을 수 있다. 이때 확인 명령을 보내면 문자들이 페이지 제어 입력으로 소비되고 남은 문자열이 다음 명령줄을 오염시킬 수 있다. 설치된 DOSBox-X 참조 소스에서도 DACPAL의 `DEBUG_BeginPagedContent/DEBUG_EndPagedContent`와 별도 입력줄 표시 분기를 확인했다.

외부 브리지의 DACPAL 처리만 다음과 같이 수정했다.

1. 실제 팔레트 출력 또는 페이지 프롬프트를 관측한다.
2. 페이지 진행은 기존 ENTER 처리로 수행한다.
3. 페이지 프롬프트가 사라지고 정확한 빈 입력줄이 100ms 유지될 때 확인 명령을 **한 번만** 보낸다.
4. DACPAL 처리에는 일반 명령의 20ms 확인 명령 재전송을 적용하지 않는다.

수정 소스: [`console.rs`](G:/Codex/MCP/emucap/dosbox-x-adapter/bridge/src/console.rs). 브리지를 오프라인 release 빌드하고 `publish-build.ps1 -SkipControl`로 배치했다. 설치된 DOSBox-X 실행 파일은 변경하지 않았다. 변경된 소스와 바이너리 해시는 원시 보고서의 `palette_bridge_build`에 있다.

셋째 실행에서 다음을 확인했다.

- 게임 화면 연속 캡처 3회 뒤 각각 CPU 조회 성공.
- 이전 장애가 발생했던 `BUILD IT` 뒤 캡처와 CPU 조회 성공.
- 별도 반복 검증으로 **캡처 10회와 각 캡처 직후 CPU 조회 10회 모두 성공**. 같은 frozen 경계의 프레임과 PC가 유지됐다.
- 셋째 실행의 보존 로그에서 `Debugger command not recognized`는 0건.
- 이후 실제 메시지 큐의 문구 입력 분기까지 진행 성공.
- 종료 전 전체 중단점을 제거하고 CPU 조회 성공을 확인한 뒤 정확한 실행 ID로 두 프로세스를 종료했다.

반복 증거: [팔레트 수정 검증 JSON](../../../build/analysis/original-font-engine/runtime-debug/extended/palette-fix-validation.json), [수정 후 전체 디버거 로그](../../../build/analysis/original-font-engine/runtime-debug/extended/palette-fixed-debugger.log), [수정 후 건설 진행 화면](../../../build/analysis/original-font-engine/runtime-debug/extended/construction-after-palette-fix.png).

이 결과는 이번 원본 Dune II VGA mode 13h 경로의 반복 캡처 검증이다. 모든 게임·페이지 출력 명령이나 모든 타이밍에서 어댑터 오류가 없음을 증명하는 전수 결과는 아니다. `pause/status`가 실제 콘솔 응답 확인 없이 frozen을 보고하는 별도 한계도 이번 수정 범위에 포함하지 않았다.

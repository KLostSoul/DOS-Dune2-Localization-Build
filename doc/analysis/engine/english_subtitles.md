> 분석·수정 이력입니다. 빌드명·해시와 당시의 “현재 후보”·“확인 전”은 해당 절 작성 시점의 기록입니다. 최신 실행본·적용 기능·사용자 확인은 [현재 상태](../../STATUS.md)를 따릅니다.

# 오프닝 영어 자막과 음성 경로 정적 분석

## 확인 결과

사용자가 앞선 자막 빌드에서 영어 자막이 화면에 나오는 것을 확인했다. 이제 그 자막 경로를 유지하면서 음성 피드백 처리가 빠지지 않도록 수정했다.

앞선 후보 `dalmuri672-english-subtitles`는 `3208:6CC0`의 영어 분기를 무조건 일반 문자열 경로로 보내면서 `0580:002A` (선형 주소 `0000:582A`) 피드백 조회 호출도 건너뛴다. 그 빌드는 자막 표시가 확인됐지만, 음성 재생은 확인되지 않았다. 따라서 이 후보를 현재 실행 대상으로 두지 않고, 피드백 호출을 유지하는 새 후보를 만들었다.

새 후보는 언어 분기와 피드백 호출을 보존하고, 피드백 항목의 문자열 ID가 0일 때만 자막을 생략하는 분기를 제거한다. 영어의 누락 자막은 원래 이벤트 문자열 ID를 기존 조회·그리기 루틴에 전달한다. 사용자가 새 후보에서 자막과 음성이 함께 정상 출력되는 것을 확인했다.

## 분석 대상과 비교

REA/Ghidra에서 `dalmuri672-production-shortcuts`의 실제 DOS MZ 실행 파일과 세그먼트 `3208` 오버레이 분석본을 확인했다.

| 항목 | 값 |
|---|---|
| 기준 실행 EXE | `build/dalmuri672-production-shortcuts/source/VIRGIN/DUNE2/DUNE2.EXE` |
| 기준 실행 EXE SHA-256 | `021e0207cc8ef542804c4069adfbf331f3a31e9f30c6f8789a4a42bc1089260b` |
| 원본 실행 EXE | `build/source/VIRGIN/DUNE2/DUNE2.EXE` |
| 원본 실행 EXE SHA-256 | `99f44e83b309dd826f3dbc5068c61679bb68047eed8d738dcef594ba0eef7552` |
| 관련 오버레이 | 인덱스 169, 세그먼트 `3208`, 길이 `FFFF`, 플래그 `0004` |
| 원본과 기준 실행 빌드 비교 | 해당 오버레이 `6381`–`70FF` 바이트 차이 0개 |

`current-segment3208-analysis.exe`는 오버레이를 Ghidra에 표시하기 위한 분석 래퍼이며 게임 실행 파일이 아니다.

## 코드 흐름

- 자막 이벤트 처리 함수는 `3208:6B37`이며 문자열 그리기 루틴 `3208:6F75`를 호출한다.
- 언어 인덱스 `4342:37AA`가 0이면 영어다.
- `3208:6CC0`의 `JNZ 3208:6D06` (`75 44`)는 비영어를 공통 문자열 경로로 보낸다. 영어는 피드백 조회 경로로 계속 진행한다.
- 영어 경로는 `3208:6CCD`에서 `0580:002A`를 호출한다. 실제 바이트는 `9A 2A 00 80 05`이며 피드백 인덱스를 전달한다.
- 이어서 `[인덱스 × 0Eh + 031Ch]` 값을 검사한다. 값이 0이면 `3208:6CE2`의 `JZ 3208:6D04` (`74 20`)가 이벤트 문자열 조회와 그리기를 건너뛴다. 0이 아니면 기존 `0000:07DF` 문자열 조회 후 `3208:6F75`에서 표시한다.
- 일반 경로와 피드백 경로 모두 기존 문자열 조회 및 그리기 엔진을 사용한다.

`0580:002A`는 관련 실행 오버레이 바깥에 있어 이 오버레이만으로 내부 동작을 완전히 분석할 수 없다. 따라서 새 패치는 이 호출 전의 분기와 호출 자체를 건드리지 않는다.

## 현재 수정

새 빌드 `build/dalmuri672-english-subtitles-feedback`는 확인된 `dalmuri672-production-shortcuts`에서 생성했다.

| 항목 | 결과 |
|---|---|
| 새 빌드 EXE SHA-256 | `642aabea9eb0b1c9945a5c17267b5c5b228ba237effdfccb85a5a04df379e7a3` |
| EXE 크기 | 382,066바이트, 기준과 동일 |
| 수정 위치 | `3208:6CE2`, 파일 오프셋 `0x54051` |
| 변경 | `74 20` (`JZ 6D04`) → `90 90` (`NOP NOP`) |
| 영어 분기 `3208:6CC0` | `75 44` 그대로 유지 |
| 피드백 호출 `3208:6CCD` | `9A 2A 00 80 05` 그대로 유지 |
| 변경 바이트 수 | 2바이트 |
| 실행 메모리 배치 | EXE 크기, 상주 이미지, 오버레이 표와 배치 변경 없음 |
| 게임 데이터 | ENGLISH.PAK, DUNE.PAK, SCENARIO.PAK, DUNEHAN.FNT/TBL 기준 빌드와 동일 |

이 변경은 영어 피드백 조회 뒤 문자열 ID가 0일 때 그리기를 건너뛰는 조건만 제거한다. 기존 이벤트 문자열 ID 조회와 `3208:6F75` 그리기 호출을 사용한다. 이전 후보의 무조건 분기 수정은 새 빌드에 들어가지 않는다.

빌드 보고서: `build/analysis/cleanup-2026-10-24/evidence/dalmuri672-english-subtitles-feedback/english-subtitles-report.json`  
재현 스크립트: `tools/patch_dalmuri672_english_subtitles_feedback.py`  
현재 실행 배치: 루트 `듄2_한글테스트.bat`

## 확인 범위

정적으로 확인한 내용:

- 이전 후보는 영어 경로의 피드백 호출을 건너뛰며, 사용자가 그 후보에서 자막 표시를 확인했다.
- 새 후보는 영어 분기와 피드백 호출을 그대로 보존하고, 누락 자막을 건너뛰는 `JZ` 두 바이트만 NOP 처리했다.
- 실행 파일 크기와 오버레이 메타데이터, 폰트 및 게임 리소스 파일은 바뀌지 않았다.

사용자 실행 확인:

- 새 후보에서 영어 오프닝 자막이 표시된다.
- 새 후보에서 음성과 자막이 함께 정상 출력된다.
- 실행 확인 주체는 사용자다. 에이전트는 게임을 실행하지 않았다.

## 근거 파일

- REA 근거 묶음: `build/analysis/intro-subtitles/rea-evidence.json`
- 이번 피드백 경로 분석 근거: `build/analysis/intro-subtitles/audio-preserving-evidence.json`
- Ghidra 오버레이 분석 래퍼: `build/analysis/intro-subtitles/current-segment3208-analysis.exe`
- 이전 후보 보고서: `build/analysis/cleanup-2026-10-24/evidence/dalmuri672-english-subtitles/english-subtitles-report.json`
- 현재 후보 보고서: `build/analysis/cleanup-2026-10-24/evidence/dalmuri672-english-subtitles-feedback/english-subtitles-report.json`

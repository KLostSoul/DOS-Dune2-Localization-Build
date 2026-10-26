# 가문 가입 질문을 완성 문장 세 줄로 저장하는 시험

작성일: 2026-10-22. 사용자가 시험판에 대해 “정상적으로 출력된다”고 확인했다. 개별 가문·언어별 실행 범위는 별도로 명시하지 않았다.

현재 CG 편집 범위와 제외 이력, 이번 시험의 언어·가문 9조합 표, 파일 해시, PNG 채택 이후 상태를 통합한 기록은 [CG 누적 확인 결과](../verification/graphics_verification_20261022.md)에 있다.

사용자 요청대로 원본 영문 그림의 나뉜 문구를 가문별 완성 문장 세 줄로 합쳤다. **언어 선택값이 ENG일 때만** 선택한 가문의 완성 줄을 한 번 복사한다. FRE·GER 및 그 밖의 0이 아닌 선택값은 기존 두 부분 복사 경로를 사용한다. 이번 시험에서는 한글 그림을 새로 그리지 않고 원본 영문 픽셀을 그대로 재배치했다.

## 실행 파일

- 사용자 확인을 마친 기반 빌드: `build/dalmuri672-production-shortcuts`.
- 시험 빌드: `build/cg-house-question-three-lines-test`.
- 시험 실행 배치: [`듄2_가문질문_세줄테스트.bat`](../../../archives/tools/root-bat-before-cleanup-20261024.zip#듄2_가문질문_세줄테스트.bat).
- 시험 DOS 실행 파일: [`DUNE2.EXE`](../../../archives/builds/verified/cg-house-question-three-lines-test.zip#cg-house-question-three-lines-test/source/VIRGIN/DUNE2/DUNE2.EXE).
- 제작 도구: [`build_house_question_three_lines_test.py`](../../../archives/tools/legacy-tools-20261024.zip#tools/build_house_question_three_lines_test.py).
- 정적 확인 보고서: [`three-lines-report.json`](../../../archives/builds/verified/cg-house-question-three-lines-test.zip#cg-house-question-three-lines-test/three-lines-report.json).

기존 `듄2_한글테스트.bat`은 기반 빌드를 계속 실행한다. 시험 빌드는 별도 배치로 실행한다. CSV 번역, 폰트, 치트 코드에는 이번 변경을 적용하지 않았다.

## 이미지 배치

원본은 `ENGLISH.PAK/MISC.ENG`의 `(0,0,208,24)` 공통 앞부분과 `(0,24+가문번호×24,104,24)` 가문명 부분을 합쳐 표시했다. 이 두 조각을 미리 합쳐 아래처럼 저장한다. 원본 가문 번호 순서를 유지한다.

| 가문 번호 | 가문 | 새 원본 사각형 `(X,Y,W,H)` | 내용 |
|---:|---|---|---|
| 0 | 하코넨 | `(0,0,312,24)` | Do you wish to join House Harkonnen? |
| 1 | 아트레이데스 | `(0,24,312,24)` | Do you wish to join House Atreides? |
| 2 | 오르도스 | `(0,48,312,24)` | Do you wish to join House Ordos? |

한 줄의 복사 대상은 기존과 같은 화면 `(0,0)`이다. CPS 전체 크기는 320×200이고 나머지 영역은 비어 있다.

시험용 이미지: [`frame_000.png`](../../../archives/builds/verified/cg-house-question-three-lines-test.zip#cg-house-question-three-lines-test/cg/MISC.ENG/frame_000.png). 이 배치는 시험 EXE와 한 쌍이다. 사용자 정상 출력 확인 뒤 요청에 따라 [`cg/editable/images/ENGLISH/MISC.ENG/frame_000.png`](../../../import/GFX/images/ENGLISH/MISC.ENG/frame_000.png)에도 동일한 세 줄 PNG를 복사했다. 후속 한글 그림은 이 세 줄의 각 영역에 완성 문장을 넣으면 된다.

편집 프로젝트에서는 원본 비교용 `resources/ENGLISH/MISC.ENG`, `original/ENGLISH.PAK`, 매니페스트의 원본 해시를 보존했다. 인코더가 PNG의 편집을 감지하는 구조이므로 이 기준 자료까지 세 줄로 덮어쓰지 않는다. 교체한 PNG를 재인코딩하면 사용자 정상 출력 확인을 받은 시험판의 `MISC.ENG`와 전체 바이트가 일치함을 확인했다. 이번 편집 프로젝트 변경 파일은 요청한 PNG 한 개뿐이다.

## 영어에서만 실행되는 코드

기존 언어별 파일명 생성기 `044B:075D`는 `DS:[37AA]`를 인덱스로 사용한다. `DS:31CC`의 인라인 코드 표는 `ENG\0FRE\0GER\0`이고, 0이 ENG다. 시험 제작 도구는 현재 기반 EXE에서도 이 코드·표·가문 이름 대응을 검사한다.

실제 질문 코드가 든 FBOV 오버레이 모듈 206의 `3314:1398..13E6` 79바이트 안에서 다음과 같이 바꿨다.

1. `DS:[37AA] == 0`이면 앞부분 복사를 건너뛴다.
2. 두 번째 복사 자리에 ENG는 `(0,가문번호×24,0,0,39,24,2,0)`을 전달한다.
3. 나머지 언어는 원래의 앞부분 `(0,0,0,0,26,24,2,0)`과 가문명 `(0,가문번호×24+24,26,0,13,24,2,0)`을 전달한다.

위 인자의 X·폭은 8픽셀 단위다. 따라서 39는 312픽셀이다. 페이지 2에서 페이지 0으로 복사하는 기존 화면 복사 함수를 계속 호출한다.

오버레이 호출 `3314:13B3`, `3314:13DF`의 주소와 5바이트 호출 명령을 보존했다. 오버레이의 재배치·호출 표에 새 항목을 추가하지 않았다. 변경한 인자 준비에는 80186 이상에서 지원되는 `PUSH imm8`, `IMUL r16,r16,imm8`을 사용하며, 기존 시험 설정인 486에서 지원한다.

## 확인한 범위

- 현재 기반 EXE SHA-256: `021e0207cc8ef542804c4069adfbf331f3a31e9f30c6f8789a4a42bc1089260b`.
- 시험 EXE SHA-256: `935af87d7d700951e7200365b56d1e3bcb9f68cdb724fa955965b3235065405a`.
- EXE 길이 382,066바이트 및 MZ 상주 이미지 전체가 그대로다. 위 오버레이의 79바이트 구간 밖은 바이트 단위로 같다.
- 새 버퍼나 메모리 할당 호출을 추가하지 않았다. CPS 해제 픽셀은 전후 모두 64,000바이트이며 기존 화면 페이지를 사용한다. CPS 파일 크기는 3,493 → 4,558바이트로 1,065바이트 증가했다.
- Capstone으로 실제 수정 명령을 해독하고, 분기와 스택 인자를 정적으로 평가했다. ENG·FRE·GER × 가문 3개, 총 9조합을 검사했다.
- ENG 3조합은 한 번의 전체 줄 복사를 수행한다. FRE·GER 6조합은 원본과 같은 주소의 두 호출에 같은 인자를 전달한다.
- 각 언어의 실제 원본 CPS를 사용해 호출 인자대로 픽셀을 복사했다. 9조합 모두 최종 화면이 원본과 바이트 단위로 같다. 인자 스택의 최대 사용량은 모두 기존과 같은 16바이트다.
- `ENGLISH.PAK`은 `MISC.ENG` 멤버만 바뀐다. `FRENCH.PAK`, `GERMAN.PAK`과 다른 PAK는 기반 빌드와 같다.
- 게시된 시험 폴더와 기반 `source` 폴더의 파일 699개를 다시 읽어 대조했다. 차이는 `DUNE2.EXE`, `ENGLISH.PAK`, 그 PAK에서 풀어 둔 `ENGLISH.files/MISC.ENG` 세 파일뿐이다.
- CPS 재인코딩 후 다시 해제한 결과가 새 PNG와 일치한다. PAK의 멤버 순서와 나머지 멤버도 대조했다.
- 제작 도구의 임시폴더 권한이 결과에 남지 않도록, 게시한 시험 폴더는 `build`의 일반 권한을 상속하도록 처리했다. 데스크톱 파일뷰어에서 결과 PNG가 열리는 것을 확인했다.

위 9조합 결과는 정적 코드·이미지 검증이다. 에이전트가 DOSBox나 실제 DOS 게임을 실행한 결과로 기술하지 않는다. 이후 사용자가 시험판의 정상 출력을 확인했으며, 개별 가문·언어별 실행 여부는 확대해 기록하지 않는다. 새 CPS는 이미 완성 문장 세 줄이므로 기존 두 부분 코드로 읽으면 정상 질문이 나오지 않는다. 이 PNG로 재인코딩한 PAK는 영문 전용 세 줄 분기가 적용된 EXE와 함께 사용한다.

기존 원본 분석과 정확한 복사 좌표는 [가입 질문 출처 분석](house_question_source.md)에 있다. 이전 답변에서 이 기록을 놓치고 좌표가 미확인이라고 한 설명을 정정한다.

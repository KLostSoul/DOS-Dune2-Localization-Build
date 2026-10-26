# 가문 가입 질문의 실제 출처

작성일: 2026-10-21

`Do you wish to join House Atreides?`는 FNT 글자를 출력하는 문자열이 아니다. `ENGLISH.PAK` 안의 **`MISC.ENG`에 저장된 화면 그림**을 두 부분으로 복사해 표시한다. `INTRO.FNT`로 이 문구를 출력한다고 설명했던 판단을 정정한다.

이 그림은 이미 [MISC.png](../../../export/GFX/images/ENGLISH/MISC.ENG/frame_000.png)로 추출되어 있었다. 언어별 문자열 CSV와 EXE ASCII 검색에서 문장이 나오지 않은 이유는, 이 문구가 글자 코드 대신 압축된 그림 픽셀로 저장되어 있기 때문이다. FNT 추출 여부와는 별개의 문제다.

## 원본 자산

| 항목 | 확인 결과 |
|---|---|
| PAK / 내부 파일 | `ENGLISH.PAK` / `MISC.ENG` |
| 추출된 원본 | `build/source/VIRGIN/DUNE2/ENGLISH.files/MISC.ENG` |
| 파일 길이 | 3,493바이트 |
| 파일 형식 | CPS, 압축 방식 4(LCW/Format 80) |
| 해제 결과 | 320×200, 64,000바이트의 색상 인덱스 픽셀 |
| 내부 팔레트 | 없음, 헤더의 팔레트 길이 0 |
| SHA-256 | `23346ff9a97d9419c985f6e0fd75fc87eee13ab94c5e40b088f84103c78c48c3` |

원본 PAK에서 읽은 `MISC.ENG`는 추출 폴더의 파일과 전체 바이트가 같다. 원본 CPS를 다시 해제한 픽셀과 기존 `cg/language_graphics/ENGLISH/MISC.png`의 픽셀도 같다. 현재 `build/cheat-dalmuri-8x8-runtime/source/VIRGIN/DUNE2/ENGLISH.PAK`에 든 `MISC.ENG` 역시 원본과 같다.

## 원본 EXE의 읽기·표시 경로

대상 EXE SHA-256은 `99f44e83b309dd826f3dbc5068c61679bb68047eed8d738dcef594ba0eef7552`다. 아래 오버레이 주소는 FBOV의 실제 코드 기준이며, 이전 분석의 잘못된 `3208` 일괄 주소를 사용하지 않았다. 오버레이 스텁의 `INT 3F` 뒤 대상 오프셋을 읽어 실제 진입점을 확인했다.

가문 선택 함수는 실제 모듈 `3314:0FB0`, EXE 파일 위치 `0x56620`에서 시작한다.

| 위치 | 원본 코드에서 확인한 동작 |
|---|---|
| 데이터 `3342:2BFE` / 파일 `0x3AC1E` | NUL 종료 리소스 이름 `MISC` |
| `3314:137E` / 파일 `0x569EE` | `MISC` 이름의 오프셋 `2BFEh`를 전달 |
| `3314:1382` / 파일 `0x569F2` | 언어별 파일명 생성기 `044B:075D` 호출 |
| `3314:138B` / 파일 `0x569FB` | 이미지 로더 호출. 스텁 `32CD:0020` → 실제 `32CD:020F` |
| `32CD:0286` / 파일 `0x4B4C6` | CPS 경로에서 `2341:0104` 호출 |
| `2341:0104` 이후 | CPS 헤더와 데이터를 읽고 `2341:0244`에서 압축 방식에 따라 해제 |
| `3314:13B3` / 파일 `0x56A23` | 공통 질문 앞부분을 화면으로 복사 |
| `3314:13DF` / 파일 `0x56A4F` | 선택한 가문 이름과 물음표 그림을 뒤에 복사 |

두 복사 호출의 명령에는 세그먼트 피연산자 `0160h`가 들어 있다. 이는 오버레이 호출의 FBOV 표 선택값이며, 실제 대상은 **`22D5:0007`**이다. 이 래퍼가 `DS:[66C8]`의 그래픽 콜백 **`20AA:06E1`**을 호출한다. 해당 드라이버는 X 좌표를 3비트 왼쪽으로 이동하고, 행의 픽셀을 `REP MOVSW`로 복사한다. 따라서 X와 폭 인자는 8픽셀 단위다.

## 그림을 합치는 정확한 좌표

복사 인자 순서는 `(원본 X, 원본 Y, 대상 X, 대상 Y, 폭, 높이, 원본 페이지, 대상 페이지)`다. X와 폭만 8픽셀 단위이며, Y와 높이는 픽셀 단위다.

| 부분 | 원본 픽셀 사각형 `(X,Y,W,H)` | 화면 픽셀 위치 `(X,Y)` |
|---|---|---|
| `Do you wish to join House` | `(0,0,208,24)` | `(0,0)` |
| `Harkonnen?`, 가문 번호 0 | `(0,24,104,24)` | `(208,0)` |
| `Atreides?`, 가문 번호 1 | `(0,48,104,24)` | `(208,0)` |
| `Ordos?`, 가문 번호 2 | `(0,72,104,24)` | `(208,0)` |

두 번째 복사는 원본 Y를 `24 × 가문 번호 + 24`로 계산한다. 원본 EXE의 가문 테이블 `3342:37EC + 번호×30`을 따라 이름 포인터를 읽으면 번호 0/1/2가 각각 `Harkonnen`/`Atreides`/`Ordos`와 대응한다.

Atreides 선택 시 실제 인자는 다음과 같다.

```text
3314:13B3 → (0,  0,  0, 0, 26, 24, 2, 0)
3314:13DF → (0, 48, 26, 0, 13, 24, 2, 0)
```

이 좌표를 원본 CPS 픽셀에 적용한 [재구성 이미지](../../../build/analysis/house-join-prompt/original-atreides-question-3x.png):

![원본 두 복사 호출의 픽셀 재구성](../../../build/analysis/house-join-prompt/original-atreides-question-3x.png)

이 이미지는 FNT로 문장을 새로 그린 결과가 아니다. 원본 이미지의 두 영역만 복사한 결과다. `?`도 가문 이름과 같은 원본 그림 안에 있다. 이 질문 표시 블록은 문자열표 조회나 FNT 글리프 출력으로 문장을 그리지 않는다.

따라서 요청한 조합 글리프 한글 문장을 이 위치에 출력하려면, 위 질문 그림 복사 구간에 한글 텍스트 출력 경로를 연결해야 한다. ENG 문자열표만 바꾸거나 FNT 파일만 교체하는 것으로 이 그림 문구는 바뀌지 않는다. 이번 분석에서는 게임 파일이나 빌드를 수정하지 않았다.

## 재현 자료

- [정적 분석 도구](../../../archives/tools/legacy-tools-20261024.zip#tools/analyze_house_join_prompt.py)
- [바이트·해시·복사 인자 근거](../../../build/analysis/house-join-prompt/evidence.json)
- [가문 선택 함수 전체](../../../build/analysis/house-join-prompt/original-house-selection-3314.txt)
- [질문 그림 읽기와 두 복사 호출](../../../build/analysis/house-join-prompt/question-image-load-and-copy.txt)
- [복사 래퍼](../../../build/analysis/house-join-prompt/copy-wrapper-22D5.txt)
- [픽셀 복사 드라이버](../../../build/analysis/house-join-prompt/pixel-copy-driver-20AA.txt)
- [이미지 로더의 CPS 분기](../../../build/analysis/house-join-prompt/image-loader-cps-branch-32CD.txt)
- [CPS 로더와 압축 방식 분기](../../../build/analysis/house-join-prompt/cps-loader-2341.txt)

재현 명령:

```powershell
& 'C:\Users\LS\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools/analyze_house_join_prompt.py
```

게임이나 DOSBox 실행 없이 저장된 원본 파일만 읽는다. 출력은 `build/analysis/house-join-prompt`의 분석 자료와 PNG이며, 원본 EXE·PAK 및 현재 시험 빌드에는 쓰지 않는다.

## 2026-10-22 후속: 영문 완성 문장 세 줄 시험

원본의 두 조각을 가문별 완성 문장 세 줄로 미리 합치고, ENG 선택값 0에서만 해당 줄을 한 번 복사하는 별도 시험판을 만들었다. FRE·GER는 기존 두 부분 복사 인자를 유지한다. 기반 검증 빌드와 일반 실행 배치는 보존했다. 정적 언어·가문 9조합 검사를 통과한 뒤 사용자가 “정상적으로 출력된다”고 확인했다. 이어 사용자 요청으로 `cg/editable/images/ENGLISH/MISC.ENG/frame_000.png`도 검증된 세 줄 이미지로 교체했다. [시험 파일·정적 확인·사용자 확인 결과](three_row_house_question.md)를 참고한다.

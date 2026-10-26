# CG 편집과 재인코딩

`cg/editable/images`에 현재 게임 리소스의 원래 크기·팔레트를 가진 편집용 PNG를 준비했다. 기존 `cg`의 접촉 시트는 미리보기다. 이 도구는 기존 추출기의 디코더를 재사용한다.

선택한 전체 파일 목록, 제외·정리 이력, 실제 해시, 과거 143개 코덱 검증과 현재 10개 편집 목록의 구분, 가문 질문의 사용자 정상 보고는 [CG 누적 확인 결과](../verification/graphics_verification_20261022.md)에 자세히 기록했다.

현재 `DUNE.PAK`에서는 `CHOAM.CPS`, `MAPMACH.CPS`, `SCREEN.CPS`만 편집한다. `FRENCH`, `GERMAN`, `FINALE`, `MENTAT`, `INTRO`은 편집 대상에서 제외한다. 현재 편집 PAK는 DUNE과 ENGLISH 두 개다. `cg/editable/original`에는 이 두 PAK의 전체 원본만 보관하고, 재인코딩 결과도 이 두 PAK만 만든다. 각 PAK 안에서 편집하지 않은 멤버는 원본 그대로 보존한다.

## 지원 범위

| 형식 | 대상 | 리소스 수 |
|---|---|---:|
| CPS | 선택한 화면과 다른 PAK의 화면 | 7 |
| 언어별 SHP | 남아 있는 언어별 버튼·CHOAM·멘타트 스프라이트 | 3 |

현재 편집 프로젝트에는 10개 리소스와 44개 PNG가 있다. 제외한 PAK는 이 편집 프로젝트와 출력에서 제외한다. DUNE.PAK의 나머지 멤버는 전체 원본 DUNE.PAK 안에서 보존한다.

## 수정과 실행

1. `cg/editable/images`의 해당 PNG를 수정하고 같은 경로에 저장한다.
2. `CG_재인코딩.bat`을 실행한다.
3. 완료 메시지의 `build/cg-encoded-날짜-시간` 폴더에 현재 편집 목록의 PAK만 생성된다. 변경한 원본 형식 파일은 그 안의 `resources`에 있고, 검증 내역은 `encode-report.json`에 있다.
4. 사용할 게임 사본에 출력 PAK를 복사한 뒤 게임에서 확인한다.

대표 편집 경로:

- CHOAM 화면: `cg/editable/images/DUNE/CHOAM.CPS/frame_000.png`
- MAPMACH 화면: `cg/editable/images/DUNE/MAPMACH.CPS/frame_000.png`
- SCREEN 화면: `cg/editable/images/DUNE/SCREEN.CPS/frame_000.png`
- 다른 PAK의 편집 대상: 해당 PAK 이름의 하위 폴더에 있는 개별 PNG

`images/ENGLISH/MISC.ENG/frame_000.png`는 사용자 정상 출력 확인을 받은 완성 문장 세 줄 배치로 교체했다. 320×200 이미지 안에서 가문 번호 순서대로 하코넨 `(0,0,312,24)`, 아트레이데스 `(0,24,312,24)`, 오르도스 `(0,48,312,24)`를 편집한다. 이 PNG로 만든 PAK는 `build/cg-house-question-three-lines-test`의 영문 전용 세 줄 분기가 적용된 EXE와 함께 사용한다. 다른 언어는 기존 두 부분 복사를 유지한다. [코드·그림·사용자 확인 기록](three_row_house_question.md)을 참고한다.

원본 비교 자료와 매니페스트 해시는 보존했으므로 재인코더는 이 PNG를 편집된 리소스로 감지한다. 교체 직후 재인코딩한 `MISC.ENG`는 검증된 시험판과 전체 바이트가 같았다.

그림 크기·프레임 수·번호를 유지한다. 인덱스 색상 PNG로 편집하면 같은 RGB로 보이는 팔레트 슬롯도 구분된다. 투명색은 원본 인덱스를 유지하며 반투명 픽셀은 사용할 수 없다. RGB/RGBA로 저장한 경우 원래 색으로 정확히 대응 가능한 픽셀만 받아들이며, 색을 임의로 근사 변환하지 않는다. SHP·ICN은 각 프레임·타일의 원래 색상표에 들어 있는 색만 사용할 수 있다. FNT는 회색값 0, 17, 34, …, 255를 사용한다.

이미 있는 `language_graphics/ENGLISH/TITLE.png`를 편집했다면 그 파일을 위 타이틀 편집 경로로 복사할 수 있다. CHOAM 등의 축소·배치된 접촉 시트는 입력으로 사용하지 않는다.

## 원본과 메모리 보존

`manifest.json`에 활성 PAK·리소스·프레임 대응, 크기, 해시, 팔레트와 WSA 연결 정보를 보존한다. `original`과 `resources`는 편집 전 자료이므로 수정하지 않는다. 인코더는 모든 입력을 확인한 후 결과를 새 폴더로 완성한다. 이미 존재하는 출력 폴더에 덮어쓰지 않는다. 그림을 수정하지 않으면 출력 PAK가 입력 PAK와 바이트 단위로 같다. 현재 편집 목록에 없는 PAK는 스냅샷과 출력에서 제외한다.

WSA의 첫 프레임 생략, 이전 시퀀스 연결, 마지막에서 처음으로 돌아오는 루프 델타를 보존한다. 이전 시퀀스의 끝을 수정하면 연결 시퀀스의 첫 화면을 이어받아 다음 델타를 다시 계산한다. 재생 시간은 게임 코드에서 정하므로 미리보기 GIF의 프레임 간격으로 대체하지 않는다.

기본 인코딩은 WSA 작업 버퍼를 원본보다 키워야 하는 수정에 오류를 낸다. `CG_재인코딩.bat --allow-buffer-growth`를 명시하면 증가를 허용하며, 증가 바이트는 `encode-report.json`의 `buffer_growth`에서 확인한다. 이 경우 DOS 가용 메모리와 호출자가 제공하는 버퍼는 게임 실행에서 별도 확인해야 한다. SHP·FNT의 16비트 크기와 오프셋 한도도 검사한다.

원본 FNT에서 여러 글자가 같은 비트맵을 공유하는 경우 수정한 글리프의 데이터를 별도로 저장하여 다른 글자가 함께 바뀌지 않게 한다.

## 다른 게임 사본에서 추출

기본 추출원은 `듄2_한글테스트.bat`이 가리키는 게임 폴더다. `cg/editable`은 이미 준비되어 있으므로 다시 추출할 필요가 없다. 다른 사본을 편집하려면 새 프로젝트 경로를 지정한다.

```powershell
.\CG_편집용_추출.bat --game "게임 폴더" --project "cg/다른편집본"
.\CG_재인코딩.bat --project "cg/다른편집본"
```

기존 편집 프로젝트가 비어 있지 않으면 추출을 거부한다. 현재 게임 파일·실행 배치에 자동 적용하지 않으며 게임을 자동 실행하지 않는다.

## 형식 근거와 검증

기존 로컬 추출기와 OpenDUNE의 [스프라이트·CPS 로더](https://github.com/OpenDUNE/OpenDUNE/blob/master/src/sprites.c), [WSA 로더](https://github.com/OpenDUNE/OpenDUNE/blob/master/src/wsa.c), [타일 렌더러](https://github.com/OpenDUNE/OpenDUNE/blob/master/src/gfx.c)를 대조했다. 언어별 SHP도 v1.07의 프레임 수+1 DWORD 오프셋표와 마지막 오프셋을 작성한다.

`tools/check_cg_codec.py`는 편집 프로젝트 사본에서 무수정 PAK 바이트 일치, 실제 리소스별 픽셀 수정, 재인코딩 후 픽셀·크기·팔레트·투명색 일치, PAK 전체 항목 일치를 확인한다. 이 검증은 게임 실행 검증과 별개다.

2026-10-22 검증 결과: `build/cg-codec-check-20261022-165136-614030/check-report.json`. 당시 전체 143개 리소스 각각에 실제 픽셀을 수정한 사본이 모두 재인코딩 검증을 통과했다. 이후 현재 DUNE.PAK 편집 범위를 세 CPS로 좁혔다. 무수정 PAK 바이트 일치, WSA 루프 전환 효과 보존, 기본 설정의 WSA 버퍼 증가 차단과 미완성 출력 미게시, 원본 게임 PAK 해시 보존을 당시 전체 리소스 집합에서 확인했다. 게임은 실행하지 않았다. 수정 사본 테스트에서만 버퍼 증가 허용 옵션을 사용했으며 일반 실행의 기본값은 차단이다.

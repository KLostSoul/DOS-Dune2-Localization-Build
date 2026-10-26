> 분석·수정 이력입니다. 빌드명·해시와 당시의 “현재 후보”·“확인 전”은 해당 절 작성 시점의 기록입니다. 최신 실행본·적용 기능·사용자 확인은 [현재 상태](../../STATUS.md)를 따릅니다.

# Dune II 한글화용 엔진·텍스트·CG 분석

작성일: 2026-10-19  
대상 작업본: `build\source\VIRGIN\DUNE2`  
CD 이미지: `img\DUNE2CD.img` (`.ccd`, `.cue`, `.sub` 동반)

## 조사 요약

Dune II v1.07의 한글화 대상은 네 경로에 나뉘어 있다.

1. `ENGLISH.PAK`의 문자열 데이터와 Mentat 설명
2. `SCENARIO.PAK`의 지역 지도 이야기 문구
3. `DUNE2.EXE`에 포함된 표시 문자열
4. 그림 파일 자체에 래스터화된 메뉴·버튼 글자

영문 문자열과 지역 지도 문구 1,350행을 [번역 원문 CSV](../../../export/strings/source_strings_complete.csv)로 모았다. 실행 파일의 ASCII 문구 후보 86개는 [실행 파일 문자열 검토 CSV](../../../export/strings/executable_strings_review.csv)에 파일 오프셋과 함께 별도로 기록했다. 컷신·그림·스프라이트·폰트 미리보기는 [`cg`](../../GRAPHICS.md)에 있다.

이번 분석은 추출된 게임 자산과 실행 파일을 정적으로 조사했다. 원본 PAK, EXE, ISO에는 수정 사항을 쓰지 않았다. DOSBox-X 디버거로 런타임 호출 경로를 추적하지 않았으므로, 문자열이 특정 화면에서 실제로 그려지는 시점과 CD/설치본 중 어느 경로에서 읽히는지는 추가 확인이 필요하다.

## 게임 실행 파일과 자료 구조

게임 자료는 `DUNE.PAK`, `INTRO.PAK`, `MENTAT.PAK`, `SCENARIO.PAK`, `SOUND.PAK` 같은 Westwood PAK 묶음으로 배포된다. 추출본에는 15개 PAK에서 나온 파일 그룹이 있다. PAK는 파일명을 담은 목록과 데이터 블록으로 구성되고, 시나리오는 INI, 행동 스크립트는 EMC로 저장된다. 그래픽은 WSA 애니메이션, CPS 화면 그림, SHP 스프라이트, PAL 팔레트, ICN 타일셋, FNT 폰트를 사용한다. [OpenDUNE 파일 형식 개요](https://github.com/OpenDUNE/OpenDUNE/wiki/Dune-II-file-formats), [Dune II 형식 목록](https://moddingwiki.shikadi.net/wiki/Dune_II)

현재 DOSBox-X 설정은 `build\source`를 C 드라이브로 연결하고 `build\launcher`에서 시작 배치를 호출한다. 설정 파일 안에는 광학 디스크 마운트가 없다. 따라서 이 작업본에서 파일을 시험할 때는 추출된 작업 폴더를 대상으로 할 수 있다. 패치된 실물 배포용 CD 이미지를 만들 때는 별도 이미지 작성 절차가 필요할 수 있다.

이미지 안의 `DUNE2.EXE`와 `build\source\VIRGIN\DUNE2\DUNE2.EXE`는 길이가 같고 한 바이트가 다르다.

| 위치 | CD 이미지 파일 | 작업본 |
|---|---:|---:|
| 파일 오프셋 `0x4ED31` | `74` | `EB` |

이 차이의 의도는 아직 식별하지 못했다. 데이터 구성은 HitSquad 다국어 v1.07판이며, 알려진 배포 자료 해시와 대조한 기록은 [기존 분석 요약](../../BUILD.md)에 있다.

## 번역 대상 텍스트 인벤토리

CSV의 행 수는 리소스 인덱스 행 수다. 문장 중복은 합치지 않았고, 빈 항목 6개도 보존했다. 빈 인덱스는 `DUNE.ENG[0]`, `MESSAGE.ENG[0,29]`, `INTRO.ENG[0,38]`, `PROTECT.ENG[415]`다.

| 파일 | 행 수 | 기능 및 구조 |
|---|---:|---|
| `DUNE.ENG` | 340 | 명령, 메뉴, 상태, 오류, 단위·건물 관련 문자열. 16비트 오프셋표와 NUL 종료 문자열 |
| `MESSAGE.ENG` | 30 | 게임 중 알림 문자열. 오프셋표와 NUL 종료 문자열 |
| `INTRO.ENG` | 39 | 오프닝 대화 문구. 오프셋표와 NUL 종료 문자열 |
| `TEXTA.ENG` | 40 | 아트레이데스 임무·브리핑 문자열. 압축 문자열표 |
| `TEXTH.ENG` | 40 | 하코넨 임무·브리핑 문자열. 압축 문자열표 |
| `TEXTO.ENG` | 40 | 오르도스 임무·브리핑 문자열. 압축 문자열표 |
| `PROTECT.ENG` | 416 | 보호/인증 화면 문자열. 압축 문자열표 |
| `CREDITS.ENG` | 76 | 엔딩 크레딧의 비어 있지 않은 행 |
| `MENTATA.ENG` | 94 | 아트레이데스 Mentat 용어 47개 × 이름·설명 |
| `MENTATH.ENG` | 98 | 하코넨 Mentat 용어 49개 × 이름·설명 |
| `MENTATO.ENG` | 94 | 오르도스 Mentat 용어 47개 × 이름·설명 |
| `REGIONA.INI` | 15 | 아트레이데스 지역 지도 이야기 문구 (`ENGTXT`만 추출) |
| `REGIONH.INI` | 15 | 하코넨 지역 지도 이야기 문구 (`ENGTXT`만 추출) |
| `REGIONO.INI` | 13 | 오르도스 지역 지도 이야기 문구 (`ENGTXT`만 추출) |
| **합계** | **1,350** | 1,307개 언어 파일 행 + 43개 지역 지도 문구 행 |

영어 언어 PAK에서 문자열표 945행, Mentat 용어 286행, 크레딧 76행을 추출했다. 지역 지도 INI에서 영어 문구 43행을 추가했다. French/German PAK에는 비교용 번역 자료가 있으며, 이번 번역 CSV에는 영문본만 넣었다.

세 지역 INI에는 `[GROUP1]`부터 `[GROUP8]`까지 지역 정복 진행 상황용 이야기 줄이 있다. 각 문구 키는 `ENGTXT번호` 형식이다. `FRETXT`와 `GERTXT` 값은 프랑스어·독일어 문구이므로 원문 CSV에서 제외했다. 나머지 66개 `SCENA/SCENH/SCENO` INI 파일은 3가문 × 22개 임무의 게임 상태·배치 데이터이며, 화면에 표시될 문장은 언어별 TEXT 표와 지역 INI 쪽에서 관리되는 구조로 확인됐다.

## 문자열 인코딩과 한글 출력 제약

일반 ENG 문자열표는 파일 앞부분의 16비트 little-endian 오프셋 배열을 따라 문자열을 찾는다. 각 문자열은 NUL 바이트로 끝난다. 압축표는 문자열 바이트의 상위 비트를 사용해 144쌍 문자표를 참조한다. 문자표는 프로그램 안에도 ASCII 데이터로 포함돼 있다. CSV 내보내기 도구는 이 쌍 압축과 `0x1B` 확장 문자 표식을 풀어 사람이 읽을 수 있는 형태로 저장한다.

번역 시 다음 요소를 유지해야 한다.

- 기존 문자열 인덱스 순서와 Mentat 레코드 순서
- `%s`, `%d`, `%ld` 같은 포맷 지정자
- 개행, 탭, 색상/확장 문자 제어 바이트
- 한 줄·상자 폭 제한에 맞춘 줄바꿈과 문자열 길이
- 압축표의 바이트 제한과 16비트 오프셋 한도

일부 ENG 확장자 파일은 문자열표가 아니다. `AND.ENG`, `HERALD.ENG`, `MISC.ENG`, `TITLE.ENG`는 CPS 화면 이미지이고, `BTTN.ENG`, `CHOAM.ENG`, `MENTAT.ENG`는 언어별 SHP 그림 묶음이다. 파일 확장자만 보고 텍스트 파일로 취급하면 안 된다.

주요 폰트는 Westwood FNT v3의 색인형 4bpp 비트맵 폰트다. 파일에는 글리프 그림·폭·높이·Y 오프셋이 있고, 문자 인코딩/유니코드 대응표는 들어 있지 않다. 이 형식은 글리프를 최대 256 슬롯으로 다룬다. [Westwood FNT v3 형식](https://moddingwiki.shikadi.net/wiki/Westwood_Font_Format_v3)

초기 시험 변환기의 FNT 크기 헤더 누락은 수정했다. 이전 초안은 오프닝 폰트 로드 지점 `INTRO.FNT`를 메인 메뉴 경로로 오인했다. 정정된 분석에서 기본 FNT 이름은 실행 파일의 초기화 인자 `new8p.fnt`로 확인됐고 메뉴 출력 중 실제 활성 FNT도 런타임 추적에서 `NEW8P.FNT`로 확인됐다. 메인 메뉴 오버레이는 별도로 `NEW6P.FNT`를 보조 슬롯에 적재하며, 오프닝 오버레이는 `INTRO.FNT`를 적재한다. 공통 FNT 로더·전환·폭 계산·글리프 출력 경로와 전체 직접 호출 목록은 [원본 FNT 텍스트 엔진 역분석](font_engine.md)에 정리했다. 과거 슬롯 시험의 팔레트 수치는 [메뉴 폰트 오류 분석](../ui/menu_glyph_corruption.md)을 참고하되 최신 조합 FNT 후크의 색상 증거로 사용하지 않는다.

| 폰트 | 글리프 슬롯 수 | 최대 글리프 크기 |
|---|---:|---:|
| `NEW6P.FNT` | 226 | 8×8 |
| `NEW8P.FNT` | 226 | 10×11 |
| `NEW10P.FNT` | 160 | 10×9 |
| `STD3P.FNT` | 126 | 5×4 |
| `INTRO.FNT` | 174 | 17×17 |

과거에 조사한 `unifont-16.0.04-6x2x10.fnt` 후보는 14,208바이트이며, 16×16 1bpp 비트맵 444개를 연속 저장했다. 레코드는 행당 16비트, MSB가 왼쪽 픽셀이다. 6개 초성 변형은 20레코드 간격으로 배치되어 있고 각 묶음에 현대 초성 19개가 있다. 중성 21개는 121번과 143번부터 두 변형으로 저장되어 있다. 종성 표는 164번부터 28레코드씩 10개 변형으로 배치되며, 각 묶음의 첫 레코드는 종성이 없는 빈 글리프다. 이 시험 후보는 현재 사용하지 않아 폰트 폴더 정리 때 제거했다.

시험용 `가`는 제공된 조합 표에서 세로 모음 ㅏ·받침 없음에 해당하는 초성 변형 0의 ㄱ(레코드 1), 중성 변형 0의 ㅏ(레코드 121), 빈 종성(레코드 164)을 OR 결합한다. 과거 시험 도구는 완성 글리프 하나를 PNG로 저장하고 원본 16×16 픽셀을 16배 최근접 확대했다. 이 조합 폰트 후보와 미리보기는 현재 빌드에서 사용하지 않아 폰트 폴더 정리 때 제거했다.

입력 조합 표는 수정하지 않았고, 게임 폰트·문자열·PAK/CD 이미지도 수정하지 않았다.

## 실행 파일 내장 문자열

`DUNE2.EXE`는 주 텍스트 파일 외에도 사람이 읽을 수 있는 ASCII 후보를 포함한다. 스캐너가 86개 후보를 찾았고 오프셋을 기록했다. 예를 들면 승리 조건 설명(`Only friendly units remain`, `Spice quota reached`), 총 지역 수, 오류 문구, 일부 단위·건물 이름이 있다. 이 목록에는 실제 표시 문자열과 진단용·개발용 문자열이 함께 있을 수 있다. CSV의 오프셋은 DOS 메모리 주소가 아니라 EXE 파일 안의 바이트 위치이며, 실제 화면에서 사용되는지는 아직 디버거로 확인하지 않았다.

영문·프랑스어·독일어 런타임 문자열 파일 이름들이 EXE 안에서 확인된다. 따라서 파일 참조만으로 동적 자막 표시를 증명할 수는 없다. `INTRO.ENG`에는 영어 오프닝 대사 39개가 있지만, 사용자가 실행 중 확인한 오프닝 화면에는 자막이 나오지 않았다. 자막 그리기 루틴의 호출, 대사와 WSA/VOC의 시간 동기화, 자막 설정 비트가 있는지는 런타임 추적 대상이다. 문자열 편집만으로 자막이 화면에 나타난다고 단정할 수 없다.

## 화면 그림에 포함된 번역 대상

후속 정적 역분석에서 가문 가입 질문 `Do you wish to join House Atreides?`도 `ENGLISH.PAK`의 `MISC.ENG` CPS 그림임을 확인했다. 공통 앞부분과 가문 이름·물음표 영역을 두 번의 화면 복사로 합친다. 이 질문을 `INTRO.FNT`로 출력한다고 한 설명은 잘못이다. 원본 그림은 [`export/GFX/images/ENGLISH/MISC.ENG/frame_000.png`](../../../export/GFX/images/ENGLISH/MISC.ENG/frame_000.png), 편집 그림은 [`import/GFX/images/ENGLISH/MISC.ENG/frame_000.png`](../../../import/GFX/images/ENGLISH/MISC.ENG/frame_000.png)이며, 정확한 원본 코드 주소와 픽셀 좌표는 [가문 가입 질문의 출처 역분석](../../GRAPHICS.md)에 기록했다.

언어별 ENGLISH/FRENCH/GERMAN 리소스를 비교했다. 영어 SHP 미리보기에서 `MENTAT`, `OPTIONS`, `CREDITS`, `UPGRADE`, `SEND ORDER`, `BUILD THIS`, `RESUME GAME`, `INVOICE`, `YES`, `NO`, `EXIT`, `PROCEED`, `REPEAT` 같은 글자가 그림으로 저장된 것을 확인했다. 한국어판에서는 이 그림을 다시 그리거나, 실행 중 문자열로 렌더링하도록 코드·리소스 구조를 바꿔야 한다.

일반 그래픽 형식의 역할은 다음과 같다. WSA는 이전 프레임에 XOR 델타를 적용해 다음 장면을 만드는 애니메이션이며, CPS는 320×200 인덱스 색상 화면, SHP는 크기가 제각각인 투명 스프라이트 프레임 모음이다. WSA 일부는 처음 프레임을 포함하지 않고 앞선 WSA 시퀀스의 마지막 프레임을 이어받는다. 이런 체인은 추출기에서 이어 붙였다. [WSA 형식](https://moddingwiki.shikadi.net/wiki/Westwood_WSA_Format), [CPS 형식](https://moddingwiki.shikadi.net/wiki/Westwood_CPS_Format), [Dune II SHP 형식](https://moddingwiki.shikadi.net/wiki/Westwood_SHP_Format_%28Dune_II%29)

## CG·그래픽 추출 결과

추출 도구는 `build\source\VIRGIN\DUNE2`를 읽어 `cg`에 PNG/GIF 미리보기를 만들었다. 원본 PAK 내부 파일은 수정하지 않았다.

| 출력 | 결과 | 확인 용도 |
|---|---:|---|
| WSA 애니메이션 | 75 시퀀스 | 오프닝, 엔딩, Mentat/게임 애니메이션. 프레임 PNG와 GIF |
| CPS 화면 그림 | 27개 | 오프닝·엔딩 배경 및 언어별 정지 그림 |
| SHP 스프라이트 접촉 시트 | 26개 | 유닛·건물·아이콘 프레임 묶음 |
| 언어별 SHP 표 | 9개 | BTTN/CHOAM/MENTAT × 3개 언어 |
| FNT 글리프 아틀라스 | 5개 | 폰트 글리프 인덱스와 그림 |
| 추출 오류 | 0개 | 실행 파일 및 그래픽 파서 출력 |

WSA 체인으로 이어 붙인 파일은 `INTRO7B ← INTRO7A`, `INTRO8B ← INTRO8A`, `INTRO8C ← INTRO8B`, `HFINALC ← HFINALB`, `OFINALB ← OFINALA`, `OFINALC ← OFINALB`다. WSA 파일에 재생 시간은 들어 있지 않아서 GIF 간격은 컷신 70ms, 게임 애니메이션 100ms로 미리보기용 지정값을 사용했다. 따라서 GIF 속도는 게임과 같다고 볼 수 없다.

전체 추출 미리보기와 접촉 시트는 편집 입력에서 제외되어 정리했다. 편집에 보존한 그림 목록은 [CG 편집 범위](../../GRAPHICS.md#선택한-편집-범위-리소스-10개png-44개)에 기록했다. 현재 선택 CG 추출·인코딩 명령은 `python tools/edit_cg.py export`와 `python tools/edit_cg.py encode`다. 공용 그래픽 디코더는 `tools/cg_codec.py`에 통합했으며, 전체 게임 미리보기·접촉 시트를 만드는 별도 실행기는 정리했다.

`ICON.ICN`/`ICON.MAP` 타일셋은 원본 추출 폴더에 남아 있으나 이 미리보기 도구가 타일셋 렌더링을 구현하지 않아 접촉 시트에는 포함하지 않았다. 타일셋은 지형·구조물 지도 그림용이고, 현재 확인한 번역 문구는 CPS/SHP 언어 리소스에 집중되어 있다.

## 도구와 산출물

- [문자열·EXE 후보 내보내기](../../../tools/resources.py): `strings`·`exe` 명령
- [선택 CG 추출·인코딩](../../../tools/edit_cg.py) / [공용 CG 코덱](../../../tools/cg_codec.py)
- [번역 원문 CSV](../../../export/strings/source_strings_complete.csv)
- [EXE 검토 CSV](../../../export/strings/executable_strings_review.csv)
- [선택 CG 편집 안내](../../GRAPHICS.md)
- [기존 버전·패치·DOSBox-X 설정 요약](../../BUILD.md)

번역 파일을 실제 게임에 넣기 위해서는 ENG 테이블 작성기, CPS/SHP 재패커, 한글 폰트/코드 처리, EXE 내장 문자열 위치별 처리, 오프닝 자막 출력 시점 확인이 남아 있다. CD 실행 경로를 유지해 배포하려면 게임이 어느 파일을 열어 읽는지 DOSBox-X 로그/디버거로 확인한 뒤, 이미지 재작성 또는 파일 오버레이 방식을 정하면 된다.

## 참고 형식 문서

- [OpenDUNE: Dune II 파일 형식과 PAK/그래픽/시나리오 개요](https://github.com/OpenDUNE/OpenDUNE/wiki/Dune-II-file-formats)
- [ModdingWiki: WSA](https://moddingwiki.shikadi.net/wiki/Westwood_WSA_Format)
- [ModdingWiki: CPS](https://moddingwiki.shikadi.net/wiki/Westwood_CPS_Format)
- [ModdingWiki: Dune II SHP](https://moddingwiki.shikadi.net/wiki/Westwood_SHP_Format_%28Dune_II%29)
- [ModdingWiki: Westwood FNT v3](https://moddingwiki.shikadi.net/wiki/Westwood_Font_Format_v3)
- [ModdingWiki: Dune II 형식 개요](https://moddingwiki.shikadi.net/wiki/Dune_II)

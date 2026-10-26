# 듄 II 한글화 작업 분석 요약

## 최신 기준점 — 2026-10-22

[현재 빌드·누적 확인 결과](../verification/build_verification_20261022.md)에 실행 대상, 파일 해시, 폰트·간격·테두리·가문 이름·단축키 수정, 사용자 정상 작동 보고를 정리했다. 현재 실행 대상은 `build/dalmuri672-english-subtitles-feedback`이며, 영어 피드백 조회 호출을 보존하면서 자막 생략 조건만 정적으로 수정했다. 아래 초기 분석 내용은 당시 상태의 이력이다.

추가로 `build/cg-house-question-three-lines-test`의 영문 전용 가문 질문 세 줄 표시를 사용자가 “정상적으로 출력된다”고 확인했다. 편집용 `MISC.ENG` PNG도 해당 배치로 채택했다. 이 CG 시험 빌드는 현재 기본 실행 대상과 별도다. 현재 CG 편집 범위 10개 리소스·44개 PNG, 원본 PAK 정리, 코덱 검증, BTTN·SCREEN 비교, 영문 전용 코드와 9조합 정적 검사, 사용자 확인은 [CG 누적 확인 결과](../verification/graphics_verification_20261022.md)에 모았다.

텍스트 리소스·실행 파일 문구·폰트·CG 추출을 정리한 전체 분석은 [Dune II 엔진·텍스트·CG 분석](engine_text_graphics.md)을 참고한다.

한글 번역 후 `Attack`의 A 및 `Move`의 M 명령 단축키가 사라지는 원인과 보존 방향은 [한글 명령 단축키 중단 원인](../ui/translated_shortcuts.md)에 기록했다.

## 확인 범위와 현재 상태

- 작업 폴더: `G:\Codex\DOS\DOS-Dune2-Localization-Build`
- 기존 CD 이미지, 패치 압축 파일, DOSBox-X 실행 설정을 읽기 전용으로 확인했다.
- 초기 분석은 패치와 ISO/실행 파일/DOSBox-X 설정을 바꾸지 않고 진행했다. 이후 오프닝 영어 자막의 생략 분기만 수정한 현재 빌드 정보는 아래 분석과 현재 빌드 문서에 기록했다.
- 실행 파일에서 영어 자막이 피드백 항목의 문자열 ID가 0일 때 생략되는 것을 특정했다. 현재 후보는 `3208:6CC0` 언어 분기와 `3208:6CCD` 피드백 호출을 유지하며 `3208:6CE2`의 생략 점프만 NOP 처리한다. `듄2_한글테스트.bat`은 현재 후보를 실행한다. 사용자가 이 빌드에서 자막과 음성이 함께 정상 출력되는 것을 확인했다. 주소·바이트·정적 분석 범위와 사용자 확인은 [오프닝 영어 자막 정적 분석](english_subtitles.md)에 기록했다.

## 게임 버전과 CD 이미지

`img\DUNE2CD.ccd`, `img\DUNE2CD.cue`, `img\DUNE2CD.img`, `img\DUNE2CD.sub`가 CloneCD 이미지 세트다. 디스크 안의 언어 데이터와 설치 파일 구성은 HitSquad의 다국어판에 해당한다. HitSquad 1.07 데이터 해시를 정리한 [Debian game-data-packager 매니페스트](https://sources.debian.org/src/game-data-packager/73/data/dune2.yaml/)와도 일치한다.

이미지의 `DUNE2.EXE`와 작업본 `build\source\VIRGIN\DUNE2\DUNE2.EXE`는 크기가 같고, 비교에서 한 바이트만 달랐다.

- 오프셋: `0x4ED31`
- CD 이미지: `74`
- 작업본: `EB`

따라서 이미지가 완전히 다른 게임 버전이라고 볼 근거는 없다. 이 한 바이트가 왜 변경됐는지는 아직 밝혀지지 않았다.

## `patch` 폴더의 파일

### `Dune_2_The_Building_of_a_Dynasty_eng_patches.rar`

압축 안에는 MrFlibble의 비공식 v1.07 수정 파일과 설명서(`dune2eng\V107UPG\DUNE2FIX.TXT`)가 있다. `V107UPG` 아래에 `ARRAKIS`, `DYNASTY`, `HITSQUAD`별 파일이 나뉘어 있으며, 현재 확인된 HitSquad판에는 `HITSQUAD` 버전이 대응한다.

설명서에는 게임 v1.0에 바로 적용하지 말고 먼저 공식 v1.07로 갱신하라고 적혀 있다. 이 패키지는 게임 버전에 맞춘 수정 파일 묶음이다. 주요 내용은 AI 공격 팀 오류, 일부 미션 데이터, 사운드 잡음과 설정 프로그램 수정 등이다. 별도로 다음 파일도 들어 있다.

- `SFX-FIX`: 일부 효과음의 클릭 잡음 수정
- `GUS-FIX`: Gravis Ultrasound용 선택 패치. GUS 드라이버 설정이 필요한 경우에만 사용

포럼의 [Dune 2 v1.07 Fix 글](https://forum.dune2k.com/topic/20168-dune-2-v107-fix/)은 MrFlibble 패치와 판본별 파일을 안내한다. 후속 글에서는 사운드와 게임 버그 수정이 통합됐고, 2010년 추가 업데이트가 있었다고 설명한다. 현재 RAR의 설명서와 구성은 이 패치 계열과 겹친다. 포럼 파일과 로컬 압축 파일의 바이트 단위 동일성까지 확인한 것은 아니지만, 같은 핵심 패치를 다시 받을 필요는 없어 보인다.

## 오프닝 음성·자막

이 절의 초기 웹 자료 검토는 실행 파일의 자막 출력 분기를 분석하기 전 상태의 기록이다. 후속 REA/Ghidra 정적 분석으로 영어만 음성 피드백 표를 검사하고 유효하지 않은 ID에서 생략되는 것을 확인했다. `3208:6CC0`의 `75 44`를 `EB 44`로 바꾼 새 빌드는 영어도 기존 일반 문자열 조회·그리기 경로를 사용한다. 실제 화면에서의 출력은 사용자가 확인해야 한다. 상세 주소·바이트 비교·확인 한계는 [오프닝 영어 자막 정적 분석](english_subtitles.md)에 기록했다.

## DOSBox-X 실행 및 소리 설정

`듄2_실행.bat`은 `C:\DOSBox-X\dosbox-x.exe`를 다음 설정으로 실행한다.

```bat
-conf "dosbox-x-dune2.conf" -fastlaunch -exit
```

`dosbox-x-dune2.conf`는 C 드라이브에 `build\source`, D 드라이브에 `build\launcher`를 연결하고 `D:\D2START.BAT`을 호출한다. 사운드는 Sound Blaster Pro 2, `A220 I7 D1 H5` 설정이다. `듄2_소리설정.bat`은 별도 설정 파일로 DOSBox-X를 열어 게임의 `SETUP.EXE`를 실행한다.

설정 파일에는 `nosound=false`, Sound Blaster 설정, `BLASTER=A220 I7 D1 H5 T3`가 지정돼 있다. 실제 게임에서 소리가 정상 출력되는지까지는 이 파일 확인만으로 검증되지 않았다.

## 마우스 헬퍼

`Dune_2_The_Building_of_a_Dynasty_Mouse_Helper.rar`에는 `Dune2_MH_2_0.exe`와 AutoHotkey 소스가 있다. 게임 파일을 바꾸는 패치가 아니라 Windows에서 마우스 입력을 게임 키 입력으로 바꾸는 보조 프로그램이다. 압축을 푼 뒤 EXE를 실행하면 트레이에 상주하며, 게임 창이 활성화됐을 때 동작한다.

소스에 적힌 조작은 다음과 같다.

| 입력 | 동작 |
|---|---|
| 우클릭 | `M` 이동 명령 후 클릭 |
| 가운데 클릭 | 공격·수확 명령을 보내고 클릭 |
| 마우스 휠 | 지도 스크롤 |
| `Shift` + 세로 휠 | 좌우 지도 스크롤 |
| 마우스 측면 버튼 | 좌우 지도 스크롤 |
| `Z` / `X` | 여러 유닛에 이동 / 공격 명령 반복 |
| `F10` | 도움말 표시 |
| `Pause` | 헬퍼 단축키 일시 중지/재개 |
| `Shift+F11` | WASD 지도 스크롤 켜기/끄기 |

헬퍼 v2.0은 DOSBox 계열 실행 파일 창 중 제목에 `DUNE2`, `SUPER`, `SVN-lfn`, `DUNEX`가 포함된 창을 찾도록 되어 있다. 현재 `dosbox-x-dune2.conf`의 제목은 `Dune II - Korean Localization Workspace`라서 이 조건에 맞지 않는다. 실행 파일명 `dosbox-x.exe`는 DOSBox 프로세스 조건에 맞지만, 현재 창 제목 그대로라면 헬퍼가 게임을 감지하지 못할 수 있다. 제목을 `DUNE2 - Korean Localization Workspace`처럼 바꾸거나 헬퍼의 제목 검색 문자열을 조정해야 한다. 아직 어느 쪽도 변경하지 않았다.

## 관련 로컬 파일

- 실행: `듄2_실행.bat`
- 소리 설정 실행: `듄2_소리설정.bat`
- 영어 설정 복원: `듄2_영어언어복원.bat` — `DUNE.CFG.before-subtitles`를 `DUNE.CFG`로 복사하는 스크립트
- 게임 설정: `dosbox-x-dune2.conf`, `dosbox-x-dune2-audio-setup.conf`
- 패치 압축 파일: `patch\Dune_2_The_Building_of_a_Dynasty_eng_patches.rar`, `patch\Dune_2_The_Building_of_a_Dynasty_Mouse_Helper.rar`

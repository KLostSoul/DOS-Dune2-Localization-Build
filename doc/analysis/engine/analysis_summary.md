# 게임 엔진과 한글 패치 구조

듄 II는 DOS MZ 실행 파일과 FBOV 오버레이, PAK 리소스로 구성된다. 한글 패치는 원본의 문자열 조회·서식·줄바꿈·픽셀 출력 경로에 글리프 선택과 토큰 처리를 연결한다.

## 리소스와 출력

- `DUNE.PAK`에는 공통 게임 자료와 원본 FNT가 있다.
- `ENGLISH.PAK`에는 영어 문자열·멘타트·언어 UI 그림이 있다.
- `SCENARIO.PAK`의 REGION INI에는 임무 선택 지도 문구가 있다.
- 그림 안의 글자는 PNG 편집과 CG 인코딩으로 반영한다.

세부 형식은 [텍스트·CG 엔진](engine_text_graphics.md), 함수 계약은 [FNT 엔진](font_engine.md), 실행 시 폰트 선택은 [화면별 관측](font_runtime_debug.md)에 설명한다.

## 한글 처리

일반 게임은 달무리 8×8, 영상 자막은 Unifont 16×16을 사용한다. 완성 음절과 부호 토큰은 번역을 인코딩하는 빌드에서 지정한다. 글꼴 파일 생성과 MZ/XMS 배치는 [폰트 안내](../../FONTS.md)를 따른다.

## 게임 기능 패치

[영어 자막과 음성](english_subtitles.md), [하코넨 마지막 자막](harkonnen_final_caption.md), [오르도스 마지막 자막](ordos_final_caption.md), [보안 질문과 임무 전환](security_briefing_transition.md)은 각각 대상 코드 경로를 제한한다. 치트 입력·화면·메모리는 [치트 설계](../cheats/cheat_input_design.md)에 설명한다.

현재 생성 명령·산출물 위치는 [빌드 안내](../../BUILD.md), 적용 기능과 해시는 [상태 문서](../../STATUS.md)를 따른다.

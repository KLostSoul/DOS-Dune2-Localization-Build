# 문서 목차

빌드·번역·CG 편집과 패치 적용 방법을 안내한다.

## 최종 빌드 안내

| 문서 | 내용 |
|---|---|
| [STATUS.md](STATUS.md) | 현재 산출물·해시·적용 기능·확인 결과 |
| [BUILD.md](BUILD.md) | 빌드 환경·원본 입력·생성 과정·HitSquad Fix·검사 |
| [FONTS.md](FONTS.md) | 영구 음절표·완성 FNT 1회 생성·2바이트 토큰·MZ/XMS |
| [GRAPHICS.md](GRAPHICS.md) | 선택 CG·PNG 인코딩·팔레트·가문 질문 행 |
| [RUNTIME.md](RUNTIME.md) | 치트·단축키·스타일·간격·임무 전환·영상 수정 |
| [PATCHING.md](PATCHING.md) | 원본 IMG에 Xdelta 적용·BIN/CUE 사용 |
| [README.md](README.md) | 현재 안내와 원본 분석 기록의 위치 |

구현 파일별 명령은 [tools/README.md](../tools/README.md)에 있다.

## 원본 분석 기록

`analysis/`는 원본 코드와 패치의 동작을 설명한다. 함수 주소·명령·메모리 계약과 관측 표본을 기능별로 정리한다. 표본의 주소와 수치는 분석 대상에 한정되며 최종 빌드의 크기·해시는 [STATUS](STATUS.md)를 따른다.

### 엔진·출력·영상·임무 전환

| 기록 | 분석 내용 |
|---|---|
| [analysis_summary.md](analysis/engine/analysis_summary.md) | 게임 엔진과 한글 패치 구조 |
| [engine_text_graphics.md](analysis/engine/engine_text_graphics.md) | 실행 파일·문자열·CG의 리소스 구조 |
| [english_subtitles.md](analysis/engine/english_subtitles.md) | 영어 자막과 음성의 출력 분기 |
| [font_engine.md](analysis/engine/font_engine.md) | 원본 FNT 엔진의 조회·배치·픽셀 출력 계약 |
| [font_runtime_debug.md](analysis/engine/font_runtime_debug.md) | 화면별 원본 폰트 선택과 실행 주소 판독 |
| [harkonnen_final_caption.md](analysis/engine/harkonnen_final_caption.md) | 하코넨 두 번째 영상의 마지막 자막과 입 애니메이션 |
| [house_description_freeze.md](analysis/engine/house_description_freeze.md) | 설명문 분할과 포인터 진행 조건 |
| [mentat_info_length.md](analysis/engine/mentat_info_length.md) | 멘타트 INFO의 읽기 길이와 버퍼 경계 |
| [native_output_rebuild.md](analysis/engine/native_output_rebuild.md) | 멘타트 리소스와 원본 출력 인터페이스 |
| [ordos_final_caption.md](analysis/engine/ordos_final_caption.md) | 오르도스 두 번째 영상의 마지막 자막과 입 애니메이션 |
| [original_dalmoori_output.md](analysis/engine/original_dalmoori_output.md) | 원본 출력기와 한글 토큰 처리의 인터페이스 비교 |
| [security_briefing_reanalysis.md](analysis/engine/security_briefing_reanalysis.md) | 보안 질문 종료에서 임무 설명으로 이어지는 상태 경로 |
| [security_briefing_transition.md](analysis/engine/security_briefing_transition.md) | 보안 질문 생략과 임무 설명의 전환 구조 |
| [security_gray_panel_delay.md](analysis/engine/security_gray_panel_delay.md) | 보안 질문 생략 시 화면 준비와 대기의 경계 |
| [security_mz_fbov.md](analysis/engine/security_mz_fbov.md) | DOS MZ와 FBOV의 주소·게이트 판독 |

### 치트·입력·메모리

| 기록 | 분석 내용 |
|---|---|
| [cheat_input_design.md](analysis/cheats/cheat_input_design.md) | 게임 내 치트 입력과 명령 처리 |
| [cheat_input_rewrite.md](analysis/cheats/cheat_input_rewrite.md) | 치트 입력 소유권과 Enter 전달 |
| [cheat_memory_layout.md](analysis/cheats/cheat_memory_layout.md) | 폰트·치트의 상주 배치와 DOS 힙 확장 |
| [cheat_modal_wait.md](analysis/cheats/cheat_modal_wait.md) | 치트창의 모달 대기와 화면 복원 |
| [cheat_panel_redraw.md](analysis/cheats/cheat_panel_redraw.md) | 전장 화면 복사와 치트 패널의 소실 원인 |

### 폰트 설계·출력·메모리

| 기록 | 분석 내용 |
|---|---|
| [completed_syllable_fnt_test.md](analysis/fonts/completed_syllable_fnt_test.md) | 조합 글리프와 완성 음절의 대조 방법 |
| [composed_hangul_fnt.md](analysis/fonts/composed_hangul_fnt.md) | 조합형 한글 FNT의 데이터와 토큰 계약 |
| [dalmoori639_verified_rebuild.md](analysis/fonts/dalmoori639_verified_rebuild.md) | 달무리 폭 콜백과 문자열 포인터 계약 |
| [dalmoori_8x8_test.md](analysis/fonts/dalmoori_8x8_test.md) | 달무리 8×8 완성 음절의 저장과 출력 셀 |
| [dalmoori_latin_symbols.md](analysis/fonts/dalmoori_latin_symbols.md) | 달무리 영문·숫자·부호의 출력 선택 |
| [dalmoori_symbols.md](analysis/fonts/dalmoori_symbols.md) | 달무리 부호의 래스터화와 FNT 레코드 |
| [font_memory_lifecycle.md](analysis/fonts/font_memory_lifecycle.md) | 원본 폰트의 할당·해제·선택 계약 |
| [hangul_16x16_design.md](analysis/fonts/hangul_16x16_design.md) | 16×16 한글 출력에 필요한 셀·레이아웃 규약 |
| [unifont_cinematics.md](analysis/fonts/unifont_cinematics.md) | 영상 자막의 Unifont FNT와 XMS 출력 |

### 메뉴·단축키·간격·테두리

| 기록 | 분석 내용 |
|---|---|
| [embedded_house_names.md](analysis/ui/embedded_house_names.md) | 가문 식별자와 한글 표시 이름의 분리 |
| [font_edges.md](analysis/ui/font_edges.md) | 원본 스타일을 따르는 글리프 가장자리 |
| [game_menu_text_position.md](analysis/ui/game_menu_text_position.md) | 게임 메뉴 버튼 텍스트의 Y좌표 |
| [mentat_topic_spacing.md](analysis/ui/mentat_topic_spacing.md) | 멘타트 목록의 기준점과 행 간격 |
| [menu_edge_test.md](analysis/ui/menu_edge_test.md) | 원본 스타일과 정보창 줄 간격의 검사 기준 |
| [menu_glyph_corruption.md](analysis/ui/menu_glyph_corruption.md) | 메뉴 글리프 손상의 좌표·폭·슬롯 원인 |
| [menu_hooks.md](analysis/ui/menu_hooks.md) | 원본 메뉴의 문자열·폭·채우기 경계 |
| [mission_map_first_syllable.md](analysis/ui/mission_map_first_syllable.md) | 임무 지도 INI 파서의 고위 바이트 판정 |
| [mission_map_text_spacing.md](analysis/ui/mission_map_text_spacing.md) | 임무 지도 설명의 가로 간격 |
| [top_message_spacing.md](analysis/ui/top_message_spacing.md) | 게임 상단 메시지의 가로 간격과 Y좌표 |
| [translated_shortcuts.md](analysis/ui/translated_shortcuts.md) | 한글 명령의 단축키 판독과 원본 입력 경로 |

### CG 형식·가문 질문

| 기록 | 분석 내용 |
|---|---|
| [graphics_codec.md](analysis/graphics/graphics_codec.md) | CG 추출·편집·재인코딩 구조 |
| [herald_palette_repair.md](analysis/graphics/herald_palette_repair.md) | HERALD.ENG의 팔레트 색 번호 |
| [house_question_row_order.md](analysis/graphics/house_question_row_order.md) | 가문 가입 질문의 행 선택 |
| [house_question_source.md](analysis/graphics/house_question_source.md) | 가문 가입 질문의 CPS와 원본 복사 함수 |
| [mentat_transparency_repair.md](analysis/graphics/mentat_transparency_repair.md) | MENTAT.ENG 버튼의 투명색 메타데이터 |
| [three_row_house_question.md](analysis/graphics/three_row_house_question.md) | 완성 문장 세 줄로 저장하는 가문 질문 |

### 원본 리소스

| 기록 | 분석 내용 |
|---|---|
| [english_resource_languages.md](analysis/resources/english_resource_languages.md) | 영어 리소스에 포함된 독일어 문구 |

### 검수 방법과 범위

| 기록 | 분석 내용 |
|---|---|
| [build_validation.md](analysis/verification/build_validation.md) | 최종 빌드의 검수 범위 |
| [graphics_validation.md](analysis/verification/graphics_validation.md) | CG 코덱과 가문 질문의 검수 범위 |

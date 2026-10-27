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

`analysis/`는 원본 코드의 역분석과 실행 관측 기록이다. 주소·해시·빌드명은 각 기록의 분석 대상을 가리킨다. 현재 적용 상태는 [STATUS](STATUS.md)를 따른다.

### 엔진·출력·영상·임무 전환

| 기록 | 분석 내용 |
|---|---|
| [analysis_summary.md](analysis/engine/analysis_summary.md) | 듄 II 한글화 작업 분석 요약 |
| [engine_text_graphics.md](analysis/engine/engine_text_graphics.md) | Dune II 한글화용 엔진·텍스트·CG 분석 |
| [english_subtitles.md](analysis/engine/english_subtitles.md) | 오프닝 영어 자막과 음성 경로 정적 분석 |
| [font_engine.md](analysis/engine/font_engine.md) | Dune II 원본 FNT 텍스트 엔진 정적 역분석 |
| [font_runtime_debug.md](analysis/engine/font_runtime_debug.md) | Dune II 원본 FNT 화면별 디버그 검증 |
| [harkonnen_final_caption.md](analysis/engine/harkonnen_final_caption.md) | 하코넨 두 번째 황제 영상의 마지막 자막과 입 애니메이션 |
| [house_description_freeze.md](analysis/engine/house_description_freeze.md) | 가문 선택 이후 멈춤 정적 분석 |
| [mentat_info_length.md](analysis/engine/mentat_info_length.md) | 멘타트 하코넨 설명의 INFO 길이 오류 |
| [native_output_rebuild.md](analysis/engine/native_output_rebuild.md) | 원본 출력 구조를 보존한 달무리 639음절 재작성 |
| [ordos_final_caption.md](analysis/engine/ordos_final_caption.md) | 오르도스 두 번째 황제 영상의 마지막 308번 자막 |
| [original_dalmoori_output.md](analysis/engine/original_dalmoori_output.md) | 원본과 달무리 639음절 수정판의 출력 경로 대조 |
| [security_briefing_reanalysis.md](analysis/engine/security_briefing_reanalysis.md) | 보안 질문 정상 종료에서 임무 설명까지의 실제 연결 |
| [security_briefing_transition.md](analysis/engine/security_briefing_transition.md) | 보안 질문과 임무 설명 전환 |
| [security_gray_panel_delay.md](analysis/engine/security_gray_panel_delay.md) | 보안 질문 생략 후보에 남은 화면 전환과 대기 |
| [security_mz_fbov.md](analysis/engine/security_mz_fbov.md) | 보안 질문 경로와 DOS MZ 분석 범위 |

### 치트·입력·메모리

| 기록 | 분석 내용 |
|---|---|
| [cheat_input_design.md](analysis/cheats/cheat_input_design.md) | Dune II 게임 내 치트 문자열 입력 설계 |
| [cheat_input_rewrite.md](analysis/cheats/cheat_input_rewrite.md) | 치트 입력 변경 철회와 재작성 (2026-10-21) |
| [cheat_memory_layout.md](analysis/cheats/cheat_memory_layout.md) | 치트 추가 후 메모리 오류: 원본·한글 전용·치트 빌드 정적 대조 |
| [cheat_modal_wait.md](analysis/cheats/cheat_modal_wait.md) | 치트창 소실 수정 — 게임 루프 대기 방식 (2026-10-21) |
| [cheat_panel_redraw.md](analysis/cheats/cheat_panel_redraw.md) | Dune II 치트창 소실 원인: 원본 화면 갱신과 후크 대조 |

### 폰트 설계·출력·메모리

| 기록 | 분석 내용 |
|---|---|
| [completed_syllable_fnt_test.md](analysis/fonts/completed_syllable_fnt_test.md) | Dune II 한글 조합 FNT 비교 상태 |
| [composed_hangul_fnt.md](analysis/fonts/composed_hangul_fnt.md) | Dune II 한글 조합 FNT 메뉴 시험 준비 |
| [dalmoori639_verified_rebuild.md](analysis/fonts/dalmoori639_verified_rebuild.md) | 달무리 639음절 빌드 재작성 |
| [dalmoori_8x8_test.md](analysis/fonts/dalmoori_8x8_test.md) | Dune II 달무리 완성형 8×8 시험 |
| [dalmoori_latin_symbols.md](analysis/fonts/dalmoori_latin_symbols.md) | 한글 번역문에 달무리 알파벳·숫자·부호 연결 |
| [dalmoori_symbols.md](analysis/fonts/dalmoori_symbols.md) | 달무리 부호를 한글 음절 FNT에 추가 — 2026-10-22 |
| [font_memory_lifecycle.md](analysis/fonts/font_memory_lifecycle.md) | Dune II 폰트 메모리 수명과 원본 할당 규약 역분석 |
| [hangul_16x16_design.md](analysis/fonts/hangul_16x16_design.md) | Dune II 16×16 한글 폰트 적용 설계 |
| [unifont_cinematics.md](analysis/fonts/unifont_cinematics.md) | 오프닝·엔딩 유니폰트 FNT 적용 |

### 메뉴·단축키·간격·테두리

| 기록 | 분석 내용 |
|---|---|
| [embedded_house_names.md](analysis/ui/embedded_house_names.md) | EXE 내장 가문 이름 번역 |
| [font_edges.md](analysis/ui/font_edges.md) | 한글 테두리 추가 — 2026-10-22 |
| [game_menu_text_position.md](analysis/ui/game_menu_text_position.md) | 게임 메뉴 선택문 Y 위치 — 2026-10-22 |
| [mentat_topic_spacing.md](analysis/ui/mentat_topic_spacing.md) | 멘타트 목록 대주제 위 여백 |
| [menu_edge_test.md](analysis/ui/menu_edge_test.md) | 원본 폰트 스타일을 따르는 한글 테두리 시험판 |
| [menu_glyph_corruption.md](analysis/ui/menu_glyph_corruption.md) | Dune II 메뉴 한글 폰트 오류: 런타임 원인 분석 |
| [menu_hooks.md](analysis/ui/menu_hooks.md) | Dune II 원본·한글 시험본 메뉴 렌더링 역분석 |
| [mission_map_first_syllable.md](analysis/ui/mission_map_first_syllable.md) | 2026-10-25 임무 선택 지도 첫 음절 누락 수정 |
| [mission_map_text_spacing.md](analysis/ui/mission_map_text_spacing.md) | 임무 선택 지도 설명의 가로 간격 |
| [top_message_spacing.md](analysis/ui/top_message_spacing.md) | 게임 상단 메시지의 가로 간격·Y 위치 |
| [translated_shortcuts.md](analysis/ui/translated_shortcuts.md) | Dune II 한글 번역 후 명령 단축키가 동작하지 않는 원인 |

### CG 형식·가문 질문

| 기록 | 분석 내용 |
|---|---|
| [graphics_codec.md](analysis/graphics/graphics_codec.md) | CG 편집과 재인코딩 |
| [herald_palette_repair.md](analysis/graphics/herald_palette_repair.md) | HERALD.ENG 편집 PNG의 색 번호 복원 — 2026-10-25 |
| [house_question_row_order.md](analysis/graphics/house_question_row_order.md) | 2026-10-25 편집 MISC.ENG 가문 행 순서 연결 수정 |
| [house_question_source.md](analysis/graphics/house_question_source.md) | 가문 가입 질문의 실제 출처 |
| [mentat_transparency_repair.md](analysis/graphics/mentat_transparency_repair.md) | MENTAT.ENG 버튼 PNG의 투명색 설정 복원 — 2026-10-25 |
| [three_row_house_question.md](analysis/graphics/three_row_house_question.md) | 가문 가입 질문을 완성 문장 세 줄로 저장하는 시험 |

### 원본 리소스

| 기록 | 분석 내용 |
|---|---|
| [english_resource_languages.md](analysis/resources/english_resource_languages.md) | 영어 리소스에 포함된 독일어 문구 대조 |

### 누적 실행 확인 기록

| 기록 | 분석 내용 |
|---|---|
| [build_verification_20261022.md](analysis/verification/build_verification_20261022.md) | 현재 빌드와 누적 확인 결과 — 2026-10-22 |
| [graphics_verification_20261022.md](analysis/verification/graphics_verification_20261022.md) | CG 편집·재인코딩·가문 질문 누적 확인 결과 — 2026-10-22 |

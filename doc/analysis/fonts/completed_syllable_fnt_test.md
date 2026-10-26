# Dune II 한글 조합 FNT 비교 상태

## 10×10 게임 FNT

게임 런타임은 `font/dune2-hangul-compose.fnt`에서 316개 10×10 구성 글리프와 조합 선택표를 읽는다. 파일 크기는 7,874바이트다. 10×10 결과는 게임에서 직접 확인해야 하며, 이전에 만든 전수 비교 자료는 글자 가독성이나 게임 출력을 증명하지 않는다.

`font/dune2-hangul-syllables-dune.fnt` 및 과거 10×10 접촉 시트/비교 이미지는 이전 방식의 산출물이다. 검증 자료로 사용하지 않는다.

## 16×16 조합 기준 자료

`tools/build_and_verify_hangul_syllables.py`는 원본 `font/unifont-16.0.04-minimized-316-selfcontained.fnt`를 입력으로 삼아 U+AC00..U+D7A3의 11,172개 음절을 16×16으로 조합한다. 각 결과를 독립적으로 읽은 선택표 결과와 보존된 `font/dune2-hangul-syllables.fnt`에 직접 대조한다. 2026-10-20 실행 결과는 11,172개 비교, 조합 불일치 0개, 기준 16×16 음절 FNT 불일치 0개다.

전체 음절 PNG는 `build/hangul-compose-validation/contact-sheets/`의 44장이다. 묶음은 `build/hangul-runtime-16x16/hangul-16x16-contact-sheets.zip`에서 확인할 수 있다. `font/dune2-hangul-compose-15x15-cell16.fnt`는 원본 316개 구성 글리프의 빈 첫 행·첫 열을 생략해 15×15로 저장한다. 후크가 (1,1)에 출력한 결과를 전수 비교해 원본 16×16의 11,172개 음절과 모두 일치하는 것을 확인했다.

## 게임 시험

정상 출력 확인이 끝난 10×10 격리 사본은 `build/hangul-runtime/source/VIRGIN/DUNE2/`에 있다. 새 16×16 셀 시험 사본은 `build/hangul-runtime-16x16/source/VIRGIN/DUNE2/`에 있고 `build/hangul-runtime-16x16/run_hangul_test.bat`로 실행한다. 메뉴 패널 높이·행 간격·선택 행 계산은 격리된 실행 파일에서 16픽셀로 조정했다. 전수 PNG·바이트 비교는 조합 결과 확인이며, DOSBox-X에서의 실제 렌더링은 사용자가 확인해야 한다.

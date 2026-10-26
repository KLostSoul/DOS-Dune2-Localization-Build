## HERALD.ENG 편집 PNG의 색 번호 복원 — 2026-10-25

`images/ENGLISH/HERALD.ENG/frame_000.png`는 인덱스 PNG였지만 원본 팔레트와 색 번호가 달랐다. 편집본의 검정은 7번으로 합쳐졌고 게임 팔레트에는 같은 RGB 검정이 0번과 12번에 있어 인코더의 색 번호 역변환이 실패했다.

사용자가 제공한 루트 `frame_000.png`는 보관 게임 리소스를 디코딩한 팔레트·픽셀 번호와 완전히 같았다. 이를 기준으로 편집 PNG의 원본 팔레트를 복원했다. 원래 RGB가 유지된 픽셀은 기존 색 번호를 보존하고, 기존 영문을 지운 새 검정 배경 341픽셀은 배경색 0번을 사용했다. 새 한글을 포함한 편집본의 RGB 화면은 한 픽셀도 바꾸지 않았다. 팔레트에 없는 새 색은 없었다.

수정 대상은 `cg/editable/images/ENGLISH/HERALD.ENG/frame_000.png`다. 수정 전 PNG는 `build/analysis/herald-palette-fix/frame_000.before.png`에 보존했다. 원본 공급 PNG와 게임 파일은 바꾸지 않았다. `load_pixels` 검사와 CPS 재인코딩·재디코딩을 통과했고 색 번호와 팔레트도 일치했다. 생성한 단독 리소스는 같은 분석 폴더의 `HERALD.ENG`, 해시·검사 근거는 `report.json`에 있다. 실제 게임 적용·실행 확인은 별도다.

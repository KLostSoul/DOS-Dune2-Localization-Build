## MENTAT.ENG 버튼 PNG의 투명색 설정 복원 — 2026-10-25

편집 PNG `images/ENGLISH/MENTAT.ENG/frame_000.png`의 팔레트는 원본과 같았지만 투명색 메타데이터가 없어 `transparency index changed` 오류가 났다. 사용자가 공급한 `frame_000.png`부터 `frame_009.png`까지 열 장은 보관된 MENTAT.ENG 원본 프레임과 팔레트·픽셀 번호·투명색 0번 설정이 같았다.

편집본 0~9번 열 장에 원본의 투명색 0번 설정을 복원했다. 한글 편집 픽셀 번호, 팔레트, 크기는 전부 그대로다. 공급되지 않은 10~13번 프레임도 수정하지 않았다. 전체 14프레임의 `load_pixels` 검사와 embedded SHP 재인코딩·재디코딩을 통과했다.

수정 전 열 장은 `build/analysis/mentat-png-transparency-fix/frame_XXX.before.png`로 보존했다. 프레임별 공급 원본·수정 전후 해시·검사 결과는 같은 폴더 `report.json`, 단독 재인코딩 결과는 `MENTAT.ENG`다. 게임 PAK와 EXE는 이번 PNG 설정 복원에서 바꾸지 않았다.

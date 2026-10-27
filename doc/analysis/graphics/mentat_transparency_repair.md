# MENTAT.ENG 버튼의 투명색 메타데이터

MENTAT.ENG 버튼 프레임은 팔레트 색 번호와 투명색 0번 설정을 함께 사용한다. 픽셀·팔레트가 그대로여도 PNG의 투명색 메타데이터가 빠지면 `transparency index changed` 검사가 실패한다.

## 보존할 속성

`import/GFX/images/ENGLISH/MENTAT.ENG/`의 프레임은 크기·색 번호·팔레트·투명색을 보존해야 한다. 투명색 복원은 PNG 메타데이터 변경이며 편집 픽셀 자체를 바꾸는 작업이 아니다.

MENTAT.ENG는 14프레임이다. 원본 프레임과 `load_pixels`를 대조하고 embedded SHP를 재인코딩·재디코딩해 투명색과 픽셀의 일치를 검사한다. 특정 버튼의 설정을 다른 색 번호로 임의 통일하지 않는다.

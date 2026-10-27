# 영어 리소스에 포함된 독일어 문구

## 리소스 내용

원본 CD 이미지의 `/VIRGIN/DUNE2/ENGLISH.PAK`에 포함된 `MENTATH.ENG`에서 독일어 문구 세 항목을 확인했다. 화면상 위치로는 하코넨 멘타트 37번 한 곳과 44번 한 곳이며, 44번은 목록 이름과 그림 설명 두 문자열로 구성된다.

| 멘타트 번호 | 종류 | `source_en`에 추출된 원문 | 언어 |
|---:|---|---|---|
| 37 | 본문 | `Die Elitetruppen des Imperators.` | 독일어 |
| 44 | 목록 이름 | `Frigatte` | 독일어 |
| 44 | 그림 설명·본문 | `CHOAM Frigatte / Planetarisches Transportsystem / Diese gewaltigen Raumschiffe dienen dazu, Schiffsladungen aus dem Orbit zum Raumflughafen zu transportieren.` | 독일어 |

## 원인과 추출 경로

원본 CD에서 ISO9660 경로 `/VIRGIN/DUNE2/ENGLISH.PAK`를 직접 읽은 SHA-256은 `576a7bea7826a0c47605c9b3c3abc7e24c74cc834c1b74fd997b2783a011cb74`다. 이 바이트열은 `export/PAK/ENGLISH.PAK`와 일치했다. 해당 PAK 안의 `MENTATH.ENG` 멤버도 추출 폴더 파일과 바이트 단위로 일치하며 SHA-256은 `2992a30fa0b2c2703054f10a56bb95c45aad20234b2c44b388c854f61cdfd9f2`다.

`tools/resources.py`의 `read_mentat()`는 `MENTNAME` 레코드에서 본문 오프셋을 읽고 압축을 풀어 내용을 `source_en`으로 기록한다. 언어를 판별하거나 독일어 파일에서 가져오는 동작은 없다. 따라서 독일어가 들어간 지점은 CSV 내보내기가 아니라 원본 `ENGLISH.PAK`의 `MENTATH.ENG` 데이터다. 왜 배포 원본의 영어 명명 리소스 안에 이 독일어 항목이 실렸는지는 확인 자료만으로 단정하지 않는다.

현재 `export/strings/source_strings_complete.csv`와 `import/strings/source_strings_complete_ko_draft.csv`는 추출된 원본 1,350행과 `source_en` 값이 모두 일치한다. `source_en` 열은 문자열의 실제 언어를 보증하지 않고, 영어 리소스 파일에서 읽은 원문을 보관한다. 그러므로 해당 세 항목의 독일어는 추출 오류나 다른 언어 PAK의 우발적 혼입이 아니다.

독일어 PAK의 하코넨 멘타트와 대조하면 37번 본문은 같은 독일어 문장이다. 독일어 PAK의 44번은 `Ordos Deviator` 항목이라 영어 PAK의 프리깃 44번과 일치하지 않는다. 따라서 영어 PAK의 44번을 독일어 PAK의 같은 번호에서 복사했다고 볼 근거는 없다.

## 검사 범위

영어 PAK의 문자열 리소스와 시나리오 지도 문구를 포함한 추출 행 1,350개를 현재 두 CSV와 대조했다. PAK 안의 멘타트 세 파일에서 이름 레코드가 가리키지 않는 추가 본문 데이터는 발견되지 않았다. 영어 리소스 안에서 확인된 독일어는 위 세 항목이며, 나머지 추출 문구에서는 독일어·프랑스어 등 추가 언어 혼입 후보를 찾지 못했다.

`DUNE2.EXE`에는 설치 안내와 확장 메모리 안내가 영어·독일어·프랑스어로 함께 들어 있다. 이는 별도 실행 파일 내 문자열이며 영어 PAK의 멘타트 추출물과 다른 범주다. 그래픽·음성 리소스 내부의 시각·청각 언어 내용까지 이 문자열 대조에 포함하지는 않았다.

문구 위치 근거는 [현재 번역 CSV 37번](../../../import/strings/source_strings_complete_ko_draft.csv)과 [원본 추출기](../../../tools/resources.py)다.

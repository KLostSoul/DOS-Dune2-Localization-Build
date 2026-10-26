# CD 패치 적용

한글 배포물은 `output/`의 `Dune2-Battle-for-Arrakis-Korean-v1.01` 이름을 사용한다. 번역·CG를 수정해 배포물을 생성하는 방법은 [BUILD](BUILD.md), 현재 결과 해시는 [STATUS](STATUS.md)와 배포 JSON을 따른다.

| 파일 | 용도 |
|---|---|
| `.bin.xdelta` | 원본 IMG에 적용하는 단일 Xdelta 3 VCDIFF 패치 |
| `.bin` | 한글 게임이 들어 있는 raw Mode 1/2352 CD 이미지 |
| `.cue` | BIN과 함께 사용하는 단일 데이터 트랙 마운트 정보 |
| `.json` | 원본·결과 해시, 사용 게임 폴더, 섹터·파일 구성 기록 |

## 패치 입력

기본 원본은 `img/DUNE2CD.img`다. SHA-256은 다음 값이어야 한다.

```text
edcdce3de2e4d986421d99cc11be424277317fc3e8cd71cf78f8ed544bce81bf
```

적용 명령은 대응하는 `.bin.xdelta`와 `.json`을 함께 읽는다. 기본 위치는 프로젝트의 `output/`이다.

## 적용과 실행

프로젝트 루트에서 실행한다.

```powershell
python tools/clonecd_xdelta.py apply
```

`output/`에 BIN을 기록하고 CUE를 생성한다. 생성 후 JSON의 결과 해시·섹터 수와 일치하는지 확인한다. 게임을 CD 이미지로 실행할 때는 **새 BIN과 새 CUE를 함께 사용한다.** 원본 CloneCD의 CCD·SUB·CUE는 원본 보존용으로 두며 한글 BIN의 마운트 정보로 재사용하지 않는다.

입력과 출력 위치를 바꾸려면 해당 옵션을 지정한다.

```powershell
python tools/clonecd_xdelta.py apply --original-dir "원본 CD 폴더" --patch "패치.bin.xdelta" --manifest "패치.json" --output-dir "한글 CD 출력 폴더"
```

## 실행 도구

Python 별칭을 사용할 수 없으면 설치된 실행 파일을 직접 지정한다.

```powershell
& 'C:\Users\LS\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools/clonecd_xdelta.py apply
```

`xdelta3.exe`는 PATH에서 찾으며, 없으면 `build/analysis-deps/xdelta3-3.2.2/xdelta3-3.2.2-windows-x86_64/xdelta3.exe`를 사용한다. 다른 실행 파일은 `--xdelta3 "실행 파일 경로"`로 지정한다.

## CD 산출물만 재생성

기존 최종 실행본에서 BIN/CUE·Xdelta를 다시 만들 때는 다음 명령을 사용한다. 기본 게임 입력은 `build/final-build/source/VIRGIN/DUNE2`, 기본 출력은 `output/`이다.

```powershell
python tools/clonecd_xdelta.py create
```

다른 게임 사본은 `--game-dir "게임 폴더"`, 별도 출력은 `--output-dir "출력 폴더"`로 지정한다. `create`에서 별도 패치·JSON 경로를 지정하지 않으면 선택한 출력 폴더에 함께 생성한다.

이미지 안의 `/VIRGIN/DUNE2/`에 게임 파일과 생성 FNT·색인표를 반영한다. 커진 파일은 원본 뒤의 새 섹터에 놓고 ISO9660 디렉터리와 변경 raw 섹터의 EDC/ECC를 갱신한다. 원본 IMG와 로컬 소리 설정을 보존하며 세이브 파일을 추가하지 않는다.

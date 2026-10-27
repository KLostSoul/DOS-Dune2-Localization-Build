# 빌드 입력 자료

번역 문자열, 편집 CG, 어셈블리 소스와 게임 패치 입력을 저장합니다.

| 경로 | 내용 |
|---|---|
| [strings/](strings/README.md) | 게임 문자열과 화면 표시용 가문 이름의 번역 CSV |
| [GFX/](GFX/README.md) | 게임에 반영할 편집 PNG. 입력 위치는 `GFX/images/` |
| [asm/](asm/README.md) | 폰트·자막·치트의 16비트 ASM 소스와 JWasm 조립 도구 |
| [fnt/](fnt/README.md) | 등록 한글 문자표와 빌드에서 생성하는 달무리·유니폰트 FNT 및 색인표 |
| [patches/](patches/README.md) | HitSquad 1.07 Fix 패키지 |
| `cd-runtime-base.json` | 원본 EXE의 패치 위치·수정 전후 바이트·검증 해시 |
| `runtime-settings.json` | 실행용 게임 폴더에 적용할 `DUNE.CFG`·`OPTIONS.CFG`·`ONETIME.DAT` 기본값 |

## 수정과 빌드

번역은 `strings/` CSV의 `translation_ko` 열에서, CG는 `GFX/images/`의 PNG에서 수정합니다. 문자열의 서식 지정자와 PNG의 크기·팔레트 색 번호·투명색을 유지합니다.

프로젝트 루트에서 실행합니다.

```powershell
python tools/build_game.py
```

빌드는 `font/`의 HEX와 번역 자료로 필요한 FNT를 생성하고, ASM을 조립해 게임 파일과 CD 배포물에 반영합니다. 실행용 게임은 `build/final-build/source/VIRGIN/DUNE2/`, BIN·CUE·Xdelta·배포 JSON은 `output/`에 생성됩니다.

`runtime-settings.json`의 설정은 실행용 게임 폴더에 적용하며 CD 이미지에는 추가하지 않습니다.

전체 생성 과정은 [빌드 안내](../doc/BUILD.md), 글꼴과 문자표는 [폰트 안내](../doc/FONTS.md), CG 형식은 [CG 편집 안내](../doc/GRAPHICS.md)를 참고하세요.

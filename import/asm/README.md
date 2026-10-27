# 어셈블리 소스

최종 빌드에 사용하는 16비트 ASM 소스와 JWasm 도구입니다.

| 파일 | 용도 |
|---|---|
| `font/dalmoori-base.asm` | 기본 한글 출력 후크 |
| `font/dalmoori-latin-hook.asm` | 달무리 영문·숫자·부호 출력 |
| `font/unifont-intro-hook.asm` | 영상 자막의 유니폰트 출력 |
| `scene/harkonnen-second-scene.asm` | 하코넨 두 번째 영상의 마지막 자막 |
| `scene/ordos-second-scene.asm` | 오르도스 두 번째 영상의 마지막 자막 |
| `scene/subtitle-normalize.asm` | 영상 자막 토큰 처리 |
| `cheat/cheat-hook-build.asm` | 기본 치트와 입력 처리 |
| `cheat/cheat-extra.asm` | FASTBUILD·REVEAL 치트 |

`python tools/build_game.py`를 실행하면 `JWasm.exe` v2.20으로 소스를 조립합니다. 조립 결과는 빌드 중간 자료로 사용됩니다.

## 라이선스

[JWasm-License.txt](JWasm-License.txt)에 Sybase Open Watcom Public License 1.0 전문을 포함합니다.

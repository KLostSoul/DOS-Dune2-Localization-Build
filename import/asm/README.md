# 어셈블리 입력 소스

최종 게임 빌드가 실행 파일을 생성할 때 읽는 ASM 원본을 이 폴더에 둔다. 최종 빌드 코드의 입력 경로는 저장소 루트 기준 `import/asm/`이다.

폰트 출력 ASM은 `font/` 하위에 모아 두었다.

| 파일 | 용도 |
|---|---|
| `font/dalmoori-base.asm` | 원본 CD EXE에 초기 달무리 출력 후크를 재현하는 기본 모듈 |
| `font/dalmoori-latin-hook.asm` | 달무리 영문·숫자·부호 출력 후크 |
| `font/unifont-intro-hook.asm` | 오프닝·엔딩 유니폰트 출력 후크 |

중간 영상 패치와 자막 전처리 소스는 `scene/` 하위에 둔다.

| 파일 | 용도 |
|---|---|
| `scene/harkonnen-second-scene.asm` | 하코넨 두 번째 영상 마지막 자막 |
| `scene/ordos-second-scene.asm` | 오르도스 두 번째 영상 마지막 자막 |
| `scene/subtitle-normalize.asm` | 두 바이트 한글 토큰을 보존하는 자막 전처리 |

치트 어셈블리는 `cheat/` 하위에 모아 두었다.

| 파일 | 용도 |
|---|---|
| `cheat/cheat-hook-build.asm` | 검증된 기본 치트와 Enter 처리 |
| `cheat/cheat-extra.asm` | FASTBUILD·REVEAL 추가 치트 |

빌드별 생성물과 과거 분석 증거는 각각의 `build/` 아래에 보존한다.

## 어셈블러 도구

| 파일 | 내용 |
|---|---|
| `JWasm.exe` | JWasm v2.20 실행 파일. 최종 게임 빌드의 모든 ASM 모듈을 컴파일하는 도구 |
| `JWasm-License.txt` | 배포본에 포함된 라이선스 전문(Sybase Open Watcom Public License 1.0) |

JWasm 실행 파일 SHA-256: `ce95d1a4e83b2cba74fadffdf1f009438e668a30f6314c93d7b044e55be7ecee`.

최종 게임 빌드는 이 실행 파일만 사용해 모든 ASM 모듈을 컴파일한다. 원본 CD에서 초기 치트 모듈을 조립하고 그 생성 해시로 확인하며, 새로 생성한 중간 치트 모듈과 최종 확장 치트 모듈도 JWasm으로 조립한다.

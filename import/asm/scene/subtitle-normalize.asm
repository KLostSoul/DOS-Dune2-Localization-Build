; Same FAR C interface and 81-byte slot as the original subtitle normalizer.
; Preserve two-byte Hangul tokens before applying the original single-byte
; E1h -> 01h conversion. Supports separate buffers and the original in-place call.
.386
KOREAN SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:KOREAN
ORG 0CB5h
SubtitleNormalize PROC FAR
    push bp
    mov bp, sp
    pushf
    push ds
    push es
    push si
    push di
    lds si, dword ptr [bp+6]
    mov ax, ds
    or ax, si
    jz Done
    les di, dword ptr [bp+10]
    mov ax, es
    or ax, di
    jz Done
    cld
NextByte:
    lodsb
    or al, al
    jz Terminator
    cmp al, 0E2h
    jb SingleByte
    cmp al, 0FEh
    ja SingleByte
    cmp al, 0FAh
    je SingleByte
    cmp byte ptr [si], 80h
    jb SingleByte
    cmp byte ptr [si], 0FEh
    ja SingleByte
    stosb
    lodsb
    stosb
    jmp NextByte
SingleByte:
    cmp al, 0E1h
    jne StoreByte
    mov al, 1
StoreByte:
    stosb
    jmp NextByte
Terminator:
    stosb
Done:
    pop di
    pop si
    pop es
    pop ds
    popf
    pop bp
    retf
SubtitleNormalize ENDP
KOREAN ENDS
END

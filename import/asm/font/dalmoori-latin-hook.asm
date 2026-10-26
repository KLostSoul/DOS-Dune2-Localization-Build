; Explicit scope state belongs to original text-owner calls, not keyboard or
; printf parsing. The raw ASCII bytes and Reader's one-byte contract stay intact.
MapLatin PROC NEAR
    cmp ax, 0100h
    jae MapLatinDone
    cmp word ptr cs:[LatinMode-LatinSegmentZero], 1
    jne MapLatinDone
    push bx
    mov bx, ax
    shl bx, 1
    mov bx, word ptr cs:[LatinLookup+bx-LatinSegmentZero]
    cmp bx, 0FFFFh
    je MapLatinUnmapped
    mov ax, bx
MapLatinUnmapped:
    pop bx
MapLatinDone:
    ret
MapLatin ENDP

; Physical glyph index (without 0100h). CF=1 means a Latin/symbol record.
IsLatinGlyph PROC NEAR
    cmp ax, 639
    jb NotLatinGlyph
    cmp ax, 672
    jb YesLatinGlyph
    cmp ax, LATIN_GLYPH_START
    jae YesLatinGlyph
NotLatinGlyph:
    clc
    ret
YesLatinGlyph:
    stc
    ret
IsLatinGlyph ENDP

DetectLatinString PROC NEAR
    cmp word ptr cs:[LatinFixedDepth-LatinSegmentZero], 0
    jne DetectLatinDone
    mov word ptr cs:[LatinMode-LatinSegmentZero], 0
    mov ax, es
    or ax, bx
    jz DetectLatinDone
    mov cx, 0FFFFh
DetectLatinNext:
    call Reader
    or ax, ax
    jz DetectLatinDone
    cmp ax, 0100h
    jb DetectLatinAdvance
    sub ax, 0100h
    call IsLatinGlyph
    jc DetectLatinAdvance
    mov word ptr cs:[LatinMode-LatinSegmentZero], 1
    ret
DetectLatinAdvance:
    add bx, dx
    jc DetectLatinDone
    loop DetectLatinNext
DetectLatinDone:
    ret
DetectLatinString ENDP

LatinSingleWidth PROC NEAR
    push bp
    mov bp, sp
    push bx
    push es
    xor ax, ax
    mov al, byte ptr ss:[bp+6]
    call MapLatin
    cmp ax, 0100h
    jb LatinSingleOriginal
    mov ax, 6
    add ax, word ptr ds:[6CF8h]
    jmp LatinSingleReturn
LatinSingleOriginal:
    push word ptr ss:[bp+6]
    push cs
    call NEAR PTR OriginalByteWidth
    add sp, 2
LatinSingleReturn:
    pop es
    pop bx
    pop bp
    retf
LatinSingleWidth ENDP

; Existing DrawGlyph's explicit effective-Y helper owns [BP-18h]. Align the
; native 8px Latin baseline with 16px Unifont only in the INTRO font context.
LatinEffectiveY PROC NEAR
    mov ax, word ptr ss:[bp+10]
    cmp byte ptr cs:[0442h], 10
    jne LatinYBase
    or ax, ax
    jz LatinYBase
    dec ax
LatinYBase:
    push ax
    mov ax, word ptr ss:[bp+6]
    call MapLatin
    cmp ax, 0100h
    jb LatinYOriginal
    sub ax, 0100h
    call IsLatinGlyph
    jnc LatinYOriginal
    call IsIntroFont
    jne LatinYOriginal
    pop ax
    add ax, 8
    jmp LatinYStore
LatinYOriginal:
    pop ax
LatinYStore:
    mov word ptr ss:[bp-18h], ax
    ret
LatinEffectiveY ENDP

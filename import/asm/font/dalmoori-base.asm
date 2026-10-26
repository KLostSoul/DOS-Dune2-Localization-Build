; Dune II extension. Original layout loops own all text cursors.
; No return-address dispatch, parent-frame inspection, or shared callback hook.
; AX internal glyph = 0100h + dense 639-entry index; original slots stay 00..FF.
.386
KOREAN SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:KOREAN
MODULE_SEG EQU 3D02h

ORG 0000h
OriginalWidth LABEL FAR
    INCLUDE original-width.inc

ORG 0026h
; Original font-info load, with a local line height for outlined descriptions.
; ES:BX:DI are the original font cursor; AX is the only register result.
GetLineHeight PROC FAR
    xor ah, ah
    mov al, byte ptr es:[bx+di+4]
    pushf
    push bx
    push dx
    push es
    mov dx, ax
    call CheckOutlineStyle
    jne LineHeightDone
    mov ax, 11
    jmp LineHeightCompare
GetLineHeight ENDP

ORG 0040h
; ES:BX cursor -> AX glyph, DX byte count. No memory writes.
; Preserve BX/CX/SI/DI/BP/DS/ES.
ReadGlyph PROC NEAR
    push cx
    push di
    xor ax, ax
    mov al, byte ptr es:[bx]
    mov dx, 1
    cmp al, 0F8h
    jb ReadSingle
    cmp al, 0FEh
    ja ReadInvalid
    cmp al, 0FAh
    je ReadInvalid
    xor cx, cx
    mov cl, byte ptr es:[bx+1]
    cmp cx, 80h
    jb ReadInvalid
    cmp cx, 0EAh
    ja ReadInvalid
    sub cx, 80h
    mov di, cx
    sub al, 0F8h
    cmp al, 2
    jb ReadPage
    dec al
ReadPage:
    mov cx, 107
    mul cx
    add ax, di
    cmp ax, 639
    jae ReadInvalid
    add ax, 0100h
    mov dx, 2
    jmp ReadDone
ReadSingle:
    jmp ReadDone
ReadInvalid:
    ; Preserve the original single-byte slot if this is not a valid token.
    xor ax, ax
    mov al, byte ptr es:[bx]
    mov dx, 1
ReadDone:
    pop di
    pop cx
    ret
ReadGlyph ENDP

ORG 0098h
; Style 30h maps indices 2/3 to 0Ch/0Ch. Menu styles 10h/20h do not.
CheckOutlineStyle PROC NEAR
    mov ax, cs
    sub ax, MODULE_SEG-20AAh
    mov es, ax
    mov bx, 0093h
    mov ax, word ptr es:[bx]
    cmp ax, 0C0Ch
    ret
CheckOutlineStyle ENDP

ORG 00B0h
; AX glyph -> AX advance. Does not consume a string or alter its pointer.
WidthByGlyph PROC NEAR
    jmp WidthWithSymbols
WidthByGlyph ENDP

ORG 00E0h
; Explicit owner-loop interface: ES:BX, SI accumulated width.
; Returns BX next cursor, SI updated width, AX width, DX byte count.
NextAndAccumulate PROC FAR
    call ReadGlyph
    add bx, dx
    call WidthByGlyph
    add si, ax
    retf
NextAndAccumulate ENDP

ORG 0100h
; Original reverse scan subtracts current width, then moves to predecessor.
; Returns BX predecessor, SI updated width, AX width. No caller-frame writes.
PreviousAndAccumulate PROC FAR
    call ReadGlyph
    call WidthByGlyph
    sub si, ax
    push ax
    push dx
    dec bx
    cmp byte ptr es:[bx], 80h
    jb PreviousDone
    cmp byte ptr es:[bx], 0EAh
    ja PreviousDone
    push bx
    dec bx
    call ReadGlyph
    pop bx
    cmp dx, 2
    jne PreviousDone
    dec bx
PreviousDone:
    pop dx
    pop ax
    retf
PreviousAndAccumulate ENDP

ORG 0126h
LineHeightCompare:
    sub ax, word ptr ds:[6CFAh]
    cmp dx, ax
    jge LineHeightDone
    mov dx, ax
LineHeightDone:
    mov ax, dx
    pop es
    pop dx
    pop bx
    popf
    retf

ORG 0140h
; ES:SI -> AX glyph, DX byte count. Cursor remains unchanged.
GlyphAtSI PROC FAR
    push bx
    mov bx, si
    call ReadGlyph
    pop bx
    retf
GlyphAtSI ENDP

ORG 0160h
; Width stage of the original 29C7:0004 loop. Only AX is a return value.
WidthAtSI PROC FAR
    push bx
    push dx
    mov bx, si
    call ReadGlyph
    call WidthByGlyph
    pop dx
    pop bx
    retf
WidthAtSI ENDP

ORG 016Eh
; Keep the 8-row Hangul body at the original Y; raise only outlined glyphs.
SelectDrawY PROC NEAR
    mov ax, word ptr [bp+10]
    cmp byte ptr cs:[0442h], 10
    jne DrawYReady
    or ax, ax
    jz DrawYReady
    dec ax
DrawYReady:
    mov word ptr [bp-24], ax
    ret
SelectDrawY ENDP

ORG 0190h
; Stack (FAR C): glyph word, X, Y. Preserve all registers and flags.
; Both Latin and Hangul pixels are written by original DS:[66D8].
DrawGlyph PROC FAR
    push bp
    mov bp, sp
    pushf
    pusha
    push ds
    push es
    sub sp, 2
    mov ax, word ptr [bp+6]
    call ResolveSymbol
    cmp ax, 0100h
    jb DrawLegacy
    sub ax, 0100h
    cmp ax, 672
    jae DrawReturn
    mov byte ptr cs:[0446h], 10
    cmp ax, 639
    jb DrawWidthReady
    mov byte ptr cs:[0446h], 6
DrawWidthReady:
    mov dx, 10
    mul dx
    add ax, 049Ah
    mov si, ax
    push cs
    pop ds
    ; CS:[93h/94h] are the original FNT color mappings for indices 2/3.
    ; Accept only the exact description-style mapping, not any nonzero entry.
    call CheckOutlineStyle
    je SelectOutline
SelectBody:
    mov byte ptr cs:[0442h], 8
    mov byte ptr cs:[0448h], 8
    push cs
    pop ds
    mov di, 0449h
    mov dx, 8
BodyPackRow:
    xor bx, bx
    mov bl, byte ptr [si]
    inc si
    shl bx, 1
    xor cx, cx
    mov cl, byte ptr cs:[0446h]
BodyPackPixel:
    xor ax, ax
    test bx, 0200h
    jz BodyPackNibble
    inc ax
BodyPackNibble:
    shl bx, 1
    test cl, 1
    jnz BodyPackHigh
    mov byte ptr [di], al
    jmp BodyPackNext
BodyPackHigh:
    shl al, 4
    or byte ptr [di], al
    inc di
BodyPackNext:
    loop BodyPackPixel
    dec dx
    jnz BodyPackRow

    jmp PackedReady
SelectOutline:
    ; At Y=0 the original glyph origin has priority over the clipped top edge.
    cmp word ptr [bp+10], 0
    je SelectBody
    mov byte ptr cs:[0442h], 10
    mov byte ptr cs:[0448h], 10
    push cs
    pop ds
    mov di, 0449h
    push bp
    xor bp, bp
OutlineRow:
    xor ax, ax
    xor bx, bx
    xor dx, dx
    cmp bp, 2
    jb NoPreviousRow
    mov al, byte ptr ds:[bp+si-2]
NoPreviousRow:
    cmp bp, 1
    jb NoCurrentRow
    cmp bp, 8
    ja NoCurrentRow
    mov bl, byte ptr ds:[bp+si-1]
NoCurrentRow:
    cmp bp, 8
    jae NoNextRow
    mov dl, byte ptr ds:[bp+si]
NoNextRow:
    shl ax, 1
    shl bx, 1
    shl dx, 1
    ; Form the same upper/left 3 and lower/right 2 edge masks as original FNTs.
    mov cx, dx
    shl cx, 1
    or dx, cx
    shr cx, 2
    or dx, cx
    mov cx, bx
    shl cx, 1
    or dx, cx
    mov cx, ax
    shl cx, 1
    or ax, cx
    shr cx, 2
    or ax, cx
    mov cx, bx
    shr cx, 1
    or ax, cx
    push si
    mov si, ax
    xor cx, cx
    mov cl, byte ptr cs:[0446h]
OutlinePixel:
    xor ax, ax
    test bx, 0200h
    jz OutlineBackground
    mov al, 1
    jmp OutlinePacked
OutlineBackground:
    test dx, 0200h
    jz OutlineLower
    mov al, 3
    jmp OutlinePacked
OutlineLower:
    test si, 0200h
    jz OutlinePacked
    mov al, 2
OutlinePacked:
    shl bx, 1
    shl dx, 1
    shl si, 1
    test cl, 1
    jnz OutlineHighNibble
    mov byte ptr [di], al
    jmp OutlineNextPixel
OutlineHighNibble:
    shl al, 4
    or byte ptr [di], al
    inc di
OutlineNextPixel:
    loop OutlinePixel
    pop si
    inc bp
    cmp bp, 10
    jb OutlineRow
    pop bp
PackedReady:
    call SelectDrawY
    ; Save the exact original driver FNT cache on our stack.
    ; Only its glyph source changes for this one call; game font globals stay.
    mov ax, cs
    sub ax, MODULE_SEG-20AAh
    mov es, ax
    push word ptr es:[007Ch]
    push word ptr es:[007Eh]
    push word ptr es:[0080h]
    push word ptr es:[0082h]
    push word ptr es:[0084h]
    push word ptr es:[0086h]
    push word ptr es:[0088h]
    push word ptr es:[008Ah]
    push word ptr es:[008Ch]
    mov word ptr es:[007Ch], 14
    mov word ptr es:[007Eh], 20
    mov word ptr es:[0080h], 22
    mov word ptr es:[0082h], 25
    mov word ptr es:[0084h], 23
    mov word ptr es:[008Ah], 0430h
    mov ax, cs
    mov word ptr es:[008Ch], ax
    mov ax, word ptr ss:[bp-20] ; our saved DS, never the caller's parent frame
    mov ds, ax
    ; Y is selected by the active string style.
    push word ptr [bp-24]
    push word ptr [bp+8]
    xor ax, ax
    push ax
    call dword ptr ds:[66D8h]
    add sp, 6
    pop word ptr es:[008Ch]
    pop word ptr es:[008Ah]
    pop word ptr es:[0088h]
    pop word ptr es:[0086h]
    pop word ptr es:[0084h]
    pop word ptr es:[0082h]
    pop word ptr es:[0080h]
    pop word ptr es:[007Eh]
    pop word ptr es:[007Ch]
    jmp DrawReturn
DrawLegacy:
    push word ptr [bp+10]
    push word ptr [bp+8]
    push word ptr [bp+6]
    call dword ptr ds:[66D8h]
    add sp, 6
DrawReturn:
    add sp, 2
    pop es
    pop ds
    popa
    popf
    pop bp
    retf
DrawGlyph ENDP



ORG 042Ch
OriginalTextPtr dw 0004h, 0

ORG 0430h
; A valid one-slot Westwood 4bpp FNT passed to the unmodified pixel renderer.
ScratchFont LABEL BYTE
    dw 75, 0500h, 14, 20, 22, 25, 23
    db 12h, 10h, 0, 0, 8, 10
    dw 25
    db 10, 0, 8
ScratchBitmap db 50 dup (0)

ORG 0480h
FontTable LABEL BYTE
    INCLUDE font-table.inc
ORG 1EE0h
; Original fixed-pitch text helper, now with a 3-byte local glyph string.
; Its original arguments, iteration order, renderer and pitch are preserved.
FixedPitchDraw PROC FAR
    push bp
    mov bp, sp
    sub sp, 4
    push si
    mov si, word ptr [bp+10]
FixedLoop:
    les bx, dword ptr [bp+6]
    call ReadGlyph
    or ax, ax
    jz FixedDone
    cmp ax, 0100h
    jb FixedSingle
    mov ax, word ptr es:[bx]
    mov word ptr [bp-4], ax
    mov word ptr [bp-2], 0
    jmp FixedReady
FixedSingle:
    mov byte ptr [bp-4], al
    mov byte ptr [bp-3], 0
FixedReady:
    add bx, dx
    mov word ptr [bp+6], bx
    push word ptr [bp+16]
    push word ptr [bp+14]
    push word ptr [bp+12]
    push si
    push ss
    lea ax, [bp-4]
    push ax
    mov ax, cs
    sub ax, MODULE_SEG-29C7h
    mov word ptr cs:[042Eh], ax
    call dword ptr cs:[042Ch]
    add sp, 12
    add si, word ptr [bp+18]
    jmp FixedLoop
FixedDone:
    pop si
    mov sp, bp
    pop bp
    retf
FixedPitchDraw ENDP

ORG 1F40h
; AX is an original byte or a syllable glyph. Return the same value except
; for the 32 ASCII punctuation slots and CP437 FAh (middle dot).
ResolveSymbol PROC NEAR
    cmp ax, 21h
    jb SymbolDone
    cmp ax, 2Fh
    jbe SymbolRange1
    cmp ax, 3Ah
    jb SymbolDone
    cmp ax, 40h
    jbe SymbolRange2
    cmp ax, 5Bh
    jb SymbolDone
    cmp ax, 60h
    jbe SymbolRange3
    cmp ax, 7Bh
    jb SymbolDone
    cmp ax, 7Eh
    jbe SymbolRange4
    cmp ax, 0FAh
    jne SymbolDone
    mov ax, 0100h+639+32
    ret
SymbolRange1:
    add ax, 0100h+639-21h
    ret
SymbolRange2:
    add ax, 0100h+639+15-3Ah
    ret
SymbolRange3:
    add ax, 0100h+639+22-5Bh
    ret
SymbolRange4:
    add ax, 0100h+639+28-7Bh
SymbolDone:
    ret
ResolveSymbol ENDP

ORG 1FA0h
WidthWithSymbols PROC NEAR
    push bx
    push es
    call ResolveSymbol
    cmp ax, 0100h+639
    jae SymbolWidth
    cmp ax, 0100h
    jae SyllableWidth
    push ax
    push cs
    call NEAR PTR OriginalWidth
    add sp, 2
    jmp WidthFinished
SyllableWidth:
    mov ax, 10
    jmp AddOriginalSpacing
SymbolWidth:
    mov ax, 6
AddOriginalSpacing:
    add ax, word ptr ds:[6CF8h]
WidthFinished:
    pop es
    pop bx
    ret
WidthWithSymbols ENDP

KOREAN ENDS
END

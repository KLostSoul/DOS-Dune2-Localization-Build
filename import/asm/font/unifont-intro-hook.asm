; Native 16x16 FNTs and their syllable map live in one XMS block.
; No DOS AH=48h block or game FAR heap is used. Only foreground text calls
; perform the one-time synchronous file load; subsequent glyphs use XMS moves.
IsIntroFont PROC NEAR
    push ax
    push bx
    push es
    mov ax, cs
    sub ax, 3D02h-20AAh
    mov es, ax
    les bx, dword ptr es:[008Ah]
    cmp word ptr es:[bx], 1C24h
    jne IntroFontDone
    cmp word ptr es:[bx+2], 0500h
    jne IntroFontDone
    cmp word ptr es:[bx+18], 1113h
IntroFontDone:
    pop es
    pop bx
    pop ax
    ret
IsIntroFont ENDP

; AX is a physical glyph index, excluding the renderer's 0100h marker.
IsUniPunct PROC NEAR
    push bx
    push cx
    xor bx, bx
    mov cx, UNI_PUNCT_COUNT
    jcxz UniPunctMissing
UniPunctNext:
    cmp ax, word ptr cs:[UniPunctSlots+bx]
    je UniPunctFound
    add bx, 2
    loop UniPunctNext
UniPunctMissing:
    clc
    jmp UniPunctReturn
UniPunctFound:
    stc
UniPunctReturn:
    pop cx
    pop bx
    ret
IsUniPunct ENDP

; The input and DX (two-byte token length) survive an unhandled result.
; CF=1 returns the actual Unifont symbol advance, 8 or 16, plus spacing.
UniSymbolWidth PROC NEAR
    push bx
    push cx
    push ax
    cmp ax, 0100h
    jb UniSymbolWidthMissing
    sub ax, 0100h
    xor bx, bx
    mov cx, UNI_PUNCT_COUNT
    jcxz UniSymbolWidthMissing
UniSymbolWidthNext:
    cmp ax, word ptr cs:[UniPunctSlots+bx]
    je UniSymbolWidthFound
    add bx, 2
    loop UniSymbolWidthNext
    jmp UniSymbolWidthMissing
UniSymbolWidthFound:
    call IsIntroFont
    jne UniSymbolWidthMissing
    call EnsureUniFont
    cmp word ptr cs:[UniStatus], 1
    jne UniSymbolWidthMissing
    pop ax
    mov ax, word ptr cs:[UniPunctWidths+bx]
    add ax, word ptr ds:[6CF8h]
    stc
    jmp UniSymbolWidthReturn
UniSymbolWidthMissing:
    pop ax
    clc
UniSymbolWidthReturn:
    pop cx
    pop bx
    ret
UniSymbolWidth ENDP

IntroSymbol PROC NEAR
    call MapLatin
    cmp ax, 0100h
    jae IntroSymbolDone
    call IsIntroFont
    jne IntroSymbolLegacy
    call EnsureUniFont
    cmp word ptr cs:[UniStatus], 1
    je IntroSymbolDone
IntroSymbolLegacy:
    call ReleaseUniFont
    cmp ax, 28h
    je IntroSymbolDone
    cmp ax, 29h
    je IntroSymbolDone
    jmp LegacySymbol
IntroSymbolDone:
    ret
IntroSymbol ENDP

UniMoveBlock PROC NEAR
    push ds
    push si
    push cs
    pop ds
    mov si, OFFSET UniMove
    mov ah, 0Bh
    call dword ptr cs:[UniXmsEntry]
    pop si
    pop ds
    ret
UniMoveBlock ENDP

EnsureUniFont PROC NEAR
    pushf
    pusha
    push ds
    push es
    cmp word ptr cs:[UniStatus], 0
    jne UniInitDone
    mov word ptr cs:[UniStatus], 0FFFFh
    mov ax, 4300h
    int 2Fh
    cmp al, 80h
    jne UniInitDone
    mov ax, 4310h
    int 2Fh
    mov word ptr cs:[UniXmsEntry], bx
    mov word ptr cs:[UniXmsEntry+2], es
    mov dx, UNI_XMS_KIB
    mov ah, 09h
    call dword ptr cs:[UniXmsEntry]
    cmp ax, 1
    jne UniInitDone
    mov word ptr cs:[UniXmsHandle], dx
    push cs
    pop ds
    mov di, OFFSET UniFiles
    mov word ptr cs:[UniFilesLeft], UNI_FILE_COUNT
UniOpenFile:
    mov dword ptr cs:[UniFileRead], 0
    mov eax, dword ptr cs:[di+6]
    mov dword ptr cs:[UniDestination], eax
    mov dx, word ptr cs:[di]
    mov ax, 3D00h
    int 21h
    jc UniInitFailed
    mov word ptr cs:[UniDosHandle], ax
UniReadFile:
    mov eax, dword ptr cs:[di+2]
    sub eax, dword ptr cs:[UniFileRead]
    jz UniCheckEOF
    cmp eax, 256
    jbe UniReadLength
    mov ax, 256
UniReadLength:
    mov word ptr cs:[UniRequested], ax
    mov cx, ax
    mov bx, word ptr cs:[UniDosHandle]
    mov dx, OFFSET UniTransfer
    mov ah, 3Fh
    int 21h
    jc UniInitFailed
    cmp ax, word ptr cs:[UniRequested]
    jne UniInitFailed
    movzx eax, ax
    add dword ptr cs:[UniFileRead], eax
    ; XMS requires an even transfer length. Only the final file chunk can
    ; be odd; each file's XMS base is explicitly padded to an even address.
    mov bx, ax
    mov byte ptr cs:[bx+UniTransfer], 0
    inc ax
    and ax, 0FFFEh
    mov word ptr cs:[UniMoveLength], ax
    mov word ptr cs:[UniMoveLength+2], 0
    mov word ptr cs:[UniSourceHandle], 0
    mov word ptr cs:[UniSource], OFFSET UniTransfer
    mov word ptr cs:[UniSource+2], cs
    mov ax, word ptr cs:[UniXmsHandle]
    mov word ptr cs:[UniDestinationHandle], ax
    call UniMoveBlock
    cmp ax, 1
    jne UniInitFailed
    mov eax, dword ptr cs:[UniMoveLength]
    add dword ptr cs:[UniDestination], eax
    jmp UniReadFile
UniCheckEOF:
    mov bx, word ptr cs:[UniDosHandle]
    mov dx, OFFSET UniTransfer
    mov cx, 1
    mov ah, 3Fh
    int 21h
    jc UniInitFailed
    or ax, ax
    jnz UniInitFailed
    mov bx, word ptr cs:[UniDosHandle]
    mov ah, 3Eh
    int 21h
    mov word ptr cs:[UniDosHandle], 0FFFFh
    jc UniInitFailed
    add di, 10
    dec word ptr cs:[UniFilesLeft]
    jnz UniOpenFile
    mov word ptr cs:[UniStatus], 1
    jmp UniInitDone
UniInitFailed:
    cmp word ptr cs:[UniDosHandle], 0FFFFh
    je UniReleaseHandle
    mov bx, word ptr cs:[UniDosHandle]
    mov ah, 3Eh
    int 21h
    mov word ptr cs:[UniDosHandle], 0FFFFh
UniReleaseHandle:
    mov dx, word ptr cs:[UniXmsHandle]
    or dx, dx
    jz UniInitDone
    mov ah, 0Ah
    call dword ptr cs:[UniXmsEntry]
    mov word ptr cs:[UniXmsHandle], 0
UniInitDone:
    pop es
    pop ds
    popa
    popf
    ret
EnsureUniFont ENDP

ReleaseUniFont PROC NEAR
    pushf
    pusha
    push ds
    push es
    cmp word ptr cs:[UniStatus], 1
    jne UniReleaseDone
    mov dx, word ptr cs:[UniXmsHandle]
    mov ah, 0Ah
    call dword ptr cs:[UniXmsEntry]
    cmp ax, 1
    jne UniReleaseDone
    mov word ptr cs:[UniXmsHandle], 0
    mov word ptr cs:[UniStatus], 0
UniReleaseDone:
    pop es
    pop ds
    popa
    popf
    ret
ReleaseUniFont ENDP

IntroDraw PROC NEAR
    call EnsureUniFont
    cmp word ptr cs:[UniStatus], 1
    jne IntroFallback
    push ax
    ; MAP is indexed by physical glyph slot for Hangul and punctuation.
    movzx eax, ax
    shl eax, 2
    mov dword ptr cs:[UniSource], eax
    mov word ptr cs:[UniMoveLength], 4
    mov word ptr cs:[UniMoveLength+2], 0
    mov ax, word ptr cs:[UniXmsHandle]
    mov word ptr cs:[UniSourceHandle], ax
    mov word ptr cs:[UniDestinationHandle], 0
    mov word ptr cs:[UniDestination], OFFSET UniGlyphOffset
    mov word ptr cs:[UniDestination+2], cs
    call UniMoveBlock
    cmp ax, 1
    jne IntroReadFailed
    mov eax, dword ptr cs:[UniGlyphOffset]
    cmp eax, 0FFFFFFFFh
    je IntroReadFailed
    mov dword ptr cs:[UniSource], eax
    mov word ptr cs:[UniMoveLength], 128
    mov word ptr cs:[UniDestination], OFFSET IntroPixels
    call UniMoveBlock
    cmp ax, 1
    jne IntroReadFailed
    pop ax
    ; Same original pixel entry point and nine-word FNT cache contract as
    ; the verified Dalmoori renderer. No owner-loop pointers are modified.
    mov ax, cs
    sub ax, 3D02h-20AAh
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
    mov word ptr es:[008Ah], OFFSET IntroScratch
    mov ax, cs
    mov word ptr es:[008Ch], ax
    mov ax, word ptr ss:[bp-20]
    mov ds, ax
    push word ptr [bp+10]
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
    jmp OriginalDrawReturn
IntroReadFailed:
    pop ax
IntroFallback:
    jmp DalmuriRecord
IntroDraw ENDP

UniStatus dw 0
UniXmsEntry dd 0
UniXmsHandle dw 0
UniDosHandle dw 0FFFFh
UniFilesLeft dw 0
UniFileRead dd 0
UniRequested dw 0
UniGlyphOffset dd 0
UniMove LABEL BYTE
UniMoveLength dd 0
UniSourceHandle dw 0
UniSource dd 0
UniDestinationHandle dw 0
UniDestination dd 0
IntroScratch LABEL BYTE
    dw 153, 0500h, 14, 20, 22, 25, 23
    db 12h, 10h, 0, 0, 16, 16
    dw 25
    db 16, 0, 16
IntroPixels db 128 dup (0)
; Extra byte permits padding a full or odd final transfer without overrun.
UniTransfer db 257 dup (0)

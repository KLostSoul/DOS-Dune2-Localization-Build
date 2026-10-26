; Shared FASTBUILD and REVEAL extension used by editor builds.
; The modal handler and segment addresses are inserted by cheat_extra.py.
ORG 0990h

ExtraDispatch PROC NEAR
    or   al, al
    jz   UnknownCommand
    cmp  al, 1
    je   DoCredits
    cmp  al, 2
    je   DoWin
    cmp  al, 3
    je   DoLose
    cmp  al, 4
    je   ExtraFast
    cmp  al, 5
    je   ExtraReveal
    jmp  UnknownCommand
ExtraFast:
    mov  byte ptr cs:[EXTRA_PENDING], 4
    call ClosePanel
    jmp  Intercept
ExtraReveal:
    mov  byte ptr cs:[EXTRA_PENDING], 5
    call ClosePanel
    jmp  Intercept
ExtraDispatch ENDP

ResetExtraState PROC NEAR
    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 0
    mov  byte ptr cs:[EXTRA_PENDING], 0
    mov  byte ptr cs:[FAST_ENABLED], 0
    ret
ResetExtraState ENDP

ApplyExtraPending PROC NEAR
    cmp  byte ptr cs:[EXTRA_PENDING], 0
    je   ExtraPendingDone
    call IsGameInputOwner
    jnz  ExtraDiscard
    xor  ax, ax
    xchg al, byte ptr cs:[EXTRA_PENDING]
    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 0
    cmp  al, 4
    je   ExtraToggleFast
    cmp  al, 5
    jne  ExtraServiceDone
    call RevealNativeMap
    jmp  ExtraServiceDone
ExtraToggleFast:
    xor  byte ptr cs:[FAST_ENABLED], 1
    call ShowFastStatus
ExtraServiceDone:
    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 1
ExtraPendingDone:
    ret
ExtraDiscard:
    mov  byte ptr cs:[EXTRA_PENDING], 0
    ret
ApplyExtraPending ENDP

RevealNativeMap PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov  ax, cs
    sub  ax, HOOK_SEGMENT_ID
    add  ax, 32D0h
    mov  word ptr cs:[MAP_VALID_PTR+2], ax
    mov  word ptr cs:[MAP_REVEAL_PTR+2], ax
    xor  di, di
RevealNextTile:
    push di
    call dword ptr cs:[MAP_VALID_PTR]
    pop  cx
    or   ax, ax
    jz   RevealAdvance
    push word ptr ds:[3A2Ch]
    push di
    call dword ptr cs:[MAP_REVEAL_PTR]
    add  sp, 4
RevealAdvance:
    inc  di
    cmp  di, 1000h
    jb   RevealNextTile
    pop  es
    pop  ds
    pop  bp
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
RevealNativeMap ENDP

ScaleProduction PROC FAR
    ; 077B:04D2 held the original countdown write and threshold comparison.
    ; Keep the engine frame and existing fixed-point/resource calculation.
    push ax
    push bx
    push cx
    push dx
    push ds
    push es
    cmp  byte ptr cs:[FAST_ENABLED], 1
    jne  ProductionRestore
    les  bx, dword ptr ds:[84C0h]
    xor  dx, dx
    mov  dl, byte ptr es:[bx+08h]
    cmp  dx, word ptr ds:[3A2Ch]
    jne  ProductionRestore
    cmp  byte ptr es:[bx+02h], 0Dh
    je   ProductionRestore
    mov  ax, si
    mov  cx, 5
    mul  cx
    or   dx, dx
    jnz  ProductionOverflow
    mov  si, ax
    jmp  ProductionClamp
ProductionOverflow:
    mov  si, 0FFFFh
ProductionClamp:
    cmp  si, word ptr es:[bx+50h]
    jbe  ProductionRestore
    mov  si, word ptr es:[bx+50h]
ProductionRestore:
    pop  es
    pop  ds
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    mov  word ptr ss:[bp-10h], ax
    cmp  si, 0100h
    retf
ScaleProduction ENDP

; @@GAME_INPUT_BEGIN@@

ShowFastStatus PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov  ax, cs
    sub  ax, HOOK_SEGMENT_ID
    add  ax, 0EEDh
    mov  word ptr cs:[STATUS_MESSAGE_PTR+2], ax
    mov  ax, 0B80h
    cmp  byte ptr cs:[FAST_ENABLED], 1
    je   FastStatusSelected
    mov  ax, 0B92h
FastStatusSelected:
    push 2
    push cs
    push ax
    call dword ptr cs:[STATUS_MESSAGE_PTR]
    add  sp, 6
    pop  es
    pop  ds
    pop  bp
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
ShowFastStatus ENDP

ORG 0B80h
    db "FASTBUILD ON", 0
ORG 0B92h
    db "FASTBUILD OFF", 0

ORG 0C00h
    db 7, "CREDITS", 1
    db 3, "WIN", 2
    db 4, "LOSE", 3
    db 9, "FASTBUILD", 4
    db 6, "REVEAL", 5
    db 0

ORG 0C40h
    db 0
    db 0
    dw 0057h, 0
    dw 00CAh, 0
    dw 09ABh, 0

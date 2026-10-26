; Ordos mission-8 private scene list. The verified Harkonnen branch and
; shared animation/subtitle player are not modified.
.386
SCENES SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:SCENES
ORG 0E8h
OriginalBranchDone LABEL NEAR
ORG 0F0h
OriginalIntermission LABEL NEAR
ORG ORIGINAL_CODE_SIZE
OrdosSecondScene PROC NEAR
    push si
    push di
    push es
    sub sp, 32
    mov bx, sp
    mov di, bx
    push ss
    pop es
    mov si, 1D61h
    mov cx, 16
    cld
    rep movsw
    ; 75 -> 135 units adds 360 ticks. Mode 1 loops the same open WSA.
    ; 135*6/50 = 16 ticks/frame (original: 75*6/27 = 16).
    mov word ptr es:[bx+20], 3287h
    mov word ptr es:[bx+22], 0041h
    mov ax, 22h
    push ax
    push ds
    mov ax, 1DC0h
    push ax
    push ds
    mov ax, 1DBDh
    push ax
    push ds
    mov ax, 1D81h
    push ax
    push ss
    push bx
    push cs
    call OriginalIntermission
    add sp, 18
    add sp, 32
    pop es
    pop di
    pop si
    jmp OriginalBranchDone
OrdosSecondScene ENDP
SCENES ENDS
END

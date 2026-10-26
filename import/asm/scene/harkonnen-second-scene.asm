; Private scene-list construction in overlay 32B1's Harkonnen mission-8
; branch only. The scene list lives in SS, independent of overlay eviction.
.386
SCENES SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:SCENES
ORG 0E8h
OriginalBranchDone LABEL NEAR
ORG 0F0h
OriginalIntermission LABEL NEAR
ORG 0131h
HarkonnenSecondScene PROC NEAR
    push si
    push di
    push es
    sub sp, 32
    mov bx, sp
    mov di, bx
    push ss
    pop es
    mov si, 1E35h
    mov cx, 16
    cld
    rep movsw
    ; Extend only the final EFINALA scene from 85 to 145 duration units.
    ; Native mode 1 wraps the WSA frame index, keeping the same WSA open.
    ; 145*6/48 = 18 ticks per frame (original: 85*6/27 = 18).
    ; Caption events still advance through the original player, including 320.
    mov word ptr es:[bx+20], 3091h
    mov word ptr es:[bx+22], 0041h
    ; Same original nine arguments, except the private SS scene-list pointer.
    mov ax, 22h
    push ax
    push ds
    mov ax, 1E9Eh
    push ax
    push ds
    mov ax, 1E9Bh
    push ax
    push ds
    mov ax, 1E55h
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
HarkonnenSecondScene ENDP
SCENES ENDS
END

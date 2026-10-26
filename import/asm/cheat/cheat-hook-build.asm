; Resident Dune II cheat-command hook for the verified 16x16 Hangul build.
; All addresses are image-relative segment offsets. The builder validates the
; MZ relocations and supplies the segment IDs used below.

.386
CHEAT SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:CHEAT

HOOK_SEGMENT_ID EQU 3D64h
GAME_SEGMENT_DELTA EQU HOOK_SEGMENT_ID-27ECh
DATA_SEGMENT_DELTA EQU HOOK_SEGMENT_ID-3342h
RESULT_SEGMENT_DELTA EQU HOOK_SEGMENT_ID-1223h
VIDEO_SEGMENT_DELTA EQU HOOK_SEGMENT_ID-20AAh
STACK_SEGMENT_ID EQU 3DFDh         ; first paragraph after the packed 0x0990-byte module
ORIGINAL_STACK_SEGMENT_ID EQU 3CFAh
STACK_SHIFT_PARAGRAPHS EQU STACK_SEGMENT_ID-ORIGINAL_STACK_SEGMENT_ID
CREDITS_AMOUNT EQU 2710h         ; 10,000 credits; baseline verifier substitutes 03E8h

MODE_VAR EQU 0816h
DISPLAY_MODE_VAR EQU 0817h
COMMAND_LENGTH_VAR EQU 0818h
STATUS_VAR EQU 0819h
CONSUME_VAR EQU 081Ah
PENDING_RESULT_VAR EQU 081Bh
RAW_SCAN_VAR EQU 081Ch
RESULT_TARGET_VAR EQU 081Eh
ORIGINAL_ENTRY_PTR EQU 0820h
COMMAND_BUFFER EQU 0824h
COMMAND_TABLE EQU 0834h
SCAN_MAP EQU 0849h
GLYPH_TABLE EQU 086Ch
TITLE_TEXT EQU 0922h
USAGE_TEXT EQU 092Dh
UNKNOWN_TEXT EQU 0941h
DRAW_TEXT_PTR EQU 0950h
DRAW_TEXT_LENGTH EQU 0952h
DRAW_X_VAR EQU 0954h
DRAW_Y_VAR EQU 0956h
PIXEL_BITS_VAR EQU 0958h
PIXEL_COLOR_VAR EQU 095Ah
KEY_DOWN_MAP EQU 095Ch
XMS_ENTRY_PTR EQU 096Ch
XMS_HANDLE_VAR EQU 0970h
XMS_READY_VAR EQU 0972h
XMS_SAVE_OK_VAR EQU 0973h
XMS_MOVE EQU 0974h
PANEL_PAGE_SEG_VAR EQU 0984h
PANEL_ROW_VAR EQU 0986h
PANEL_VIDEO_OFFSET_VAR EQU 0988h
PANEL_XMS_OFFSET_VAR EQU 098Ah
PANEL_COPY_DIRECTION_VAR EQU 098Ch
GAME_INPUT_ACTIVE_VAR EQU 098Dh
PANEL_DIRTY_VAR EQU 098Eh

PANEL_WIDTH EQU 128
PANEL_HEIGHT EQU 32
PANEL_X EQU 16
PANEL_Y EQU 160
PANEL_TEXT_X EQU PANEL_X+8
PANEL_VIDEO_OFFSET EQU PANEL_Y*320+PANEL_X

ORG 0000h
BootSetStack PROC FAR
    ; The original Borland startup sizes SS:SP immediately after this site.
    ; Move the stack base to the end of the MZ image so its downward-growing
    ; stack cannot overwrite the appended resident module.
    call InitializeXms
    mov  dx, cs
    sub  dx, HOOK_SEGMENT_ID
    add  dx, STACK_SEGMENT_ID
    mov  ax, cs
    sub  ax, HOOK_SEGMENT_ID
    add  ax, 3342h
    mov  es, ax
    sub  bp, STACK_SHIFT_PARAGRAPHS
    mov  bx, cs
    sub  bx, HOOK_SEGMENT_ID
    push bx
    push 0062h
    retf
BootSetStack ENDP

ORG 0040h
CheatKeyHook PROC FAR
    ; Mirror the displaced PUSH BP / MOV BP,SP / SUB SP,4 prologue.
    push bp
    mov  bp, sp
    sub  sp, 4
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es

    mov  byte ptr cs:[CONSUME_VAR], 0

    ; Only the INT 09h event path at 27EC:0F0B is intercepted.
    cmp  word ptr ss:[bp+2], 0F0Bh
    jne  ChainOriginal
    mov  ax, cs
    sub  ax, GAME_SEGMENT_DELTA
    cmp  word ptr ss:[bp+4], ax
    jne  ChainOriginal

    ; 27EC:0D51 stores the raw scan byte before calling this function.
    mov  es, ax
    mov  bx, word ptr es:[025Eh]
    dec  bx
    and  bx, 000Fh
    mov  al, byte ptr es:[bx+024Ch]
    mov  byte ptr cs:[RAW_SCAN_VAR], al

    ; Keep repeat bookkeeping valid even when a menu owns the keyboard.
    test al, 80h
    jz   CheckInputOwner
    and  al, 7Fh
    call ClearKeyDown
    mov  al, byte ptr cs:[RAW_SCAN_VAR]
CheckInputOwner:
    call IsGameInputOwner
    jnz  ChainOriginal

    cmp  byte ptr cs:[MODE_VAR], 0
    jne  CaptureMode

    ; Enter opens the command line only in DOS text mode or VGA mode 13h and
    ; only after the human player record has been installed.
    test al, 80h
    jnz  ChainOriginal
    cmp  al, 1Ch
    jne  ChainOriginal
    ; ES currently points at the game segment; read the BIOS mode from 0040h.
    mov  ax, 0040h
    mov  es, ax
    mov  al, byte ptr es:[0049h]
    mov  byte ptr cs:[DISPLAY_MODE_VAR], al
    cmp  al, 13h
    jne  ChainOriginal
    mov  ax, cs
    sub  ax, DATA_SEGMENT_DELTA
    mov  ds, ax
    mov  ax, word ptr ds:[3A30h]
    or   ax, ax
    jz   ChainOriginal

    mov  byte ptr cs:[MODE_VAR], 1
    mov  byte ptr cs:[COMMAND_LENGTH_VAR], 0
    mov  byte ptr cs:[STATUS_VAR], 0
    mov  byte ptr cs:[CONSUME_VAR], 1
    mov  al, 1Ch                ; consume the opening Enter through key repeat
    call MarkKeyDown
    mov  byte ptr cs:[PANEL_DIRTY_VAR], 1
    jmp  Intercept

CaptureMode:
    mov  al, byte ptr cs:[RAW_SCAN_VAR]
    test al, 80h
    jnz  CaptureRelease

    ; Key-down events are consumed while the command line owns input.
    mov  byte ptr cs:[CONSUME_VAR], 1
    call MarkKeyDown
    or   al, al
    jnz  Intercept               ; ignore typematic repeats
    mov  al, byte ptr cs:[RAW_SCAN_VAR]
    cmp  al, 01h
    je   CancelCommand
    cmp  al, 0Eh
    je   BackspaceCommand
    cmp  al, 1Ch
    je   SubmitCommand

    call ScanToAscii
    or   al, al
    jz   RedrawCommand
    cmp  byte ptr cs:[COMMAND_LENGTH_VAR], 16
    jae  RedrawCommand
    xor  bx, bx
    mov  bl, byte ptr cs:[COMMAND_LENGTH_VAR]
    mov  byte ptr cs:[COMMAND_BUFFER+bx], al
    inc  byte ptr cs:[COMMAND_LENGTH_VAR]
    mov  byte ptr cs:[STATUS_VAR], 0
RedrawCommand:
    mov  byte ptr cs:[PANEL_DIRTY_VAR], 1
    jmp  Intercept

BackspaceCommand:
    cmp  byte ptr cs:[COMMAND_LENGTH_VAR], 0
    je   RedrawCommand
    dec  byte ptr cs:[COMMAND_LENGTH_VAR]
    jmp  RedrawCommand

SubmitCommand:
    cmp  byte ptr cs:[COMMAND_LENGTH_VAR], 0
    jne  SubmitNonEmptyCommand
    call ClosePanel
    jmp  Intercept
SubmitNonEmptyCommand:
    call FindCommand
    or   al, al
    jz   UnknownCommand
    cmp  al, 1
    je   DoCredits
    cmp  al, 2
    je   DoWin
    cmp  al, 3
    je   DoLose
    jmp  UnknownCommand

DoCredits:
    call ApplyCredits
    or   al, al
    jz   UnknownCommand
    call ClosePanel
    jmp  Intercept

DoWin:
    mov  byte ptr cs:[PENDING_RESULT_VAR], 1
    call RequestResult
    call ClosePanel
    jmp  Intercept

DoLose:
    mov  byte ptr cs:[PENDING_RESULT_VAR], 2
    call RequestResult
    call ClosePanel
    jmp  Intercept

UnknownCommand:
    mov  byte ptr cs:[STATUS_VAR], 1
    mov  byte ptr cs:[COMMAND_LENGTH_VAR], 0
    jmp  RedrawCommand

CancelCommand:
    call ClosePanel
    jmp  Intercept

CaptureRelease:
    ; Let the original routine clear any key-state bit established before the
    ; console opened, then suppress the event at AfterKeyHook.
    mov  byte ptr cs:[CONSUME_VAR], 1
    and  al, 7Fh
    call ClearKeyDown
    jmp  ChainOriginal

ChainOriginal:
    ; Restore the caller-visible machine state while retaining the emulated
    ; original BP frame and four-byte local area.
    mov  word ptr cs:[ORIGINAL_ENTRY_PTR], 0A5Ah
    mov  ax, cs
    sub  ax, GAME_SEGMENT_DELTA
    mov  word ptr cs:[ORIGINAL_ENTRY_PTR+2], ax
    pop  es
    pop  ds
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    popf
    jmp  dword ptr cs:[ORIGINAL_ENTRY_PTR]

Intercept:
    pop  es
    pop  ds
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    popf
    mov  sp, bp
    pop  bp
    retf
CheatKeyHook ENDP

ORG 0200h
AfterKeyHook PROC FAR
    ; This replaces 27EC:0F0B's POP AX / CMP AL,6E / JNE 0F1F sequence.
    pop  ax
    cmp  byte ptr cs:[CONSUME_VAR], 0
    je   PreserveOriginalDispatch
    mov  byte ptr cs:[CONSUME_VAR], 0
    mov  bx, cs
    sub  bx, GAME_SEGMENT_DELTA
    push bx
    push 0F58h                 ; acknowledge IRQ and IRET without BIOS chaining
    retf

PreserveOriginalDispatch:
    cmp  al, 6Eh
    jne  DispatchOther
    mov  bx, cs
    sub  bx, GAME_SEGMENT_DELTA
    push bx
    push 0F10h
    retf
DispatchOther:
    mov  bx, cs
    sub  bx, GAME_SEGMENT_DELTA
    push bx
    push 0F1Fh
    retf
AfterKeyHook ENDP

ORG 0240h
IsGameInputOwner PROC NEAR
    push ax
    push ds
    cmp  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 1
    jne  InputOwnerDenied
    mov  ax, cs
    sub  ax, DATA_SEGMENT_DELTA
    mov  ds, ax
    cmp  word ptr ds:[38ECh], 0
    je   InputOwnerDenied
    ; The GUI core stores its current widget-list head at 1902:1904.
    ; The normal game loop passes the game list at 3C1A:3C1C.
    mov  ax, word ptr ds:[3C1Ah]
    cmp  ax, word ptr ds:[1902h]
    jne  InputOwnerDenied
    mov  ax, word ptr ds:[3C1Ch]
    cmp  ax, word ptr ds:[1904h]
    jne  InputOwnerDenied
    ; Equal pointers must also be non-null. ZF=1 means allowed.
    or   ax, word ptr ds:[3C1Ah]
    jz   InputOwnerDenied
    cmp  ax, ax
    jmp  InputOwnerDone
InputOwnerDenied:
    or   al, 1
InputOwnerDone:
    pop  ds
    pop  ax
    ret
IsGameInputOwner ENDP

ORG 02A0h
GameInputBegin PROC FAR
    ; Only 044B:0309 calls this. Reproduce its page=0 setter exactly:
    ; AX returns the old page, the caller still removes its zero argument.
    ; Own the cheat window here, outside the keyboard interrupt. While it is
    ; open this normal game iteration waits, so world copies cannot erase it.
    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 1
    mov  ax, word ptr ds:[6D1Dh]
    mov  word ptr ds:[6D1Dh], 0
    pushf
    pusha
    push ds
    push es
    cld
    cmp  byte ptr cs:[MODE_VAR], 0
    je   ModalDone
    call SavePanel
    cmp  byte ptr cs:[XMS_SAVE_OK_VAR], 1
    jne  ModalSaveFailed
    mov  byte ptr cs:[PANEL_DIRTY_VAR], 1
ModalLoop:
    cmp  byte ptr cs:[MODE_VAR], 0
    je   ModalRestore
    cmp  byte ptr cs:[PANEL_DIRTY_VAR], 0
    je   ModalWait
    ; Clear before drawing so a new IRQ update cannot be lost.
    mov  byte ptr cs:[PANEL_DIRTY_VAR], 0
    call DrawPanel
    jmp  ModalLoop
ModalWait:
    sti
    hlt
    jmp  ModalLoop
ModalRestore:
    call RestorePanel
    jmp  ModalDone
ModalSaveFailed:
    call ClosePanel
ModalDone:
    pop  es
    pop  ds
    popa
    popf
    retf
GameInputBegin ENDP

ORG 0300h
ResultHook PROC FAR
    ; Replaces the mission result evaluator's OR/JNE/JMP branch at 1223:0328.
    push bp
    mov  bp, sp
    push ax
    push bx
    push ds

    cmp  byte ptr cs:[PENDING_RESULT_VAR], 1
    je   ForceWin
    cmp  byte ptr cs:[PENDING_RESULT_VAR], 2
    je   ForceLose
    mov  ax, word ptr ss:[bp-2]
    or   ax, ax
    jnz  SelectWin
SelectLose:
    mov  word ptr cs:[RESULT_TARGET_VAR], 048Dh
    jmp  TransferResult
SelectWin:
    mov  word ptr cs:[RESULT_TARGET_VAR], 032Fh
    jmp  TransferResult
ForceWin:
    mov  word ptr cs:[RESULT_TARGET_VAR], 032Fh
    jmp  TransferResult
ForceLose:
    mov  word ptr cs:[RESULT_TARGET_VAR], 048Dh

TransferResult:
    ; This branch is reached only after an actual win/loss was selected,
    ; unlike 1223:02A9, which is polled during ordinary gameplay as well.
    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 0
    mov  byte ptr cs:[PENDING_RESULT_VAR], 0
    mov  ax, cs
    sub  ax, DATA_SEGMENT_DELTA
    mov  ds, ax
    mov  word ptr ds:[3792h], 0
    pop  ds
    pop  bx
    pop  ax
    mov  sp, bp
    pop  bp
    add  sp, 4                 ; discard this helper's FAR CALL return frame
    mov  ax, cs
    sub  ax, RESULT_SEGMENT_DELTA
    push ax
    push word ptr cs:[RESULT_TARGET_VAR]
    retf
ResultHook ENDP

; The three far-call entry points remain fixed; pack helpers after ResultHook.
ORG 0370h
ScanToAscii PROC NEAR
    cmp  al, 010h
    jb   ScanUnknown
    cmp  al, 032h
    ja   ScanUnknown
    sub  al, 010h
    xor  bx, bx
    mov  bl, al
    mov  al, byte ptr cs:[SCAN_MAP+bx]
    ret
ScanUnknown:
    xor  al, al
    ret
ScanToAscii ENDP

MarkKeyDown PROC NEAR
    push bx
    push cx
    push dx
    push di
    and  al, 7Fh
    mov  bl, al
    mov  cl, 3
    shr  al, cl
    xor  ah, ah
    mov  di, ax
    and  bl, 7
    mov  cl, bl
    mov  dl, 1
    shl  dl, cl
    mov  al, byte ptr cs:[KEY_DOWN_MAP+di]
    test al, dl
    jnz  KeyWasDown
    or   al, dl
    mov  byte ptr cs:[KEY_DOWN_MAP+di], al
    xor  al, al
    jmp  MarkDownDone
KeyWasDown:
    mov  al, 1
MarkDownDone:
    pop  di
    pop  dx
    pop  cx
    pop  bx
    ret
MarkKeyDown ENDP

ClearKeyDown PROC NEAR
    push bx
    push cx
    push di
    and  al, 7Fh
    mov  bl, al
    mov  cl, 3
    shr  al, cl
    xor  ah, ah
    mov  di, ax
    and  bl, 7
    mov  cl, bl
    mov  al, 1
    shl  al, cl
    not  al
    and  byte ptr cs:[KEY_DOWN_MAP+di], al
    pop  di
    pop  cx
    pop  bx
    ret
ClearKeyDown ENDP

FindCommand PROC NEAR
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    push cs
    pop  ds
    push cs
    pop  es
    mov  si, COMMAND_TABLE
FindNext:
    lodsb
    or   al, al
    jz   FindNotFound
    mov  dl, al
    push si                    ; IRQ-local registry cursor; never share draw state
    cmp  al, byte ptr cs:[COMMAND_LENGTH_VAR]
    jne  FindSkip
    mov  di, COMMAND_BUFFER
    xor  cx, cx
    mov  cl, dl
    repe cmpsb
    jne  FindSkip
    mov  al, byte ptr cs:[si]
    pop  si
    jmp  FindDone
FindSkip:
    pop  si
    xor  bx, bx
    mov  bl, dl
    add  si, bx
    inc  si                     ; skip command handler ID
    jmp  FindNext
FindNotFound:
    xor  al, al
FindDone:
    pop  es
    pop  ds
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    ret
FindCommand ENDP

ApplyCredits PROC NEAR
    push bx
    push ds
    push es
    mov  ax, cs
    sub  ax, DATA_SEGMENT_DELTA
    mov  ds, ax
    les  bx, dword ptr ds:[3A2Eh]
    mov  ax, es
    or   ax, ax
    jz   CreditsFailed
    or   bx, bx
    jz   CreditsFailed
    mov  ax, word ptr es:[bx+12h]
    add  ax, CREDITS_AMOUNT
    jnc  CreditsValueReady
    mov  ax, 0FFFFh
CreditsValueReady:
    mov  word ptr es:[bx+12h], ax
    mov  word ptr ds:[38A8h], ax
    mov  al, 1
    jmp  CreditsDone
CreditsFailed:
    xor  al, al
CreditsDone:
    pop  es
    pop  ds
    pop  bx
    ret
ApplyCredits ENDP

RequestResult PROC NEAR
    push ax
    push ds
    mov  ax, cs
    sub  ax, DATA_SEGMENT_DELTA
    mov  ds, ax
    mov  word ptr ds:[3792h], 1
    pop  ds
    pop  ax
    ret
RequestResult ENDP

SavePanel PROC NEAR
    push ax
    push bx
    push cx
    push di
    push si
    push ds
    push es
    push cs
    pop  ds
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 0
    cmp  byte ptr cs:[XMS_READY_VAR], 0
    je   SavePanelDone
    call SelectVideoPage
    mov  word ptr cs:[PANEL_PAGE_SEG_VAR], ax
    mov  al, 0
    call CopyVideoPanelRows
SavePanelDone:
    pop  es
    pop  ds
    pop  si
    pop  di
    pop  cx
    pop  bx
    pop  ax
    ret
SavePanel ENDP

RestorePanel PROC NEAR
    push ax
    push bx
    push cx
    push di
    push si
    push ds
    push es
    push cs
    pop  ds
    cmp  byte ptr cs:[XMS_SAVE_OK_VAR], 1
    jne  RestorePanelDone
    mov  al, 1
    call CopyVideoPanelRows
RestorePanelDone:
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 0
    pop  es
    pop  ds
    pop  si
    pop  di
    pop  cx
    pop  bx
    pop  ax
    ret
RestorePanel ENDP

DrawPanel PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push di
    push si
    push ds
    push es
    push cs
    pop  ds
    call SelectVideoPage
    cmp  ax, word ptr cs:[PANEL_PAGE_SEG_VAR]
    je   DrawPanelOnPage
    ; The game can change its drawing page while the input is open.
    ; Move the saved rectangle to the new page before drawing there.
    call RestorePanel
    call SavePanel
DrawPanelOnPage:
    call DrawVideoPanel
DrawPanelDone:
    pop  es
    pop  ds
    pop  si
    pop  di
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
DrawPanel ENDP

DrawVideoPanel PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push di
    push si
    push es
    push ds
    call SelectVideoPage
    mov  es, ax
    push cs
    pop  ds
    mov  di, PANEL_VIDEO_OFFSET
    mov  bx, PANEL_HEIGHT
VideoFillRow:
    mov  al, 0E9h
    mov  cx, PANEL_WIDTH
    rep  stosb
    add  di, 320-PANEL_WIDTH
    dec  bx
    jnz  VideoFillRow

    ; Thin raised frame: white upper/left edge, dark lower/right edge.
    mov  di, PANEL_VIDEO_OFFSET
    mov  al, 0Fh
    mov  cx, PANEL_WIDTH
    rep  stosb
    mov  di, PANEL_VIDEO_OFFSET+(PANEL_HEIGHT-1)*320
    mov  al, 0EBh
    mov  cx, PANEL_WIDTH
    rep  stosb
    mov  bx, PANEL_HEIGHT
    mov  di, PANEL_VIDEO_OFFSET
VideoLeftBorder:
    mov  byte ptr es:[di], 0Fh
    mov  byte ptr es:[di+PANEL_WIDTH-1], 0EBh
    add  di, 320
    dec  bx
    jnz  VideoLeftBorder

    mov  si, TITLE_TEXT
    mov  cx, 11
    mov  bx, PANEL_TEXT_X
    mov  dx, PANEL_Y+2
    mov  al, 0Fh
    call DrawPixelString
    mov  si, COMMAND_BUFFER
    xor  cx, cx
    mov  cl, byte ptr cs:[COMMAND_LENGTH_VAR]
    mov  bx, PANEL_TEXT_X
    mov  dx, PANEL_Y+11
    mov  al, 0Fh
    call DrawPixelString
    cmp  byte ptr cs:[STATUS_VAR], 0
    jne  VideoUnknownStatus
    mov  si, USAGE_TEXT
    mov  cx, 18
    jmp  VideoStatusDraw
VideoUnknownStatus:
    mov  si, UNKNOWN_TEXT
    mov  cx, 15
VideoStatusDraw:
    mov  bx, PANEL_TEXT_X
    mov  dx, PANEL_Y+20
    mov  al, 0Fh
    call DrawPixelString

    pop  ds
    pop  es
    pop  si
    pop  di
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
DrawVideoPanel ENDP

SelectVideoPage PROC NEAR
    ; Match the game's 20AA:0E02 active-page table lookup.
    push bx
    push ds
    push si
    mov  bx, cs
    sub  bx, VIDEO_SEGMENT_DELTA
    mov  es, bx
    mov  ds, word ptr es:[1Bh]
    mov  si, word ptr es:[19h]
    lodsb
    xor  ah, ah
    and  ax, 001Eh
    shl  ax, 1
    mov  ds, word ptr es:[17h]
    mov  si, word ptr es:[15h]
    add  si, ax
    lodsw
    pop  si
    pop  ds
    pop  bx
    ret
SelectVideoPage ENDP

CopyVideoPanelRows PROC NEAR
    ; AL=0 saves the exact rectangle to packed XMS; AL=1 restores it.
    push ax
    push bx
    push cx
    push dx
    push di
    push si
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 0
    mov  byte ptr cs:[PANEL_COPY_DIRECTION_VAR], al
    mov  word ptr cs:[PANEL_ROW_VAR], PANEL_HEIGHT
    mov  word ptr cs:[PANEL_VIDEO_OFFSET_VAR], PANEL_VIDEO_OFFSET
    mov  word ptr cs:[PANEL_XMS_OFFSET_VAR], 0
CopyVideoPanelRow:
    mov  word ptr cs:[XMS_MOVE], PANEL_WIDTH
    mov  word ptr cs:[XMS_MOVE+2], 0
    cmp  byte ptr cs:[PANEL_COPY_DIRECTION_VAR], 0
    jne  CopyVideoPanelFromXms
    mov  word ptr cs:[XMS_MOVE+4], 0
    mov  ax, word ptr cs:[PANEL_VIDEO_OFFSET_VAR]
    mov  word ptr cs:[XMS_MOVE+6], ax
    mov  ax, word ptr cs:[PANEL_PAGE_SEG_VAR]
    mov  word ptr cs:[XMS_MOVE+8], ax
    mov  ax, word ptr cs:[XMS_HANDLE_VAR]
    mov  word ptr cs:[XMS_MOVE+10], ax
    mov  ax, word ptr cs:[PANEL_XMS_OFFSET_VAR]
    mov  word ptr cs:[XMS_MOVE+12], ax
    mov  word ptr cs:[XMS_MOVE+14], 0
    call MoveScreenToXms
    jc   CopyVideoPanelFailed
    jmp  CopyVideoPanelNextRow
CopyVideoPanelFromXms:
    mov  ax, word ptr cs:[XMS_HANDLE_VAR]
    mov  word ptr cs:[XMS_MOVE+4], ax
    mov  ax, word ptr cs:[PANEL_XMS_OFFSET_VAR]
    mov  word ptr cs:[XMS_MOVE+6], ax
    mov  word ptr cs:[XMS_MOVE+8], 0
    mov  word ptr cs:[XMS_MOVE+10], 0
    mov  ax, word ptr cs:[PANEL_VIDEO_OFFSET_VAR]
    mov  word ptr cs:[XMS_MOVE+12], ax
    mov  ax, word ptr cs:[PANEL_PAGE_SEG_VAR]
    mov  word ptr cs:[XMS_MOVE+14], ax
    call MoveScreenFromXms
CopyVideoPanelNextRow:
    add  word ptr cs:[PANEL_VIDEO_OFFSET_VAR], 320
    add  word ptr cs:[PANEL_XMS_OFFSET_VAR], PANEL_WIDTH
    dec  word ptr cs:[PANEL_ROW_VAR]
    jnz  CopyVideoPanelRow
    cmp  byte ptr cs:[PANEL_COPY_DIRECTION_VAR], 0
    jne  CopyVideoPanelDone
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 1
    jmp  CopyVideoPanelDone
CopyVideoPanelFailed:
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 0
CopyVideoPanelDone:
    pop  si
    pop  di
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
CopyVideoPanelRows ENDP

DrawPixelString PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push si
    mov  word ptr cs:[DRAW_TEXT_PTR], si
    mov  word ptr cs:[DRAW_TEXT_LENGTH], cx
    mov  word ptr cs:[DRAW_X_VAR], bx
    mov  word ptr cs:[DRAW_Y_VAR], dx
    mov  byte ptr cs:[PIXEL_COLOR_VAR], al
PixelStringLoop:
    cmp  word ptr cs:[DRAW_TEXT_LENGTH], 0
    je   PixelStringDone
    mov  si, word ptr cs:[DRAW_TEXT_PTR]
    mov  al, byte ptr cs:[si]
    inc  si
    mov  word ptr cs:[DRAW_TEXT_PTR], si
    call DrawPixelGlyph
    add  word ptr cs:[DRAW_X_VAR], 6
    dec  word ptr cs:[DRAW_TEXT_LENGTH]
    jmp  PixelStringLoop
PixelStringDone:
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
DrawPixelString ENDP

DrawPixelGlyph PROC NEAR
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    cmp  al, 'A'
    jb   PixelGlyphBlank
    cmp  al, 'Z'
    ja   PixelGlyphBlank
    sub  al, 'A'
    xor  ah, ah
    mov  bx, 7
    mul  bx
    mov  si, GLYPH_TABLE
    add  si, ax
    mov  bp, 7
PixelGlyphRow:
    mov  al, byte ptr cs:[si]
    inc  si
    mov  byte ptr cs:[PIXEL_BITS_VAR], al
    mov  ax, word ptr cs:[DRAW_Y_VAR]
    mov  bx, 320
    mul  bx
    add  ax, word ptr cs:[DRAW_X_VAR]
    mov  di, ax
    mov  bl, 10h
    mov  cx, 5
PixelGlyphColumn:
    test byte ptr cs:[PIXEL_BITS_VAR], bl
    jz   PixelGlyphNoPixel
    mov  al, byte ptr cs:[PIXEL_COLOR_VAR]
    mov  byte ptr es:[di], al
PixelGlyphNoPixel:
    inc  di
    shr  bl, 1
    loop PixelGlyphColumn
    inc  word ptr cs:[DRAW_Y_VAR]
    dec  bp
    jnz  PixelGlyphRow
    sub  word ptr cs:[DRAW_Y_VAR], 7
    jmp  PixelGlyphDone
PixelGlyphBlank:
    ; Spaces still advance by one six-pixel cell in DrawPixelString.
PixelGlyphDone:
    pop  bp
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
DrawPixelGlyph ENDP

ClosePanel PROC NEAR
    ; No graphics or XMS inside the keyboard interrupt. The game-loop owner
    ; restores the saved background before it resumes the world simulation.
    mov  byte ptr cs:[MODE_VAR], 0
    mov  byte ptr cs:[COMMAND_LENGTH_VAR], 0
    mov  byte ptr cs:[STATUS_VAR], 0
    ret
ClosePanel ENDP

InitializeXms PROC NEAR
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov  ax, 4300h
    int  2Fh
    cmp  al, 80h
    jne  InitializeXmsDone
    mov  ax, 4310h
    int  2Fh
    mov  word ptr cs:[XMS_ENTRY_PTR], bx
    mov  word ptr cs:[XMS_ENTRY_PTR+2], es
    mov  ah, 09h
    mov  dx, 4
    call dword ptr cs:[XMS_ENTRY_PTR]
    cmp  ax, 1
    jne  InitializeXmsDone
    mov  word ptr cs:[XMS_HANDLE_VAR], dx
    mov  byte ptr cs:[XMS_READY_VAR], 1
InitializeXmsDone:
    pop  es
    pop  ds
    pop  bp
    pop  di
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    popf
    ret
InitializeXms ENDP

MoveScreenToXms PROC NEAR
    push ds
    push si
    push cs
    pop  ds
    mov  si, XMS_MOVE
    mov  ah, 0Bh
    call dword ptr cs:[XMS_ENTRY_PTR]
    pop  si
    pop  ds
    cmp  ax, 1
    jne  MoveScreenToXmsFailed
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 1
    clc
    ret
MoveScreenToXmsFailed:
    mov  byte ptr cs:[XMS_SAVE_OK_VAR], 0
    stc
    ret
MoveScreenToXms ENDP

MoveScreenFromXms PROC NEAR
    push ds
    push si
    push cs
    pop  ds
    mov  si, XMS_MOVE
    mov  ah, 0Bh
    call dword ptr cs:[XMS_ENTRY_PTR]
    pop  si
    pop  ds
    ret
MoveScreenFromXms ENDP

ORG 0816h
    db 0
    db 0
    db 0
    db 0
    db 0
    db 0
    db 0
    db 0
    dw 0
    dd 0

ORG 0824h
    db 16 dup (0)

; Extensible command registry: length, uppercase ASCII name, handler ID.
ORG 0834h
    db 7, "CREDITS", 1
    db 3, "WIN", 2
    db 4, "LOSE", 3
    db 0

; Compact PC/AT set-1 scan-code table for A-Z (scan codes 10h..32h).
ORG 0849h
    db 'Q','W','E','R','T','Y','U','I','O','P',0,0,0,0,'A','S'
    db 'D','F','G','H','J','K','L',0,0,0,0,0,'Z','X','C','V'
    db 'B','N','M'

; 5x7 uppercase font, one byte per row, columns in bits 4..0.
ORG 086Ch
    db 0Eh,11h,11h,1Fh,11h,11h,11h
    db 1Eh,11h,11h,1Eh,11h,11h,1Eh
    db 0Eh,11h,10h,10h,10h,11h,0Eh
    db 1Eh,11h,11h,11h,11h,11h,1Eh
    db 1Fh,10h,10h,1Eh,10h,10h,1Fh
    db 1Fh,10h,10h,1Eh,10h,10h,10h
    db 0Eh,11h,10h,17h,11h,11h,0Fh
    db 11h,11h,11h,1Fh,11h,11h,11h
    db 0Eh,04h,04h,04h,04h,04h,0Eh
    db 07h,02h,02h,02h,12h,12h,0Ch
    db 11h,12h,14h,18h,14h,12h,11h
    db 10h,10h,10h,10h,10h,10h,1Fh
    db 11h,1Bh,15h,15h,11h,11h,11h
    db 11h,19h,15h,13h,11h,11h,11h
    db 0Eh,11h,11h,11h,11h,11h,0Eh
    db 1Eh,11h,11h,1Eh,10h,10h,10h
    db 0Eh,11h,11h,11h,15h,12h,0Dh
    db 1Eh,11h,11h,1Eh,14h,12h,11h
    db 0Fh,10h,10h,0Eh,01h,01h,1Eh
    db 1Fh,04h,04h,04h,04h,04h,04h
    db 11h,11h,11h,11h,11h,11h,0Eh
    db 11h,11h,11h,11h,11h,0Ah,04h
    db 11h,11h,11h,15h,15h,15h,0Ah
    db 11h,11h,0Ah,04h,0Ah,11h,11h
    db 11h,11h,0Ah,04h,04h,04h,04h
    db 1Fh,01h,02h,04h,08h,10h,1Fh

ORG 0922h
    db "CHEAT ENTRY"
ORG 092Dh
    db "ENTER=RUN ESC=EXIT"
ORG 0941h
    db "UNKNOWN COMMAND"

ORG 0950h
    dw 6 dup (0)

ORG 095Ch
    db 16 dup (0)
ORG 096Ch
    dd 0
    dw 0
    db 0
    db 0
ORG 0974h
    db 16 dup (0)
ORG 0984h
    dw 0
    dw 0
    dw 0
    dw 0
    db 0

CHEAT ENDS
END BootSetStack

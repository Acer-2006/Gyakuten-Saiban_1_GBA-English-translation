#ifndef GUARD_EN_MENU_H
#define GUARD_EN_MENU_H

// English patch: the save, load and erase screens as the DS English release
// shows them (src/en_menu.c, graphics from tools/en/make_menus.py).

#define EN_MENU_SAVE  1   // save prompt during the game / at the end of a part
#define EN_MENU_LOAD  2   // "From save point." / "From chapter start."
#define EN_MENU_CLEAR 3   // erase all data (no hint line)

#define EN_MENU_TEXT_PAL 13   // OBJ palette of the plate text

// what a confirmed choice does on screen (EnMenuConfirm)
#define EN_CONFIRM_SAVE_YES 0   // blink, the other button flips away, Yes slides to the middle and turns into "Saving..."
#define EN_CONFIRM_STAY     1   // blink, the other button flips away, the chosen one stays
#define EN_CONFIRM_LOAD     2   // blink, then the brackets go and the other button flips away
#define EN_CONFIRM_CANCEL   3   // brackets go, both buttons flip away (bottom one first)

// frames after EnMenuConfirm at which the screens move on, as on the DS
#define EN_MENU_T_STAY_FADE     59   // EN_CONFIRM_STAY: start the fade
#define EN_MENU_T_LOAD_FADE     22   // EN_CONFIRM_LOAD: start the fade
#define EN_MENU_T_CANCEL_FADE   30   // EN_CONFIRM_CANCEL: start the fade
#define EN_MENU_T_SAVING_DONE  140   // EN_CONFIRM_SAVE_YES: "Saving..." has blinked twice

struct EnMenuButton
{
    s16 x, y;      // top-left of the first sprite
    u16 tile;      // first OBJ tile
    u8 sprites;    // 2 (64x32 + 32x32) or 3 (3 x 64x32)
    u8 pal;        // OBJ palette in use
    s8 lean;       // which way the button tilts when it flips: -1, 0, 1
    u8 anim;       // EN_BTN_*
    u8 t;          // frame of the flip
    u8 blinkOff;   // hidden for this frame (selection blink)
};

struct EnMenu
{
    u8 kind;           // EN_MENU_*, 0 when no menu screen is up
    u8 textMode;       // plate text: DS menu font, centred lines (vwf.c)
    u8 halfLine;       // single line centred between the two text lines
    u8 fading;         // a fade is being done through the palettes
    u8 fadeLevel;      // 0 (normal) .. 16 (black)
    u8 fadePending;    // fadeBuf goes to the palettes at the next VBlank
    u8 phase;          // EN_PH_*
    u8 slideDelay;
    s16 slide;         // plate offset from its place, px
    u16 t;             // frames since the current phase began
    u8 sel;            // selected button
    u8 count;          // buttons on screen
    u8 confirm;        // EN_CONFIRM_*
    u8 bracketsOn;
    u8 introDelay;
    u8 pad[3];
    struct EnMenuButton buttons[3];   // [2] is "Saving..."
    u16 pal[0x200];        // full-brightness palettes while fading
    u16 fadeBuf[0x200];
    u16 backup[0x200];     // the game's palettes while the screen is up
};

// in the old script heap (see ewram.h, vwf.c): free after the VWF buffers
#define gEnMenu ((struct EnMenu *)(EWRAM_START + 0x11FC0 + 0x8000))

void EnMenuBegin(u32 kind);
void EnMenuEnd(bool32 restorePalettes);
bool32 EnMenuSlideDone(void);
void EnMenuSetupButtons(u32 kind, u32 selected, bool32 firstDisabled);
void EnMenuShowButtons(u32 delay);
bool32 EnMenuButtonsReady(void);
void EnMenuSelect(u32 sel);
void EnMenuConfirm(u32 how);
void EnMenuShowSaving(bool32 show);
u32 EnMenuTime(void);
void EnMenuSetTextPos(void);
// main loop hooks
bool32 EnMenuFrame(void);
void EnMenuVBlank(void);
// vwf.c
u32 EnMenuLineStart(void);

#endif // GUARD_EN_MENU_H

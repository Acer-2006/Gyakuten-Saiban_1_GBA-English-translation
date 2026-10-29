// English patch, the RFTA build: the safe's keypad (the DS's 74 8 34: Chief
// Gant's safe on Day 3, script command 69 5<<8; tools/en/rfta/keypad.py has
// what the DS does). It runs on the 3D viewer's machinery (en_evidence3d.c:
// the screen and the script saved and given back, the Court Record's state
// 8): the device on one screen, its LCD over its keypad (two rows of keys);
// the + pad moves the cursor over the keys, A presses one, B is Back Space.
// Seven digits in, the code is checked as the DS checks it; the right one
// shows the safe's handle turning, and either way Gant's office and the DS's
// next section follow (en_evidence3d.c goes on in it).
#include "global.h"
#include "main.h"
#include "script.h"
#include "sound.h"
#include "animation.h"
#include "investigation.h"
#include "background.h"
#include "ewram.h"
#include "constants/songs.h"
#include "en_rfta.h"

#if RFTA

#include "data/en_rfta_keypad.h"
extern const u8 gEnKeypadData[];
#define K(off) (gEnKeypadData + (off))

enum { K_INTRO, K_INPUT, K_CHECK, K_RESULT, K_FADE, K_CUT, K_SAFE_TURN, K_SAFE_HOLD, K_SAFE_OUT };

// the DS's frames
#define PROMPT_FRAMES 60            // "Input code." blinking, before the keys light
#define LIGHT_FRAMES 4              // a key lit every 4
#define WAIT_FRAMES 60              // after the seventh digit
#define STEP_FRAMES 21              // the check: a digit every 21
#define STEPS 13                    // seven digits, six blinks
#define RESULT_SE_FRAME 30
#define RESULT_FRAMES 120
#define TURN_FRAMES 64              // the handle: a quarter turn
#define HOLD_FRAMES 60
#define CLOCK 60                    // the LCD's clock (the cursor, the segment, the blinks, the LED)
#define PRESS_FRAMES 4              // a key orange at least this long

#define KEYS 11
#define KEY_BACK 10
#define OAM_FIRST 57
#define OAM_LAST 87
#define OAM_HANDLE OAM_LAST                          // (on the room's screen: past the map markers' 57-64)
#define OAM_SAFE_LIGHT (OAM_LAST - 1)
#define TILE_BASE 0x1A0
#define TILE_KEYS TILE_BASE                         // ten keys of 16 tiles, Back Space 32
#define TILE_LEDS (TILE_BASE + 192)                 // red, green
#define TILE_CURSOR (TILE_LEDS + 2)                 // 32 x 32, 64 x 32
#define TILE_HANDLE TILE_BASE                       // (on the room's screen: the record's tiles given back after)
#define TILE_SAFE_LIGHT (TILE_HANDLE + 8)
#define PAL_KEYS 9                                  // dark, lit, pressed
#define PAL_LED 12
#define PAL_CURSOR 13
#define PAL_HANDLE 13                               // (on the room's: its colours given back after)
#define PAL_SAFE_LIGHT 14
#define AFFINE 31
#define LCD_TILES (KEYPAD_LCD_W * KEYPAD_LCD_H)

struct EnKeypad
{
    u8 mode, count, step, right;
    u8 cursor, pressed, pressTimer, lit;     // the key under the cursor; the one pressed (0xFF none)
    u8 clock, prompt, ledGreen, shown;      // the LCD's clock; "Input code." up; the LED green; the message up
    u8 digits[7], lcdReady;
    u8 oam, spare[3];                       // the next sprite
    u16 timer;
    u32 lcdKey;                             // what the LCD shows (drawn again when it changes)
};
// after the viewer's state (0x274 bytes), before its backups
#define gKeypad (*(struct EnKeypad *)(EWRAM_START + 0x11FC0 + 0x9400))
#define sLcd ((u8 *)(EWRAM_START + 0x2CFC0))           // the LCD's tiles as drawn (the background's buffer)

static void SetMode(u32 mode)
{
    gKeypad.mode = mode;
    gKeypad.timer = 0;
}

// ---------------------------------------------------------------- the LCD
static void Put(const u8 * src, s32 x, s32 y, s32 w, s32 h)
{
    s32 i, j;
    x -= KEYPAD_LCD_X0 * 8;
    y -= KEYPAD_LCD_Y0 * 8;
    for (j = 0; j < h; j++)
        for (i = 0; i < w; i++)
        {
            u32 v = src[j * w + i];
            s32 px = x + i, py = y + j;
            if (v)
                sLcd[((py >> 3) * KEYPAD_LCD_W + (px >> 3)) * 64 + (py & 7) * 8 + (px & 7)] = v;
        }
}

static void Glyph(u32 n, u32 cell)
{
    Put(K(KEYPAD_GFX_PICTURES) + n * KEYPAD_GLYPH_W * KEYPAD_GLYPH_H, KEYPAD_DIGIT_X + 22 * cell, KEYPAD_DIGIT_Y,
        KEYPAD_GLYPH_W, KEYPAD_GLYPH_H);
}

static void Bars(u32 cell)
{
    Put(K(KEYPAD_GFX_BARS), KEYPAD_BAR_X + 22 * cell, KEYPAD_BAR_TOP, 20, 4);
    Put(K(KEYPAD_GFX_BARS) + 80, KEYPAD_BAR_X + 22 * cell, KEYPAD_BAR_BOTTOM, 20, 4);
}

static void Message(u32 n)
{
    Put(K(KEYPAD_GFX_MESSAGES) + n * KEYPAD_MESSAGE_W * KEYPAD_MESSAGE_H, KEYPAD_MESSAGE_X, KEYPAD_MESSAGE_Y,
        KEYPAD_MESSAGE_W, KEYPAD_MESSAGE_H);
}

// what the LCD shows now, as the DS draws it: a key, the picture drawn
// again when it changes
static u32 LcdKey(void)
{
    struct EnKeypad * k = &gKeypad;
    switch (k->mode)
    {
    case K_INTRO:
        return k->prompt ? 1 : 0;
    case K_INPUT:
        return 0x100 | k->count << 1 | (k->count < 7 && k->clock < 40);
    case K_CHECK:
        if (k->step < 7)
            return 0x200 | k->step << 4 | k->clock / 10;
        return 0x300 | (k->clock < 50);
    case K_RESULT:
    case K_FADE:
        return k->shown ? 0x400 | k->right : 0x500;
    }
    return 0x600;
}

static void LcdDraw(void)
{
    struct EnKeypad * k = &gKeypad;
    u32 key = LcdKey(), i;
    if (key == k->lcdKey)
        return;
    k->lcdKey = key;
    DmaCopy32(3, K(KEYPAD_GFX_TILES), sLcd, LCD_TILES * 64);
    switch (k->mode)
    {
    case K_INTRO:
        if (k->prompt)
            Message(0);
        break;
    case K_INPUT:
        for (i = 0; i < k->count; i++)
            Glyph(k->digits[i], i);
        if (k->count < 7 && k->clock < 40)
            Glyph(KEYPAD_GLYPH_CURSOR, k->count);
        break;
    case K_CHECK:
        for (i = 0; i < 7; i++)
        {
            if (k->step < 7 && i == k->step)
            {
                // the segment running round the digit being checked, between its bars
                Bars(i);
                Glyph(KEYPAD_GLYPH_SEGMENT + k->clock / 10, i);
            }
            else if (k->step < 7 || k->clock < 50)
                Glyph(k->digits[i], i);
        }
        break;
    case K_RESULT:
    case K_FADE:
        if (k->shown)
            Message(k->right ? 1 : 2);
        break;
    }
    k->lcdReady = TRUE;
}

// ---------------------------------------------------------------- the screen
// BG3 the device (256 colours: the LCD's tiles first, drawn into), the keys,
// the LED and the cursor sprites
void EnKeypadScreen(void)
{
    struct IORegisters * io = &gIORegisters;
    struct EnKeypad * k = &gKeypad;
    const u16 * map = (const u16 *)K(KEYPAD_GFX_MAP);
    u32 r, c;
    io->lcd_dispcnt &= ~(DISPCNT_BG0_ON | DISPCNT_BG1_ON | DISPCNT_BG2_ON);
    io->lcd_dispcnt |= DISPCNT_BG3_ON | DISPCNT_OBJ_ON;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(2) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_256COLOR;
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
            gBG3MapBuffer[r * 32 + c] = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? map[(r - 1) * 30 + c - 1] : 0;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaCopy32(3, K(KEYPAD_GFX_TILES), BG_CHAR_ADDR(1), KEYPAD_TILE_COUNT * 64);
    DmaCopy16(3, sKeypadPalette, BG_PLTT, KEYPAD_COLOURS * 2);
    DmaCopy32(3, K(KEYPAD_GFX_KEYS), OBJ_VRAM0 + TILE_KEYS * 32, 192 * 32);
    DmaCopy32(3, K(KEYPAD_GFX_LEDS), OBJ_VRAM0 + TILE_LEDS * 32, 2 * 32);
    DmaCopy32(3, K(KEYPAD_GFX_CURSOR), OBJ_VRAM0 + TILE_CURSOR * 32, 48 * 32);
    DmaCopy16(3, sKeypadKeyPals, OBJ_PLTT + PAL_KEYS * 32, 3 * 32);
    DmaCopy16(3, sKeypadLedPal, OBJ_PLTT + PAL_LED * 32, 32);
    DmaCopy16(3, sKeypadCursorPal, OBJ_PLTT + PAL_CURSOR * 32, 32);
    // the puzzle's start
    k->mode = K_INTRO;
    k->timer = 0;
    k->count = k->step = k->right = 0;
    k->cursor = 0;                      // ("1")
    k->pressed = 0xFF;
    k->lit = 0;
    k->clock = 0;
    k->prompt = TRUE;
    k->ledGreen = k->shown = FALSE;
    k->lcdKey = 0xFFFFFFFF;
    LcdDraw();
}

// the vertical blank's: the LCD as drawn
void EnKeypadVBlank(void)
{
    struct EnKeypad * k = &gKeypad;
    if (k->lcdReady && k->mode < K_CUT)
    {
        DmaCopy32(3, sLcd, BG_CHAR_ADDR(1), LCD_TILES * 64);
        k->lcdReady = FALSE;
    }
}

// ---------------------------------------------------------------- sprites
#define sOam (gKeypad.oam)

static void Obj(u32 attr0, u32 attr1, u32 attr2)
{
    struct OamAttrs * o;
    if (sOam > OAM_LAST)
        return;
    o = &gOamObjects[sOam++];
    o->attr0 = attr0;
    o->attr1 = attr1;
    o->attr2 = attr2;
}

static void KeyAt(u32 key, s32 * x, s32 * y)
{
    *x = KEYPAD_KEY_X + 32 * (key % 6);
    *y = KEYPAD_KEY_Y + 32 * (key / 6);
}

static u32 KeyState(u32 key)
{
    struct EnKeypad * k = &gKeypad;
    if (key == k->pressed)
        return 2;
    if (k->mode == K_INTRO)
        return key < k->lit;
    return k->mode == K_INPUT && k->count < 7;
}

void EnKeypadSprites(void)
{
    struct EnKeypad * k = &gKeypad;
    s32 x, y;
    u32 key;
    sOam = OAM_FIRST;
    if (k->mode == K_INPUT && k->count < 7)
    {
        KeyAt(k->cursor, &x, &y);
        if (k->cursor == KEY_BACK)
            Obj(SPRITE_ATTR0(y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE),
                SPRITE_ATTR1_NONAFFINE(x, FALSE, FALSE, 3), SPRITE_ATTR2(TILE_CURSOR + 16, 1, PAL_CURSOR));
        else
            Obj(SPRITE_ATTR0(y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE),
                SPRITE_ATTR1_NONAFFINE(x, FALSE, FALSE, 2), SPRITE_ATTR2(TILE_CURSOR, 1, PAL_CURSOR));
    }
    if (k->ledGreen || (k->shown && k->right))
        Obj(SPRITE_ATTR0(KEYPAD_LED_Y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE),
            SPRITE_ATTR1_NONAFFINE(KEYPAD_LED_X, FALSE, FALSE, 0), SPRITE_ATTR2(TILE_LEDS + (k->ledGreen ? 1 : 0), 1, PAL_LED));
    for (key = 0; key < KEYS; key++)
    {
        KeyAt(key, &x, &y);
        if (key == KEY_BACK)
            Obj(SPRITE_ATTR0(y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE),
                SPRITE_ATTR1_NONAFFINE(x, FALSE, FALSE, 3), SPRITE_ATTR2(TILE_KEYS + 16 * key, 2, PAL_KEYS + KeyState(key)));
        else
            Obj(SPRITE_ATTR0(y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE),
                SPRITE_ATTR1_NONAFFINE(x, FALSE, FALSE, 2), SPRITE_ATTR2(TILE_KEYS + 16 * key, 2, PAL_KEYS + KeyState(key)));
    }
    for (; sOam <= OAM_LAST; sOam++)
        gOamObjects[sOam].attr0 = SPRITE_ATTR0_CLEAR;
}

// the handle on the safe: a quarter turn about the dial (t of TURN_FRAMES);
// the safe's light, red
static void Handle(u32 t)
{
    struct OamAttrs * l = &gOamObjects[OAM_SAFE_LIGHT];
    s32 a = 90 * 16 * t / TURN_FRAMES;                 // degrees x 16
    s32 s = EnSin16(a), c = EnSin16(a + 90 * 16);       // 1.14
    s32 x = KEYPAD_HANDLE_X + ((KEYPAD_HANDLE_R * s) >> 14), y = KEYPAD_HANDLE_Y + ((KEYPAD_HANDLE_R * c) >> 14);
    struct OamAttrs * o = &gOamObjects[OAM_HANDLE];
    o->attr0 = SPRITE_ATTR0((y - 32) & 0xFF, ST_OAM_AFFINE_DOUBLE, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_V_RECTANGLE);
    o->attr1 = SPRITE_ATTR1_AFFINE((x - 16) & 0x1FF, AFFINE, 2);
    o->attr2 = SPRITE_ATTR2(TILE_HANDLE, 2, PAL_HANDLE);
    l->attr0 = SPRITE_ATTR0(KEYPAD_SAFE_LIGHT_Y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
    l->attr1 = SPRITE_ATTR1_NONAFFINE(KEYPAD_SAFE_LIGHT_X, FALSE, FALSE, 0);
    l->attr2 = SPRITE_ATTR2(TILE_SAFE_LIGHT, 2, PAL_SAFE_LIGHT);
    gOamObjects[AFFINE * 4 + 0].attr3 = c >> 6;
    gOamObjects[AFFINE * 4 + 1].attr3 = -s >> 6;
    gOamObjects[AFFINE * 4 + 2].attr3 = s >> 6;
    gOamObjects[AFFINE * 4 + 3].attr3 = c >> 6;
}

// ---------------------------------------------------------------- the frames
static void Press(u32 key)
{
    struct EnKeypad * k = &gKeypad;
    k->pressed = key;
    k->pressTimer = 0;
    if (key == KEY_BACK)
    {
        PlaySE(KEYPAD_SE_BACK);
        if (k->count > 0)
            k->count--;
    }
    else
    {
        PlaySE(KEYPAD_SE_KEY);
        k->digits[k->count++] = key;
    }
    k->clock = 0;
    k->lcdKey = 0xFFFFFFFF;
}

static void Input(void)
{
    struct EnKeypad * k = &gKeypad;
    u32 pressed = gJoypad.pressedKeys, held = gJoypad.heldKeys;
    s32 col = k->cursor == KEY_BACK ? 4 : k->cursor % 6, row = k->cursor / 6;
    // a key stays orange while its button is held (as long as the DS's touch)
    if (k->pressed != 0xFF && ++k->pressTimer >= PRESS_FRAMES && !(held & (A_BUTTON | B_BUTTON)))
        k->pressed = 0xFF;
    if (k->count >= 7)
    {
        // the seventh: the keys dark, then the check 60 frames on (counted,
        // in step, while no key is held: the DS's while the screen isn't touched)
        if (k->pressed == 0xFF && ++k->step > WAIT_FRAMES)
        {
            SetMode(K_CHECK);
            k->step = 0;
            k->ledGreen = FALSE;
        }
        return;
    }
    if (pressed & A_BUTTON)
    {
        Press(k->cursor);
        return;
    }
    if (pressed & B_BUTTON)
    {
        Press(KEY_BACK);
        return;
    }
    if (pressed & DPAD_LEFT)
        col = row == 1 && col == 4 ? 3 : col == 0 ? (row ? 4 : 5) : col - 1;
    else if (pressed & DPAD_RIGHT)
        col = row == 1 ? (col >= 4 ? 0 : col + 1) : (col == 5 ? 0 : col + 1);
    else if (pressed & (DPAD_UP | DPAD_DOWN))
        row ^= 1;
    else
        return;
    k->cursor = row == 1 && col >= 4 ? KEY_BACK : row * 6 + col;
    PlaySE(SE000_MENU_CHANGE);
}

static void Right(void)
{
    struct EnKeypad * k = &gKeypad;
    u32 i;
    k->right = TRUE;
    for (i = 0; i < 7; i++)
        if (k->digits[i] != sKeypadCode[i])
            k->right = FALSE;
}

// a frame of the keypad: KEYPAD_ON (its screen up), KEYPAD_ROOM (the room's
// screen given back: the safe), or the section to go on in (the screen
// black: faded in after)
u32 EnKeypadFrame(void)
{
    struct EnKeypad * k = &gKeypad;
    struct Main * main = &gMain;
    u32 t = ++k->timer;
    if (++k->clock >= CLOCK)
        k->clock = 0;
    switch (k->mode)
    {
    case K_INTRO:
        // "Input code." on for 20, off for 20 while the keys wait, then the keys lit
        if (t < PROMPT_FRAMES)
            k->prompt = (t / 20) % 2 == 0;
        else
            k->prompt = TRUE;
        if (t > PROMPT_FRAMES && t % LIGHT_FRAMES == 0)
        {
            if (k->lit < KEYS)
            {
                k->lit++;
                PlaySE(KEYPAD_SE_LIGHT);
            }
            else
            {
                SetMode(K_INPUT);
                k->clock = 0;
            }
        }
        break;
    case K_INPUT:
        Input();
        break;
    case K_CHECK:
        // the DS's clock: the LED green from 0 to 50
        if (k->clock == 0)
            k->ledGreen = TRUE;
        else if (k->clock == 50)
            k->ledGreen = FALSE;
        if (t >= STEP_FRAMES)
        {
            if (k->step < 7)
                PlaySE(KEYPAD_SE_CHECK);
            k->timer = 0;
            if (++k->step >= STEPS)
            {
                Right();
                k->ledGreen = FALSE;
                k->shown = FALSE;
                SetMode(K_RESULT);
            }
        }
        break;
    case K_RESULT:
        if (k->clock == 0)
            k->shown = TRUE;
        if (t == RESULT_SE_FRAME)
            PlaySE(k->right ? KEYPAD_SE_RIGHT : KEYPAD_SE_WRONG);
        if (t > RESULT_FRAMES)
        {
            // the wrong code: the fade; the right: the safe at once (the DS's
            // top screen goes to it as it is: here a frame black, the
            // screen changed under it)
            if (k->right)
            {
                StartHardwareBlend(2, 1, 16, 0x3F);
                SetMode(K_CUT);
            }
            else
            {
                StartHardwareBlend(2, 1, 1, 0x3F);
                SetMode(K_FADE);
            }
        }
        break;
    case K_FADE:
        if (main->blendMode != 0)
            break;
        En3dGiveBack(KEYPAD_OFFICE_BG);
        return KEYPAD_SECTION_WRONG;
    case K_CUT:
        // the safe, its handle down
        En3dGiveBack(KEYPAD_SAFE_BG);
        DmaCopy32(3, K(KEYPAD_GFX_HANDLE), OBJ_VRAM0 + TILE_HANDLE * 32, 8 * 32);
        DmaCopy32(3, K(KEYPAD_GFX_SAFE_LIGHT), OBJ_VRAM0 + TILE_SAFE_LIGHT * 32, 32);
        DmaCopy16(3, sKeypadHandlePal, OBJ_PLTT + PAL_HANDLE * 32, 32);
        DmaCopy16(3, sKeypadSafeLightPal, OBJ_PLTT + PAL_SAFE_LIGHT * 32, 32);
        Handle(0);
        StartHardwareBlend(1, 1, 16, 0x3F);
        SetMode(K_SAFE_TURN);
        return KEYPAD_ROOM;
    case K_SAFE_TURN:
        Handle(t);
        if (t >= TURN_FRAMES)
            SetMode(K_SAFE_HOLD);
        return KEYPAD_ROOM;
    case K_SAFE_HOLD:
        Handle(TURN_FRAMES);
        if (t > HOLD_FRAMES)
        {
            StartHardwareBlend(2, 1, 1, 0x3F);
            SetMode(K_SAFE_OUT);
        }
        return KEYPAD_ROOM;
    case K_SAFE_OUT:
        Handle(TURN_FRAMES);
        if (main->blendMode != 0)
            return KEYPAD_ROOM;
        // the handle away, the record's tiles back where it was; Gant's office
        gOamObjects[OAM_HANDLE].attr0 = SPRITE_ATTR0_CLEAR;
        gOamObjects[OAM_SAFE_LIGHT].attr0 = SPRITE_ATTR0_CLEAR;
        En3dGiveBackObj();
        En3dChangeBg(KEYPAD_OFFICE_BG);
        return KEYPAD_SECTION_RIGHT;
    }
    if (k->pressed != 0xFF && k->mode != K_INPUT)
        k->pressed = 0xFF;
    LcdDraw();
    return KEYPAD_ON;
}

#endif

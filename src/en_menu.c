#include "global.h"
#include "main.h"
#include "script.h"
#include "background.h"
#include "en_menu.h"
#include "en_menu_gfx.h"

// The save, load and erase screens laid out and animated as on the DS
// English release (timings measured frame by frame on the DS):
//  - the DS plate, hint and buttons over the GBA's own sepia courtroom (BG3,
//    as on the Japanese screens; no DS scanlines). Fades on these screens go
//    through the palettes; the hardware fade takes over once black.
//  - the plate slides in from the right 12 px a frame (BG2, window 0 hides
//    the wrapped copy), then the text is typed in the DS menu font (vwf.c);
//  - the buttons flip in one after the other, the brackets close in on the
//    selected one; a choice blinks, the other button flips away, and so on.

#define EN_BTN_HIDDEN   0
#define EN_BTN_SHOWN    1
#define EN_BTN_FLIP_IN  2
#define EN_BTN_FLIP_OUT 3

#define EN_PH_IDLE    0
#define EN_PH_SLIDE   1
#define EN_PH_INTRO   2
#define EN_PH_READY   3
#define EN_PH_CONFIRM 4

#define PAL_NORMAL  9
#define PAL_PRESSED 10
#define PAL_FADED   11
#define PAL_BRACKET 12
#define PAL_TEXT    13

#define OBJ_TILE(addr) ((addr) / TILE_SIZE_4BPP)
#define OAM_BRACKETS 36   // 4 corners, over the buttons
#define OAM_BUTTONS  40   // 3 buttons x 3 sprites

#define DARK_BLDCNT (BLDCNT_TGT1_BG0 | BLDCNT_TGT1_BG1 | BLDCNT_TGT1_BG2 | BLDCNT_TGT1_BG3 | BLDCNT_TGT1_OBJ | BLDCNT_TGT1_BD | BLDCNT_EFFECT_DARKEN)

#define PLATE_LEFT 21     // plate's left edge on screen once in place
#define SLIDE_START 240
#define SLIDE_SPEED 12

// flip: vertical scale (1/256) and the slant (px between the top and bottom
// edges) for each frame; flipping in plays the first six backwards
static const u16 sFlipScale[7] = {256, 233, 200, 166, 133, 90, 44};
static const u8 sFlipSlant[7] = {0, 3, 5, 6, 7, 7, 8};
#define FLIP_OUT_FRAMES 7
#define FLIP_IN_FRAMES 6

static void SetButton(struct EnMenuButton * b, s32 x, s32 y, u32 tile, u32 sprites, s32 lean)
{
    b->x = x;
    b->y = y;
    b->tile = tile;
    b->sprites = sprites;
    b->pal = PAL_NORMAL;
    b->lean = lean;
    b->anim = EN_BTN_HIDDEN;
    b->t = 0;
    b->blinkOff = FALSE;
}

static void HideSprites(void)
{
    u32 i;
    for (i = OAM_BRACKETS; i < OAM_BUTTONS + 9; i++)
        gOamObjects[i].attr0 = SPRITE_ATTR0_CLEAR;
}

void EnMenuBegin(u32 kind)
{
    struct EnMenu * m = gEnMenu;
    struct IORegisters * io = &gIORegisters;
    const u16 * map;
    u32 i;

    m->kind = kind;
    m->textMode = TRUE;
    m->halfLine = FALSE;
    m->fading = FALSE;
    m->fadeLevel = 16;      // called while the screen is black
    m->fadePending = FALSE;
    m->phase = EN_PH_SLIDE;
    m->slide = SLIDE_START;
    m->slideDelay = 6;
    m->t = 0;
    m->count = 0;
    m->bracketsOn = FALSE;
    // the game's palettes, before the courtroom picture changes palette 2
    DmaCopy16(3, PLTT, m->backup, sizeof(m->backup));
    DecompressBackgroundIntoBuffer(0x43);
    CopyBGDataToVram(0x43);

    DmaCopy16(3, gEnMenuBgTiles, BG_CHAR_ADDR(0) + EN_MENU_BG_TILE_BASE * TILE_SIZE_4BPP, EN_MENU_BG_TILE_COUNT * TILE_SIZE_4BPP);
    DmaCopy16(3, gEnMenuBgPal, BG_PLTT + EN_MENU_BG_PAL * 0x20, 0x20);
    if (kind == EN_MENU_LOAD)
    {
        DmaCopy16(3, gEnMenuButtonsLong, OBJ_VRAM0 + 0x3800, EN_MENU_LONG_BUTTON_BYTES * 2);
        DmaCopy16(3, gEnMenuBracket, OBJ_VRAM0 + 0x3800 + EN_MENU_LONG_BUTTON_BYTES * 2, 0x200);
        map = gEnMenuMapLoad;
    }
    else
    {
        DmaCopy16(3, gEnMenuButtonsShort, OBJ_VRAM0 + 0x3800, EN_MENU_SHORT_BUTTON_BYTES * 3);
        DmaCopy16(3, gEnMenuBracket, OBJ_VRAM0 + 0x3800 + EN_MENU_SHORT_BUTTON_BYTES * 3, 0x200);
        map = kind == EN_MENU_SAVE ? gEnMenuMapSave : gEnMenuMapClear;
    }
    // normal, pressed and greyed-out buttons, brackets, plate text
    DmaCopy16(3, gEnMenuObjPal, OBJ_PLTT + PAL_NORMAL * 0x20, 0x20 * 5);

    for (i = 0; i < 32 * 20; i++)
        gBG2MapBuffer[i] = map[i];
    for (; i < 32 * 32; i++)
        gBG2MapBuffer[i] = 0;
    io->lcd_bg2cnt = BGCNT_PRIORITY(1) | BGCNT_CHARBASE(0) | BGCNT_SCREENBASE(30) | BGCNT_16COLOR | BGCNT_WRAP | BGCNT_TXT256x256;
    io->lcd_bg2hofs = 8 - SLIDE_START;
    io->lcd_bg2vofs = 0;
    io->lcd_win0h = (DISPLAY_WIDTH << 8) | DISPLAY_WIDTH;
    io->lcd_win0v = DISPLAY_HEIGHT;
    io->lcd_winin = 0x3F;            // window 0: every layer, effects on
    io->lcd_winout = 0x3F & ~0x04;   // outside: no BG2
    io->lcd_dispcnt = DISPCNT_MODE_0 | DISPCNT_OBJ_1D_MAP | DISPCNT_BG2_ON | DISPCNT_BG3_ON | DISPCNT_OBJ_ON | DISPCNT_WIN0_ON;
    gMain.tilemapUpdateBits = 0xC;
    HideSprites();
}

void EnMenuEnd(bool32 restorePalettes)
{
    struct EnMenu * m = gEnMenu;
    if (!m->kind)
        return;
    m->kind = 0;
    m->textMode = FALSE;
    m->halfLine = FALSE;
    m->fading = FALSE;
    m->fadePending = FALSE;
    m->phase = EN_PH_IDLE;
    HideSprites();
    if (restorePalettes)
        DmaCopy16(3, m->backup, PLTT, sizeof(m->backup));
}

bool32 EnMenuSlideDone(void)
{
    return gEnMenu->phase != EN_PH_SLIDE;
}

void EnMenuSetupButtons(u32 kind, u32 selected, bool32 firstDisabled)
{
    struct EnMenu * m = gEnMenu;
    if (kind == EN_MENU_LOAD)
    {
        u32 base = OBJ_TILE(0x3800);
        SetButton(&m->buttons[0], 24, 96, base, 3, 0);
        SetButton(&m->buttons[1], 24, 128, base + EN_MENU_LONG_BUTTON_BYTES / TILE_SIZE_4BPP, 3, 0);
        SetButton(&m->buttons[2], 0, 0, 0, 0, 0);
        if (firstDisabled)
            m->buttons[0].pal = PAL_FADED;
    }
    else
    {
        u32 base = OBJ_TILE(0x3800), n = EN_MENU_SHORT_BUTTON_BYTES / TILE_SIZE_4BPP;
        // DS places, less 8 px across and 20 px up: Yes (11, 96), No (128, 96);
        // "Saving..." where Yes ends up, in the middle
        SetButton(&m->buttons[0], 11, 96, base, 2, -1);
        SetButton(&m->buttons[1], 128, 96, base + n, 2, 1);
        SetButton(&m->buttons[2], 71, 96, base + 2 * n, 2, 0);
    }
    m->count = 2;
    m->sel = selected;
    m->bracketsOn = FALSE;
    if (m->phase != EN_PH_SLIDE)
        m->phase = EN_PH_IDLE;
}

void EnMenuShowButtons(u32 delay)
{
    if (gEnMenu->phase != EN_PH_IDLE)
        return;
    gEnMenu->phase = EN_PH_INTRO;
    gEnMenu->t = 0;
    gEnMenu->introDelay = delay;
}

bool32 EnMenuButtonsReady(void)
{
    return gEnMenu->phase >= EN_PH_READY;
}

void EnMenuSelect(u32 sel)
{
    gEnMenu->sel = sel;
}

void EnMenuConfirm(u32 how)
{
    gEnMenu->phase = EN_PH_CONFIRM;
    gEnMenu->confirm = how;
    gEnMenu->t = 0;
}

void EnMenuShowSaving(bool32 show)
{
    gEnMenu->buttons[2].anim = show ? EN_BTN_SHOWN : EN_BTN_HIDDEN;
}

u32 EnMenuTime(void)
{
    return gEnMenu->t;
}

void EnMenuSetTextPos(void)
{
    // DS plate text: the first line's cell starts 47 px below the plate's
    // top edge (y 52 here on both screens); the glyphs start two rows into
    // the cell
    gScriptContext.textXOffset = 0;
    gScriptContext.textYOffset = 54;
}

// pen position for a centred plate line: the DS centres a line of width W
// at (258 - W) / 2 on its 256 px screen
u32 EnMenuLineStart(void)
{
    const u16 * p = gScriptContext.scriptPtr;
    s32 w = 0, x;
    while (*p >= 0x80)
    {
        u32 c = *p++ - 0x80;
        w += (c < EN_PLATE_FONT_CODES && gEnPlateFontAdv[c]) ? gEnPlateFontAdv[c] : 8;
    }
    x = (258 - w) / 2 - 8;
    return x < 0 ? 0 : x;
}

static void Flip(struct EnMenuButton * b, u32 anim)
{
    b->anim = anim;
    b->t = 0;
}

static void Blink(struct EnMenuButton * b, u32 t)
{
    b->pal = PAL_PRESSED;
    b->blinkOff = (t >= 2 && t < 8) || (t >= 12 && t < 18);
}

static void BracketBox(const struct EnMenuButton * b, s32 * box)
{
    s32 left = b->sprites == 2 ? 4 : 0, width = b->sprites == 2 ? 92 : 192;
    box[0] = b->x + left - 2;
    box[1] = b->y + 1;
    box[2] = b->x + left + width + 1;
    box[3] = b->y + 30;
}

static void DrawBrackets(void)
{
    struct EnMenu * m = gEnMenu;
    struct OamAttrs * oam = &gOamObjects[OAM_BRACKETS];
    u32 tile = OBJ_TILE(0x3800) + (m->kind == EN_MENU_LOAD ? EN_MENU_LONG_BUTTON_BYTES * 2 : EN_MENU_SHORT_BUTTON_BYTES * 3) / TILE_SIZE_4BPP;
    s32 box[4], q;
    if (!m->bracketsOn)
    {
        for (q = 0; q < 4; q++)
            oam[q].attr0 = SPRITE_ATTR0_CLEAR;
        return;
    }
    BracketBox(&m->buttons[m->sel], box);
    if (m->phase == EN_PH_INTRO && m->t < 16)
    {
        // closing in from a box around most of the screen, three frames
        s32 k = m->t - 13, start[4];
        start[0] = 30;
        start[1] = box[1] - 88;
        start[2] = 238;
        start[3] = box[3] + 34;
        for (q = 0; q < 4; q++)
            box[q] = start[q] + (box[q] - start[q]) * k / 3;
    }
    for (q = 0; q < 4; q++, oam++)
    {
        s32 x = (q & 1) ? box[2] - 15 : box[0];
        s32 y = (q & 2) ? box[3] - 15 : box[1];
        oam->attr0 = (y & 0xFF) | (ST_OAM_SQUARE << 14);
        oam->attr1 = (x & 0x1FF) | (1 << 14);
        oam->attr2 = (tile + q * 4) | (1 << 10) | (PAL_BRACKET << 12);
    }
}

static void DrawButton(u32 n)
{
    struct EnMenuButton * b = &gEnMenu->buttons[n];
    struct OamAttrs * oam = &gOamObjects[OAM_BUTTONS + n * 3];
    bool32 affine = FALSE;
    s32 x = b->x;
    u32 i;
    if (b->anim == EN_BTN_HIDDEN || b->blinkOff || !b->sprites)
    {
        for (i = 0; i < 3; i++)
            oam[i].attr0 = SPRITE_ATTR0_CLEAR;
        return;
    }
    if (b->anim == EN_BTN_FLIP_IN || b->anim == EN_BTN_FLIP_OUT)
    {
        u32 k = b->anim == EN_BTN_FLIP_OUT ? b->t : FLIP_IN_FRAMES - b->t;
        s32 s = sFlipScale[k];
        s32 slant = sFlipSlant[k] * b->lean;
        // matrix n: screen -> texture. The face (26 rows) is s/256 high;
        // its top edge is moved `slant` px right of its bottom edge
        gOamObjects[n * 4 + 0].attr3 = 0x100;
        gOamObjects[n * 4 + 1].attr3 = slant * 65536 / (26 * s);
        gOamObjects[n * 4 + 2].attr3 = 0;
        gOamObjects[n * 4 + 3].attr3 = 65536 / s;
        affine = TRUE;
    }
    for (i = 0; i < 3; i++, oam++)
    {
        u32 wide = !(b->sprites == 2 && i == 1);   // 64x32, else 32x32
        u32 w = wide ? 64 : 32;
        if (i >= b->sprites)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            continue;
        }
        if (affine)
        {
            oam->attr0 = ((b->y - 16) & 0xFF) | (ST_OAM_AFFINE_DOUBLE << 8) | ((wide ? ST_OAM_H_RECTANGLE : ST_OAM_SQUARE) << 14);
            oam->attr1 = ((x - w / 2) & 0x1FF) | (n << 9) | ((wide ? 3 : 2) << 14);
        }
        else
        {
            oam->attr0 = (b->y & 0xFF) | ((wide ? ST_OAM_H_RECTANGLE : ST_OAM_SQUARE) << 14);
            oam->attr1 = (x & 0x1FF) | ((wide ? 3 : 2) << 14);
        }
        oam->attr2 = (b->tile + i * 32) | (1 << 10) | (b->pal << 12);
        x += w;
    }
}

static void AdvanceButton(struct EnMenuButton * b)
{
    if (b->anim == EN_BTN_FLIP_IN && ++b->t >= FLIP_IN_FRAMES)
        b->anim = EN_BTN_SHOWN;
    else if (b->anim == EN_BTN_FLIP_OUT && ++b->t >= FLIP_OUT_FRAMES)
        b->anim = EN_BTN_HIDDEN;
}

static void UpdatePhase(void)
{
    struct EnMenu * m = gEnMenu;
    struct EnMenuButton * s = &m->buttons[m->sel], * o = &m->buttons[m->sel ^ 1];
    u32 t = m->t;
    switch (m->phase)
    {
    case EN_PH_SLIDE:
        if (m->slideDelay)
            m->slideDelay--;
        else if ((m->slide -= SLIDE_SPEED) <= 0)
        {
            m->slide = 0;
            m->phase = EN_PH_IDLE;
        }
        return;
    case EN_PH_INTRO:
        if (m->introDelay)
        {
            m->introDelay--;
            return;
        }
        if (t == 0)
            Flip(&m->buttons[0], EN_BTN_FLIP_IN);
        if (t == 10)
            Flip(&m->buttons[1], EN_BTN_FLIP_IN);
        if (t == 13)
            m->bracketsOn = TRUE;
        if (t >= 16)
            m->phase = EN_PH_READY;
        break;
    case EN_PH_CONFIRM:
        switch (m->confirm)
        {
        case EN_CONFIRM_SAVE_YES:
        case EN_CONFIRM_STAY:
            Blink(s, t);
            if (t == 23)
                Flip(o, EN_BTN_FLIP_OUT);
            if (m->confirm == EN_CONFIRM_STAY)
                break;
            if (t == 31)
                m->bracketsOn = FALSE;
            if (t >= 31 && s->x != m->buttons[2].x)
            {
                // to the middle, 12 px a frame
                s->x += SLIDE_SPEED;
                if (s->x > m->buttons[2].x)
                    s->x = m->buttons[2].x;
            }
            if (t == 42)
            {
                s->lean = 0;
                Flip(s, EN_BTN_FLIP_OUT);
            }
            if (t == 52)
                Flip(&m->buttons[2], EN_BTN_FLIP_IN);
            // "Saving..." blinks: off 9 frames in 40
            m->buttons[2].blinkOff = t >= 68 && (t - 68) % 40 < 9;
            break;
        case EN_CONFIRM_LOAD:
            Blink(s, t);
            if (t == 22)
            {
                m->bracketsOn = FALSE;
                Flip(o, EN_BTN_FLIP_OUT);
            }
            break;
        case EN_CONFIRM_CANCEL:
            m->bracketsOn = FALSE;
            if (t == 12)
                Flip(&m->buttons[1], EN_BTN_FLIP_OUT);
            if (t == 22)
                Flip(&m->buttons[0], EN_BTN_FLIP_OUT);
            break;
        }
        break;
    default:
        return;
    }
    if (m->t < 0xFFFF)
        m->t++;
}

static void FadePalettes(u32 level)
{
    struct EnMenu * m = gEnMenu;
    u32 i;
    for (i = 0; i < 0x200; i++)
    {
        u32 c = m->pal[i];
        u32 r = c & 0x1F, g = (c >> 5) & 0x1F, b = (c >> 10) & 0x1F;
        // the GBA's own darken: I - I * level / 16
        r -= r * level >> 4;
        g -= g * level >> 4;
        b -= b * level >> 4;
        m->fadeBuf[i] = r | (g << 5) | (b << 10);
    }
    m->fadePending = TRUE;
}

// darken fades (blend modes 1 and 2) on a menu screen, done on the palettes
static void Blend(void)
{
    struct EnMenu * m = gEnMenu;
    struct Main * main = &gMain;
    struct IORegisters * io = &gIORegisters;
    if (main->blendMode == 1 || main->blendMode == 2)
    {
        if (!m->fading)
        {
            // the palettes are at full brightness now: for a fade in they were
            // loaded while the screen was dark
            DmaCopy16(3, PLTT, m->pal, sizeof(m->pal));
            m->fading = TRUE;
            m->fadeLevel = main->blendMode == 1 ? 16 : 0;
        }
        if (++main->blendCounter >= main->blendDelay)
        {
            main->blendCounter = 0;
            if (main->blendMode == 1)
                m->fadeLevel = m->fadeLevel > main->blendDeltaY ? m->fadeLevel - main->blendDeltaY : 0;
            else
                m->fadeLevel = m->fadeLevel + main->blendDeltaY < 16 ? m->fadeLevel + main->blendDeltaY : 16;
        }
        FadePalettes(m->fadeLevel);
        if ((main->blendMode == 1 && m->fadeLevel == 0) || (main->blendMode == 2 && m->fadeLevel == 16))
        {
            main->blendMode = 0;
            m->fading = FALSE;
        }
    }
    if (m->fadeLevel >= 16)
    {
        // black: the hardware keeps it black while the next screen loads
        io->lcd_bldcnt = DARK_BLDCNT;
        io->lcd_bldy = 16;
    }
    else
    {
        io->lcd_bldcnt = 0;
        io->lcd_bldy = 0;
    }
}

// once a frame (from UpdateHardwareBlend); TRUE when the menu has done the
// blending for this frame
bool32 EnMenuFrame(void)
{
    struct EnMenu * m = gEnMenu;
    struct IORegisters * io = &gIORegisters;
    s32 left;
    u32 i;
    if (!m->kind)
        return FALSE;
    if (gMain.blendMode > 2)
        return FALSE;
    UpdatePhase();
    io->lcd_bg2hofs = 8 - m->slide;
    left = PLATE_LEFT + m->slide;
    if (left > DISPLAY_WIDTH)
        left = DISPLAY_WIDTH;
    io->lcd_win0h = (left << 8) | DISPLAY_WIDTH;
    for (i = 0; i < 3; i++)
        DrawButton(i);
    DrawBrackets();
    for (i = 0; i < 3; i++)
        AdvanceButton(&m->buttons[i]);
    Blend();
    return TRUE;
}

void EnMenuVBlank(void)
{
    if (gEnMenu->fadePending)
    {
        DmaCopy16(3, gEnMenu->fadeBuf, PLTT, sizeof(gEnMenu->fadeBuf));
        gEnMenu->fadePending = FALSE;
    }
}

// English patch, the RFTA build: the staff roll (the DS's 74 c 0, 74 d n and
// 74 8 40 / 41 / 2e, the ending's: tools/en/rfta/credits.py has what the DS
// does). The DS dusts the credits on its touch screen while the epilogue's
// scenes play on the top one; here a page takes the screen while the
// epilogue's is black, between its scenes: the fingerprints' green grid, a
// brush crossing it three times dropping powder (the DS's stamps), the
// powder blown off but where the page's words are, the words blown away
// before the next scene (and the sparks the powder throws as it goes). The
// sketches the DS leaves to the player's touch while a scene plays are left
// out. The powder a byte a pixel, a quarter of its rows blown and drawn a
// step (the DS's frame), by ARM code in IWRAM (en_credits_arm.s); a step
// takes two frames where the powder covers the screen (the frame's work
// done before the sound's, as the background stripes'), and while the
// pages are up the script's waits count the vertical blanks.
// The script's command 6A (translate.py): sub << 8 | n
//   0 (74 c 0)   no page picked
//   1 (74 d n)   page n picked
//   2 (74 8 40)  the page shown: a credits page takes the screen (or, up
//                already, is dusted over the last one); a sketch gives it
//                back (the script waits for the fade)
//   3 (74 8 41)  the page blown away
//   4 (74 8 2e)  the screen given back (waited for)
#include "global.h"
#include "main.h"
#include "background.h"
#include "script.h"
#include "ewram.h"
#include "en_rfta.h"

#if RFTA
#include "data/en_rfta_credits.h"

extern const u8 gEnCreditsData[];
extern const u8 gEnCreditsCodeStart[];
extern const u8 gEnCreditsCodeEnd[];
extern u32 gEnMovieCode[];

struct EnCreditsArgs
{
    u8 * powder;
    u8 * part;
    const u8 * page;
    const s8 * pts;
    u32 count;
    s32 cx, cy;
    u32 y0, y1;
    u32 level, masked, far;
    u8 * tiles;
    u32 seed;
};
#define Stamp ((void (*)(struct EnCreditsArgs *))((u8 *)gEnMovieCode + 0))
#define Blow ((void (*)(struct EnCreditsArgs *))((u8 *)gEnMovieCode + 4))
#define Render ((void (*)(struct EnCreditsArgs *))((u8 *)gEnMovieCode + 8))

enum { CR_OFF, CR_FIRST, CR_FADE_IN, CR_UP, CR_FADE_OUT };   // the screen (CR_FIRST: drawn behind the black)
enum { ST_BUILD, ST_AUTO, ST_BLOW = 3 };                 // the DS's process 26's states
enum { B_RIGHT, B_LEFT, B_NEXT, B_DONE };                // its brush's (0x0207b6fc)

struct EnCredits
{
    struct EnCreditsArgs a;
    u8 screen, state, sub, quarter;
    u8 page, shown, far, brush;
    u8 brushRow, row, blowing, masked;
    u8 level, sliceLines, pad[2];
    u16 timer;
    s16 bx, by, jitter, count;
    u16 dispcnt, bg3cnt, bg3hofs, bg3vofs;
    u32 vblanks;                // the vertical blanks counted at the last frame
};
// in the old script heap's tail (ewram.h; the fingerprints' powder is the
// powder here too), the sparks in the background's buffer (decompressed
// again when the screen is given back)
#define HEAP (EWRAM_START + 0x11FC0)
#define gEnCredits (*(struct EnCredits *)(HEAP + 0x19E00))
#define sPalBackup ((u16 *)(HEAP + 0x1A000))      // 0x200
#define sMapBackup ((u16 *)(HEAP + 0x1A200))      // 0x800
#define sPowder ((u8 *)(HEAP + 0x10000))          // 240 x 160
#define sParts ((u8 *)eBGDecompBuffer)            // 240 x 160
#define FADE_ALL 0x1F

// the DS's quarters of its rows (48 each) on the GBA's screen (16 rows up),
// a step a frame; a step's rows blown and drawn a slice at a time while the
// frame has time for one before the sound (EN_BG_FRAME_END: a step can take
// more than a frame, the sound never waits)
static const u8 sQuarters[5] = { 0, 32, 80, 128, 160 };
#define SLICE 4

#define JITTER(ab) JITTER_(ab)
#define JITTER_(a, b) ((s32)Rand(a) - (b))

static u32 Rand(u32 n)
{
    struct EnCredits * c = &gEnCredits;
    u32 x = c->a.seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    c->a.seed = x;
    return ((x >> 16) * n) >> 16;
}

void EnCreditsReset(void)
{
    gEnCredits.screen = CR_OFF;
}

// ---------------------------------------------------------------- the brush
static void StampAt(s32 x, s32 y)
{
    struct EnCredits * c = &gEnCredits;
    const struct EnCreditsStamp * st = &sEnCreditsStamps[Rand(4)];
    c->a.pts = (const s8 *)(gEnCreditsData + CREDITS_GFX_STAMPS) + 2 * st->first;
    c->a.count = st->count;
    c->a.cx = x - CREDITS_CROP_X;
    c->a.cy = y - CREDITS_CROP_Y;
    Stamp(&c->a);
}

static void BrushStart(void)
{
    struct EnCredits * c = &gEnCredits;
    c->brush = B_RIGHT;
    c->brushRow = 0;
    c->bx = CREDITS_BRUSH_X0;
    c->by = sEnCreditsRows[0];
    c->jitter = JITTER(CREDITS_JITTER_FIRST);
    c->count = 0;
}

// a frame of it: a stamp where it is, a step every four frames; TRUE once
// its three rows are crossed (right, left, right)
static bool32 BrushFrame(void)
{
    struct EnCredits * c = &gEnCredits;
    switch (c->brush)
    {
    case B_RIGHT:
    case B_LEFT:
        StampAt(c->bx, c->by + c->jitter);
        if ((++c->count & (CREDITS_BRUSH_FRAMES - 1)) == 0)
        {
            c->bx += c->brush == B_LEFT ? -CREDITS_BRUSH_STEP : CREDITS_BRUSH_STEP;
            c->jitter = JITTER(CREDITS_JITTER_STEP);
        }
        if (c->brush == B_RIGHT ? c->bx > CREDITS_BRUSH_X1 : c->bx < CREDITS_BRUSH_X0)
        {
            c->count = 0;
            c->brush = B_NEXT;
        }
        return FALSE;
    case B_NEXT:
        if (++c->brushRow >= CREDITS_BRUSH_ROWS)
        {
            c->brush = B_DONE;
            return FALSE;
        }
        c->by = sEnCreditsRows[c->brushRow];
        c->count = 0;
        if (c->brushRow & 1)
        {
            c->bx = CREDITS_BRUSH_X1;
            c->brush = B_LEFT;
        }
        else
        {
            c->bx = CREDITS_BRUSH_X0;
            c->brush = B_RIGHT;
        }
        return FALSE;
    default:
        return TRUE;
    }
}

// ---------------------------------------------------------------- the powder
// this step's rows blown (as the slices are drawn)
static void BlowQuarter(u32 level, bool32 masked)
{
    struct EnCredits * c = &gEnCredits;
    c->blowing = TRUE;
    c->level = level;
    c->masked = masked;
}

// the DS's process a step (its frame, 0x02071d14): the page made, dusted,
// its powder blown off but where its words are; or blown away
static void Step(void)
{
    struct EnCredits * c = &gEnCredits;
    c->far = TRUE;
    c->blowing = FALSE;
    switch (c->state)
    {
    case ST_BUILD:              // (the page's mask made: five frames)
        if (++c->timer >= 5)
        {
            c->state = ST_AUTO;
            c->sub = 0;
            c->timer = 0;
        }
        break;
    case ST_AUTO:
        switch (c->sub)
        {
        case 0:
            BrushStart();
            c->sub++;
            break;
        case 1:
            if (BrushFrame())
            {
                c->timer = 0;
                c->sub++;
            }
            break;
        case 2:                 // a wait, then from the first quarter
            if (++c->timer > CREDITS_WAIT_FRAMES && c->quarter == 3)
            {
                c->timer = 0;
                c->sub++;
            }
            break;
        case 3:
            BlowQuarter(CREDITS_REVEAL_LEVEL, TRUE);
            if (++c->timer >= CREDITS_REVEAL_FRAMES)
            {
                c->timer = 0;
                c->sub++;
            }
            break;
        }
        break;
    case ST_BLOW:
        switch (c->sub)
        {
        case 0:
            if (c->quarter == 3)
                c->sub++;
            break;
        case 1:
            if (c->timer < CREDITS_BLOW_NEAR_FRAMES)
                c->far = FALSE;
            BlowQuarter(CREDITS_BLOW_LEVEL, FALSE);
            if (++c->timer >= CREDITS_BLOW_FRAMES)
            {
                c->timer = 0;
                c->sub++;
            }
            break;
        }
        break;
    }
}

static void Slice(u32 y0, u32 y1)
{
    struct EnCredits * c = &gEnCredits;
    c->a.y0 = y0;
    c->a.y1 = y1;
    if (c->blowing)
    {
        c->a.page = gEnCreditsData + CREDITS_GFX_PAGES + (c->shown - CREDITS_FIRST_PAGE) * CREDITS_PAGE_BYTES;
        c->a.level = c->level;
        c->a.masked = c->masked;
        Blow(&c->a);
    }
    c->a.far = c->far;
    Render(&c->a);
}

// time for another slice before the frame's sound (as the last one took)
static bool32 TimeLeft(void)
{
    struct EnCredits * c = &gEnCredits;
    s32 limit = EN_BG_FRAME_END - gEnSoundLines - 6;
    if (gEnVBlanks != c->vblanks)       // (the frame over already)
        return FALSE;
    return (s32)(EnLinesSinceVBlank() + c->sliceLines) < limit;
}

// the frame's part of the step (at least a slice); its state first, as the
// step starts (none while the screen is drawn and faded in)
static void Work(void)
{
    struct EnCredits * c = &gEnCredits;
    u32 y1 = sQuarters[c->quarter + 1];
    bool32 first = TRUE;
    if (c->row == sQuarters[c->quarter])
    {
        if (c->screen == CR_UP || c->screen == CR_FADE_OUT)
            Step();
        else
        {
            c->far = TRUE;
            c->blowing = FALSE;
        }
    }
    while (c->row < y1)
    {
        u32 n = c->row + SLICE, t, now;
        if (!first && !TimeLeft())
            return;
        first = FALSE;
        t = EnLinesSinceVBlank();
        Slice(c->row, n);
        c->row = n;
        now = EnLinesSinceVBlank();
        c->sliceLines = now >= t && now - t < 60 ? now - t + 1 : 60;
    }
    c->quarter = (c->quarter + 1) & 3;
    c->row = sQuarters[c->quarter];
    if (c->screen == CR_FIRST && c->quarter == 0)
    {
        StartHardwareBlend(1, 1, 1, FADE_ALL);
        c->screen = CR_FADE_IN;
    }
}

// ---------------------------------------------------------------- the screen
// BG3 ours (the powder's 600 tiles, 256 colours), the rest off; the screen
// dark at once (the epilogue's is black) and faded in
static void TakeScreen(void)
{
    struct EnCredits * c = &gEnCredits;
    struct IORegisters * io = &gIORegisters;
    u32 r, col;
    EnMovieClose();
    CpuCopy32(gEnCreditsCodeStart, gEnMovieCode, gEnCreditsCodeEnd - gEnCreditsCodeStart);
    c->dispcnt = io->lcd_dispcnt;
    c->bg3cnt = io->lcd_bg3cnt;
    c->bg3hofs = io->lcd_bg3hofs;
    c->bg3vofs = io->lcd_bg3vofs;
    DmaCopy16(3, gBG3MapBuffer, sMapBackup, 0x800);
    DmaCopy16(3, BG_PLTT, sPalBackup, 0x200);
    io->lcd_bldcnt = FADE_ALL | BLDCNT_EFFECT_DARKEN;
    io->lcd_bldy = 16;
    gMain.isBGScrolling = FALSE;
    io->lcd_dispcnt = (io->lcd_dispcnt & ~(DISPCNT_BG0_ON | DISPCNT_BG1_ON | DISPCNT_BG2_ON | DISPCNT_OBJ_ON)) | DISPCNT_BG3_ON;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(3) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_256COLOR;
    for (r = 0; r < 32; r++)
        for (col = 0; col < 32; col++)
            gBG3MapBuffer[r * 32 + col] = (r >= 1 && r <= 20 && col >= 1 && col <= 30) ? (r - 1) * 30 + col - 1 : 0;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaCopy16(3, sEnCreditsPowderPal, BG_PLTT + CREDITS_PAL_POWDER * 2, sizeof(sEnCreditsPowderPal));
    DmaCopy16(3, sEnCreditsGridPal, BG_PLTT + CREDITS_PAL_GRID * 2, sizeof(sEnCreditsGridPal));
    DmaFill32(3, 0, sPowder, DISPLAY_WIDTH * DISPLAY_HEIGHT);
    DmaFill32(3, 0, sParts, DISPLAY_WIDTH * DISPLAY_HEIGHT);
    c->a.powder = sPowder;
    c->a.part = sParts;
    c->a.tiles = (u8 *)BG_CHAR_ADDR(1);
    c->a.seed = (gMain.frameCounter << 8) ^ 0x2545F491;
    if (c->a.seed == 0)
        c->a.seed = 1;
    c->quarter = 0;
    c->row = 0;
    c->sliceLines = 8;
    c->screen = CR_FIRST;
    c->vblanks = gEnVBlanks;
}

// everything as it was (the black background the epilogue left, or its own)
static void GiveBack(void)
{
    struct EnCredits * c = &gEnCredits;
    struct IORegisters * io = &gIORegisters;
    c->screen = CR_OFF;
    DmaCopy16(3, sPalBackup, BG_PLTT, 0x200);
    DmaCopy16(3, sMapBackup, gBG3MapBuffer, 0x800);
    io->lcd_dispcnt = c->dispcnt;
    io->lcd_bg3cnt = c->bg3cnt;
    if (gMain.currentBG != 0xFF)
        DecompressBackgroundIntoBuffer(gMain.currentBG);
    CopyBGDataToVram(gMain.currentBG);
    io->lcd_bg3hofs = c->bg3hofs;
    io->lcd_bg3vofs = c->bg3vofs;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
}

// the screen faded out and given back: TRUE while that is under way
static bool32 Leave(void)
{
    struct EnCredits * c = &gEnCredits;
    if (c->screen == CR_OFF)
        return FALSE;
    if (c->screen == CR_FIRST)          // (still black)
    {
        GiveBack();
        return FALSE;
    }
    if (c->screen != CR_FADE_OUT)
    {
        StartHardwareBlend(2, 1, 1, FADE_ALL);
        c->screen = CR_FADE_OUT;
    }
    return TRUE;
}

// the script's wait (its 0C) in vertical blanks while the pages are up: a
// game frame that runs long then does not hold the epilogue back, which the
// DS's music goes on under
static void KeepTime(void)
{
    struct EnCredits * c = &gEnCredits;
    struct ScriptContext * ctx = &gScriptContext;
    u32 vb = gEnVBlanks, missed = vb - c->vblanks - 1;
    c->vblanks = vb;
    if (missed == 0 || missed > 8 || *ctx->scriptPtr != 0x0C || ctx->waitTimer <= 1)
        return;
    ctx->waitTimer = ctx->waitTimer > missed + 1 ? ctx->waitTimer - missed : 1;
}

// once a frame (main.c)
void EnCreditsFrame(void)
{
    struct EnCredits * c = &gEnCredits;
    if (c->screen != CR_OFF)
        KeepTime();
    switch (c->screen)
    {
    case CR_OFF:
        return;
    case CR_FADE_IN:
        if (gMain.blendMode == 0)
            c->screen = CR_UP;
        break;
    case CR_FADE_OUT:
        if (gMain.blendMode == 0)
        {
            GiveBack();
            return;
        }
        break;
    }
    Work();
}

bool32 Command6A(struct ScriptContext * scriptCtx)
{
    struct EnCredits * c = &gEnCredits;
    u32 arg = scriptCtx->scriptPtr[1], sub = arg >> 8, n = arg & 0xFF;
    switch (sub)
    {
    case 0:
        c->page = 0;
        break;
    case 1:
        c->page = n;
        break;
    case 2:
        if (c->page >= CREDITS_FIRST_PAGE && c->page <= CREDITS_LAST_PAGE)
        {
            if (c->screen == CR_FADE_OUT)
                break;
            if (c->screen == CR_OFF)
                TakeScreen();
            c->shown = c->page;
            c->state = ST_BUILD;
            c->sub = 0;
            c->timer = 0;
            break;
        }
        if (Leave())
            return 1;
        break;
    case 3:
        if (c->screen != CR_OFF)
        {
            c->state = ST_BLOW;
            c->sub = 0;
            c->timer = 0;
        }
        break;
    case 4:
        if (Leave())
            return 1;
        break;
    }
    scriptCtx->scriptPtr += 2;
    return 0;
}

#endif // RFTA

// English patch, the RFTA build: joining the dots (the DS's 74 8 3e: the
// final day's trial, the blood traces the victim left joined into the
// murderer's name; script command 69 7<<8; tools/en/rfta/dots.py has what
// the DS does). It runs on the 3D viewer's machinery (en_evidence3d.c: the
// screen and the script saved and given back, the Court Record's state 8,
// the Court Record and "Take that!" after):
//   the picture (background 0x8e) in 256 colours, its 16 then the lines'
//   and the traces': the traces drawn over it in the DS's dark red, the
//   lines into its tiles as the DS draws them (8 wide, round ends), each
//   tile put together again where something changed;
//   the examine pointer is the touch: the + pad moves it, A held is the
//   stylus down: held on a trace it starts a line from its middle, which
//   follows the pointer (blue, its shades running; white over another
//   trace, both lit); let go over another trace, the two are joined;
//   B (Back) takes the last line away, L presents the lines (the DS's
//   check), R opens the Court Record; the DS's bar and buttons over the top.
#include "global.h"
#include "main.h"
#include "background.h"
#include "ewram.h"
#include "sound.h"
#include "graphics.h"
#include "en_rfta.h"

#if RFTA

#include "data/en_rfta_dots.h"
extern const u8 gEnDotsData[];
#define G(off) (gEnDotsData + (off))

#define MAX_LINES (DOTS_TRACES * (DOTS_TRACES - 1) / 2)
#define TILES (30 * 20)
#define BLANK_TILE TILES
#define POINTER_SPEED 3             // the examine pointer's
#define POINTER_TIP_X 11            // the finger's tip in its picture
#define POINTER_TIP_Y 1
#define NEAR 11                     // a tile's middle this near a line's: the line may be in it (4 + its corner's 5.7)
#define OAM_FIRST 57
#define OAM_LAST 87
#define TILE_BASE 0x1A0
#define TILE_POINTER (TILE_BASE + DOTS_GFX_SPRITE_TILES)
#define PAL_UI 8
#define PAL_POINTER 9

struct EnDots
{
    s8 start, end;                  // the trace the line is drawn from, the one under the pointer (-1 none)
    u8 count, undo;                 // the lines; the last one white (taken away the next frame)
    u8 touched, cycle, cycleTimer, pointerColour;
    u8 pointerTimer, bandOn, bandWhite, oam;
    s8 litA, litB, spare[2];        // the traces lit as shown
    s16 px, py;                     // the pointer (its tip)
    s16 bx0, by0, bx1, by1;         // the line being drawn, as shown
    u32 dirty[20];                  // tiles to show again: a word a row
    u8 a[MAX_LINES], b[MAX_LINES];  // the lines (a < b)
};
// after the keypad's state, before the viewer's backups
#define gEnDots (*(struct EnDots *)(EWRAM_START + 0x11FC0 + 0x9480))
typedef char sEnDotsFits[sizeof(struct EnDots) <= 0x9800 - 0x9480 ? 1 : -1];
// the picture, the lines joined and the traces (8bpp tiles; the movies' buffer)
#define sBase ((u8 *)(EWRAM_START + 0x11FC0 + 0x10000))
#define sPicture ((const u8 *)eBGDecompBuffer)

// ---------------------------------------------------------------- drawing
// (a tile: 64 bytes, its top left at (x0, y0) on the screen)
static void Line(u8 * out, s32 x0, s32 y0, s32 ax, s32 ay, s32 bx, s32 by, u32 colour)
{
    s32 dx = bx - ax, dy = by - ay;
    s32 l2 = dx * dx + dy * dy;
    u32 lim = DOTS_HALF_WIDTH * DOTS_HALF_WIDTH * l2;
    s32 r, c, k;
    if (l2)
    {
        for (r = 0; r < 8; r++)
        {
            s32 px = x0 - ax, py = y0 + r - ay;
            s32 t = px * dx + py * dy, n = px * dy - py * dx;
            for (c = 0; c < 8; c++, t += dx, n += dy)
                if (t >= 0 && t <= l2 && (u32)(n * n) <= lim)
                    out[r * 8 + c] = colour;
        }
    }
    // the round ends
    for (k = 0; k < 2; k++)
    {
        s32 cx = (k ? bx : ax) - 4 - x0, cy = (k ? by : ay) - 4 - y0;
        if (cx <= -8 || cx >= 8 || cy <= -8 || cy >= 8)
            continue;
        for (r = 0; r < 8; r++)
        {
            u32 bits = sEnDotsCap[r];
            if (cy + r < 0 || cy + r >= 8)
                continue;
            for (c = 0; c < 8; c++)
                if ((bits & (0x80 >> c)) && cx + c >= 0 && cx + c < 8)
                    out[(cy + r) * 8 + cx + c] = colour;
        }
    }
}

// a line may be in the tile at (x0, y0)
static bool32 LineNear(s32 x0, s32 y0, s32 ax, s32 ay, s32 bx, s32 by)
{
    s32 dx = bx - ax, dy = by - ay;
    s32 l2 = dx * dx + dy * dy, len;
    s32 px = x0 + 4 - ax, py = y0 + 4 - ay, t, n;
    if (l2 == 0)
        return px * px + py * py <= NEAR * NEAR;
    len = EnISqrt(l2) + 1;
    t = px * dx + py * dy;
    n = px * dy - py * dx;
    if (n < 0)
        n = -n;
    return n <= NEAR * len && t >= -NEAR * len && t <= l2 + NEAR * len;
}

static void Trace(u8 * out, s32 x0, s32 y0, u32 i, u32 colour)
{
    const struct EnDotsTrace * d = &sEnDotsTraces[i];
    const u8 * m = G(d->mask);
    s32 r, c;
    if (d->mx >= x0 + 8 || d->mx + d->mw <= x0 || d->my >= y0 + 8 || d->my + d->mh <= y0)
        return;
    for (r = 0; r < 8; r++)
    {
        s32 my = y0 + r - d->my;
        if (my < 0 || my >= d->mh)
            continue;
        for (c = 0; c < 8; c++)
        {
            s32 mx = x0 + c - d->mx;
            if (mx >= 0 && mx < d->mw && m[my * d->mw + mx])
                out[r * 8 + c] = colour;
        }
    }
}

static void Ends(u32 k, s32 * ax, s32 * ay, s32 * bx, s32 * by)
{
    struct EnDots * s = &gEnDots;
    *ax = sEnDotsTraces[s->a[k]].cx;
    *ay = sEnDotsTraces[s->a[k]].cy;
    *bx = sEnDotsTraces[s->b[k]].cx;
    *by = sEnDotsTraces[s->b[k]].cy;
}

// the picture's tile with the lines joined and the traces over them
static void BaseTile(u32 tx, u32 ty)
{
    struct EnDots * s = &gEnDots;
    u32 t = ty * 30 + tx;
    u8 * out = sBase + t * 64;
    const u8 * src = sPicture + t * 32;
    s32 x0 = tx * 8, y0 = ty * 8, ax, ay, bx, by;
    u32 i, k;
    for (i = 0; i < 32; i++)
    {
        u32 v = src[i];
        out[2 * i] = (v & 15) ? 32 + (v & 15) : 0;
        out[2 * i + 1] = (v >> 4) ? 32 + (v >> 4) : 0;
    }
    for (k = 0; k < s->count; k++)
    {
        Ends(k, &ax, &ay, &bx, &by);
        if (LineNear(x0, y0, ax, ay, bx, by))
            Line(out, x0, y0, ax, ay, bx, by, DOTS_PAL_LINE);
    }
    for (i = 0; i < DOTS_TRACES; i++)
        Trace(out, x0, y0, i, DOTS_PAL_TRACE);
}

static void MarkTile(s32 tx, s32 ty)
{
    if (tx >= 0 && tx < 30 && ty >= 0 && ty < 20)
        gEnDots.dirty[ty] |= 1u << tx;
}

// the tiles a line may be in: marked (and their picture put together again)
static void MarkLine(s32 ax, s32 ay, s32 bx, s32 by, bool32 base)
{
    s32 tx0 = ((ax < bx ? ax : bx) - 6) >> 3, tx1 = ((ax > bx ? ax : bx) + 6) >> 3;
    s32 ty0 = ((ay < by ? ay : by) - 6) >> 3, ty1 = ((ay > by ? ay : by) + 6) >> 3;
    s32 tx, ty;
    if (tx0 < 0) tx0 = 0;
    if (ty0 < 0) ty0 = 0;
    if (tx1 > 29) tx1 = 29;
    if (ty1 > 19) ty1 = 19;
    for (ty = ty0; ty <= ty1; ty++)
        for (tx = tx0; tx <= tx1; tx++)
            if (LineNear(tx * 8, ty * 8, ax, ay, bx, by))
            {
                if (base)
                    BaseTile(tx, ty);
                MarkTile(tx, ty);
            }
}

static void MarkTrace(u32 i)
{
    const struct EnDotsTrace * d = &sEnDotsTraces[i];
    s32 tx, ty;
    for (ty = d->my >> 3; ty <= (d->my + d->mh - 1) >> 3; ty++)
        for (tx = d->mx >> 3; tx <= (d->mx + d->mw - 1) >> 3; tx++)
            MarkTile(tx, ty);
}

// a tile as shown: the line being drawn over the traces, the lit ones over it
static void ShowTile(u32 tx, u32 ty)
{
    struct EnDots * s = &gEnDots;
    u32 buf[16], t = ty * 30 + tx;
    u8 * out = (u8 *)buf;
    s32 x0 = tx * 8, y0 = ty * 8, ax, ay, bx, by;
    CpuCopy32(sBase + t * 64, buf, 64);
    // (a line is tried only in the tiles it may be in: further, its sums would run over)
    if (s->bandOn && LineNear(x0, y0, s->bx0, s->by0, s->bx1, s->by1))
        Line(out, x0, y0, s->bx0, s->by0, s->bx1, s->by1, DOTS_PAL_BAND);
    if (s->litA >= 0)
        Trace(out, x0, y0, s->litA, DOTS_PAL_LIT);
    if (s->litB >= 0)
        Trace(out, x0, y0, s->litB, DOTS_PAL_LIT);
    if (s->undo && s->count)
    {
        Ends(s->count - 1, &ax, &ay, &bx, &by);
        if (LineNear(x0, y0, ax, ay, bx, by))
            Line(out, x0, y0, ax, ay, bx, by, DOTS_PAL_WHITE);
    }
    CpuCopy32(buf, BG_CHAR_ADDR(1) + t * 64, 64);
}

static void ShowDirty(void)
{
    struct EnDots * s = &gEnDots;
    u32 w, k;
    for (w = 0; w < ARRAY_COUNT(s->dirty); w++)
    {
        u32 bits = s->dirty[w];
        if (!bits)
            continue;
        s->dirty[w] = 0;
        for (k = 0; k < 32; k++)
            if (bits & (1u << k))
                ShowTile(k, w);
    }
}

// ---------------------------------------------------------------- the screen
// the traces as they start: no lines, the pointer in the middle
void EnDotsStart(void)
{
    struct EnDots * s = &gEnDots;
    s->count = 0;
    s->undo = FALSE;
    s->start = s->end = -1;
    s->px = 120;
    s->py = 80;
}

// BG3 the picture in 256 colours (its 16 at 32), the lines and the traces
// drawn into it; the bar, the tabs and the pointer sprites
void EnDotsScreen(void)
{
    struct IORegisters * io = &gIORegisters;
    struct EnDots * s = &gEnDots;
    u16 * pal = (u16 *)BG_PLTT;
    u32 r, c, t;
    io->lcd_dispcnt &= ~(DISPCNT_BG0_ON | DISPCNT_BG1_ON | DISPCNT_BG2_ON);
    io->lcd_dispcnt |= DISPCNT_BG3_ON | DISPCNT_OBJ_ON;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(2) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_256COLOR;
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
            gBG3MapBuffer[r * 32 + c] = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? (r - 1) * 30 + c - 1 : BLANK_TILE;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaFill32(3, 0, BG_CHAR_ADDR(1) + BLANK_TILE * 64, 64);
    DmaCopy16(3, GetBGPalettePtr(DOTS_PICTURE_BG), BG_PLTT + 32 * 2, 32);
    pal[DOTS_PAL_LINE] = DOTS_COLOUR_LINE;
    pal[DOTS_PAL_TRACE] = DOTS_COLOUR_TRACE;
    pal[DOTS_PAL_LIT] = DOTS_COLOUR_LIT;
    pal[DOTS_PAL_WHITE] = DOTS_COLOUR_WHITE;
    pal[DOTS_PAL_BAND] = sEnDotsBandColours[0];
    // the picture, the lines there are (back from the Court Record) and the traces
    DecompressBackgroundIntoBuffer(DOTS_PICTURE_BG);
    s->start = s->end = -1;
    s->undo = FALSE;
    s->litA = s->litB = -1;
    s->bandOn = FALSE;
    s->touched = FALSE;
    s->cycle = s->cycleTimer = 0;
    for (r = 0; r < 20; r++)
        for (c = 0; c < 30; c++)
            BaseTile(c, r);
    DmaCopy32(3, sBase, BG_CHAR_ADDR(1), TILES * 64);
    for (t = 0; t < ARRAY_COUNT(s->dirty); t++)
        s->dirty[t] = 0;
    // the sprites
    DmaCopy32(3, G(DOTS_GFX_SPRITES), OBJ_VRAM0 + TILE_BASE * 32, DOTS_GFX_SPRITE_TILES * 32);
    DmaCopy16(3, gGfxInvestigationExamineCursor, OBJ_VRAM0 + TILE_POINTER * 32, 4 * 32);
    DmaCopy16(3, sEnDotsUiPalette, OBJ_PLTT + PAL_UI * 32, 32);
    DmaCopy16(3, gPalInvestigationExamineCursors, OBJ_PLTT + PAL_POINTER * 32, 32);
    s->pointerColour = s->pointerTimer = 0;
}

// the vertical blank's: the colours that change (the line being drawn, the pointer's)
void EnDotsVBlank(void)
{
    struct EnDots * s = &gEnDots;
    ((u16 *)BG_PLTT)[DOTS_PAL_BAND] = s->bandWhite ? DOTS_COLOUR_WHITE : sEnDotsBandColours[s->cycle];
    DmaCopy16(3, &gPalInvestigationExamineCursors[s->pointerColour * 0x20], OBJ_PLTT + PAL_POINTER * 32, 32);
}

// ---------------------------------------------------------------- sprites
static void Obj(u32 attr0, u32 attr1, u32 attr2)
{
    struct EnDots * s = &gEnDots;
    struct OamAttrs * o;
    if (s->oam > OAM_LAST)
        return;
    o = &gOamObjects[s->oam++];
    o->attr0 = attr0;
    o->attr1 = attr1;
    o->attr2 = attr2;
}

static void Sprite(u32 first, s32 x, s32 y)
{
    const struct EnDotsPiece * p = &sEnDotsPieces[first];
    for (;; p++)
    {
        s32 px = x + p->dx, py = y + p->dy;
        if (px > -64 && px < DISPLAY_WIDTH)
            Obj(SPRITE_ATTR0(py & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, p->shape),
                SPRITE_ATTR1_NONAFFINE(px & 0x1FF, FALSE, FALSE, p->size), SPRITE_ATTR2(TILE_BASE + p->tile, 0, PAL_UI));
        if (p->last)
            break;
    }
}

void EnDotsSprites(void)
{
    struct EnDots * s = &gEnDots;
    s->oam = OAM_FIRST;
    Obj(SPRITE_ATTR0((s->py - POINTER_TIP_Y) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE),
        SPRITE_ATTR1_NONAFFINE((s->px - POINTER_TIP_X) & 0x1FF, FALSE, FALSE, 1), SPRITE_ATTR2(TILE_POINTER, 0, PAL_POINTER));
    Sprite(DOTS_SPRITE_BANNER, DOTS_BANNER_X, DOTS_BANNER_Y);
    Sprite(DOTS_SPRITE_PRESENT, DOTS_PRESENT_X, DOTS_PRESENT_Y);
    Sprite(DOTS_SPRITE_RECORD, DOTS_RECORD_X, DOTS_RECORD_Y);
    Sprite(DOTS_SPRITE_BACK, DOTS_BACK_X, DOTS_BACK_Y);
    for (; s->oam <= OAM_LAST; s->oam++)
        gOamObjects[s->oam].attr0 = SPRITE_ATTR0_CLEAR;
}

// ---------------------------------------------------------------- the traces
// the trace under the touch (the DS's 0x0206d9d0): the first whose box has
// it, if a trace's pixel is under the brush round it; -1 none
static s32 HitTest(s32 x, s32 y)
{
    s32 i, k, r, c, hit = -1;
    for (i = 0; i < DOTS_TRACES; i++)
    {
        const struct EnDotsTrace * d = &sEnDotsTraces[i];
        if (x >= d->bx && x <= d->bx + d->bw && y >= d->by && y <= d->by + d->bh)
        {
            hit = i;
            break;
        }
    }
    if (hit < 0)
        return -1;
    // (any trace's pixel: the DS's masks are all in one buffer)
    for (r = 0; r < 8; r++)
        for (c = 0; c < 8; c++)
        {
            s32 px = x - 4 + c, py = y - 4 + r;
            if (!(sEnDotsBrush[r] & (0x80 >> c)))
                continue;
            for (k = 0; k < DOTS_TRACES; k++)
            {
                const struct EnDotsTrace * d = &sEnDotsTraces[k];
                s32 mx = px - d->mx, my = py - d->my;
                if (mx >= 0 && mx < d->mw && my >= 0 && my < d->mh && G(d->mask)[my * d->mw + mx])
                    return hit;
            }
        }
    return -1;
}

// two traces joined (unless they are already)
static void Join(s32 p, s32 q)
{
    struct EnDots * s = &gEnDots;
    u32 a = p < q ? p : q, b = p < q ? q : p, k;
    s32 ax, ay, bx, by;
    for (k = 0; k < s->count; k++)
        if (s->a[k] == a && s->b[k] == b)
            return;
    if (s->count >= MAX_LINES)
        return;
    s->a[s->count] = a;
    s->b[s->count] = b;
    s->count++;
    Ends(s->count - 1, &ax, &ay, &bx, &by);
    MarkLine(ax, ay, bx, by, TRUE);
}

static void TakeLast(void)
{
    struct EnDots * s = &gEnDots;
    s32 ax, ay, bx, by;
    Ends(s->count - 1, &ax, &ay, &bx, &by);
    s->count--;
    MarkLine(ax, ay, bx, by, TRUE);
}

// the US build's check (the DS's 0x0206d294): every line one of the name's,
// the six counted all there, the A's legs whole
bool32 EnDotsRight(void)
{
    struct EnDots * s = &gEnDots;
    u32 k, counted = 0, has = 0;
    for (k = 0; k < s->count; k++)
    {
        u32 kind = sEnDotsKinds[s->a[k]][s->b[k]];
        if (kind == 0)
            return FALSE;
        if (kind == 1)
            counted++;
        has |= 1 << kind;
    }
    if (counted != DOTS_COUNTED)
        return FALSE;
    // 4-10, or 4-7 and 7-10; 4-11, or 4-8 and 8-11
    if (!(has & (1 << 4)) && !((has & (1 << 2)) && (has & (1 << 6))))
        return FALSE;
    return (has & (1 << 5)) || ((has & (1 << 3)) && (has & (1 << 7)));
}

// a frame: DOTS_ON, DOTS_PRESENT (L: the lines checked) or DOTS_RECORD (R)
u32 EnDotsFrame(void)
{
    struct EnDots * s = &gEnDots;
    u32 held = gJoypad.heldKeys, pressed = gJoypad.pressedKeys;
    s32 state, dragging, ax, ay;
    s8 lit0, lit1;
    // the pointer
    if (held & DPAD_LEFT)
        s->px = s->px < POINTER_SPEED ? 0 : s->px - POINTER_SPEED;
    else if (held & DPAD_RIGHT)
        s->px = s->px + POINTER_SPEED > DISPLAY_WIDTH - 1 ? DISPLAY_WIDTH - 1 : s->px + POINTER_SPEED;
    if (held & DPAD_UP)
        s->py = s->py < POINTER_SPEED ? 0 : s->py - POINTER_SPEED;
    else if (held & DPAD_DOWN)
        s->py = s->py + POINTER_SPEED > DISPLAY_HEIGHT - 1 ? DISPLAY_HEIGHT - 1 : s->py + POINTER_SPEED;
    if (++s->pointerTimer > 1)
    {
        s->pointerTimer = 0;
        s->pointerColour = (s->pointerColour + 1) & 0xF;
    }
    // the touch (the DS's 0x0206e204): 1 held, 2 let go this frame
    state = (held & A_BUTTON) ? 1 : s->touched ? 2 : 0;
    s->touched = (held & A_BUTTON) != 0;
    dragging = s->start >= 0;
    s->end = -1;
    if (state == 0)
        s->start = -1;
    else if (s->start < 0)
        s->start = HitTest(s->px, s->py);
    else
    {
        s->end = HitTest(s->px, s->py);
        if (s->end == s->start)
            s->end = -1;
        if (s->end >= 0 && state == 2)
        {
            Join(s->start, s->end);
            PlaySE(DOTS_SE_JOIN);
            s->start = -1;
        }
    }
    // Back: the last line white for a frame, then away
    if (s->undo)
    {
        s->undo = FALSE;
        TakeLast();
        PlaySE(DOTS_SE_BACK);
    }
    else if ((pressed & B_BUTTON) && s->count && s->start < 0)
    {
        s32 bx, by;
        s->undo = TRUE;
        Ends(s->count - 1, &ax, &ay, &bx, &by);
        MarkLine(ax, ay, bx, by, FALSE);
    }
    // the line being drawn and the traces lit, as they change
    {
        bool32 on = s->start >= 0;
        s16 x0 = 0, y0 = 0;
        if (on)
        {
            x0 = sEnDotsTraces[s->start].cx;
            y0 = sEnDotsTraces[s->start].cy;
        }
        if (on != s->bandOn || (on && (x0 != s->bx0 || y0 != s->by0 || s->px != s->bx1 || s->py != s->by1)))
        {
            if (s->bandOn)
                MarkLine(s->bx0, s->by0, s->bx1, s->by1, FALSE);
            s->bandOn = on;
            s->bx0 = x0;
            s->by0 = y0;
            s->bx1 = s->px;
            s->by1 = s->py;
            if (on)
                MarkLine(s->bx0, s->by0, s->bx1, s->by1, FALSE);
        }
        s->bandWhite = s->end >= 0;
    }
    lit0 = s->start;
    lit1 = s->end;
    if (lit0 != s->litA || lit1 != s->litB)
    {
        if (s->litA >= 0) MarkTrace(s->litA);
        if (s->litB >= 0) MarkTrace(s->litB);
        if (lit0 >= 0) MarkTrace(lit0);
        if (lit1 >= 0) MarkTrace(lit1);
        s->litA = lit0;
        s->litB = lit1;
    }
    if (++s->cycleTimer >= DOTS_CYCLE_FRAMES)
    {
        s->cycleTimer = 0;
        if (++s->cycle >= 6)
            s->cycle = 0;
    }
    ShowDirty();
    // the buttons (not while a line is drawn)
    if (dragging)
        return DOTS_ON;
    if (pressed & R_BUTTON)
        return DOTS_RECORD;
    if (pressed & L_BUTTON)
        return DOTS_PRESENT;
    return DOTS_ON;
}

#endif

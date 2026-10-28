// English patch, the RFTA build: the fifth episode's fingerprints (the DS's
// fingerprint screens; tools/en/rfta/fingerprint.py has what they were read
// off). Three screens on the GBA's one:
//   the fingers: the case's picture, a cross moved with the + pad; A on a
//     finger (its square shows) dusts it, B goes back (not on the first case)
//   the dusting: the DS's green grid, the powder a byte a pixel; A drops
//     powder where the ring points (the DS's four stamps, four frames a
//     touch), R held blows it away (the DS's microphone), B goes back; a
//     quarter of the rows each frame (ARM code in IWRAM, en_fingerprint_arm.s)
//     blows, counts and marks what changed; the finger is found when enough
//     of its print holds powder and none of the ring round it does
//   the comparison: the found print and the chosen person's, the meter and
//     the counter, the card below (the + pad picks, A compares): three
//     sweeps, the matching points counted, "Match found." or not
// The script hands over with command 68 (translate.py: the DS's 74 9 n, the
// 74 5 0 of the fingerprints' sections, its 74 8 37-3D) and the screens run
// the DS's sections back (13B-142, 146, file 35's C9 and CA, 12A, 12B).
#include "global.h"
#include "main.h"
#include "background.h"
#include "script.h"
#include "ewram.h"
#include "animation.h"
#include "constants/process.h"
#include "constants/oam_allocations.h"
#include "constants/songs.h"
#include "investigation.h"
#include "sound.h"
#include "utils.h"
#include "graphics.h"
#include "en_rfta.h"

#if RFTA

struct EnFpPiece { s16 dx, dy; u8 shape, size; u16 tile; u8 last; };
struct EnFpStamp { u32 offset; u16 count; };
struct EnFpMask { u32 planes; u16 need; u8 x, y, w, h; };
struct EnFpFinger { s16 quad[8]; s16 x, y; u8 type, mask; };
struct EnFpCase { u16 bg; u8 count, answer; const struct EnFpFinger * fingers; u8 points[16][2]; };
#include "data/en_rfta_fingerprint.h"
#include "data/en_rfta_luminol_sections.h"
extern const u8 gEnFingerprintGfx[];

// the sections the screens run (the DS's 0x0207be54; C9 and CA are file
// 35's, after the luminol's stain lines in the chapters that have it)
#define SEC_FIRST_FINGER 0x13B          // case 0: choose a finger
#define SEC_HOW_TO_DUST 0x13C
#define SEC_BACK_CASE0 0x13D
#define SEC_GLOVE 0x13E
#define SEC_CLEAR_PRINT 0x13F
#define SEC_NO_MATCH_CASE0 0x141
#define SEC_MATCH_CASE0 0x142
#define SEC_MATCH_CASE1 0x146
#define SEC_NO_MATCH_CASE2 0x12A
#define SEC_MATCH_CASE2 0x12B
#define SHARED_BACK 8                   // file 35's C9, CA (shared 1-7 the stains', C2-C8)
#define SHARED_NO_PRINT 9
#define FLAG_DUSTED 0x1B                // the dusting's how-to seen (the DS's)
#define FLAG_GLOVE 0x1C                 // the glove print found: the print beside the blood next

enum { FP_OFF, FP_ENTER, FP_STARTED, FP_SCRIPT, FP_SELECT, FP_TO_SELECT, FP_TO_DUST, FP_DUST, FP_FOUND,
       FP_TO_COMPARE, FP_COMPARE, FP_COMPARING, FP_RESULT, FP_LEAVE, FP_END };
enum { SCR_NONE, SCR_PICTURE, SCR_DUST, SCR_COMPARE, SCR_OTHER };

#define TILE_BASE 0x1A0                 // OBJ tiles 0x1A0-0x27F (the luminol's): the sets
#define PAL_UI 8
#define PAL_FACE 9
#define OAM_FIRST OAM_IDX_GENERAL_2     // 57-87
#define OAM_LAST 87
#define DUST_PAL 15                     // BG palette 15: the dusting screen's
#define BLOW 0x30                       // taken off a pass (the DS's 0x60 microphone level)
#define CURSOR_SPEED 2
#define PRINT_PX (EN_FP_PRINT_TW * 8)
#define PRINT_PY (EN_FP_PRINT_TH * 8)

struct EnFpBand { u8 * powder; const u8 * print, * count, * ring; u32 rows, blow, y; u32 * dirty; u32 good, bad; };
struct EnFpRender { u8 * powder; u32 * dirty; u32 * tiles; u32 max; const u8 * shade; };

struct EnFp
{
    u8 mode, phase, caseIdx, finger;
    u8 pending, after, screen, person;
    u16 timer, sweep;
    s16 curX, curY;
    u8 frame, band, emit[2];
    u8 repeat, blowing, demo, pass;
    u8 count, shown, scripted, oam;
    u16 points;                         // the points of this comparison (bits)
    u16 drawn;                          // those crossed so far
    u32 seed;
    u32 good, bad;
    u16 saveBg3cnt, saveBg3hofs, saveBg3vofs, savedMap;
    u32 dirty[19];
    u8 fromState, fromVar1, fromVar2, fromPad;  // the investigation's process as the 68 0 found it
    struct InvestigationStruct fromInv;         // and its buttons
};
// in the old script heap (ewram.h): the state after the luminol's, the powder
// (a byte a pixel) where the movies unpack theirs, BG3's map while it is ours
#define gEnFp (*(struct EnFp *)(EWRAM_START + 0x11FC0 + 0xFE00))
#define sPowder ((u8 *)(EWRAM_START + 0x11FC0 + 0x10000))
#define sMapBackup ((u16 *)(EWRAM_START + 0x11FC0 + 0x19600))

extern const u8 gEnFpCodeStart[];
extern const u8 gEnFpCodeEnd[];
extern const u8 gEnFpShade[];
extern u32 gEnMovieCode[];
#define Band ((void (*)(struct EnFpBand *))((u8 *)gEnMovieCode + 0))
#define Render ((u32 (*)(struct EnFpRender *))((u8 *)gEnMovieCode + 4))
#define SHADE ((const u8 *)gEnMovieCode + (gEnFpShade - gEnFpCodeStart))

void UpdateScrollPromptSprite(struct Main *, u32);   // investigation.c

static const struct EnFpCase * Case(void)
{
    return &sEnFpCases[gEnFp.caseIdx];
}

static const struct EnFpFinger * Finger(void)
{
    return &Case()->fingers[gEnFp.finger];
}

static const struct EnFpMask * Mask(void)
{
    return &sEnFpMasks[Finger()->mask];
}

static u32 Rand(u32 n)
{
    gEnFp.seed = gEnFp.seed * 1103515245 + 12345;
    return ((gEnFp.seed >> 16) * n) >> 16;
}

bool32 EnFingerprintActive(void)
{
    return gEnFp.mode != FP_OFF;
}

void EnFingerprintReset(void)
{
    gEnFp.mode = FP_OFF;
}

static void SetMode(u32 mode)
{
    gEnFp.mode = mode;
    gEnFp.phase = 0;
    gEnFp.timer = 0;
}

// ---------------------------------------------------------------- sprites
#define sOam (gEnFp.oam)

static void BeginSprites(void)
{
    sOam = OAM_FIRST;
}

static void EndSprites(void)
{
    for (; sOam <= OAM_LAST; sOam++)
        gOamObjects[sOam].attr0 = SPRITE_ATTR0_CLEAR;
}

static void HideSprites(void)
{
    BeginSprites();
    EndSprites();
}

// a sprite of the set loaded (its pieces from sEnFpPieces[first])
static void Sprite(u32 first, s32 x, s32 y, u32 flags)
{
    const struct EnFpPiece * p = &sEnFpPieces[first];
    for (;; p++)
    {
        struct OamAttrs * oam;
        s32 px = x + p->dx, py = y + p->dy;
        if (sOam > OAM_LAST)
            return;
        oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0(py & 0xFF, ST_OAM_AFFINE_OFF, (flags & 1) ? ST_OAM_OBJ_BLEND : ST_OAM_OBJ_NORMAL,
                                  FALSE, ST_OAM_4BPP, p->shape);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE(px & 0x1FF, (flags & 2) != 0, (flags & 4) != 0, p->size);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + p->tile, 1, PAL_UI);
        if (p->last)
            return;
    }
}

static void LoadSet(u32 offset, u32 tiles)
{
    DmaCopy16(3, gEnFingerprintGfx + offset, OBJ_VRAM0 + TILE_BASE * 32, tiles * 32);
    DmaCopy16(3, sEnFpUiPalette, OBJ_PLTT + PAL_UI * 32, 32);
}

// the examine pointer's graphics and colours, the lists' colours (as the luminol leaves them)
static void RestoreSprites(void)
{
    HideSprites();
    DmaCopy16(3, gGfxInvestigationExamineCursor, OBJ_VRAM0 + 0x3200, 0x200);
    DmaCopy16(3, gPalInvestigationExamineCursors, OBJ_PLTT + 0x100, 0x20);
    DmaCopy16(3, gPalChoiceSelected, OBJ_PLTT + 0x120, 0x40);
}

// ---------------------------------------------------------------- the screens
static void ChangeBg(u32 bg)
{
    gMain.previousBG = gMain.currentBG;
    gMain.currentBG = bg;
    gMain.currentBgStripe = 1;
}

// the room's own picture (as the investigation's buttons expect it)
static u32 RoomBg(void)
{
    return gMain.roomData[gMain.currentRoomId][0];
}

static bool32 BgChanged(void)
{
    return gMain.currentBgStripe == 0;
}

static void TextBlend(void)
{
    gIORegisters.lcd_bldcnt = BLDCNT_TGT1_BG1 | BLDCNT_TGT2_BG2 | BLDCNT_TGT2_BG3 | BLDCNT_TGT2_OBJ | BLDCNT_EFFECT_BLEND;
    gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(0x1F, 0x7);
    gIORegisters.lcd_bldy = 0;
}

static void HidePerson(void)
{
    ChangeAnimationActivity(&gAnimation[1], FALSE);
}

// the investigation's buttons out of the way, every frame (a section's 1C 3
// slides them in)
static void HideActions(void)
{
    struct InvestigationStruct * inv = &gInvestigation;
    inv->inactiveActions = 0xF;
    inv->inactiveActionButtonY = 0xE0;
    inv->actionState = 4;
}

// BG3 ours (the dusting's 16 colours or the comparison's 256): its control
// and map kept to give back
static void TakeBg3(bool32 colours16)
{
    struct EnFp * f = &gEnFp;
    struct IORegisters * io = &gIORegisters;
    u32 r, c;
    if (!f->savedMap)
    {
        f->savedMap = TRUE;
        f->saveBg3cnt = io->lcd_bg3cnt;
        f->saveBg3hofs = io->lcd_bg3hofs;
        f->saveBg3vofs = io->lcd_bg3vofs;
        DmaCopy16(3, gBG3MapBuffer, sMapBackup, 0x800);
    }
    gMain.isBGScrolling = FALSE;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(3) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256
                   | (colours16 ? BGCNT_16COLOR : BGCNT_256COLOR);
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
        {
            u32 v = 630;        // (the blank tile, InitBG3's)
            if (r >= 1 && r <= 20 && c >= 1 && c <= 30)
                v = (r - 1) * 30 + c - 1;
            gBG3MapBuffer[r * 32 + c] = colours16 ? (v | (DUST_PAL << 12)) : v;
        }
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
}

static void GiveBackBg3(void)
{
    struct EnFp * f = &gEnFp;
    struct IORegisters * io = &gIORegisters;
    if (!f->savedMap)
        return;
    f->savedMap = FALSE;
    DmaCopy16(3, sMapBackup, gBG3MapBuffer, 0x800);
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    io->lcd_bg3cnt = f->saveBg3cnt;
    io->lcd_bg3hofs = f->saveBg3hofs;
    io->lcd_bg3vofs = f->saveBg3vofs;
}

// the case's picture (the fingers), through the game's background
static void ShowPicture(void)
{
    struct EnFp * f = &gEnFp;
    GiveBackBg3();
    LoadSet(EN_FP_SET_SELECT, EN_FP_SET_SELECT_TILES);
    f->screen = SCR_PICTURE;
    if (gMain.currentBG != Case()->bg)
        ChangeBg(Case()->bg);
    else
        CopyBGDataToVram(gMain.currentBG);
}

static void ShowDust(void)
{
    struct EnFp * f = &gEnFp;
    u32 i;
    CpuCopy32(gEnFpCodeStart, gEnMovieCode, gEnFpCodeEnd - gEnFpCodeStart);
    TakeBg3(TRUE);
    DmaCopy16(3, sEnFpDustPalette, BG_PLTT + DUST_PAL * 32, 32);
    DmaFill32(3, 0, sPowder, DISPLAY_WIDTH * DISPLAY_HEIGHT);
    for (i = 0; i < ARRAY_COUNT(f->dirty); i++)
        f->dirty[i] = 0xFFFFFFFF;
    {
        struct EnFpRender r = { sPowder, f->dirty, (u32 *)BG_CHAR_ADDR(1), 600, SHADE };
        Render(&r);
    }
    LoadSet(EN_FP_SET_DUST, EN_FP_SET_DUST_TILES);
    f->screen = SCR_DUST;
    f->band = 0;
    f->good = f->bad = 0;
    f->emit[0] = f->emit[1] = 0;
    f->blowing = 0;
    f->curX = Mask()->x + Mask()->w / 2;
    f->curY = Mask()->y + Mask()->h / 2;
}

// ---------------------------------------------------------------- the powder
static void MarkDirty(s32 x0, s32 y0, s32 x1, s32 y1)
{
    struct EnFp * f = &gEnFp;
    s32 tx, ty;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > DISPLAY_WIDTH - 1) x1 = DISPLAY_WIDTH - 1;
    if (y1 > DISPLAY_HEIGHT - 1) y1 = DISPLAY_HEIGHT - 1;
    for (ty = y0 >> 3; ty <= y1 >> 3; ty++)
        for (tx = x0 >> 3; tx <= x1 >> 3; tx++)
        {
            u32 t = ty * 30 + tx;
            f->dirty[t >> 5] |= 1 << (t & 31);
        }
}

// one of the DS's stamps where the ring is: each dot a random 0-190 more
static void Deposit(s32 cx, s32 cy)
{
    const struct EnFpStamp * st = &sEnFpStamps[Rand(4)];
    const s8 * p = (const s8 *)(gEnFingerprintGfx + st->offset);
    u32 i;
    for (i = 0; i < st->count; i++, p += 2)
    {
        s32 x = cx + p[0], y = cy + p[1];
        u8 * q;
        u32 v;
        if ((u32)x >= DISPLAY_WIDTH || (u32)y >= DISPLAY_HEIGHT)
            continue;
        q = &sPowder[y * DISPLAY_WIDTH + x];
        v = *q + 2 * Rand(0x60);
        *q = v > 255 ? 255 : v;
    }
    MarkDirty(cx - 60, cy - 60, cx + 60, cy + 60);
}

static void Emit(void)
{
    struct EnFp * f = &gEnFp;
    u32 k = f->emit[0] <= f->emit[1] ? 0 : 1;
    f->emit[k] = 4;
}

// a quarter of the rows: blown, counted; the finger found (TRUE) after the
// last quarter when enough of its print has powder and its ring none
static bool32 PowderStep(u32 blow)
{
    struct EnFp * f = &gEnFp;
    const struct EnFpMask * m = Mask();
    const u8 * planes = gEnFingerprintGfx + m->planes;
    struct EnFpBand b;
    u32 y0 = f->band * 40, i;
    bool32 found = FALSE;
    for (i = 0; i < 2; i++)
        if (f->emit[i])
        {
            f->emit[i]--;
            Deposit(f->curX, f->curY);
        }
    if (f->band == 0)
        f->good = f->bad = 0;
    b.powder = sPowder + y0 * DISPLAY_WIDTH;
    b.print = planes + y0 * 30;
    b.count = planes + 4800 + y0 * 30;
    b.ring = planes + 9600 + y0 * 30;
    b.rows = 40;
    b.blow = blow;
    b.y = y0;
    b.dirty = f->dirty;
    b.good = f->good;
    b.bad = f->bad;
    Band(&b);
    f->good = b.good;
    f->bad = b.bad;
    if (++f->band == 4)
    {
        f->band = 0;
        found = f->good >= m->need && f->bad == 0;
    }
    {
        struct EnFpRender r = { sPowder, f->dirty, (u32 *)BG_CHAR_ADDR(1), 150, SHADE };
        Render(&r);
    }
    return found;
}

// ---------------------------------------------------------------- the comparison
static void PutPrint(u32 print, u32 tx, u32 ty, u32 base)
{
    // 4bpp tiles to the BG's 256 colours, from palette entry base
    const u8 * src = gEnFingerprintGfx + EN_FP_PRINTS + print * (EN_FP_PRINT_TW * EN_FP_PRINT_TH * 32);
    u32 x, y, i;
    for (y = 0; y < EN_FP_PRINT_TH; y++)
        for (x = 0; x < EN_FP_PRINT_TW; x++)
        {
            vu16 * dst = (vu16 *)(BG_CHAR_ADDR(1) + ((ty + y) * 30 + tx + x) * 64);
            for (i = 0; i < 32; i++, src++)
                dst[i] = (base + (*src & 15)) | (base + (*src >> 4)) << 8;
        }
}

static void PutCard(u32 card)
{
    const u8 * src = gEnFingerprintGfx + EN_FP_CARDS + card * (30 * 6 * 32);
    vu16 * dst = (vu16 *)(BG_CHAR_ADDR(1) + EN_FP_CARD_ROW * 30 * 64);
    u32 i;
    for (i = 0; i < 30 * 6 * 32; i++, src++)
        dst[i] = (EN_FP_PAL_CARD + (*src & 15)) | (EN_FP_PAL_CARD + (*src >> 4)) << 8;
}

static void PutFace(u32 person)
{
    const u8 * src = gEnFingerprintGfx + EN_FP_FACES + person * (32 + 64 * 32);
    DmaCopy16(3, src, OBJ_PLTT + PAL_FACE * 32, 32);
    DmaCopy16(3, src + 32, OBJ_VRAM0 + (TILE_BASE + EN_FP_FACE_TILE) * 32, 64 * 32);
}

// a pixel of the BG's 256 colours (x, y on screen)
static void PutPixel(s32 x, s32 y, u32 c)
{
    vu16 * p;
    u32 off;
    if ((u32)x >= DISPLAY_WIDTH || (u32)y >= DISPLAY_HEIGHT)
        return;
    off = ((y >> 3) * 30 + (x >> 3)) * 64 + (y & 7) * 8 + (x & 7);
    p = (vu16 *)(BG_CHAR_ADDR(1) + (off & ~1));
    *p = (off & 1) ? ((*p & 0xFF) | c << 8) : ((*p & 0xFF00) | c);
}

static void PutCross(u32 i)
{
    const u8 * pt = Case()->points[i];
    s32 k, x, y;
    for (k = 0; k < 2; k++)
    {
        x = (k ? EN_FP_RIGHT_PRINT_X : EN_FP_LEFT_PRINT_X) * 8 + pt[0];
        y = (k ? EN_FP_RIGHT_PRINT_Y : EN_FP_LEFT_PRINT_Y) * 8 + pt[1];
        PutPixel(x - 2, y, EN_FP_PAL_CROSS); PutPixel(x - 1, y, EN_FP_PAL_CROSS); PutPixel(x, y, EN_FP_PAL_CROSS);
        PutPixel(x + 1, y, EN_FP_PAL_CROSS); PutPixel(x + 2, y, EN_FP_PAL_CROSS);
        PutPixel(x, y - 2, EN_FP_PAL_CROSS); PutPixel(x, y - 1, EN_FP_PAL_CROSS);
        PutPixel(x, y + 1, EN_FP_PAL_CROSS); PutPixel(x, y + 2, EN_FP_PAL_CROSS);
    }
}

static void Meter(u32 count, bool32 match)
{
    vu16 * pal = (vu16 *)BG_PLTT + EN_FP_PAL_METER;
    u32 i;
    for (i = 0; i < EN_FP_SEGMENTS; i++)
        pal[i] = sEnFpSegment[i][i < count ? (match ? 2 : 1) : 0];
}

// the found print's colours: the DS's greys, or as dusted while compared
static void LeftColours(bool32 dusted)
{
    DmaCopy16(3, dusted ? sEnFpGreenPalette : sEnFpPrintPalette, BG_PLTT + EN_FP_PAL_LEFT * 2, 32);
}

static void ShowPerson(void)
{
    struct EnFp * f = &gEnFp;
    PutPrint(sEnFpPersonPrint[f->person], EN_FP_RIGHT_PRINT_X, EN_FP_RIGHT_PRINT_Y, EN_FP_PAL_RIGHT);
    PutCard(f->person);
    f->shown = f->person;
    PutFace(f->person);
}

// the comparison screen afresh: the found print, the person's, no points
static void ShowCompare(void)
{
    struct EnFp * f = &gEnFp;
    TakeBg3(FALSE);
    DmaCopy16(3, gEnFingerprintGfx + EN_FP_COMPARE_TILES, BG_CHAR_ADDR(1), EN_FP_CARD_ROW * 30 * 64);
    DmaCopy16(3, gEnFingerprintGfx + EN_FP_COMPARE_PAL + 64, BG_PLTT + 64, (EN_FP_PAL_LEFT - 32) * 2);
    DmaCopy16(3, sEnFpPrintPalette, BG_PLTT + EN_FP_PAL_RIGHT * 2, 32);
    LeftColours(FALSE);
    PutPrint(sEnFpPersonPrint[Case()->answer], EN_FP_LEFT_PRINT_X, EN_FP_LEFT_PRINT_Y, EN_FP_PAL_LEFT);
    LoadSet(EN_FP_SET_COMPARE, EN_FP_SET_COMPARE_TILES);
    ShowPerson();
    Meter(0, FALSE);
    f->count = 0;
    f->screen = SCR_COMPARE;
}

// the points this comparison finds: all 16 for the print's owner (3, 7 and
// 6 in the sweeps, as the DS counts them), two to four for another
static u32 PointsFor(u32 person)
{
    u32 k, n, bitsSet = 0;
    if (person == Case()->answer)
        return 0xFFFF;
    n = 2 + (person + gEnFp.caseIdx) % 3;
    for (k = 0; k < n; k++)
        bitsSet |= 1 << ((person * 5 + k * 7) % 16);
    return bitsSet;
}

static u32 PassOf(u32 point)
{
    struct EnFp * f = &gEnFp;
    u32 k, j = 0;
    if (f->points == 0xFFFF)
        return point < 3 ? 0 : point < 10 ? 1 : 2;
    for (k = 0; k < point; k++)
        if (f->points & (1 << k))
            j++;
    return j == 0 ? 0 : j == 1 ? 1 : 2;
}

static void DrawCompareSprites(void)
{
    struct EnFp * f = &gEnFp;
    BeginSprites();
    Sprite(EN_FP_COMPARE_DIGIT0 + f->count / 10, EN_FP_DIGITS_X, EN_FP_DIGITS_Y, 0);
    Sprite(EN_FP_COMPARE_DIGIT0 + f->count % 10, EN_FP_DIGITS_X + 8, EN_FP_DIGITS_Y, 0);
    // the person's face with their card (not under the script's text box)
    if ((f->mode == FP_COMPARE || f->mode == FP_TO_COMPARE) && f->shown == f->person)
    {
        struct OamAttrs * oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0(EN_FP_FACE_Y, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE(EN_FP_FACE_X, FALSE, FALSE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + EN_FP_FACE_TILE, 1, PAL_FACE);
        if (f->mode == FP_COMPARE)
            Sprite(EN_FP_COMPARE_COMPARE, 158, 140, 0);
    }
    if (f->mode == FP_COMPARING && f->phase == 0)
    {
        s32 y = EN_FP_LEFT_PRINT_Y * 8 + f->sweep - 8;
        Sprite(EN_FP_COMPARE_SCAN, EN_FP_LEFT_PRINT_X * 8, y, 1);
        Sprite(EN_FP_COMPARE_SCAN, EN_FP_RIGHT_PRINT_X * 8, y, 1);
    }
    EndSprites();
}

// ---------------------------------------------------------------- the sections
// the script waiting at its 15; a section that leaves its text box up (file
// 35's C9: the DS's 74 5 0 put it away itself) has it slid away here
static bool32 ScriptStopped(void)
{
    if (!(gScriptContext.flags & SCRIPT_LOOP))
        return FALSE;
    if (gMain.showTextboxCharacters)
    {
        SlideTextbox(0);
        HideActions();
    }
    return TRUE;
}

static u32 SharedSection(u32 shared)
{
    u32 c = gMain.scenarioIdx;
    return sEnLuminolShared[c - RFTA_FIRST_CHAPTER] + shared - 1;
}

// a section of the DS's over the screen now on, the screen `after` once
// the script stops after its 68 1 (the DS's 74 5 0)
static void RunSection(u32 section, u32 after)
{
    struct EnFp * f = &gEnFp;
    f->pending = FALSE;
    f->after = after;
    ChangeScriptSection(section);
    SlideTextbox(1);
    SetMode(FP_SCRIPT);
}

// ---------------------------------------------------------------- leaving
// the fingerprints over: the game's sprites and BG3 back, the investigation
// as the 68 0 found it (the menu, examining, talking: its process and
// buttons), and on with the script: a match's section, or none (Back) the
// section's end as its 1C 3 would have made it
static void Leave(u32 section)
{
    struct EnFp * f = &gEnFp;
    struct InvestigationStruct * inv = &gInvestigation;
    RestoreSprites();
    TextBlend();
    GiveBackBg3();
    f->mode = FP_OFF;
    f->screen = SCR_NONE;
    ChangeAnimationActivity(&gAnimation[1], TRUE);
    *inv = f->fromInv;
    gMain.process[GAME_PROCESS_STATE] = f->fromState;
    gMain.process[GAME_PROCESS_VAR1] = f->fromVar1;
    gMain.process[GAME_PROCESS_VAR2] = f->fromVar2;
    if (section)
    {
        ChangeScriptSection(section);
        SlideTextbox(1);
        return;
    }
    // (script_commands.c, Command1C 3; the text box already away)
    SlideTextbox(0);
    gScriptContext.textboxState = 1;
    gIORegisters.lcd_dispcnt &= ~DISPCNT_BG1_ON;
    gIORegisters.lcd_bg1vofs = ~80;
    inv->selectedActionYOffset = 0;
    if (f->fromState == INVESTIGATION_INSPECT)
        SetInactiveActionButtons(inv, 1);
    if (f->fromState == INVESTIGATION_TALK)
    {
        SetInactiveActionButtons(inv, 4);
        inv->actionState = 4;
        inv->inactiveActionButtonY = 0xE0;
    }
    if (f->fromState == INVESTIGATION_PRESENT)
        SetInactiveActionButtons(inv, 8);
    inv->inspectionPaused = FALSE;
}

// ---------------------------------------------------------------- each screen
static bool32 InQuad(const s16 * q, s32 x, s32 y)
{
    // inside the quadrilateral (convex, either way round)
    s32 i, sgn = 0;
    for (i = 0; i < 4; i++)
    {
        s32 ax = q[2 * i], ay = q[2 * i + 1], bx = q[2 * ((i + 1) & 3)], by = q[2 * ((i + 1) & 3) + 1];
        s32 cr = (bx - ax) * (y - ay) - (by - ay) * (x - ax);
        if (cr == 0)
            continue;
        if (sgn == 0)
            sgn = cr > 0 ? 1 : -1;
        else if ((cr > 0 ? 1 : -1) != sgn)
            return FALSE;
    }
    return TRUE;
}

// the finger under the cross that may be picked (the DS's 0x0207f4cc: on the
// first case the fingers in the blood until the glove print, then the print
// beside them), or -1
static s32 FingerAt(s32 x, s32 y)
{
    const struct EnFpCase * c = Case();
    u32 i;
    for (i = 0; i < c->count; i++)
    {
        const struct EnFpFinger * fg = &c->fingers[i];
        if (gEnFp.caseIdx == 0 && (fg->type == 1) != GetFlag(0, FLAG_GLOVE))
            continue;
        // (the DS tests the cross's 4 x 4 square against the quadrilateral)
        if (InQuad(fg->quad, x, y) || InQuad(fg->quad, x + 3, y) || InQuad(fg->quad, x, y + 3)
            || InQuad(fg->quad, x + 3, y + 3))
            return i;
    }
    return -1;
}

static void MoveCursor(void)
{
    struct EnFp * f = &gEnFp;
    u32 held = gJoypad.heldKeys;
    s32 lo = 0, hiX = DISPLAY_WIDTH - 1, hiY = DISPLAY_HEIGHT - 1;
    if (held & DPAD_LEFT)
        f->curX = f->curX - CURSOR_SPEED < lo ? lo : f->curX - CURSOR_SPEED;
    if (held & DPAD_RIGHT)
        f->curX = f->curX + CURSOR_SPEED > hiX ? hiX : f->curX + CURSOR_SPEED;
    if (held & DPAD_UP)
        f->curY = f->curY - CURSOR_SPEED < lo ? lo : f->curY - CURSOR_SPEED;
    if (held & DPAD_DOWN)
        f->curY = f->curY + CURSOR_SPEED > hiY ? hiY : f->curY + CURSOR_SPEED;
}

static void DrawSelectSprites(bool32 player)
{
    struct EnFp * f = &gEnFp;
    s32 k, finger;
    BeginSprites();
    if (player)
    {
        finger = FingerAt(f->curX, f->curY);
        Sprite(EN_FP_SELECT_BANNER, -8, 0, 0);
        if (finger >= 0)
            Sprite(EN_FP_SELECT_BOX, Case()->fingers[finger].x, Case()->fingers[finger].y, 0);
        Sprite(EN_FP_SELECT_SQUARE, f->curX - 3, f->curY - 3, 0);
        for (k = 0; k < 4; k++)
            Sprite(EN_FP_SELECT_HLINE, k * 64, f->curY, 0);
        for (k = 0; k < 3; k++)
            Sprite(EN_FP_SELECT_VLINE, f->curX, k * 64, 0);
        if (f->caseIdx != 0)
            Sprite(EN_FP_SELECT_BACK, 0, DISPLAY_HEIGHT - 16, 0);
        if (finger >= 0)
            Sprite(EN_FP_SELECT_EXAMINE, DISPLAY_WIDTH - 72, DISPLAY_HEIGHT - 16, 0);
    }
    EndSprites();
}

static void SelectMode(void)
{
    struct EnFp * f = &gEnFp;
    s32 finger;
    MoveCursor();
    finger = FingerAt(f->curX, f->curY);
    if ((gJoypad.pressedKeys & A_BUTTON) && finger >= 0)
    {
        PlaySE(SE001_MENU_CONFIRM);
        f->finger = finger;
        SetMode(FP_TO_DUST);
        return;
    }
    if ((gJoypad.pressedKeys & B_BUTTON) && f->caseIdx != 0)
    {
        PlaySE(SE002_MENU_CANCEL);
        SetMode(FP_LEAVE);
        return;
    }
    DrawSelectSprites(TRUE);
}

static void DrawDustSprites(bool32 player)
{
    struct EnFp * f = &gEnFp;
    BeginSprites();
    if (player)
    {
        Sprite(EN_FP_DUST_BANNER, -8, 0, 0);
        Sprite(EN_FP_DUST_BRUSH, f->curX - 8, f->curY - 8, 0);
        Sprite(EN_FP_DUST_BACK, 0, DISPLAY_HEIGHT - 16, 0);
        Sprite(EN_FP_DUST_POWDER, DISPLAY_WIDTH - 112, DISPLAY_HEIGHT - 16, 0);
    }
    if (f->mode == FP_FOUND && f->phase == 0)
    {
        const struct EnFpMask * m = Mask();
        Sprite(EN_FP_DUST_CORNER, m->x - 4, m->y - 4, 0);
        Sprite(EN_FP_DUST_CORNER, m->x + m->w - 4, m->y - 4, 2);
        Sprite(EN_FP_DUST_CORNER, m->x - 4, m->y + m->h - 4, 4);
        Sprite(EN_FP_DUST_CORNER, m->x + m->w - 4, m->y + m->h - 4, 6);
    }
    EndSprites();
}

static void DustMode(void)
{
    struct EnFp * f = &gEnFp;
    MoveCursor();
    if (gJoypad.pressedKeys & B_BUTTON)
    {
        PlaySE(SE002_MENU_CANCEL);
        DrawDustSprites(FALSE);
        RunSection(f->caseIdx == 0 ? SEC_BACK_CASE0 : SharedSection(SHARED_BACK), FP_TO_SELECT);
        return;
    }
    if (gJoypad.pressedKeys & A_BUTTON)
    {
        Emit();
        f->repeat = 8;
    }
    else if ((gJoypad.heldKeys & A_BUTTON) && --f->repeat == 0)
    {
        Emit();
        f->repeat = 8;
    }
    if (PowderStep((gJoypad.heldKeys & R_BUTTON) ? BLOW : 0))
    {
        SetMode(FP_FOUND);
        return;
    }
    DrawDustSprites(TRUE);
}

// found: on the first case the script's lines at once; on the others the
// DS's jingle and corner marks first
static void FoundMode(void)
{
    struct EnFp * f = &gEnFp;
    if (f->caseIdx == 0)
    {
        DrawDustSprites(FALSE);
        if (Finger()->type == 1)
            RunSection(SEC_CLEAR_PRINT, FP_COMPARE);
        else
        {
            ChangeFlag(0, FLAG_GLOVE, TRUE);
            RunSection(SEC_GLOVE, FP_TO_SELECT);
        }
        return;
    }
    if (f->phase == 0)
    {
        if (f->timer == 0)
            PlaySE(BGM017_JINGLE_IDEA);
        DrawDustSprites(FALSE);
        if (++f->timer < 60)
            return;
        f->phase = 1;
    }
    DrawDustSprites(FALSE);
    if (Finger()->type == 1)
        SetMode(FP_TO_COMPARE);
    else
        RunSection(SharedSection(SHARED_NO_PRINT), FP_TO_SELECT);
}

static void CompareMode(void)
{
    struct EnFp * f = &gEnFp;
    if (gJoypad.pressedKeys & (DPAD_LEFT | DPAD_RIGHT))
    {
        PlaySE(SE000_MENU_CHANGE);
        f->person = (gJoypad.pressedKeys & DPAD_LEFT) ? (f->person + EN_FP_PEOPLE - 1) % EN_FP_PEOPLE
                                                      : (f->person + 1) % EN_FP_PEOPLE;
        ShowPerson();
    }
    else if (gJoypad.pressedKeys & A_BUTTON)
    {
        PlaySE(SE001_MENU_CONFIRM);
        f->points = PointsFor(f->person);
        f->drawn = 0;
        f->pass = 0;
        f->sweep = 0;
        f->count = 0;
        Meter(0, FALSE);
        LeftColours(TRUE);
        PutCard(EN_FP_CARD_STATUS);
        gIORegisters.lcd_bldcnt = BLDCNT_TGT1_OBJ | BLDCNT_TGT2_BG3 | BLDCNT_EFFECT_BLEND;
        gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(10, 8);
        SetMode(FP_COMPARING);
    }
    DrawCompareSprites();
}

// three sweeps (2 rows a frame), the points crossed as the sweep passes
// them, then counted up one by one (SE0C6); "Comparison complete."
static void Status(u32 card)
{
    struct EnFp * f = &gEnFp;
    if (f->shown != card)
    {
        f->shown = card;
        PutCard(card);
    }
}

static u32 CountBits(u32 v)
{
    u32 n = 0;
    for (; v; v &= v - 1)
        n++;
    return n;
}

static void ComparingMode(void)
{
    struct EnFp * f = &gEnFp;
    u32 i;
    f->frame++;
    if (f->phase < 3)
        Status(EN_FP_CARD_STATUS + ((f->frame >> 4) & 3));
    switch (f->phase)
    {
    case 0:     // the sweep
        f->sweep += 2;
        for (i = 0; i < 16; i++)
            if ((f->points & (1 << i)) && !(f->drawn & (1 << i)) && PassOf(i) == f->pass
                && Case()->points[i][1] < f->sweep)
            {
                f->drawn |= 1 << i;
                PutCross(i);
            }
        if (f->sweep >= PRINT_PY + 8)
        {
            f->phase = 1;
            f->timer = 0;
        }
        break;
    case 1:     // the count, a point every 8 frames
        if (++f->timer % 8)
            break;
        if (f->count < CountBits(f->drawn))
        {
            f->count++;
            Meter(f->count, FALSE);
            PlaySE(EN_FP_SE_SCAN);
            break;
        }
        f->phase = 2;
        f->timer = 0;
        break;
    case 2:     // a pause, the next sweep
        if (++f->timer < 20)
            break;
        if (++f->pass < 3)
        {
            f->sweep = 0;
            f->phase = 0;
            break;
        }
        Status(EN_FP_CARD_STATUS + 4);
        f->phase = 3;
        f->timer = 0;
        break;
    case 3:     // "Comparison complete."
        if (++f->timer < 40)
            break;
        TextBlend();
        SetMode(FP_RESULT);
        break;
    }
    DrawCompareSprites();
}

// "Match found." (SE0C0, a flash, the meter's top alight) or "No matches
// found." (the DS's BGM032), two seconds, then the script
static void ResultMode(void)
{
    struct EnFp * f = &gEnFp;
    bool32 match = f->person == Case()->answer;
    if (f->timer == 0)
    {
        Status(match ? EN_FP_CARD_MATCH : EN_FP_CARD_NO_MATCH);
        if (match)
        {
            Meter(f->count, TRUE);
            PlaySE(EN_FP_SE_MATCH);
            StartHardwareBlend(3, 1, 4, 0x3F);
        }
        else
            PlaySE(BGM032_JINGLE_WRONG_CHOICE);
    }
    DrawCompareSprites();
    if (++f->timer < 120)
        return;
    if (match)
    {
        SetMode(FP_END);
        return;
    }
    if (f->caseIdx == 0)
        RunSection(SEC_NO_MATCH_CASE0, FP_COMPARE);
    else if (f->caseIdx == 2)
        RunSection(SEC_NO_MATCH_CASE2, FP_COMPARE);
    else
    {
        ShowCompare();
        SetMode(FP_COMPARE);
    }
}

// ---------------------------------------------------------------- the process
static void StartPlayer(u32 mode)
{
    struct EnFp * f = &gEnFp;
    switch (mode)
    {
    case FP_COMPARE:
        if (f->screen != SCR_COMPARE)
        {
            SetMode(FP_TO_COMPARE);
            return;
        }
        ShowCompare();
        break;
    case FP_TO_SELECT:
    case FP_TO_DUST:
    case FP_TO_COMPARE:
    case FP_LEAVE:
        SetMode(mode);
        return;
    case FP_DUST:
        f->repeat = 8;
        break;
    }
    SetMode(mode);
}

// a fade to black, the next screen, a fade back
static bool32 FadeTo(void (*show)(void), u32 then)
{
    struct EnFp * f = &gEnFp;
    if (gMain.blendMode)
        return FALSE;
    switch (f->phase)
    {
    case 0:
        StartHardwareBlend(2, 1, 2, 0x3F);
        f->phase = 1;
        return FALSE;
    case 1:
        HideSprites();
        show();
        f->phase = 2;
        return FALSE;
    case 2:
        if (!BgChanged())
            return FALSE;
        StartHardwareBlend(1, 1, 2, 0x3F);
        f->phase = 3;
        return FALSE;
    }
    return TRUE;
}

static void ShowSelectScreen(void)
{
    struct EnFp * f = &gEnFp;
    ShowPicture();
    f->curX = DISPLAY_WIDTH / 2;
    f->curY = DISPLAY_HEIGHT / 2;
}

static void ShowCompareScreen(void)
{
    gEnFp.person = 0;
    ShowCompare();
}

void EnFingerprintProcess(struct Main * main, struct InvestigationStruct * inv)
{
    struct EnFp * f = &gEnFp;
    UpdateScrollPromptSprite(main, 0);
    if (f->mode != FP_OFF)
        HideActions();
    switch (f->mode)
    {
    case FP_OFF:
        SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_MAIN, 0, 0, main);
        return;
    case FP_ENTER:      // the picture (the script has shown it), the sprites
        HidePerson();
        HideActions();
        gOamObjects[OAM_IDX_POINTER].attr0 = SPRITE_ATTR0_CLEAR;
        ShowPicture();
        f->curX = DISPLAY_WIDTH / 2;
        f->curY = DISPLAY_HEIGHT / 2;
        SetMode(FP_STARTED);
        return;
    case FP_STARTED:    // the script's 1C 3 / 15 after the 68 0, then the first finger's how-to
        if (!BgChanged() || !ScriptStopped())
            return;
        if (f->caseIdx == 0)
            RunSection(SEC_FIRST_FINGER, FP_SELECT);
        else
            SetMode(FP_SELECT);
        return;
    case FP_SCRIPT:     // a section: the player's turn when it stops after its 68 1
        if (f->screen == SCR_DUST)
        {
            if (f->demo == 2)
            {
                if (f->timer < 120)
                    f->timer++;
                PowderStep(f->timer < 120 ? BLOW : 0);
            }
            else
                PowderStep(0);
            DrawDustSprites(FALSE);
        }
        else if (f->screen == SCR_COMPARE)
        {
            // (the card blank under the text box; the player's turn puts it back)
            Status(EN_FP_CARD_BLANK);
            DrawCompareSprites();
        }
        else
            DrawSelectSprites(FALSE);
        if (f->pending && ScriptStopped())
        {
            f->pending = FALSE;
            f->demo = 0;
            StartPlayer(f->after);
        }
        return;
    case FP_SELECT:
        SelectMode();
        return;
    case FP_TO_SELECT:
        if (FadeTo(ShowSelectScreen, FP_SELECT))
            SetMode(FP_SELECT);
        else
            DrawSelectSprites(FALSE);
        return;
    case FP_TO_DUST:
        if (FadeTo(ShowDust, FP_DUST))
        {
            if (f->caseIdx == 0 && !GetFlag(0, FLAG_DUSTED))
            {
                ChangeFlag(0, FLAG_DUSTED, TRUE);
                RunSection(SEC_HOW_TO_DUST, FP_DUST);
            }
            else
                StartPlayer(FP_DUST);
        }
        else if (f->phase == 3)
            DrawDustSprites(FALSE);
        return;
    case FP_DUST:
        DustMode();
        return;
    case FP_FOUND:
        FoundMode();
        return;
    case FP_TO_COMPARE:
        if (FadeTo(ShowCompareScreen, FP_COMPARE))
            SetMode(FP_COMPARE);
        if (f->phase == 3 || f->mode == FP_COMPARE)
            DrawCompareSprites();
        return;
    case FP_COMPARE:
        CompareMode();
        return;
    case FP_COMPARING:
        ComparingMode();
        return;
    case FP_RESULT:
        ResultMode();
        return;
    case FP_END:        // the match: the room back (cases 0, 1), the section
        if (main->blendMode)
            return;
        if (f->phase == 0)
        {
            StartHardwareBlend(2, 1, 2, 0x3F);
            f->phase = 1;
            return;
        }
        if (f->phase == 1)
        {
            HideSprites();
            GiveBackBg3();
            // (the cloth's picture on the last case: its section shows the room itself)
            ChangeBg(f->caseIdx == 2 ? Case()->bg : RoomBg());
            f->phase = 2;
            return;
        }
        if (!BgChanged())
            return;
        Leave(f->caseIdx == 0 ? SEC_MATCH_CASE0 : f->caseIdx == 1 ? SEC_MATCH_CASE1 : SEC_MATCH_CASE2);
        StartHardwareBlend(1, 1, 2, 0x3F);
        return;
    case FP_LEAVE:      // Back from the fingers: the room, the investigation's menu
        if (main->blendMode)
            return;
        if (f->phase == 0)
        {
            HideSprites();
            StartHardwareBlend(2, 1, 2, 0x3F);
            f->phase = 1;
            return;
        }
        if (f->phase == 1)
        {
            GiveBackBg3();
            ChangeBg(RoomBg());
            f->phase = 2;
            return;
        }
        if (!BgChanged())
            return;
        Leave(0);
        StartHardwareBlend(1, 1, 2, 0x3F);
        return;
    }
}

// ---------------------------------------------------------------- the script
// GBA command 68 (tools/en/rfta/translate.py: FINGERPRINT), its argument
// sub << 8 | n:
//   0 n  start case n (the DS's 74 9 n): its picture is up; the script goes
//        on to its 1C 3 / 15, the screens take over
//   1    the player's turn once the script stops (the DS's 74 5 0)
//   2    Ema's powder (74 8 37), 3 her blowing (74 8 38)
//   4    the fingers' picture again (74 8 39)
//   5    the comparison screen (74 8 3A, 3B: afresh)
//   6    background n (74 8 3C: the evidence room's picture, 0xBA)
//   7    the comparison screen back as it was (74 8 3D)
bool32 Command68(struct ScriptContext * scriptCtx)
{
    struct EnFp * f = &gEnFp;
    u32 arg = scriptCtx->scriptPtr[1], sub = arg >> 8, n = arg & 0xFF;
    if (gMain.process[GAME_PROCESS] != INVESTIGATION_PROCESS)
    {
        scriptCtx->scriptPtr += 2;
        return 0;
    }
    switch (sub)
    {
    case 0:
        DmaFill16(3, 0, f, sizeof(*f));
        f->fromState = gMain.process[GAME_PROCESS_STATE];
        f->fromVar1 = gMain.process[GAME_PROCESS_VAR1];
        f->fromVar2 = gMain.process[GAME_PROCESS_VAR2];
        f->fromInv = gInvestigation;
        f->caseIdx = n;
        f->seed = gMain.frameCounter ^ 0x5A5A;
        f->finger = 0;
        f->shown = 0xFF;
        SetMode(FP_ENTER);
        SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_FINGERPRINT, 0, 0, (&gMain));
        break;
    case 1:
        f->pending = TRUE;
        break;
    case 2:
        if (f->screen == SCR_DUST)
        {
            f->curX = EN_FP_DUST_X + 0x80 * 10 / 11;
            f->curY = 0x40 * 10 / 11;
            Emit();
        }
        break;
    case 3:
        f->demo = 2;
        f->timer = 0;
        break;
    case 4:
        HideSprites();
        ShowPicture();
        break;
    case 5:
        if (f->screen != SCR_COMPARE || n)
        {
            HideSprites();
            ShowCompareScreen();
        }
        break;
    case 6:
        HideSprites();
        GiveBackBg3();
        ChangeBg(n);
        f->screen = SCR_OTHER;
        break;
    case 7:
        ShowCompare();
        break;
    }
    scriptCtx->scriptPtr += 2;
    return 0;
}

#endif // RFTA

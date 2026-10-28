// English patch, the RFTA build: the fifth episode's luminol (the DS's
// luminol screen, its 0x020809xx-0x02082fxx; tools/en/rfta/luminol.py has
// what it was read off). The room turns red, a nozzle is moved with the +
// pad and A sprays a puff of mist where it points; a stain the mist reaches
// starts to glow, and three sprays, each after the glow of the last has
// settled, bring it out: corner marks round it, then its three pictures,
// then its lines. B goes back to the investigation, L to the other half of
// a wide room, as on the DS's touch screen ("Back", the arrows).
//
// The DS's Court Record has "Spray" on the luminol (the Court Record here:
// A, court_record.c); the parking lot's tutorial (chapter 22) starts it from
// the script (74 6 0, here 67 0), sprays once to show how (74 6 1, 67 1),
// hands over (its 74 5 0 there, 67 2) and leaves after the stain's question
// (74 5 0 in 97/98, 67 4). After a stain's lines from the Court Record the
// DS goes back to the red room (file 35's 74 5 0, 67 3).
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
#include "court_record.h"
#include "sound.h"
#include "utils.h"
#include "graphics.h"
#include "en_rfta.h"

#if RFTA

struct EnStain
{
    u8 bg;              // the room's background
    u8 flag;            // set when it is found
    u8 shared;          // its lines: file 35's C2-C8 as 1-7 (every luminol chapter has them), or 0:
    u16 section;        // the chapter's own section (the tutorial's, chapter 22)
    s16 x, y;           // in the room's picture
    u8 w, h;
    u8 zoom[3];         // the pictures it is found in
    u16 gfx;            // its mask, 64 x 32 (gEnLuminolGfx)
};
#include "data/en_rfta_luminol.h"
#include "data/en_rfta_luminol_sections.h"
extern const u8 gEnLuminolGfx[];

#define TUTORIAL_CHAPTER 22             // the one chapter with a stain's lines of its own

enum { LUM_OFF, LUM_ENTER, LUM_SCRIPT, LUM_SPRAY, LUM_SCROLL, LUM_FOUND, LUM_STAIN, LUM_BACK, LUM_LEAVE };
enum { PEND_NONE, PEND_PLAYER, PEND_RETURN };

// the glow, one state for the whole stain (the DS's 0x020c1c1c): a step every
// other frame from 1, stopping at 63 and 103 until sprayed again; 134 found
#define GLOW_STOP1 63
#define GLOW_STOP2 103
#define GLOW_FOUND 134
#define GLOW_SHOWN_FOUND 255            // found before: its found colours

#define MAX_IN_VIEW 2
#define PUFFS 2
#define PUFF_LIFE 40                    // frames, the DS's
#define PUFF_HOLD 14
#define SPRAY_GAP 15                    // between sprays (the DS's)
#define SPRAY_HALF 16                   // the spray's square: 32 x 32 round the nozzle
#define NOZZLE_SPEED 2

// OBJ tiles 0x1A0-0x27F are the Court Record's and the Move / Talk lists'
// (each loads its own when it opens): free while the luminol is up
#define TILE_MIST 0x1A0                 // 64 x 64
#define TILE_GLOW 0x1E0                 // 2 x 64 x 32
#define TILE_NOZZLE 0x220               // 32 x 32
#define TILE_MARK 0x230                 // 16 x 16
#define TILE_CROSS 0x234                // 16 x 16
#define PAL_SPRITES 8                   // (the examine pointer's)
#define PAL_GLOW 9                      // 9, 10 (the Move / Talk lists')
#define OAM_NOZZLE (OAM_IDX_GENERAL_2 + 0)
#define OAM_MIST (OAM_IDX_GENERAL_2 + 1)
#define OAM_GLOW (OAM_IDX_GENERAL_2 + 3)
#define OAM_MARK (OAM_IDX_GENERAL_2 + 5)
#define OAM_CROSS (OAM_IDX_GENERAL_2 + 9)
#define OAM_COUNT 10

struct EnLuminol
{
    u8 mode, phase, scripted, pending;
    u16 timer;
    u16 roomBg;
    u16 roomPos;                // the room's scroll (a wide room's half)
    s16 nozzleX, nozzleY;
    u8 cooldown;
    u8 found;                   // the stain being found
    u8 inView[MAX_IN_VIEW];     // stains (0xFF none)
    u8 glow[MAX_IN_VIEW];
    u8 puffAge[PUFFS];          // 0: none
    s16 puffX[PUFFS], puffY[PUFFS];
    u8 frame;
    u8 picture;
};
// in the old script heap (ewram.h), after the movies' state and restore record
#define gEnLuminol (*(struct EnLuminol *)(EWRAM_START + 0x11FC0 + 0xFC00))

void UpdateScrollPromptSprite(struct Main *, u32);   // investigation.c

static u32 LuminolRoom(void)
{
    return gEnLuminol.roomBg;
}

bool32 EnLuminolActive(void)
{
    return gEnLuminol.mode != LUM_OFF;
}

void EnLuminolReset(void)
{
    gEnLuminol.mode = LUM_OFF;
}

// ---------------------------------------------------------------- sprites
static void HideSprites(void)
{
    u32 i;
    for (i = 0; i < OAM_COUNT; i++)
        gOamObjects[OAM_NOZZLE + i].attr0 = SPRITE_ATTR0_CLEAR;
}

static void LoadSprites(void)
{
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_MIST, OBJ_VRAM0 + TILE_MIST * 32, 64 * 32);
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_NOZZLE, OBJ_VRAM0 + TILE_NOZZLE * 32, 16 * 32);
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_MARK, OBJ_VRAM0 + TILE_MARK * 32, 4 * 32);
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_CROSS, OBJ_VRAM0 + TILE_CROSS * 32, 4 * 32);
    DmaCopy16(3, sEnLuminolPalette, OBJ_PLTT + PAL_SPRITES * 32, 32);
}

// the examine pointer's graphics and colours, the lists' colours
static void RestoreSprites(void)
{
    HideSprites();
    DmaCopy16(3, gGfxInvestigationExamineCursor, OBJ_VRAM0 + 0x3200, 0x200);
    DmaCopy16(3, gPalInvestigationExamineCursors, OBJ_PLTT + 0x100, 0x20);
    DmaCopy16(3, gPalChoiceSelected, OBJ_PLTT + 0x120, 0x40);
}

// the blend the text box needs (the game's usual), or the mist's: added to
// the room at its level
static void TextBlend(void)
{
    gIORegisters.lcd_bldcnt = BLDCNT_TGT1_BG1 | BLDCNT_TGT2_BG2 | BLDCNT_TGT2_BG3 | BLDCNT_TGT2_OBJ | BLDCNT_EFFECT_BLEND;
    gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(0x1F, 0x7);
    gIORegisters.lcd_bldy = 0;
}

static void MistBlend(u32 level)
{
    gIORegisters.lcd_bldcnt = BLDCNT_TGT2_BG3 | BLDCNT_TGT2_BG2;
    gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(level, 16);
}

// ---------------------------------------------------------------- stains
static u32 SharedSection(u32 shared)
{
    u32 c = gMain.scenarioIdx;
    if (c < RFTA_FIRST_CHAPTER || c > RFTA_LAST_CHAPTER || sEnLuminolShared[c - RFTA_FIRST_CHAPTER] == 0)
        return 0;
    return sEnLuminolShared[c - RFTA_FIRST_CHAPTER] + shared - 1;
}

static bool32 StainHere(const struct EnStain * s)
{
    if (s->bg != (LuminolRoom() & 0x7FFF))
        return FALSE;
    if (s->shared ? SharedSection(s->shared) == 0 : gMain.scenarioIdx != TUTORIAL_CHAPTER)
        return GetFlag(0, s->flag);     // (lines of its own elsewhere: shown if found)
    return TRUE;
}

static s32 ScreenX(const struct EnStain * s)
{
    return s->x - gMain.Bg256_pos_x;
}

// the stains in view: on screen, not more than two (the DS's scenes have two at most)
static void FindStains(void)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 i, n = 0;
    l->roomPos = gMain.Bg256_pos_x;
    for (i = 0; i < MAX_IN_VIEW; i++)
        l->inView[i] = 0xFF;
    for (i = 0; i < EN_STAIN_COUNT && n < MAX_IN_VIEW; i++)
    {
        const struct EnStain * s = &sEnStains[i];
        s32 x = ScreenX(s);
        if (!StainHere(s) || x + s->w <= 0 || x >= DISPLAY_WIDTH)
            continue;
        l->inView[n] = i;
        l->glow[n] = GetFlag(0, s->flag) ? GLOW_SHOWN_FOUND : 0;
        DmaCopy16(3, gEnLuminolGfx + s->gfx, OBJ_VRAM0 + (TILE_GLOW + 32 * n) * 32, 32 * 32);
        n++;
    }
}

static u32 GlowColorIndex(u32 state)
{
    if (state == 0)
        return 0;
    if (state < 32)
        return 1;
    state = 2 + (state - 32) / 8;
    return state > 15 ? 15 : state;
}

static void DrawStains(void)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 i;
    for (i = 0; i < MAX_IN_VIEW; i++)
    {
        struct OamAttrs * oam = &gOamObjects[OAM_GLOW + i];
        vu16 * pal = (vu16 *)(OBJ_PLTT + (PAL_GLOW + i) * 32);
        const struct EnStain * s;
        s32 x, y;
        if (l->inView[i] == 0xFF || l->glow[i] == 0)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            continue;
        }
        s = &sEnStains[l->inView[i]];
        if (l->glow[i] == GLOW_SHOWN_FOUND || l->glow[i] >= GLOW_FOUND)
        {
            pal[1] = EN_GLOW_FOUND_INSIDE;
            pal[2] = EN_GLOW_FOUND_OUTLINE;
        }
        else
            pal[1] = pal[2] = sEnGlowColors[GlowColorIndex(l->glow[i])];
        x = ScreenX(s);
        y = s->y - gMain.Bg256_pos_y;
        if (x <= -64 || x >= DISPLAY_WIDTH)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            continue;
        }
        oam->attr0 = SPRITE_ATTR0(y & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE(x & 0x1FF, FALSE, FALSE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_GLOW + 32 * i, 2, PAL_GLOW + i);
    }
}

// a step every other frame; the stain found when it reaches the top
static s32 AdvanceGlows(void)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 i;
    if (l->frame & 1)
        return -1;
    for (i = 0; i < MAX_IN_VIEW; i++)
    {
        u32 g = l->glow[i];
        if (l->inView[i] == 0xFF || g == 0 || g == GLOW_STOP1 || g == GLOW_STOP2 || g >= GLOW_FOUND)
            continue;
        g = g == 15 || (g > 15 && g < 32) ? 32 : g + 1;
        l->glow[i] = g;
        if (g >= GLOW_FOUND)
            return i;
    }
    return -1;
}

// ---------------------------------------------------------------- the mist
static void Spray(s32 x, s32 y, bool32 hits)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 i, slot = 0;
    for (i = 0; i < PUFFS; i++)
        if (l->puffAge[i] == 0 || l->puffAge[i] > l->puffAge[slot])
            slot = i;
    for (i = 0; i < PUFFS; i++)
        if (l->puffAge[i] == 0)
        {
            slot = i;
            break;
        }
    l->puffAge[slot] = 1;
    l->puffX[slot] = x;
    l->puffY[slot] = y;
    l->cooldown = SPRAY_GAP;
    PlaySE(EN_LUMINOL_SE_SPRAY);
    if (!hits)
        return;
    // the first stain the spray's square meets, not found yet: a step on
    for (i = 0; i < MAX_IN_VIEW; i++)
    {
        const struct EnStain * s;
        s32 sx;
        if (l->inView[i] == 0xFF || l->glow[i] >= GLOW_FOUND)
            continue;
        s = &sEnStains[l->inView[i]];
        sx = ScreenX(s);
        if (x + SPRAY_HALF > sx && x - SPRAY_HALF < sx + s->w && y + SPRAY_HALF > s->y && y - SPRAY_HALF < s->y + s->h)
        {
            l->glow[i]++;
            break;
        }
    }
}

static void DrawMist(void)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 i, level = 0;
    for (i = 0; i < PUFFS; i++)
    {
        struct OamAttrs * oam = &gOamObjects[OAM_MIST + i];
        u32 a = l->puffAge[i];
        if (a == 0)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            continue;
        }
        if (++l->puffAge[i] > PUFF_LIFE)
            l->puffAge[i] = 0;
        a = a < 3 ? a * 6 : a <= PUFF_HOLD ? 16 : 16 - (a - PUFF_HOLD) * 16 / (PUFF_LIFE - PUFF_HOLD);
        if (a > level)
            level = a;
        oam->attr0 = SPRITE_ATTR0((l->puffY[i] - 32) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_BLEND, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE((l->puffX[i] - 32) & 0x1FF, FALSE, FALSE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_MIST, 2, PAL_SPRITES);
    }
    MistBlend(level);
}

static void DrawNozzle(bool32 show)
{
    struct EnLuminol * l = &gEnLuminol;
    struct OamAttrs * oam = &gOamObjects[OAM_NOZZLE];
    if (!show)
    {
        oam->attr0 = SPRITE_ATTR0_CLEAR;
        return;
    }
    oam->attr0 = SPRITE_ATTR0((l->nozzleY - 16) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
    oam->attr1 = SPRITE_ATTR1_NONAFFINE((l->nozzleX - 16) & 0x1FF, FALSE, FALSE, 2);
    oam->attr2 = SPRITE_ATTR2(TILE_NOZZLE, 1, PAL_SPRITES);
}

// the corner marks round the stain being found, the cross at its middle
static void DrawMarks(bool32 show)
{
    struct EnLuminol * l = &gEnLuminol;
    const struct EnStain * s = &sEnStains[l->found];
    s32 x0 = ScreenX(s) - 8, y0 = s->y - 8, x1 = ScreenX(s) + s->w + 8 - 16, y1 = s->y + s->h + 8 - 16;
    u32 i;
    for (i = 0; i < 4; i++)
    {
        struct OamAttrs * oam = &gOamObjects[OAM_MARK + i];
        if (!show)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            continue;
        }
        oam->attr0 = SPRITE_ATTR0(((i & 2) ? y1 : y0) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE(((i & 1) ? x1 : x0) & 0x1FF, i & 1, (i & 2) != 0, 1);
        oam->attr2 = SPRITE_ATTR2(TILE_MARK, 1, PAL_SPRITES);
    }
    if (!show)
    {
        gOamObjects[OAM_CROSS].attr0 = SPRITE_ATTR0_CLEAR;
        return;
    }
    gOamObjects[OAM_CROSS].attr0 = SPRITE_ATTR0((s->y + s->h / 2 - 8) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
    gOamObjects[OAM_CROSS].attr1 = SPRITE_ATTR1_NONAFFINE((ScreenX(s) + s->w / 2 - 8) & 0x1FF, FALSE, FALSE, 1);
    gOamObjects[OAM_CROSS].attr2 = SPRITE_ATTR2(TILE_CROSS, 1, PAL_SPRITES);
}

// ---------------------------------------------------------------- the room
// the room's picture for the half on screen (CopyBGDataToVram: a wide
// picture shows the half its scroll bits start at, 0x8000 the other)
static u32 RoomBg(void)
{
    u32 bg = gEnLuminol.roomBg & 0x7FFF;
    bool32 startsRight = (GetBGControlBits(bg) & BG_MODE_HSCROLL_RIGHT) != 0;
    bool32 right = gEnLuminol.roomPos != 0;
    return bg | (startsRight != right ? 0x8000 : 0);
}

static void ChangeBg(u32 bg)
{
    gMain.previousBG = gMain.currentBG;
    gMain.currentBG = bg;
    gMain.currentBgStripe = 1;
}

static bool32 BgChanged(void)
{
    return gMain.currentBgStripe == 0;
}

// white at once (the hardware too: the frames of a background change don't
// write the registers), then back over four frames
static void Flash(void)
{
    gIORegisters.lcd_bldcnt = 0x3F | BLDCNT_EFFECT_LIGHTEN;
    gIORegisters.lcd_bldy = 16;
    REG_BLDCNT = gIORegisters.lcd_bldcnt;
    REG_BLDY = 16;
}

static void FlashBack(void)
{
    StartHardwareBlend(3, 1, 4, 0x3F);
}

static void HidePerson(void)
{
    ChangeAnimationActivity(&gAnimation[1], FALSE);
}

static void SetMode(u32 mode)
{
    gEnLuminol.mode = mode;
    gEnLuminol.phase = 0;
    gEnLuminol.timer = 0;
}

// the buttons of the investigation out of the way
static void HideActions(void)
{
    struct InvestigationStruct * inv = &gInvestigation;
    SetInactiveActionButtons(inv, 0xF);
    inv->inactiveActionButtonY = 0xE0;
    inv->actionState = 4;
}

// ---------------------------------------------------------------- starting
static void Start(bool32 scripted)
{
    struct EnLuminol * l = &gEnLuminol;
    DmaFill16(3, 0, l, sizeof(*l));
    l->scripted = scripted;
    l->roomBg = gMain.currentBG;
    l->nozzleX = DISPLAY_WIDTH / 2;
    l->nozzleY = 70;
    SetMode(LUM_ENTER);
    HideSprites();
    HideActions();
    UpdateScrollPromptSprite(&gMain, 0);
    gOamObjects[OAM_IDX_POINTER].attr0 = SPRITE_ATTR0_CLEAR;
}

// the Court Record's "Spray" (court_record.c): the record goes, the room
// turns red
void EnLuminolFromRecord(void)
{
    Start(FALSE);
    SET_PROCESS_BACKUP_PTR(INVESTIGATION_PROCESS, INVESTIGATION_LUMINOL, 0, 0, (&gMain));  // (restored as the record goes)
}

// may the Court Record offer it: in an investigation, between its scenes
bool32 EnLuminolAvailable(void)
{
    return gMain.processCopy[GAME_PROCESS] == INVESTIGATION_PROCESS && gMain.process[GAME_PROCESS_VAR2] == 0
        && gMain.scenarioIdx >= RFTA_FIRST_CHAPTER && gEnLuminol.mode == LUM_OFF;
}

// the luminol shown in the Court Record's evidence, where it can be used
bool32 EnRecordSprayable(struct CourtRecord * courtRecord)
{
    return !(courtRecord->flags & COURT_RECORD_VIEW_PROFILES) && courtRecord->displayItemCount
        && courtRecord->displayItemList[courtRecord->selectedItem] == RFTA_LUMINOL_EVIDENCE && EnLuminolAvailable();
}

// "A Spray" left of "R Profiles": the A button's picture (the record's, tile
// 0x1C0) and the label in the record's free tiles 0x1B8 and 0x1D0 ("OK", not
// shown while the record is only looked at; loaded again when it opens)
#define OAM_SPRAY_PROMPT OAM_IDX_GENERAL_2
void EnRecordSprayPrompt(struct CourtRecord * courtRecord, bool32 show)
{
    struct OamAttrs * oam = &gOamObjects[OAM_SPRAY_PROMPT];
    u32 i;
    if (!show || !EnRecordSprayable(courtRecord))
    {
        for (i = 0; i < 3; i++)
            oam[i].attr0 = SPRITE_ATTR0_CLEAR;
        return;
    }
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_SPRAY, OBJ_VRAM0 + 0x1B8 * 32, 8 * 32);
    DmaCopy16(3, gEnLuminolGfx + EN_LUMINOL_GFX_SPRAY + 8 * 32, OBJ_VRAM0 + 0x1D0 * 32, 8 * 32);
    oam[0].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
    oam[0].attr1 = SPRITE_ATTR1_NONAFFINE(96, FALSE, FALSE, 1);
    oam[0].attr2 = SPRITE_ATTR2(0x1C0, 0, 4);
    oam[1].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE);
    oam[1].attr1 = SPRITE_ATTR1_NONAFFINE(112, FALSE, FALSE, 2);
    oam[1].attr2 = SPRITE_ATTR2(0x1B8, 0, 4);
    oam[2].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE);
    oam[2].attr1 = SPRITE_ATTR1_NONAFFINE(144, FALSE, FALSE, 2);
    oam[2].attr2 = SPRITE_ATTR2(0x1D0, 0, 4);
}

// ---------------------------------------------------------------- each frame
static void Leave(void)
{
    struct InvestigationStruct * inv = &gInvestigation;
    struct EnLuminol * l = &gEnLuminol;
    EnLuminolTint(FALSE);
    RestoreSprites();
    TextBlend();
    l->mode = LUM_OFF;
    if (l->scripted)
    {
        // the tutorial's: the script goes on (Ema back), then the menu (the
        // buttons away as at a chapter's start until the script's 1C 3)
        ChangeAnimationActivity(&gAnimation[1], TRUE);
        SetInactiveActionButtons(inv, 0xF);
        inv->inactiveActionButtonY = 0xE0;
        inv->selectedActionYOffset = 0;
        inv->lastActionYOffset = 8;
        inv->selectedAction = 0;
        inv->lastAction = 0;
        inv->actionState = 4;
        SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_MAIN, 0, 0, (&gMain));
    }
    else
    {
        // as the examining ends (B): the person back, the buttons in; the
        // text box as an examined thing's lines leave it (1C 3: slid away)
        gScriptContext.textboxState = 1;
        gMain.advanceScriptContext = FALSE;
        gMain.showTextboxCharacters = FALSE;
        gIORegisters.lcd_dispcnt &= ~DISPCNT_BG1_ON;
        gIORegisters.lcd_bg1vofs = ~80;
        inv->selectedAction = 0;
        inv->lastAction = 0;
        SetInactiveActionButtons(inv, 0xE);
        inv->actionState = 2;
        inv->inactiveActionButtonY = 0xE0;
        inv->selectedActionYOffset = 0x10;
        inv->lastActionYOffset = 0;
        inv->inspectionPaused = FALSE;
        SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_INSPECT, 2, 0, (&gMain));
    }
}

// the script stopped (its 15) with the text box away
static bool32 ScriptStopped(void)
{
    return (gScriptContext.flags & SCRIPT_LOOP) && !gMain.showTextboxCharacters;
}

static void SprayMode(void)
{
    struct EnLuminol * l = &gEnLuminol;
    s32 found;
    u32 held = gJoypad.heldKeys;
    if (held & DPAD_LEFT)
        l->nozzleX = l->nozzleX > NOZZLE_SPEED ? l->nozzleX - NOZZLE_SPEED : 0;
    if (held & DPAD_RIGHT)
        l->nozzleX = l->nozzleX + NOZZLE_SPEED < DISPLAY_WIDTH - 1 ? l->nozzleX + NOZZLE_SPEED : DISPLAY_WIDTH - 1;
    if (held & DPAD_UP)
        l->nozzleY = l->nozzleY > NOZZLE_SPEED ? l->nozzleY - NOZZLE_SPEED : 0;
    if (held & DPAD_DOWN)
        l->nozzleY = l->nozzleY + NOZZLE_SPEED < DISPLAY_HEIGHT - 1 ? l->nozzleY + NOZZLE_SPEED : DISPLAY_HEIGHT - 1;
    if (l->cooldown)
        l->cooldown--;
    if ((gJoypad.pressedKeys & A_BUTTON) && l->cooldown == 0)
        Spray(l->nozzleX, l->nozzleY, TRUE);
    else if ((gJoypad.pressedKeys & B_BUTTON) && !l->scripted)
    {
        PlaySE(SE002_MENU_CANCEL);
        SetMode(LUM_LEAVE);
        return;
    }
    else if ((gJoypad.pressedKeys & L_BUTTON) && !l->scripted
          && (GetBGControlBits(gMain.currentBG) & BG_MODE_SIZE_480x160)
          && (gMain.Bg256_pos_x == 0 || gMain.Bg256_pos_x == 240))
    {
        PlaySE(SE001_MENU_CONFIRM);
        gMain.isBGScrolling = TRUE;
        gMain.horizontolBGScrollSpeed = gMain.Bg256_pos_x == 0 ? 6 : -6;
        SetMode(LUM_SCROLL);
        return;
    }
    found = AdvanceGlows();
    if (found >= 0)
    {
        l->found = l->inView[found];
        SetMode(LUM_FOUND);
    }
}

// the stain's three pictures: marks for 32 frames, then a flash before each
// picture (24 frames each), a last flash, its lines
static void FoundMode(void)
{
    struct EnLuminol * l = &gEnLuminol;
    const struct EnStain * s = &sEnStains[l->found];
    switch (l->phase)
    {
    case 0:
        DrawNozzle(FALSE);
        DrawMarks(TRUE);
        if (++l->timer < 32)
            return;
        DrawMarks(FALSE);
        l->picture = 0;
        l->phase = 1;
        // fall through
    case 1:     // a flash and the next picture
        HideSprites();
        if (l->picture == 0)
        {
            EnLuminolTint(FALSE);
            TextBlend();
        }
        Flash();
        PlaySE(SE033_CAMERA_SOUND_ZOOM_IN);
        ChangeBg(s->zoom[l->picture]);
        l->phase = 2;
        return;
    case 2:
        if (!BgChanged())
            return;
        FlashBack();
        l->timer = 0;
        l->phase = 3;
        return;
    case 3:
        if (gMain.blendMode || ++l->timer < 22)
            return;
        if (++l->picture < 3)
        {
            l->phase = 1;
            return;
        }
        // its lines, the flag set (and the DS's two that go with a stain of a day)
        Flash();
        FlashBack();
        ChangeFlag(0, s->flag, TRUE);
        if (gMain.scenarioIdx == 22 && s->flag == 0x13)
            ChangeFlag(0, 0xD, TRUE);
        if (gMain.scenarioIdx == 29 && s->flag == 0x17)
            ChangeFlag(0, 0xE, TRUE);
        l->pending = PEND_NONE;
        ChangeScriptSection(s->shared ? SharedSection(s->shared) : s->section);
        SlideTextbox(1);    // (the script runs once the box is up, as an examined thing's lines)
        SetMode(LUM_STAIN);
        return;
    }
}

void EnLuminolProcess(struct Main * main, struct InvestigationStruct * inv)
{
    struct EnLuminol * l = &gEnLuminol;
    l->frame++;
    UpdateScrollPromptSprite(main, 0);
    switch (l->mode)
    {
    case LUM_OFF:
        SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_MAIN, 0, 0, main);
        return;
    case LUM_ENTER:     // to black, the room red, back
        if (main->blendMode)
            return;
        if (l->phase == 0)
        {
            StartHardwareBlend(2, 1, 2, 0x3F);
            l->phase = 1;
            return;
        }
        if (l->phase == 1)
        {
            HidePerson();
            LoadSprites();
            EnLuminolTint(TRUE);
            FindStains();
            DrawStains();
            StartHardwareBlend(1, 1, 2, 0x3F);
            l->phase = 2;
            return;
        }
        MistBlend(0);
        SetMode(l->scripted ? LUM_SCRIPT : LUM_SPRAY);
        return;
    case LUM_SCRIPT:    // the tutorial's lines, the demonstration's mist
        DrawStains();
        DrawNozzle(FALSE);
        if (l->pending == PEND_PLAYER && ScriptStopped())
        {
            l->pending = PEND_NONE;
            SetMode(LUM_SPRAY);
            break;
        }
        DrawMist();
        if (l->puffAge[0] == 0 && l->puffAge[1] == 0)
            TextBlend();    // (the text box's: the mist's blend shows it solid)
        return;
    case LUM_SPRAY:
        SprayMode();
        DrawStains();
        DrawNozzle(l->mode == LUM_SPRAY);
        break;
    case LUM_SCROLL:
        DrawNozzle(FALSE);
        DrawStains();
        if (main->isBGScrolling || (main->Bg256_pos_x != 0 && main->Bg256_pos_x != 240))
            break;
        FindStains();
        SetMode(LUM_SPRAY);
        break;
    case LUM_FOUND:
        if (l->phase == 0)
            DrawStains();
        FoundMode();
        if (l->mode != LUM_FOUND || l->phase != 0)
            return;
        break;
    case LUM_STAIN:     // its lines over the last picture
        if (l->pending == PEND_RETURN && ScriptStopped())
        {
            l->pending = PEND_NONE;
            SetMode(LUM_BACK);
        }
        return;
    case LUM_BACK:      // the picture to black, the red room back
        if (main->blendMode)
            return;
        if (l->phase == 0)
        {
            StartHardwareBlend(2, 2, 1, 0x3F);
            l->phase = 1;
            return;
        }
        if (l->phase == 1)
        {
            ChangeBg(RoomBg());
            l->phase = 2;
            return;
        }
        if (l->phase == 2)
        {
            if (!BgChanged())
                return;
            LoadSprites();
            EnLuminolTint(TRUE);
            FindStains();
            DrawStains();
            StartHardwareBlend(1, 1, 2, 0x3F);
            l->phase = 3;
            return;
        }
        MistBlend(0);
        SetMode(LUM_SPRAY);
        return;
    case LUM_LEAVE:     // to black, the room in colour, back
        if (main->blendMode)
            return;
        if (l->phase == 0)
        {
            HideSprites();
            StartHardwareBlend(2, 1, 2, 0x3F);
            l->phase = 1;
            return;
        }
        if (l->phase == 1)
        {
            if (main->currentBG != RoomBg())
            {
                ChangeBg(RoomBg());
                l->phase = 2;
                return;
            }
            l->phase = 2;
        }
        if (!BgChanged())
            return;
        Leave();
        StartHardwareBlend(1, 1, 2, 0x3F);
        return;
    }
    DrawMist();
}

// ---------------------------------------------------------------- the script
// GBA command 67 n (tools/en/rfta/translate.py: LUMINOL)
//   0 the tutorial's luminol: the room turns red (the script waits)
//   1 Ema's spray, to show how
//   2 the player's turn once the script stops
//   3 after a stain's lines: the red room again once the script stops
//   4 leave the luminol (the script waits)
bool32 Command67(struct ScriptContext * scriptCtx)
{
    struct EnLuminol * l = &gEnLuminol;
    u32 sub = scriptCtx->scriptPtr[1];
    if (gMain.process[GAME_PROCESS] != INVESTIGATION_PROCESS)
    {
        scriptCtx->scriptPtr += 2;
        return 0;
    }
    switch (sub)
    {
    case 0:
        if (l->mode == LUM_OFF)
        {
            Start(TRUE);
            SET_PROCESS_PTR(INVESTIGATION_PROCESS, INVESTIGATION_LUMINOL, 0, 0, (&gMain));
            return 1;
        }
        if (l->mode == LUM_ENTER)
            return 1;
        break;
    case 1:
        if (l->mode != LUM_OFF)
            Spray(152, 40, FALSE);
        break;
    case 2:
        l->pending = PEND_PLAYER;
        break;
    case 3:
        l->pending = PEND_RETURN;
        break;
    case 4:
        if (l->mode == LUM_OFF)
            break;
        if (l->mode != LUM_LEAVE)
        {
            SetMode(LUM_LEAVE);
            l->scripted = TRUE;
        }
        return 1;
    }
    scriptCtx->scriptPtr += 2;
    return 0;
}

#endif // RFTA

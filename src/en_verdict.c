#include "global.h"
#include "main.h"
#include "sound.h"
#include "utils.h"
#include "court.h"
#include "constants/songs.h"
#include "constants/oam_allocations.h"
#define EN_VERDICT_TABLES
#include "en_effects.h"

// The English verdict, as the DS English release shows it: one sprite per
// letter. Each letter waits for its delay, then zooms from 2x to 1x over ten
// frames and lands with a thud and a short shake. "Guilty" comes in letter by
// letter; "Not Guilty" comes in as two words. Letters, delays and placement
// are the DS ones (tools/en/make_effects.py).

#define VERDICT_ZOOM_FRAMES 10
#define VERDICT_PALETTE 5
// nine sprites: the court record action slots (unused here), the verdict
// kanji slots and the button prompts; 57 onwards is rewritten every frame
#define OAM_IDX_VERDICT_LETTERS (OAM_IDX_EVIDENCE_RECORD_ACTIONS + 3)

static const struct VerdictLetter * VerdictLetters(bool32 notGuilty, u32 * count)
{
    if (notGuilty)
    {
        *count = ARRAY_COUNT(gVerdictLettersNotGuilty);
        return gVerdictLettersNotGuilty;
    }
    *count = ARRAY_COUNT(gVerdictLettersGuilty);
    return gVerdictLettersGuilty;
}

void EnVerdictHide(void)
{
    u32 i;
    for (i = 0; i < ARRAY_COUNT(gVerdictLettersNotGuilty); i++)
        gOamObjects[OAM_IDX_VERDICT_LETTERS + i].attr0 = SPRITE_ATTR0_CLEAR;
}

void EnVerdictLoad(bool32 notGuilty)
{
    u32 i, count;
    const struct VerdictLetter * l = VerdictLetters(notGuilty, &count);
    for (i = 0; i < count; i++, l++)
        DmaCopy16(3, gEnVerdictLetterTiles + l->src, OBJ_VRAM0 + l->vram, l->size);
    DmaCopy16(3, notGuilty ? gEnVerdictPalNotGuilty : gEnVerdictPalGuilty, OBJ_PLTT + VERDICT_PALETTE * 0x20, 0x20);
    EnVerdictHide();
    StartHardwareBlend(3, 1, 8, 0x1F);
}

// one frame of the letters; process VAR1 counts the frames, VAR2 is set for
// "Not Guilty". Returns TRUE once every letter has landed.
bool32 EnVerdictAnimate(struct Main * main)
{
    u32 i, count, n = main->process[GAME_PROCESS_VAR1];
    bool32 done = TRUE, thud = FALSE;
    const struct VerdictLetter * l = VerdictLetters(main->process[GAME_PROCESS_VAR2], &count);
    for (i = 0; i < count; i++, l++)
    {
        struct OamAttrs * oam = &gOamObjects[OAM_IDX_VERDICT_LETTERS + i];
        s16 inv;
        u32 t;
        if (n < l->delay)
        {
            oam->attr0 = SPRITE_ATTR0_CLEAR;
            done = FALSE;
            continue;
        }
        t = n - l->delay;
        if (t > VERDICT_ZOOM_FRAMES)
            t = VERDICT_ZOOM_FRAMES;
        if (t < VERDICT_ZOOM_FRAMES)
            done = FALSE;
        if (t == VERDICT_ZOOM_FRAMES - 2)
            thud = TRUE;
        oam->attr2 = (l->vram / TILE_SIZE_4BPP) | (VERDICT_PALETTE << 12);
        if (t == VERDICT_ZOOM_FRAMES)
        {
            // landed: a plain sprite (an affine double-size one costs several
            // times the per-line sprite time, and nine of them do not fit)
            oam->attr0 = ((l->y + 32) & 0xFF) | (l->tall ? 0x8000 : 0);
            oam->attr1 = ((l->x + (l->tall ? 16 : 32)) & 0x1FF) | 0xC000;
            continue;
        }
        inv = fix_inverse(0x200 - 0x100 * t / VERDICT_ZOOM_FRAMES);
        gOamObjects[i * 4 + 0].attr3 = inv;
        gOamObjects[i * 4 + 1].attr3 = 0;
        gOamObjects[i * 4 + 2].attr3 = 0;
        gOamObjects[i * 4 + 3].attr3 = inv;
        oam->attr0 = (l->y & 0xFF) | 0x300 | (l->tall ? 0x8000 : 0); // affine, double size, square / tall
        oam->attr1 = (l->x & 0x1FF) | 0xC000 | (i << 9);             // 64x64 / 32x64, matrix i
    }
    if (thud)
    {
        PlaySE(SE02C_GAME_OVER);
        main->shakeTimer = 4;
        main->shakeIntensity = 1;
    }
    if (n < 0xFF)
        main->process[GAME_PROCESS_VAR1]++;
    return done;
}

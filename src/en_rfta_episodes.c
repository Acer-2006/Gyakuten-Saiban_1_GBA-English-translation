#include "global.h"
#include "en_rfta.h"
#if RFTA
// Rise from the Ashes (make RFTA=1): the episode select and the "new episode"
// screen with five plates. They are episode_load_processes.c's, the four rows
// made five: the plates are 25 rows apart (the four were 32; a plate is 24
// rows high), from 2 rows above the screen to 2 above the text box, and
// staggered 24 columns (the four were 32), the last at the same place as
// the fourth was. The fifth title plate goes after the four in OBJ VRAM.
#include "main.h"
#include "animation.h"
#include "script.h"
#include "sound.h"
#include "save.h"
#include "agb_sram.h"
#include "utils.h"
#include "vwf.h"
#include "ewram.h"
#include "graphics.h"
#include "case_data.h"
#include "constants/script.h"
#include "constants/songs.h"
#include "constants/process.h"
#include "constants/oam_allocations.h"

void EpisodeInit(struct Main * main);
void EpisodeLoadGfx(struct Main * main);

#define TILE_LOCKED 0x1A0                 // "? ? ?"
#define TILE_TITLE(i) (0x1E0 + (i) * 0x40) // the titles, 0x40 tiles a plate (two 64x32 halves)
#define PAL_SELECTED 9
#define PAL_PLAIN 10
#define PLATES_OAM (&gOamObjects[OAM_IDX_GENERIC_TEXT_ICON])
#define SELECTED_X 56
#define SELECTED_Y 56

static s32 RowY(u32 i)
{
    return 25 * i - 2;
}

static u32 RowX(u32 i)
{
    return 8 + 24 * i;
}

static u32 PlateAttr2(struct Main * main, u32 i, u32 j, u32 palette)
{
    if ((main->caseEnabledFlags >> i) & 1)
        return SPRITE_ATTR2(TILE_TITLE(i), 0, palette) + j * 0x20;
    return SPRITE_ATTR2(TILE_LOCKED, 0, palette) + j * 0x20;
}

static void SetPlate(struct OamAttrs * oam, s32 y, u32 affine)
{
    u32 j;
    for (j = 0; j < 2; j++)
        oam++->attr0 = SPRITE_ATTR0(y & 0xFF, affine, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, 1);
}

static void SetPlateX(struct OamAttrs * oam, u32 x)
{
    u32 j;
    for (j = 0; j < 2; j++)
        oam++->attr1 = SPRITE_ATTR1_AFFINE((x + j * 64) & 0x1FF, 0, 3);
}

// EpisodeLoadGfx and the fifth plate: its title, and the five rows. The
// fifth title's tiles are where a person's are in the game (OBJ VRAM 0x5800
// on), so the people are put away first: an upload of theirs still queued
// would land on the plates the next frame.
static void LoadGfx(struct Main * main)
{
    struct OamAttrs * oam = PLATES_OAM;
    u32 i, j;
    ResetAnimationSystem();
    EpisodeLoadGfx(main);
    DmaCopy16(3, gRftaEpisodeTitle, OBJ_VRAM0 + TILE_TITLE(RFTA_EPISODE) * TILE_SIZE_4BPP, 0x800);
    for (i = 0; i < EPISODES; i++)
    {
        SetPlate(oam, RowY(i), ST_OAM_AFFINE_OFF);
        for (j = 0; j < 2; j++)
            oam[j].attr2 = PlateAttr2(main, i, j, PAL_SELECTED);
        oam += 2;
    }
}

// the plates slide in from the right together, each stopping at its place
// (the four's slide: xPosCounter 152, 184, 216, 248 for columns 8 ... 104)
static bool32 SlideIn(struct Main * main)
{
    struct OamAttrs * oam = PLATES_OAM;
    bool32 done = TRUE;
    u32 i;
    main->xPosCounter += 6;
    main->xPosCounter &= 0x1FF;
    for (i = 0; i < EPISODES; i++, oam += 2)
    {
        if (main->xPosCounter >= 152 + 24 * i)
            SetPlateX(oam, RowX(i));
        else
        {
            SetPlateX(oam, main->xPosCounter + 0x170);
            done = FALSE;
        }
    }
    return done;
}

static void SetAffine(struct Main * main)
{
    gOamObjects[0].attr3 = fix_mul(_Cos(0), fix_inverse(0x100));
    gOamObjects[1].attr3 = fix_mul(_Sin(0), fix_inverse(0x100));
    gOamObjects[2].attr3 = fix_mul(-_Sin(0), fix_inverse(main->affineScale));
    gOamObjects[3].attr3 = fix_mul(_Cos(0), fix_inverse(main->affineScale));
}

void RftaEpisodeClearedProcess(struct Main * main)
{
    struct OamAttrs * oam;
    u32 j, episode = main->process[GAME_PROCESS_VAR2];
    switch (main->process[GAME_PROCESS_STATE])
    {
        case 0:
            EpisodeInit(main);
            break;
        case 1:
            if (main->blendMode != 0)
                break;
            LoadGfx(main);
            if (gMain.saveContinueFlags & 0xF0)
            {
                ReadSram(SRAM_START, (void *)&gSaveDataBuffer, sizeof(gSaveDataBuffer));
                VwfLoadLog();
                gSaveDataBuffer.main.caseEnabledFlags |= 1 << episode;
                SaveGameData();
            }
            else
            {
                DmaCopy16(3, gSaveVersion, gSaveDataBuffer.saveDataVer, sizeof(gSaveVersion));
                gSaveDataBuffer.magic = 0;
                gSaveDataBuffer.main.caseEnabledFlags |= 1 << episode;
                WriteSramEx((void *)&gSaveDataBuffer, SRAM_START, sizeof(gSaveDataBuffer));
            }
            break;
        case 2:
            if (SlideIn(main))
            {
                main->caseEnabledFlags |= 1 << episode;
                main->affineScale = 0x100;
                main->process[GAME_PROCESS_STATE] = 6;
            }
            break;
        case 6: // the new plate folds up ("? ? ?")...
            main->affineScale -= 0x10;
            oam = PLATES_OAM + episode * 2;
            SetPlate(oam, RowY(episode), ST_OAM_AFFINE_NORMAL);
            if (main->affineScale != 0)
            {
                SetAffine(main);
                break;
            }
            for (j = 0; j < 2; j++)
                oam[j].attr2 = SPRITE_ATTR2(TILE_LOCKED, 0, PAL_SELECTED) + j * 0x20;
            main->process[GAME_PROCESS_STATE]++;
            break;
        case 7: // ...and unfolds with the title
            oam = PLATES_OAM + episode * 2;
            main->affineScale += 0x10;
            if (main->affineScale >= 0x100)
            {
                main->advanceScriptContext = TRUE;
                main->showTextboxCharacters = TRUE;
                gScriptContext.currentSection = 0xFFFF;
                ChangeScriptSection(5);
                SetPlate(oam, RowY(episode), ST_OAM_AFFINE_OFF);
                main->process[GAME_PROCESS_STATE]++;
            }
            else
            {
                SetAffine(main);
                SetPlate(oam, RowY(episode), ST_OAM_AFFINE_NORMAL);
                for (j = 0; j < 2; j++)
                    oam[j].attr2 = PlateAttr2(main, episode, j, PAL_SELECTED);
            }
            break;
        case 8:
            if (gScriptContext.flags & 8)
            {
                if (gJoypad.pressedKeys & (A_BUTTON | B_BUTTON | SELECT_BUTTON | START_BUTTON))
                {
                    PauseBGM();
                    PlaySE(SE001_MENU_CONFIRM);
                    gSaveDataBuffer.main.scenarioIdx = main->scenarioIdx;
                    gSaveDataBuffer.main.caseEnabledFlags = main->caseEnabledFlags;
                    SET_PROCESS_PTR(SAVE_GAME_PROCESS, 0, 0, 1, main);
                }
            }
            break;
        default:
            break;
    }
}

static const u8 sFirstChapter[EPISODES] = { 0, 1, 5, 11, RFTA_FIRST_CHAPTER };

// the next unlocked episode up (-1) or down (+1), the same if there is none
static void MoveSelection(struct Main * main, s32 step)
{
    u32 i, from = main->selectedButton;
    for (i = 0; i < EPISODES; i++)
    {
        if (step < 0)
            main->selectedButton = main->selectedButton == 0 ? EPISODES - 1 : main->selectedButton - 1;
        else
            main->selectedButton = main->selectedButton + 1 >= EPISODES ? 0 : main->selectedButton + 1;
        if ((main->caseEnabledFlags >> main->selectedButton) & 1)
        {
            if (main->selectedButton != from)
                PlaySE(SE000_MENU_CHANGE);
            break;
        }
    }
}

static s32 PlateY(struct OamAttrs * oam)
{
    s32 y = oam->attr0 & 0xFF;
    return y >= 160 ? y - 256 : y;
}

void RftaSelectEpisodeProcess(struct Main * main)
{
    struct OamAttrs * oam;
    u32 i, j;
    s32 x, y;
    switch (main->process[GAME_PROCESS_STATE])
    {
        case 0:
            EpisodeInit(main);
            break;
        case 1:
            if (main->blendMode)
                return;
            if (main->saveContinueFlags & 0xF0)
                main->caseEnabledFlags = gSaveDataBuffer.main.caseEnabledFlags;
            LoadGfx(main);
            main->selectedButton = main->process[GAME_PROCESS_VAR2];
            oam = PLATES_OAM;
            for (i = 0; i < EPISODES; i++, oam += 2)
                for (j = 0; j < 2; j++)
                    oam[j].attr2 = PlateAttr2(main, i, j, main->selectedButton == i ? PAL_SELECTED : PAL_PLAIN);
            break;
        case 2:
            if (SlideIn(main))
            {
                main->advanceScriptContext = TRUE;
                main->showTextboxCharacters = TRUE;
                gScriptContext.currentSection = 0xFFFF;
                ChangeScriptSection(2);
                SetTimedKeysAndDelay(DPAD_UP | DPAD_DOWN, 20);
                main->process[GAME_PROCESS_STATE] = 6;
            }
            break;
        case 6: // choosing
            if (gScriptContext.flags & SCRIPT_LOOP)
            {
                if (gJoypad.activeTimedKeys & DPAD_UP)
                    MoveSelection(main, -1);
                else if (gJoypad.activeTimedKeys & DPAD_DOWN)
                    MoveSelection(main, 1);
                else if (gJoypad.pressedKeys & A_BUTTON)
                {
                    PlaySE(SE001_MENU_CONFIRM);
                    main->xPosCounter = 0;
                    main->advanceScriptContext = FALSE;
                    main->showTextboxCharacters = FALSE;
                    gIORegisters.lcd_dispcnt &= ~DISPCNT_BG1_ON;
                    main->tilemapUpdateBits &= ~2;
                    main->process[GAME_PROCESS_STATE]++;
                    main->process[GAME_PROCESS_VAR2] = 0;
                    main->process[GAME_PROCESS_VAR1] = 0;
                }
                else if (gJoypad.pressedKeys & B_BUTTON)
                {
                    PlaySE(SE002_MENU_CANCEL);
                    StartHardwareBlend(2, 0, 1, 0x1F);
                    main->process[GAME_PROCESS_STATE] = 12;
                }
            }
            oam = PLATES_OAM;
            for (i = 0; i < EPISODES; i++, oam += 2)
                for (j = 0; j < 2; j++)
                    oam[j].attr2 = PlateAttr2(main, i, j, i == main->selectedButton ? PAL_SELECTED : PAL_PLAIN);
            break;
        case 7: // the chosen plate to the middle, the others off to the right
            main->process[GAME_PROCESS_VAR1]++;
            if (main->process[GAME_PROCESS_VAR1] > 0x28)
            {
                main->xPosCounter = 0;
                main->process[GAME_PROCESS_STATE]++;
                main->process[GAME_PROCESS_VAR2] = 0;
                main->process[GAME_PROCESS_VAR1] = 0;
            }
            oam = PLATES_OAM;
            for (i = 0; i < EPISODES; i++, oam += 2)
            {
                x = oam->attr1 & 0x1FF;
                if (i == main->selectedButton)
                {
                    if (x < SELECTED_X)
                        x = x + 4 > SELECTED_X ? SELECTED_X : x + 4;
                    else if (x > SELECTED_X)
                        x = x - 4 < SELECTED_X ? SELECTED_X : x - 4;
                    SetPlateX(oam, x);
                }
                else if (oam->attr0 != SPRITE_ATTR0_CLEAR)
                {
                    x = (x + main->xPosCounter) & 0x1FF;
                    if (x > 0xF0)
                        oam[0].attr0 = oam[1].attr0 = SPRITE_ATTR0_CLEAR;
                    else
                        SetPlateX(oam, x);
                }
            }
            if (main->xPosCounter < 8)
                main->xPosCounter++;
            break;
        case 8: // up or down to the middle
            oam = PLATES_OAM;
            for (i = 0; i < EPISODES; i++, oam += 2)
                if (i != main->selectedButton)
                    oam[0].attr0 = oam[1].attr0 = SPRITE_ATTR0_CLEAR;
            oam = PLATES_OAM + main->selectedButton * 2;
            y = PlateY(oam);
            if (y < SELECTED_Y)
                y = y + 4 > SELECTED_Y ? SELECTED_Y : y + 4;
            else if (y > SELECTED_Y)
                y = y - 4 < SELECTED_Y ? SELECTED_Y : y - 4;
            SetPlate(oam, y, ST_OAM_AFFINE_OFF);
            if (y == SELECTED_Y)
            {
                main->process[GAME_PROCESS_STATE] = 9;
                main->process[GAME_PROCESS_VAR2] = 0;
                main->process[GAME_PROCESS_VAR1] = 0;
            }
            break;
        case 9:
            main->process[GAME_PROCESS_VAR1]++;
            if (main->process[GAME_PROCESS_VAR1] > 20)
            {
                main->process[GAME_PROCESS_STATE] = 10;
                main->process[GAME_PROCESS_VAR2] = 0;
                main->process[GAME_PROCESS_VAR1] = 0;
            }
            break;
        case 10: // the chosen plate flashes
            main->process[GAME_PROCESS_VAR1]++;
            if (main->process[GAME_PROCESS_VAR1] > 50)
            {
                StartHardwareBlend(2, 4, 1, 0x1F);
                main->process[GAME_PROCESS_STATE]++;
                main->process[GAME_PROCESS_VAR2] = 0;
            }
            else
            {
                if (main->process[GAME_PROCESS_VAR2] > 5)
                    main->process[GAME_PROCESS_VAR2] = 0;
                main->process[GAME_PROCESS_VAR2]++;
            }
            oam = PLATES_OAM + main->selectedButton * 2;
            for (j = 0; j < 2; j++)
                oam[j].attr2 = PlateAttr2(main, main->selectedButton, j, main->process[GAME_PROCESS_VAR2] > 2 ? PAL_PLAIN : PAL_SELECTED);
            break;
        case 11:
            if (main->blendMode)
                return;
            main->scenarioIdx = main->selectedButton < EPISODES ? sFirstChapter[main->selectedButton] : 0;
            SET_PROCESS_PTR(gCaseStartProcess[main->scenarioIdx], 0, 0, 0, main);
            break;
        case 12:
            if (main->blendMode)
                return;
            SET_PROCESS_PTR(TITLE_SCREEN_PROCESS, 0, 0, 0, main);
            break;
    }
}
#endif // RFTA

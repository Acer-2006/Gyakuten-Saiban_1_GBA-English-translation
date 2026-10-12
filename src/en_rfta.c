#include "global.h"
#include "en_rfta.h"
#if RFTA
// Rise from the Ashes (make RFTA=1): what the fifth episode's scripts and
// investigation code need from the engine beyond the first four episodes.
#include "main.h"
#include "script.h"
#include "ewram.h"
#include "background.h"
#include "investigation.h"
#include "case_data.h"
#include "sound.h"
#include "utils.h"
#include "graphics.h"

#define RFTA_DATA __attribute__((section("rfta_data")))

RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_00_script[] = INCBIN_U8("script_rfta/scenario_5_00_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_01_script[] = INCBIN_U8("script_rfta/scenario_5_01_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_02_script[] = INCBIN_U8("script_rfta/scenario_5_02_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_03_script[] = INCBIN_U8("script_rfta/scenario_5_03_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_04_script[] = INCBIN_U8("script_rfta/scenario_5_04_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_05_script[] = INCBIN_U8("script_rfta/scenario_5_05_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_06_script[] = INCBIN_U8("script_rfta/scenario_5_06_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_07_script[] = INCBIN_U8("script_rfta/scenario_5_07_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_08_script[] = INCBIN_U8("script_rfta/scenario_5_08_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_09_script[] = INCBIN_U8("script_rfta/scenario_5_09_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_10_script[] = INCBIN_U8("script_rfta/scenario_5_10_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_11_script[] = INCBIN_U8("script_rfta/scenario_5_11_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_12_script[] = INCBIN_U8("script_rfta/scenario_5_12_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_13_script[] = INCBIN_U8("script_rfta/scenario_5_13_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_14_script[] = INCBIN_U8("script_rfta/scenario_5_14_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_15_script[] = INCBIN_U8("script_rfta/scenario_5_15_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_16_script[] = INCBIN_U8("script_rfta/scenario_5_16_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_17_script[] = INCBIN_U8("script_rfta/scenario_5_17_script.phscr");
RFTA_DATA __attribute__((aligned(4))) const u8 scenario_5_18_script[] = INCBIN_U8("script_rfta/scenario_5_18_script.phscr");

const u8 * const gRftaScriptTable[RFTA_SCRIPTS] = {
    scenario_5_00_script, scenario_5_01_script, scenario_5_02_script, scenario_5_03_script, scenario_5_04_script,
    scenario_5_05_script, scenario_5_06_script, scenario_5_07_script, scenario_5_08_script, scenario_5_09_script,
    scenario_5_10_script, scenario_5_11_script, scenario_5_12_script, scenario_5_13_script, scenario_5_14_script,
    scenario_5_15_script, scenario_5_16_script, scenario_5_17_script, scenario_5_18_script,
};

const u32 gRftaScriptSizes[RFTA_SCRIPTS] = {
    sizeof(scenario_5_00_script), sizeof(scenario_5_01_script), sizeof(scenario_5_02_script), sizeof(scenario_5_03_script),
    sizeof(scenario_5_04_script), sizeof(scenario_5_05_script), sizeof(scenario_5_06_script), sizeof(scenario_5_07_script),
    sizeof(scenario_5_08_script), sizeof(scenario_5_09_script), sizeof(scenario_5_10_script), sizeof(scenario_5_11_script),
    sizeof(scenario_5_12_script), sizeof(scenario_5_13_script), sizeof(scenario_5_14_script), sizeof(scenario_5_15_script),
    sizeof(scenario_5_16_script), sizeof(scenario_5_17_script), sizeof(scenario_5_18_script),
};

extern const u32 gScriptSizes[];

u32 EnScriptSize(u32 chapter)
{
    if (chapter < RFTA_FIRST_CHAPTER)
        return gScriptSizes[chapter];
    if (chapter < RFTA_FIRST_CHAPTER + RFTA_SCRIPTS)
        return gRftaScriptSizes[chapter - RFTA_FIRST_CHAPTER];
    return 0;
}

// The DS's rooms 0x16-0x1D (the fifth episode's: the prosecutor's office,
// Criminal Affairs, the parking lot...) are rows 0x10-0x17 of the GBA's
// gMain.roomData, which the fifth episode doesn't otherwise use; everything
// that names a room (room data, talk and present tables, the room setup
// code, script commands 33 / 34) is renumbered by the tools the same way.
#define DS_FIRST_NEW_ROOM 0x16
#define GBA_FIRST_NEW_ROOM 0x10
#define NEW_ROOMS 8

u32 EnDsRoom(u32 gbaRoom)
{
    if (gbaRoom >= GBA_FIRST_NEW_ROOM && gbaRoom < GBA_FIRST_NEW_ROOM + NEW_ROOMS)
        return gbaRoom - GBA_FIRST_NEW_ROOM + DS_FIRST_NEW_ROOM;
    return gbaRoom;
}

u32 EnGbaRoom(u32 dsRoom)
{
    if (dsRoom >= DS_FIRST_NEW_ROOM && dsRoom < DS_FIRST_NEW_ROOM + NEW_ROOMS)
        return dsRoom - DS_FIRST_NEW_ROOM + GBA_FIRST_NEW_ROOM;
    return dsRoom;
}

// The Move menu's plate for a room: in the fifth episode rooms 0x10-0x17 are
// the DS's 0x16-0x1D, whose plates follow the DS's English ones; the first
// four episodes' rooms 0x10-0x14 (Gourd Lake...) keep theirs.
const u8 * EnLocationPlate(u32 room)
{
    if (gMain.scenarioIdx >= RFTA_FIRST_CHAPTER && room >= GBA_FIRST_NEW_ROOM && room < GBA_FIRST_NEW_ROOM + NEW_ROOMS)
        return gRftaLocationChoices + (room - GBA_FIRST_NEW_ROOM) * 0x800;
    return gGfxLocationChoices + room * 0x800;
}

// The Talk menu's plate for a topic icon: the first four episodes have
// 0-124, the fifth 125-187
const u8 * EnTalkPlate(u32 icon)
{
    if (icon >= RFTA_FIRST_TOPIC)
        return gRftaTalkChoices + (icon - RFTA_FIRST_TOPIC) * 0x800;
    return gGfxTalkChoices + icon * 0x800;
}

// The DS's chapter load (ARM9 0x020237c4, the second argument 1): the
// chapter's script in place of the current one, at its first section. Day 1's
// investigation is two script files; entering a room loads the one that room's
// conversations are in (the room hooks, en_rfta_rooms.c).
void EnLoadChapter(u32 chapter)
{
    gMain.scenarioIdx = chapter;
    gScriptBase = gRftaScriptTable[chapter - RFTA_FIRST_CHAPTER];
    ChangeScriptSection(0x80);
}

// The DS's 0x0202884c: InvestigationSetScriptSectionAndFlag without pausing the music
void EnSetScriptSectionAndFlagKeepBgm(u32 section, u32 flag)
{
    ChangeFlag(0, flag, TRUE);
    ChangeScriptSection(section);
    SlideTextbox(1);
}

static u32 GbaBg(u32 bg)
{
    return (bg & 0x7FFF) == 0xFFF ? 0xFF : bg;
}

void EnDecompressBackground(u32 bg)
{
    DecompressBackgroundIntoBuffer(GbaBg(bg));
}

void EnShowBackground(u32 bg)
{
    CopyBGDataToVram(GbaBg(bg));
}

// The DS starts a scroll across the picture here (0x0201cf0c); for now the
// picture is shown as it is
void EnScrollBackgroundEnd(u32 bg)
{
    CopyBGDataToVram(GbaBg(bg));
}

extern const struct ExaminationData * const gRftaExamTables[];
extern const u8 gRftaExamCounts[];

// The DS's examine table copy (its examine data holds 32 entries): the first
// 16 into gExaminationData as the GBA keeps them (and saves them), the table's
// number into gMain.unk8B (unused by the game) for the examining itself
void EnLoadExamData(u32 table)
{
    u32 n = gRftaExamCounts[table];
    DmaCopy16(3, gRftaExamTables[table], gExaminationData, (n < 16 ? n : 16) * sizeof(struct ExaminationData));
    gMain.unk8B = table + 1;
}

// The examine areas in force: the fifth episode's table, or gExaminationData
const struct ExaminationData * EnExamData(u32 * count)
{
    if (gMain.scenarioIdx >= RFTA_FIRST_CHAPTER && gMain.unk8B != 0)
    {
        *count = gRftaExamCounts[gMain.unk8B - 1];
        return gRftaExamTables[gMain.unk8B - 1];
    }
    *count = 16;
    return gExaminationData;
}

// The text box out of the way of a spot the pointer is over, or back
void EnSpotSelectTextbox(bool32 hide)
{
    if (hide)
    {
        gMain.showTextboxCharacters = FALSE;
        gIORegisters.lcd_dispcnt &= ~DISPCNT_BG1_ON;
    }
    else
    {
        gMain.showTextboxCharacters = TRUE;
        gIORegisters.lcd_dispcnt |= DISPCNT_BG1_ON;
    }
}

// Script command 60 (the DS's 6A): go on in chapter file n, at its first
// section, as the DS does where a trial day is split in two files (no save
// prompt in between). The DS clears the talk flags (its gMain+0x94, the
// GBA's talkEndFlags) and keeps the scenario flags.
bool32 Command60(struct ScriptContext * scriptCtx)
{
    u32 chapter;
    scriptCtx->scriptPtr++;
    chapter = *scriptCtx->scriptPtr;
    scriptCtx->scriptPtr++;
    DmaFill32(3, 0, gMain.talkEndFlags, sizeof(gMain.talkEndFlags));
    EnLoadChapter(chapter);
    return 0;
}

// After the right evidence in a cross-examination the game leaves it for
// the scene the answer starts; for these answers the DS stays in the
// cross-examination instead (its 0x02031754: the scene ends by going back to
// a statement, adding one). Chapter, section.
static const u8 sReturnToQuestioning[][2] = {
    { 19, 0x97 }, { 19, 0xAA }, { 20, 0xBC }, { 20, 0xBD }, { 21, 0xA9 }, { 25, 0x9B }, { 32, 0x90 },
};

bool32 EnPresentReturnsToQuestioning(u32 section)
{
    u32 i;
    for (i = 0; i < ARRAY_COUNT(sReturnToQuestioning); i++)
        if (sReturnToQuestioning[i][0] == gMain.scenarioIdx && sReturnToQuestioning[i][1] == section)
            return TRUE;
    return FALSE;
}

// Script command 61: go on in section n. Where the DS hands over to one of
// its own systems (the evidence turned over in 3D, the luminol, the prints,
// the footage) and that system starts the next section, the translator
// (translate.py, BYPASS) goes on in that section straight away until the
// system exists here.
bool32 Command61(struct ScriptContext * scriptCtx)
{
    u32 section;
    scriptCtx->scriptPtr++;
    section = *scriptCtx->scriptPtr;
    ChangeScriptSection(section);
    return 0;
}
#endif // RFTA

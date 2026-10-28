#ifndef GUARD_EN_RFTA_H
#define GUARD_EN_RFTA_H

// Rise from the Ashes, the DS's fifth episode (built with `make RFTA=1`).
// Chapters 17-34 are its 18 chapter files, in the DS's order; 35 is the
// file of lines spoken while examining evidence (docs/rise_from_the_ashes.md).

#ifndef RFTA
#define RFTA 0
#endif

#define RFTA_FIRST_CHAPTER 17
#define RFTA_LAST_CHAPTER 34
#define RFTA_CHAPTERS (RFTA_LAST_CHAPTER - RFTA_FIRST_CHAPTER + 1)
#define RFTA_SCRIPTS (RFTA_CHAPTERS + 1)     // and the evidence-examination file
#define RFTA_EPISODE 4                      // episode index (bit 4 of caseEnabledFlags)
#define RFTA_TITLE_SECTION 31               // the common script's first fifth-episode chapter title

#if RFTA
#include "main.h"
#include "script.h"

struct InvestigationPresentData;
struct CourtPresentData;

// the chapter of the first four episodes' numbering (0-16) or the fifth's (17-34)
#define LAST_CHAPTER RFTA_LAST_CHAPTER
// the common script section with the chapter's title (load screen)
#define CHAPTER_TITLE_SECTION(idx) ((idx) < RFTA_FIRST_CHAPTER ? (idx) + 7 : (idx) - RFTA_FIRST_CHAPTER + RFTA_TITLE_SECTION)

extern const u8 * const gRftaScriptTable[RFTA_SCRIPTS];
extern const u32 gRftaScriptSizes[RFTA_SCRIPTS];
u32 EnScriptSize(u32 chapter);

// rooms: the DS numbers the fifth episode's new rooms 0x16-0x1D, the GBA's
// gMain.roomData has 24 rows, so they are 0x10-0x17 here
u32 EnDsRoom(u32 gbaRoom);
u32 EnGbaRoom(u32 dsRoom);

void EnLoadChapter(u32 chapter);
void EnSetScriptSectionAndFlagKeepBgm(u32 section, u32 flag);
void EnDecompressBackground(u32 bg);
void EnShowBackground(u32 bg);
void EnScrollBackgroundEnd(u32 bg);
bool32 Command60(struct ScriptContext * scriptCtx);
bool32 Command61(struct ScriptContext * scriptCtx);
bool32 Command62(struct ScriptContext * scriptCtx);
bool32 Command63(struct ScriptContext * scriptCtx);
// the partner portraits' evidence entries (tools/en/rfta/evidence.py)
#define RFTA_FIRST_PORTRAIT 0xD1
bool32 EnPresentReturnsToQuestioning(u32 section);

// the flags a chapter starts with (the DS keeps flags 0-0x27 through the
// episode), the chapter after one that ends (the third investigation's end
// is in its first file: on to the final day)
#define RFTA_DAY3_END 28
#define RFTA_FINAL_DAY 31
void EnRftaChapterFlags(struct Main * main, bool32 court);
u32 EnNextChapter(u32 chapter);

// Angel Starr's box lunch ends with her pose (animation.c)
void EnRftaDropLunch(void);

void EnRftaDay1RoomHook(struct Main * main);
void EnRftaDay2RoomHook(struct Main * main);
void EnRftaDay3RoomHook(struct Main * main);

// the Move and Talk menus' plates: the fifth episode's rooms 0x10-0x17 and
// topics 125-187 are its own (tools/en/rfta/plates.py)
#define RFTA_FIRST_TOPIC 125
extern u8 gRftaLocationChoices[];
extern u8 gRftaTalkChoices[];
extern u8 gRftaEpisodeTitle[];
const u8 * EnLocationPlate(u32 room);
const u8 * EnTalkPlate(u32 icon);

// the examine areas: the fifth episode's tables are up to 32 entries, the
// GBA's gExaminationData holds 16. The table in use is kept by its number
// (gMain.unk8B, saved with gMain) and read from ROM
struct ExaminationData;
void EnLoadExamData(u32 table);
const struct ExaminationData * EnExamData(u32 * count);

// the "point at it" pictures: the GBA's lowest pointer row (above the text
// box); the box makes way for a fifth-episode picture with a spot lower down
#define SPOTSELECT_BOTTOM 102
void EnSpotSelectTextbox(bool32 hide);

// the episode select with the fifth episode (en_rfta_episodes.c)
#define EPISODES 5
void RftaEpisodeClearedProcess(struct Main * main);
void RftaSelectEpisodeProcess(struct Main * main);

#else
#define LAST_CHAPTER 16
#define CHAPTER_TITLE_SECTION(idx) ((idx) + 7)
#endif

#endif // GUARD_EN_RFTA_H

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

void EnRftaDay1RoomHook(struct Main * main);
void EnRftaDay2RoomHook(struct Main * main);
void EnRftaDay3RoomHook(struct Main * main);

#else
#define LAST_CHAPTER 16
#define CHAPTER_TITLE_SECTION(idx) ((idx) + 7)
#endif

#endif // GUARD_EN_RFTA_H

#ifndef GUARD_EWRAM_H
#define GUARD_EWRAM_H

#define eUnknown_0200AFC0 ((void *)EWRAM_START+0xAFC0)
// English patch: scripts are no longer decompressed into EWRAM. They run
// straight from ROM; the first word of the old 108KB heap holds the pointer
// to the current script and the rest is used by the VWF renderer (vwf.c).
#define gScriptBase (*(const u8 **)(EWRAM_START + 0x11FC0))
#define eScriptHeap ((void*) gScriptBase)
#define eBGDecompBuffer ((void*) (EWRAM_START + 0x2CFC0))
#define eUnknown_02031FC0 ((void*) (EWRAM_START + 0x31FC0))

#endif//GUARD_EWRAM_H
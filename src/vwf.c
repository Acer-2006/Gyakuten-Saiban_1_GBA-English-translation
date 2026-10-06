#include "global.h"
#include "main.h"
#include "script.h"
#include "ewram.h"
#include "vwf.h"
#include "agb_sram.h"
#include "en_menu.h"
#include "en_menu_gfx.h"
#include <stddef.h>

// English VWF text renderer.
// The scripts now run straight from ROM, so the old 108KB script heap in
// EWRAM is free. The first word holds the script base pointer (see ewram.h);
// the VWF line buffers live right after it.

struct VwfState
{
    u8 pen[4];
    u8 tiles[VWF_LINES][VWF_BLOCKS_PER_LINE * 8 * 32];
    // what is on each line (code | color << 11), so the text box can be
    // redrawn after the save screen or after loading a save
    u32 logMagic;
    u16 choiceIds[4];            // answer labels on screen (choiceIds[3] == 1)
    u8 logLen[4];
    u16 log[VWF_LINES][VWF_LOG_LEN];
};
#define VWF_LOG_MAGIC 0x31465756 // "VWF1"
#define VWF_SRAM_OFFSET 0x2A00   // after the original 0x29D0-byte save

#define gVwf ((struct VwfState *)(EWRAM_START + 0x11FC0 + 0x10))
// copy kept while the save screen borrows the text box
#define gVwfBackup ((struct VwfState *)(EWRAM_START + 0x11FC0 + 0x2000))

extern const u8 gVwfFontGlyphs[];
extern const u8 gVwfFontWidths[];

static void VwfCopyBlocks(u32 line, u32 firstBlock, u32 lastBlock)
{
    u8 * src = gVwf->tiles[line] + firstBlock * 256;
    u8 * dst = (u8 *)OBJ_VRAM0 + line * VWF_LINE_VRAM_STRIDE + firstBlock * 256;
    DmaCopy16(3, src, dst, (lastBlock - firstBlock + 1) * 256);
}

static void VwfShowBlocks(u32 line, u32 lastBlock)
{
    u32 b;
    for (b = 0; b <= lastBlock && b < VWF_BLOCKS_PER_LINE; b++)
    {
        struct TextBoxCharacter * c = &gTextBoxCharacters[line * VWF_BLOCKS_PER_LINE + b];
        c->x = b * 32;
        if (gEnMenu->textMode)
        {
            // menu plate: DS line pitch 16; one line on its own sits half-way
            c->y = line * 16 - (gEnMenu->halfLine && line == 1 ? 8 : 0);
            c->objAttr2 = (line * (VWF_LINE_VRAM_STRIDE / 32) + b * 8) | (EN_MENU_TEXT_PAL << 12);
        }
        else
        {
            c->y = line * VWF_LINE_HEIGHT;
            c->objAttr2 = (line * (VWF_LINE_VRAM_STRIDE / 32) + b * 8) + 0x400;
        }
        c->state = 0x8000 | line;
        c->color = 0;
    }
}

void VwfClearLine(u32 line)
{
    u32 b;
    if (line >= VWF_LINES)
        return;
    gVwf->pen[line] = 0;
    gVwf->logLen[line] = 0;
    gVwf->logMagic = VWF_LOG_MAGIC;
    DmaFill16(3, 0, gVwf->tiles[line], sizeof(gVwf->tiles[line]));
    VwfCopyBlocks(line, 0, VWF_BLOCKS_PER_LINE - 1);
    for (b = 0; b < VWF_BLOCKS_PER_LINE; b++)
        gTextBoxCharacters[line * VWF_BLOCKS_PER_LINE + b].state &= ~0x8000;
    if (gEnMenu->textMode)
    {
        // menu plate: each line is centred, as the DS does
        gVwf->pen[line] = EnMenuLineStart();
        if (line == 0)
            gEnMenu->halfLine = FALSE;
        else if (line == 1)
        {
            gEnMenu->halfLine = TRUE;
            for (b = 0; b < VWF_BLOCKS_PER_LINE; b++)
                if (gTextBoxCharacters[b].state & 0x8000)
                    gEnMenu->halfLine = FALSE;
        }
    }
}

// a character in the DS menu font (plate text)
static void VwfDrawMenuChar(u32 code, u32 line)
{
    const u8 * glyph;
    u8 * buf = gVwf->tiles[line];
    u32 pen = gVwf->pen[line], x, y, first, last;
    s32 off;
    if (code >= EN_PLATE_FONT_CODES || !gEnPlateFontAdv[code])
    {
        gVwf->pen[line] = pen + 8; // space, or nothing to draw
        return;
    }
    if (pen + 16 > VWF_LINE_PIXELS)
        return;
    glyph = gEnPlateFont + code * EN_PLATE_FONT_ROWS * 8;
    off = (s8)gEnPlateFontOff[code];
    for (y = 0; y < EN_PLATE_FONT_ROWS; y++)
    {
        for (x = 0; x < 16; x++)
        {
            u32 v = glyph[y * 8 + (x >> 1)];
            v = (x & 1) ? (v >> 4) : (v & 0xF);
            if (v && (s32)(pen + x) + off >= 0)
            {
                u32 px = pen + x + off;
                u32 tile = (px >> 5) * 8 + (y >> 3) * 4 + ((px >> 3) & 3);
                u8 * p = buf + tile * 32 + (y & 7) * 4 + ((px & 7) >> 1);
                if (px & 1)
                    *p = (*p & 0x0F) | (v << 4);
                else
                    *p = (*p & 0xF0) | v;
            }
        }
    }
    gVwf->pen[line] = pen + gEnPlateFontAdv[code];
    first = pen >> 5;
    last = (pen + 15) >> 5;
    if (last >= VWF_BLOCKS_PER_LINE)
        last = VWF_BLOCKS_PER_LINE - 1;
    VwfCopyBlocks(line, first, last);
    VwfShowBlocks(line, last);
}

static void VwfDrawChar(u32 code, u32 line, u32 color, bool32 copy);

void VwfPutChar(u32 code, u32 line, u32 color)
{
    if (line >= VWF_LINES)
        line = VWF_LINES - 1;
    if (code >= VWF_GLYPH_COUNT)
        code = 0xFF;
    if (gVwf->logLen[line] < VWF_LOG_LEN)
        gVwf->log[line][gVwf->logLen[line]++] = code | (color << 11);
    if (gEnMenu->textMode)
        VwfDrawMenuChar(code, line);
    else
        VwfDrawChar(code, line, color, TRUE);
}

static void VwfDrawChar(u32 code, u32 line, u32 color, bool32 copy)
{
    const u8 * glyph;
    u8 * buf;
    u32 width, pen, x, y;

    pen = gVwf->pen[line];
    if (code == 0xFF) // space
    {
        gVwf->pen[line] = pen + VWF_SPACE_WIDTH;
        return;
    }
    width = gVwfFontWidths[code];
    if (pen + width > VWF_LINE_PIXELS)
        return; // line full: drop the character rather than corrupt memory
    glyph = gVwfFontGlyphs + code * VWF_GLYPH_BYTES;
    buf = gVwf->tiles[line];
    for (y = 0; y < VWF_GLYPH_ROWS; y++)
    {
        for (x = 0; x < width; x++)
        {
            u32 v = glyph[y * 8 + (x >> 1)];
            v = (x & 1) ? (v >> 4) : (v & 0xF);
            if (v)
            {
                u32 px = pen + x;
                u32 tile = (px >> 5) * 8 + (y >> 3) * 4 + ((px >> 3) & 3);
                u8 * p = buf + tile * 32 + (y & 7) * 4 + ((px & 7) >> 1);
                if (color)
                    v += color * 3;
                if (px & 1)
                    *p = (*p & 0x0F) | (v << 4);
                else
                    *p = (*p & 0xF0) | v;
            }
        }
    }
    gVwf->pen[line] = pen + width + 1;
    if (copy)
    {
        u32 first = pen >> 5;
        u32 last = (pen + width) >> 5;
        if (last >= VWF_BLOCKS_PER_LINE)
            last = VWF_BLOCKS_PER_LINE - 1;
        VwfCopyBlocks(line, first, last);
        VwfShowBlocks(line, last);
    }
}

// Rebuild the text box from the per-line log (after the save screen, or
// after loading a save) and push it to VRAM.
void VwfRedraw(void)
{
    u32 line, i, n;
    if (gVwf->logMagic != VWF_LOG_MAGIC)
    {
        for (line = 0; line < VWF_LINES; line++)
            gVwf->logLen[line] = 0;
        gVwf->choiceIds[3] = 0;
        gVwf->logMagic = VWF_LOG_MAGIC;
    }
    for (line = 0; line < VWF_LINES; line++)
    {
        n = gVwf->logLen[line];
        if (n > VWF_LOG_LEN)
            n = gVwf->logLen[line] = 0;
        gVwf->pen[line] = 0;
        DmaFill16(3, 0, gVwf->tiles[line], sizeof(gVwf->tiles[line]));
        for (i = 0; i < n; i++)
        {
            u32 code = gVwf->log[line][i] & 0x7FF;
            if (code >= VWF_GLYPH_COUNT)
                code = 0xFF;
            VwfDrawChar(code, line, gVwf->log[line][i] >> 11, FALSE);
        }
        VwfCopyBlocks(line, 0, VWF_BLOCKS_PER_LINE - 1);
    }
    VwfReloadChoiceLabels();
}

void VwfReloadChoiceLabels(void)
{
    if (gVwf->logMagic == VWF_LOG_MAGIC && gVwf->choiceIds[3] == 1)
        ReloadChoiceLabelGfx(gVwf->choiceIds);
}

void VwfSetChoiceLabels(const u16 *ids)
{
    u32 k;
    for (k = 0; k < 3; k++)
        gVwf->choiceIds[k] = ids ? ids[k] : 0xFFFF;
    gVwf->choiceIds[3] = ids ? 1 : 0;
}

void VwfBackup(void)
{
    DmaCopy16(3, gVwf, gVwfBackup, sizeof(struct VwfState));
}

void VwfRestore(void)
{
    DmaCopy16(3, gVwfBackup, gVwf, sizeof(struct VwfState));
}

// The save screen runs while the backup holds the game's text box; that is
// what gets stored next to the save data.
void VwfSaveLog(void)
{
    WriteSramEx((const u8 *)&gVwfBackup->logMagic, (u8 *)SRAM_START + VWF_SRAM_OFFSET,
                sizeof(struct VwfState) - offsetof(struct VwfState, logMagic));
}

void VwfLoadLog(void)
{
    ReadSram((const u8 *)SRAM_START + VWF_SRAM_OFFSET, (u8 *)&gVwfBackup->logMagic,
             sizeof(struct VwfState) - offsetof(struct VwfState, logMagic));
}

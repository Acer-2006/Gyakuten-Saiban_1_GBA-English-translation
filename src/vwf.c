#include "global.h"
#include "main.h"
#include "script.h"
#include "ewram.h"
#include "vwf.h"

// English VWF text renderer.
// The scripts now run straight from ROM, so the old 108KB script heap in
// EWRAM is free. The first word holds the script base pointer (see ewram.h);
// the VWF line buffers live right after it.

struct VwfState
{
    u8 pen[4];
    u8 tiles[VWF_LINES][VWF_BLOCKS_PER_LINE * 8 * 32];
};

#define gVwf ((struct VwfState *)(EWRAM_START + 0x11FC0 + 0x10))

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
        c->y = line * VWF_LINE_HEIGHT;
        c->objAttr2 = (line * (VWF_LINE_VRAM_STRIDE / 32) + b * 8) + 0x400;
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
    DmaFill16(3, 0, gVwf->tiles[line], sizeof(gVwf->tiles[line]));
    VwfCopyBlocks(line, 0, VWF_BLOCKS_PER_LINE - 1);
    for (b = 0; b < VWF_BLOCKS_PER_LINE; b++)
        gTextBoxCharacters[line * VWF_BLOCKS_PER_LINE + b].state &= ~0x8000;
}

void VwfPutChar(u32 code, u32 line, u32 color)
{
    const u8 * glyph;
    u8 * buf;
    u32 width, pen, x, y;

    if (line >= VWF_LINES)
        line = VWF_LINES - 1;
    if (code >= VWF_GLYPH_COUNT)
        code = 0xFF;
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
    {
        u32 first = pen >> 5;
        u32 last = (pen + width) >> 5;
        if (last >= VWF_BLOCKS_PER_LINE)
            last = VWF_BLOCKS_PER_LINE - 1;
        VwfCopyBlocks(line, first, last);
        VwfShowBlocks(line, last);
    }
}

// Called after loading a save: the line buffers survive in EWRAM only if the
// game was not power-cycled, so just push whatever is there back to VRAM.
void VwfRedraw(void)
{
    u32 line;
    for (line = 0; line < VWF_LINES; line++)
        VwfCopyBlocks(line, 0, VWF_BLOCKS_PER_LINE - 1);
}

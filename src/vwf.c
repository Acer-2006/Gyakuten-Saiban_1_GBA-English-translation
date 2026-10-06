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
    u8 lineStart[4];             // pen position each line starts at
    u8 centre;                   // lines are centred (script command 5D, as the DS)
    u8 pad[3];
};
#define VWF_LOG_MAGIC 0x32465756 // "VWF2"
#define VWF_LOG_MAGIC_V1 0x31465756 // "VWF1": no line starts / centring
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

// arguments of each script command, to step over the ones inside a line
static const u8 sCmdArgs[0x60] = {
    0, 0, 0, 1, 1, 2, 1, 0, 2, 3, 1, 1, 1, 0, 1, 2, 1, 0, 3, 1, 0, 0, 0, 1, 1, 2, 4, 1, 1, 1, 3, 0,
    1, 0, 2, 2, 0, 1, 1, 2, 1, 1, 3, 0, 1, 0, 0, 2, 1, 2, 2, 5, 1, 2, 1, 2, 1, 1, 2, 2, 1, 1, 1, 0,
    0, 0, 1, 1, 1, 0, 1, 2, 2, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 0,
};

// The DS centres location cards, testimony titles and a few lines with
// command 5D. Measure the line that starts at the script pointer (up to the
// next line break or end of message) and start it so it sits in the middle
// of the screen.
static u32 VwfCentredLineStart(void)
{
    const u16 * p = gScriptContext.scriptPtr;
    s32 w = 0, x;
    for (;;)
    {
        u32 t = *p;
        if (t >= 0x80)
        {
            t -= 0x80;
            if (t == 0xFF)
                w += VWF_SPACE_WIDTH;
            else if (t < VWF_GLYPH_COUNT)
                w += gVwfFontWidths[t] + 1;
            p++;
            continue;
        }
        // line breaks, ends of messages and jumps end the line
        if (t <= 0x02 || t == 0x07 || t == 0x08 || t == 0x09 || t == 0x0A || t == 0x0D
         || t == 0x15 || t == 0x2D || t == 0x2E || t == 0x35 || t == 0x36 || t >= 0x5D)
            break;
        p += 1 + sCmdArgs[t];
    }
    if (w > 0)
        w--;    // no gap after the last letter
    x = (DISPLAY_WIDTH / 2 - gScriptContext.textXOffset) - w / 2;
    return x < 0 ? 0 : x;
}

void VwfSetCentre(u32 on)
{
    gVwf->centre = on ? 1 : 0;
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
    if (!gEnMenu->textMode && gVwf->centre)
        gVwf->pen[line] = VwfCentredLineStart();
    gVwf->lineStart[line] = gVwf->pen[line];
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
        {
            gVwf->logLen[line] = 0;
            gVwf->lineStart[line] = 0;
        }
        gVwf->centre = 0;
        gVwf->choiceIds[3] = 0;
        gVwf->logMagic = VWF_LOG_MAGIC;
    }
    for (line = 0; line < VWF_LINES; line++)
    {
        n = gVwf->logLen[line];
        if (n > VWF_LOG_LEN)
            n = gVwf->logLen[line] = 0;
        gVwf->pen[line] = gVwf->lineStart[line];
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
    u32 line;
    ReadSram((const u8 *)SRAM_START + VWF_SRAM_OFFSET, (u8 *)&gVwfBackup->logMagic,
             sizeof(struct VwfState) - offsetof(struct VwfState, logMagic));
    if (gVwfBackup->logMagic == VWF_LOG_MAGIC_V1)
    {
        // saved by v0.2 - v0.4: the same log, without the line starts
        for (line = 0; line < 4; line++)
            gVwfBackup->lineStart[line] = 0;
        gVwfBackup->centre = 0;
        gVwfBackup->logMagic = VWF_LOG_MAGIC;
    }
}

// A save keeps its place in the script as a ROM address. Each build of the
// patch may lay the scripts out differently (an added sound, a moved fade),
// so a save made with an earlier build can point at the wrong line, or into
// the middle of a command, and the dialogue that follows is lost. Section
// numbers stay the same between builds, and the text box contents are saved
// with the game (the log above), so after loading, the save's section is
// walked from its start and the place is checked: the command the script was
// waiting at must be there, with the same text on the page. If it is not, the
// page with that text is looked up in the section (the nearest one to where
// the save was in the old section). Without either, the section starts over.
extern const u32 gScriptSizes[];

#define NO_POS 0xFFFFFFFF

struct PageSim
{
    u32 x, y;                // as textX / textY
    u8 len[VWF_LINES];       // characters on each line
    u8 written[VWF_LINES];   // line started on this page
    u8 bad[VWF_LINES];       // differs from the saved log
};

static void SimClearPage(struct PageSim * sim)
{
    u32 l;
    sim->x = sim->y = 0;
    for (l = 0; l < VWF_LINES; l++)
        sim->written[l] = 0;
}

static void SimPutChar(struct PageSim * sim, u32 code, bool32 useLog)
{
    u32 l = sim->y < VWF_LINES ? sim->y : VWF_LINES - 1;
    if (code >= VWF_GLYPH_COUNT)
        code = 0xFF;
    if (sim->x == 0)
    {
        // a line starts (VwfClearLine)
        sim->len[l] = 0;
        sim->bad[l] = 0;
        sim->written[l] = 1;
    }
    if (useLog && sim->len[l] < VWF_LOG_LEN && (gVwf->log[l][sim->len[l]] & 0x7FF) != code)
        sim->bad[l] = 1;
    if (sim->len[l] < 0xFF)
        sim->len[l]++;
    sim->x++;
}

static bool32 SimMatches(const struct PageSim * sim, const struct ScriptContext * ctx, bool32 useLog)
{
    u32 l, n;
    if (sim->y != ctx->textY || sim->x != ctx->textX)
        return FALSE;
    if (!useLog)
        return TRUE;
    for (l = 0; l < VWF_LINES; l++)
    {
        if (!sim->written[l])
            continue;
        n = sim->len[l] < VWF_LOG_LEN ? sim->len[l] : VWF_LOG_LEN;
        if (sim->bad[l] || gVwf->logLen[l] != n)
            return FALSE;
    }
    return TRUE;
}

void VwfFixSavedScriptPos(void)
{
    struct ScriptContext * ctx = &gScriptContext;
    const u8 * base = gScriptBase;
    const u32 * offs;
    const u16 * s;
    struct PageSim sim;
    u32 size, n, k, i, sec, start, end, pos, len, oldPos, rel, best, bestDist, d, t;
    bool32 useLog, oldValid = FALSE, oldText = FALSE;

    if (ctx->currentSection < 0x80 || (ctx->flags & SCRIPT_FULLSCREEN) || gMain.scenarioIdx > 16)
        return;
    size = gScriptSizes[gMain.scenarioIdx];
    n = *(const u32 *)base;
    offs = (const u32 *)(base + 4);
    // the section offsets come first, in order; jump records follow them
    for (k = 0; k < n; k++)
        if (offs[k] >= size || (k > 0 && offs[k] <= offs[k - 1]))
            break;
    sec = ctx->currentSection - 0x80;
    if (sec >= k)
        return;
    start = offs[sec];
    end = sec + 1 < k ? offs[sec + 1] : size;
    s = (const u16 *)(base + start);
    len = (end - start) / 2;
    oldPos = (ctx->scriptPtr >= s && ctx->scriptPtr < s + len) ? (u32)(ctx->scriptPtr - s) : NO_POS;
    rel = (u32)(ctx->scriptPtr - ctx->scriptSectionPtr);
    useLog = gVwf->logMagic == VWF_LOG_MAGIC;

    best = NO_POS;
    bestDist = NO_POS;
    for (i = 0; i < VWF_LINES; i++)
        sim.len[i] = sim.bad[i] = 0;
    SimClearPage(&sim);
    for (pos = 0; pos < len; )
    {
        t = s[pos];
        if (t == ctx->currentToken)
        {
            bool32 match = SimMatches(&sim, ctx, useLog);
            if (pos == oldPos)
            {
                oldValid = TRUE;
                oldText = match;
            }
            if (match)
            {
                d = pos > rel ? pos - rel : rel - pos;
                if (d < bestDist)
                {
                    best = pos;
                    bestDist = d;
                }
            }
        }
        if (t >= 0x80)
        {
            SimPutChar(&sim, t - 0x80, useLog);
            pos++;
            continue;
        }
        switch (t)
        {
        case 0x01: // new line
            sim.x = 0;
            sim.y++;
            break;
        case 0x00: // section start
        case 0x02: // wait for A (page end)
        case 0x07:
        case 0x0A:
        case 0x08: // choices
        case 0x09:
        case 0x2C:
        case 0x2E:
            SimClearPage(&sim);
            break;
        }
        pos += 1 + (t < 0x60 ? sCmdArgs[t] : 0);
    }

    ctx->scriptSectionPtr = s;
    if (oldValid && oldText)
        return;                         // the same place (the same script)
    if (best != NO_POS)
    {
        ctx->scriptPtr = s + best;      // the page with the saved text
        return;
    }
    if (oldValid)
        return;                         // nothing to compare: keep it
    // start the section over, with an empty text box
    ctx->scriptPtr = s;
    ctx->textX = 0;
    ctx->textY = 0;
    ctx->flags &= ~(1 | 2 | 0x20);
    for (i = 0; i < VWF_LINES; i++)
        gVwf->logLen[i] = 0;
    gVwf->choiceIds[3] = 0;
    for (i = 0; i < ARRAY_COUNT(gTextBoxCharacters); i++)
        gTextBoxCharacters[i].state &= ~0x8000;
}

#ifndef GUARD_VWF_H
#define GUARD_VWF_H

// Variable-width font renderer for the English text box.
// Three lines of text, each drawn into eight 32x16 sprites.

#define VWF_LINES 3
#define VWF_BLOCKS_PER_LINE 8          // 8 x 32px = 256px (224px used)
#define VWF_LINE_PIXELS (VWF_BLOCKS_PER_LINE * 32)
#define VWF_LINE_HEIGHT 14
// Where the lines sit in the text box (the sprites' offset: textXOffset,
// textYOffset). The box's inside is rows 114-157; the glyph cell has two blank
// rows on top, so the first line's capitals start at 116, two rows in, as the
// Japanese game's letters did (the DS has five); the third line's capitals are
// at 144-153, where the DS's "next" arrow sits (rows 144-152, bg.c).
// The font is the DS English release's (tools/en/make_vwf_font.py): each
// character's pixels, drawn at the pen; gVwfFontWidths says how many columns
// hold pixels, gVwfFontAdvance how far the pen moves (the width and a pixel;
// 4 for a space).
#define VWF_TEXT_X 9
#define VWF_TEXT_Y 114
#define VWF_GLYPH_ROWS 16
#define VWF_GLYPH_BYTES (VWF_GLYPH_ROWS * 8)
#define VWF_GLYPH_COUNT 1400
#define VWF_SPACE 0xFF                 // the space's character (its advance is the font's)
#define VWF_LINE_VRAM_STRIDE 0x800     // same per-line VRAM stride as the original text
#define VWF_LOG_LEN 64

void VwfPutChar(u32 code, u32 line, u32 color);
void VwfClearLine(u32 line);
void VwfSetCentre(u32 on);
void VwfRedraw(void);
void VwfBackup(void);
void VwfRestore(void);
void VwfSaveLog(void);
void VwfSetChoiceLabels(const u16 *ids);
void VwfReloadChoiceLabels(void);
bool32 VwfChoiceLabelsPending(void);
void ReloadChoiceLabelGfx(const u16 *ids);
void VwfLoadLog(void);
bool32 VwfFixSavedScriptPos(void);
void VwfFixSavedTextbox(void);

#endif // GUARD_VWF_H

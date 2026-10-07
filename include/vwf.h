#ifndef GUARD_VWF_H
#define GUARD_VWF_H

// Variable-width font renderer for the English text box.
// Three lines of text, each drawn into eight 32x16 sprites.

#define VWF_LINES 3
#define VWF_BLOCKS_PER_LINE 8          // 8 x 32px = 256px (224px used)
#define VWF_LINE_PIXELS (VWF_BLOCKS_PER_LINE * 32)
#define VWF_LINE_HEIGHT 14
#define VWF_GLYPH_ROWS 13
#define VWF_GLYPH_BYTES (VWF_GLYPH_ROWS * 8)
#define VWF_GLYPH_COUNT 1400
#define VWF_SPACE_WIDTH 4
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

#endif // GUARD_VWF_H

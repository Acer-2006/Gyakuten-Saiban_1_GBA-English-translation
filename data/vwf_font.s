	.section en_data, "a"
	.align 2
	.global gVwfFontGlyphs
gVwfFontGlyphs:
	.incbin "graphics/vwf/font_glyphs.bin"
	.align 2
	.global gVwfFontWidths
gVwfFontWidths:
	.incbin "graphics/vwf/font_widths.bin"
	.align 2
	.global gVwfFontAdvance
gVwfFontAdvance:
	.incbin "graphics/vwf/font_advance.bin"

@ the pages whose lines move a pixel or two so that none touch (vwf.c
@ VwfLineStarts, tools/en/text_gaps.py): 12 bytes a page, sorted
	.align 2
	.global gVwfPageMoves
gVwfPageMoves:
	.incbin "graphics/vwf/page_moves.bin"
gVwfPageMovesEnd:
	.global gVwfPageMoveCount
gVwfPageMoveCount:
	.word (gVwfPageMovesEnd - gVwfPageMoves) / 12

	.section en_data, "a"
	.align 2
	.global gVwfFontGlyphs
gVwfFontGlyphs:
	.incbin "graphics/vwf/font_glyphs.bin"
	.align 2
	.global gVwfFontWidths
gVwfFontWidths:
	.incbin "graphics/vwf/font_widths.bin"

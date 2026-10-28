@ English patch, the RFTA build's fingerprints (src/en_fingerprint.c): the
@ powder's inner loops, ARM code copied to IWRAM (gEnMovieCode, the movies'
@ place, which no movie needs while the fingerprints are up) when the
@ dusting screen opens.
@ Entry points by offset from the start (each a branch):
@   +0  void Band(struct EnFpBand *b)
@         a band of rows of the powder (a byte a pixel, 240 a row): where the
@         print's plane has no bit, the blow taken off (not below 0), the
@         tile marked in the dirty bits when it changes; the pixels of the
@         counted plane holding more than 0x80 added to good, those of the
@         ring plane holding 0x20 or more to bad (as the DS's 0x0206e600 and
@         0x0206f030). The planes: a bit a pixel, 30 bytes a row.
@   +4  u32 Render(struct EnFpRender *r)
@         the dirty tiles drawn (at most max, in order), each pixel the
@         powder's shade (the table) or the DS's grid under it (a line every
@         16 pixels at 7: colours 1 the green, 2 the line, 3 the crossing);
@         4bpp tiles, the screen's 30 x 20 in order; how many were drawn
@ struct EnFpBand: powder, print, count, ring, rows, blow, y, dirty, good, bad
@ struct EnFpRender: powder, dirty, tiles, max, shade

	.ifdef RFTA
	.text
	.align 2
	.arm
	.global gEnFpCodeStart
	.global gEnFpCodeEnd
	.global gEnFpShade
gEnFpCodeStart:
	b	Band
	b	Render

Band:
	push	{r4-r11, lr}
	sub	sp, sp, #8
	str	r0, [sp]		@ the arguments
	ldr	r12, [r0, #24]
	str	r12, [sp, #4]		@ y
	ldr	r4, [r0, #16]		@ rows
	ldr	r5, [r0, #20]		@ blow
	ldr	r7, [r0, #32]		@ good
	ldr	r8, [r0, #36]		@ bad
	ldmia	r0, {r0-r3}		@ powder, print, count, ring
1:	mov	r9, #0			@ the row's byte (8 pixels)
2:	ldmia	r0, {r11, r12}		@ no powder in the 8: nothing to do
	orrs	r11, r11, r12
	addeq	r0, r0, #8
	beq	6f
	ldrb	r10, [r1, r9]		@ the planes' bits: print, counted << 8, ring << 16
	ldrb	r11, [r2, r9]
	ldrb	r12, [r3, r9]
	orr	r10, r10, r11, lsl #8
	orr	r10, r10, r12, lsl #16
	mov	r11, #1
	mov	r6, #0			@ changed
3:	ldrb	r12, [r0]
	cmp	r12, #0
	beq	5f
	tst	r10, r11
	bne	4f
	subs	r12, r12, r5
	movmi	r12, #0
	strb	r12, [r0]
	orr	r6, r6, r5
4:	tst	r10, r11, lsl #8
	beq	41f
	cmp	r12, #0x80
	addhi	r7, r7, #1
41:	tst	r10, r11, lsl #16
	beq	5f
	cmp	r12, #0x20
	addhs	r8, r8, #1
5:	add	r0, r0, #1
	mov	r11, r11, lsl #1
	cmp	r11, #0x100
	blo	3b
	cmp	r6, #0
	beq	6f
	ldr	lr, [sp, #4]		@ the tile: (y >> 3) * 30 + byte
	mov	lr, lr, lsr #3
	rsb	lr, lr, lr, lsl #4
	add	lr, r9, lr, lsl #1
	ldr	r12, [sp]
	ldr	r12, [r12, #28]		@ dirty
	and	r11, lr, #31
	mov	r6, #1
	mov	r6, r6, lsl r11
	mov	lr, lr, lsr #5
	ldr	r11, [r12, lr, lsl #2]
	orr	r11, r11, r6
	str	r11, [r12, lr, lsl #2]
6:	add	r9, r9, #1
	cmp	r9, #30
	blo	2b
	add	r1, r1, #30
	add	r2, r2, #30
	add	r3, r3, #30
	ldr	lr, [sp, #4]
	add	lr, lr, #1
	str	lr, [sp, #4]
	subs	r4, r4, #1
	bne	1b
	ldr	r12, [sp]
	str	r7, [r12, #32]
	str	r8, [r12, #36]
	add	sp, sp, #8
	pop	{r4-r11, lr}
	bx	lr

@ a pixel n of the row: the shade, or the grid's nibble n
	.macro PX n
	ldrb	r12, [r0, #\n]
	ldrb	r12, [r9, r12]
	cmp	r12, #0
	.if \n
	moveq	r12, r10, lsr #(4 * \n)
	andeq	r12, r12, #15
	.else
	andeq	r12, r10, #15
	.endif
	orr	r11, r11, r12, lsl #(4 * \n)
	.endm

Render:
	push	{r4-r11, lr}
	sub	sp, sp, #4
	ldr	r12, [r0, #12]
	str	r12, [sp]		@ max
	ldr	r8, [r0]		@ powder
	ldr	r1, [r0, #4]		@ dirty
	ldr	r2, [r0, #8]		@ tiles
	ldr	r9, [r0, #16]		@ shade
	mov	r7, #0			@ drawn
	mov	r4, #0			@ the tile
	mov	r6, #0			@ its row
1:	mov	r5, #0			@ its column
2:	mov	r12, r4, lsr #5
	ldr	r11, [r1, r12, lsl #2]
	and	lr, r4, #31
	mov	r10, #1
	tst	r11, r10, lsl lr
	beq	5f
	bic	r11, r11, r10, lsl lr
	str	r11, [r1, r12, lsl #2]
	mov	r0, r6, lsl #11		@ the powder: row * 1920 + column * 8
	sub	r0, r0, r6, lsl #7
	add	r0, r0, r5, lsl #3
	add	r0, r8, r0
	add	r3, r2, r4, lsl #5	@ the tile's 32 bytes
	mov	lr, #8
3:	ldr	r10, =0x11111111	@ the grid's row: the green, the line at 7 of an even column
	tst	r5, #1
	addeq	r10, r10, #0x10000000
	cmp	lr, #1			@ (row 7 of an even row of tiles: all line)
	bne	4f
	tst	r6, #1
	ldreq	r12, =0x11111111
	addeq	r10, r10, r12
4:	mov	r11, #0
	PX	0
	PX	1
	PX	2
	PX	3
	PX	4
	PX	5
	PX	6
	PX	7
	str	r11, [r3], #4
	add	r0, r0, #240
	subs	lr, lr, #1
	bne	3b
	add	r7, r7, #1
	ldr	r12, [sp]
	cmp	r7, r12
	bhs	6f
5:	add	r4, r4, #1
	add	r5, r5, #1
	cmp	r5, #30
	blo	2b
	add	r6, r6, #1
	cmp	r6, #20
	blo	1b
6:	mov	r0, r7
	add	sp, sp, #4
	pop	{r4-r11, lr}
	bx	lr
	.ltorg

@ the powder's shade by its amount (0: none, the grid shows; then the DS's
@ four, measured: colours 4-7)
gEnFpShade:
	.byte	0
	.rept	31
	.byte	4
	.endr
	.rept	32
	.byte	5
	.endr
	.rept	48
	.byte	6
	.endr
	.rept	144
	.byte	7
	.endr
	.align 2
gEnFpCodeEnd:
	.endif

@ English patch, the RFTA build's movie player (src/en_movie.c): its inner
@ loops, ARM code copied to IWRAM (gEnMovieCode) when a movie opens.
@ Entry points by offset from the start (each a branch):
@   +0  u32 UnLz8(struct EnLz *lz, u8 *stop)
@         LZ77 in the BIOS's format, into EWRAM, a token at a time until
@         lz->dst reaches stop (or the end); 1 when it is all unpacked
@   +4  u32 UnLz32(struct EnLz *lz, u32 *stop)
@         the same for LZ77 of whole words (tools/en/rfta/movlz.c, UNIT 4:
@         the literals in a stream of their own, word-aligned), into VRAM
@   +8  void Apply(const u32 *bitmap, const u32 *tiles, u32 *slots, u32 mode)
@         the slots whose bits are set take the next tiles: copied (mode 0),
@         XORed (1), or copied with every other slot cleared (2, a keyframe);
@         mode >> 8: the number of slots
@   +12 void Overlay(const struct EnOverlayArgs *a)
@         the security footage's time stamp over its two rows of slots: each
@         slot it falls on is copied to a tile of its own with the stamp's
@         pixels drawn in, and the map shows that tile (en_movie.c)
@ struct EnLz: src (the flags and matches), dst, end, flag state (the flag
@ byte, bits 8-15 the tokens left in it), lit (UnLz32's literals)

	.ifdef RFTA
	.text
	.align 2
	.arm
	.global gEnMovieCodeStart
gEnMovieCodeStart:
	b	UnLz8
	b	UnLz32
	b	Apply
	b	Overlay

UnLz8:
	push	{r4-r8, lr}
	ldmia	r0, {r2-r5}		@ src, dst, end, flag state
	cmp	r1, r4
	movhi	r1, r4
	mov	r6, r5, lsr #8		@ tokens left in the flag byte
	and	r5, r5, #0xff
1:	cmp	r3, r1
	bhs	9f
	subs	r6, r6, #1
	ldrmib	r5, [r2], #1
	movmi	r6, #7
	tst	r5, #0x80
	mov	r5, r5, lsl #1
	bne	2f
	ldrb	r7, [r2], #1		@ a literal
	strb	r7, [r3], #1
	b	1b
2:	ldrb	r7, [r2], #1		@ a match: (len - 3) << 4 | disp >> 8, disp & 0xff
	ldrb	r8, [r2], #1
	orr	r8, r8, r7, lsl #8
	bic	r8, r8, #0xf000
	mov	r7, r7, lsr #4
	add	r7, r7, #3
	sub	r8, r3, r8
	sub	r8, r8, #1
3:	ldrb	r12, [r8], #1
	strb	r12, [r3], #1
	subs	r7, r7, #1
	bne	3b
	b	1b
9:	and	r5, r5, #0xff
	orr	r5, r5, r6, lsl #8
	stmia	r0, {r2-r5}
	cmp	r3, r4
	movhs	r0, #1
	movlo	r0, #0
	pop	{r4-r8, lr}
	bx	lr

UnLz32:
	push	{r4-r9, lr}
	ldmia	r0, {r2-r6}		@ src, dst, end, flag state, literals
	cmp	r1, r4
	movhi	r1, r4
	mov	r7, r5, lsr #8
	and	r5, r5, #0xff
1:	cmp	r3, r1
	bhs	9f
	subs	r7, r7, #1
	ldrmib	r5, [r2], #1
	movmi	r7, #7
	tst	r5, #0x80
	mov	r5, r5, lsl #1
	bne	2f
	ldr	r8, [r6], #4		@ a literal word
	str	r8, [r3], #4
	b	1b
2:	ldrb	r8, [r2], #1		@ a match: (len - 1) << 12 | (disp - 1), words
	ldrb	r9, [r2], #1
	orr	r9, r9, r8, lsl #8
	mov	r8, r9, lsr #12
	bic	r9, r9, #0xf000
	sub	r9, r3, r9, lsl #2
	sub	r9, r9, #4
3:	ldr	r12, [r9], #4
	str	r12, [r3], #4
	subs	r8, r8, #1
	bpl	3b
	b	1b
9:	and	r5, r5, #0xff
	orr	r5, r5, r7, lsl #8
	stmia	r0, {r2-r6}
	cmp	r3, r4
	movhs	r0, #1
	movlo	r0, #0
	pop	{r4-r9, lr}
	bx	lr

Apply:
	push	{r4-r11, lr}
	mov	lr, r3, lsr #8		@ slots
	and	r3, r3, #3		@ mode
	mov	r5, #0			@ the slot
1:	cmp	r5, lr
	bhs	9f
	tst	r5, #31
	ldreq	r4, [r0], #4		@ the bitmap's next word
	add	r12, r2, r5, lsl #5
	add	r5, r5, #1
	movs	r4, r4, lsr #1
	bcs	3f
	cmp	r3, #2
	beq	2f
	cmp	r4, #0			@ (no more in this word: on to the next)
	bne	1b
	add	r5, r5, #31
	bic	r5, r5, #31
	b	1b
2:	mov	r6, #0			@ a keyframe's empty slot
	mov	r7, #0
	mov	r8, #0
	mov	r9, #0
	stmia	r12!, {r6-r9}
	stmia	r12!, {r6-r9}
	b	1b
3:	cmp	r3, #1
	beq	4f
	ldmia	r1!, {r6-r11}
	stmia	r12!, {r6-r11}
	ldmia	r1!, {r6-r7}
	stmia	r12!, {r6-r7}
	b	1b
4:	ldmia	r1!, {r6-r8}
	ldmia	r12, {r9-r11}
	eor	r9, r9, r6
	eor	r10, r10, r7
	eor	r11, r11, r8
	stmia	r12!, {r9-r11}
	ldmia	r1!, {r6-r8}
	ldmia	r12, {r9-r11}
	eor	r9, r9, r6
	eor	r10, r10, r7
	eor	r11, r11, r8
	stmia	r12!, {r9-r11}
	ldmia	r1!, {r6-r7}
	ldmia	r12, {r9-r10}
	eor	r9, r9, r6
	eor	r10, r10, r7
	stmia	r12!, {r9-r10}
	b	1b
9:	pop	{r4-r11, lr}
	bx	lr

@ struct EnOverlayArgs
	OA_ROWS = 0		@ the stamp's rows for this second, 24 bytes each (bit x & 7 of byte x >> 3)
	OA_SLOTS = 4		@ the slots' tiles
	OA_OWN = 8		@ the stamp's tiles: one a slot of the two rows
	OA_MAP = 12		@ the map's first of the two rows (VRAM)
	OA_MAPBUF = 16		@ and in gBG3MapBuffer
	OA_SCROLL = 20		@ the screen's left edge in the ring (0-255)
	OA_COLOUR = 24		@ the stamp's colour in all eight nibbles
	OA_Y0 = 28		@ the stamp row at the first row's top line (may be below 0)
	OA_HEIGHT = 32		@ the stamp's rows
	OA_OWNMAP = 36		@ the map entry for the first stamp tile
	OA_SLOTMAP = 40		@ the map entry for the first row's first slot
	OA_LUT = 44		@ 16 halfwords: 4 pixels' bits to their nibbles

Overlay:
	push	{r4-r11, lr}
	mov	r11, r0
	mov	r10, #0			@ the row (0, 1)
1:	mov	r9, #0			@ the ring column
2:	ldr	r0, [r11, #OA_SCROLL]	@ the column's x on the screen, -8..247
	rsb	r0, r0, r9, lsl #3
	and	r0, r0, #255
	cmp	r0, #248
	subge	r0, r0, #256
	ldr	r1, [r11, #OA_SLOTMAP]	@ the map entry: the slot (unless the stamp is on it)
	add	r1, r1, r10, lsl #5
	add	r1, r1, r9
	cmn	r0, #8
	ble	8f
	cmp	r0, #160
	bge	8f
	ldr	r2, [r11, #OA_SLOTS]
	mov	r3, r1, lsl #20
	mov	r3, r3, lsr #20
	add	r2, r2, r3, lsl #5	@ the slot's tile
	ldr	r3, [r11, #OA_OWN]
	add	r12, r9, r10, lsl #5
	add	r3, r3, r12, lsl #5	@ its stamp tile
	ldr	r4, [r11, #OA_Y0]
	add	r4, r4, r10, lsl #3	@ the stamp row
	mov	r5, #0			@ any pixel
	mov	r6, #8
3:	ldr	r7, [r2], #4
	cmp	r4, #0
	blt	6f
	ldr	r12, [r11, #OA_HEIGHT]
	cmp	r4, r12
	bge	6f
	ldr	r12, [r11, #OA_ROWS]
	add	r12, r12, r4, lsl #4
	add	r12, r12, r4, lsl #3	@ rows + 24 * row
	cmp	r0, #0
	blt	4f
	add	r12, r12, r0, asr #3
	ldrb	r8, [r12]
	ldrb	lr, [r12, #1]
	orr	r8, r8, lr, lsl #8
	and	lr, r0, #7
	mov	r8, r8, lsr lr
	b	5f
4:	ldrb	r8, [r12]
	rsb	lr, r0, #0
	mov	r8, r8, lsl lr
5:	ands	r8, r8, #0xff
	beq	6f
	orr	r5, r5, r8
	ldr	r12, [r11, #OA_LUT]
	and	lr, r8, #15
	add	lr, r12, lr, lsl #1
	ldrh	lr, [lr]
	mov	r8, r8, lsr #4
	add	r12, r12, r8, lsl #1
	ldrh	r12, [r12]
	orr	r8, lr, r12, lsl #16	@ the pixels' nibbles
	ldr	r12, [r11, #OA_COLOUR]
	bic	r7, r7, r8
	and	r12, r12, r8
	orr	r7, r7, r12
6:	str	r7, [r3], #4
	add	r4, r4, #1
	subs	r6, r6, #1
	bne	3b
	cmp	r5, #0
	beq	8f
	ldr	r1, [r11, #OA_OWNMAP]
	add	r1, r1, r10, lsl #5
	add	r1, r1, r9
8:	add	r12, r9, #1		@ the map's column for the ring column
	and	r12, r12, #31
	add	r12, r12, r10, lsl #5
	mov	r12, r12, lsl #1
	ldr	r2, [r11, #OA_MAP]
	strh	r1, [r2, r12]
	ldr	r2, [r11, #OA_MAPBUF]
	strh	r1, [r2, r12]
	add	r9, r9, #1
	cmp	r9, #32
	blt	2b
	add	r10, r10, #1
	cmp	r10, #2
	blt	1b
	pop	{r4-r11, lr}
	bx	lr

	.global gEnMovieCodeEnd
gEnMovieCodeEnd:
	.endif

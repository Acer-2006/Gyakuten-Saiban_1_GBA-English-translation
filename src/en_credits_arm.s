@ English patch, the RFTA build's staff roll (src/en_credits.c): the
@ powder's inner loops, ARM code copied to IWRAM (gEnMovieCode, the movies'
@ place, which no movie needs while the pages are up). The DS's own
@ (0x0206ea50, 0x0206ec90, 0x0206f168: tools/en/rfta/credits.py) on the
@ GBA's screen: the powder a byte a pixel (240 a row), the sparks a byte a
@ pixel (0 or 1), the page a bit a pixel (30 bytes a row).
@ Entry points by offset from the start (each a branch), all taking the
@ same arguments (struct EnCreditsArgs, below):
@   +0  void Stamp(args)
@         count dots (dx, dy: s8 pairs at pts) round (cx, cy), each the
@         DS's rand(96) x 4 more powder (not over 255)
@   +4  void Blow(args)
@         rows y0 to y1 blown. masked: level + 0-31 taken off (not below
@         0), a pixel in 8 of those with powder throwing a spark; then the
@         page's made 0xE0 at least (its white: the DS holds them at the
@         page's 0xF0, drawn the same), a pixel in 16 of them throwing one.
@         Not masked: level taken off and a pixel in 4 of those with powder
@         throwing one where it is and another 1-8 rows above, -3 to 4
@         across. (The DS: 1 in 10 and 1 in 20 from fixed patterns, rand(24)
@         and rand(7).)
@   +8  void Render(args)
@         rows y0 to y1 drawn into BG3's 8bpp tiles (30 x 20, in order): the
@         powder's colour by its amount (Lut: the DS's min(w / 16 + 1, 14)),
@         the grid where there is none, a spark as colour 1 or 15 of the
@         powder's (and moved up k rows and q - 8 across, q the DS's x / 16:
@         k 8 + q, or (far) 24 + 3 q)
@ The random numbers: xorshift32 (seed, never 0).

	.ifdef RFTA
	.text
	.align 2
	.arm
	.global gEnCreditsCodeStart
	.global gEnCreditsCodeEnd
gEnCreditsCodeStart:
	b	Stamp
	b	Blow
	b	Render

	.equ	W, 240
	.equ	H, 160
	.equ	PAL, 48			@ the powder's colours 1-15
	.equ	GRID, 64		@ the green, the line, the crossing
@ struct EnCreditsArgs
	.equ	A_POWDER, 0
	.equ	A_PART, 4
	.equ	A_PAGE, 8
	.equ	A_PTS, 12
	.equ	A_COUNT, 16
	.equ	A_CX, 20
	.equ	A_CY, 24
	.equ	A_Y0, 28
	.equ	A_Y1, 32
	.equ	A_LEVEL, 36
	.equ	A_MASKED, 40
	.equ	A_FAR, 44
	.equ	A_TILES, 48
	.equ	A_SEED, 52

	.macro XS r
	eor	\r, \r, \r, lsl #13
	eor	\r, \r, \r, lsr #17
	eor	\r, \r, \r, lsl #5
	.endm

@ ---------------------------------------------------------------- Stamp
Stamp:
	push	{r4-r8, lr}
	ldr	r1, [r0, #A_PTS]
	ldr	r2, [r0, #A_COUNT]
	ldr	r3, [r0, #A_CX]
	ldr	r4, [r0, #A_CY]
	ldr	r5, [r0, #A_SEED]
	ldr	r6, [r0, #A_POWDER]
	cmp	r2, #0
	beq	9f
1:	ldrsb	r7, [r1], #1		@ dx
	ldrsb	r8, [r1], #1		@ dy
	add	r7, r7, r3
	cmp	r7, #W
	bhs	8f			@ (off the screen: unsigned)
	add	r8, r8, r4
	cmp	r8, #H
	bhs	8f
	mov	r12, #W
	mla	r7, r8, r12, r7		@ y * 240 + x
	XS	r5
	and	r12, r5, #0xFF		@ rand(96) * 4: (b * 3 / 2) & ~3
	add	r12, r12, r12, lsl #1
	mov	r12, r12, lsr #1
	bic	r12, r12, #3
	ldrb	lr, [r6, r7]
	add	lr, lr, r12
	cmp	lr, #255
	movhi	lr, #255
	strb	lr, [r6, r7]
8:	subs	r2, r2, #1
	bne	1b
9:	str	r5, [r0, #A_SEED]
	pop	{r4-r8, lr}
	bx	lr

@ ---------------------------------------------------------------- Blow
@ masked, a pixel s (0, 8, 16, 24) of the word P (the sparks' word S):
@ off the page as on it (the page's made at least 0xE0 after: PAGE), r5 the
@ level, lr the random word (the pixel's byte: bits 0-4 the amount, 5-7 the
@ spark)
	.macro MPX P, S, s
	ands	r12, \P, #(0xFF << \s)
	beq	43f
	and	r10, lr, #(31 << \s)
	add	r10, r10, r5, lsl #\s
	subs	r12, r12, r10
	movcc	r12, #0
	bic	\P, \P, #(0xFF << \s)
	orr	\P, \P, r12
	tst	lr, #(0xE0 << \s)
	orreq	\S, \S, #(1 << \s)
43:
	.endm

@ the page's pixels of the word (the low 4 bits of r4): at least 0xE0, half
@ their sparks taken off again
	.macro PAGE P, S
	and	r12, r4, #15
	adr	r10, Page01
	ldr	r12, [r10, r12, lsl #2]	@ 1 in each byte of the page's
	rsb	r10, r12, r12, lsl #3
	orr	\P, \P, r10, lsl #5
	and	r10, r12, lr, lsr #4
	bic	\S, \S, r10
	.endm

@ r0 powder, r1 sparks, r2 page, r3 the 8s left in the row, r4 the page's
@ bits, r5 level, r6 r7 the sparks thrown, r8 r9 the powder, r11 the rows
@ left, lr the seed
Blow:
	push	{r4-r11, lr}
	push	{r0}
	ldr	r12, [r0, #A_Y0]
	ldr	r11, [r0, #A_Y1]
	sub	r11, r11, r12		@ rows
	ldr	r5, [r0, #A_LEVEL]
	ldr	lr, [r0, #A_SEED]
	ldr	r10, [r0, #A_MASKED]
	mov	r3, #W
	mul	r3, r12, r3		@ y0 * 240
	ldr	r1, [r0, #A_PART]
	add	r1, r1, r3
	ldr	r2, [r0, #A_PAGE]
	add	r2, r2, r3, lsr #3	@ (y0 * 30)
	ldr	r0, [r0, #A_POWDER]
	add	r0, r0, r3
	cmp	r11, #0
	ble	99f
	cmp	r10, #0
	beq	Free
1:	mov	r3, #30
2:	ldrb	r4, [r2], #1
	ldmia	r0, {r8, r9}
	orr	r10, r8, r9
	orrs	r10, r10, r4
	beq	7f			@ no powder, no page: nothing
	mov	r6, #0
	mov	r7, #0
	XS	lr
	MPX	r8, r6, 0
	MPX	r8, r6, 8
	MPX	r8, r6, 16
	MPX	r8, r6, 24
	PAGE	r8, r6
	mov	r4, r4, lsr #4
	XS	lr
	MPX	r9, r7, 0
	MPX	r9, r7, 8
	MPX	r9, r7, 16
	MPX	r9, r7, 24
	PAGE	r9, r7
	stmia	r0, {r8, r9}
	orrs	r10, r6, r7
	beq	7f
	ldmia	r1, {r10, r12}
	orr	r10, r10, r6
	orr	r12, r12, r7
	stmia	r1, {r10, r12}
7:	add	r0, r0, #8
	add	r1, r1, #8
	subs	r3, r3, #1
	bne	2b
	subs	r11, r11, #1
	bne	1b
	b	99f

Page01:
	.irp	n, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
	.word	(\n & 1) | ((\n >> 1) & 1) << 8 | ((\n >> 2) & 1) << 16 | ((\n >> 3) & 1) << 24
	.endr

@ not masked: r0 r1 the row's powder and sparks, r3 x, r8 the 8 left, r9 y
Free:
	ldr	r9, [sp]
	ldr	r9, [r9, #A_Y0]
1:	mov	r3, #0
2:	add	r12, r0, r3
	ldmia	r12, {r6, r7}
	orrs	r6, r6, r7
	addeq	r3, r3, #8
	beq	6f
	mov	r8, #8
3:	ldrb	r6, [r0, r3]
	cmp	r6, #0
	beq	5f
	subs	r6, r6, r5
	movcc	r6, #0
	strb	r6, [r0, r3]
	XS	lr
	tst	lr, #3
	bne	5f
	mov	r6, #1
	strb	r6, [r1, r3]
	mov	r6, lr, lsr #2		@ the second: x + 4 - rand(8), 1 + rand(8) rows up
	and	r6, r6, #7
	rsb	r6, r6, #4
	add	r6, r6, r3
	cmp	r6, #W
	bhs	5f
	mov	r7, lr, lsr #5
	and	r7, r7, #7
	add	r7, r7, #1
	cmp	r7, r9
	bhi	5f
	mov	r12, #W
	mul	r12, r7, r12
	sub	r6, r6, r12
	mov	r12, #1
	strb	r12, [r1, r6]
5:	add	r3, r3, #1
	subs	r8, r8, #1
	bne	3b
6:	cmp	r3, #W
	blo	2b
	add	r0, r0, #W
	add	r1, r1, #W
	add	r9, r9, #1
	subs	r11, r11, #1
	bne	1b
99:	pop	{r0}
	str	lr, [r0, #A_SEED]
	pop	{r4-r11, lr}
	bx	lr

@ ---------------------------------------------------------------- Render
@ r0 powder, r1 sparks, r2 the tile's row, r3 y, r4 Lut, r5 r9 the 8
@ pixels drawn, r6 x, r7 the row's grid (4 pixels), r8 its last 4 of 16
@ (the line's pixel at x & 15 == 15), r11 seed; [sp] args, y1, far
Render:
	push	{r4-r11, lr}
	sub	sp, sp, #12
	str	r0, [sp]
	ldr	r12, [r0, #A_Y1]
	str	r12, [sp, #4]
	ldr	r12, [r0, #A_FAR]
	str	r12, [sp, #8]
	ldr	r11, [r0, #A_SEED]
	ldr	r3, [r0, #A_Y0]
	mov	r12, #W
	mul	r12, r3, r12
	ldr	r1, [r0, #A_PART]
	add	r1, r1, r12
	ldr	r0, [r0, #A_POWDER]
	add	r0, r0, r12
	adr	r4, Lut
	ldr	r12, [sp, #4]
	cmp	r3, r12
	bhs	99f
1:	and	r12, r3, #15		@ the grid: y & 15 == 7 a line (the DS's y 7 of 16)
	cmp	r12, #7
	moveq	r12, #GRID + 1
	movne	r12, #GRID
	strb	r12, [r4]		@ (no powder: the grid's)
	orr	r7, r12, r12, lsl #8
	orr	r7, r7, r7, lsl #16
	add	r8, r7, #0x01000000	@ the line across it (the crossing on a line)
	ldr	r2, [sp]		@ tiles + (y >> 3) * 1920 + (y & 7) * 8
	ldr	r2, [r2, #A_TILES]
	mov	r12, r3, lsr #3
	add	r2, r2, r12, lsl #11
	sub	r2, r2, r12, lsl #7
	and	r12, r3, #7
	add	r2, r2, r12, lsl #3
	mov	r6, #0
2:	ldmia	r1!, {r12, lr}
	orr	lr, r12, lr		@ sparks among the 8?
	ldmia	r0!, {r9, r10}
	orr	r12, r9, r10
	orrs	r12, r12, lr
	bne	3f
	tst	r6, #8			@ nothing: the grid
	moveq	r9, r7
	movne	r9, r8
	stmia	r2, {r7, r9}
	b	6f
3:	and	r12, r9, #0xFF		@ the powder's colours
	ldrb	r5, [r4, r12]
	and	r12, r9, #0xFF00
	ldrb	r12, [r4, r12, lsr #8]
	orr	r5, r5, r12, lsl #8
	and	r12, r9, #0xFF0000
	ldrb	r12, [r4, r12, lsr #16]
	orr	r5, r5, r12, lsl #16
	ldrb	r12, [r4, r9, lsr #24]
	orr	r5, r5, r12, lsl #24
	and	r12, r10, #0xFF
	ldrb	r9, [r4, r12]
	and	r12, r10, #0xFF00
	ldrb	r12, [r4, r12, lsr #8]
	orr	r9, r9, r12, lsl #8
	and	r12, r10, #0xFF0000
	ldrb	r12, [r4, r12, lsr #16]
	orr	r9, r9, r12, lsl #16
	movs	r12, r10, lsr #24
	ldrb	r12, [r4, r12]
	bne	4f
	tst	r6, #8			@ (none on the last pixel: the line's colour)
	addne	r12, r12, #1
4:	orr	r9, r9, r12, lsl #24
	cmp	lr, #0
	bne	Sparks
5:	stmia	r2, {r5, r9}
6:	add	r2, r2, #64
	add	r6, r6, #8
	cmp	r6, #W
	blo	2b
	add	r3, r3, #1
	ldr	r12, [sp, #4]
	cmp	r3, r12
	blo	1b
99:	ldr	r0, [sp]
	str	r11, [r0, #A_SEED]
	add	sp, sp, #12
	pop	{r4-r11, lr}
	bx	lr

@ a spark of the 8 (byte s of w, pixel k): drawn in colour 1 or 15 (a bit of
@ r11), set again at r3 + k if r7 has bit k (its place on the screen)
	.macro SPK w, out, s, k
	tst	\w, #(0xFF << \s)
	beq	59f
	bic	\out, \out, #(0xFF << \s)
	tst	r11, #(1 << \k)
	orreq	\out, \out, #((PAL + 1) << \s)
	orrne	\out, \out, #((PAL + 15) << \s)
	tst	r7, #(1 << \k)
	strneb	r8, [r3, #\k]
59:
	.endm

@ the 8's sparks: drawn, taken off and set again up the screen (k rows up,
@ q - 8 across: the same for the 8, q the DS's x / 16); [sp] y, then args,
@ y1, far
Sparks:
	push	{r3, r7, r8}
	ldmdb	r1, {r10, r12}
	mov	r8, #0
	mov	lr, #0
	stmdb	r1, {r8, lr}
	add	lr, r6, #8
	mov	lr, lr, lsr #4		@ q
	ldr	r8, [sp, #20]		@ far
	cmp	r8, #0
	addeq	r8, lr, #8		@ k: 8 + q
	addne	r8, lr, lr, lsl #1
	addne	r8, r8, #24		@ or 24 + 3 q
	mov	r7, #0xFF		@ the pixels whose place is on the screen:
	cmp	r6, #0
	moveq	r7, #0			@ not the first 8's (off to the left)
	cmp	r6, #W - 8
	moveq	r7, #1			@ the last 8's first only
	cmp	r8, r3
	movhi	r7, #0			@ none above the top
	sub	r3, r1, #16		@ the 8's sparks + q - 8 - k * 240
	add	r3, r3, lr
	rsb	lr, r8, r8, lsl #4
	sub	r3, r3, lr, lsl #4
	mov	r8, #1
	XS	r11
	SPK	r10, r5, 0, 0
	SPK	r10, r5, 8, 1
	SPK	r10, r5, 16, 2
	SPK	r10, r5, 24, 3
	SPK	r12, r9, 0, 4
	SPK	r12, r9, 8, 5
	SPK	r12, r9, 16, 6
	SPK	r12, r9, 24, 7
	pop	{r3, r7, r8}
	b	5b

@ the powder's colour by its amount (0: the grid's, set for each row)
	.align 2
Lut:
	.byte	GRID
	.rept	15
	.byte	PAL + 1
	.endr
	.irp	k, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
	.rept	16
	.byte	PAL + \k
	.endr
	.endr
	.rept	48
	.byte	PAL + 14
	.endr
	.align 2
gEnCreditsCodeEnd:
	.endif

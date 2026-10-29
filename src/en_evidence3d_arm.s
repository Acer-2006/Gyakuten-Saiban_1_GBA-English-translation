@ English patch, the RFTA build's evidence in 3D (src/en_evidence3d.c): the
@ renderer, ARM code copied to IWRAM (gEnMovieCode, the movies' place, free
@ while the viewer is up). The DS's camera, the vertices as the GX's
@ 1.3.12, the textures 16 colours (a nibble a texel), the triangles
@ textured with the perspective right every 16 pixels, one side drawn, a
@ 16-bit depth buffer of 1/depth (nearer is larger). Its every step in
@ integers is modelled in tools/en/rfta/evidence3d.py (Model), and the two
@ agree to the pixel.
@
@ Entry points by offset from the start (each a branch):
@   +0  void Transform(struct En3dXf *x)
@         each vertex (s16 x, y, z) into 3 words: x and y in 1/16 pixel
@         of the viewport, W = 2^26 / depth (0: nearer than the near plane)
@   +4  u32 DrawPart(struct En3dDraw *d)
@         the triangles of one part (one texture), until the frame's time is
@         up (1: called again, it goes on where it stopped) or they are done (0)
@
@ struct En3dXf { const s16 *verts; u32 count; s32 *out;
@                 s32 cx[4], cy[4], cz[4];   (the matrix's columns, 1.14, and the offset, 1.19.12)
@                 const u32 *r31; u32 maxW; }
@ struct En3dDraw { const u8 *tris; u32 count; const s32 *xv; const u8 *tex;
@                   u32 wlog, hlog, pal, zshift; u8 *fb; u16 *zb; const u32 *r31;
@                   u8 *frame; u32 limit, resume; }
@ (the frame: 280 bytes, best in IWRAM; it is the stack while DrawPart runs)
@ Triangles: u16 v0, v1, v2; s16 u0, v0, u1, v1, u2, v2 (1/16 texel), 18 bytes.
@ The frame buffer: the viewport's 24 x 16 tiles of 64 bytes, in order; the
@ depth buffer: 192 x 128 halfwords, row by row. r31: 2^31 / n, n 0..4097.

	.ifdef RFTA
	.text
	.align 2
	.arm
	.global gEn3dCodeStart
	.global gEn3dCodeEnd

	.equ VIEW_W, 192
	.equ VIEW_H, 128
	.equ DIST, (20 << 12)
	.equ NEAR, 2048
	.equ FX4, 1943			@ the DS's focal lengths in 1/16 pixel a unit
	.equ FY4, 1922
	.equ CLAMP, 0x8000		@ screen coordinates kept within +-2048 pixels

	.equ X_R31, 60			@ struct En3dXf
	.equ X_MAXW, 64
	.equ D_XV, 8			@ struct En3dDraw
	.equ D_TEX, 12
	.equ D_FB, 32
	.equ D_ZB, 36
	.equ D_R31, 40
	.equ D_FRAME, 44		@ (the frame below, kept between calls)
	.equ D_LIMIT, 48		@ the scanline after the vertical blank to stop by
	.equ D_RESUME, 52		@ 0 a new part, 1 at its next triangle, 2 at its row F_J

gEn3dCodeStart:
	b	Transform
	b	DrawPart

@ (a * b) >> s of the 64-bit product, s 1..31 (dst, tmp, a distinct)
	.macro MULHI dst, a, b, s, tmp
	smull	\tmp, \dst, \a, \b
	mov	\dst, \dst, lsl #(32 - \s)
	orr	\dst, \dst, \tmp, lsr #\s
	.endm

@ past the time the frame has (the scanlines since the vertical blank at
@ the struct's limit): to Suspend with r1 = kind (r1, r2)
	.macro OVER kind
	mov	r1, #0x04000000
	ldrh	r1, [r1, #6]
	subs	r1, r1, #160
	addlo	r1, r1, #228
	ldr	r2, [sp, #F_LIM]
	cmp	r1, r2
	movhs	r1, #\kind
	bhs	Suspend
	.endm

@ ---------------------------------------------------------------- Transform
Transform:
	push	{r4-r11, lr}
	mov	r12, r0
	ldr	r0, [r12]		@ verts
	ldr	r1, [r12, #4]		@ count
	ldr	r2, [r12, #8]		@ out
	ldr	r3, [r12, #X_R31]
	mov	r14, #0			@ the largest W
	cmp	r1, #0
	beq	9f
1:	ldrsh	r4, [r0], #2		@ x, y, z
	ldrsh	r5, [r0], #2
	ldrsh	r6, [r0], #2
	add	r7, r12, #12		@ X = (x cx0 + y cx1 + z cx2) >> 14 + cx3
	ldmia	r7!, {r8, r9, r10, r11}
	mul	r8, r4, r8
	mla	r8, r5, r9, r8
	mla	r8, r6, r10, r8
	add	r8, r11, r8, asr #14
	str	r8, [r2]		@ (X kept in the output)
	ldmia	r7!, {r8, r9, r10, r11}	@ Y
	mul	r8, r4, r8
	mla	r8, r5, r9, r8
	mla	r8, r6, r10, r8
	add	r8, r11, r8, asr #14
	str	r8, [r2, #4]
	ldmia	r7, {r8, r9, r10, r11}	@ Z
	mul	r8, r4, r8
	mla	r8, r5, r9, r8
	mla	r8, r6, r10, r8
	add	r8, r11, r8, asr #14
	rsb	r8, r8, #DIST		@ d = DIST - Z
	cmp	r8, #NEAR
	blt	7f
	@ W = R31 interpolated by d >> 6, >> 11
	mov	r9, r8, lsr #6
	cmp	r9, #4096
	movhs	r9, #4096
	andlo	r10, r8, #63
	movhs	r10, #0
	add	r11, r3, r9, lsl #2
	ldmia	r11, {r6, r7}
	sub	r7, r6, r7
	mul	r7, r10, r7
	sub	r6, r6, r7, lsr #6
	mov	r6, r6, lsr #11		@ W
	cmp	r6, r14
	movhi	r14, r6
	@ x16 = 96 * 16 + (X W FX4) >> 26, y16 = 64 * 16 - (Y W FY4) >> 26
	ldr	r4, [r2]		@ X
	ldr	r5, [r2, #4]		@ Y
	ldr	r9, =FX4
	mul	r9, r6, r9
	MULHI	r7, r4, r9, 26, r10
	add	r7, r7, #(VIEW_W / 2 * 16)
	ldr	r9, =FY4
	mul	r9, r6, r9
	MULHI	r8, r5, r9, 26, r10
	rsb	r8, r8, #(VIEW_H / 2 * 16)
	mov	r9, #CLAMP		@ (clamped)
	cmp	r7, r9
	movgt	r7, r9
	cmn	r7, r9
	rsblt	r7, r9, #0
	cmp	r8, r9
	movgt	r8, r9
	cmn	r8, r9
	rsblt	r8, r9, #0
	stmia	r2!, {r7, r8}
	str	r6, [r2], #4
	subs	r1, r1, #1
	bne	1b
	b	9f
7:	mov	r7, #0			@ too near: W 0
	mov	r8, #0
	stmia	r2!, {r7, r8}
	str	r7, [r2], #4
	subs	r1, r1, #1
	bne	1b
9:	str	r14, [r12, #X_MAXW]
	pop	{r4-r11, lr}
	bx	lr
	.ltorg

@ ---------------------------------------------------------------- DrawPart
@ the frame (sp +; sp unchanged throughout, the subroutines keep lr here):
	.equ F_P, 0		@ the struct
	.equ F_TRI, 4		@ the next triangle
	.equ F_LEFT, 8		@ triangles left
	.equ F_V0, 12		@ 3 vertices x 5 words: x, y, aW (W << 12), aU (u W), aV (v W)
	.equ F_V1, 32
	.equ F_V2, 52
	.equ F_GX, 72		@ the per-pixel gradients of aW, aU, aV
	.equ F_GY, 84		@ the per-row ones (F_GX + 12)
	.equ F_INV02, 96
	.equ F_J, 120		@ the row, the last row (exclusive)
	.equ F_J1, 124
	.equ F_I1, 128		@ the span's end
	.equ F_A, 132		@ aW, aU, aV at the chunk's start
	.equ F_U, 144		@ u, v there (16.16 texels)
	.equ F_V, 148
	.equ F_X, 152		@ the pixel
	.equ F_AE, 156		@ aW, aU, aV at the chunk's end
	.equ F_FBROW, 168
	.equ F_ZBROW, 172
	.equ F_LR1, 176		@ Rows' return
	.equ F_LR2, 180		@ Span's
	.equ F_N, 184		@ the chunk's pixels
	.equ F_D, 188		@ A1 - Al (3 words)
	.equ F_SP, 200		@ the caller's stack
	.equ F_XVP, 204		@ the struct's pointers and limit, copied at each call
	.equ F_TEXP, 208
	.equ F_FBP, 212
	.equ F_ZBP, 216
	.equ F_R31P, 220
	.equ F_LIM, 224
	.equ F_AFF, 228		@ the triangle drawn without the perspective (its depth hardly changes)
	.equ F_AR, 232		@ aW, aU, aV at the row's i0 (3 words; F_A the span's working copy)
	.equ F_I0P, 244		@ that i0
	.equ F_FIRST, 248	@ the half's first row (its attributes worked out in full)
	.equ F_X0, 252		@ the rows' edges, in a row for one ldm: the long edge from V0,
	.equ F_Y0, 256
	.equ F_S02, 260		@ its slope (16.16),
	.equ F_XE, 264		@ the short edge: x, y, slope,
	.equ F_YE, 268
	.equ F_SE, 272
	.equ F_LL, 276		@ the width at the middle vertex (> 0: the long edge on the left)
	.equ F_SIZE, 280

DrawPart:
	push	{r4-r11, lr}
	ldr	r1, [r0, #D_FRAME]	@ the frame is the struct's (the interrupts keep to their own stack)
	str	sp, [r1, #F_SP]
	mov	sp, r1
	str	r0, [sp, #F_P]
	ldr	r1, [r0, #D_XV]
	ldr	r2, [r0, #D_TEX]
	ldr	r3, [r0, #D_FB]
	ldr	r4, [r0, #D_ZB]
	ldr	r5, [r0, #D_R31]
	ldr	r6, [r0, #D_LIMIT]
	add	r7, sp, #F_XVP
	stmia	r7, {r1, r2, r3, r4, r5, r6}
	ldr	r1, [r0, #D_RESUME]
	cmp	r1, #1
	beq	NextTri
	cmp	r1, #2
	ldreq	r0, [sp, #F_J]
	beq	RowLoop
	ldmia	r0, {r1, r2}		@ tris, count
	str	r1, [sp, #F_TRI]
	str	r2, [sp, #F_LEFT]
	@ the pixel loop's shifts, the palette and the depth shift into its code
	ldr	r1, [r0, #16]		@ wlog
	ldr	r2, [r0, #20]		@ hlog
	ldr	r3, [r0, #24]		@ pal
	ldr	r4, [r0, #28]		@ zshift
	adrl	r5, PxZ			@ mov r12, r2, asr #zshift
	ldr	r6, [r5]
	bic	r6, r6, #0xF80
	orr	r6, r6, r4, lsl #7
	str	r6, [r5]
	adrl	r5, PxV			@ mov r12, r6, lsr #(32 - hlog)
	ldr	r6, [r5]
	bic	r6, r6, #0xF80
	rsb	r7, r2, #32
	orr	r6, r6, r7, lsl #7
	str	r6, [r5]
	adrl	r5, PxU			@ mov r14, r4, lsr #(32 - wlog)
	ldr	r6, [r5]
	bic	r6, r6, #0xF80
	rsb	r7, r1, #32
	orr	r6, r6, r7, lsl #7
	str	r6, [r5]
	adrl	r5, PxI			@ add r12, r14, r12, lsl #wlog
	ldr	r6, [r5]
	bic	r6, r6, #0xF80
	orr	r6, r6, r1, lsl #7
	str	r6, [r5]
	adrl	r5, PxP			@ orr r14, r14, #pal
	ldr	r6, [r5]
	bic	r6, r6, #0xFF
	orr	r6, r6, r3
	str	r6, [r5]
	adrl	r5, ChU			@ the chunk's pre-shifts: lsl #(16 - wlog), (16 - hlog)
	rsb	r7, r1, #16
	rsb	r8, r2, #16
	ldmia	r5, {r9, r10, r11, r12}
	bic	r9, r9, #0xF80
	orr	r9, r9, r7, lsl #7
	bic	r10, r10, #0xF80
	orr	r10, r10, r7, lsl #7
	bic	r11, r11, #0xF80
	orr	r11, r11, r8, lsl #7
	bic	r12, r12, #0xF80
	orr	r12, r12, r8, lsl #7
	stmia	r5, {r9, r10, r11, r12}
	adrl	r5, AffU		@ the affine span's, the same
	ldmia	r5, {r9, r10, r11, r12}
	bic	r9, r9, #0xF80
	orr	r9, r9, r7, lsl #7
	bic	r10, r10, #0xF80
	orr	r10, r10, r7, lsl #7
	bic	r11, r11, #0xF80
	orr	r11, r11, r8, lsl #7
	bic	r12, r12, #0xF80
	orr	r12, r12, r8, lsl #7
	stmia	r5, {r9, r10, r11, r12}
	adrl	r5, AffU2		@ the rows' own, the same
	stmia	r5, {r9, r10, r11, r12}
	@ the rows' pixel loop: its instructions as the span's (patched above)
	adrl	r5, PxZ
	adrl	r6, PxZ2
	ldr	r7, [r5]
	str	r7, [r6]
	ldr	r7, [r5, #(PxV - PxZ)]
	str	r7, [r6, #(PxV2 - PxZ2)]
	ldr	r7, [r5, #(PxU - PxZ)]
	str	r7, [r6, #(PxU2 - PxZ2)]
	ldr	r7, [r5, #(PxI - PxZ)]
	str	r7, [r6, #(PxI2 - PxZ2)]
	ldr	r7, [r5, #(PxP - PxZ)]
	str	r7, [r6, #(PxP2 - PxZ2)]

NextTri:
	OVER	1
	ldr	r0, [sp, #F_LEFT]
	subs	r0, r0, #1
	bmi	DoneTris
	str	r0, [sp, #F_LEFT]
	ldr	r0, [sp, #F_TRI]
	add	r1, r0, #18
	str	r1, [sp, #F_TRI]
	ldr	r12, [sp, #F_XVP]
	@ the three vertices: x, y; aW, aU, aV
	add	r11, sp, #F_V0
	add	r9, r0, #6		@ (the coordinates)
	mov	r10, #3
1:	ldrh	r1, [r0], #2		@ the index
	add	r1, r1, r1, lsl #1
	add	r1, r12, r1, lsl #2
	ldmia	r1, {r2, r3, r4}	@ x, y, W
	cmp	r4, #0
	beq	NextTri
	ldrsh	r5, [r9], #2		@ u
	ldrsh	r6, [r9], #2		@ v
	stmia	r11!, {r2, r3, r4, r5, r6}	@ (as they are, for now)
	subs	r10, r10, #1
	bne	1b
	@ one side: area = (x1 - x0)(y2 - y0) - (x2 - x0)(y1 - y0) > 0
	ldr	r0, [sp, #F_V0]
	ldr	r1, [sp, #(F_V0 + 4)]
	ldr	r2, [sp, #F_V1]
	ldr	r3, [sp, #(F_V1 + 4)]
	ldr	r4, [sp, #F_V2]
	ldr	r5, [sp, #(F_V2 + 4)]
	sub	r2, r2, r0		@ x1 - x0
	sub	r3, r3, r1		@ y1 - y0
	sub	r4, r4, r0		@ x2 - x0
	sub	r5, r5, r1		@ y2 - y0
	smull	r6, r7, r2, r5
	smull	r8, r9, r4, r3
	subs	r6, r6, r8
	sbcs	r7, r7, r9
	bmi	NextTri
	orrs	r6, r6, r7
	beq	NextTri
	@ affine when the depth hardly changes: max W - min W <= min W / 8 (half a texel off at most)
	ldr	r0, [sp, #(F_V0 + 8)]
	ldr	r1, [sp, #(F_V1 + 8)]
	ldr	r2, [sp, #(F_V2 + 8)]
	cmp	r0, r1
	movls	r3, r0
	movhi	r3, r1
	movls	r4, r1
	movhi	r4, r0
	cmp	r2, r3
	movlo	r3, r2
	cmp	r2, r4
	movhi	r4, r2
	sub	r4, r4, r3
	cmp	r4, r3, lsr #3
	movls	r5, #1
	movhi	r5, #0
	str	r5, [sp, #F_AFF]
	@ the attributes: aW = W << 12; aU, aV = u W, v W (affine: u, v << 12, texels 16.16)
	add	r11, sp, #(F_V0 + 8)
	mov	r10, #3
2:	ldmia	r11, {r2, r3, r4}	@ W, u, v
	mov	r6, r2, lsl #12
	cmp	r5, #0
	muleq	r7, r3, r2
	muleq	r8, r4, r2
	movne	r7, r3, lsl #12
	movne	r8, r4, lsl #12
	stmia	r11, {r6, r7, r8}
	add	r11, r11, #20
	subs	r10, r10, #1
	bne	2b
	@ sorted by y (a stable bubble: 01, 12, 01)
	add	r0, sp, #F_V0
	add	r1, sp, #F_V1
	bl	Sort2
	add	r0, sp, #F_V1
	add	r1, sp, #F_V2
	bl	Sort2
	add	r0, sp, #F_V0
	add	r1, sp, #F_V1
	bl	Sort2
	b	Setup

@ the records at r0 and r1 swapped if y0 > y1 (r2-r12)
Sort2:
	ldr	r2, [r0, #4]
	ldr	r3, [r1, #4]
	cmp	r2, r3
	bxle	lr
	ldmia	r0, {r2, r3, r4, r5, r6}
	ldmia	r1, {r7, r8, r9, r10, r11}
	stmia	r0, {r7, r8, r9, r10, r11}
	stmia	r1, {r2, r3, r4, r5, r6}
	bx	lr

Setup:
	ldr	r0, [sp, #F_V0]		@ x0
	ldr	r1, [sp, #(F_V0 + 4)]	@ y0
	ldr	r2, [sp, #F_V1]		@ x1
	ldr	r3, [sp, #(F_V1 + 4)]	@ y1
	ldr	r4, [sp, #F_V2]		@ x2
	ldr	r5, [sp, #(F_V2 + 4)]	@ y2
	subs	r6, r5, r1		@ dy02
	ble	NextTri
	str	r0, [sp, #F_X0]
	str	r1, [sp, #F_Y0]
	bl	Recip31
	str	r6, [sp, #F_INV02]
	cmp	r3, r5
	beq	3f
	@ the long edge at y1: t = (y1 - y0) inv02 (1.31); xl, Al
	sub	r7, r3, r1
	mul	r7, r6, r7		@ t
	sub	r8, r4, r0
	MULHI	r9, r8, r7, 31, r10
	add	r9, r0, r9		@ xl
	sub	r10, r2, r9		@ width = x1 - xl
	str	r10, [sp, #F_LL]
	add	r12, sp, #(F_V0 + 8)
	add	r11, sp, #F_D
	mov	r3, #3
4:	ldr	r8, [r12]		@ A0
	ldr	r9, [r12, #40]		@ A2
	sub	r9, r9, r8
	MULHI	r4, r9, r7, 31, r5
	add	r4, r8, r4		@ Al
	ldr	r9, [r12, #20]		@ A1
	sub	r9, r9, r4
	str	r9, [r11], #4
	add	r12, r12, #4
	subs	r3, r3, #1
	bne	4b
	b	5f
3:	sub	r10, r2, r4		@ y1 == y2: xl = x2, Al = A2
	str	r10, [sp, #F_LL]
	add	r12, sp, #(F_V0 + 8)
	add	r11, sp, #F_D
	mov	r3, #3
6:	ldr	r8, [r12, #40]		@ A2
	ldr	r9, [r12, #20]		@ A1
	sub	r9, r9, r8
	str	r9, [r11], #4
	add	r12, r12, #4
	subs	r3, r3, #1
	bne	6b
5:	ldr	r6, [sp, #F_LL]		@ |width| < 2: nothing
	cmp	r6, #0
	rsblt	r6, r6, #0
	cmp	r6, #2
	blt	NextTri
	bl	Recip31			@ invw
	ldr	r14, [sp, #F_LL]
	add	r12, sp, #F_D
	add	r11, sp, #F_GX
	mov	r3, #3
8:	ldr	r9, [r12], #4		@ gx = (A1 - Al) 16 / width
	MULHI	r8, r9, r6, 27, r10
	cmp	r14, #0
	rsblt	r8, r8, #0
	str	r8, [r11], #4
	subs	r3, r3, #1
	bne	8b
	@ gy = ((A2 - A0) - gx (x2 - x0) / 16) 16 / dy02
	ldr	r0, [sp, #F_V0]
	ldr	r4, [sp, #F_V2]
	sub	r4, r4, r0		@ x2 - x0
	ldr	r7, [sp, #F_INV02]
	add	r12, sp, #(F_V0 + 8)
	add	r11, sp, #F_GX
	mov	r3, #3
10:	ldr	r8, [r11]		@ gx
	MULHI	r9, r8, r4, 4, r10
	ldr	r8, [r12]		@ A0
	ldr	r10, [r12, #40]		@ A2
	sub	r10, r10, r8
	sub	r10, r10, r9
	MULHI	r8, r10, r7, 27, r9
	str	r8, [r11, #12]		@ gy
	add	r11, r11, #4
	add	r12, r12, #4
	subs	r3, r3, #1
	bne	10b
	MULHI	r8, r4, r7, 15, r9	@ the long edge's slope
	bl	ClampSlope
	str	r8, [sp, #F_S02]
	@ the top half: y0 to y1, the short edge 0 -> 1
	ldr	r0, [sp, #F_V0]
	ldr	r1, [sp, #(F_V0 + 4)]
	ldr	r2, [sp, #F_V1]
	ldr	r3, [sp, #(F_V1 + 4)]
	cmp	r3, r1
	ble	11f
	str	r0, [sp, #F_XE]
	str	r1, [sp, #F_YE]
	sub	r6, r3, r1
	bl	Recip31
	sub	r4, r2, r0
	MULHI	r8, r4, r6, 15, r9
	bl	ClampSlope
	str	r8, [sp, #F_SE]
	mov	r0, r1
	mov	r1, r3
	bl	Rows
11:	@ the bottom half: y1 to y2, the short edge 1 -> 2
	ldr	r0, [sp, #F_V1]
	ldr	r1, [sp, #(F_V1 + 4)]
	ldr	r2, [sp, #F_V2]
	ldr	r3, [sp, #(F_V2 + 4)]
	cmp	r3, r1
	ble	NextTri
	str	r0, [sp, #F_XE]
	str	r1, [sp, #F_YE]
	sub	r6, r3, r1
	bl	Recip31
	sub	r4, r2, r0
	MULHI	r8, r4, r6, 15, r9
	bl	ClampSlope
	str	r8, [sp, #F_SE]
	mov	r0, r1
	mov	r1, r3
	bl	Rows
	b	NextTri

DoneTris:
	mov	r1, #0
	mov	r0, #0
	b	1f
Suspend:			@ r1: how to go on
	mov	r0, #1
1:	ldr	r2, [sp, #F_P]
	str	r1, [r2, #D_RESUME]
	ldr	sp, [sp, #F_SP]
	pop	{r4-r11, lr}
	bx	lr

@ r6 = 2^31 / r6 (r6 >= 1): the table to 4096, interpolated by r6 >> 4
@ past it (r7, r8)
Recip31:
	ldr	r7, [sp, #F_R31P]
	cmp	r6, #4096
	ldrls	r6, [r7, r6, lsl #2]
	bxls	lr
	mov	r8, r6, lsr #4
	cmp	r8, #4096
	movhs	r8, #4096
	andlo	r6, r6, #15
	movhs	r6, #0
	add	r7, r7, r8, lsl #2
	ldmia	r7, {r7, r8}
	sub	r8, r7, r8
	mul	r8, r6, r8
	sub	r6, r7, r8, lsr #4
	mov	r6, r6, lsr #4
	bx	lr

@ r8 clamped to +-2^30
ClampSlope:
	cmp	r8, #0x40000000
	movgt	r8, #0x40000000
	cmn	r8, #0x40000000
	movlt	r8, #0xC0000000
	bx	lr

@ ---------------------------------------------------------------- Rows
@ the rows with centres in [r0, r1) (1/16 pixel): the long edge (V0,
@ F_S02), the short (F_XE, F_YE, F_SE)
Rows:
	str	lr, [sp, #F_LR1]
	sub	r0, r0, #8		@ j0 = max(0, (ya - 8 + 15) >> 4)
	add	r0, r0, #15
	movs	r0, r0, asr #4
	movmi	r0, #0
	sub	r1, r1, #8		@ j1 = min(VIEW_H, (yb - 8 + 15) >> 4)
	add	r1, r1, #15
	mov	r1, r1, asr #4
	cmp	r1, #VIEW_H
	movgt	r1, #VIEW_H
	str	r1, [sp, #F_J1]
	mov	r2, #1
	str	r2, [sp, #F_FIRST]
RowLoop:
	ldr	r1, [sp, #F_J1]
	cmp	r0, r1
	ldrge	pc, [sp, #F_LR1]
	str	r0, [sp, #F_J]
	tst	r0, #7			@ (the time looked at every 8 rows)
	bne	5f
	OVER	2
5:	mov	r11, r0, lsl #4		@ yc = 16 j + 8
	add	r11, r11, #8
	add	r12, sp, #F_X0
	ldmia	r12, {r1, r2, r3, r5, r6, r7, r8}	@ x0, y0, s02, xe, ye, se, the width
	sub	r4, r11, r2		@ (yc - y0, kept)
	MULHI	r9, r3, r4, 16, r10	@ the long edge: xa = x0 + s02 (yc - y0) >> 16
	add	r9, r1, r9
	sub	r6, r11, r6		@ the short edge
	MULHI	r10, r7, r6, 16, r3
	add	r10, r5, r10
	cmp	r8, #0
	movle	r3, r9			@ (the long edge on the right)
	movle	r9, r10
	movle	r10, r3
	add	r6, r9, #7		@ i0 = max(0, (left - 8 + 15) >> 4)
	movs	r6, r6, asr #4
	movmi	r6, #0
	add	r7, r10, #7		@ i1 = min(VIEW_W, (right - 8 + 15) >> 4)
	mov	r7, r7, asr #4
	cmp	r7, #VIEW_W
	movgt	r7, #VIEW_W
	@ the attributes at (i0, yc): A0 + gx (16 i0 + 8 - x0) / 16 + gy (yc - y0) / 16
	@ in full on the half's first row, then the last row's + gy + gx (i0 - its i0)
	@ (the same, to the bit) -> r0, r1, r2
	ldr	r8, [sp, #F_FIRST]
	cmp	r8, #0
	beq	3f
	mov	r5, r6, lsl #4
	add	r5, r5, #8
	sub	r5, r5, r1
	add	r12, sp, #(F_V0 + 8)
	add	r11, sp, #F_GX
	add	r10, sp, #F_AR
	mov	r3, #3
1:	ldr	r8, [r11]		@ gx
	MULHI	r9, r8, r5, 4, r1
	ldr	r8, [r11, #12]		@ gy
	MULHI	r2, r8, r4, 4, r1
	add	r9, r9, r2
	ldr	r8, [r12], #4		@ A0
	add	r9, r9, r8
	str	r9, [r10], #4
	add	r11, r11, #4
	subs	r3, r3, #1
	bne	1b
	mov	r8, #0
	str	r8, [sp, #F_FIRST]
	add	r12, sp, #F_AR
	ldmia	r12, {r0, r1, r2}
	b	4f
3:	ldr	r8, [sp, #F_I0P]
	sub	r8, r6, r8
	add	r12, sp, #F_AR
	ldmia	r12, {r0, r1, r2}
	add	r9, sp, #F_GX
	ldmia	r9, {r3, r4, r5}
	mla	r0, r3, r8, r0
	mla	r1, r4, r8, r1
	mla	r2, r5, r8, r2
	add	r9, sp, #F_GY
	ldmia	r9, {r3, r4, r5}
	add	r0, r0, r3
	add	r1, r1, r4
	add	r2, r2, r5
	stmia	r12, {r0, r1, r2}
4:	str	r6, [sp, #F_I0P]
	subs	r9, r7, r6		@ the pixels
	ble	RowNext
	@ the row in the frame buffer: + (j >> 3) 24 64 + (j & 7) 8; the depth buffer: + j 384
	ldr	r10, [sp, #F_J]
	ldr	r11, [sp, #F_FBP]
	mov	r12, r10, lsr #3
	add	r12, r12, r12, lsl #1
	add	r11, r11, r12, lsl #9
	and	r12, r10, #7
	add	r11, r11, r12, lsl #3
	ldr	r12, [sp, #F_ZBP]
	add	r10, r10, r10, lsl #1
	add	r12, r12, r10, lsl #7
	ldr	r10, [sp, #F_AFF]
	cmp	r10, #0
	bne	RowAffine
	@ with the perspective: the span's chunks (Span)
	str	r11, [sp, #F_FBROW]
	str	r12, [sp, #F_ZBROW]
	str	r7, [sp, #F_I1]
	str	r6, [sp, #F_X]
	add	r12, sp, #F_A
	stmia	r12, {r0, r1, r2}
	bl	Span
	b	RowNext
	@ straight across: the pixel loop here (its own copy, patched as the other)
RowAffine:
	mov	r10, r6, lsr #3		@ the buffers at i0
	add	r11, r11, r10, lsl #6
	and	r10, r6, #7
	add	r11, r11, r10
	add	r12, r12, r6, lsl #1
	mov	r4, r1
	mov	r6, r2
	mov	r2, r0
	mov	r0, r11
	mov	r1, r12
	add	r12, sp, #F_GX
	ldmia	r12, {r3, r5, r7}	@ gW, du, dv
AffU2:	mov	r4, r4, lsl #9		@ U = u << (16 - wlog)    (patched)
	mov	r5, r5, lsl #9		@ dU
	mov	r6, r6, lsl #9		@ V = v << (16 - hlog)    (patched)
	mov	r7, r7, lsl #9		@ dV
	ldr	r8, [sp, #F_TEXP]
PxZ2:	mov	r12, r2, asr #6		@ the depth: aW >> zshift   (patched)
	ldrh	r11, [r1]
	cmp	r12, r11
	bls	2f
	strh	r12, [r1]
PxV2:	mov	r12, r6, lsr #26	@ v & (h - 1)     (patched: 32 - hlog)
PxU2:	mov	r14, r4, lsr #26	@ u & (w - 1)     (patched: 32 - wlog)
PxI2:	add	r12, r14, r12, lsl #6	@ v w + u         (patched: wlog)
	ldrb	r14, [r8, r12, lsr #1]
	tst	r12, #1
	movne	r14, r14, lsr #4
	and	r14, r14, #15
PxP2:	orr	r14, r14, #0x20		@ the palette slot (patched)
	strb	r14, [r0]
2:	add	r2, r2, r3
	add	r4, r4, r5
	add	r6, r6, r7
	add	r0, r0, #1
	tst	r0, #7
	addeq	r0, r0, #56
	add	r1, r1, #2
	subs	r9, r9, #1
	bne	PxZ2
RowNext:
	ldr	r0, [sp, #F_J]
	add	r0, r0, #1
	b	RowLoop

@ ---------------------------------------------------------------- Span
@ the pixels F_X to F_I1 of the row, the attributes F_A at the first, in
@ chunks to the next multiple of 16
Span:
	str	lr, [sp, #F_LR2]
	ldr	r0, [sp, #F_AFF]
	cmp	r0, #0
	bne	SpanAffine
	add	r12, sp, #F_A
	ldmia	r12, {r0, r1, r2}
	bl	UV
	str	r0, [sp, #F_U]
	str	r1, [sp, #F_V]
Chunk:
	ldr	r10, [sp, #F_X]
	ldr	r11, [sp, #F_I1]
	subs	r9, r11, r10		@ left
	ldrle	pc, [sp, #F_LR2]
	and	r8, r10, #15		@ n = min(16 - (x & 15), left)
	rsb	r8, r8, #16
	cmp	r9, r8
	movlt	r8, r9
	str	r8, [sp, #F_N]
	add	r12, sp, #F_A		@ the chunk's end: A + g n
	ldmia	r12, {r0, r1, r2}
	add	r12, sp, #F_GX
	ldmia	r12, {r3, r4, r5}
	mla	r0, r3, r8, r0
	mla	r1, r4, r8, r1
	mla	r2, r5, r8, r2
	add	r12, sp, #F_AE
	stmia	r12, {r0, r1, r2}
	bl	UV			@ u2, v2
	ldr	r8, [sp, #F_N]
	adr	r12, RecipChunk		@ du = (u2 - u) / n, dv
	ldr	r12, [r12, r8, lsl #2]
	ldr	r2, [sp, #F_U]
	ldr	r3, [sp, #F_V]
	str	r0, [sp, #F_U]		@ (the next chunk's start)
	str	r1, [sp, #F_V]
	sub	r0, r0, r2
	MULHI	r5, r0, r12, 16, r6
	sub	r1, r1, r3
	MULHI	r7, r1, r12, 16, r6
	@ pre-shifted to the texture's size: wrapping by overflow
ChU:	mov	r4, r2, lsl #9		@ U = u << (16 - wlog)    (patched)
	mov	r5, r5, lsl #9		@ dU
	mov	r6, r3, lsl #9		@ V = v << (16 - hlog)    (patched)
	mov	r7, r7, lsl #9		@ dV
	ldr	r10, [sp, #F_X]
	add	r11, r10, r8
	str	r11, [sp, #F_X]
	mov	r9, r8
	ldr	r0, [sp, #F_FBROW]	@ the buffers at x
	mov	r11, r10, lsr #3
	add	r0, r0, r11, lsl #6
	and	r11, r10, #7
	add	r0, r0, r11
	ldr	r1, [sp, #F_ZBROW]
	add	r1, r1, r10, lsl #1
	ldr	r2, [sp, #F_A]		@ aW
	ldr	r3, [sp, #F_GX]		@ gW
	ldr	r8, [sp, #F_TEXP]
PxZ:	mov	r12, r2, asr #6		@ the depth: aW >> zshift   (patched)
	ldrh	r11, [r1]
	cmp	r12, r11
	bls	2f
	strh	r12, [r1]
PxV:	mov	r12, r6, lsr #26	@ v & (h - 1)     (patched: 32 - hlog)
PxU:	mov	r14, r4, lsr #26	@ u & (w - 1)     (patched: 32 - wlog)
PxI:	add	r12, r14, r12, lsl #6	@ v w + u         (patched: wlog)
	ldrb	r14, [r8, r12, lsr #1]
	tst	r12, #1
	movne	r14, r14, lsr #4
	and	r14, r14, #15
PxP:	orr	r14, r14, #0x20		@ the palette slot (patched)
	strb	r14, [r0]
2:	add	r2, r2, r3
	add	r4, r4, r5
	add	r6, r6, r7
	add	r0, r0, #1
	tst	r0, #7
	addeq	r0, r0, #56
	add	r1, r1, #2
	subs	r9, r9, #1
	bne	PxZ
	add	r12, sp, #F_AE		@ the next chunk from the end's attributes
	ldmia	r12, {r0, r1, r2}
	add	r12, sp, #F_A
	stmia	r12, {r0, r1, r2}
	b	Chunk

@ the affine span: u, v straight on (the pixel loop's end goes back to Chunk:
@ nothing left there)
SpanAffine:
	ldr	r10, [sp, #F_X]
	ldr	r11, [sp, #F_I1]
	sub	r9, r11, r10
	str	r11, [sp, #F_X]
	add	r12, sp, #F_A
	ldmia	r12, {r2, r4, r6}	@ aW, u, v
	add	r12, sp, #F_AE
	stmia	r12, {r2, r4, r6}
	add	r12, sp, #F_GX
	ldmia	r12, {r3, r5, r7}	@ gW, du, dv
AffU:	mov	r4, r4, lsl #9		@ U = u << (16 - wlog)    (patched)
	mov	r5, r5, lsl #9		@ dU
	mov	r6, r6, lsl #9		@ V = v << (16 - hlog)    (patched)
	mov	r7, r7, lsl #9		@ dV
	ldr	r0, [sp, #F_FBROW]
	mov	r11, r10, lsr #3
	add	r0, r0, r11, lsl #6
	and	r11, r10, #7
	add	r0, r0, r11
	ldr	r1, [sp, #F_ZBROW]
	add	r1, r1, r10, lsl #1
	ldr	r8, [sp, #F_TEXP]
	b	PxZ

@ r0 = aW, r1 = aU, r2 = aV -> r0 = u, r1 = v (16.16 texels): the depth
@ 2^28 / W (W = aW >> 12) from R31 by W >> 3, interpolated, >> 6 (r3-r6)
UV:
	mov	r3, r0, asr #12
	cmp	r3, #8
	movlt	r3, #8
	mov	r4, r3, lsr #3
	and	r5, r3, #7
	cmp	r4, #4096
	movhs	r4, #4096
	movhs	r5, #0
	ldr	r6, [sp, #F_R31P]
	add	r6, r6, r4, lsl #2
	ldmia	r6, {r3, r4}
	sub	r4, r3, r4
	mul	r4, r5, r4
	sub	r3, r3, r4, lsr #3
	mov	r3, r3, lsr #6		@ z
	MULHI	r0, r1, r3, 16, r4
	MULHI	r1, r2, r3, 16, r4
	bx	lr

@ 2^16 / n for the chunks, n 0..16
RecipChunk:
	.word	0, 65536, 32768, 21845, 16384, 13107, 10923, 9362, 8192, 7282, 6554, 5958, 5461, 5041, 4681, 4369, 4096
gEn3dCodeEnd:
	@ the frame follows the code at 0xC00 (en_evidence3d.c: sFrame): an
	@ error here ("attempt to move .org backwards") when the code outgrows it
	.org	gEn3dCodeStart + 0xC00
	.endif

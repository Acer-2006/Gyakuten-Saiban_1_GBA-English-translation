// English patch, the RFTA build: the fifth episode's evidence in 3D (the
// DS's Court Record "Check" on evidence with a model, and the scenes that
// have evidence turned over; tools/en/rfta/evidence3d.py has what was read
// off the DS). The Court Record's L ("Check", shown beside the L button)
// opens the viewer on evidence with a model:
//   the model drawn as the DS draws it (en_evidence3d_arm.s: in real time,
//     in the time each frame has, the picture shown when it is whole)
//   the + pad turns it, R and the + pad move the touch's point (the blue
//     lines and square), L and up / down zoom (the slider's knob)
//   "Examine" (A) shows on a hotspot under the point: the model turns to the
//     DS's pose for it and its lines run (file 35's, or the chapter's for
//     the scenes' own); some change the model with an animation (the wallet
//     opened, the phone flipped, the knife's switch, the book's pages)
//   B goes back to the Court Record (the scenes' Back: their section)
// Script command 69 (translate.py): 69 0 n opens the Court Record for scene
// n (the DS's 74 8 2e, 74 b 0: the evidence to be checked there; B is held
// off until the scene ends), 69 2<<8 | n shows close-up n in the viewer (the
// DS's 7B 0 n), 69 3<<8 takes it away, 69 4<<8 | n starts the jar puzzle
// (the DS's 74 8 32: the Unstable Jar's pieces put together, with the
// viewer's renderer and screen; jarpuzzle.py).
// The viewer is the Court Record's state 8: it saves what the screen, the
// text box and the script had (gSaveDataBuffer, as the evidence details do)
// and puts it all back as it leaves.
#include "global.h"
#include "main.h"
#include "background.h"
#include "script.h"
#include "ewram.h"
#include "animation.h"
#include "court_record.h"
#include "save.h"
#include "vwf.h"
#include "constants/process.h"
#include "constants/oam_allocations.h"
#include "constants/songs.h"
#include "investigation.h"
#include "sound.h"
#include "utils.h"
#include "graphics.h"
#include "en_rfta.h"

#if RFTA

struct En3dTexture { u32 off; u8 wlog, hlog; u16 pal[16]; };
struct En3dMesh { u32 head, tris; };
struct En3dQuad { u8 id, word; s16 n[3]; s16 pts[12]; };
struct En3dRecord { u8 meshes[3]; u8 nhot, nblock; u16 first; };
struct En3dId { u16 section; u8 chapter, flag, to; s16 q[4]; s32 t[3]; u8 anim[4]; u8 nanim; u16 elseSection; };
struct En3dScene { u8 ev; u16 open, hover; u8 final; u16 after, back; };
struct En3dCloseup { u32 off; u16 pal[16]; };
struct En3dPiece { s16 dx, dy; u8 shape, size; u16 tile; u8 last; };
struct En3dJarStep { s16 yaw; u8 crossX, crossY; s32 ty, tz; u16 guide, nguide; u8 box[4], cache[4]; };
#include "data/en_rfta_evidence3d.h"
extern const u8 gEn3dData[];

// the renderer (en_evidence3d_arm.s), copied to IWRAM
struct En3dXf { const s16 * verts; u32 count; s32 * out; s32 cx[4], cy[4], cz[4]; const u32 * r31; u32 maxW;
                s32 fx, fy, ox, oy; };
struct En3dDraw { const u8 * tris; u32 count; const s32 * xv; const u8 * tex; u32 wlog, hlog, pal, zshift;
                  u8 * fb; u16 * zb; const u32 * r31; u8 * frame; u32 limit, resume; };
extern const u8 gEn3dCodeStart[];
extern const u8 gEn3dCodeEnd[];
extern u32 gEnMovieCode[];
#define Transform ((void (*)(struct En3dXf *))((u8 *)gEnMovieCode + 0))
#define DrawPart ((u32 (*)(struct En3dDraw *))((u8 *)gEnMovieCode + 4))

enum { V_OFF, V_FADE_OUT, V_SETUP, V_FIRST, V_FADE_IN, V_VIEW, V_TURN, V_ANIM, V_SCRIPT, V_FADE_LEAVE, V_LEAVE, V_SHOW_RECORD,
       // the jar puzzle's (after V_FIRST's picture: V_FADE_IN, then these)
       J_RISE, J_SPIN, J_PLAY, J_ROTATE, J_SEND, J_FIT, J_FLASH, J_HOLD, J_TURN, J_MISS, J_RETURN, J_END,
       // the Blue Badger's angle's
       B_PLAY, B_FLASH };
enum { R_IDLE, R_CLEAR, R_XFORM, R_DRAW, R_READY };
enum { AFTER_NONE, AFTER_RESTORE, AFTER_STAY, AFTER_END, AFTER_BACK };
enum { THEN_EXAMINE, THEN_VIEW };

#define CHAPTER_SECTIONS_UNTIL 18       // the DS's flagged ids: their chapter lines in chapter 18 and before
#define OAM_FIRST OAM_IDX_GENERAL_2     // 57-87
#define OAM_LAST 87
#define TILE_BASE 0x1A0                 // OBJ tiles 0x1A0-0x27F: the viewer's sprites
#define PAL_UI 8
// the jar puzzle's sprites: its own set, the fragment (64 x 64, affine) and
// the crosshair after it; the fragment's colours, the crosshair's (pulsing)
#define JAR_TILE_FRAGMENT EN3D_JAR_SPRITE_TILES
#define JAR_TILE_CROSS (EN3D_JAR_SPRITE_TILES + 64)
#define PAL_FRAGMENT 10
#define PAL_CROSS 11
#define JAR_AFFINE 31                   // (the last affine group: the plate's and the people's are the first)
#define TURN_STEP_COS 16380             // 2.5 degrees a frame (half angles, 1.14)
#define TURN_STEP_SIN 357
#define ZOOM_MAX (12 << 12)             // toward the camera, 1.19.12 (the DS's poses go to 12)
#define ZOOM_STEP 0x180
#define CURSOR_SPEED 2
#define TURN_FRAMES 20
#define ANIM_FRAMES 8
#define TEXTBOX_TOP 112                 // (the text box's top: the tabs under it while it talks)
#define FADE_ALL 0x3F                   // the fades' targets: the backdrop too (the grid's grey, under the picture)

struct En3d
{
    u8 mode, phase, scene, sceneHere;       // scene: n + 1 while one is on; sceneHere: this evidence is its
    u8 record, evidence, hit, hovered;
    u8 render, mesh, part, dirty;
    u8 closeup, closeupShown, uploadAll, after;
    u8 animStep, animTimer, pendingId, file35;
    u8 fromState, fromVar1, fromVar2, sceneEnding;
    u8 turnThen, drawRec, coloursRec, oam;
    u16 afterSection, timer;
    s16 curX, curY;
    s32 zoom;
    s16 q[4], q0[4], q1[4], qSaved[4];
    s32 t[3], t0[3], t1[3], tSaved[3];
    u8 box[4], drawnBox[4];                 // tiles: x0, y0, x1, y1 (the picture being drawn, the one shown)
    u8 upload0, upload1, uploadReady, zshift;
    u16 vertsOf[3];
    u32 maxW;
    const u8 * scriptBase;
    struct En3dDraw draw;
    struct En3dXf xf;
    s32 m[9];                               // the rotation, 1.14, row by row
    s32 rm[9], rt[3];                       // the picture being drawn's
    struct ScriptContext savedCtx;          // the script while file 35's section runs
    // the picture's meshes (the record's, or the jar's) and their transforms
    u8 nitems, spare, interleave, guideDrawn;
    u8 itemMesh[12], itemXf[12];
    s32 rm2[9], rt2[3];                     // the second (the jar's piece in flight)
    // the jar puzzle (jar: 0 the viewer; 1 Day 2's, 2 Day 3's)
    u8 jar, jarStep, jarEnd, jarSel;        // the step, the one it ends at, the fragment picked (its place in the list)
    u8 jarCount, jarFly, jarFlying, jarFit; // the list's length; the piece's flight: its frame, on; a fit (else it comes back)
    u8 jarGuide, jarFlash, jarColours, jarPulse;    // the guide and the crosshair shown; the jar white; (its colours); the pulse's frame
    u8 jarFragShown, jarSpriteShown, jarDone, jarCircle;    // (the fragment in VRAM); its sprite shown; the leave's kind; in the circle
    u8 jarList[9], jarPlaced[9];
    s16 jarAngle[9];                        // each fragment's angle (degrees)
    s16 jarShown, jarShown0, jarShown1;     // the picked one's as shown (degrees x 16), a turn's
    s16 jarYaw, jarYaw0, jarYaw1;           // the jar's turn about y (degrees x 16)
    s32 jarTy, jarTz, jarTy0, jarTz0, jarTy1, jarTz1;   // its place (1.19.12)
    s16 jarSprX, jarSprY, jarSprX0, jarSprY0, jarSprX1, jarSprY1;   // the fragment's sprite's middle (pixels)
    u8 jarSub, jarCached, jarKeep, jarSaveAt;   // an animation's step (paced by the pictures); the jar kept for the flight: saved, still in the picture beyond its box, saved after this item
    u8 jarFlyDrawn, jarSaveRow, cacheBox[4];    // (the flight's frame drawn; the save's next row; the kept box)
    u8 keypad, keypadSpare[3];              // the safe's keypad up (en_keypad.c: the viewer's screen and script kept, its own frames)
    // the Blue Badger's angle: up, the angle presented right; the roll (degrees), the drums' turns (0-10)
    u8 badger, badgerRight, badgerSpare[2];
    s16 badgerRoll, badgerDrumH, badgerDrumV, badgerSpare2;
    s32 bm[9];                              // the jar's turn as the DS keeps it (row vectors: v' = v M), 1.14
    u32 badgerVBlank;                       // (the vertical blanks counted when its keys were last read)
};
// in the old script heap's free space (+0x9000-0xF000: after the menu's,
// before the movie's), the picture and its depth in the background's buffer
// (its picture decompressed again as the viewer leaves)
#define HEAP (EWRAM_START + 0x11FC0)
#define gEn3d (*(struct En3d *)(HEAP + 0x9000))
#define sFrame ((u8 *)gEnMovieCode + 0xC00)              // the renderer's own (280 bytes, after its code in IWRAM)
#define sObjPalBackup ((u16 *)(HEAP + 0x9800))          // 0x200
#define sBgPalBackup ((u16 *)(HEAP + 0x9A00))           // 0x200
#define sMapBackup ((u16 *)(HEAP + 0x9C00))             // BG3's map, 0x800
#define sObjBackup ((u8 *)(HEAP + 0xA400))              // OBJ tiles 0x1A0-0x2BF (the record's, the plate's): 0x2400
#define sJarCache ((u8 *)(HEAP + 0x10000))              // the jar as a piece flies: the kept box's tiles, then its depth (the movies' buffer, the fingerprints': free while the puzzle is up), up to 0x9600
#define sVerts ((s32 *)(HEAP + 0xC800))                 // 12 bytes a vertex: 0x1950
#define sCorners ((s16 *)(HEAP + 0xE200))               // a quad's corners
#define sCornersOut ((s32 *)(HEAP + 0xE240))
#define OBJ_BACKUP_TILES (0x2C0 - TILE_BASE)
#define sFb ((u8 *)(EWRAM_START + 0x2CFC0))             // 24 x 16 tiles, 8bpp (0: the grid under it)
#define sZb ((u16 *)(EWRAM_START + 0x2CFC0 + 0x6000))   // 192 x 128
#define MAX_VERTS 540
typedef char sEn3dFits[sizeof(struct En3d) <= 0x7FC ? 1 : -1];   // (before the backups; gEnVBlanks after)
// the grid (BG2, under BG3: its tiles and map where nothing else is while
// the viewer is up, its colour in BG palette 14)
#define GRID_CHAR 3
#define GRID_SCREEN 27
#define GRID_PAL 14
#define FB_ROW (24 * 64)

#define D(off) (gEn3dData + (off))
static const u32 * R31(void) { return (const u32 *)D(EN3D_R31); }

void UpdateItemPlate(struct Main *);
static void KeypadProcess(struct Main * main);
static void BadgerMatrix(void);
static void BadgerMask(void);
static void BadgerScreen(void);
static void BadgerSetup(void);
static void BadgerFrame(void);
static void DrawBadgerSprites(void);
static void BadgerGone(struct Main * main);

// ---------------------------------------------------------------- state
bool32 En3dActive(void)
{
    return gEn3d.mode != V_OFF;
}

void En3dReset(void)
{
    gEn3d.mode = V_OFF;
    gEn3d.jar = 0;
    gEn3d.keypad = 0;
    gEn3d.badger = 0;
    gEn3d.scene = 0;
    gEn3d.sceneEnding = FALSE;
    gEn3d.afterSection = 0;
}

static void SetMode(u32 mode)
{
    gEn3d.mode = mode;
    gEn3d.phase = 0;
    gEn3d.timer = 0;
    gEn3d.jarSub = 0;
}

static const struct En3dRecord * Record(void)
{
    return &sEn3dRecords[gEn3d.record];
}

static const struct En3dScene * Scene(void)
{
    return gEn3d.scene ? &sEn3dScenes[gEn3d.scene - 1] : NULL;
}

// the evidence the Court Record's L checks
bool32 En3dCheckable(struct CourtRecord * courtRecord)
{
    u32 ev;
    if (courtRecord->flags & COURT_RECORD_VIEW_PROFILES || !courtRecord->displayItemCount)
        return FALSE;
    ev = courtRecord->displayItemList[courtRecord->selectedItem];
    return ev < ARRAY_COUNT(sEn3dEvidence) && sEn3dEvidence[ev] != 0 && gMain.scenarioIdx >= RFTA_FIRST_CHAPTER;
}

// the record held open (no B) while a scene waits for its evidence
bool32 En3dHoldsRecord(void)
{
    return gEn3d.scene != 0;
}

// the portrait plate shown over the viewer (as the DS's face box)
bool32 En3dShowsPlate(void)
{
    return gEn3d.mode >= V_FIRST && gEn3d.mode <= V_SCRIPT && !gEn3d.jar && !gEn3d.keypad && !gEn3d.badger;
}

// ---------------------------------------------------------------- maths
static void QMul(s16 * out, const s16 * a, const s16 * b)
{
    s32 w = a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3];
    s32 x = a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2];
    s32 y = a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1];
    s32 z = a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0];
    out[0] = w >> 14; out[1] = x >> 14; out[2] = y >> 14; out[3] = z >> 14;
}

static u32 ISqrt(u32 v)
{
    u32 r = 0, bit = 1 << 30;
    while (bit > v)
        bit >>= 2;
    while (bit)
    {
        if (v >= r + bit)
        {
            v -= r + bit;
            r = (r >> 1) + bit;
        }
        else
            r >>= 1;
        bit >>= 2;
    }
    return r;
}

static void QNormalize(s16 * q)
{
    s32 n = q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3];
    s32 len = ISqrt(n), k;
    if (len == 0)
    {
        q[0] = 1 << 14; q[1] = q[2] = q[3] = 0;
        return;
    }
    for (k = 0; k < 4; k++)
        q[k] = (q[k] << 14) / len;
}

// the rotation (column vectors, 1.14) of q
static void Matrix(s32 * m, const s16 * q)
{
    s32 w = q[0], x = q[1], y = q[2], z = q[3];
    m[0] = 16384 - ((y * y + z * z) >> 13); m[1] = (x * y - w * z) >> 13; m[2] = (x * z + w * y) >> 13;
    m[3] = (x * y + w * z) >> 13; m[4] = 16384 - ((x * x + z * z) >> 13); m[5] = (y * z - w * x) >> 13;
    m[6] = (x * z - w * y) >> 13; m[7] = (y * z + w * x) >> 13; m[8] = 16384 - ((x * x + y * y) >> 13);
}

// a mod n, 0 to n - 1 (the library's % is not linked)
static s32 Wrap(s32 a, s32 n)
{
    a -= (a / n) * n;
    return a < 0 ? a + n : a;
}

// sine and cosine of a (degrees x 16), 1.14
static s32 Sin16(s32 a)
{
    s32 sign = 1, i, f, s;
    a = Wrap(a, 360 * 16);
    if (a >= 180 * 16)
    {
        a -= 180 * 16;
        sign = -1;
    }
    if (a > 90 * 16)
        a = 180 * 16 - a;
    i = a >> 4;
    f = a & 15;
    s = sEn3dSin[i];
    if (f)
        s += ((sEn3dSin[i + 1] - s) * f) >> 4;
    return sign * s;
}

static s32 Cos16(s32 a)
{
    return Sin16(a + 90 * 16);
}

s32 EnSin16(s32 a)
{
    return Sin16(a);
}

static void SetXf(struct En3dXf * xf, const s32 * m, const s32 * t)
{
    u32 k;
    for (k = 0; k < 3; k++)
    {
        xf->cx[k] = m[k]; xf->cy[k] = m[3 + k]; xf->cz[k] = m[6 + k];
    }
    xf->cx[3] = t[0]; xf->cy[3] = t[1]; xf->cz[3] = t[2];
    xf->r31 = R31();
    // the projection: the viewer's (the DS's touch screen's), or the jar's
    // (its top screen's at 2/3, its middle at the shown columns' middle)
    if (gEn3d.jar)
    {
        xf->fx = EN3D_JAR_FX; xf->fy = EN3D_JAR_FY; xf->ox = EN3D_JAR_OX; xf->oy = EN3D_JAR_OY;
    }
    else if (gEn3d.badger)
    {
        // (the DS's 128 x 128 viewport: the frame buffer's first 16 x 16 tiles)
        xf->fx = xf->fy = EN3D_BADGER_F; xf->ox = xf->oy = 64 * 16;
    }
    else
    {
        xf->fx = EN3D_FX; xf->fy = EN3D_FY; xf->ox = EN3D_VIEW_W / 2 * 16; xf->oy = EN3D_VIEW_H / 2 * 16;
    }
}

// the model turned in the view: about the screen's y (right) or x (down)
static void TurnBy(u32 axis, s32 sign)
{
    struct En3d * v = &gEn3d;
    s16 d[4], out[4];
    d[0] = TURN_STEP_COS; d[1] = d[2] = d[3] = 0;
    d[axis] = sign * TURN_STEP_SIN;
    QMul(out, d, v->q);
    QNormalize(out);
    v->q[0] = out[0]; v->q[1] = out[1]; v->q[2] = out[2]; v->q[3] = out[3];
    v->dirty = TRUE;
}

// ---------------------------------------------------------------- the meshes
static const u8 * MeshHead(u32 mesh)
{
    return D(sEn3dMeshes[mesh].head);
}

static u32 MeshVerts(u32 mesh)
{
    return ((const u16 *)MeshHead(mesh))[0];
}

static u32 MeshParts(u32 mesh)
{
    return ((const u16 *)MeshHead(mesh))[2];
}

static const u16 * MeshPart(u32 mesh, u32 k)
{
    return (const u16 *)(MeshHead(mesh) + 8) + 3 * k;
}

static const s16 * MeshVertices(u32 mesh)
{
    return (const s16 *)(MeshHead(mesh) + ((8 + 6 * MeshParts(mesh) + 3) & ~3));
}

static u32 ShownIndex(void)
{
    struct En3d * v = &gEn3d;
    if (v->mode == V_ANIM && v->animStep < sEn3dIds[v->pendingId].nanim)
        return sEn3dIds[v->pendingId].anim[v->animStep];
    return v->record;
}

// the textures' colours, each in its slot (the order the meshes name them)
static u32 TextureSlot(const struct En3dRecord * r, u32 tex)
{
    u32 k, p, slots = 0;
    u16 seen[5];
    for (k = 0; k < 3 && r->meshes[k] != 0xFF; k++)
        for (p = 0; p < MeshParts(r->meshes[k]); p++)
        {
            u32 t = MeshPart(r->meshes[k], p)[2], s;
            for (s = 0; s < slots; s++)
                if (seen[s] == t)
                    break;
            if (s == slots && slots < 5)
                seen[slots++] = t;
            if (t == tex)
                return s;
        }
    return 0;
}

static void LoadColours(const struct En3dRecord * r)
{
    u32 k, p;
    for (k = 0; k < 3 && r->meshes[k] != 0xFF; k++)
        for (p = 0; p < MeshParts(r->meshes[k]); p++)
        {
            u32 t = MeshPart(r->meshes[k], p)[2];
            DmaCopy16(3, sEn3dTextures[t].pal, BG_PLTT + (EN3D_PAL_TEXTURES + 16 * TextureSlot(r, t)) * 2, 32);
        }
}

// the jar's textures, each in its slot (sEn3dJarTextures' order)
static u32 JarSlot(u32 tex)
{
    u32 s;
    for (s = 0; s < EN3D_JAR_TEXTURES; s++)
        if (sEn3dJarTextures[s] == tex)
            return s;
    return 0;
}

// (white: the DS's flash as a piece fits)
static void JarColours(bool32 white)
{
    u32 s;
    for (s = 0; s < EN3D_JAR_TEXTURES; s++)
    {
        if (white)
        {
            DmaFill16(3, 0x7FFF, BG_PLTT + (EN3D_PAL_TEXTURES + 16 * s) * 2, 32);
        }
        else
        {
            DmaCopy16(3, sEn3dTextures[sEn3dJarTextures[s]].pal, BG_PLTT + (EN3D_PAL_TEXTURES + 16 * s) * 2, 32);
        }
    }
}

// ---------------------------------------------------------------- drawing
static u32 Lines(void)
{
    return EnLinesSinceVBlank();
}

static u32 Limit(void)
{
    s32 l = EN_BG_FRAME_END - gEnSoundLines - 6;
    return l < 20 ? 20 : l;
}

static bool32 TimeLeft(u32 need)
{
    u32 now = Lines();
    return now < 160 + 68 - 4 && now + need < Limit();
}

// the picture's tiles back to the grid (the box drawn last) and its depth to 0
static bool32 ClearRows(bool32 budget)
{
    struct En3d * v = &gEn3d;
    u32 ty, y;
    if (v->drawnBox[2] <= v->drawnBox[0])
        return TRUE;
    for (ty = v->drawnBox[1]; ty < v->drawnBox[3]; ty++)
    {
        if (budget && !TimeLeft(4))
        {
            v->drawnBox[1] = ty;
            return FALSE;
        }
        DmaFill32(3, 0, sFb + 64 * (ty * 24 + v->drawnBox[0]), (v->drawnBox[2] - v->drawnBox[0]) * 64);
        for (y = ty * 8; y < ty * 8 + 8; y++)
            DmaFill32(3, 0, sZb + y * EN3D_VIEW_W + v->drawnBox[0] * 8, (v->drawnBox[2] - v->drawnBox[0]) * 16);
    }
    v->drawnBox[2] = v->drawnBox[0];
    return TRUE;
}

static void ClearAll(void)
{
    struct En3d * v = &gEn3d;
    v->drawnBox[0] = 0; v->drawnBox[1] = 0; v->drawnBox[2] = 24; v->drawnBox[3] = 16;
    ClearRows(FALSE);
}

// the jar kept as a piece flies: the kept box's tiles (row by row) and its
// depth (row by row) in sJarCache
static u16 * JarCacheDepth(void)
{
    struct En3d * v = &gEn3d;
    return (u16 *)(sJarCache + (v->cacheBox[2] - v->cacheBox[0]) * (v->cacheBox[3] - v->cacheBox[1]) * 64);
}

static bool32 JarSave(void)
{
    struct En3d * v = &gEn3d;
    const u8 * c = v->cacheBox;
    u32 w = c[2] - c[0], ty, y;
    u16 * zc = JarCacheDepth();
    for (ty = c[1] + v->jarSaveRow; ty < c[3]; ty++)
    {
        if (!TimeLeft(4))
        {
            v->jarSaveRow = ty - c[1];
            return FALSE;
        }
        DmaCopy32(3, sFb + 64 * (ty * 24 + c[0]), sJarCache + 64 * w * (ty - c[1]), w * 64);
        for (y = ty * 8; y < ty * 8 + 8; y++)
            DmaCopy32(3, sZb + y * EN3D_VIEW_W + c[0] * 8, zc + (y - c[1] * 8) * w * 8, w * 16);
    }
    return TRUE;
}

// the last picture's box put back as the jar was kept (the piece's last
// place gone; within the kept box, which holds the piece's whole flight)
static bool32 JarRestore(void)
{
    struct En3d * v = &gEn3d;
    const u8 * c = v->cacheBox;
    u8 * b = v->drawnBox;
    u32 w = c[2] - c[0], ty, y, x0, x1;
    u16 * zc = JarCacheDepth();
    if (b[0] < c[0]) b[0] = c[0];
    if (b[1] < c[1]) b[1] = c[1];
    if (b[2] > c[2]) b[2] = c[2];
    if (b[3] > c[3]) b[3] = c[3];
    if (b[2] <= b[0] || b[3] <= b[1])
    {
        b[2] = b[0];
        return TRUE;
    }
    x0 = b[0];
    x1 = b[2];
    for (ty = b[1]; ty < b[3]; ty++)
    {
        if (!TimeLeft(4))
        {
            b[1] = ty;
            return FALSE;
        }
        DmaCopy32(3, sJarCache + 64 * (w * (ty - c[1]) + x0 - c[0]), sFb + 64 * (ty * 24 + x0), (x1 - x0) * 64);
        for (y = ty * 8; y < ty * 8 + 8; y++)
            DmaCopy32(3, zc + (y - c[1] * 8) * w * 8 + (x0 - c[0]) * 8, sZb + y * EN3D_VIEW_W + x0 * 8, (x1 - x0) * 16);
    }
    b[2] = b[0];
    return TRUE;
}

// the box to clear after a flight: the last one's and the kept jar's
static void JarKeptBox(void)
{
    struct En3d * v = &gEn3d;
    u8 * b = v->drawnBox;
    const u8 * c = v->cacheBox;
    if (b[2] <= b[0] || b[3] <= b[1])
    {
        b[0] = c[0]; b[1] = c[1]; b[2] = c[2]; b[3] = c[3];
        return;
    }
    if (c[0] < b[0]) b[0] = c[0];
    if (c[1] < b[1]) b[1] = c[1];
    if (c[2] > b[2]) b[2] = c[2];
    if (c[3] > b[3]) b[3] = c[3];
}

// the jar as the DS draws it: the base and the pieces in place (the step's
// records) turned about y and moved up and forward (the DS's row vectors:
// x' = x c + z s, z' = z c - x s), and the piece in its flight
static void JarPicture(void)
{
    struct En3d * v = &gEn3d;
    s32 c = Cos16(v->jarYaw), s = Sin16(v->jarYaw);
    u32 k, n = 0;
    v->rm[0] = c; v->rm[1] = 0; v->rm[2] = s;
    v->rm[3] = 0; v->rm[4] = 1 << 14; v->rm[5] = 0;
    v->rm[6] = -s; v->rm[7] = 0; v->rm[8] = c;
    v->rt[0] = 0; v->rt[1] = v->jarTy; v->rt[2] = v->jarTz;
    // (as a piece flies, the jar is drawn once and kept: then the piece alone)
    if (!(v->jarFlying && v->jarCached))
        for (k = 0; k <= v->jarStep; k++, n++)
        {
            v->itemMesh[n] = sEn3dJarMeshes[k];
            v->itemXf[n] = 0;
        }
    v->jarSaveAt = 0xFF;
    if (v->jarFlying)
    {
        if (!v->jarCached)
        {
            const u8 * b = sEn3dJarSteps[v->jarStep].cache;
            v->jarSaveAt = n;
            v->jarSaveRow = 0;
            v->cacheBox[0] = b[0]; v->cacheBox[1] = b[1]; v->cacheBox[2] = b[2]; v->cacheBox[3] = b[3];
        }
        v->jarFlyDrawn = v->jarFly;
        for (k = 0; k < 9; k++)
            v->rm2[k] = v->rm[k];
        v->rt2[0] = 0;
        v->rt2[1] = v->jarTy + sEn3dJarFlight[v->jarFly][0];
        v->rt2[2] = v->jarTz + sEn3dJarFlight[v->jarFly][1];
        v->itemMesh[n] = sEn3dJarMeshes[v->jarStep + 1];
        v->itemXf[n] = 1;
        n++;
    }
    v->nitems = n;
    v->interleave = TRUE;
    v->guideDrawn = v->jarGuide;
}

static void StartPicture(void)
{
    struct En3d * v = &gEn3d;
    v->dirty = FALSE;
    if (v->jar)
        JarPicture();
    else
    {
        const struct En3dRecord * r;
        u32 k;
        if (v->badger)
            BadgerMatrix();
        else
        {
            Matrix(v->rm, v->q);
            v->rt[0] = v->t[0]; v->rt[1] = v->t[1]; v->rt[2] = v->t[2];
        }
        v->drawRec = ShownIndex();
        r = &sEn3dRecords[v->drawRec];
        for (k = 0; k < 3 && r->meshes[k] != 0xFF; k++)
        {
            v->itemMesh[k] = r->meshes[k];
            v->itemXf[k] = 0;
        }
        v->nitems = k;
        v->interleave = FALSE;
    }
    v->render = R_CLEAR;
    v->mesh = 0;
    v->part = 0;
    v->maxW = 0;
    v->box[0] = 24; v->box[1] = 16; v->box[2] = 0; v->box[3] = 0;
}

// the screen box of the vertices just transformed (in tiles, a pixel's margin)
static void Grow(const s32 * xv, u32 count)
{
    struct En3d * v = &gEn3d;
    s32 x0 = 0x7FFF, y0 = 0x7FFF, x1 = -0x7FFF, y1 = -0x7FFF;
    u32 k;
    for (k = 0; k < count; k++, xv += 3)
    {
        if (xv[2] == 0)
            continue;
        if (xv[0] < x0) x0 = xv[0];
        if (xv[0] > x1) x1 = xv[0];
        if (xv[1] < y0) y0 = xv[1];
        if (xv[1] > y1) y1 = xv[1];
    }
    if (x1 < x0)
        return;
    x0 = (x0 >> 4) - 1; x1 = (x1 >> 4) + 2; y0 = (y0 >> 4) - 1; y1 = (y1 >> 4) + 2;
    x0 = x0 < 0 ? 0 : x0 >> 3; y0 = y0 < 0 ? 0 : y0 >> 3;
    x1 = x1 <= 0 ? 0 : (x1 + 7) >> 3; y1 = y1 <= 0 ? 0 : (y1 + 7) >> 3;
    if (x1 > 24) x1 = 24;
    if (y1 > 16) y1 = 16;
    if (x0 >= x1 || y0 >= y1)
        return;
    if (x0 < v->box[0]) v->box[0] = x0;
    if (y0 < v->box[1]) v->box[1] = y0;
    if (x1 > v->box[2]) v->box[2] = x1;
    if (y1 > v->box[3]) v->box[3] = y1;
}

static u32 ZShift(u32 maxW)
{
    u32 zs = 1;
    while (((maxW << 12) >> zs) >= 0x10000)
        zs++;
    return zs;
}

// the picture whole: up when the next vertical blank comes (the rows of the
// old picture and the new); the jar's guide (the red where the next piece
// goes) put in it first
static void PictureDone(void)
{
    struct En3d * v = &gEn3d;
    u32 y0, y1;
    if (v->jar && v->guideDrawn && v->jarStep < EN3D_JAR_STEPS)
    {
        const struct En3dJarStep * st = &sEn3dJarSteps[v->jarStep];
        const u16 * o = &sEn3dJarGuides[st->guide];
        u32 k;
        for (k = 0; k < st->nguide; k++)
            sFb[o[k]] = EN3D_JAR_GUIDE_INDEX;
        if (st->nguide)
        {
            if (st->box[0] < v->box[0]) v->box[0] = st->box[0];
            if (st->box[1] < v->box[1]) v->box[1] = st->box[1];
            if (st->box[2] > v->box[2]) v->box[2] = st->box[2];
            if (st->box[3] > v->box[3]) v->box[3] = st->box[3];
        }
    }
    if (v->badger)
        BadgerMask();
    y0 = v->box[1]; y1 = v->box[3];
    if (v->drawnBox[3] > v->drawnBox[1] || v->uploadAll)
    {
        if (v->drawnBox[1] < y0 || y1 <= y0) y0 = v->drawnBox[1];
        if (v->drawnBox[3] > y1) y1 = v->drawnBox[3];
    }
    if (v->uploadAll)
    {
        y0 = 0; y1 = 16;
        v->uploadAll = FALSE;
    }
    v->upload0 = y0;
    v->upload1 = y1;
    v->drawnBox[0] = v->box[0]; v->drawnBox[1] = v->box[1];
    v->drawnBox[2] = v->box[2]; v->drawnBox[3] = v->box[3];
    v->uploadReady = y1 > y0;
    v->coloursRec = v->jar ? 0xFF : v->drawRec;       // (the jar's are its own: JarVBlank)
    v->render = R_IDLE;
}

// item k's vertices: transformed into sVerts (after the earlier items' when
// they are all done first; the jar's one at a time, each then drawn)
static void TransformItem(u32 k, u32 off)
{
    struct En3d * v = &gEn3d;
    u32 mesh = v->itemMesh[k];
    v->vertsOf[v->interleave ? 0 : k] = off;
    if (v->itemXf[k])
        SetXf(&v->xf, v->rm2, v->rt2);
    else
        SetXf(&v->xf, v->rm, v->rt);
    v->xf.verts = MeshVertices(mesh);
    v->xf.count = MeshVerts(mesh);
    v->xf.out = sVerts + 3 * off;
    Transform(&v->xf);
    if (v->xf.maxW > v->maxW)
        v->maxW = v->xf.maxW;
    Grow(v->xf.out, v->xf.count);
}

// the picture, as far as the frame's time goes
static void RenderWork(void)
{
    struct En3d * v = &gEn3d;
    for (;;)
    {
        switch (v->render)
        {
        case R_IDLE:
            if (!v->dirty || v->uploadReady)
                return;
            StartPicture();
            break;
        case R_CLEAR:
            if (v->jar && v->jarFlying && v->jarCached)
            {
                if (!JarRestore())
                    return;
            }
            else
            {
                if (v->jarKeep)
                {
                    // (the jar kept for a flight is in the picture beyond its last box)
                    JarKeptBox();
                    v->jarKeep = FALSE;
                }
                if (!ClearRows(TRUE))
                    return;
            }
            v->render = R_XFORM;
            break;
        case R_XFORM:
        {
            u32 off = 0, k;
            if (v->interleave)
            {
                // the jar: an item, then its parts
                if (v->mesh >= v->nitems)
                {
                    PictureDone();
                    return;
                }
                if (v->mesh == v->jarSaveAt)
                {
                    // the jar whole: kept for the piece's flight
                    if (!JarSave())
                        return;
                    v->jarSaveAt = 0xFF;
                    v->jarCached = v->jarKeep = TRUE;
                }
                if (!TimeLeft(24))
                    return;
                TransformItem(v->mesh, 0);
                v->zshift = EN3D_JAR_ZSHIFT;
                v->part = 0;
                v->draw.resume = 0;
                v->render = R_DRAW;
                break;
            }
            if (v->mesh >= v->nitems)
            {
                v->zshift = ZShift(v->maxW);
                v->mesh = 0;
                v->part = 0;
                v->draw.resume = 0;
                v->render = R_DRAW;
                break;
            }
            if (!TimeLeft(24))
                return;
            for (k = 0; k < v->mesh; k++)
                off += MeshVerts(v->itemMesh[k]);
            TransformItem(v->mesh, off);
            v->mesh++;
            break;
        }
        case R_DRAW:
        {
            struct En3dDraw * d = &v->draw;
            u32 mesh;
            if (v->mesh >= v->nitems)
            {
                PictureDone();
                return;
            }
            mesh = v->itemMesh[v->mesh];
            if (v->part >= MeshParts(mesh))
            {
                v->mesh++;
                v->part = 0;
                if (v->interleave)
                    v->render = R_XFORM;
                break;
            }
            if (!TimeLeft(6))
                return;
            if (d->resume == 0)
            {
                const u16 * p = MeshPart(mesh, v->part);
                const struct En3dTexture * t = &sEn3dTextures[p[2]];
                d->tris = D(sEn3dMeshes[mesh].tris) + 18 * p[0];
                d->count = p[1];
                d->xv = sVerts + 3 * v->vertsOf[v->interleave ? 0 : v->mesh];
                d->tex = D(t->off);
                d->wlog = t->wlog;
                d->hlog = t->hlog;
                d->pal = EN3D_PAL_TEXTURES + 16 * (v->jar ? JarSlot(p[2]) : TextureSlot(&sEn3dRecords[v->drawRec], p[2]));
                d->zshift = v->zshift;
                d->fb = sFb;
                d->zb = sZb;
                d->r31 = R31();
                d->frame = sFrame;
            }
            d->limit = Limit();
            if (DrawPart(d) == 0)
            {
                v->part++;
                d->resume = 0;
            }
            else
                return;
            break;
        }
        default:
            return;
        }
    }
}

// the jar's fragment the circle shows (0xFF: none left)
static u32 JarPiece(void)
{
    struct En3d * v = &gEn3d;
    return v->jarSel < v->jarCount && !v->jarPlaced[v->jarSel] ? v->jarList[v->jarSel] : 0xFF;
}

// the jar's in the vertical blank: the pulse's colours (the guide's red,
// the crosshair's), the white of the flash, the fragment shown
static void JarVBlank(void)
{
    struct En3d * v = &gEn3d;
    u32 p = sEn3dJarPulse[v->jarPulse / EN3D_JAR_PULSE_FRAMES], piece = JarPiece();
    ((u16 *)BG_PLTT)[EN3D_JAR_GUIDE_INDEX] = sEn3dJarGuideRed[p];
    DmaCopy16(3, sEn3dJarCrossPal[p], OBJ_PLTT + PAL_CROSS * 32, 32);
    if (v->jarColours != v->jarFlash)
    {
        JarColours(v->jarFlash);
        v->jarColours = v->jarFlash;
    }
    if (piece != 0xFF && piece != v->jarFragShown)
    {
        DmaCopy32(3, D(EN3D_JAR_GFX_FRAGMENTS) + 2048 * piece, OBJ_VRAM0 + (TILE_BASE + JAR_TILE_FRAGMENT) * 32, 2048);
        DmaCopy16(3, sEn3dJarFragmentPal[piece], OBJ_PLTT + PAL_FRAGMENT * 32, 32);
        v->jarFragShown = piece;
    }
}

// the vertical blank's: the picture (its rows) or the close-up to VRAM
void En3dVBlank(void)
{
    struct En3d * v = &gEn3d;
    if (v->keypad)
    {
        if (v->mode == V_VIEW)
            EnKeypadVBlank();
        return;
    }
    if (v->mode < V_FIRST || v->mode == V_LEAVE || v->mode == V_SHOW_RECORD)
        return;
    if (v->jar)
        JarVBlank();
    if (v->coloursRec != 0xFF && (v->uploadReady || v->closeup != v->closeupShown))
    {
        LoadColours(&sEn3dRecords[v->coloursRec]);
        v->coloursRec = 0xFF;
    }
    if (v->closeup != v->closeupShown)
    {
        if (v->closeup)
        {
            const struct En3dCloseup * c = &sEn3dCloseups[v->closeup - 1];
            DmaCopy16(3, c->pal, BG_PLTT + EN3D_PAL_CLOSEUP * 2, 32);
            DmaCopy32(3, D(c->off), BG_CHAR_ADDR(1), EN3D_VIEW_TILES * 64);
        }
        else
            DmaCopy32(3, sFb, BG_CHAR_ADDR(1), EN3D_VIEW_TILES * 64);
        v->closeupShown = v->closeup;
        v->uploadReady = FALSE;
        return;
    }
    if (v->uploadReady && !v->closeup)
    {
        DmaCopy32(3, sFb + v->upload0 * FB_ROW, BG_CHAR_ADDR(1) + v->upload0 * FB_ROW, (v->upload1 - v->upload0) * FB_ROW);
        v->uploadReady = FALSE;
    }
    else if (v->uploadReady)
        v->uploadReady = FALSE;
}

// ---------------------------------------------------------------- hit test
static bool32 InTriangle(s32 px, s32 py, const s32 * a, const s32 * b, const s32 * c)
{
    s32 d1 = ((b[0] - a[0]) >> 2) * ((py - a[1]) >> 2) - ((b[1] - a[1]) >> 2) * ((px - a[0]) >> 2);
    s32 d2 = ((c[0] - b[0]) >> 2) * ((py - b[1]) >> 2) - ((c[1] - b[1]) >> 2) * ((px - b[0]) >> 2);
    s32 d3 = ((a[0] - c[0]) >> 2) * ((py - c[1]) >> 2) - ((a[1] - c[1]) >> 2) * ((px - c[0]) >> 2);
    bool32 neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
    return !(neg && pos);
}

static bool32 InQuad(const struct En3dQuad * q, s32 px, s32 py)
{
    struct En3d * v = &gEn3d;
    struct En3dXf xf;
    const s32 * o = sCornersOut;
    u32 k;
    for (k = 0; k < 12; k++)
        sCorners[k] = q->pts[k];
    SetXf(&xf, v->m, v->t);
    xf.verts = sCorners;
    xf.count = 4;
    xf.out = sCornersOut;
    Transform(&xf);
    for (k = 0; k < 4; k++)
        if (o[3 * k + 2] == 0)
            return FALSE;
    return InTriangle(px, py, o, o + 3, o + 6) || InTriangle(px, py, o, o + 6, o + 9);
}

// the facing: the normal's z turned (toward the camera)
static s32 Facing(const struct En3dQuad * q)
{
    const s32 * m = gEn3d.m;
    return (m[6] * q->n[0] + m[7] * q->n[1] + m[8] * q->n[2]) >> 14;
}

// the id under the point (0: none): a facing blocker over it hides all
static u32 HitTest(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dRecord * r = Record();
    s32 px = v->curX * 16 + 8, py = v->curY * 16 + 8;
    u32 k;
    Matrix(v->m, v->q);         // (the picture being drawn keeps its own)
    for (k = 0; k < r->nblock; k++)
    {
        const struct En3dQuad * q = &sEn3dQuads[r->first + r->nhot + k];
        if (Facing(q) > 0 && InQuad(q, px, py))
            return 0;
    }
    for (k = 0; k < r->nhot; k++)
    {
        const struct En3dQuad * q = &sEn3dQuads[r->first + k];
        if (Facing(q) >= 0 && InQuad(q, px, py))
            return q->id;
    }
    return 0;
}

// ---------------------------------------------------------------- sprites
#define sOam (gEn3d.oam)

static void SpriteOf(const struct En3dPiece * p, s32 x, s32 y, u32 pal)
{
    for (;; p++)
    {
        struct OamAttrs * oam;
        if (sOam > OAM_LAST)
            return;
        oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0((y + p->dy) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, p->shape);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE((x + p->dx) & 0x1FF, FALSE, FALSE, p->size);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + p->tile, 2, pal);
        if (p->last)
            return;
    }
}

static void Sprite(u32 first, s32 x, s32 y)
{
    SpriteOf(&sEn3dPieces[first], x, y, PAL_UI);
}

static void EndSprites(void)
{
    for (; sOam <= OAM_LAST; sOam++)
        gOamObjects[sOam].attr0 = SPRITE_ATTR0_CLEAR;
}

static void DrawSprites(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dScene * sc = Scene();
    u32 k;
    s32 cx = EN3D_VIEW_X + v->curX, cy = EN3D_VIEW_Y + v->curY;
    sOam = OAM_FIRST;
    if (v->mode == V_VIEW && !v->closeup)
    {
        for (k = 0; k < 6; k++)
            Sprite(EN3D_SPRITE_HLINE, EN3D_VIEW_X + 32 * k, cy);
        for (k = 0; k < 4; k++)
            Sprite(EN3D_SPRITE_VLINE, cx, EN3D_VIEW_Y + 32 * k);
        Sprite(EN3D_SPRITE_SQUARE, cx - 3, cy - 3);
        if (!(v->sceneHere && sc && !sc->back))
            Sprite(EN3D_SPRITE_BACK, 0, EN3D_TAB_Y);
        if (v->hit)
            Sprite(EN3D_SPRITE_EXAMINE, 240 - 72, EN3D_TAB_Y);
    }
    // the knob: zoomed out at the bottom of its track
    Sprite(EN3D_SPRITE_KNOB, 4, EN3D_ZOOM_BOTTOM - (v->zoom * (EN3D_ZOOM_BOTTOM - EN3D_ZOOM_TOP)) / ZOOM_MAX);
    EndSprites();
}

static void JarSprite(u32 first, s32 x, s32 y, u32 pal)
{
    SpriteOf(&sEn3dJarPieces[first], x, y, pal);
}

// the next fragment left in the list that way (-1: none)
static s32 JarNext(s32 dir)
{
    struct En3d * v = &gEn3d;
    s32 k;
    for (k = v->jarSel + dir; k >= 0 && k < v->jarCount; k += dir)
        if (!v->jarPlaced[k])
            return k;
    return -1;
}

// the jar's: the tabs, the fragment's number, the arrows and the red cross
// by the circle, the fragment (turned: affine, its colours its own) and the
// crosshair over where it goes (the cross over the circle and the
// crosshair in the pulse's colours)
static void DrawJarSprites(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dJarStep * st = &sEn3dJarSteps[v->jarStep];
    u32 piece = JarPiece(), k;
    struct OamAttrs * oam;
    s32 c, s;
    sOam = OAM_FIRST;
    JarSprite(EN3D_JAR_SPRITE_BACK, 0, EN3D_TAB_Y, PAL_UI);
    if (piece != 0xFF)
        JarSprite(EN3D_JAR_SPRITE_COMBINE, EN3D_JAR_COMBINE_X, EN3D_TAB_Y, PAL_UI);
    if (v->jarSpriteShown && piece != 0xFF)
        JarSprite(EN3D_JAR_SPRITE_DIGIT1 + v->jarSel, EN3D_JAR_DIGIT_X, EN3D_JAR_DIGIT_Y, PAL_UI);
    if (v->jarCircle && piece != 0xFF)
    {
        if (JarNext(-1) >= 0)
            JarSprite(EN3D_JAR_SPRITE_LEFT, EN3D_JAR_LEFT_X, EN3D_JAR_ARROW_Y, PAL_UI);
        if (JarNext(1) >= 0)
            JarSprite(EN3D_JAR_SPRITE_RIGHT, EN3D_JAR_RIGHT_X, EN3D_JAR_ARROW_Y, PAL_UI);
        for (k = 0; k < 2; k++)
        {
            JarSprite(EN3D_JAR_SPRITE_HLINE, EN3D_JAR_CIRCLE_X - EN3D_JAR_CROSS_R + 16 * k, EN3D_JAR_CIRCLE_Y, PAL_CROSS);
            JarSprite(EN3D_JAR_SPRITE_VLINE, EN3D_JAR_CIRCLE_X, EN3D_JAR_CIRCLE_Y - EN3D_JAR_CROSS_R + 16 * k, PAL_CROSS);
        }
    }
    if (v->jarSpriteShown && piece != 0xFF && sOam <= OAM_LAST)
    {
        // (double size: its middle 64 pixels in)
        oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0((v->jarSprY - 64) & 0xFF, ST_OAM_AFFINE_DOUBLE, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_AFFINE((v->jarSprX - 64) & 0x1FF, JAR_AFFINE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + JAR_TILE_FRAGMENT, 2, PAL_FRAGMENT);
        c = Cos16(v->jarShown) >> 6;
        s = Sin16(v->jarShown) >> 6;
        gOamObjects[JAR_AFFINE * 4 + 0].attr3 = c;
        gOamObjects[JAR_AFFINE * 4 + 1].attr3 = s;
        gOamObjects[JAR_AFFINE * 4 + 2].attr3 = -s;
        gOamObjects[JAR_AFFINE * 4 + 3].attr3 = c;
    }
    if (v->jarGuide && v->jarStep < v->jarEnd && sOam <= OAM_LAST)
    {
        oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0((st->crossY - 32) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE((st->crossX - 32) & 0x1FF, FALSE, FALSE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + JAR_TILE_CROSS, 2, PAL_CROSS);
    }
    EndSprites();
}

// ---------------------------------------------------------------- the screen
static void SaveScreen(void)
{
    struct Main * main = &gMain;
    struct En3d * v = &gEn3d;
    u32 i;
    DmaCopy16(3, &gMain, &gSaveDataBuffer.main, sizeof(gMain));
    DmaCopy16(3, &gIORegisters, &gSaveDataBuffer.ioRegs, sizeof(gIORegisters));
    DmaCopy16(3, &gScriptContext, &gSaveDataBuffer.scriptCtx, sizeof(gScriptContext));
    DmaCopy16(3, &gInvestigation, &gSaveDataBuffer.investigation, sizeof(gInvestigation));
    DmaCopy16(3, gMapMarker, gSaveDataBuffer.mapMarker, sizeof(gMapMarker));
    DmaCopy16(3, gOamObjects, gSaveDataBuffer.oam, sizeof(gOamObjects));
    DmaCopy16(3, gTextBoxCharacters, gSaveDataBuffer.textBoxCharacters, sizeof(gTextBoxCharacters));
    DmaCopy16(3, gBG0MapBuffer, gSaveDataBuffer.bg0Map, sizeof(gBG0MapBuffer));
    DmaCopy16(3, gBG1MapBuffer, gSaveDataBuffer.bg1Map, sizeof(gBG1MapBuffer));
    DmaCopy16(3, gBG3MapBuffer, sMapBackup, 0x800);
    DmaCopy16(3, OBJ_PLTT, sObjPalBackup, 0x200);
    DmaCopy16(3, BG_PLTT, sBgPalBackup, 0x200);
    DmaCopy32(3, OBJ_VRAM0 + TILE_BASE * 32, sObjBackup, OBJ_BACKUP_TILES * 32);
    VwfBackup();
    v->scriptBase = gScriptBase;
    for (i = 0; i < 8; i++)
        gMapMarker[i].id |= 0xFF;
    // what the record shows, away (the details' way)
    ClearEvidenceSprites(&gCourtRecord);
    UpdateRecordInfoActionSprites(0);
    UpdateRecordPresentActionSprites(0);
    for (i = 0; i < 128; i++)
        if (i < OAM_IDX_TEXT || i >= OAM_IDX_TEXT + OAM_COUNT_TEXT)
            gOamObjects[i].attr0 = SPRITE_ATTR0_CLEAR;
    main->showTextboxCharacters = FALSE;
    main->animationFlags &= ~(2 | 1);
    main->isBGScrolling = FALSE;
}

// the viewer's screen: BG3 the frame and the picture (256 colours), the
// rest off but the text box's (the jar's: its own frame, the picture in its
// left 144 columns, its sprites)
static void TakeScreen(void)
{
    struct IORegisters * io = &gIORegisters;
    struct En3d * v = &gEn3d;
    u32 r, c;
    const u16 * map = (const u16 *)D(v->jar ? EN3D_JAR_GFX_MAP : EN3D_GFX_MAP);
    s32 viewX = v->jar ? EN3D_JAR_VIEW_X : EN3D_VIEW_X, viewY = v->jar ? EN3D_JAR_VIEW_Y : EN3D_VIEW_Y;
    s32 viewW = v->jar ? EN3D_JAR_VIS_W : EN3D_VIEW_W;
    CpuCopy32(gEn3dCodeStart, gEnMovieCode, gEn3dCodeEnd - gEn3dCodeStart);
    if (v->badger)
    {
        BadgerScreen();
        return;
    }
    io->lcd_dispcnt &= ~(DISPCNT_BG0_ON | DISPCNT_BG1_ON);
    io->lcd_dispcnt |= DISPCNT_BG2_ON | DISPCNT_BG3_ON | DISPCNT_OBJ_ON;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(2) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_256COLOR;
    io->lcd_bg2hofs = 8;
    io->lcd_bg2vofs = 8;
    io->lcd_bg2cnt = BGCNT_PRIORITY(3) | BGCNT_CHARBASE(GRID_CHAR) | BGCNT_SCREENBASE(GRID_SCREEN) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_16COLOR;
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
        {
            s32 vx = c - 1 - viewX / 8, vy = r - 1 - viewY / 8;
            u16 t = (vx >= 0 && vx < viewW / 8 && vy >= 0 && vy < EN3D_VIEW_H / 8) ? ((vx & 1) | (vy & 1) << 1) : 0;
            ((u16 *)BG_SCREEN_ADDR(GRID_SCREEN))[r * 32 + c] = t | (GRID_PAL << 12);
        }
    DmaCopy16(3, D(EN3D_GFX_GRID), BG_CHAR_ADDR(GRID_CHAR), 4 * 32);
    ((u16 *)BG_PLTT)[GRID_PAL * 16 + 1] = EN3D_GRID_LINE;
    ((u16 *)BG_PLTT)[0] = EN3D_GRID_BG;
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
            gBG3MapBuffer[r * 32 + c] = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? map[(r - 1) * 30 + c - 1] : EN3D_VIEW_TILES;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    if (v->jar)
    {
        DmaCopy32(3, D(EN3D_JAR_GFX_FRAME), BG_CHAR_ADDR(1) + EN3D_VIEW_TILES * 64, EN3D_JAR_FRAME_TILES * 64);
        DmaCopy16(3, sEn3dJarFramePalette, BG_PLTT + EN3D_PAL_FRAME * 2, EN3D_JAR_FRAME_COLOURS * 2);
        DmaCopy16(3, D(EN3D_JAR_GFX_SPRITES), OBJ_VRAM0 + TILE_BASE * 32, EN3D_JAR_SPRITE_TILES * 32);
        DmaCopy16(3, D(EN3D_JAR_GFX_CROSS), OBJ_VRAM0 + (TILE_BASE + JAR_TILE_CROSS) * 32, 64 * 32);
        JarColours(FALSE);
    }
    else
    {
        DmaCopy32(3, D(EN3D_GFX_FRAME), BG_CHAR_ADDR(1) + EN3D_VIEW_TILES * 64, EN3D_FRAME_TILES * 64);
        DmaCopy16(3, sEn3dFramePalette, BG_PLTT + EN3D_PAL_FRAME * 2, EN3D_FRAME_COLOURS * 2);
        DmaCopy16(3, D(EN3D_GFX_SPRITES), OBJ_VRAM0 + TILE_BASE * 32, EN3D_SPRITE_TILES * 32);
    }
    DmaCopy16(3, sEn3dUiPalette, OBJ_PLTT + PAL_UI * 32, 32);
    ClearAll();
    DmaCopy32(3, sFb, BG_CHAR_ADDR(1), EN3D_VIEW_TILES * 64);
}

// everything as it was (the background decompressed again: the picture had
// its buffer), or on another background (the keypad's: the safe, the office)
static void ChangeBg(u32 bg)
{
    struct Main * main = &gMain;
    main->previousBG = main->currentBG;
    main->currentBG = bg;
    DecompressBackgroundIntoBuffer(bg);
    CopyBGDataToVram(bg);
}

static void GiveBackScreenOn(u32 bg)
{
    struct Main * main = &gMain;
    struct En3d * v = &gEn3d;
    u32 i;
    if (bg == main->currentBG)
    {
        DecompressBackgroundIntoBuffer(main->currentBG);
        CopyBGDataToVramAndScrollBG(main->currentBG);
    }
    DmaCopy16(3, sMapBackup, gBG3MapBuffer, 0x800);
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaCopy16(3, sBgPalBackup, BG_PLTT, 0x200);
    DmaCopy16(3, sObjPalBackup, OBJ_PLTT, 0x200);
    DmaCopy32(3, sObjBackup, OBJ_VRAM0 + TILE_BASE * 32, OBJ_BACKUP_TILES * 32);
    DmaCopy16(3, gSaveDataBuffer.bg0Map, gBG0MapBuffer, sizeof(gBG0MapBuffer));
    DmaCopy16(3, gSaveDataBuffer.bg1Map, gBG1MapBuffer, sizeof(gBG1MapBuffer));
    DmaCopy16(3, gSaveDataBuffer.textBoxCharacters, gTextBoxCharacters, sizeof(gTextBoxCharacters));
    VwfRestore();
    RedrawTextboxCharacters();
    gScriptBase = v->scriptBase;
    DmaCopy16(3, &gSaveDataBuffer.scriptCtx, &gScriptContext, sizeof(gScriptContext));
    DmaCopy16(3, &gSaveDataBuffer.ioRegs, &gIORegisters, sizeof(gIORegisters));
    DmaCopy16(3, &gSaveDataBuffer.investigation, &gInvestigation, sizeof(gInvestigation));
    DmaCopy16(3, gSaveDataBuffer.mapMarker, gMapMarker, sizeof(gMapMarker));
    DmaCopy16(3, gSaveDataBuffer.oam, gOamObjects, sizeof(gOamObjects));
    MakeMapMarkerSprites();
    main->advanceScriptContext = gSaveDataBuffer.main.advanceScriptContext;
    main->showTextboxCharacters = gSaveDataBuffer.main.showTextboxCharacters;
    main->animationFlags = gSaveDataBuffer.main.animationFlags;
    main->gameStateFlags = gSaveDataBuffer.main.gameStateFlags;
    main->shakeTimer = gSaveDataBuffer.main.shakeTimer;
    main->isBGScrolling = gSaveDataBuffer.main.isBGScrolling;
    main->tilemapUpdateBits = gSaveDataBuffer.main.tilemapUpdateBits | 0x3;
    main->itemPlateEvidenceId = gSaveDataBuffer.main.itemPlateEvidenceId;
    main->itemPlateState = gSaveDataBuffer.main.itemPlateState;
    main->itemPlateSide = gSaveDataBuffer.main.itemPlateSide;
    main->itemPlateRotation = gSaveDataBuffer.main.itemPlateRotation;
    main->itemPlateSize = gSaveDataBuffer.main.itemPlateSize;
    main->itemPlateCounter = gSaveDataBuffer.main.itemPlateCounter;
    main->itemPlateAction = gSaveDataBuffer.main.itemPlateAction;
    for (i = OAM_FIRST; i <= OAM_LAST; i++)
        if (gOamObjects[i].attr2 >= TILE_BASE && gOamObjects[i].attr2 < TILE_BASE + EN3D_SPRITE_TILES)
            gOamObjects[i].attr0 = SPRITE_ATTR0_CLEAR;
    if (bg != main->currentBG)
        ChangeBg(bg);       // (the room's registers back: the background's own after them)
}

static void GiveBackScreen(void)
{
    GiveBackScreenOn(gMain.currentBG);
}

// ---------------------------------------------------------------- the record
static void ShowRecord(u32 record)
{
    struct En3d * v = &gEn3d;
    v->record = record;
    v->dirty = TRUE;
}

static void ResetView(void)
{
    struct En3d * v = &gEn3d;
    v->q[0] = 1 << 14; v->q[1] = v->q[2] = v->q[3] = 0;
    v->t[0] = v->t[1] = v->t[2] = 0;
    v->zoom = 0;
    v->curX = EN3D_VIEW_W / 2;
    v->curY = EN3D_VIEW_H / 2;
    v->dirty = TRUE;
}

// L on evidence with a model (court_record.c)
void En3dOpenFromRecord(struct CourtRecord * courtRecord)
{
    struct En3d * v = &gEn3d;
    struct Main * main = &gMain;
    u32 ev = courtRecord->displayItemList[courtRecord->selectedItem];
    const struct En3dScene * sc;
    v->evidence = ev;
    v->record = sEn3dEvidence[ev] - 1;
    sc = Scene();
    v->sceneHere = sc && sc->ev == ev;
    v->hovered = FALSE;
    v->hit = 0;
    v->closeup = v->closeupShown = 0;
    v->after = AFTER_NONE;
    v->afterSection = 0;
    v->sceneEnding = FALSE;
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->coloursRec = 0xFF;
    v->file35 = FALSE;
    v->fromState = main->process[GAME_PROCESS_STATE];
    v->fromVar1 = main->process[GAME_PROCESS_VAR1];
    v->fromVar2 = main->process[GAME_PROCESS_VAR2];
    main->process[GAME_PROCESS_STATE] = RECORD_3D;
    main->process[GAME_PROCESS_VAR1] = 0;
    StartHardwareBlend(2, 1, 1, FADE_ALL);
    SetMode(V_FADE_OUT);
}

// ---------------------------------------------------------------- the jar puzzle
// The DS's 74 8 32 (script command 69 4<<8 | n: n 0 Day 2's, 1 Day 3's):
// the Unstable Jar's pieces put back together (jarpuzzle.py has what the
// DS does). The jar is drawn as the viewer draws its models, its view in
// the viewport's left 144 columns; the fragment picked is in the circle on
// the right: left and right pick, L and R turn it, A sends it to the jar
// (it fits, the next piece turned right, or comes back), B leaves. The
// DS's frames for each thing it does:
#define JAR_RISE_FRAMES 30          // the base up into its place
#define JAR_SPIN_FRAMES 60          // and once round
#define JAR_ROTATE_FRAMES 15        // a fragment turned by 90
#define JAR_SEND_FRAMES 15          // to the crosshair (then its flight, sEn3dJarFlight: as the
                                    // frames go, the jar drawn once and kept, the piece alone again)
#define JAR_MISS_SEND_FRAMES 12
#define JAR_MISS_HOVER_FRAMES 40
#define JAR_RETURN_FRAMES 20
#define JAR_FLASH_FRAMES 11         // the jar white as a piece fits
#define JAR_HOLD_FRAMES 60
#define JAR_TURN_FRAMES 30          // to the next step's view
#define JAR_END_FRAMES 60           // the jar done, before the fade
// The jar's own moves (the rise, the turn round, the turn to the next view)
// go a step a picture, at most the DS's pace: the whole jar takes the
// renderer several frames, and a turn shown in three pictures is no turn.
#define JAR_RISE_STEPS 6
#define JAR_SPIN_STEPS 15
#define JAR_TURN_STEPS 6

static s32 Lerp(s32 a, s32 b, u32 t, u32 n)
{
    return a + (b - a) * (s32)t / (s32)n;
}

// the picture asked for is whole
static bool32 PictureUp(void)
{
    return gEn3d.render == R_IDLE && !gEn3d.dirty;
}

// the next step of a move paced by the pictures (n steps, each at least
// `min` frames): TRUE as one starts (its picture asked for)
static bool32 JarStepOn(u32 n, u32 min)
{
    struct En3d * v = &gEn3d;
    if (v->jarSub >= n || v->timer < min || !PictureUp())
        return FALSE;
    v->jarSub++;
    v->timer = 0;
    v->dirty = TRUE;
    return TRUE;
}

static bool32 JarStepsDone(u32 n)
{
    return gEn3d.jarSub >= n && PictureUp();
}

// command 69 4<<8 | n: the screen faded out, then the puzzle's
static void JarStart(u32 variant)
{
    struct En3d * v = &gEn3d;
    v->jar = variant + 1;
    v->sceneHere = FALSE;
    v->hovered = FALSE;
    v->hit = 0;
    v->closeup = v->closeupShown = 0;
    v->after = AFTER_NONE;
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->coloursRec = 0xFF;
    v->file35 = FALSE;
    v->dirty = FALSE;
    BACKUP_PROCESS();
    SET_PROCESS(COURT_RECORD_PROCESS, RECORD_3D, 0, 0);
    StartHardwareBlend(2, 1, 1, FADE_ALL);
    SetMode(V_FADE_OUT);
}

// the fragments (Day 2: eight, in the DS's order; Day 3: the last alone,
// the jar whole but for it), each at a random quarter turn
static void JarSetup(void)
{
    struct En3d * v = &gEn3d;
    u32 k;
    if (v->jar == 1)
    {
        v->jarStep = 0;
        v->jarEnd = 8;
        v->jarCount = 8;
        for (k = 0; k < 8; k++)
            v->jarList[k] = sEn3dJarOrder[k];
    }
    else
    {
        v->jarStep = 8;
        v->jarEnd = 9;
        v->jarCount = 1;
        v->jarList[0] = 8;
    }
    for (k = 0; k < v->jarCount; k++)
    {
        v->jarPlaced[k] = FALSE;
        v->jarAngle[k] = (Wrap(Random(), 3) + 1) * 90;
    }
    v->jarSel = 0;
    v->jarYaw = sEn3dJarSteps[v->jarStep].yaw * 16;
    v->jarTy = v->jarTz = 0;                // (it rises into its place)
    v->jarShown = v->jarAngle[0] * 16;
    v->jarGuide = v->jarFlying = v->jarFlash = v->jarColours = FALSE;
    v->jarCached = v->jarKeep = FALSE;
    v->jarSaveAt = 0xFF;
    v->jarPulse = 0;
    v->jarFragShown = 0xFF;
    v->jarSpriteShown = v->jarCircle = TRUE;
    v->jarSprX = EN3D_JAR_CIRCLE_X;
    v->jarSprY = EN3D_JAR_CIRCLE_Y;
    v->dirty = TRUE;
}

// the player's turn: the guide and the crosshair over where the next piece
// goes, the fragment in the circle
static void JarPlay(void)
{
    struct En3d * v = &gEn3d;
    v->jarGuide = TRUE;
    if (PictureUp() && !v->uploadReady)
    {
        // (written into the picture as it is: no new one)
        v->guideDrawn = TRUE;
        v->box[0] = v->drawnBox[0]; v->box[1] = v->drawnBox[1];
        v->box[2] = v->drawnBox[2]; v->box[3] = v->drawnBox[3];
        PictureDone();
    }
    else
        v->dirty = TRUE;
    v->jarSpriteShown = v->jarCircle = JarPiece() != 0xFF;
    v->jarSprX = EN3D_JAR_CIRCLE_X;
    v->jarSprY = EN3D_JAR_CIRCLE_Y;
    SetMode(J_PLAY);
}

// to the step's view (the shorter way round)
static void JarTurn(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dJarStep * st = &sEn3dJarSteps[v->jarStep];
    s32 d;
    v->jarYaw0 = Wrap(v->jarYaw, 360 * 16);
    d = st->yaw * 16 - v->jarYaw0;
    if (d > 180 * 16)
        d -= 360 * 16;
    else if (d <= -180 * 16)
        d += 360 * 16;
    v->jarYaw1 = v->jarYaw0 + d;
    v->jarTy0 = v->jarTy;
    v->jarTz0 = v->jarTz;
    v->jarTy1 = st->ty;
    v->jarTz1 = st->tz;
    SetMode(J_TURN);
}

// the screen faded out (slowly when the jar is done), then away
static void JarLeave(bool32 done)
{
    struct En3d * v = &gEn3d;
    v->jarDone = done;
    v->jarGuide = FALSE;
    StartHardwareBlend(2, done ? 4 : 1, 1, FADE_ALL);
    SetMode(V_FADE_LEAVE);
}

// everything back, the room's background (or the jar's picture: as the
// script's 1B changes it) and the section the DS goes on in; faded in, but
// Day 2's done, whose section fades out first (the screen left near black
// so that its fade ends at once, as the DS's on a black screen)
static void JarGone(struct Main * main)
{
    struct En3d * v = &gEn3d;
    const u16 * e = sEn3dJarExits[v->jar - 1][v->jarDone];
    bool32 fadesOut = v->jar == 1 && v->jarDone;
    GiveBackScreen();
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->jar = 0;
    SetMode(V_OFF);
    RESTORE_PROCESS_PTR(main);
    // no one shown (the DS's sections after it bring the person in themselves)
    DestroyAnimation(&gAnimation[1]);
    gInvestigation.personActive = 0;
    SetInactiveActionButtons(&gInvestigation, 15);
    if (e[0] != main->currentBG)
    {
        main->previousBG = main->currentBG;
        main->currentBG = e[0];
        main->currentBgStripe = 1;
    }
    ChangeScriptSection(e[1]);
    if (fadesOut)
        gIORegisters.lcd_bldy = 0x10 - 1;
    else
        StartHardwareBlend(1, 1, 1, FADE_ALL);
}

static void JarInput(void)
{
    struct En3d * v = &gEn3d;
    u32 pressed = gJoypad.pressedKeys;
    s32 k;
    if (pressed & B_BUTTON)
    {
        PlaySE(SE002_MENU_CANCEL);
        JarLeave(FALSE);
        return;
    }
    if (pressed & A_BUTTON && JarPiece() != 0xFF)
    {
        // Combine: it fits if it is the next piece, turned as it goes
        const struct En3dJarStep * st = &sEn3dJarSteps[v->jarStep];
        PlaySE(SE00A_SWITCH_RECORD);
        v->jarFit = JarPiece() == v->jarStep && v->jarAngle[v->jarSel] == 0;
        v->jarCircle = FALSE;
        v->jarSprX0 = v->jarSprX;
        v->jarSprY0 = v->jarSprY;
        v->jarSprX1 = st->crossX;
        v->jarSprY1 = st->crossY;
        SetMode(J_SEND);
        return;
    }
    if (pressed & (L_BUTTON | R_BUTTON) && JarPiece() != 0xFF)
    {
        s32 turn = pressed & R_BUTTON ? 90 : -90;
        PlaySE(EN3D_JAR_SE_TURN);
        v->jarShown0 = v->jarAngle[v->jarSel] * 16;
        v->jarShown1 = v->jarShown0 + turn * 16;
        v->jarAngle[v->jarSel] = Wrap(v->jarAngle[v->jarSel] + turn, 360);
        SetMode(J_ROTATE);
        return;
    }
    if (pressed & (DPAD_LEFT | DPAD_RIGHT))
    {
        k = JarNext(pressed & DPAD_RIGHT ? 1 : -1);
        if (k >= 0)
        {
            PlaySE(SE00C_MENU_CHANGE_PAGE);
            v->jarSel = k;
            v->jarShown = v->jarAngle[k] * 16;
        }
    }
}

static void JarFrame(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dJarStep * st = &sEn3dJarSteps[v->jarStep];
    u32 t = ++v->timer;
    s32 k;
    if (++v->jarPulse >= 12 * EN3D_JAR_PULSE_FRAMES)
        v->jarPulse = 0;
    switch (v->mode)
    {
    case J_RISE:
        if (JarStepOn(JAR_RISE_STEPS, JAR_RISE_FRAMES / JAR_RISE_STEPS))
        {
            v->jarTy = Lerp(0, st->ty, v->jarSub, JAR_RISE_STEPS);
            v->jarTz = Lerp(0, st->tz, v->jarSub, JAR_RISE_STEPS);
        }
        if (JarStepsDone(JAR_RISE_STEPS))
            SetMode(J_SPIN);
        break;
    case J_SPIN:
        if (JarStepOn(JAR_SPIN_STEPS, JAR_SPIN_FRAMES / JAR_SPIN_STEPS))
            v->jarYaw = st->yaw * 16 - Lerp(0, 360 * 16, v->jarSub, JAR_SPIN_STEPS);
        if (JarStepsDone(JAR_SPIN_STEPS))
        {
            v->jarYaw = st->yaw * 16;
            JarPlay();
        }
        break;
    case J_PLAY:
        JarInput();
        break;
    case J_ROTATE:
        v->jarShown = Lerp(v->jarShown0, v->jarShown1, t, JAR_ROTATE_FRAMES);
        if (t >= JAR_ROTATE_FRAMES)
        {
            v->jarShown = v->jarAngle[v->jarSel] * 16;
            SetMode(J_PLAY);
        }
        break;
    case J_SEND:
    {
        u32 n = v->jarFit ? JAR_SEND_FRAMES : JAR_MISS_SEND_FRAMES;
        v->jarSprX = Lerp(v->jarSprX0, v->jarSprX1, t, n);
        v->jarSprY = Lerp(v->jarSprY0, v->jarSprY1, t, n);
        if (t < n)
            break;
        if (!v->jarFit)
        {
            SetMode(J_MISS);
            break;
        }
        // it flies into its place (the next fragment picked meanwhile)
        v->jarSpriteShown = FALSE;
        v->jarGuide = FALSE;
        v->jarFlying = TRUE;
        v->jarCached = FALSE;
        v->jarFly = 0;
        v->jarFlyDrawn = 0xFF;
        v->jarPlaced[v->jarSel] = TRUE;
        k = JarNext(1);
        if (k < 0)
            k = JarNext(-1);
        if (k >= 0)
        {
            v->jarSel = k;
            v->jarShown = v->jarAngle[k] * 16;
        }
        v->dirty = TRUE;
        SetMode(J_FIT);
        break;
    }
    case J_FIT:
    {
        u32 f = t < EN3D_JAR_FLIGHT - 1 ? t : EN3D_JAR_FLIGHT - 1;
        if (f != v->jarFly)
        {
            v->jarFly = f;
            v->dirty = TRUE;
        }
        if (f == EN3D_JAR_FLIGHT - 1 && v->jarFlyDrawn == f && PictureUp())
        {
            // in its place (the picture as it is): the jar's from now on
            v->jarFlying = v->jarCached = FALSE;
            v->jarStep++;
            v->jarFlash = TRUE;
            PlaySE(EN3D_JAR_SE_FIT);
            SetMode(J_FLASH);
        }
        break;
    }
    case J_FLASH:
        if (t >= JAR_FLASH_FRAMES)
        {
            v->jarFlash = FALSE;
            SetMode(J_HOLD);
        }
        break;
    case J_HOLD:
        if (t >= JAR_HOLD_FRAMES)
            JarTurn();
        break;
    case J_TURN:
        if (JarStepOn(JAR_TURN_STEPS, JAR_TURN_FRAMES / JAR_TURN_STEPS))
        {
            v->jarYaw = Lerp(v->jarYaw0, v->jarYaw1, v->jarSub, JAR_TURN_STEPS);
            v->jarTy = Lerp(v->jarTy0, v->jarTy1, v->jarSub, JAR_TURN_STEPS);
            v->jarTz = Lerp(v->jarTz0, v->jarTz1, v->jarSub, JAR_TURN_STEPS);
        }
        if (!JarStepsDone(JAR_TURN_STEPS))
            break;
        if (v->jarStep < v->jarEnd)
        {
            JarPlay();
            break;
        }
        if (v->jar == 2)
            PlaySE(EN3D_JAR_SE_DONE);
        SetMode(J_END);
        break;
    case J_MISS:
        if (t >= JAR_MISS_HOVER_FRAMES)
        {
            v->jarSprX0 = v->jarSprX;
            v->jarSprY0 = v->jarSprY;
            SetMode(J_RETURN);
        }
        break;
    case J_RETURN:
        v->jarSprX = Lerp(v->jarSprX0, EN3D_JAR_CIRCLE_X, t, JAR_RETURN_FRAMES);
        v->jarSprY = Lerp(v->jarSprY0, EN3D_JAR_CIRCLE_Y, t, JAR_RETURN_FRAMES);
        if (t >= JAR_RETURN_FRAMES)
            JarPlay();
        break;
    case J_END:
        if (t >= JAR_END_FRAMES)
            JarLeave(TRUE);
        break;
    }
}

// ---------------------------------------------------------------- sections
// a section run over the viewer: file 35's (the script switched to it for
// the while, then put back as it was) or the chapter's own
static void RunSection(u32 section, bool32 file35)
{
    struct En3d * v = &gEn3d;
    v->file35 = file35;
    if (file35)
    {
        DmaCopy16(3, &gScriptContext, &v->savedCtx, sizeof(gScriptContext));
        gScriptBase = gRftaScriptTable[RFTA_SCRIPTS - 1];
    }
    ChangeScriptSection(section);
    SlideTextbox(1);
    SetMode(V_SCRIPT);
}

// the script at its 15 again: the text box away if the section left it
static bool32 SectionDone(void)
{
    struct En3d * v = &gEn3d;
    if (!(gScriptContext.flags & SCRIPT_LOOP))
        return FALSE;
    if (gMain.showTextboxCharacters)
        SlideTextbox(0);
    if (gScriptContext.textboxState != 1 && gScriptContext.textboxState != 0)
        return FALSE;
    if (v->file35)
    {
        gScriptBase = v->scriptBase;
        DmaCopy16(3, &v->savedCtx, &gScriptContext, sizeof(gScriptContext));
        v->file35 = FALSE;
    }
    return TRUE;
}

static void StartTurn(const s16 * q, const s32 * t, u32 then)
{
    struct En3d * v = &gEn3d;
    u32 k;
    s32 dot = 0;
    v->turnThen = then;
    for (k = 0; k < 4; k++)
    {
        v->q0[k] = v->q[k];
        dot += v->q[k] * q[k];
    }
    for (k = 0; k < 4; k++)
        v->q1[k] = dot < 0 ? -q[k] : q[k];
    for (k = 0; k < 3; k++)
    {
        v->t0[k] = v->t[k];
        v->t1[k] = t[k];
    }
    SetMode(V_TURN);
}

static void TurnStep(void)
{
    struct En3d * v = &gEn3d;
    s32 s = (++v->timer * 256) / TURN_FRAMES, k;
    s = (s * s * (3 * 256 - 2 * s)) >> 16;          // smooth, 0-256
    for (k = 0; k < 4; k++)
        v->q[k] = v->q0[k] + (((v->q1[k] - v->q0[k]) * s) >> 8);
    QNormalize(v->q);
    for (k = 0; k < 3; k++)
        v->t[k] = v->t0[k] + (((v->t1[k] - v->t0[k]) >> 4) * s >> 4);
    v->dirty = TRUE;
}

// A on hotspot id: its pose, its animation, its lines
static void Examine(u32 id)
{
    struct En3d * v = &gEn3d;
    const struct En3dId * e = &sEn3dIds[id];
    u32 k;
    PlaySE(SE001_MENU_CONFIRM);
    v->pendingId = id;
    for (k = 0; k < 4; k++)
        v->qSaved[k] = v->q[k];
    for (k = 0; k < 3; k++)
        v->tSaved[k] = v->t[k];
    if (e->nanim)
    {
        v->animStep = 0;
        v->animTimer = 0;
        SetMode(V_ANIM);
        v->dirty = TRUE;
        return;
    }
    StartTurn(e->q, e->t, THEN_EXAMINE);
}

// the id's lines (or none), and what comes after them
static void ExamineSection(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dId * e = &sEn3dIds[v->pendingId];
    const struct En3dScene * sc = Scene();
    u32 section = e->section;
    bool32 file35 = !e->chapter;
    if (e->flag != 0xFF)
    {
        if (!GetFlag(0, e->flag) && gMain.scenarioIdx <= CHAPTER_SECTIONS_UNTIL)
            ChangeFlag(0, e->flag, TRUE);
        else
        {
            section = e->elseSection;
            file35 = TRUE;
        }
    }
    if (v->sceneHere && sc && sc->final == v->pendingId)
        v->after = AFTER_END;
    else if (e->to != 0xFF)
        v->after = AFTER_STAY;
    else
        v->after = AFTER_RESTORE;
    if (section)
        RunSection(section, file35);
    else
        SetMode(V_SCRIPT);              // (straight on: no lines)
}

static void AfterSection(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dScene * sc = Scene();
    switch (v->after)
    {
    case AFTER_RESTORE:
        v->after = AFTER_NONE;
        StartTurn(v->qSaved, v->tSaved, THEN_VIEW);
        return;
    case AFTER_END:
        // the scene's end: the viewer and the record away, then its section
        v->afterSection = sc->after;
        v->sceneEnding = TRUE;
        StartHardwareBlend(2, 1, 1, FADE_ALL);
        SetMode(V_FADE_LEAVE);
        return;
    case AFTER_BACK:
        v->afterSection = sc->back;
        v->sceneEnding = TRUE;
        StartHardwareBlend(2, 1, 1, FADE_ALL);
        SetMode(V_FADE_LEAVE);
        return;
    default:
        v->after = AFTER_NONE;
        SetMode(V_VIEW);
        v->dirty = TRUE;
        return;
    }
}

// ---------------------------------------------------------------- each frame
static void ViewInput(void)
{
    struct En3d * v = &gEn3d;
    struct Joypad * joy = &gJoypad;
    const struct En3dScene * sc = Scene();
    u32 held = joy->heldKeys, hit;
    if (held & R_BUTTON)
    {
        s32 x = v->curX, y = v->curY;
        if (held & DPAD_LEFT) x -= CURSOR_SPEED;
        if (held & DPAD_RIGHT) x += CURSOR_SPEED;
        if (held & DPAD_UP) y -= CURSOR_SPEED;
        if (held & DPAD_DOWN) y += CURSOR_SPEED;
        v->curX = x < 0 ? 0 : x >= EN3D_VIEW_W ? EN3D_VIEW_W - 1 : x;
        v->curY = y < 0 ? 0 : y >= EN3D_VIEW_H ? EN3D_VIEW_H - 1 : y;
    }
    else if (held & L_BUTTON)
    {
        s32 z = v->zoom;
        if (held & DPAD_UP) z += ZOOM_STEP;
        if (held & DPAD_DOWN) z -= ZOOM_STEP;
        z = z < 0 ? 0 : z > ZOOM_MAX ? ZOOM_MAX : z;
        if (z != v->zoom)
        {
            v->zoom = z;
            v->t[2] = z;
            v->dirty = TRUE;
        }
    }
    else
    {
        if (held & DPAD_LEFT) TurnBy(2, -1);
        if (held & DPAD_RIGHT) TurnBy(2, 1);
        if (held & DPAD_UP) TurnBy(1, -1);
        if (held & DPAD_DOWN) TurnBy(1, 1);
    }
    hit = HitTest();
    v->hit = hit;
    if (hit && v->sceneHere && sc && sc->hover && !v->hovered)
    {
        v->hovered = TRUE;
        v->after = AFTER_NONE;
        RunSection(sc->hover, FALSE);
        return;
    }
    if (joy->pressedKeys & A_BUTTON && hit)
    {
        Examine(hit);
        return;
    }
    if (joy->pressedKeys & B_BUTTON)
    {
        if (v->sceneHere && sc)
        {
            if (!sc->back)
                return;
            PlaySE(SE002_MENU_CANCEL);
            v->after = AFTER_BACK;
            AfterSection();
            return;
        }
        PlaySE(SE002_MENU_CANCEL);
        StartHardwareBlend(2, 1, 1, FADE_ALL);
        SetMode(V_FADE_LEAVE);
    }
}

// A (and B held, past what was read) for the text: the script's Command02
// takes them itself in the court's and the investigation's processes only
static void TextInput(void)
{
    struct ScriptContext * ctx = &gScriptContext;
    if (ctx->flags & 1 && gJoypad.pressedKeys & A_BUTTON)
        ctx->flags |= 2;
    if (ctx->paragraphSkipDelayCounter > 0)
        ctx->paragraphSkipDelayCounter--;
    if (gJoypad.heldKeys & B_BUTTON && ctx->textSkip != 0 && ctx->paragraphSkipDelayCounter == 0)
        ctx->flags |= 2;
}

// the Court Record's state 8
void En3dProcess(struct Main * main, struct CourtRecord * courtRecord)
{
    struct En3d * v = &gEn3d;
    const struct En3dScene * sc = Scene();
    if (v->keypad)
    {
        KeypadProcess(main);
        return;
    }
    switch (v->mode)
    {
    case V_FADE_OUT:
        if (main->blendMode != 0)
            return;
        if (v->badger)
            EnMovieClose();         // (the DS's Blue Badger on its top screen: here the panel is the screen)
        SaveScreen();
        SetMode(V_SETUP);
        return;
    case V_SETUP:
        TakeScreen();
        if (v->jar)
            JarSetup();
        else if (v->badger)
            BadgerSetup();
        else
        {
            ResetView();
            ShowRecord(v->record);
        }
        v->uploadAll = TRUE;
        SetMode(V_FIRST);
        break;
    case V_FIRST:
        // (the first picture whole before the fade)
        if (v->render == R_IDLE && !v->dirty && !v->uploadReady)
        {
            if (v->jar)
                StartHardwareBlend(1, 2, 1, FADE_ALL);
            else if (v->badger)
                StartHardwareBlend(1, 1, 1, FADE_ALL);
            else
                StartHardwareBlend(1, 1, 2, FADE_ALL);
            SetMode(V_FADE_IN);
        }
        break;
    case V_FADE_IN:
        if (main->blendMode != 0)
            break;
        gIORegisters.lcd_bldcnt = BLDCNT_TGT1_BG1 | BLDCNT_TGT2_BG2 | BLDCNT_TGT2_BG3 | BLDCNT_TGT2_OBJ | BLDCNT_TGT2_BD | BLDCNT_EFFECT_BLEND;
        gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(0x1F, 0x7);
        gIORegisters.lcd_bldy = 0;
        if (v->jar)
        {
            SetMode(J_RISE);
            break;
        }
        if (v->badger)
        {
            v->badgerVBlank = gEnVBlanks;
            SetMode(B_PLAY);
            break;
        }
        if (v->sceneHere && sc && sc->open && !v->hovered)
        {
            v->after = AFTER_NONE;
            RunSection(sc->open, FALSE);
            break;
        }
        SetMode(V_VIEW);
        break;
    case V_VIEW:
        ViewInput();
        break;
    case V_TURN:
        TurnStep();
        if (v->timer >= TURN_FRAMES)
        {
            if (v->turnThen == THEN_EXAMINE)
                ExamineSection();
            else
            {
                v->zoom = v->t[2] < 0 ? 0 : v->t[2] > ZOOM_MAX ? ZOOM_MAX : v->t[2];
                SetMode(V_VIEW);
            }
        }
        break;
    case V_ANIM:
        if (++v->animTimer >= ANIM_FRAMES && v->render == R_IDLE && !v->dirty)
        {
            const struct En3dId * e = &sEn3dIds[v->pendingId];
            v->animTimer = 0;
            if (++v->animStep >= e->nanim)
            {
                ShowRecord(e->to);
                v->q[0] = e->q[0]; v->q[1] = e->q[1]; v->q[2] = e->q[2]; v->q[3] = e->q[3];
                v->t[0] = e->t[0]; v->t[1] = e->t[1]; v->t[2] = e->t[2];
                v->zoom = e->t[2] < 0 ? 0 : e->t[2] > ZOOM_MAX ? ZOOM_MAX : e->t[2];
                ExamineSection();
                break;
            }
            v->dirty = TRUE;
        }
        break;
    case V_SCRIPT:
        TextInput();
        if (!SectionDone())
            break;
        AfterSection();
        break;
    case V_FADE_LEAVE:
        if (main->blendMode != 0)
            break;
        SetMode(V_LEAVE);
        return;
    case V_LEAVE:
        if (v->jar)
        {
            JarGone(main);
            return;
        }
        if (v->badger)
        {
            BadgerGone(main);
            return;
        }
        GiveBackScreen();
        v->render = R_IDLE;
        v->uploadReady = FALSE;
        v->closeup = v->closeupShown = 0;
        main->process[GAME_PROCESS_VAR1] = v->fromVar1;
        main->process[GAME_PROCESS_VAR2] = v->fromVar2;
        main->process[GAME_PROCESS_STATE] = RECORD_3D;
        StartHardwareBlend(1, 1, 2, FADE_ALL);
        SetMode(V_SHOW_RECORD);
        UpdateBG2Window(courtRecord);
        UpdateRecordSprites(courtRecord);
        return;
    case V_SHOW_RECORD:
        UpdateBG2Window(courtRecord);
        UpdateRecordSprites(courtRecord);
        if (main->blendMode != 0)
            return;
        main->process[GAME_PROCESS_STATE] = v->fromState;
        if (v->sceneEnding)
        {
            // the record goes too (its section when it is away: En3dRecordClosed)
            v->scene = 0;
            PlaySE(SE002_MENU_CANCEL);
            SlideInBG2Window(0x3, 0xC);
            main->process[GAME_PROCESS_STATE] = RECORD_EXIT;
        }
        SetMode(V_OFF);
        return;
    default:
        if (v->mode < J_RISE)
            return;
        if (v->badger)
            BadgerFrame();
        else
            JarFrame();
        break;
    }
    // the hover's how-to may have started a section above
    gIORegisters.lcd_bg3hofs = 8;
    gIORegisters.lcd_bg3vofs = 8;
    if (v->mode == V_SCRIPT || v->mode == V_ANIM || v->mode == V_TURN)
        v->hit = 0;
    if (v->jar)
        DrawJarSprites();
    else if (v->badger)
        DrawBadgerSprites();
    else
        DrawSprites();
    RenderWork();
}

// the record away after a scene's end: its section (court_record.c)
void En3dRecordClosed(void)
{
    struct En3d * v = &gEn3d;
    if (!v->sceneEnding)
        return;
    v->sceneEnding = FALSE;
    if (v->afterSection)
    {
        ChangeScriptSection(v->afterSection);
        SlideTextbox(1);
    }
    v->afterSection = 0;
}

// ---------------------------------------------------------------- the record's prompt
// "L Check" left of "R Profiles" (as the luminol's "A Spray"): the record's
// L button (tile 0x1CC) and the label in its free tiles 0x1B8 and 0x1D0
#define OAM_CHECK_PROMPT OAM_IDX_GENERAL_2
void En3dRecordPrompt(struct CourtRecord * courtRecord, bool32 show)
{
    struct OamAttrs * oam = &gOamObjects[OAM_CHECK_PROMPT];
    if (!show || !En3dCheckable(courtRecord))
        return;             // (the luminol's prompt clears these when it has none)
    DmaCopy16(3, D(EN3D_GFX_CHECK), OBJ_VRAM0 + 0x1B8 * 32, 8 * 32);
    DmaCopy16(3, D(EN3D_GFX_CHECK) + 8 * 32, OBJ_VRAM0 + 0x1D0 * 32, 8 * 32);
    oam[0].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
    oam[0].attr1 = SPRITE_ATTR1_NONAFFINE(96, FALSE, FALSE, 1);
    oam[0].attr2 = SPRITE_ATTR2(0x1CC, 0, 4);
    oam[1].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE);
    oam[1].attr1 = SPRITE_ATTR1_NONAFFINE(112, FALSE, FALSE, 2);
    oam[1].attr2 = SPRITE_ATTR2(0x1B8, 0, 4);
    oam[2].attr0 = SPRITE_ATTR0(96, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_H_RECTANGLE);
    oam[2].attr1 = SPRITE_ATTR1_NONAFFINE(144, FALSE, FALSE, 2);
    oam[2].attr2 = SPRITE_ATTR2(0x1D0, 0, 4);
}

// ---------------------------------------------------------------- the Blue Badger's angle
// The DS's 74 8 33 (script command 69 6<<8): the Unstable Jar turned until
// it looks like the Blue Badger (badger.py has what the DS does). The jar
// whole (the DS's object record 17) is drawn by the viewer's renderer in the
// DS's circle, its turn kept as the DS keeps it: a matrix (row vectors) each
// turn is applied after, about the screen's axes. The + pad turns it 2
// degrees a frame (and runs the drums' ticks round, as the DS's drag
// does), L and R 1 about the line of sight (the ring's ticks turn with
// it); A presents it: the DS's angles read off the matrix, then the white,
// and the Take that! section (translate.py) on to BD or BC.
#include "data/en_rfta_badger_sections.h"
#define B_OAM 90                        // (the screen's own: nothing else draws while it is up)
#define B_OAM_LAST 121
#define B_AFFINE 30
#define PAL_RING 10
#define PAL_TICK 11
#define B_TILE_TICKS (TILE_BASE + 256)
// BG2's grid tiles (4 bits, charbase GRID_CHAR) after BG3's: the frame buffer's and the panel's
#define B_GRID_TILE (((EN3D_VIEW_TILES + EN3D_BADGER_TILES) * 64 + 0x4000 - 0x4000 * GRID_CHAR + 31) / 32)
typedef char sEn3dBadgerFits[B_GRID_TILE * 32 + 5 * 32 + 0x4000 * GRID_CHAR <= 0x800 * GRID_SCREEN ? 1 : -1];

// M = M x R: R the DS's rotation (row vectors) about x, y or z by its
// step (the + pad's, or L and R's: the sine table's entries), d its sign
static void BadgerTurn(u32 axis, s32 d)
{
    s32 * m = gEn3d.bm;
    s32 c = axis == 2 ? EN3D_BADGER_ROLL_COS : EN3D_BADGER_TURN_COS, s, i, a, b;
    s = axis == 2 ? EN3D_BADGER_ROLL_SIN : EN3D_BADGER_TURN_SIN;
    if (d < 0)
        s = -s;
    for (i = 0; i < 3; i++)
    {
        s32 * r = m + 3 * i;
        if (axis == 1)
        {
            a = (r[0] * c + r[2] * s) >> 14; b = (r[2] * c - r[0] * s) >> 14;
            r[0] = a; r[2] = b;
        }
        else if (axis == 0)
        {
            a = (r[1] * c - r[2] * s) >> 14; b = (r[1] * s + r[2] * c) >> 14;
            r[1] = a; r[2] = b;
        }
        else
        {
            a = (r[0] * c - r[1] * s) >> 14; b = (r[0] * s + r[1] * c) >> 14;
            r[0] = a; r[1] = b;
        }
    }
}

static void Normalize3(s32 * v)
{
    s32 len = ISqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (len == 0)
        return;
    v[0] = (v[0] << 14) / len; v[1] = (v[1] << 14) / len; v[2] = (v[2] << 14) / len;
}

static void Cross3(s32 * out, const s32 * a, const s32 * b)
{
    out[0] = (a[1] * b[2] - a[2] * b[1]) >> 14;
    out[1] = (a[2] * b[0] - a[0] * b[2]) >> 14;
    out[2] = (a[0] * b[1] - a[1] * b[0]) >> 14;
}

// kept a rotation (the DS's 0x02067ca4 each frame)
static void BadgerSquare(void)
{
    s32 * m = gEn3d.bm;
    Normalize3(m + 6);
    Cross3(m, m + 3, m + 6);
    Normalize3(m);
    Cross3(m + 3, m + 6, m);
}

// the renderer's (column vectors: M turned over), the jar 2 behind its place
static void BadgerMatrix(void)
{
    struct En3d * v = &gEn3d;
    u32 i, j;
    for (i = 0; i < 3; i++)
        for (j = 0; j < 3; j++)
            v->rm[3 * i + j] = v->bm[3 * j + i];
    v->rt[0] = v->rt[1] = 0;
    v->rt[2] = EN3D_BADGER_Z;
}

// the ring's pixels over the picture where it crosses it (four at a time:
// most of the mask's words are all the ring's or all the picture's)
static void BadgerMask(void)
{
    const u32 * m = (const u32 *)D(EN3D_BADGER_GFX_MASKS);
    const u16 * at = (const u16 *)D(EN3D_BADGER_GFX_MASK_AT);
    u32 k, i, j;
    for (k = 0; k < EN3D_BADGER_MASKS; k++, m += 16)
    {
        u32 * t = (u32 *)(sFb + 64 * at[k]);
        for (i = 0; i < 16; i++)
        {
            u32 w = m[i];
            if (w == 0)
                continue;
            if ((w & 0xFF) && (w & 0xFF00) && (w & 0xFF0000) && (w & 0xFF000000))
                t[i] = w;
            else
            {
                u8 * tb = (u8 *)&t[i];
                for (j = 0; j < 4; j++, w >>= 8)
                    if (w & 0xFF)
                        tb[j] = w;
            }
        }
    }
}

// the angle of (x, y), degrees x 16 (0 to 360: the DS's FX_Atan2Idx's)
static s32 Atan2Deg16(s32 y, s32 x)
{
    s32 ax = x < 0 ? -x : x, ay = y < 0 ? -y : y, n, d, lo = 0, hi = 45 * 16, a;
    bool32 swap = ay > ax;
    n = swap ? ax : ay;
    d = swap ? ay : ax;
    if (d == 0)
        return 0;
    while (lo < hi)
    {
        s32 mid = (lo + hi + 1) >> 1;
        if (Sin16(mid) * d <= Cos16(mid) * n)
            lo = mid;
        else
            hi = mid - 1;
    }
    a = swap ? 90 * 16 - lo : lo;
    if (x < 0)
        a = 180 * 16 - a;
    if (y < 0)
        a = 360 * 16 - a;
    return a >= 360 * 16 ? a - 360 * 16 : a;
}

// the DS's 0x02067dac: the angles of the matrix, and whether they are the Badger's
static bool32 BadgerRight(void)
{
    const s32 * m = gEn3d.bm;
    s32 x = m[6], y = m[7], z = m[8], a, b, c, r0[3], r1, r2, sa, ca, sb, cb;
    a = Atan2Deg16(-y, ISqrt(x * x + z * z)) >> 4;
    b = Atan2Deg16(x, z) >> 4;
    // the first row turned back by b about y, then by a about x
    sb = Sin16(-b * 16); cb = Cos16(-b * 16);
    sa = Sin16(-a * 16); ca = Cos16(-a * 16);
    r0[0] = (m[0] * cb + m[2] * sb) >> 14;
    r0[1] = m[1];
    r0[2] = (m[2] * cb - m[0] * sb) >> 14;
    r1 = (r0[1] * ca - r0[2] * sa) >> 14;
    r2 = r0[0];
    c = Atan2Deg16(r1, r2) >> 4;
    return a > EN3D_BADGER_A0 && a < EN3D_BADGER_A1
        && ((b > EN3D_BADGER_B0 && b < EN3D_BADGER_B1) || (b >= 0 && b < EN3D_BADGER_B2))
        && c > EN3D_BADGER_C0 && c < EN3D_BADGER_C1;
}

// command 69 6<<8: the screen faded out (the DS's 2, 3, 1), then the panel's
static void BadgerStart(void)
{
    struct En3d * v = &gEn3d;
    v->badger = TRUE;
    v->jar = 0;
    v->keypad = 0;
    v->scene = 0;
    v->sceneHere = FALSE;
    v->hovered = FALSE;
    v->hit = 0;
    v->closeup = v->closeupShown = 0;
    v->after = AFTER_NONE;
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->coloursRec = 0xFF;
    v->file35 = FALSE;
    v->dirty = FALSE;
    BACKUP_PROCESS();
    SET_PROCESS(COURT_RECORD_PROCESS, RECORD_3D, 0, 0);
    StartHardwareBlend(2, 3, 1, FADE_ALL);
    SetMode(V_FADE_OUT);
}

// the panel: BG3 the frame buffer's tiles in the circle, the panel's round
// it; BG2 the grid under the picture; the ring's ticks and the drums' sprites
static void BadgerScreen(void)
{
    struct IORegisters * io = &gIORegisters;
    const u16 * map = (const u16 *)D(EN3D_BADGER_GFX_MAP);
    const u8 * grid = D(EN3D_BADGER_GFX_GRID_MAP);
    u32 r, c, k;
    io->lcd_dispcnt &= ~(DISPCNT_BG0_ON | DISPCNT_BG1_ON);
    io->lcd_dispcnt |= DISPCNT_BG2_ON | DISPCNT_BG3_ON | DISPCNT_OBJ_ON;
    io->lcd_bg3hofs = 8;
    io->lcd_bg3vofs = 8;
    io->lcd_bg3cnt = BGCNT_PRIORITY(2) | BGCNT_CHARBASE(1) | BGCNT_SCREENBASE(31) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_256COLOR;
    io->lcd_bg2hofs = 8;
    io->lcd_bg2vofs = 8;
    io->lcd_bg2cnt = BGCNT_PRIORITY(3) | BGCNT_CHARBASE(GRID_CHAR) | BGCNT_SCREENBASE(GRID_SCREEN) | BGCNT_WRAP | BGCNT_TXT256x256 | BGCNT_16COLOR;
    DmaCopy16(3, D(EN3D_BADGER_GFX_GRID), BG_CHAR_ADDR(GRID_CHAR) + B_GRID_TILE * 32, 4 * 32);
    DmaFill16(3, 0, BG_CHAR_ADDR(GRID_CHAR) + (B_GRID_TILE + 4) * 32, 32);
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
        {
            u32 g = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? grid[(r - 1) * 30 + c - 1] : 0;
            ((u16 *)BG_SCREEN_ADDR(GRID_SCREEN))[r * 32 + c] = (g ? B_GRID_TILE + g - 1 : B_GRID_TILE + 4) | (GRID_PAL << 12);
        }
    DmaCopy16(3, sEn3dBadgerGridPal, BG_PLTT + GRID_PAL * 32, 8);
    ((u16 *)BG_PLTT)[0] = sEn3dBadgerGridPal[1];
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
            gBG3MapBuffer[r * 32 + c] = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? map[(r - 1) * 30 + c - 1] : EN3D_VIEW_TILES;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaCopy32(3, D(EN3D_BADGER_GFX_TILES), BG_CHAR_ADDR(1) + EN3D_VIEW_TILES * 64, EN3D_BADGER_TILES * 64);
    DmaCopy16(3, sEn3dBadgerPalette, BG_PLTT + EN3D_PAL_FRAME * 2, EN3D_BADGER_COLOURS * 2);
    DmaCopy32(3, D(EN3D_BADGER_GFX_RING), OBJ_VRAM0 + TILE_BASE * 32, 256 * 32);
    DmaCopy32(3, D(EN3D_BADGER_GFX_TICKS), OBJ_VRAM0 + B_TILE_TICKS * 32, 2 * 32);
    DmaCopy16(3, sEn3dBadgerRingPal, OBJ_PLTT + PAL_RING * 32, 32);
    DmaCopy16(3, sEn3dBadgerTickPal, OBJ_PLTT + PAL_TICK * 32, 32);
    for (k = OAM_FIRST; k <= OAM_LAST; k++)
        gOamObjects[k].attr0 = SPRITE_ATTR0_CLEAR;
    ClearAll();
    BadgerMask();
    DmaCopy32(3, sFb, BG_CHAR_ADDR(1), EN3D_VIEW_TILES * 64);
}

// the jar upright, the drums and the ring at rest; the picture's record
static void BadgerSetup(void)
{
    struct En3d * v = &gEn3d;
    u32 k;
    for (k = 0; k < 9; k++)
        v->bm[k] = (k % 4 == 0) ? 1 << 14 : 0;
    v->badgerRoll = v->badgerDrumH = v->badgerDrumV = 0;
    v->badgerRight = FALSE;
    v->record = EN3D_BADGER_RECORD;
    v->dirty = TRUE;
}

// a drum's ticks: k of n, at the drum's turn (degrees: its sine along the drum's middle)
static void BadgerTicks(u32 * o, bool32 across)
{
    struct En3d * v = &gEn3d;
    u32 n = across ? 16 : 12, k;
    for (k = 0; k < n && *o <= B_OAM_LAST; k++)
    {
        s32 r = across ? EN3D_BADGER_DRUM_H_R : EN3D_BADGER_DRUM_V_R;
        s32 ang = (across ? v->badgerDrumH + sEn3dBadgerTicksH[k] : v->badgerDrumV + sEn3dBadgerTicksV[k]) + 360;
        s32 sv = r * Sin16(ang * 16) / 16384, x, y;   // (toward 0: the DS's float to int)
        s32 out = r - (sv < 0 ? -sv : sv);
        struct OamAttrs * oam = &gOamObjects[(*o)++];
        if (across)
        {
            x = EN3D_BADGER_DRUM_H_X + sv;
            y = sEn3dBadgerBowH[out] + EN3D_BADGER_DRUM_H_Y;
        }
        else
        {
            y = EN3D_BADGER_DRUM_V_Y + sv;
            x = sEn3dBadgerBowV[out] + EN3D_BADGER_DRUM_V_X;
        }
        oam->attr0 = SPRITE_ATTR0(y & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE(x & 0x1FF, FALSE, FALSE, 0);
        oam->attr2 = SPRITE_ATTR2(B_TILE_TICKS + !across, 1, PAL_TICK);
    }
}

static void DrawBadgerSprites(void)
{
    struct En3d * v = &gEn3d;
    u32 o = B_OAM, q;
    s32 c = Cos16(v->badgerRoll * 16), s = Sin16(v->badgerRoll * 16);
    // the ring's ticks: four quarters, turned about the circle's middle by the roll
    for (q = 0; q < 4; q++)
    {
        s32 dx = (q & 1) ? 32 : -32, dy = (q & 2) ? 32 : -32;
        s32 x = EN3D_BADGER_RING_X + ((dx * c + dy * s) >> 14), y = EN3D_BADGER_RING_Y + ((dy * c - dx * s) >> 14);
        struct OamAttrs * oam = &gOamObjects[o++];
        oam->attr0 = SPRITE_ATTR0((y - 64) & 0xFF, ST_OAM_AFFINE_DOUBLE, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, ST_OAM_SQUARE);
        oam->attr1 = SPRITE_ATTR1_AFFINE((x - 64) & 0x1FF, B_AFFINE, 3);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + 64 * q, 1, PAL_RING);
    }
    gOamObjects[B_AFFINE * 4 + 0].attr3 = c >> 6;
    gOamObjects[B_AFFINE * 4 + 1].attr3 = -s >> 6;
    gOamObjects[B_AFFINE * 4 + 2].attr3 = s >> 6;
    gOamObjects[B_AFFINE * 4 + 3].attr3 = c >> 6;
    BadgerTicks(&o, TRUE);
    BadgerTicks(&o, FALSE);
    for (; o <= B_OAM_LAST; o++)
        gOamObjects[o].attr0 = SPRITE_ATTR0_CLEAR;
}

// the player's turn: the + pad and L and R held turn the jar (the DS's
// order: about the upright, across, the line of sight) a step for each
// frame that passed (the DS's frames: a picture can take a frame's work
// over its time), A presents it
static void BadgerFrame(void)
{
    struct En3d * v = &gEn3d;
    u32 held = gJoypad.heldKeys, n = gEnVBlanks - v->badgerVBlank;
    s32 dy = 0, dp = 0, dr = 0;
    v->badgerVBlank = gEnVBlanks;
    if (n > 4)
        n = 4;
    if (v->mode == B_FLASH)
    {
        if (gMain.blendMode == 0)
            SetMode(V_LEAVE);
        return;
    }
    if (gJoypad.pressedKeys & A_BUTTON)
    {
        // the white (the DS's both screens), then the Take that!
        v->badgerRight = BadgerRight();
        StartHardwareBlend(4, 1, 4, FADE_ALL);
        SetMode(B_FLASH);
        return;
    }
    if (held & DPAD_LEFT)
        dy = -EN3D_BADGER_TURN;
    else if (held & DPAD_RIGHT)
        dy = EN3D_BADGER_TURN;
    if (held & DPAD_UP)
        dp = -EN3D_BADGER_TURN;
    else if (held & DPAD_DOWN)
        dp = EN3D_BADGER_TURN;
    if (held & L_BUTTON)
        dr = EN3D_BADGER_ROLL;
    else if (held & R_BUTTON)
        dr = -EN3D_BADGER_ROLL;
    if (!dy && !dp && !dr)
        return;
    for (; n > 0; n--)
    {
        if (dy)
        {
            BadgerTurn(1, dy);
            v->badgerDrumH = Wrap(v->badgerDrumH + dy, 11);
        }
        if (dp)
        {
            BadgerTurn(0, dp);
            v->badgerDrumV = Wrap(v->badgerDrumV + dp, 11);
        }
        if (dr)
        {
            BadgerTurn(2, dr);
            v->badgerRoll = Wrap(v->badgerRoll + dr, 360);
        }
        BadgerSquare();
    }
    v->dirty = TRUE;
}

// everything back, the screen white; the Take that! (the GBA's own,
// translate.py) and the DS's next section
static void BadgerGone(struct Main * main)
{
    struct En3d * v = &gEn3d;
    GiveBackScreen();
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->badger = FALSE;
    SetMode(V_OFF);
    RESTORE_PROCESS_PTR(main);
    gIORegisters.lcd_bldcnt = FADE_ALL | BLDCNT_EFFECT_LIGHTEN;
    gIORegisters.lcd_bldy = 16;
    ChangeScriptSection(v->badgerRight ? EN3D_BADGER_SECTION_RIGHT : EN3D_BADGER_SECTION_WRONG);
}

// ---------------------------------------------------------------- the keypad
// The DS's 74 8 34 (script command 69 5<<8): the safe's keypad, its frames
// en_keypad.c's; here its screen taken and given back (the viewer's way)
static void KeypadStart(void)
{
    struct En3d * v = &gEn3d;
    v->keypad = TRUE;
    v->jar = 0;
    v->scene = 0;
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    v->closeup = v->closeupShown = 0;
    v->coloursRec = 0xFF;
    v->dirty = FALSE;
    BACKUP_PROCESS();
    SET_PROCESS(COURT_RECORD_PROCESS, RECORD_3D, 0, 0);
    StartHardwareBlend(2, 1, 1, FADE_ALL);
    SetMode(V_FADE_OUT);
}

// the room's screen given back on background bg, no one in it (the DS's
// sections after the keypad bring the person in themselves)
void En3dGiveBack(u32 bg)
{
    struct En3d * v = &gEn3d;
    GiveBackScreenOn(bg);
    v->render = R_IDLE;
    v->uploadReady = FALSE;
    DestroyAnimation(&gAnimation[1]);
    gInvestigation.personActive = 0;
    SetInactiveActionButtons(&gInvestigation, 15);
}

// the record's sprites' tiles and the colours back (after the safe's handle)
void En3dGiveBackObj(void)
{
    DmaCopy16(3, sObjPalBackup, OBJ_PLTT, 0x200);
    DmaCopy32(3, sObjBackup, OBJ_VRAM0 + TILE_BASE * 32, OBJ_BACKUP_TILES * 32);
}

void En3dChangeBg(u32 bg)
{
    ChangeBg(bg);
}

static void KeypadProcess(struct Main * main)
{
    struct En3d * v = &gEn3d;
    u32 r;
    switch (v->mode)
    {
    case V_FADE_OUT:
        if (main->blendMode != 0)
            return;
        SaveScreen();
        EnKeypadScreen();
        EnKeypadSprites();
        // (the DS's keypad fades in as the LCD's prompt blinks)
        StartHardwareBlend(1, 2, 1, FADE_ALL);
        SetMode(V_VIEW);
        return;
    case V_VIEW:
        r = EnKeypadFrame();
        if (r == KEYPAD_ON)
            EnKeypadSprites();
        else if (r >= KEYPAD_SECTION)
        {
            // on in the section the DS's would start, faded in
            v->keypad = FALSE;
            SetMode(V_OFF);
            RESTORE_PROCESS_PTR(main);
            ChangeScriptSection(r);
            StartHardwareBlend(1, 1, 1, FADE_ALL);
        }
        return;
    }
}

// ---------------------------------------------------------------- the script
// Script command 69: 69 0 n the record opened for scene n, 69 2<<8 | n
// close-up n shown in the viewer, 69 3<<8 taken away, 69 4<<8 | n the jar
// puzzle (n 0 Day 2's, 1 Day 3's), 69 5<<8 the safe's keypad, 69 6<<8 the
// Blue Badger's angle
bool32 Command69(struct ScriptContext * scriptCtx)
{
    struct En3d * v = &gEn3d;
    u32 arg;
    scriptCtx->scriptPtr++;
    arg = *scriptCtx->scriptPtr++;
    switch (arg >> 8)
    {
    case 0:
        v->scene = (arg & 0xFF) + 1;
        v->sceneEnding = FALSE;
        v->afterSection = 0;
        PlaySE(SE007_MENU_OPEN_SUBMENU);
        BACKUP_PROCESS();
        SET_PROCESS(COURT_RECORD_PROCESS, RECORD_INIT, 0, 0);
        break;
    case 2:
        if (v->mode != V_OFF && (arg & 0xFF) < EN3D_CLOSEUPS)
            v->closeup = (arg & 0xFF) + 1;
        break;
    case 3:
        if (v->closeup)
        {
            v->closeup = 0;
            v->uploadAll = TRUE;
        }
        break;
    case 4:
        JarStart(arg & 0xFF);
        break;
    case 5:
        KeypadStart();
        break;
    case 6:
        BadgerStart();
        break;
    }
    return 0;
}

#endif

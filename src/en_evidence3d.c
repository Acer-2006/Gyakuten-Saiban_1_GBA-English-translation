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
// DS's 7B 0 n), 69 3<<8 takes it away.
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
#include "data/en_rfta_evidence3d.h"
extern const u8 gEn3dData[];

// the renderer (en_evidence3d_arm.s), copied to IWRAM
struct En3dXf { const s16 * verts; u32 count; s32 * out; s32 cx[4], cy[4], cz[4]; const u32 * r31; u32 maxW; };
struct En3dDraw { const u8 * tris; u32 count; const s32 * xv; const u8 * tex; u32 wlog, hlog, pal, zshift;
                  u8 * fb; u16 * zb; const u32 * r31; u8 * frame; u32 limit, resume; };
extern const u8 gEn3dCodeStart[];
extern const u8 gEn3dCodeEnd[];
extern u32 gEnMovieCode[];
#define Transform ((void (*)(struct En3dXf *))((u8 *)gEnMovieCode + 0))
#define DrawPart ((u32 (*)(struct En3dDraw *))((u8 *)gEnMovieCode + 4))

enum { V_OFF, V_FADE_OUT, V_SETUP, V_FIRST, V_FADE_IN, V_VIEW, V_TURN, V_ANIM, V_SCRIPT, V_FADE_LEAVE, V_LEAVE, V_SHOW_RECORD };
enum { R_IDLE, R_CLEAR, R_XFORM, R_DRAW, R_READY };
enum { AFTER_NONE, AFTER_RESTORE, AFTER_STAY, AFTER_END, AFTER_BACK };
enum { THEN_EXAMINE, THEN_VIEW };

#define CHAPTER_SECTIONS_UNTIL 18       // the DS's flagged ids: their chapter lines in chapter 18 and before
#define OAM_FIRST OAM_IDX_GENERAL_2     // 57-87
#define OAM_LAST 87
#define TILE_BASE 0x1A0                 // OBJ tiles 0x1A0-0x27F: the viewer's sprites
#define PAL_UI 8
#define TURN_STEP_COS 16380             // 2.5 degrees a frame (half angles, 1.14)
#define TURN_STEP_SIN 357
#define ZOOM_MAX (12 << 12)             // toward the camera, 1.19.12 (the DS's poses go to 12)
#define ZOOM_STEP 0x180
#define CURSOR_SPEED 2
#define TURN_FRAMES 20
#define ANIM_FRAMES 8
#define TEXTBOX_TOP 112                 // (the text box's top: the tabs under it while it talks)

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
#define sVerts ((s32 *)(HEAP + 0xC800))                 // 12 bytes a vertex: 0x1950
#define sCorners ((s16 *)(HEAP + 0xE200))               // a quad's corners
#define sCornersOut ((s32 *)(HEAP + 0xE240))
#define OBJ_BACKUP_TILES (0x2C0 - TILE_BASE)
#define sFb ((u8 *)(EWRAM_START + 0x2CFC0))             // 24 x 16 tiles, 8bpp (0: the grid under it)
#define sZb ((u16 *)(EWRAM_START + 0x2CFC0 + 0x6000))   // 192 x 128
#define MAX_VERTS 540
// the grid (BG2, under BG3: its tiles and map where nothing else is while
// the viewer is up, its colour in BG palette 14)
#define GRID_CHAR 3
#define GRID_SCREEN 27
#define GRID_PAL 14
#define FB_ROW (24 * 64)

#define D(off) (gEn3dData + (off))
static const u32 * R31(void) { return (const u32 *)D(EN3D_R31); }

void UpdateItemPlate(struct Main *);

// ---------------------------------------------------------------- state
bool32 En3dActive(void)
{
    return gEn3d.mode != V_OFF;
}

void En3dReset(void)
{
    gEn3d.mode = V_OFF;
    gEn3d.scene = 0;
    gEn3d.sceneEnding = FALSE;
    gEn3d.afterSection = 0;
}

static void SetMode(u32 mode)
{
    gEn3d.mode = mode;
    gEn3d.phase = 0;
    gEn3d.timer = 0;
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
    return gEn3d.mode >= V_FIRST && gEn3d.mode <= V_SCRIPT;
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

static void SetXf(struct En3dXf * xf, const s32 * m, const s32 * t)
{
    u32 k;
    for (k = 0; k < 3; k++)
    {
        xf->cx[k] = m[k]; xf->cy[k] = m[3 + k]; xf->cz[k] = m[6 + k];
    }
    xf->cx[3] = t[0]; xf->cy[3] = t[1]; xf->cz[3] = t[2];
    xf->r31 = R31();
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

static void StartPicture(void)
{
    struct En3d * v = &gEn3d;
    v->dirty = FALSE;
    Matrix(v->rm, v->q);
    v->rt[0] = v->t[0]; v->rt[1] = v->t[1]; v->rt[2] = v->t[2];
    v->drawRec = ShownIndex();
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

// the picture, as far as the frame's time goes
static void RenderWork(void)
{
    struct En3d * v = &gEn3d;
    const struct En3dRecord * r = &sEn3dRecords[v->drawRec];
    for (;;)
    {
        switch (v->render)
        {
        case R_IDLE:
            if (!v->dirty || v->uploadReady)
                return;
            StartPicture();
            r = &sEn3dRecords[v->drawRec];
            break;
        case R_CLEAR:
            if (!ClearRows(TRUE))
                return;
            v->render = R_XFORM;
            break;
        case R_XFORM:
        {
            u32 mesh, off = 0, k;
            if (v->mesh >= 3 || r->meshes[v->mesh] == 0xFF)
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
                off += MeshVerts(r->meshes[k]);
            mesh = r->meshes[v->mesh];
            v->vertsOf[v->mesh] = off;
            SetXf(&v->xf, v->rm, v->rt);
            v->xf.verts = MeshVertices(mesh);
            v->xf.count = MeshVerts(mesh);
            v->xf.out = sVerts + 3 * off;
            Transform(&v->xf);
            if (v->xf.maxW > v->maxW)
                v->maxW = v->xf.maxW;
            Grow(v->xf.out, v->xf.count);
            v->mesh++;
            break;
        }
        case R_DRAW:
        {
            struct En3dDraw * d = &v->draw;
            u32 mesh;
            if (v->mesh >= 3 || r->meshes[v->mesh] == 0xFF)
            {
                // whole: up when the next vertical blank comes (the rows of
                // the old picture and the new)
                u32 y0 = v->box[1], y1 = v->box[3];
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
                v->coloursRec = v->drawRec;
                v->render = R_IDLE;
                return;
            }
            mesh = r->meshes[v->mesh];
            if (v->part >= MeshParts(mesh))
            {
                v->mesh++;
                v->part = 0;
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
                d->xv = sVerts + 3 * v->vertsOf[v->mesh];
                d->tex = D(t->off);
                d->wlog = t->wlog;
                d->hlog = t->hlog;
                d->pal = EN3D_PAL_TEXTURES + 16 * TextureSlot(r, p[2]);
                d->zshift = v->zshift;
                d->fb = sFb;
                d->zb = sZb;
                d->r31 = R31();
                d->frame = sFrame;
            }
            d->limit = Limit();
            if (DrawPart(d) == 0)
                v->part++;
            else
                return;
            break;
        }
        default:
            return;
        }
    }
}

// the vertical blank's: the picture (its rows) or the close-up to VRAM
void En3dVBlank(void)
{
    struct En3d * v = &gEn3d;
    if (v->mode < V_FIRST || v->mode > V_FADE_LEAVE)
        return;
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

static void Sprite(u32 first, s32 x, s32 y)
{
    const struct En3dPiece * p = &sEn3dPieces[first];
    for (;; p++)
    {
        struct OamAttrs * oam;
        if (sOam > OAM_LAST)
            return;
        oam = &gOamObjects[sOam++];
        oam->attr0 = SPRITE_ATTR0((y + p->dy) & 0xFF, ST_OAM_AFFINE_OFF, ST_OAM_OBJ_NORMAL, FALSE, ST_OAM_4BPP, p->shape);
        oam->attr1 = SPRITE_ATTR1_NONAFFINE((x + p->dx) & 0x1FF, FALSE, FALSE, p->size);
        oam->attr2 = SPRITE_ATTR2(TILE_BASE + p->tile, 2, PAL_UI);
        if (p->last)
            return;
    }
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
// rest off but the text box's
static void TakeScreen(void)
{
    struct IORegisters * io = &gIORegisters;
    u32 r, c;
    const u16 * map = (const u16 *)D(EN3D_GFX_MAP);
    CpuCopy32(gEn3dCodeStart, gEnMovieCode, gEn3dCodeEnd - gEn3dCodeStart);
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
            s32 vx = c - 1 - EN3D_VIEW_X / 8, vy = r - 1 - EN3D_VIEW_Y / 8;
            u16 t = (vx >= 0 && vx < EN3D_VIEW_W / 8 && vy >= 0 && vy < EN3D_VIEW_H / 8) ? ((vx & 1) | (vy & 1) << 1) : 0;
            ((u16 *)BG_SCREEN_ADDR(GRID_SCREEN))[r * 32 + c] = t | (GRID_PAL << 12);
        }
    DmaCopy16(3, D(EN3D_GFX_GRID), BG_CHAR_ADDR(GRID_CHAR), 4 * 32);
    ((u16 *)BG_PLTT)[GRID_PAL * 16 + 1] = EN3D_GRID_LINE;
    ((u16 *)BG_PLTT)[0] = EN3D_GRID_BG;
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
            gBG3MapBuffer[r * 32 + c] = (r >= 1 && r <= 20 && c >= 1 && c <= 30) ? map[(r - 1) * 30 + c - 1] : EN3D_VIEW_TILES;
    DmaCopy16(3, gBG3MapBuffer, BG_SCREEN_ADDR(31), 0x800);
    DmaCopy32(3, D(EN3D_GFX_FRAME), BG_CHAR_ADDR(1) + EN3D_VIEW_TILES * 64, EN3D_FRAME_TILES * 64);
    DmaCopy16(3, sEn3dFramePalette, BG_PLTT + EN3D_PAL_FRAME * 2, EN3D_FRAME_COLOURS * 2);
    DmaCopy16(3, D(EN3D_GFX_SPRITES), OBJ_VRAM0 + TILE_BASE * 32, EN3D_SPRITE_TILES * 32);
    DmaCopy16(3, sEn3dUiPalette, OBJ_PLTT + PAL_UI * 32, 32);
    ClearAll();
    DmaCopy32(3, sFb, BG_CHAR_ADDR(1), EN3D_VIEW_TILES * 64);
}

// everything as it was (the background decompressed again: the picture had
// its buffer)
static void GiveBackScreen(void)
{
    struct Main * main = &gMain;
    struct En3d * v = &gEn3d;
    u32 i;
    DecompressBackgroundIntoBuffer(main->currentBG);
    CopyBGDataToVramAndScrollBG(main->currentBG);
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
    StartHardwareBlend(2, 1, 1, 0x1F);
    SetMode(V_FADE_OUT);
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
        StartHardwareBlend(2, 1, 1, 0x1F);
        SetMode(V_FADE_LEAVE);
        return;
    case AFTER_BACK:
        v->afterSection = sc->back;
        v->sceneEnding = TRUE;
        StartHardwareBlend(2, 1, 1, 0x1F);
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
        StartHardwareBlend(2, 1, 1, 0x1F);
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
    switch (v->mode)
    {
    case V_FADE_OUT:
        if (main->blendMode != 0)
            return;
        SaveScreen();
        SetMode(V_SETUP);
        return;
    case V_SETUP:
        TakeScreen();
        ResetView();
        ShowRecord(v->record);
        v->uploadAll = TRUE;
        SetMode(V_FIRST);
        break;
    case V_FIRST:
        // (the first picture whole before the fade)
        if (v->render == R_IDLE && !v->dirty && !v->uploadReady)
        {
            StartHardwareBlend(1, 1, 2, 0x1F);
            SetMode(V_FADE_IN);
        }
        break;
    case V_FADE_IN:
        if (main->blendMode != 0)
            break;
        gIORegisters.lcd_bldcnt = BLDCNT_TGT1_BG1 | BLDCNT_TGT2_BG2 | BLDCNT_TGT2_BG3 | BLDCNT_TGT2_OBJ | BLDCNT_TGT2_BD | BLDCNT_EFFECT_BLEND;
        gIORegisters.lcd_bldalpha = BLDALPHA_BLEND(0x1F, 0x7);
        gIORegisters.lcd_bldy = 0;
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
        GiveBackScreen();
        v->render = R_IDLE;
        v->uploadReady = FALSE;
        v->closeup = v->closeupShown = 0;
        main->process[GAME_PROCESS_VAR1] = v->fromVar1;
        main->process[GAME_PROCESS_VAR2] = v->fromVar2;
        main->process[GAME_PROCESS_STATE] = RECORD_3D;
        StartHardwareBlend(1, 1, 2, 0x1F);
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
        return;
    }
    // the hover's how-to may have started a section above
    gIORegisters.lcd_bg3hofs = 8;
    gIORegisters.lcd_bg3vofs = 8;
    if (v->mode == V_SCRIPT || v->mode == V_ANIM || v->mode == V_TURN)
        v->hit = 0;
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

// ---------------------------------------------------------------- the script
// Script command 69: 69 0 n the record opened for scene n, 69 2<<8 | n
// close-up n shown in the viewer, 69 3<<8 taken away
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
    }
    return 0;
}

#endif

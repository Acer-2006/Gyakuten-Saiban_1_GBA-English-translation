// English patch, the RFTA build: the fifth episode's movies (the DS's script
// command 75 and its frame sequences: tools/en/rfta/movies.py), every frame
// at the DS's 30 a second, on BG3 in 16 colours.
//
// The DS's player (0x0206b0dc, its state at 0x020cdf3c) is followed: a
// position that moves a frame every other frame between a start and an end
// frame, forwards (state 1), backwards (4), held (3), stopped at the end and
// kept on screen (5, flag 0x4000) or going round (flag 0x8000), closed (2).
// On the frame the position moves the DS unpacks that frame, on the next it
// shows it. Here the changes that lead from the frame on screen to the one
// wanted are unpacked between the game's work and the sound (in the time the
// frame leaves: EN_BG_FRAME_END, as the background stripes), into EWRAM
// (packed in bytes) or VRAM after the slots (in words), by ARM code in IWRAM
// (en_movie_lz.s), and go into the slots in the vertical blank, top first.
#include "global.h"
#include "main.h"
#include "background.h"
#include "script.h"
#include "ewram.h"
#include "constants/process.h"
#include "en_rfta.h"

#if RFTA

struct EnMovieBlob
{
    u16 frames, flags, nKeys, nPals;
    u32 changes, keys, palIdx, pals, scroll, overlay;
};
#define BLOB_PAN 1                  // a scene wider than the screen, the slots 32 of its columns
#define BLOB_OVERLAY 2              // the time stamp drawn over it
#define CHANGE_XOR 1
#define CHANGE_WORDS 2

struct EnMovieKey
{
    u16 frame, flags;
    u32 offset;
};

struct EnMovieOverlay
{
    u8 x, y, height, colour;
    u16 count, phase;               // the second of frame k: (k + phase) / 30
    u8 rows[0];                     // each second's: height rows of 24 bytes
};

struct EnLz
{
    const u8 * src;
    u8 * dst;
    u8 * end;
    u32 flags;
    const u32 * lit;
};

enum { MV_IDLE, MV_UNPACKING, MV_READY };
enum { APPLY_COPY, APPLY_XOR, APPLY_KEY, APPLY_NONE };

struct EnMovie
{
    // the DS's
    u8 open;            // set up, until closed
    u8 seq;
    u8 tick;            // its +6: 0 the frame the position moves, 1 the frame it shows
    u8 phase;           // its +5: 0 a frame to unpack, 1 to show, 2 neither
    u16 flags;          // its +0x16: the state in the low four bits, 0x8000 round, 0x4000 hold, 0x2000
    s16 pos;            // its +0x10 (whole frames: the scripts keep the speed at 100)
    s16 start, end;     // its +0xc, +0xe
    s16 jump;           // its +0x14
    // the GBA's
    u8 state;           // MV_*
    u8 mode;            // APPLY_* for what was unpacked
    u8 words;           // unpacked in words (into VRAM) or bytes (EWRAM)
    u8 due;             // the DS has shown the frame: show it at the next vertical blank
    u8 taken;           // BG3 is the movie's (its control, map and colours saved)
    u8 hidden;          // a long way to the frame: black until it is there
    u8 vramLost;        // something else drew on BG3: unpack it all again
    u8 bgPending;       // the script changed the background: shown at the close
    s16 shown;          // the frame in the slots (-1: none)
    s16 goal;           // the frame to show
    s16 next;           // the frame the unpacked change leads to
    u16 slots;
    u16 bg;             // the background under the movie
    u16 saveBg3cnt;
    u16 saveBackdrop;
    u8 saveScrolling;
    u8 pad;
    u16 scroll;         // the panning movie's: the screen's left edge in the scene
    struct EnLz lz;
    const struct EnMovieBlob * blob;
};

// in the old script heap (ewram.h): the state, the byte buffer, BG3's map while the movie has it
#define gEnMovie (*(struct EnMovie *)(EWRAM_START + 0x11FC0 + 0xF000))
#define sMovieBuffer ((u8 *)(EWRAM_START + 0x11FC0 + 0x10000))       // 80 + 640 * 32 bytes
#define sMovieMapBackup ((u16 *)(EWRAM_START + 0x11FC0 + 0x15100))    // 0x800 bytes
#define SLOT_VRAM ((u32 *)BG_CHAR_ADDR(1))
#define VRAM_END (VRAM + 0xE000)    // (BG0's map from here)
#define MOVIE_PAL 2                 // BG palette 2 (the 16-colour backgrounds')
#define OVERLAY_ROW 17              // the time stamp's two rows of tiles

extern const struct EnMovieBlob * const gRftaMovies[];
extern const u8 gEnMovieCodeStart[];
extern const u8 gEnMovieCodeEnd[];
extern u32 gEnMovieCode[];          // IWRAM (Makefile: RFTA_IWRAM)

#define UnLz8 ((u32 (*)(struct EnLz *, u8 *))((u8 *)gEnMovieCode + 0))
#define UnLz32 ((u32 (*)(struct EnLz *, u8 *))((u8 *)gEnMovieCode + 4))
#define Apply ((void (*)(const void *, const void *, u32 *, u32))((u8 *)gEnMovieCode + 8))
struct EnOverlayArgs;
#define Overlay ((void (*)(const struct EnOverlayArgs *))((u8 *)gEnMovieCode + 12))

static inline const u8 * BlobAt(const struct EnMovieBlob * b, u32 offset)
{
    return (const u8 *)b + offset;
}

static u32 ChangeEntry(u32 frame)
{
    const struct EnMovieBlob * b = gEnMovie.blob;
    return ((const u32 *)BlobAt(b, b->changes))[frame];
}

static bool32 IsPan(void)
{
    return gEnMovie.blob->flags & BLOB_PAN;
}

// where the slots' tiles end: changes packed in words unpack after them
static u8 * Scratch(void)
{
    // the slots, a blank tile, and for the time stamp a tile a slot of its two rows
    return (u8 *)SLOT_VRAM + (gEnMovie.slots + 1 + (IsPan() ? 64 : 0)) * 32;
}

static bool32 Playing(void)
{
    u32 p = gMain.process[GAME_PROCESS];
    return p == COURT_PROCESS || p == INVESTIGATION_PROCESS || p == TESTIMONY_PROCESS
        || p == QUESTIONING_PROCESS || p == EVIDENCE_ADDED_PROCESS;
}

// ---------------------------------------------------------------- unpacking
static void StartUnpack(u32 entry, u32 mode, s32 next)
{
    struct EnMovie * m = &gEnMovie;
    const u8 * p = BlobAt(m->blob, entry & ~3);
    u32 size = *(const u32 *)p >> 8;
    m->mode = mode;
    m->next = next;
    m->words = (entry & CHANGE_WORDS) != 0;
    m->lz.flags = 0;
    if (m->words)
    {
        m->lz.src = p + 8;
        m->lz.lit = (const u32 *)(p + ((const u32 *)p)[1]);
        m->lz.dst = Scratch();
    }
    else
    {
        m->lz.src = p + 4;
        m->lz.dst = sMovieBuffer;
    }
    m->lz.end = m->lz.dst + size;
    m->state = MV_UNPACKING;
}

// the nearest keyframe to frame f that can lead to it (a movie of XOR
// changes runs both ways from one)
static const struct EnMovieKey * NearestKey(s32 f)
{
    const struct EnMovieBlob * b = gEnMovie.blob;
    const struct EnMovieKey * k = (const struct EnMovieKey *)BlobAt(b, b->keys), * best = k;
    u32 i;
    for (i = 0; i < b->nKeys; i++, k++)
    {
        s32 d = f - k->frame, bd = f - best->frame;
        if (d < 0 && !IsPan())
            continue;
        if (d < 0)
            d = -d;
        if (bd < 0)
            bd = -bd;
        if (d < bd)
            best = k;
    }
    return best;
}

// the next step from the frame shown towards the goal
static void PlanStep(void)
{
    struct EnMovie * m = &gEnMovie;
    s32 goal = m->goal, shown = m->shown, dist;
    const struct EnMovieKey * k = NearestKey(goal);
    s32 kd = goal - k->frame;
    if (kd < 0)
        kd = -kd;
    dist = goal - shown;
    if (shown >= 0 && !m->vramLost && (dist == 1 || (dist == -1 && (ChangeEntry(shown) & CHANGE_XOR) && IsPan())
        || (dist > 1 && dist <= kd) || (dist < -1 && IsPan() && -dist <= kd)))
    {
        u32 e;
        if (dist > 0)
        {
            e = ChangeEntry(shown + 1);
            m->hidden = dist > 1;
            if (e == 0)
            {
                m->next = shown + 1;
                m->mode = APPLY_NONE;
                m->state = MV_READY;
            }
            else
                StartUnpack(e, (e & CHANGE_XOR) ? APPLY_XOR : APPLY_COPY, shown + 1);
        }
        else
        {
            e = ChangeEntry(shown);         // (an XOR change undoes itself)
            m->hidden = dist < -1;
            if (e == 0)
            {
                m->next = shown - 1;
                m->mode = APPLY_NONE;
                m->state = MV_READY;
            }
            else
                StartUnpack(e, APPLY_XOR, shown - 1);
        }
        return;
    }
    m->hidden = k->frame != goal;
    StartUnpack(k->offset | k->flags, APPLY_KEY, k->frame);
}

// cycles an unpacked byte (tools/en/rfta/movies.py: CYCLES_BYTE, CYCLES_WORD), a little over
#define LINE_CYCLES 1232
#define CHUNK 1024

void EnMovieWork(void)
{
    struct EnMovie * m = &gEnMovie;
    if (!m->open || m->blob == NULL || !Playing())
        return;
    if (m->state == MV_IDLE && m->goal != m->shown)
        PlanStep();
    while (m->state == MV_UNPACKING)
    {
        u32 now = EnLinesSinceVBlank();
        u32 lines = now + gEnSoundLines + 2;
        u32 cyclesPerByte = m->words ? 5 : 16;
        u32 budget;
        if (lines >= EN_BG_FRAME_END)
            break;
        budget = (EN_BG_FRAME_END - lines) * LINE_CYCLES / cyclesPerByte;
        if (budget > CHUNK)
            budget = CHUNK;
        if (budget < 64)
            break;
        if ((m->words ? UnLz32 : UnLz8)(&m->lz, m->lz.dst + budget))
            m->state = MV_READY;
    }
}

// ---------------------------------------------------------------- the screen
static void WriteMap(void)
{
    // movie row r at map row r + 1, column c at c + 1 (BG3's offsets are
    // 8, 8 with no shake); the margins on a blank tile
    struct EnMovie * m = &gEnMovie;
    u16 * map = gBG3MapBuffer;
    u32 r, c, blank = m->slots | (MOVIE_PAL << 12);
    for (r = 0; r < 32; r++)
        for (c = 0; c < 32; c++)
        {
            u32 v = blank;
            if (r >= 1 && r <= 20)
            {
                if (IsPan())
                    v = ((r - 1) * 32 + ((c - 1) & 31)) | (MOVIE_PAL << 12);
                else if (c >= 1 && c <= 30)
                    v = ((r - 1) * 30 + c - 1) | (MOVIE_PAL << 12);
            }
            map[r * 32 + c] = v;
        }
    DmaCopy16(3, map, BG_SCREEN_ADDR(31), 0x800);
}

static void TakeBg3(void)
{
    struct EnMovie * m = &gEnMovie;
    struct IORegisters * io = &gIORegisters;
    if (m->taken)
        return;
    m->taken = TRUE;
    m->saveBg3cnt = io->lcd_bg3cnt;
    m->saveBackdrop = *(vu16 *)BG_PLTT;
    m->saveScrolling = gMain.isBGScrolling;
    gMain.isBGScrolling = FALSE;
    DmaCopy16(3, gBG3MapBuffer, sMovieMapBackup, 0x800);
    io->lcd_bg3cnt &= ~BGCNT_256COLOR;
    REG_BG3CNT = io->lcd_bg3cnt;
    DmaFill32(3, 0, (u8 *)SLOT_VRAM + m->slots * 32, 32);       // the blank tile
    WriteMap();
}

static void GiveBackBg3(void)
{
    struct EnMovie * m = &gEnMovie;
    if (!m->taken)
        return;
    m->taken = FALSE;
    DmaCopy16(3, sMovieMapBackup, gBG3MapBuffer, 0x800);
    gIORegisters.lcd_bg3cnt = m->saveBg3cnt;
    *(vu16 *)BG_PLTT = m->saveBackdrop;
    gMain.isBGScrolling = m->saveScrolling;
    CopyBGDataToVram(gMain.currentBG);
}

static void SetColours(s32 frame)
{
    const struct EnMovieBlob * b = gEnMovie.blob;
    const u16 * pal = (const u16 *)BlobAt(b, b->pals) + 16 * ((const u16 *)BlobAt(b, b->palIdx))[frame];
    if (gEnMovie.hidden)
    {
        DmaFill16(3, 0, BG_PLTT + MOVIE_PAL * 32, 32);
        *(vu16 *)BG_PLTT = 0;
        return;
    }
    DmaCopy16(3, pal, BG_PLTT + MOVIE_PAL * 32, 32);
    *(vu16 *)BG_PLTT = pal[0];          // (colour 0 is see-through: the backdrop shows it)
}

// the time stamp over the security footage: the slots under it, in its two
// rows, are copied to tiles of their own with its white pixels drawn in
// (en_movie_lz.s: about 6 lines of the vertical blank)
static const u16 sNibbles[16] = {
    0x0000, 0x000F, 0x00F0, 0x00FF, 0x0F00, 0x0F0F, 0x0FF0, 0x0FFF,
    0xF000, 0xF00F, 0xF0F0, 0xF0FF, 0xFF00, 0xFF0F, 0xFFF0, 0xFFFF,
};

struct EnOverlayArgs
{
    const u8 * rows;
    u32 * slots;
    u32 * own;
    u16 * map;
    u16 * mapBuf;
    u32 scroll;
    u32 colour;
    s32 y0;
    u32 height;
    u32 ownMap;
    u32 slotMap;
    const u16 * lut;
};

static void DrawOverlay(s32 frame, u32 scroll)
{
    const struct EnMovieBlob * b = gEnMovie.blob;
    const struct EnMovieOverlay * o = (const struct EnMovieOverlay *)BlobAt(b, b->overlay);
    struct EnOverlayArgs a;
    u32 sec = (frame + o->phase) / 30;
    if (sec >= o->count)
        sec = o->count - 1;
    a.rows = o->rows + sec * o->height * 24;
    a.slots = SLOT_VRAM;
    a.own = SLOT_VRAM + (gEnMovie.slots + 1) * 8;
    a.map = (u16 *)BG_SCREEN_ADDR(31) + (OVERLAY_ROW + 1) * 32;
    a.mapBuf = gBG3MapBuffer + (OVERLAY_ROW + 1) * 32;
    a.scroll = scroll & 255;
    a.colour = o->colour * 0x11111111;
    a.y0 = OVERLAY_ROW * 8 - o->y;
    a.height = o->height;
    a.ownMap = (gEnMovie.slots + 1) | (MOVIE_PAL << 12);
    a.slotMap = (OVERLAY_ROW * 32) | (MOVIE_PAL << 12);
    a.lut = sNibbles;
    Overlay(&a);
}

// the vertical blank: the unpacked change into the slots, the frame's colours and place
void EnMovieVBlank(void)
{
    struct EnMovie * m = &gEnMovie;
    const struct EnMovieBlob * b = m->blob;
    s32 frame;
    if (!m->open)
        return;
    if (m->taken && IsPan())        // (every frame: the registers are written every frame without it)
        REG_BG3HOFS = gIORegisters.lcd_bg3hofs + m->scroll;
    if (m->state != MV_READY || !Playing() || !(m->due || m->hidden || m->mode == APPLY_KEY))
        return;
    TakeBg3();
    if (m->mode != APPLY_NONE)
    {
        const u8 * src = m->words ? Scratch() : sMovieBuffer;
        Apply(src, src + 80, SLOT_VRAM, m->mode | (m->slots << 8));
    }
    if (m->mode == APPLY_KEY)
        m->vramLost = FALSE;
    frame = m->shown = m->next;
    m->state = MV_IDLE;
    if (m->shown == m->goal)
    {
        m->hidden = FALSE;
        m->due = FALSE;
    }
    SetColours(frame);
    if (IsPan())
    {
        m->scroll = ((const s16 *)BlobAt(b, b->scroll))[frame];
        REG_BG3HOFS = gIORegisters.lcd_bg3hofs + m->scroll;
        if (b->flags & BLOB_OVERLAY)
            DrawOverlay(frame, m->scroll & 255);
    }
}

// ---------------------------------------------------------------- the DS's player
static void Close(void)
{
    struct EnMovie * m = &gEnMovie;
    GiveBackBg3();
    DmaFill32(3, 0, m, sizeof(*m));
}


// once a frame (the DS's 0x0206b0dc)
void EnMovieFrame(void)
{
    struct EnMovie * m = &gEnMovie;
    u32 state;
    if (!m->open || !Playing())
        return;
    state = m->flags & 0xF;
    if (state == 2)
    {
        Close();
        return;
    }
    if (state == 1 || state == 4 || state == 3)
    {
        if (m->tick == 0)
        {
            m->phase = 0;
            if (state == 1)
                m->pos++;
            else if (state == 4)
                m->pos--;
            if ((state == 1 && m->pos > m->end) || (state == 4 && m->pos < m->start)
                || (state == 3 && m->pos < m->start))
            {
                m->pos = state == 4 ? m->start : m->end;
                if (state == 3)
                    m->pos = m->start;
                if (m->flags & 0x8000)
                    m->pos = state == 4 ? m->end : m->start;
                else
                {
                    m->phase = 2;
                    m->flags = (m->flags & ~0xF) | ((m->flags & 0x4000) ? 5 : 2);
                    return;
                }
            }
            m->tick = 1;
        }
        else
        {
            if (m->flags & 0x2000)
                m->flags = (m->flags & ~0x200F) | 3;
            m->phase = 1;
            m->tick = 0;
        }
    }
    else if (state == 5)
        m->phase = 2;
    if (m->phase == 0)
    {
        if (m->jump)
        {
            m->pos = m->jump;
            m->jump = 0;
        }
        m->goal = m->pos;
    }
    else if (m->phase == 1)
        m->due = TRUE;
}

// the wait (75 6, the DS's 0x0206a6d4): the end (or the start, backwards) reached
static bool32 Busy(void)
{
    struct EnMovie * m = &gEnMovie;
    u32 state = m->flags & 0xF;
    if (!m->open || state == 5 || m->flags == 0)
        return FALSE;
    if (state == 4)
        return m->pos != m->start;
    return m->pos != m->end;
}

static void Open(u32 seq, u32 flags)
{
    struct EnMovie * m = &gEnMovie;
    if (m->open)
        Close();
    DmaFill32(3, 0, m, sizeof(*m));
    CpuCopy32(gEnMovieCodeStart, gEnMovieCode, gEnMovieCodeEnd - gEnMovieCodeStart);
    m->open = TRUE;
    m->seq = seq;
    m->blob = gRftaMovies[seq];
    m->flags = flags;
    m->end = m->blob->frames - 1;
    m->shown = -1;
    m->goal = 0;
    m->slots = IsPan() ? 640 : 600;
    m->bg = gMain.currentBG;
}

// GBA command 65 sub a b: the DS's 75 (tools/en/rfta/translate.py)
bool32 Command65(struct ScriptContext * scriptCtx)
{
    struct EnMovie * m = &gEnMovie;
    u32 sub = scriptCtx->scriptPtr[1], a = scriptCtx->scriptPtr[2], b = scriptCtx->scriptPtr[3];
    switch (sub)
    {
    case 0:                         // set up: the sequence, the flags
        Open(a, b);
        break;
    case 1:                         // the state (the low four bits: the tick starts again) and flags
        if (a & 0xF)
        {
            m->flags &= ~0xF;
            m->tick = 0;
        }
        m->flags |= a;
        break;
    case 2:                         // to frame a
        m->jump = (s32)a > m->end ? m->end : a;
        break;
    case 3:                         // the speed (100: a frame a frame); always 100 in the scripts
        break;
    case 4:
        m->start = a == 0xFFFF ? 0 : a;
        break;
    case 5:
        m->end = m->blob && a > m->blob->frames - 1 ? m->blob->frames - 1 : a;
        break;
    case 6:                         // until the movie is at its end
        if (Busy())
            return 1;
        break;
    }
    scriptCtx->scriptPtr += 4;
    return 0;
}

// a background change while the movie is up waits for its close
bool32 EnMovieDefersBg(void)
{
    if (!gEnMovie.open)
        return FALSE;
    gEnMovie.bg = gMain.currentBG;
    gEnMovie.bgPending = TRUE;
    return TRUE;
}

// CopyBGDataToVram while the movie is up: the background under it is the
// movie's to show (a screen that drew over it, the Court Record's or the save
// screen's, putting it back): the movie is shown again instead; anything
// else draws over the movie, which then has to be unpacked again
bool32 EnMovieTakesBg(u32 bg)
{
    struct EnMovie * m = &gEnMovie;
    if (!m->open || !m->taken)
        return FALSE;
    if ((bg & ~0x8000) == m->bg)
    {
        gIORegisters.lcd_bg3cnt &= ~BGCNT_256COLOR;
        REG_BG3CNT = gIORegisters.lcd_bg3cnt;
        gMain.isBGScrolling = FALSE;
        WriteMap();
        if (m->vramLost)
        {
            m->state = MV_IDLE;     // (whatever was being unpacked is for slots that are gone)
            m->goal = m->pos;
        }
        else if (m->shown >= 0)
            SetColours(m->shown);
        return TRUE;
    }
    m->vramLost = TRUE;
    return FALSE;
}

void EnMovieReset(void)
{
    DmaFill32(3, 0, &gEnMovie, sizeof(gEnMovie));
}

#endif // RFTA

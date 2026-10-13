# Rise from the Ashes on the GBA — stage 1: what it is made of

The fifth episode of the DS release does not exist on the GBA. Bringing it
over would be an optional second patch (a 32 MB ROM) on top of the English
backport. This is the inventory that decides how: exact counts from the DS
data on hand (`mes_all.bin`, `data.bin`, `sound_data.sdat`, the ARM9
binary), what each new piece of the DS engine does, and what the GBA side
would have to grow. Everything here was measured with the tools in
`tools/en/rfta/` (see the end); nothing is from memory.

Short version: the episode is roughly three quarters of the base game in
text, brings six new characters and 68 new backgrounds, and leans on seven
DS-only systems — a partner portrait, a movie player, a second fade system,
bottom-screen panels, and the luminol / fingerprint / 3D-evidence
mechanics. The script engine itself needs eleven new commands and about a
hundred new variants of commands the DS already used in episodes 1–4. None
of it is blocked by the GBA. The one hard number is the security-camera
video: 1,420 frames, 22.6 MB compressed on the DS, which does not fit next
to the 13.2 MB the current ROM uses in a 32 MB cartridge without being cut
down (fewer frames per second or a smaller picture).

## 1. The script

| | episodes 1–4 | Rise from the Ashes |
|---|---|---|
| chapter files | 17 | 19 (18 chapters + one shared file) |
| sections | 2,279 | 1,523 |
| letters of dialogue | 679,021 | 493,366 |
| choices (08/09) | 161 | 33 |
| script bytes, decompressed | 1,992,802 | 1,482,558 |

The DS splits the episode into 18 chapters (its save titles: "Day 1 -
Investigation" twice, "Day 2 - Trial Former" twice, "Day 2 - Trial Latter",
and so on to "Final Day - Trial Latter2" twice). Three of the splits are
seamless, mid-scene: the script switches chapter file with command `6A`
(below) and no save prompt. The 19th file holds the lines spoken while
examining evidence in three dimensions ("So this is what the back of the
badge looks like!"), shared by every chapter.

The DS script engine has 128 command slots. Episodes 1–4 use 82 of them
(72 of the GBA's 00–4C, and the DS's own 4D, 4E, 5D, 65, 69, 6B, 6F, 74,
78, 7A). The fifth episode uses 88: eleven that episodes 1–4 never touch,
and new variants of the DS-only ones. Argument counts were read off the ARM9 handlers (`dsbin.py`) and
checked by parsing every section of the episode: no token left over, no
command landing inside text.

### Commands only the fifth episode uses

| op | args | uses | what it does | GBA plan |
|---|---|---|---|---|
| `76` | side, portrait / `2 0` | 281 | partner portrait plate: a 64×64 picture of Ema (12 expressions) or Gumshoe (6) at the side of the text box while the partner talks during investigations; `76 2 0` takes it down. Same machinery as the evidence plate (`13`), a second picture table at data.bin 0x1bb3074. | the evidence plate code with a second picture table |
| `5F` | mode, step, level | 246 | the DS's second fade system, a 23-mode software palette fade (`5F 3 1 1f` fades in from white, 171 uses; `5F 4 1 1` fades to black, 71). Used for the flashback stills and scene changes the first four episodes did with hardware blends (`12`). | map onto `12` hardware blends with the same timing |
| `5C` | mode, step, level | 22 | the same fade, holding the script until it is over | same, waiting |
| `75` | kind, value, 0, 0 | 137 | movie player: plays a frame sequence from data.bin — the opening cinematic, the Blue Badger's dance, the security-camera footage (section 3). `75 5 n` picks a sequence, `75 1 f` sets flags, `75 6` starts, `75 0 0 n 1` clears, `75 2/4 n` set positions (the video scrubber). | a GBA frame player (streamed from ROM) |
| `74` | kind, value | 241 (208 in variants episodes 1–4 never use) | bottom-screen UI: `74 5 0` puts the normal panel back (77 uses, after a portrait or a prompt), `74 8 n` shows panel n (17 panels, ids 0x2e–0x49; they follow "Court Record!" lines and evidence being added, and the tutorial), `74 d n` (18 values, in the touch tutorial), `74 a n` after questions that want an answer presented (profiles, prints), `74 9 n` / `74 6 n` / `74 c` / `74 b` around the luminol and fingerprint scenes — these readings are from the dialogue around them and still to be watched in the emulator. | most become nothing (one screen); the prompts become GBA prompts; the tutorial panels become text boxes |
| `55` | background, 9 | 21 | shows background n over the scene for a moment and puts the previous one back (flashes and cut-ins) — the handler swaps `gMain.currentBG`, waits for the background system, restores it | a short background swap; to confirm in the emulator |
| `68` | — | 23 | sets flag 0x400 in the DS's game flags: the plate on screen fades together with the scene | part of the fade mapping |
| `7B` | 1=close, picture | 12 | in the shared evidence-examination file only: shows close-up picture n (0–2: the badge's number, the bloodstain, the sketch) over the 3D view and waits for the player to close it | a close-up picture |
| `6A` | chapter file | 3 | continues in chapter file n (the seamless Former/Latter splits) | nothing (the GBA scripts run from ROM; the files can be joined) |
| `79` | — | 7 | the same handler as `15` (end of section), used after the `74 a` present prompts | `15` |
| `77` | sound, 0x78 | 2 | a sound-effect call with a length (`77 196 78`, `77 3f 78`) | a sound effect |

Two GBA commands the first four episodes never issue appear as well: `49`
(to the title screen, after the credits) and `11` (open the Court Record to
present).

Our English patch already took opcodes `5E` (choice labels) and `5F`
(game-over check) for its own use; `5D` (centre) is the DS's own. The DS's
`5F` is the fade above, so ours would move to free slots (`60`–`64` are
unused on the DS).

### DS-only commands the port has no model for yet

The porter for episodes 1–4 is an aligner: it lays the DS script over the
GBA script and takes the GBA's commands wherever the two match, so it never
had to know what the DS's own commands do beyond a handful (`4E` waits,
`5D` centring, `69 62 243` plate hide, the gavels, `7A`). The fifth episode
has no GBA script to align with: every command must be translated. The
DS-only families it uses, with the variants episodes 1–4 never use:

| op | uses | variants new to this episode | what they are |
|---|---|---|---|
| `69 62 n` / `69 4xx n` | 841 | 31 variants, 133 uses | on-screen objects and effects (gavels, the plate, pointers, flashes) |
| `6B` | 354 | 19 variants, 50 uses | person/animation preloads and positions |
| `6F` | 26 | 10 variants | background preloads (ids 0x86–0xb2) |
| `78` | 49 | 17 variants | per-section settings, one argument |
| `7A` | 30 | 8 variants | game-over checks |
| `65` | 29 | 1 variant | — |
| `4D`, `4E` | 130, 1,283 | none | visitors' room, waits (already handled) |

Finding out what each variant does is emulator work (`dsrun.py` logs every
command the DS runs with both screens photographed); the first four
episodes give a cross-check, because for them we know which GBA command
stood in the same place.

## 2. People, pictures, sound

**Characters.** Six new sprite sets: persons 0x2c, 0x2d, 0x2e, 0x2f, 0x31,
0x32 (Ema, Lana, Marshall, Meekins, Gant, Angel Starr), with 139 animation
numbers between them (talk/idle pairs, so about 70 poses; Gant, Angel
Starr and Meekins also appear as 0x4000/0x8000 variants of their person
number, as Gumshoe does in episodes 1–4). Edgeworth and Gumshoe get a few
new poses (6 animation numbers). Ten new name tags
(persons 0x2c–0x35; Goodman, Darke, Neil Marshall and the Blue Badger are
names and stills only). 18 partner portraits (above).

The DS keeps every animation of the episode in one archive (data.bin
0x2202220: 562 entries, 3.25 MB, in pairs: a graphics block, then a frame
block), in the GBA's own animation format; stage 3 (section 8) converted the
new people from it.

**Backgrounds.** 68 new (ids 0x71–0xf0 with gaps; 93 used in all). The DS
backgrounds are 256×192; the port's existing tooling (`port_backgrounds.py`)
reads them and already handles the 240×160 framing.

**Evidence.** 81 new items and 9 new profiles. The DS evidence table has
209 entries where the GBA's has 108, in the same 0x18-byte layout (found at
ARM9 0x020ab048). 60 new Court Record pictures (the DS has 147, 64×64, same
format as the portraits), 20 new detail pages (the "Check" screens, ids
12–33), English descriptions and names in the same DS archives
`make_descriptions.py` already reads.

**Per-chapter tables.** The present responses, talk topics, rooms, examine
hotspots and starting Court Record of each chapter are data in the ARM9,
in the GBA's own formats (the first four episodes' tables are byte for byte
the GBA's; the chapter pointer tables run to 35 entries, e.g. the
court-present table at 0x020b42a8). They can be extracted. The per-chapter
setup code (room and flag setup, a few dozen lines each on the GBA) would
be read out of the ARM9 and rewritten.

**Sound.** 7 new music tracks (BGM150–155 and the jingle BGM156: 579 KB of
new DS instrument samples over the shared bank) and 57 new sound-effect
slots (SE0B0–SE0E8), 28 of them used by the scripts. The DS sequences are SSEQ; the GBA plays
MusicPlayer2000 songs, so each track is a conversion (sequence to MIDI to
m4a, instruments remapped to GBA samples) — the one place where the result
is an arrangement rather than a copy.

## 3. The DS-only systems

| system | where in the episode | what the DS does | on the GBA |
|---|---|---|---|
| partner portrait | every investigation line Ema (or Gumshoe) says | 64×64 face by the text box | the plate code; cheap |
| movies | opening (329 frames), Blue Badger dance (450 frames, 256×160), ending montage (270 frames), security footage (1,420 frames, scrubbed by the player in the Day 3 trial) | 4bpp 256-wide frames, RLE or LZ: 0.85 + 1.8 + 2.4 + 22.6 MB compressed | a frame player streaming from ROM; the three short ones fit as they are (≈4.5 MB after re-encoding); the footage needs a decision: at 240×160 and 10 fps it is ≈8 MB, at full rate it does not fit |
| luminol | Day 2 investigation (the evidence room, the parking lot) | spray by touch, reaction appears where sprayed | cursor + button spraying over the same picture |
| fingerprinting | Day 2–3 investigation (the lockers, the jar) | pick a powder, dust by touch, blow into the mic | cursor + button dusting, a button to blow |
| 3D evidence | the Court Record's Check on the badge, the pieces with the bloodstain, the sketch and others; lines in the shared file | rotate a model, hotspots trigger the shared sections, `7B` close-ups | pre-rendered views (one axis, 24–36 angles each; the hotspots become angle ranges); the model data is a custom format not yet located in data.bin |
| bottom-screen panels | tutorial, prompts (`74`) | second screen | text boxes and prompts on the one screen |
| second fade system | 268 fades | software palette fades | hardware blends |

The touch and microphone wording in the dialogue ("Touch the screen to
spray it on", "blow away the extra!") is a handful of lines and would be
reworded for buttons — the only deliberate departure from the DS text.

## 4. What grows on the GBA side

- Chapter tables sized 17 go to 35: script sizes, start process, game-over
  sections, initial Court Record, court/investigation present data, talk
  data, room data, examine data, the three per-chapter function tables.
- `roomData[24]` goes to at least 27 (rooms 0x16, 0x18, 0x1a are new).
- The evidence table 108 → 209 entries; pictures, descriptions, detail
  pages to match.
- Episode select: a fifth entry. The DS's own screen is a different design
  (one episode at a time, artwork on the top screen, arrows and Confirm);
  the GBA list gains a row. `caseEnabledFlags` keeps one bit per episode on
  the GBA; the DS changed it to a count in the high nibble (0x50 = all five),
  which is what unlocks the episode after Turnabout Goodbyes.
- The transition after episode 4 is already the DS's: the end-of-credits
  command saves and shows "A brand new Episode has been added." when a
  chapter 17 exists; the code added for v0.7.54 only covers its absence.
- Save data: the same `SaveData` layout fits (chapter index is a byte,
  flags are 256 per set); a save made in the fifth episode is simply a
  chapter 17–34 save.
- ROM: 13.2 MB used of 16 now; the cartridge maximum is 32 MB (mGBA and
  flash carts take it). Estimate of the added data after conversion: script
  1.5 MB, backgrounds 2.7 MB, sprites 1.5 MB, evidence pictures and
  descriptions 2.5 MB, portraits and close-ups 0.1 MB, three short movies
  4.5 MB, pre-rendered 3D views ≈1 MB, music and samples ≈0.5 MB — about
  14 MB, which leaves ≈5 MB for the security footage. That is the budget the
  video has to meet.
- RAM: nothing new has to live in EWRAM (frames stream from ROM; the VWF
  already took the old 108 KB script heap).

## 5. What the current tools cannot do, and what is missing

- `port_script.py` aligns; the episode needs a translator that emits a
  GBA script from the DS script alone, implementing or dropping every DS
  command and variant in section 1.
- No decoder for the DS animation archive (or a recorder as fallback).
  (Stage 3 found it is the GBA's own format: section 8.)
- No SSEQ → m4a path.
- No GBA code for: portrait plate, frame player, luminol, fingerprinting,
  3D views, close-ups, the fifth episode-select entry; and the eleven new
  script commands.
- The 3D model data has not been found in data.bin (no Nitro BMD0 headers;
  a Capcom format), and `55`, `68`, `77` and the `74`/`75` variants are
  read from the code and script contexts, not yet watched in the emulator.

## 6. Stages

1. **Inventory and decoding** — this document, the tools below. Done.
2. **Translator and framework** — the DS → GBA script translator with every
   command accounted for (new variants confirmed in the emulator), the
   chapter tables extracted from the ARM9, tables widened, episode select,
   backgrounds, evidence, portraits. Milestone: the episode plays start to
   end on the GBA with placeholder sprites and without the mechanics.
3. **Characters** — the animation data decoded or recorded, six sprite
   sets converted.
4. **Mechanics** — frame player (and the footage decision), luminol,
   fingerprints, 3D views, close-ups, prompts.
5. **Sound** — seven tracks and the effects.
6. **Playthrough and release** — the sweep and audit tools extended to
   chapters 17–34, a fourth BPS for the 32 MB ROM.

Each stage leaves something visible, and the work stays on `work-branch`.

## 7. Stage 2: the episode on the GBA, without the DS's systems

`make RFTA=1` builds `pwaa1_rfta.gba` next to the base ROM; the base build
is untouched (its checksum is checked after every change). In it:

- **Episode select.** A fifth row, *Rise from the Ashes*, with the DS's
  English title plate; it starts chapter 17 (`en_rfta_episodes.c`).
- **Script.** `translate.py` writes the 18 chapter files and the shared
  evidence-examination file from the DS scripts alone. Two new GBA commands:
  `60 n` (go on in chapter file n: the DS's `6A`) and `61 n` (go on in
  section n). The DS's in-section jumps (`35`, 815 of them) are remapped to
  the translated offsets, its `78` jumps go through the section table as
  the GBA's `36`.
- **Tables.** Court and investigation present data, initial Court Records,
  start processes and game-over sections come out of the ARM9
  (`arm9_tables.py`); the room, talk and examine tables and the room code
  are decompiled from the DS's per-chapter functions (`rooms.py`). Examine
  areas are moved from DS screen space (the DS pictures' margin) and are
  kept in ROM by table number (`gMain.unk8B`), as some rooms have up to 27.
- **Pictures and text.** The 68 new backgrounds, the Court Record pictures
  and descriptions, the name tags, the Move/Talk plates, the "point at it"
  pictures (`spots.py`; the text box makes way when the spot is low).
- **People and songs.** The six new people were played by stand-ins until
  stage 3 (section 8); the seven new songs play stand-ins until stage 5.
- **The engine, where the DS's differs.** A fifth-episode chapter starts
  the DS's way: script flags 0–0x27 belong to the episode and carry over
  (a few are cleared on the day they belong to), 0x28 and up start clear
  (the GBA cleared all of them and set 0x41, which is a story flag here;
  the first episode's examine check on it is kept to episodes 1–4). The
  third investigation ends in its first file, and the chapter after it is
  the final day's (28 → 31, as the DS's `16`). In the record's present
  mode, R turns to the profiles (the GBA never asks for a person).

What the DS's own systems do is, for now, skipped: where the DS hands over
to one of them and that system then starts a section, the GBA goes on in
the section the DS starts on success (`translate.py`, `BYPASS`):

| where | DS system | goes on in |
|---|---|---|
| Day 1 investigation | the wallet turned over in 3D, the phone's redial | the ID card, the call |
| Day 2 trial | the knife opened in 3D | the knife added |
| Day 2 investigation | luminol in the parking lot | the stain, what is odd about it |
| Day 2 investigation | luminol in the evidence room (the three stains the day waits for) | the stains' lines, from the shared file, after the handprint on the locker |
| Day 2 investigation | the jar pieces put together | the Unstable Jar |
| Day 2 investigation | dusting the handprint, matching the print; dusting the wiped stain | the glove print, Gumshoe's prints; Marshall's prints |
| Day 3 trial | pointing at the security tape (twice in each half) | the answer's section (the DS's frame table at 0x020c09cc) |
| Day 3 investigation | the locker number, dusting the cloth, the jar's last piece | Gant's number, Ema's prints, the piece fits |
| Final day | the jar turned to the Badger's angle, joining the dots | the Badger, "Ema" |
| Final day | finding the picture on the back of the list | the picture |
| The end | the staff roll | "The End", the title screen |

The questions answered with a person's profile ("What is this person's
name?", the DS's `74 A n`) stay questions: they become the GBA's present
prompt `21`, with the answers from the DS's table at 0x020b1324 added to the
court present data (a wrong answer goes to the next section, as on the DS).
Movies, the partner portrait, the bottom-screen panels and the second fade
system are left out (the dialogue around them stands).

**Checking it.** An autoplayer (outside the repository: it drives the test
harness) reads through the script and takes the decisions itself: it talks
through the topics, presents what the present tables name, examines every
area, moves everywhere, and tries each answer of a choice, a spot and a
present from a savestate, keeping the one that costs no health and leads
somewhere new. It saves at every save prompt, so a rebuilt ROM continues
from the same point (the GBA's own save, loaded with Continue). That is
how the stalls above were found and how the bypasses were checked. On the
current build it plays the episode from the Day 1 investigation through
the final day's verdict and the epilogue to the title screen (about 3,000
decisions), which is stage 2's milestone.

## 8. Stage 3: the people

Ema Skye, Lana Skye, Jake Marshall, Mike Meekins, Damon Gant and Angel
Starr are the DS's own, and Edgeworth has the two looks the DS gave him
(`characters.py`; 131 animations and two versions of Angel Starr's for her
box lunches, 3,337 frames). So are the people in the courtroom's wide shot
and Angel Starr's box lunches (`effects.py`).

**What the DS has.** The fifth episode's animations are one data.bin
archive (0x2202220) in the GBA's own animation format: a graphics block
(palettes, then RLE tiles behind an offset table) and a frame block holding
several animations, for each pair of entries. The ARM9 table at 0x020a8d4c
gives every animation number of the scripts (the `1E` arguments: Ema's are
0x178–0x197, Lana's 0x198–0x1AC, Meekins's 0x1AD–0x1BC, Angel Starr's
0x1BD–0x1CC, Marshall's 0x1CD–0x1E4, Gant's 0x1E5–0x1F8) its pair and its
offset in the pair's frame block. A GBA person is one graphics file and one
frame file, and an animation names its graphics block by an offset into the
graphics file, so a person's pairs join up as they are. The people keep
their DS person numbers (0x2C–0x32, added to `gPersonAnimData` in the RftA
build); the translator turns their animation numbers into offsets in their
files, the room code and the talk and present tables name them as the DS
does. Their two palettes go to OBJ palettes 14 and 15.

**What the GBA has no room for.** A person's tiles are copied to OBJ VRAM
for every frame, into the 320 tiles above `OBJ_VRAM0+0x5800`; the rest of
OBJ VRAM is the interface's, and the evidence plate, the speech bubbles and
the testimony banners appear with the people. The DS had more, and drew its
frames with large sprites: as the DS has them, most of Marshall's, Gant's,
Meekins's and Angel Starr's frames are over. So for each frame:

- the sprites wholly off the GBA's screen go (beyond the DS screen's width,
  which the courtroom pans can bring in, or above or below);
- a frame still over 320 tiles or 39 sprites is drawn again with sprites
  fitted to its pixels (8-pixel cells, each palette apart, the tightest
  cover that fits); the new sprites' tiles are new entries in the pair's
  graphics block, identical ones stored once;
- where even the pixels are more than 320 cells (some of Gant's and
  Marshall's frames, up to 466), cells go from the bottom up, the outermost
  of the lowest row first.

**What the DS draws on top.** Two of the people are more than their own
animations:

- Jake Marshall's poses 0x1CF–0x1DB start a second animation with them
  (the DS's 0x02022f18: animations 0x1C–0x26 of its effect table at
  0x020a984c): his red bandana and what he has in his hand (the knife he
  shaves with, the flask), at his origin, frame for frame with the pose or
  held. It uses his own palettes, so `characters.py` draws it into those
  poses, in front of him (217 frames).
- Angel Starr's box lunches (effects 0x27–0x3B, one per lunch) are started
  by the script right after her poses 0x1CA/0x1CB, laid over the box she
  holds out, and end with the next pose (the DS's 0x02022338 ends them).
  They have their own palette, so they stay animations of their own
  (`effects.py`, the GBA's 0x45–0x59, palette 13, the speech bubbles': no
  bubble comes while a lunch is out). Their tiles take the last 0xE80 bytes
  of the person's VRAM, and the two poses have a second version for when a
  lunch follows (`characters.json`: 0x10000 | pose) with that much less
  room and without the 50 cells every lunch box covers; the translator
  picks it when a lunch follows the `1E`. The engine moves a lunch with
  Angel Starr (a courtroom pan takes it along), hides it with her and ends
  it on her next pose or when she goes (`animation.c`, `EnRftaDropLunch`).

**The wide shot.** The courtroom seen from the gallery (background 6, the
gavel's lead-in) has its people as animations of their own: the GBA has the
first four episodes' (the DS's 0x97–0xB0 are its 0x24–0x3D). The DS adds
Ema beside Phoenix (0xB3) and the six witnesses on the stand seen from
behind (0xB1, 0xB2, 0xB4–0xB7: Meekins, Ema, Lana, Marshall, Angel Starr,
Gant). They are the GBA's 0x3E–0x44 (the DS's numbers less 0x73, like the
rest), each in the place its kind has on the GBA: the witnesses (palette
10) end in VRAM where the prosecutor starts (`OBJ_VRAM1+0x8C0`), Ema takes
Mia's place by Phoenix (`OBJ_VRAM1+0x1C20`, palette 14), and they end with
the background as the GBA's wide-shot people do. Their graphics and frames
are the DS's as they are; the DS's positions are about (128, 96), the GBA's
about (120, 80), and the backgrounds are cut at the same offset.

Of the DS's own `2F` animations, the rest are not converted: 0x95 and 0x96
are the gavel, which the gavel commands draw the GBA's way; 0x72–0x7B are
the opening, part of its movie (stage 4); and five one-off pictures (0x40,
0x41, 0x56, 0x7C, 0x7D: a boat and its wake in a flashback, a blood spray,
a car's headlights on the map, a mark on a photograph) come after the
background they belong to, which the GBA engine would end them with.

**Checking it.** Every converted frame is drawn back from the GBA files as
the GBA decodes them and compared with the DS's frame inside the GBA's
screen (`characters.py --check`, with Marshall's second animation drawn
in, and the lunch boxes' cells left out of Angel Starr's lunch versions):
all 3,337 are the same pixel for pixel, but for 618 frames short of cells
at the bottom, all of it in the text box's rows (screen rows 112 and
below). The text box is see-through, so with it up the cut shows dimmed as
a hem cut straight across; in court the witness stand covers most of it.
Gant loses rows from screen row 144 or 152 in 285 frames and from row 112
to 128 in his three breakdown animations (56 frames); Marshall from row 136
to 152 in 224 frames (209 of them his poses with the bandana) and from row
112 in his poncho flourish (6); Angel Starr's lunch versions from row 144 (47).
`graphics/en/rfta/characters/report.txt` lists them. In the emulator, the
lunches, the wide shots with Ema and the witnesses, and Marshall with his
bandana were photographed as the autoplayer reached them. The frame sound
effects the GBA does not have yet (35 frames, 32 of them Gant's) are left
out until stage 5.

## Tools (`tools/en/rfta/`)

All read your own DS dump: `DS_DATA` (data.bin, as `dsdata.py`), `MES_ALL`
(mes_all.bin), `DS_ARM9` (arm9.bin), `DS_ROM` (the .nds, for the emulator).

- `dsbin.py table | dis ADDR… | sweep REGEX` — the ARM9 command table,
  a disassembler (capstone, ARM mode), an instruction search.
- `ds_script.py OP [context] [max]` — where the fifth episode uses a
  command, with the dialogue around it; `ds_script.chapter(k)` and
  `sections(k)` for the other tools.
- `inventory.py [out.json]` — the counts in section 1 and 2.
- `variants.py` — the argument patterns of the DS-only commands and which
  are new.
- `dsrun.py STATE CHAPTER SEC OUT FRAMES [ops…]` — runs a section in
  DeSmuME, logs every command, photographs both screens at the watched ones.
- `movies.py [ARCHIVE FRAME out.png]` — the four frame sequences.
- `portraits.py out.png` — the partner portraits.

Stage 2 (each writes into the build; their docstrings say what from):

- `translate.py [OUT_DIR]` — the scripts (`script_rfta/`) and
  `translate_report.txt`, what was translated and what left out, per file.
- `std.py` — the common script with the 18 chapter titles.
- `arm9_tables.py` — `src/en_rfta_tables.c`, `include/en_rfta_case_data.h`.
- `rooms.py` — `src/en_rfta_rooms.c`: rooms, talks, examine areas, room code.
- `backgrounds.py`, `evidence.py`, `descriptions.py`, `nametags.py`,
  `plates.py`, `spots.py` — the pictures.

Stage 3:

- `characters.py [--check]` — `graphics/en/rfta/characters/`,
  `data/rfta/characters.s`, `include/en_rfta_characters.h`,
  `characters.json` (DS animation → GBA offset, read by `translate.py` and
  `rooms.py`); `--check` compares every frame written with the DS's.
- `effects.py` — the wide shot's people and the box lunches:
  `graphics/en/rfta/effects/`, `data/rfta/effects.s`,
  `include/en_rfta_effects.h` (the `gAnimationData` entries),
  `effects.json` (DS `2F` number → GBA number, read by `translate.py`).

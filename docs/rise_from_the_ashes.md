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
| `5F` | mode, step, level | 246 | the DS's second fade system, a 23-mode software palette effect. Its modes 3, 4 and 7 are a monochrome filter (0x0201c088 mixes each colour with its grey): `5F 3 1 1f` turns the background and the person grey at once for a flashback (199 uses), `5F 4 1 1` brings the colour back (73), `5F 4 3 20` over 96 frames (section 9). | command `64`, the same filter on the GBA's palettes |
| `5C` | mode, step, level | 22 | the same fade, holding the script until it is over | same, waiting |
| `75` | kind, value, 0, 0 | 137 | movie player (the DS's 0x0206b0dc, section 10): `75 0 0 n f` sets up sequence n with flags f, `75 1 f` sets the state (1 forwards, 3 held, 4 backwards, 2 closed) and flags (0x8000 go round, 0x4000 stay at the end), `75 2 n` jumps to frame n, `75 4 n` / `75 5 n` the first and last frame, `75 6` waits for the end | GBA command `65` (`en_movie.c`) |
| `74` | kind, value | 241 (208 in variants episodes 1–4 never use) | bottom-screen UI: `74 5 0` puts the normal panel back (77 uses, after a portrait or a prompt), `74 8 n` shows panel n (17 panels, ids 0x2e–0x49; they follow "Court Record!" lines and evidence being added, and the tutorial), `74 d n` (18 values, in the touch tutorial), `74 a n` after questions that want an answer presented (profiles, prints), `74 9 n` / `74 6 n` / `74 c` / `74 b` around the luminol and fingerprint scenes — these readings are from the dialogue around them and still to be watched in the emulator. | most become nothing (one screen); the prompts become GBA prompts; the tutorial panels become text boxes |
| `55` | background, 9 | 21 | shows background n over the scene for a moment and puts the previous one back (flashes and cut-ins) — the handler swaps `gMain.currentBG`, waits for the background system, restores it | a short background swap; to confirm in the emulator |
| `68` | — | 23 | sets flag 0x400 in the DS's game flags: the plate on screen fades together with the scene | part of the fade mapping |
| `7B` | 1=close, picture | 12 | in the shared evidence-examination file only: shows close-up picture n (0–2: the sketch, the jar's stain, the Chief's piece) over the 3D view and waits for the player to close it | a close-up picture (the GBA's `69 2<<8 \| n`, `69 3<<8`) |
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
| luminol | Day 2 investigation (the evidence room, the parking lot) | spray by touch, reaction appears where sprayed | cursor + button spraying over the same picture (done: section 11) |
| fingerprinting | Day 2–3 investigation (the locker, the wiped stain, the cloth) | pick a finger, dust by touch, blow into the mic, compare the prints | cursor + button dusting, a button to blow (done: section 12) |
| 3D evidence | the Court Record's Check on the badge, the pieces with the bloodstain, the sketch and others; lines in the shared file | rotate a model, hotspots trigger the shared sections, `7B` close-ups | the models drawn in real time, the hotspots tested as the DS tests them (done: section 13) |
| jar puzzle | Day 2 investigation (the pieces of the Unstable Jar), Day 3 (the Chief's piece) | the jar in 3D on the top screen, the pieces turned and sent from a circle on the touch screen | the jar drawn by the 3D renderer beside a circle of the pieces (done: section 14) |
| safe's keypad | Day 3 investigation (Gant's safe) | the device's display on the top screen, its keys on the touch screen; seven digits checked one by one | the device on one screen, a cursor over the keys (done: section 15) |
| the Badger's angle | Final day trial (the Unstable Jar as the Blue Badger) | the jar in 3D in a circle on the touch screen, turned by dragging drums and the circle, Present | the jar drawn by the 3D renderer in the DS's circle, the + pad and L and R (done: section 16) |
| joining the dots | Final day trial (the victim's blood traces, the murderer's name) | the picture on the touch screen, lines dragged from trace to trace, Back, Present, the Court Record | the picture with the lines and traces drawn into its tiles, the examine pointer and A held, B, L, R (done: section 17) |
| staff roll | the ending, between and under the epilogue's scenes | the credits dusted onto the touch screen by themselves and blown away; sketches of the people for the player to dust | the credits pages on the one screen between the scenes, the DS's powder (done: section 18) |
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
- No SSEQ → m4a path. (Stage 5: `music.py`, `sfx.py`.)
- No GBA code for: luminol, fingerprinting, 3D views, close-ups (the
  portrait plate, the frame player and the tape: sections 9 and 10; the
  luminol, the fingerprints and the 3D views with their close-ups:
  sections 11 to 13).
- The 3D model data has not been found in data.bin (no Nitro BMD0 headers;
  a Capcom format; found: section 13), and `55`, `68`, `77` and the
  `74`/`75` variants are read from the code and script contexts, not yet
  watched in the emulator.

## 6. Stages

1. **Inventory and decoding** — this document, the tools below. Done.
2. **Translator and framework** — the DS → GBA script translator with every
   command accounted for (new variants confirmed in the emulator), the
   chapter tables extracted from the ARM9, tables widened, episode select,
   backgrounds, evidence, portraits. Milestone: the episode plays start to
   end on the GBA with placeholder sprites and without the mechanics.
3. **Characters** — the animation data decoded or recorded, six sprite
   sets converted.
4. **Mechanics** — the frame player and the tape (done: section 10),
   luminol, fingerprints, 3D views, close-ups (done: sections 11 to 13),
   the jar puzzle (done: section 14), the safe's keypad (done: section 15),
   the jar's angle (done: section 16), the dots (done: section 17), the staff
   roll (done: section 18), prompts. The partner portrait and the
   grey flashbacks (`5F`): done (section 9).
5. **Sound** — seven tracks and the effects. Done (section 9).
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
  stage 3 (section 8), the seven new songs until stage 5 (section 9).
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
| Day 2 investigation | the luminol's tutorial in the parking lot | the player's turn with the spray, the stain's question |
| The end | the staff roll's end (its process starts the next section) | "The End", the title screen |

(The luminol in the evidence room and the security tape in the Day 3 trial
were bypassed the same way until their systems came (sections 10 and 11),
the wallet and the phone on Day 1, the knife in the Day 2 trial and the
picture in the book on the final day until the 3D viewer came (section 13),
the jar's pieces on Day 2 and its last piece on Day 3 until the jar puzzle
came (section 14), Gant's safe until its keypad came (section 15), the
jar's angle on the final day until it came (section 16), the dots after it
until they came (section 17); the staff roll was skipped whole until it
came (section 18).)

The questions answered with a person's profile ("What is this person's
name?", the DS's `74 A n`) stay questions: they become the GBA's present
prompt `21`, with the answers from the DS's table at 0x020b1324 added to the
court present data (a wrong answer goes to the next section, as on the DS).
Movies, the partner portrait, the bottom-screen panels and the second fade
system were left out (the dialogue around them stands); the portrait and the
fade system (the grey flashbacks) came in later (section 9).

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
effects the GBA did not have (35 frames, 32 of them Gant's: SE0C3–SE0C8)
play the fifth episode's own sounds since stage 5 (section 9).

## 9. Stages 4 and 5 so far: the partner portrait, the grey flashbacks, the music, the sounds

**The partner portrait.** The DS's `76 0 n` / `76 1 n` (281 uses) put Ema's
or Gumshoe's 64×64 face at the left or right of the text box while they talk
during investigations; `76 2 0` takes it away. On the GBA they are two new
commands, `62 (side << 8) | n` and `63`, on the evidence plate's code: the
18 portraits (data.bin 0x1bb3074, 0x820 bytes each) are Court Record
pictures 147–164 (`evidence.py`), entries 0xD1–0xE2 of the evidence table,
shown and put away the way a presented piece of evidence is. In the
emulator Ema's expressions change on the plate line by line as on the DS
(checked on the Day 2 crime scene, where she sprays the luminol).

**The music.** The seven new songs (BGM150–BGM156) are DS sequences in the
GBA game's style: the GBA's samples and square waves for programs 0–30 and
the drums, new recordings for programs 31 and up (IMA-ADPCM at 30–64 kHz).
`music.py` converts them to m4a songs 113–119 of the RFTA build: the
sequences followed through their calls and jumps (the jump back that loops
becomes the GOTO), ticks one to one (the tempo byte is the DS's bpm),
volumes and velocities squared as the DS's decibel tables square them, the
envelopes the tracks set converted to m4a's (decay and release fitted to its
integer envelope), vibrato and tremolo converted for the tempo. Samples
whose notes play them faster than the mixer carries are filtered down, in
copies of half an octave each (a key split). The DS's squares (up to six
tracks of them) play on the GBA's two square channels and its wave channel,
each track on the one where its notes fall least on another's (most songs:
none), at a level measured against the samples.

The mixer is where the GBA runs short: the songs play up to 14 sampled
notes at once and m4a's interpolating mixer takes about 7 scanlines a
frame for each, where the GBA's own music seldom has more than four. In the
RFTA build the music player has 16 tracks (IWRAM after the other players),
the mixer 12 channels, and the new songs' voices (type 0x10) are mixed
without interpolation, the nearest source sample for each output sample, as
the DS's own sound hardware plays them (`m4a_1.s`; the mixer moved to a
larger IWRAM buffer): about 5.5 lines a channel, and the mixer may take 100
lines a frame instead of 80 (with 12 channels busy and a bar's notes all
starting at once it takes up to 97). When the channels are taken,
a note takes one from a quieter track (track priorities by loudness).
Simulating m4a's channel allocation over the songs, the part of the notes
lost that way is 1–5% of their sound. A frame with a background change
decompresses a second stripe only when the stripe and the sound (as long as
it took over the last frames) still end in time (`gEnSoundLines`).

Levels (`music_levels.py`): recorded on their own in both games, each new
song stands to the GBA's music as on the DS to the DS's (the DS plays its
music 4.9 dB louder: median of nine songs); the seven are within 0.4 dB.

**The flashbacks in grey.** The DS's second fade system, `5F`, turned out
to be a monochrome filter: its modes 3 and 4 move a level from colour to grey
and back (the colour mixed with its grey, luma 0.299/0.587/0.114, by
level/32), mode 7 for the background alone. The fifth episode greys the
background and the person for its flashbacks (`5F 3 1 1f`, 199 times) and
brings the colour back after them (`5F 4 1 1`, 73); once the colour comes
back slowly, over 96 frames, as Phoenix remembers Lana Skye's red scarf. In
DeSmuME its mode 0x15 (the person alone back to colour, 3 uses) changes
nothing on the screen; it is left out. On the GBA it is command `64 (mode <<
8 | step) level` (`en_rfta.c`): each frame the background's colours (32–255,
or 32–47 for a 16-colour background) and the person's palettes (14 and 15) are
mixed with their grey at the level; the game's own colours are kept as it
writes them (a colour in palette RAM that is not the filter's last is a new
one), so backgrounds and poses that change during a flashback come up grey.
Checked against the DS on the red-scarf scene.

**The sounds.** The script plays 25 sounds the first four episodes lack
(SE073, SE0B6–SE0BE, SE0C2 and the opening's SE0D4–SE0E2) and the people's
animation frames six (SE0C3–SE0C8). `sfx.py` converts them as `port_sfx.py`
converts the DS's other sounds, to songs 120–159 (with the systems' own:
the fingerprints' SE0C0, the jar's SE0CC and SE0CD, the keypad's
SE0CE–SE0D3), on the player and with the priority the DS gives them; the
opening's stereo pairs on players 2 and 3 get those players a second
track. Their volumes come from recordings of each in both games
(`sfx_levels.json`); the jar's and the keypad's want more than a track's
full volume (their samples are at full scale already) and play at it, a
few dB under the DS's balance with the music.

## 10. Stage 4: the movies and the tape

**The movies, every frame.** The DS's four frame sequences (its table at
0x020c096c) play at 30 frames a second: the Blue Badger's dance (450
frames), the opening's silhouettes (329), the security footage (1420) and
the ending (270). All are kept frame by frame. `movies.py` cuts them as the
backgrounds are (240×160 at x 8, y 16) and stores each frame as the change
from the one before: a bitmap of the 600 8×8 slots that change, then their
tiles as they are or XORed with what the slot held (the smaller; an XOR
change undoes itself, so a movie of them plays backwards too). The changes
are packed with LZ77 (`movlz.c`, optimally parsed) in bytes (the BIOS's
format, unpacked into EWRAM) or in whole words (unpacked straight into the
VRAM after the slots, about three times as fast; used where a change is so
large that bytes would not unpack in time: most of the ending). Keyframes
(every 128 frames, and the frames the scripts jump to) are whole pictures.
Sizes: the dance 0.71 MB, the opening 0.27, the footage 5.05, the ending
1.90 (7.95 MB in all).

The security footage pans to and fro the whole time, and its time stamp
stays put on the screen. It is stored as a scene 678 pixels wide, the
camera's place in each frame found by matching each frame to the one before
(whole pixels); 32 columns of slots hold the part on screen and BG3's
scroll follows the camera, a column coming into view written over the one
that went out of it. Its grain would change every tile every frame, so a
tile is written again only where the picture (blurred 3×3) differs from the
slot by more than 4/3 of a grey on average, or a few pixels by 6 (thin
edges), or, after 8 frames, a line of three pixels by 3.5 (bits of an edge
left behind); in 16 fixed greys. The time stamp is taken out of the picture
(each second's, from the pixels white in nearly every frame of it: the
DS's font is proportional) and drawn over it: the slots under it in its two
rows are copied to tiles of their own with its pixels drawn in.

`en_movie.c` follows the DS's player: a position that moves a frame every
other frame between a first and a last frame, forwards, backwards or held,
going round or staying at the end. On the frame the position moves the
changes to the frame are unpacked, in the time the frame has left before the
sound (`EN_BG_FRAME_END`, as the background stripes) by ARM code in IWRAM
(`en_movie_lz.s`, 0x03006A00); they go into the slots in the next vertical
blank once the DS has shown the frame (top first; the footage's frame with
its time stamp takes about 42 lines). In the emulator the ending (its
heaviest frames) and the footage keep pace with the DS, frame for frame.
The movie takes BG3 in 16 colours (palette 2, its colour 0 the backdrop)
when its first frame is ready and gives the background back when it closes;
a background the script changes meanwhile waits for the close. A screen that
draws over BG3 (the save screen, a Court Record picture) makes the movie
unpack its frame again from the nearest keyframe (black until it is there)
when it comes back. A save made while a movie is up keeps its place (SRAM
0x2C00, after the text box log) and loading it opens the movie there.

The opening: the DS's `69 405 100` starts the silhouettes 60 frames after
an effect of the opening (the knife's flash) that the GBA does not have;
here they start at once.

**The tape in court.** On Day 3 the DS shows the footage on the touch
screen four times for a moment to be pointed out (its 0x02077c28): the
locker light, the cloth falling out, Marshall in the video, what Meekins
did. The answer depends on the frame and the place (0x0206a294: four spots,
each a run of frames with a mask a frame, and the section each question goes
to when the 16×16 box round the touch meets the mask; `movies.py` keeps the
masks' rectangles). On the GBA it is command `66 q` where the DS hands over
(`74 8 35`, `79`): the footage plays, the examine hand points (the + pad),
A points out the moment; L rewinds while held, R fast-forwards, START pauses,
a tap of L or R while paused steps a frame. A line in the text box says so
(it makes way for the hand when the hand is low).

## 11. Stage 4: the luminol

The DS sprays luminol on the touch screen: the room turns red, each touch is
a puff of mist, and a stain the mist reaches glows; three sprays, each after
the glow of the last has settled, bring it out (corner marks, three close-up
pictures with a flash before each, then the stain's lines). `luminol.py` has
the details it was read off (the scenes, the stains' records and masks, the
glow's state machine and colours, the red as measured).

On the GBA (`en_luminol.c`, the investigation's own state
`INVESTIGATION_LUMINOL`) the room is the GBA's background, tinted red through
the grey filter's palette code (`EnLuminolTint`); a nozzle moves with the
+ pad and A sprays (SE0C4, the DS's); B goes back to the investigation and L
to the other half of a wide room, as the DS's "Back" and arrows. The mist is
a 64×64 sprite added to the room (the hardware blend), the stains' glows
sprites with their own colours. The Court Record has "A Spray" on the
luminol where it can be used (between an investigation's scenes), as the
DS's button. The parking lot's tutorial (chapter 22) runs from the script:
command `67 n` (0 start, 1 Ema's spray, 2 the player's turn when the script
stops, 3 back to the red room after a stain's lines, 4 leave), which
`translate.py` writes for the DS's `74 6 n` and the `74 5 0` of the luminol's
sections; its "Touch the screen to spray it on." reads "Press the A Button
to spray it on.". File 35's stain lines (C2-C8) are copied into every chapter
the luminol is used in, after its last section (`en_rfta_luminol_sections.h`
gives where); finding all three of the evidence room's stains leaves the
luminol and takes the room's jump D2, as the DS's `74 8 3f`.

Played through by `fullplay.py` from Day 2's start: the parking lot's
tutorial and its stains, the payphone, Edgeworth's office, the Chief's
office, the evidence room's three (and the jump that follows them), on
through the Day 3 trial into Day 3's investigation (Edgeworth's office again).

## 12. Stage 4: the fingerprints

The DS's fingerprinting has three cases (`74 9 n`): the bloody handprint
on Gumshoe's locker (Day 2: five fingers in the blood, then the print
beside them), the wiped stain in the evidence room (Day 2: two fingers)
and the cloth from the Chief's safe (Day 3: five). The player picks a
finger on its picture, drops powder on it with the stylus and blows into
the microphone until the print stands out; a clear print is then compared
with the eight people's prints Edgeworth gave, card by card, in three
sweeps with the matching points counted up, until "Match found.".
`fingerprint.py` has the details it was read off (the cases' and masks'
records, the powder's stamps, the blowing and the test for a print found,
the prints, the cards, the points).

On the GBA (`en_fingerprint.c`, the investigation's own state
`INVESTIGATION_FINGERPRINT`, with its inner loops in ARM code copied to
IWRAM, `en_fingerprint_arm.s`) the screens are BG3 with 256 colours:

- the fingers' picture with the DS's cross-hairs: the + pad moves them, a
  box shows round the finger they are on, A examines it, B goes back to
  the investigation (not on the first case, as the DS);
- the dusting screen, the DS's touch screen scaled by 10/11 on its green
  grid: A drops powder where the brush is (held, a drop every 8 frames), R
  blows (the DS's microphone, at a fixed level); the powder is a byte a
  pixel in EWRAM and only the tiles it changed are drawn again each frame;
  the test for a print found is the DS's;
- the comparison: the DS's top screen's panels (the found print, the
  meter, the counter, the person's print) above its touch screen's card,
  ←/→ to change the card, A to compare; the sweeps, the crosses and the
  count, "Match found." with SE0C0 and the meter alight, or "No matches
  found." with BGM032.

The script drives it as on the DS: command `68` (sub << 8 | n) is the DS's
`74 9 n` (0: start case n), `74 5 0` in the fingerprints' sections (1: the
player's turn once the script stops) and `74 8 37`–`3D` (2–7: Ema's powder
and blowing in the tutorial, the fingers' picture again, the comparison
screen, the evidence room's picture, the comparison back); the sections
(13B–142, 145, 146, 129–12B, file 35's C9 and CA) run over the screens,
with the comparison's card blank under the text box. A section that
leaves its text box up at the player's turn (file 35's C9) has it slid
away, as the DS's `74 5 0` does. The tutorial's touch and microphone
lines are reworded for the buttons. Leaving puts the investigation back as
the `68 0` found it (the menu, examining or talking, and its buttons): a
match goes on in its section (142, 146, 12B), Back ends the section as its
`1C 3` would have.

## 13. Stage 4: the evidence in 3D

The DS's Court Record has "Check" on the fifth episode's evidence with a
model (the badge, the wallet and the ID card, the phone, the knife, the
jar and its pieces, the book, the muffler…): the bottom screen shows it in
3D, the stylus turns it, the slider zooms, and touching a hotspot brings
up "Examine", which turns the model to a pose for it and runs its lines
(the shared file 35's, a few with a close-up picture, `7B`). Four scenes
open the Court Record for evidence to be checked (`74 8 2e`, `74 b 0`):
the wallet on Day 1 (its clasp: the wallet opens, the ID card inside),
the phone on Day 1 (flipped open, then its redial button), the knife in
the Day 2 trial (its switch opens it; Back puts it in the record) and the
book on the final day (its pages: the picture). `evidence3d.py` has what
was read off the DS: the models are Capcom's own format in data.bin (the
US build's resource table at 0x020b6574 names each mesh and its texture),
the object records (0x020b91b8: the meshes, the hotspots' and blockers'
quads, their ids), the hotspot test (0x0203cc1c: the quad's corners
projected, a quad facing the camera, a blocker in front hides it), the
ids' handlers (0x020c046c: the section, the pose, and for six of them an
animation, a model change and a flag).

On the GBA (`en_evidence3d.c`, the Court Record's state `RECORD_3D`) the
models are drawn in real time as the DS draws them: its camera (20 units
back, its projection), the vertices as they are, the textures 16 colours
read from ROM, each in a 16-colour slot of BG3's 256, the back faces
culled, a 16-bit depth buffer. The renderer is ARM code copied to IWRAM
(`en_evidence3d_arm.s`): it draws into a 192 × 128 picture in EWRAM (the
background's decompression buffer, given back as the viewer leaves), the
textures with the perspective put right every 16 pixels (straight across
where a triangle's depth hardly changes), and it works in the time each
frame leaves before the music's mixing (it stops at a triangle or a row
and goes on in the next frame; the picture is copied to VRAM, the rows it
changed, when it is whole). An integer model of it in Python, run against
the assembled code in an ARM emulator (unicorn), agrees with it to the
pixel, suspended or not. A picture takes about 4 frames for the usual
models (15 a second as a model turns), more zoomed right in.

The screen is the DS's: its wood, the zoom's slider (its knob a sprite),
the turning bar, the grey grid (BG2, under the picture), the blue lines and
square of the touch's point, "B Back" and "A Examine" (when the point is on
a hotspot) as the fingerprints' tabs, and the keys' hints between them:

- the + pad turns the model (about the screen's axes), R with the + pad
  moves the point, L with up / down zooms;
- A on a hotspot examines it: the model turns to the DS's pose, its
  section runs (file 35's: the script switched to it and put back after,
  as it was; the scenes' own: the chapter's), the partner's portrait on the
  plate as the DS's face box, and the model turns back; the six special
  ids play their animation and change the model (the flagged two, the
  phone's opening and redial, run their chapter lines once, in chapter 18
  and before, as the DS);
- the close-ups (command `69 2<<8 | n`, the DS's `7B 0 n`; `69 3<<8` takes
  them away) show in the viewport;
- B goes back to the Court Record, as the viewer found it (the screen, the
  text box, the script, the sprites and their tiles: saved in
  `gSaveDataBuffer` as the evidence details do).

In the Court Record, evidence with a model shows "L Check" (the record's
own L button beside a label in its free tiles). The scenes are command
`69 0 n` (`translate.py`): the record opens and stays (no B) until the
scene's evidence is checked and its end reached: the final hotspot's lines
(the wallet's clasp, the phone's redial, the book's pages), or Back where
the DS has one (the phone put away, the knife into the record); then the
viewer and the record close and the section after it runs (C3, FD, AD, 82).
The wallet's opening and first hover lines (C0, C1, the DS's how-to) run as
on the DS.

## 14. Stage 4: the jar puzzle

On Day 2 Phoenix puts the pieces of the Unstable Jar back together in the
evidence room, on Day 3 the Chief's piece goes in as the last (the DS's
`74 8 32`). The DS shows the jar in 3D on the top screen and the pieces in a
circle on the touch screen: left and right pick a piece ("Fragment No."),
L and R turn it a quarter, Combine sends it. The next piece, turned
upright, rises into its place (the jar flashes white, waits, turns to the
next piece's view); any other comes back. Red edges mark where the next
piece goes and a crosshair its point, both pulsing. `jarpuzzle.py` has what
was read off the DS (its code at 0x02072a6c-0x020767a0): the jar is the
object records 0x2f (the base) to 0x38 (the nine pieces, each in the jar's
own frame), drawn under the 3D viewer's camera; a step table (0x020c9794:
the jar's turn and offset for each piece, the angle it must have, 0 for
all) and the crosshair's points (0x020c96b0); the pieces' order on Day 2
(0x020c92d0), each at a random quarter turn; the red edges are pictures
(guide01-guide09), the crosshair another, both through six palettes; the
pieces' circle pictures (0x020c9518, the US build's set); the timings
(the base rising 30 frames and turning once round in 60, a piece's
flight 42 frames, the flash 11, the turn to the next view 30); the sounds
(SE0CC as a piece fits, SE0CD as one turns, SE0C0 as Day 3's fits) and
where it goes on: after Back, the room's background and the section the
DS starts (135, Day 3 132); done, the jar's picture (background C0, Day 3
C1) and the section after (136, Day 3 133).

On the GBA (`en_evidence3d.c`, script command `69 4<<8 | n`, n 0 Day 2, 1
Day 3) the puzzle is the viewer's state with the jar's screen: the jar is
drawn by the same renderer, its view the DS's top screen at 2/3 in the
viewport's left 144 columns, each piece transformed and drawn in turn (the
depth's shift fixed for the nearest the jar comes, so no piece waits for
the others' vertices); the red edges are the guide pictures' pixels
written into the picture as it is finished (a colour of BG3 that pulses),
the crosshair a sprite. On the right, the circle with its grid and ring,
"Fragment No." and the piece's number, the arrows where more pieces are,
the red cross, and the L and R buttons with their turns; the piece is a 64
× 64 affine sprite (the DS's picture at half its size) that turns as on
the DS and flies to the crosshair; "B Back" and "A Combine" are the
fingerprints' tabs. A picks the DS's Combine, B its Back. The screen and
the script are saved and put back as the viewer's are; leaving changes the
background as the script's `1B` would (the jar's picture) and runs the
DS's next section, faded in as the DS fades it (Day 2's done: the section
fades the screen out itself first).

The whole jar is up to 1,900 triangles, which takes the renderer about 2
frames for the base alone and 12 with every piece in. As a piece flies, the
jar is drawn once and kept (its tiles and depth, in the movies' buffer),
and each picture puts back the piece's last place and draws the piece
alone: about 20 pictures in the 42 frames of a flight. The jar's own moves
(the rise and the turn round at the start, the turn to the next piece's
view) go a step a picture, never faster than the DS: the turn takes the
DS's 30 frames for the first pieces and up to 75 for the last, in six
pictures. The fades take the backdrop too (the grid's grey under the
picture: the viewer's fades left it lit until now).

## 15. Stage 4: the safe's keypad

On Day 3 Phoenix opens Chief Gant's safe with the number of the last ID
card on the evidence room's record (the DS's `74 8 34`, after the zoom onto
the safe: backgrounds DF, E0, E1, C8). The DS shows the device's display on
the top screen and its keys on the touch screen; `keypad.py` has what was
read off the DS (its code at 0x020791dc-0x0207b200, the display's at
0x0206c4f8): the display a 256 × 192 bitmap; its pictures (the digits, the
cursor, the six of a segment that runs round a digit, the bars over and
under it, the US build's messages "Input code.", "Code confirmed. Access
granted." and "Code input error.", the light); the keys the US build's
textures in three palettes (dark, lit, pressed); the code (0x020c91e8:
seven 7s). What it does, in frames: "Input code." blinks (20 on, 20 off)
for 60, the keys light one by one 4 frames apart (SE0CE); the cursor under
the next digit blinks on the display's 60-frame clock (shown under 40); a
key is orange while it is touched (SE0CF; Back Space SE0D0); at the
seventh the keys go dark and 60 frames on the check runs: a digit every 21
frames (SE0D1), the segment running round it between its bars, the light
green from the clock's 0 to 50, then the seven blinking for six steps
more; then the message (and the light red for the right code), SE0D3 (or
SE0D2) 30 frames in, and at 120 the right code shows the safe (E1) at once
with its handle turning a quarter about the dial (64 frames) and the
safe's own light red, 60 frames more and the fade to Gant's office (74) and
section 11E; the wrong code fades to the office and section 11D.

On the GBA (`en_keypad.c`, script command `69 5<<8`) the keypad runs on the
3D viewer's machinery (the screen and the script saved and put back, the
Court Record's state 8). The device is one screen: the DS's top screen from
(8, 58), the display at the DS's size, over the keys in two rows (1-6; 7, 8,
9, 0 and Back Space) at the DS's size in a sunken black frame; the display's
tiles are drawn into in RAM (the pictures over its own) and copied in the
vertical blank as they change, the keys, the light and a cursor are
sprites. The + pad moves the cursor over the keys (round at the ends), A
presses the key under it, B is Back Space; a key stays orange while its
button is held. Every frame count above is the DS's. The safe is the
room's screen given back on background E1 (the handle a 16 × 32 affine
sprite, its turn the DS's matrices; the safe's light, which the DS draws
over the safe's display, read off its screen), a frame black between the
display and the safe where the DS's top screen changes at once; then the
fade, the office and the section, as the jar's. Background C8, the safe's
keypad as the script shows it before, had the Japanese "もどる" key (the
US build draws its Back Space key over it): it now has the key's texture,
in the picture's greys (`backgrounds.py`).

## 16. Stage 4: the Blue Badger's angle

In the final day's trial Phoenix shows the court that the Unstable Jar,
seen from the right angle, is what the witness took for the Blue Badger
(the DS's `74 8 33`, after the section's last line, and again after the
try-again's). The DS shows the Badger on the top screen and on the touch
screen the jar whole (object record 17) in a circle, with drums on the
right and below that turn it as they are dragged, two buttons that roll it,
and Present. `badger.py` has what was read off the DS (process 20, its
code at 0x0207a1ec-0x0207b220): the jar drawn in a 128 × 128 viewport at
(64, 20) under the 3D viewer's camera, 2 further back, fovy 53 degrees;
the jar's turn kept as a matrix that each frame's turn is applied after,
about the screen's axes (the + pad held: 2 degrees a frame about the
upright and across; L and R held: 1 about the line of sight; the steps the
DS's sine table's entries 22 and 11, so 1.934 and 0.967 degrees in fact),
the matrix kept square; the ring's 16 ticks (the texture eff060) turned by
the roll, the drums' ticks (16 and 12, 11 and 15 degrees apart) along the
drums' bows. Present reads three angles off the matrix (0x02067dac: the
turn across and about the upright of the jar's axis, then the roll left
when those are undone) and wants them in (300, 320), (350, 359) or
[0, 10), and (175, 185) degrees: the jar on its head, tipped toward the
viewer, about a sixth of a turn. Then both screens go white, "Take that!"
with Phoenix on speed lines for 61 frames, the fade, and section BD (the
right angle: the jar on its head, the Badger's head) or BC (not yet, and
the angle again).

On the GBA (`en_evidence3d.c`, script command `69 6<<8`) the panel is the
viewer's state with its own screen: the DS's touch screen from (8, 12), the
circle and the jar at the DS's size (the wood and the box, the ring and the
grid, the drums and the roll's buttons drawn after the DS's, "A Present" in
the fingerprints' tabs over the circle's top, L and R by the roll's
buttons); the jar is drawn by the renderer in the frame buffer's first 16 ×
16 tiles, the ring's pixels put over it where it crosses the picture's
tiles; the ring's ticks are four affine sprites, the drums' ticks sprites.
The turns are the DS's (the same matrix, the same steps, a step for each
frame that passes, as the DS's frames: a picture may take a frame's work
over its time), and A presents with the DS's angles and ranges: L held 186
frames, up 26, right 3 is the Badger on both. The drums' ticks run with the
+ pad as with the DS's drag. The DS's top screen (the Badger's movie)
cannot be shown with the panel: the movie is closed as the panel comes up
(the sections after close it at once). The "Take that!" is the GBA's, in
two sections after file 31's own (`translate.py`): from the white, Phoenix
on his speed lines, the bubble and the shout, the DS's 61 frames, the fade,
his picture taken away in the dark (`1F`: the speed lines' Phoenix is BG2's,
which would stay over the next background), then BD or BC (which gets its
text box and a fade in).

Played through by `fullplay.py` from the final day's start: the
cross-examinations, the Badger turned to its angle (L 186 frames, up 26,
right 3) and presented, on through the trial into the next chapter; the
wrong angle's "Take that!", BC's lines and the panel again by hand.

## 17. Stage 4: joining the dots

Later in the final day's trial Phoenix joins the blood traces the victim
left into the murderer's name (the DS's `74 8 3e`). The DS's touch screen
shows the picture (background 0x8e) with the twelve traces over it in a
dark red, under a bar ("Connect the blood traces") with Present and Court
Record, Back at the bottom. `dots.py` has what was read off the DS
(process 18, its code at 0x020763c4-0x02077238 and the traces' at
0x0206d294-0x0206e5dc):

- the traces (the US build's twelve: a table at 0x020c231c, their places,
  sizes, masks in data.bin and middles; their boxes at 0x020c17d4; the
  Japanese build has fifteen, for its katakana) are sprites in one colour,
  dark, or bright red when lit;
- a touch in a trace's box, with a pixel of any trace's mask under the
  touch's 8 × 8 brush, starts a line from that trace's middle (the brush
  is a disc, but the DS reads it 256 bytes a row, so all but its first row
  are the bytes after it: kept as the DS has it); the line follows the
  touch, blue with its shades running (a step every 15 frames), white
  while the touch is on another trace; both traces are lit; let go there,
  the two are joined (SE 0x34), unless they already are;
- a line is a rectangle 8 wide from middle to middle with an 8 × 8 round
  end at each (0x0203f290: 8.0 / 2 either side, then the texture 0x94 at
  both ends); the joined ones are dark red under the traces, the one being
  drawn over them and under the lit ones;
- Back (B, the button) takes the last line away: white for a frame, then
  gone (SE 0x33); not while a line is drawn, nor are the other buttons;
- R (Court Record) opens the record (SE 0x31) and comes back to the lines
  as they were; X (Present) checks them (0x0206d294, the US build's): every
  line must be one of the name's, 0-1, 0-5 and 5-6 (the E: its middle
  stroke the picture's own), 2-3 and 2-9 (the M, with the picture's
  strokes) and 7-8 (the A's bar) must all be there, and the A's legs whole:
  4-10 (or 4-7 and 7-10) and 4-11 (or 4-8 and 8-11); then both screens
  white, "Take that!" as after the Blue Badger's angle, and section C7 (the
  name) or C6 (not: the judge, a penalty, and the traces again from C4,
  the lines gone).

On the GBA (`en_dots.c`, script command `69 7<<8`, on the 3D viewer's
machinery as the keypad) the screen is the picture as the GBA has it (its
16 colours at 32-47 of BG3's 256, the lines' and the traces' after them):
the traces and the joined lines are drawn into a copy of its tiles (in the
movies' buffer while the dots are up), and each frame the tiles that
changed are put together again from it, with the line being drawn and the
lit traces over them; the line's shades and white are its colour's, set in
the vertical blank. The examine pointer (its finger's tip) is the touch:
the + pad moves it 3 pixels a frame (as the investigation's), A held is the
stylus down, let go is the stylus lifted, so a line is drawn by holding A
on a trace and letting go on another; B is Back, L Present and R the Court
Record, as tabs (the fingerprints') under the DS's bar, the shoulder
buttons' as the jar puzzle's; Back at the bottom left as the DS's. The
Court Record is the GBA's own, over the court's screen given back (the
script's text box with it); as it closes the dots come back with their
lines. Presenting is the Blue Badger's way: the white, the GBA's "Take
that!" (two more sections after file 31's own, `translate.py`), C7 or C6
(which gets its text box and a fade in).

The marks (the DS's `43 1`, then a penalty) come up in C6 outside a
cross-examination; their tiles may have been taken by what came before
(here the spot to point at, earlier in the trial), so `43 1` loads them
again in the RFTA build, as the start of a cross-examination does.

Played through by `fullplay.py` from the final day's start: the Badger's
angle, the record's answer, the name drawn (the pointer moved to each
trace, A held from one to the next) and presented, on into the next
chapter; by hand, wrong lines (the judge's penalty with the marks, and the
traces again from C4), Back on a line drawn too many, and the Court Record
opened and closed in the middle of the name.

## 18. Stage 4: the staff roll

The ending (file 34's section 85; 88 when it is replayed, Ema's scene only)
plays the epilogue's scenes on the DS's top screen and dusts the staff roll
on its touch screen between and under them (`74 c 0`, `74 d n` a page,
`74 8 40` shown, `74 8 41` blown away, `74 8 2e` the end). `credits.py`
has what was read off the DS (process 26: 0x02072494, its frames at
0x02071d14, the brush at 0x0207b6fc; the powder's code is the
fingerprints'):

- 0x36 pages (a table at 0x020c2e88: the Japanese build's credits 0-0x14,
  sketches of the people whose scene is up 0x15-0x1e, the US build's
  credits 0x1f-0x35), each a 256 × 192 picture that becomes the mask;
- a credits page is dusted by itself: a brush crosses the screen three
  times (rows 64, 96 and 128, right, left, right; a step of 32 every four
  frames from 32 to 224, the row jittered), dropping one of the
  fingerprints' four stamps a frame; 30 frames on, the powder is blown off
  but where the page's words are (46 frames, a quarter of the rows a
  frame), sparks flying up off it as it goes; the next page is dusted over
  the last;
- `74 8 41` blows it all away (61 frames, the sparks flying less far the
  first 12); a sketch waits for the player's touch while its scene plays.

On the GBA (`en_credits.c`, `en_credits_arm.s`, script command `6A`) a
credits page takes the screen while the epilogue's is black (its scene
faded out, before the next one's background comes): the fingerprints'
green grid on BG3 (256 colours: the powder's 15 at 48, the grid's at 64),
the page cut as the backgrounds are (x − 8, y − 16: all the US build's
credits are inside), the brush, the blowing and the sparks as the DS has
them, the powder a byte a pixel in EWRAM; each step (the DS's frame) a
quarter of the rows is blown and drawn into the tiles by ARM code in IWRAM.
A sketch's `74 8 40` (its scene coming) and `74 8 2e` fade the screen out
and give it back (the background decompressed again: the sparks had its
buffer), and the script waits for that. The sketches, and Ema's, which the
DS dusts by itself under her last scene, are left out: the scenes keep the
screen. As the DS's process starts section 86 ("The End") after its last
fade, the GBA still goes on there from the section's end (`BYPASS`).

Where the powder covers the screen (the first passes of its blowing) a
step is more work than a frame has room for: it is done four rows at a
time while the frame has time before the sound (`EN_BG_FRAME_END`, as the
background stripes), so such a step takes two frames and the sound is
never late; while the pages are up the script's waits (`0C`) count
vertical blanks, so the epilogue keeps the DS's time under its music. The
sparks are thrown at random: one pixel in 8, one in 16 of the page's (the
DS's fixed patterns: one in 10, one in 20).

Played by `fullplay.py` from the final day's last save to the ending, then
through it: every page dusted and its words shown before the next, blown
away before the next scene, no frame lost while the pages are up, each
scene back on its own background, then "The End".

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
- `movies.py list | ARCHIVE FRAME out.png` — the four frame sequences.
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

Stages 4 and 5:

- `portraits.py` (above) and `evidence.py` — the partner portraits as Court
  Record pictures 147–164.
- `music.py SDAT` — `data/rfta/music.s`, `sound/direct_sound_samples/rfta/`;
  `music_levels.py DS_DIR GBA_DIR` — `music_levels.json` from recordings.
- `sfx.py SDAT` — `data/rfta/sfx.s`, `sound/direct_sound_samples/rfta_sfx/`
  and the song table's rows; `sfx.py --measure DS_DIR GBA_DIR` —
  `sfx_levels.json`.
- `movies.py` — `graphics/en/rfta/movies/*.bin` (each movie: its changes,
  keyframes, palettes, the footage's scroll and time stamp) and
  `data/rfta/movies.s` (with the tape's spots); compiles `movlz.c`, the
  LZ77 packer, with `cc`.
- `luminol.py` — `graphics/en/rfta/luminol.bin` (the stains' masks, the
  mist, the nozzle, the marks), `data/rfta/luminol.s`,
  `src/data/en_rfta_luminol.h`; its `entries()` gives the stains as the GBA
  has them (`fullplay.py` sprays them).
- `fingerprint.py [--preview DIR]` — `graphics/en/rfta/fingerprint.bin`
  (the masks as bit planes, the stamps, the prints, the faces, the cards,
  the comparison screen, the sprites), `data/rfta/fingerprint.s`,
  `src/data/en_rfta_fingerprint.h`; `--preview` draws the screens as
  pictures; its `cases()` and `masks()` give the fingers as the GBA has
  them (`fullplay.py` dusts them).
- `evidence3d.py [--preview DIR]` — `graphics/en/rfta/evidence3d.bin` (the
  meshes, the textures, the close-ups as BG3 tiles, the frame's tiles and
  map, the grid, the sprites, "Check", 2^31 / n for the renderer),
  `data/rfta/evidence3d.s`, `src/data/en_rfta_evidence3d.h` (the records,
  the hotspots, the ids' sections and poses, the evidence's records, the
  scenes); `--preview` draws each record at rest and turned.
- `jarpuzzle.py` — read by `evidence3d.py` (the jar's records go with the
  viewer's): the steps, the guides' pixels, the flight, the fragments'
  sprites and colours, the crosshair, the jar's screen and sprites, into
  the same files; `backgrounds.py` takes the jar's two pictures from it.
- `badger.py [PREVIEW]` — read by `evidence3d.py` (the jar whole goes with
  the viewer's records): the panel (its tiles and map, the ring's masks,
  the grid), the ring's and the drums' ticks, the DS's steps, angles and
  bows, into the same files; with a file name, a picture of the panel.
- `dots.py [--preview FILE]` — `graphics/en/rfta/dots.bin` (the traces'
  masks, the bar and the tabs), `data/rfta/dots.s` and
  `src/data/en_rfta_dots.h` (the traces' middles, boxes and masks' places,
  the lines the check takes, the brush and the round end, the colours, the
  layout); with `--preview`, a picture of the screen with lines drawn.
- `credits.py [--preview FILE]` — `graphics/en/rfta/credits.bin` (the US
  build's credits pages as bit planes, cut to the GBA's screen; the
  stamps' dots), `data/rfta/credits.s` and `src/data/en_rfta_credits.h`
  (the brush's rows and steps, the timings, the powder's and the grid's
  colours); with `--preview`, the pages on the grid.
- `keypad.py [--preview FILE]` — `graphics/en/rfta/keypad.bin` (the
  device's screen as 8bpp tiles, the display's first, and its map; the
  display's pictures, bars and messages in the screen's colours; the keys,
  the lights, the cursor, the handle, the safe's light), `data/rfta/keypad.s`,
  `src/data/en_rfta_keypad.h` (the places, the code, the sounds, the
  colours); `backgrounds.py` takes the Back Space key from it for C8.

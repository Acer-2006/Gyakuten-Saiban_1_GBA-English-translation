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
0x32 (Ema, Lana, Gant, Marshall, Angel Starr, Meekins), with 139 animation
numbers between them (talk/idle pairs, so about 70 poses; Gant, Angel
Starr and Meekins also appear as 0x4000/0x8000 variants of their person
number, as Gumshoe does in episodes 1–4). Edgeworth and Gumshoe get a few
new poses (6 animation numbers). Ten new name tags
(persons 0x2c–0x35; Goodman, Darke, Neil Marshall and the Blue Badger are
names and stills only). 18 partner portraits (above).

The DS appears to keep every character's animation data in one archive
(data.bin 0x2202220: 562 entries, 3.25 MB, uncompressed, in pairs: a
16-colour palette with tile data, then a frame table). The format has not been
decoded; the first four episodes never needed it because their sprites are
the GBA's own. Two ways to get the new characters out: decode the format
(it is the GBA's lineage: 4bpp tiles, OAM-style frames), or record each
animation in the emulator the way the pose comparison already does, and
rebuild GBA animation tables from the recordings. Either way the result is
converted into the GBA animation format the decomp documents.

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
- **People and songs.** Stand-ins until stage 3 and 5: Ema → Maya, Lana →
  Mia, Jake Marshall → Will Powers, Meekins → Larry, Gant → von Karma, Angel
  Starr → April May; the seven new songs play stand-ins.
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
how the stalls above were found and how the bypasses were checked.

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

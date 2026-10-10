# Gyakuten Saiban 1 English

<img width="450" height="282" alt="image" src="https://github.com/user-attachments/assets/b0044f05-d641-4705-8bd4-0b9d4a69b693" />

An English translation of **Gyakuten Saiban** (Game Boy Advance, 2001), the
original Japanese release of *Phoenix Wright: Ace Attorney*. It brings the
script and text graphics of the official English DS release (2005) to the GBA
game, running on the GBA's own engine with its own timing.

<img width="1488" height="676" alt="image" src="https://github.com/user-attachments/assets/d201b9c6-6e78-4001-a97c-2789ec49c61d" />


<img width="1568" height="527" alt="image" src="https://github.com/user-attachments/assets/c4b5cdb1-9d80-460f-af7b-75fce57196b7" />

## What's in it

- **The full English script** of all four episodes: *The First Turnabout*,
  *Turnabout Sisters*, *Turnabout Samurai* and *Turnabout Goodbyes*, as in
  the official English DS release.
- **English graphics from the DS release**: the title screen, the Court
  Record pictures and descriptions, answer buttons, the Move and Talk lists,
  the episode select, the save and load screens, the Testimony and
  Cross-Examination banners, the *Objection!*, *Hold it!* and *Take that!*
  bubbles, the verdict, map markers, and the signs and writing in the
  backgrounds.
- **A variable-width English font** made from the DS's.
- **The English voices** of the DS release (*Objection!*, *Hold it!*,
  *Take that!* and the others) and the two sounds its English script added.
  Every other sound effect is the GBA game's own, as in the original.
- **The courtroom of Gyakuten Saiban 3**: the benches, the witness stand, the
  judge's bench and the pans between them, in place of the first game's
  very bright courtroom.
- Many fixes so that the English script plays like the original game:
  poses, timings, name tags, effects and screen transitions were checked
  against both the Japanese GBA game and the DS game.

## What's not in it

- **Rise from the Ashes**, the fifth episode, was made for the DS (it uses
  the touch screen and DS-only features) and was never part of the GBA game.

## How to play

1. **You need your own copy of the game** as a ROM file:
   *Gyakuten Saiban* (Game Boy Advance, Japan), 8 MB,
   CRC32 `c88f0952`, SHA-1 `15c0e3389709bb275c42e99ed25212d09e49e361`.
   Some copies have "DUMPED BY AAA" written at the very end of the file
   (CRC32 `0d9f9697`). That is the same game with a tag added; the release
   includes a patch for those copies too. No ROMs are provided here.
2. **Download the patch** (`.bps`) from the
   [Releases](../../releases) page.
3. **Apply it** with a BPS patcher, for example
   [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) (in your
   browser) or Floating IPS (Flips). The patcher checks your ROM first and
   tells you if it is not the right one.
4. **Play** the patched ROM (16 MB) in a GBA emulator. mGBA is recommended.
   On a flash cart, set the save type to SRAM.

In-game saves carry over from one version of the patch to the next.
Emulator savestates don't, so load your in-game save after updating.

## Known issues

None known at the moment. If something looks or plays wrong, please
[open an issue](../../issues) with a screenshot and where in the game it
happened (episode, day, and the line of text on screen).

## Building from source

This repository is the full source of the hack, built on the decompilation of
Gyakuten Saiban. Set up agbcc and binutils as described in
[BUILDING.md](BUILDING.md) (the decompilation's own instructions), then:

```
make tools
make
```

The result is the patched English ROM. The scripts that make the English
version (script port, graphics, effects, courtroom) are in `tools/en`.

## Credits

- **Acer_man**: project lead, design decisions and testing.
- Made with the help of **Claude** (Anthropic), which did much of the reverse
  engineering and code.
- The **pwaa1 decompilation** of Gyakuten Saiban
  ([atasro2/pwaa1](https://github.com/atasro2/pwaa1)) and everyone who worked
  on it. This project would not exist without it.
- **Capcom**: the original game, the English script and text graphics of
  *Phoenix Wright: Ace Attorney* (Nintendo DS, 2005), and the courtroom of
  *Gyakuten Saiban 3* (GBA, 2004).

## Disclaimer

This is a non-commercial fan project, not affiliated with or endorsed by
Capcom. *Gyakuten Saiban* and *Phoenix Wright: Ace Attorney* are trademarks
of Capcom. Please support the official releases.

How anim_looks.json is made (what each DS person animation shows, in GBA animations)

1. gbascan.py      every person animation in the Japanese GBA ROM (valid frame lists) -> gba_anims.json
2. gfast.py        render every frame of each (offline, from the ROM data) -> gframes.pkl
3. dsseq.py        record each DS person animation for 200 frames in DeSmuME (English DS ROM)
4. seqmatch.py     match DS recordings to GBA animations: same picture, changing on the same frames
5. pick.py         choose per DS animation (timing first, then looks) -> dsmap.json
6. classes.py      group GBA animations with the same timing and picture (versions of one pose
                   drawn for different places: cut lower, shifted) -> ../anim_looks.json
evalposes.py / offplace.py: check a ported script (every DS pose shows the DS's expression; no pose
is drawn away from where the Japanese game puts that person on that background).
Paths inside are the ones of the build machine.

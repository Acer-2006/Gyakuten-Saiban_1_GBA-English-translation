#ifndef GUARD_EN_COURT_H
#define GUARD_EN_COURT_H

// English patch: the courtroom of Gyakuten Saiban 3 (data/en_court.s,
// tools/en/port_gs3_court.py): the defense and prosecution benches, the
// witness stand, the judge, co-counsel and the wide courtroom, and the pans
// between the benches. The lobby and the gavel close-ups are the first game's.
extern u8 gEnCourtDefenseBench[];
extern u8 gEnCourtProsecutionBench[];
extern u8 gEnCourtWitnessStand[];
extern u8 gEnCourtJudgeSeat[];
extern u8 gEnCourtCoCounsel[];
extern u8 gEnCourtCourtRoom[];
extern u8 gEnCourtPan[];

// the three pans of 16 frames (each a 256-colour palette and 240x160 of
// 256-colour tiles): defense <-> witness, prosecution <-> defense,
// prosecution <-> witness
#define EN_PAN_FRAME_BYTES 0x9800
#define EN_COURT_PAN(n) (gEnCourtPan + (n) * 16 * EN_PAN_FRAME_BYTES)

#endif // GUARD_EN_COURT_H

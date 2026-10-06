#!/usr/bin/env python3
"""QA for answer_text.py: compare the width of each transcription (measured
with a Helvetica-metric font) with the width of the lettering on the DS button.
Prints the entries whose ratio is off; a wrong or missing word shows up here."""
import os, sys, statistics
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from make_choice_labels import button
from answer_text import ANSWERS
FONT = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 40)
def ink_width(i):
    a = button(i)[6:27, 18:238].astype(int)          # inside the button frame
    cols = np.where((a >= 5).any(0))[0]
    return (cols[-1] - cols[0] + 1) if len(cols) else 0
def ref_width(s):
    return FONT.getlength(s) if s else 0
rows = []
for i, s in enumerate(ANSWERS):
    w, r = ink_width(i), ref_width(s)
    if w and r: rows.append((i, s, w, r, w / r))
    elif w or r: print('EMPTY MISMATCH', i, repr(s), w, r)
med = statistics.median(x[4] for x in rows)
bad = [x for x in rows if abs(x[4] / med - 1) > 0.07]
for i, s, w, r, q in bad: print('%3d %-34s ink %3d  expected %5.1f  ratio %.2f' % (i, s, w, r * med, q / med))
print('median', round(med, 4), 'checked', len(rows), 'flagged', len(bad))

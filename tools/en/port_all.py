#!/usr/bin/env python3
"""Port all 17 scenario scripts. usage: port_all.py GBA_SCRIPT_DIR DS_MES_DIR OUT_DIR"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(__file__))
import port_script
gdir, ddir, odir = sys.argv[1:4]
os.makedirs(odir, exist_ok=True)
gfiles = sorted(glob.glob(os.path.join(gdir, 'scenario_*.phscr')))
dfiles = [os.path.join(ddir, '%02d.bin' % i) for i in range(1, 35, 2)]
T = K = 0
for gf, df in zip(gfiles, dfiles):
    name = os.path.basename(gf)
    t, k = port_script.port(gf, df, os.path.join(odir, name), os.path.join(odir, name + '.report.txt'))
    T += t; K += k
print('ported %d sections, %d left in Japanese' % (T, K))

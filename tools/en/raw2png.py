"""Write raw 4bpp tile data into a PNG that gbagfx converts back to the same bytes.
The palette is copied from an existing template PNG."""
from PIL import Image
def raw_to_png(raw, width_tiles, template_png, out_png, mwidth=1, mheight=1):
    tpl = Image.open(template_png)
    ntiles = len(raw) // 32
    mt = mwidth * mheight
    w_px = width_tiles * 8
    h_px = (ntiles // width_tiles) * 8
    img = Image.new('P', (w_px, h_px))
    img.putpalette(tpl.getpalette())
    px = img.load()
    mcols = width_tiles // mwidth
    for t in range(ntiles):
        m, r = divmod(t, mt)                      # metatile index, tile inside
        mx, my = m % mcols, m // mcols
        tx = mx * mwidth + r % mwidth
        ty = my * mheight + r // mwidth
        for y in range(8):
            for x in range(8):
                b = raw[t * 32 + y * 4 + x // 2]
                px[tx * 8 + x, ty * 8 + y] = (b >> 4) if x & 1 else (b & 15)
    img.save(out_png)

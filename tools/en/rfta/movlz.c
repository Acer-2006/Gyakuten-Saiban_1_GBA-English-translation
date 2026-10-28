/* movlz.c: the compressor for tools/en/rfta/movies.py (the RFTA build's movies).
   movlz UNIT IN OUT
   LZ77 with UNIT-byte symbols, optimally parsed. A flag byte leads each run
   of eight tokens (most significant bit first; 1: a match). A literal is
   UNIT bytes; a match is two bytes, big-endian (len - MINLEN) << 12 | (disp - 1),
   len and disp counted in symbols (disp 1..4096).
   UNIT 1 is the GBA BIOS's LZ77 format (len 3..18; header 0x10 | size << 8).
   UNIT 4 (len 1..16) is what the movie player unpacks straight into VRAM
   (src/en_movie_lz.s): a header 0x40 | size << 8, the offset of the literals
   from the start, the flags and matches, then the literal words, word-aligned
   (one aligned load each). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define WINDOW 4096
#define CHAIN 1024

static int U, MINLEN, MAXLEN;
static uint8_t *in;
static long n;

static uint32_t sym(long i)
{
    uint32_t v = 0;
    memcpy(&v, in + i * U, U);
    return v;
}

static uint32_t hash(long i)
{
    uint32_t v = sym(i);
    if (U == 1)     /* three bytes */
        v = v | (i + 1 < n ? in[i + 1] << 8 : 0) | (i + 2 < n ? in[i + 2] << 16 : 0);
    return (v * 2654435761u) >> 16;
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: movlz UNIT IN OUT\n");
        return 1;
    }
    U = atoi(argv[1]);
    if (U != 1 && U != 4) {
        fprintf(stderr, "UNIT is 1 or 4\n");
        return 1;
    }
    MINLEN = U == 1 ? 3 : 1;
    MAXLEN = MINLEN + 15;
    FILE *f = fopen(argv[2], "rb");
    if (!f) { perror(argv[2]); return 1; }
    fseek(f, 0, SEEK_END);
    long bytes = ftell(f);
    fseek(f, 0, SEEK_SET);
    in = calloc(bytes + 8, 1);
    if (fread(in, 1, bytes, f) != (size_t)bytes) { perror(argv[2]); return 1; }
    fclose(f);
    if (bytes % U || bytes >= (1 << 24)) {
        fprintf(stderr, "%s: %ld bytes\n", argv[2], bytes);
        return 1;
    }
    n = bytes / U;
    long *cost = malloc((n + 1) * sizeof(long));
    int *clen = calloc(n + 1, sizeof(int)), *cdist = calloc(n + 1, sizeof(int));
    /* chains of earlier positions with the same hash */
    long *head = malloc(65536 * sizeof(long)), *prev = malloc((n + 1) * sizeof(long));
    for (int h = 0; h < 65536; h++)
        head[h] = -1;
    long **cands = malloc(n * sizeof(long *));
    int *ncand = calloc(n, sizeof(int));
    for (long i = 0; i < n; i++) {
        uint32_t h = hash(i);
        long c[CHAIN];
        int k = 0;
        for (long j = head[h]; j >= 0 && i - j <= WINDOW && k < CHAIN; j = prev[j])
            c[k++] = j;
        cands[i] = malloc((k ? k : 1) * sizeof(long));
        memcpy(cands[i], c, k * sizeof(long));
        ncand[i] = k;
        prev[i] = head[h];
        head[h] = i;
    }
    cost[n] = 0;
    for (long i = n - 1; i >= 0; i--) {
        int best[19] = {0};
        for (int k = 0; k < ncand[i]; k++) {
            long j = cands[i][k];
            int l = 0;
            while (l < MAXLEN && i + l < n && memcmp(in + (i + l) * U, in + (j + l) * U, U) == 0)
                l++;
            for (int m = MINLEN; m <= l; m++)
                if (!best[m])
                    best[m] = (int)(i - j);
        }
        cost[i] = cost[i + 1] + 1 + 8 * U;
        clen[i] = 0;
        for (int l = MINLEN; l <= MAXLEN; l++)
            if (best[l] && i + l <= n && cost[i + l] + 17 < cost[i]) {
                cost[i] = cost[i + l] + 17;
                clen[i] = l;
                cdist[i] = best[l];
            }
        free(cands[i]);
    }
    uint8_t *out = malloc(bytes * 2 + 64), *lit = malloc(bytes + 4);
    long o = U == 1 ? 4 : 8, i = 0, nlit = 0;
    out[0] = U == 1 ? 0x10 : 0x40;
    out[1] = bytes & 0xff;
    out[2] = (bytes >> 8) & 0xff;
    out[3] = (bytes >> 16) & 0xff;
    while (i < n) {
        long fpos = o++;
        uint8_t flags = 0;
        for (int b = 0; b < 8 && i < n; b++) {
            if (clen[i]) {
                int v = (clen[i] - MINLEN) << 12 | (cdist[i] - 1);
                flags |= 0x80 >> b;
                out[o++] = v >> 8;
                out[o++] = v & 0xff;
                i += clen[i];
            } else if (U == 1) {
                out[o++] = in[i++];
            } else {
                memcpy(lit + nlit, in + i * U, U);
                nlit += U;
                i++;
            }
        }
        out[fpos] = flags;
    }
    while (o % 4)
        out[o++] = 0;
    if (U == 4) {
        out[4] = o & 0xff;
        out[5] = (o >> 8) & 0xff;
        out[6] = (o >> 16) & 0xff;
        out[7] = 0;
        memcpy(out + o, lit, nlit);
        o += nlit;
    }
    f = fopen(argv[3], "wb");
    if (!f) { perror(argv[3]); return 1; }
    fwrite(out, 1, o, f);
    fclose(f);
    return 0;
}

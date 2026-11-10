#!/usr/bin/env python3
"""Parche widescreen para Jade Empire (Xbox, MS-109).

Uso: python3 jade_empire_ws_patch.py jade_empire.xbe salida.xbe [relacion] [--v1]
     relacion por defecto 16:9 (también 16:10, 21:9...)
     --v1 genera la versión anterior (solo 3D, HUD estirado)

v2 (por defecto):
  3D  - El motor calcula aspect = ancho/alto del viewport (640/480) en tiempo
        de ejecución. Se multiplica por K = relacion/(4/3) en 0x151FED (Hor+).
        Ese valor alimenta la proyección y el frustum culling.
  2D  - El HUD, los textos y los marcadores se dibujan con una proyección
        ortográfica de 0 a 1 (D3DXMatrixOrthoOffCenter) en 0x14B240 y
        0x154AE0. Se cambia el rango horizontal a [0.5-K/2, 0.5+K/2], así el
        HUD conserva sus proporciones y queda centrado en la zona 4:3.
  Las conversiones pantalla<->mundo (0x152C40 / 0x1531E8) quedan originales:
  con la ortográfica ensanchada, la fórmula original de 4:3 ya coloca los
  marcadores en su sitio. En v1 sí se corregían porque el HUD seguía estirado.

  El código y las constantes nuevas van en una zona libre (ceros) de la
  cabecera XBE, que el kernel mantiene mapeada en 0x10000.
"""
import struct
import sys

BASE = 0x10000
CAVE_VA = 0x11100          # zona libre de la cabecera: 0x110BA-0x117C0
CAVE_END = 0x117C0

SITE_A = 0x151FED          # divss xmm1,xmm0 ; mulss xmm0,[0x3198CC]
ORIG_A = bytes.fromhex("f30f5ec8" "f30f5905cc983100")
SITE_B = 0x152C40          # movss xmm1,[esp] ; mulss xmm6,xmm1 ; mulss xmm7,xmm1
ORIG_B = bytes.fromhex("f30f100c24" "f30f59f1" "f30f59f9")
SITE_C = 0x1531E8          # movaps xmm1,xmm0 ; mulss xmm1,[esp+38]
ORIG_C = bytes.fromhex("0f28c8" "f30f594c2438")

# Ortográfica del HUD: fldl [1.0] -> right ; fldl [0.0] -> left
ORTHO_R = (0x14B294, 0x154B20)   # dd 05 48 98 31 00
ORTHO_L = (0x14B29E, 0x154B2A)   # dd 05 08 99 31 00
ORIG_R = bytes.fromhex("dd0548983100")
ORIG_L = bytes.fromhex("dd0508993100")


def parse_sections(d):
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    secs = []
    for i in range(u(0x11C)):
        o = u(0x120) - BASE + i * 56
        _, va, vs, ra, rs, _ = struct.unpack_from("<6I", d, o)
        secs.append((va, vs, ra, rs))
    return secs


def va2raw(secs, va):
    if BASE <= va < BASE + 0x2000:          # cabecera
        return va - BASE
    for sva, vs, ra, rs in secs:
        if sva <= va < sva + rs:
            return ra + va - sva
    raise ValueError(hex(va))


def jmp(src, dst):
    return b"\xE9" + struct.pack("<i", dst - (src + 5))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    v1 = "--v1" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    src, dst = args[0], args[1]
    ratio = args[2] if len(args) > 2 else "16:9"
    w, h = (float(x) for x in ratio.split(":"))
    k = (w / h) / (4.0 / 3.0)

    d = bytearray(open(src, "rb").read())
    if d[:4] != b"XBEH" or d.find("Jade Empire".encode("utf-16le")) < 0:
        sys.exit("No parece el XBE de Jade Empire")
    secs = parse_sections(d)

    checks = [(SITE_A, ORIG_A), (SITE_B, ORIG_B), (SITE_C, ORIG_C)]
    checks += [(s, ORIG_R) for s in ORTHO_R] + [(s, ORIG_L) for s in ORTHO_L]
    for site, orig in checks:
        r = va2raw(secs, site)
        if bytes(d[r:r + len(orig)]) != orig:
            sys.exit("Bytes inesperados en %#x (¿versión distinta o ya parcheado?)" % site)

    cave = CAVE_VA
    k_va, invk_va = cave, cave + 4
    l_va, r_va = cave + 8, cave + 16
    code = bytearray(struct.pack("<ff", k, 1.0 / k))
    code += struct.pack("<dd", 0.5 - k / 2, 0.5 + k / 2)

    jumps = []

    # A: aspect = (ancho/alto) * K ; conserva alto*0.01 en xmm0
    cave_a = cave + len(code)
    a = bytearray(bytes.fromhex("f30f5ec8"))                       # divss xmm1,xmm0
    a += bytes.fromhex("f30f590d") + struct.pack("<I", k_va)        # mulss xmm1,[K]
    a += bytes.fromhex("f30f5905cc983100")                          # mulss xmm0,[0.01]
    a += jmp(cave_a + len(a), SITE_A + 12)
    code += a
    jumps.append((SITE_A, cave_a, 12))

    if v1:
        # B: pantalla->mundo, x *= K
        cave_b = cave + len(code)
        b = bytearray(bytes.fromhex("f30f100c24"))                 # movss xmm1,[esp]
        b += bytes.fromhex("f30f59f9")                              # mulss xmm7,xmm1
        b += bytes.fromhex("f30f590d") + struct.pack("<I", k_va)    # mulss xmm1,[K]
        b += bytes.fromhex("f30f59f1")                              # mulss xmm6,xmm1
        b += jmp(cave_b + len(b), SITE_B + 13)
        code += b
        jumps.append((SITE_B, cave_b, 13))

        # C: mundo->pantalla, x /= K
        cave_c = cave + len(code)
        c = bytearray(bytes.fromhex("0f28c8"))                     # movaps xmm1,xmm0
        c += bytes.fromhex("f30f594c2438")                          # mulss xmm1,[esp+38]
        c += bytes.fromhex("f30f590d") + struct.pack("<I", invk_va) # mulss xmm1,[1/K]
        c += jmp(cave_c + len(c), SITE_C + 9)
        code += c
        jumps.append((SITE_C, cave_c, 9))

    rc = va2raw(secs, cave)
    if any(d[rc - 1:rc + len(code) + 1]) or cave + len(code) > CAVE_END:
        sys.exit("La zona libre de la cabecera no está vacía")
    d[rc:rc + len(code)] = code

    for site, cave_x, n in jumps:
        r = va2raw(secs, site)
        d[r:r + n] = jmp(site, cave_x) + b"\x90" * (n - 5)

    if not v1:
        for site in ORTHO_L:
            r = va2raw(secs, site)
            d[r + 2:r + 6] = struct.pack("<I", l_va)
        for site in ORTHO_R:
            r = va2raw(secs, site)
            d[r + 2:r + 6] = struct.pack("<I", r_va)

    open(dst, "wb").write(d)
    print("OK: %s  %s  relación %s  K=%.6f  HUD x=[%.4f, %.4f]" % (
        dst, "v1" if v1 else "v2", ratio, k, 0.5 - k / 2, 0.5 + k / 2))


if __name__ == "__main__":
    main()

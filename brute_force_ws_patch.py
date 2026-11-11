#!/usr/bin/env python3
"""Parche widescreen 16:9 (Hor+) para Brute Force (Xbox, MS-030, title ID 4D53001E).

Uso: python3 brute_force_ws_patch.py brute_force.xbe salida.xbe

El motor define la cámara por FOV horizontal: tanH = tan(fovh/2) y
tanV = tanH / hvaspect (4/3). El parche deja el FOV vertical original y
ensancha el horizontal x4/3 en los sitios donde se consume:

  1. Proyección (0x6EE30, única matriz de perspectiva del juego):
     m00 = 1/(tanV*aspect) pasa a multiplicarse por 0.75.
  2. Frustum culling (0x6C840): los planos laterales usan tanH*4/3 y
     atan(tanH*4/3) en lugar de tanH y fovh, para que no desaparezcan
     objetos en los bordes.
  3. Escala X mundo<->pantalla (campo +0x38 de la cámara, en 0x6AD00 y
     0x6AB30): halfW/tanH pasa a multiplicarse por 0.75, para que los
     marcadores proyectados sobre el mundo queden en su sitio.

Como el factor se aplica sobre el aspect que calcula el juego, también vale
para los viewports de pantalla dividida. El HUD 2D y los vídeos quedan
estirados. El código nuevo va en el relleno de NOPs entre funciones de
.text y usa la constante 0.75 que ya existe en .rdata (0x3A510C).
"""
import struct
import sys

BASE = 0x10000
K075 = 0x3A510C  # float 0.75 en .rdata


def parse_sections(d):
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    secs = []
    for i in range(u(0x11C)):
        o = u(0x120) - BASE + i * 56
        _, va, vs, ra, rs, _ = struct.unpack_from("<6I", d, o)
        secs.append((va, vs, ra, rs))
    return secs


def call(src, dst):
    return b"\xE8" + struct.pack("<i", dst - (src + 5))


FMUL_075 = b"\xD8\x0D" + struct.pack("<I", K075)   # fmul dword [0x3A510C]
FDIV_075 = b"\xD8\x35" + struct.pack("<I", K075)   # fdiv dword [0x3A510C]

CAVE_PROJ = 0x6C2B2   # 14 bytes de relleno tras ret 0Ch
CAVE_XS1 = 0x6ACF2    # 14 bytes de relleno tras ret 4
CAVE_XS2 = 0x6A8E1    # 15 bytes de relleno tras ret 18h

# (va, bytes originales, bytes nuevos)
PATCHES = [
    # 1) Proyección: fdiv [ebp+0Ch] ; fmul 0.75 ; fstp [ecx] ; ret
    (CAVE_PROJ, b"\x90" * 12,
     bytes.fromhex("d8750c") + FMUL_075 + bytes.fromhex("d919c3")),
    (0x6EEB0, bytes.fromhex("d8750cd919"), call(0x6EEB0, CAVE_PROJ)),

    # 2) Frustum: mov [esp],eax ; fld tanH ; fdiv 0.75 ; fld st0 ; fchs ;
    #    fstp [esp+18h] ; fld1 ; fpatan  (ángulo queda en st0 para fsincos)
    (0x6C93E,
     bytes.fromhex("d94124" "89442400" "d9e0" "d95c2418" "d94114"
                   "d80de04f3a00" "d95c2408" "d9442408"),
     bytes.fromhex("89442400" "d94124") + FDIV_075 +
     bytes.fromhex("d9c0" "d9e0" "d95c2418" "d9e8" "d9f3") + b"\x90" * 5),

    # 3) Escala X en 0x6AD00: fld [eax+30h] ; fdiv [eax+24h] ; fmul 0.75 ; ret
    (CAVE_XS1, b"\x90" * 13,
     bytes.fromhex("d94030" "d87024") + FMUL_075 + b"\xC3"),
    (0x6AD7C, bytes.fromhex("d94030" "d87024" "d95838"),
     call(0x6AD7C, CAVE_XS1) + bytes.fromhex("d95838") + b"\x90"),

    # 4) Escala X en 0x6AB30: fdiv [eax+24h] ; fmul 0.75 ; fstp [eax+38h] ; ret
    (CAVE_XS2, b"\x90" * 13,
     bytes.fromhex("d87024") + FMUL_075 + bytes.fromhex("d95838c3")),
    (0x6ABCC, bytes.fromhex("d87024" "d95838"), call(0x6ABCC, CAVE_XS2) + b"\x90"),
]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = bytearray(open(sys.argv[1], "rb").read())
    if d[:4] != b"XBEH":
        sys.exit("No es un XBE")
    secs = parse_sections(d)

    def va2off(va):
        for sva, _, ra, rs in secs:
            if sva <= va < sva + rs:
                return va - sva + ra
        raise ValueError(hex(va))

    for va, orig, new in PATCHES:
        assert len(orig) == len(new), hex(va)
        o = va2off(va)
        cur = bytes(d[o:o + len(orig)])
        if cur == new:
            print(f"{va:#x}: ya parcheado")
            continue
        if cur != orig:
            sys.exit(f"{va:#x}: bytes inesperados {cur.hex()} (¿otra versión del XBE?)")
        d[o:o + len(new)] = new
        print(f"{va:#x} (archivo {o:#x}): {orig.hex().upper()} -> {new.hex().upper()}")

    open(sys.argv[2], "wb").write(d)
    print("OK ->", sys.argv[2])


if __name__ == "__main__":
    main()

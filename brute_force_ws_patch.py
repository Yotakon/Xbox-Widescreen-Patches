#!/usr/bin/env python3
"""Parche widescreen 16:9 (Hor+) para Brute Force (Xbox, MS-030, title ID 4D53001E).

Uso: python3 brute_force_ws_patch.py brute_force.xbe salida.xbe [--v1]
     --v1 genera la versión anterior (sin la corrección del culling 5)

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
  5. (v2) Culling por esfera del objeto cámara (método 0x6AE20): usa una
     normal de plano lateral propia (campos +0x40..+0x48) calculada con tanH
     en 0x6AD00 y 0x6AB30. En v1 seguía en 4:3 y los objetos desaparecían en
     los bordes al girar. Ahora +0x48 = tanH*4/3 antes de normalizar.

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

CAVE_CULL = 0x6B7E3   # 13 bytes de relleno tras ret

# v2: normal del plano lateral del culling por esfera (+0x48 = tanH*4/3)
PATCHES_V2 = [
    # fld [eax+24h] ; fdiv 0.75 ; fst [eax+48h] ; ret
    (CAVE_CULL, b"\x90" * 13,
     bytes.fromhex("d94024") + FDIV_075 + bytes.fromhex("d95048c3")),
    # 0x6AD00: mov [eax+48h],edx ; fld [eax+48h]  ->  call cave ; nop
    (0x6AD3C, bytes.fromhex("895048" "d94048"), call(0x6AD3C, CAVE_CULL) + b"\x90"),
    # 0x6AB30: mov [eax+48h],edx ; mov [eax+44h],ecx ; fld [eax+48h]
    #       -> mov [eax+44h],ecx ; call cave ; nop
    (0x6ABE1, bytes.fromhex("895048" "894844" "d94048"),
     bytes.fromhex("894844") + call(0x6ABE4, CAVE_CULL) + b"\x90"),
]


def main():
    args = [a for a in sys.argv[1:] if a != "--v1"]
    v1 = "--v1" in sys.argv[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    d = bytearray(open(args[0], "rb").read())
    if d[:4] != b"XBEH":
        sys.exit("No es un XBE")
    secs = parse_sections(d)

    def va2off(va):
        for sva, _, ra, rs in secs:
            if sva <= va < sva + rs:
                return va - sva + ra
        raise ValueError(hex(va))

    for va, orig, new in PATCHES + ([] if v1 else PATCHES_V2):
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

    open(args[1], "wb").write(d)
    print("OK ->", args[1])


if __name__ == "__main__":
    main()

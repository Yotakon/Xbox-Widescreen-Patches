#!/usr/bin/env python3
"""Parche widescreen 16:9 (Hor+) para Brute Force (Xbox, MS-030, title ID 4D53001E).

Uso: python3 brute_force_ws_patch.py brute_force.xbe salida.xbe [--v1 | --v2]
     sin opción genera la v3 (3D + HUD). --v1 / --v2 generan las anteriores.
     Hay que partir siempre del XBE original.

3D (todas las versiones). El motor define la cámara por FOV horizontal:
tanH = tan(fovh/2) y tanV = tanH / hvaspect (4/3). Se deja el FOV vertical
original y se ensancha el horizontal x4/3:

  1. Proyección (0x6EE30, única matriz de perspectiva): m00 x0.75.
  2. Frustum de planos (0x6C840): planos laterales con tanH*4/3.
  3. (solo v1/v2) Escala X mundo<->pantalla (+0x38 de la cámara, 0x6AD00 y
     0x6AB30) x0.75, para marcadores sobre el HUD estirado. En v3 no hace
     falta: la UI ya trabaja en un espacio de 16:9.
  5. (v2+) Culling por esfera de la cámara (0x6AE20): su normal lateral
     (+0x48) usa tanH*4/3. En v1 los objetos desaparecían en los bordes.

HUD (v3). La UI se dibuja con una ortográfica de pantalla (modo 2 de la
cámara, 0x6C0D0) de 0 a ancho del viewport (640):

  a. La ortográfica pasa a ir de -w/6 a 7w/6 (853 unidades en 16:9), así
     todo lo 2D (HUD, mirilla, radar, menús) recupera su forma. Lo que se
     coloca con coordenadas fijas queda centrado en la zona 4:3.
  b. Los límites de la zona segura que usa el juego para anclar el HUD
     (0xB2870 izquierdo, 0xB28E0 derecho) se desplazan W/6 hacia fuera.
     Los elementos anclados a los lados (vida, arma, radar, objeto) quedan
     junto a los bordes reales de la pantalla. El centro (0xB2970) no cambia.
  c. Los elementos que cubren todo el ancho (fundidos, fondos) se amplían
     W/6 por cada lado en el dibujo de widgets (0xBA950), para que sigan
     cubriendo la pantalla entera.

Como todo se calcula sobre el ancho del viewport, vale también para pantalla
dividida. Los vídeos Bink no se tocan. El código nuevo va en el relleno de
NOPs entre funciones y en la zona libre de la cabecera XBE (0x10EA0, entre el
logo y la copia de la cabecera PE, mapeada por el kernel).
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


def jmp(src, dst):
    return b"\xE9" + struct.pack("<i", dst - (src + 5))


FMUL_075 = b"\xD8\x0D" + struct.pack("<I", K075)   # fmul dword [0x3A510C]
FDIV_075 = b"\xD8\x35" + struct.pack("<I", K075)   # fdiv dword [0x3A510C]

CAVE_PROJ = 0x6C2B2   # 14 bytes de relleno tras ret 0Ch
CAVE_XS1 = 0x6ACF2    # 14 bytes de relleno tras ret 4
CAVE_XS2 = 0x6A8E1    # 15 bytes de relleno tras ret 18h
CAVE_CULL = 0x6B7E3   # 13 bytes de relleno tras ret

# (va, bytes originales, bytes nuevos)
CORE = [
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
]

XSCALE = [
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

CULL = [
    # 5) fld [eax+24h] ; fdiv 0.75 ; fst [eax+48h] ; ret
    (CAVE_CULL, b"\x90" * 13,
     bytes.fromhex("d94024") + FDIV_075 + bytes.fromhex("d95048c3")),
    # 0x6AD00: mov [eax+48h],edx ; fld [eax+48h]  ->  call cave ; nop
    (0x6AD3C, bytes.fromhex("895048" "d94048"), call(0x6AD3C, CAVE_CULL) + b"\x90"),
    # 0x6AB30: mov [eax+48h],edx ; mov [eax+44h],ecx ; fld [eax+48h]
    #       -> mov [eax+44h],ecx ; call cave ; nop
    (0x6ABE1, bytes.fromhex("895048" "894844" "d94048"),
     bytes.fromhex("894844") + call(0x6ABE4, CAVE_CULL) + b"\x90"),
]

# --- v3: HUD. Código en la cabecera (ensamblado con GNU as, base 0x10EA0) ---
HDR_CAVE = 0x10EA0
HDR_CODE = bytes.fromhex(
    # constantes: 1/6, -1/6, 7/6, 1.0
    "abaa2a3e" "abaa2abe" "5555953f" "0000803f"
    # 0x10EB0 ortho: pop eax ; fild [esi+D0h] ; fld st0 ; fmul 7/6 ; fstp [esp]
    #               fmul -1/6 ; sub esp,4 ; fstp [esp] ; jmp eax
    "58db86d0000000d9c0d80da80e0100d91c24d80da40e010083ec04d91c24ffe0"
    # 0x10ED0 left: add esp,0Ch ; W=layer.ancho ; st0 -= W/6 ; ret 4
    "83c40c8b4424048b40080fbf402050db042458d80da00e0100dee9c20400"
    # 0x10EEE right: add esp,10h ; W=layer.ancho ; st0 += W/6 ; ret 4
    "83c4108b4424048b40080fbf402050db042458d80da00e0100dec1c20400"
    # 0x10F0C full: si x<=1 y x+w+1>=W: x -= W/6 ; w += W/3 ;
    #               luego fld w ; fcomp 0.0 ; ret  (instrucciones originales)
    "8b4424148b402885c074568b400885c0744f0fbf402050db042458d9442420d81dac0e01"
    "00dfe0f6c4417433d9442420d8442444d805ac0e0100d8d9dfe0f6c401751cd80da00e01"
    "00d9442420d8e1d95c2420d8c0d8442444d95c2444eb02ddd8d9442444d81d884f3a00c3"
)
H_ORTHO, H_LEFT, H_RIGHT, H_FULL = 0x10EB0, 0x10ED0, 0x10EEE, 0x10F0C

HUD = [
    (HDR_CAVE, b"\x00" * len(HDR_CODE), HDR_CODE),
    # a) 0x6C1E8: fild [esi+D0h] ; fstp [esp] ; push 0  -> call ortho
    (0x6C1E8, bytes.fromhex("db86d0000000" "d91c24" "6a00"),
     call(0x6C1E8, H_ORTHO) + b"\x90" * 6),
    # b) salidas de los límites izquierdo y derecho: add esp,N ; ret 4 -> jmp
    (0xB28D1, bytes.fromhex("83c40c" "c20400"), jmp(0xB28D1, H_LEFT) + b"\x90"),
    (0xB2955, bytes.fromhex("83c410" "c20400"), jmp(0xB2955, H_RIGHT) + b"\x90"),
    (0xB295F, bytes.fromhex("83c410" "c20400"), jmp(0xB295F, H_RIGHT) + b"\x90"),
    # c) 0xBADA7: fld [esp+40h] ; fcomp [0.0]  -> call full
    (0xBADA7, bytes.fromhex("d9442440" "d81d884f3a00"),
     call(0xBADA7, H_FULL) + b"\x90" * 5),
]

VERSIONS = {
    "v1": CORE + XSCALE,
    "v2": CORE + XSCALE + CULL,
    "v3": CORE + CULL + HUD,
}


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ver = flags[0][2:] if flags else "v3"
    if len(args) != 2 or ver not in VERSIONS:
        sys.exit(__doc__)
    d = bytearray(open(args[0], "rb").read())
    if d[:4] != b"XBEH":
        sys.exit("No es un XBE")
    secs = parse_sections(d)

    def va2off(va):
        if BASE <= va < BASE + 0x2000:          # cabecera
            return va - BASE
        for sva, _, ra, rs in secs:
            if sva <= va < sva + rs:
                return va - sva + ra
        raise ValueError(hex(va))

    for va, orig, new in VERSIONS[ver]:
        assert len(orig) == len(new), hex(va)
        o = va2off(va)
        cur = bytes(d[o:o + len(orig)])
        if cur == new:
            print(f"{va:#x}: ya parcheado")
            continue
        if cur != orig:
            sys.exit(f"{va:#x}: bytes inesperados (usa el XBE original)")
        d[o:o + len(new)] = new
        print(f"{va:#x} (archivo {o:#x}): {len(new)} bytes")

    open(args[1], "wb").write(d)
    print(f"OK -> {args[1]} ({ver})")


if __name__ == "__main__":
    main()

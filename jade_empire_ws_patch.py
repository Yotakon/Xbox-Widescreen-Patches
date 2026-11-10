#!/usr/bin/env python3
"""Parche widescreen (Hor+) para Jade Empire (Xbox, MS-109, NTSC/PAL).

Uso: python3 jade_empire_ws_patch.py jade_empire.xbe salida.xbe [relacion]
     relacion por defecto 16:9 (tambien acepta 16:10, 21:9, etc.)

Qué hace:
  El motor calcula aspect = ancho/alto del viewport (640/480) en tiempo de
  ejecución, por eso cambiar constantes 1.3333 en el XBE no surte efecto.
  El parche multiplica ese aspect por K = (relacion destino)/(4/3), manteniendo
  el FOV vertical (Hor+). El mismo valor alimenta la matriz de proyección
  (D3DXMatrixPerspectiveFovRH) y el frustum culling, así que no desaparecen
  objetos en los bordes. También se corrigen las dos rutinas que convierten
  entre pantalla y mundo (indicadores/selección sobre personajes).

  El código nuevo vive en una zona libre (ceros) de la cabecera XBE,
  que el kernel mantiene mapeada en 0x10000 durante toda la ejecución.
"""
import struct
import sys

BASE = 0x10000
CAVE_VA = 0x11100          # zona libre de la cabecera: 0x110BA-0x117C0

# Sitios originales (VA) y bytes esperados
SITE_A = 0x151FED          # divss xmm1,xmm0 ; mulss xmm0,[0x3198CC]
ORIG_A = bytes.fromhex("f30f5ec8" "f30f5905cc983100")
SITE_B = 0x152C40          # movss xmm1,[esp] ; mulss xmm6,xmm1 ; mulss xmm7,xmm1
ORIG_B = bytes.fromhex("f30f100c24" "f30f59f1" "f30f59f9")
SITE_C = 0x1531E8          # movaps xmm1,xmm0 ; mulss xmm1,[esp+38]
ORIG_C = bytes.fromhex("0f28c8" "f30f594c2438")


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
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    ratio = sys.argv[3] if len(sys.argv) > 3 else "16:9"
    w, h = (float(x) for x in ratio.split(":"))
    k = (w / h) / (4.0 / 3.0)

    d = bytearray(open(src, "rb").read())
    if d[:4] != b"XBEH" or d.find("Jade Empire".encode("utf-16le")) < 0:
        sys.exit("No parece el XBE de Jade Empire")
    secs = parse_sections(d)

    for site, orig in ((SITE_A, ORIG_A), (SITE_B, ORIG_B), (SITE_C, ORIG_C)):
        r = va2raw(secs, site)
        if bytes(d[r:r + len(orig)]) != orig:
            sys.exit("Bytes inesperados en %#x (¿versión distinta o ya parcheado?)" % site)

    cave = CAVE_VA
    k_va, invk_va = cave, cave + 4
    code = bytearray(struct.pack("<ff", k, 1.0 / k))
    code += b"\x00" * 8                              # alineación

    # A: aspect = (ancho/alto) * K ; conserva alto*0.01 en xmm0
    cave_a = cave + len(code)
    a = bytearray(bytes.fromhex("f30f5ec8"))                       # divss xmm1,xmm0
    a += bytes.fromhex("f30f590d") + struct.pack("<I", k_va)        # mulss xmm1,[K]
    a += bytes.fromhex("f30f5905cc983100")                          # mulss xmm0,[0.01]
    a += jmp(cave_a + len(a), SITE_A + 12)
    code += a

    # B: pantalla->mundo, x *= K
    cave_b = cave + len(code)
    b = bytearray(bytes.fromhex("f30f100c24"))                     # movss xmm1,[esp]
    b += bytes.fromhex("f30f59f9")                                  # mulss xmm7,xmm1
    b += bytes.fromhex("f30f590d") + struct.pack("<I", k_va)        # mulss xmm1,[K]
    b += bytes.fromhex("f30f59f1")                                  # mulss xmm6,xmm1
    b += jmp(cave_b + len(b), SITE_B + 13)
    code += b

    # C: mundo->pantalla, x /= K
    cave_c = cave + len(code)
    c = bytearray(bytes.fromhex("0f28c8"))                         # movaps xmm1,xmm0
    c += bytes.fromhex("f30f594c2438")                              # mulss xmm1,[esp+38]
    c += bytes.fromhex("f30f590d") + struct.pack("<I", invk_va)     # mulss xmm1,[1/K]
    c += jmp(cave_c + len(c), SITE_C + 9)
    code += c

    rc = va2raw(secs, cave)
    if any(d[rc - 1:rc + len(code) + 1]) or cave + len(code) > 0x117C0:
        sys.exit("La zona libre de la cabecera no está vacía")
    d[rc:rc + len(code)] = code

    for site, cave_x, n in ((SITE_A, cave_a, 12), (SITE_B, cave_b, 13), (SITE_C, cave_c, 9)):
        r = va2raw(secs, site)
        d[r:r + n] = jmp(site, cave_x) + b"\x90" * (n - 5)

    open(dst, "wb").write(d)
    print("OK: %s  relación %s  K=%.6f" % (dst, ratio, k))


if __name__ == "__main__":
    main()

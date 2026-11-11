#!/usr/bin/env python3
"""Parche widescreen para Jade Empire (Xbox, MS-109).

Uso: python3 jade_empire_ws_patch.py jade_empire.xbe salida.xbe [relacion] [opciones]
     relacion por defecto 16:9 (también 16:10, 21:9...)
     --v1   solo 3D, toda la interfaz estirada
     --v2   3D + toda la interfaz en proporción (menús, letterbox y selección
            de personaje quedaban mal)
     --hud=a,b,c   paneles que se corrigen en v3 (por defecto %s)

v3 (por defecto):
  3D  - Igual que v1. El motor calcula aspect = ancho/alto del viewport
        (640/480). Se multiplica por K = relacion/(4/3) en 0x151FED (Hor+).
        Las conversiones pantalla<->mundo (0x152C40 / 0x1531E8) se corrigen
        x K para que los marcadores coincidan con la interfaz estirada.
  HUD - Toda la interfaz sigue estirada como en v1 (menús, cinemáticas,
        selección de personaje, textos) salvo los paneles del HUD principal:
        vida/chi/foco (playerstatus) y estilos de lucha (stylequick2,
        stylemap, styleflash, styleswitchbig).
        * CGui::Load (0xE4D6E) marca esos paneles por nombre (bit 30 de +0x34).
        * Al dibujar un panel marcado (0xE4C9C) se pone una ortográfica que
          lo encoge 1/K alrededor de su lado: si su centro está en el tercio
          izquierdo se ancla al borde izquierdo, en el derecho al borde
          derecho, si no al centro. Los elementos conservan su forma y
          siguen pegados al lateral.
        * Si el panel ocupa más de medio ancho, el anclaje se decide por cada
          control (0xE4CE8 / 0xE4CFD), para que una barra de la izquierda y un
          icono de la derecha del mismo panel vayan cada uno a su lado.
        * Al terminar el panel (0xE4D1C) se restaura la ortográfica 0..1.

  El código y las constantes nuevas van en una zona libre (ceros) de la
  cabecera XBE, que el kernel mantiene mapeada en 0x10000.
"""
import struct
import sys

BASE = 0x10000
CAVE_VA = 0x11100          # zona libre de la cabecera: 0x110BA-0x117C0
CAVE_END = 0x117C0
HUD_VA = 0x11400           # código del HUD v3 (fijo, ensamblado para esta base)

DEFAULT_HUD = ["playerstatus", "stylequick2", "stylemap", "styleflash",
               "styleswitchbig"]

SITE_A = 0x151FED          # divss xmm1,xmm0 ; mulss xmm0,[0x3198CC]
ORIG_A = bytes.fromhex("f30f5ec8" "f30f5905cc983100")
SITE_B = 0x152C40          # movss xmm1,[esp] ; mulss xmm6,xmm1 ; mulss xmm7,xmm1
ORIG_B = bytes.fromhex("f30f100c24" "f30f59f1" "f30f59f9")
SITE_C = 0x1531E8          # movaps xmm1,xmm0 ; mulss xmm1,[esp+38]
ORIG_C = bytes.fromhex("0f28c8" "f30f594c2438")

# Ortográfica de la interfaz: fldl [1.0] -> right ; fldl [0.0] -> left (v2)
ORTHO_R = (0x14B294, 0x154B20)   # dd 05 48 98 31 00
ORTHO_L = (0x14B29E, 0x154B2A)   # dd 05 08 99 31 00
ORIG_R = bytes.fromhex("dd0548983100")
ORIG_L = bytes.fromhex("dd0508993100")

# v3: código del HUD en HUD_VA. 0x11400-0x1143F: 4 pares de doubles (l, r)
# para anclaje izquierdo, centro, derecho y por defecto. Después el código
# (ensamblado con GNU as) y al final la lista de nombres.
HUD_CODE = bytes.fromhex(
    # 0x11440 set_ortho(edx -> l,r): llama 0x143FF0(l, r, 0, 1, -1, 1)
    "83ec30dd02dd1c24dd4208dd5c2408d9eedd5c2410d9e8dd5c2418d9e8d9e0dd5c2420"
    "d9e8dd5c2428e8822b130083c430c3"
    # 0x11472 pick(eax = 3*centro, ebx = panel) -> edx = par l,r
    "8b4b140fbf4910ba0014010039c87c1001c9ba2014010039c87f05ba10140100c3"
    # 0x11493 begin: si el panel está marcado, ortográfica según su centro
    "f643374074158b430cd1f80343048d0440e8c9ffffffe892ffffffd945088b03c3"
    # 0x114B4 ctl1 / 0x114C9 ctl2: anclaje por control y dibujo (+1C / +20)
    "8b0883ec04d91c2451e81c000000598b01ff501cc3"
    "8b0883ec04d91c2451e807000000598b01ff5020c3"
    # 0x114DE ctl_anchor: solo si el panel ocupa más de medio ancho
    "f6433740743d8b4b140fbf49108b430c01c039c87e2d8b4c24048b410cd1f8034104"
    "0fbf0d486c33008d0c890fbf0c4d508c330001c88d0440e856ffffffe81fffffffc3"
    # 0x11522 end: restaura 0..1 y salta a PopGuiFrame (0x14B640)
    "f6433740740aba30140100e80effffffe909a11300"
    # 0x11537 load: compara el nombre con la lista y marca el panel
    "895e28816634ffffffbf8b550c85d2742eb979150100803900742452518a013a0275"
    "0884c0740f4142ebf2595a418079ff0075f9ebe0595a814e34000000408b03c3"
)
H_BEGIN, H_CTL1, H_CTL2, H_END, H_LOAD, H_NAMES = (
    0x11493, 0x114B4, 0x114C9, 0x11522, 0x11537, 0x11579)

HUD_SITES = [
    # (va, original, destino, longitud, tipo)
    (0xE4C9C, bytes.fromhex("d94508" "8b03"), H_BEGIN, "call"),
    (0xE4CE8, bytes.fromhex("8b08" "8b01" "51" "d91c24" "ff501c"), H_CTL1, "call"),
    (0xE4CFD, bytes.fromhex("8b08" "8b01" "51" "d91c24" "ff5020"), H_CTL2, "call"),
    (0xE4D1C, bytes.fromhex("e81f690600"), H_END, "call"),
    (0xE4D6E, bytes.fromhex("895e28" "8b03"), H_LOAD, "call"),
]


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


def call(src, dst):
    return b"\xE8" + struct.pack("<i", dst - (src + 5))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = [a for a in sys.argv[1:] if a.startswith("--")]
    ver = "v3"
    hud = DEFAULT_HUD
    for o in opts:
        if o in ("--v1", "--v2"):
            ver = o[2:]
        elif o.startswith("--hud="):
            hud = [n for n in o[6:].split(",") if n]
        else:
            sys.exit("Opción desconocida: " + o)
    if len(args) < 2:
        print(__doc__ % ",".join(DEFAULT_HUD))
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
    checks += [(s[0], s[1]) for s in HUD_SITES]
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

    if ver in ("v1", "v3"):
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

    if cave + len(code) > HUD_VA:
        sys.exit("El código 3D no cabe antes de la zona del HUD")
    rc = va2raw(secs, cave)
    if any(d[rc - 1:CAVE_END - BASE]):
        sys.exit("La zona libre de la cabecera no está vacía")
    d[rc:rc + len(code)] = code

    for site, cave_x, n in jumps:
        r = va2raw(secs, site)
        d[r:r + n] = jmp(site, cave_x) + b"\x90" * (n - 5)

    if ver == "v2":
        for site in ORTHO_L:
            r = va2raw(secs, site)
            d[r + 2:r + 6] = struct.pack("<I", l_va)
        for site in ORTHO_R:
            r = va2raw(secs, site)
            d[r + 2:r + 6] = struct.pack("<I", r_va)

    if ver == "v3":
        pairs = struct.pack("<8d",
                            0.0, k,                          # ancla izquierda
                            0.5 - k / 2, 0.5 + k / 2,        # centro
                            1.0 - k, 1.0,                    # ancla derecha
                            0.0, 1.0)                        # por defecto
        names = b"".join(n.encode() + b"\0" for n in hud) + b"\0"
        blob = pairs + HUD_CODE + names
        assert HUD_VA + len(pairs) + len(HUD_CODE) == H_NAMES
        if HUD_VA + len(blob) > CAVE_END:
            sys.exit("Demasiados nombres de panel")
        r = va2raw(secs, HUD_VA)
        d[r:r + len(blob)] = blob
        for site, orig, dst_va, _ in HUD_SITES:
            r = va2raw(secs, site)
            d[r:r + len(orig)] = call(site, dst_va) + b"\x90" * (len(orig) - 5)

    open(dst, "wb").write(d)
    extra = ""
    if ver == "v2":
        extra = "  HUD x=[%.4f, %.4f]" % (0.5 - k / 2, 0.5 + k / 2)
    elif ver == "v3":
        extra = "  HUD: " + ", ".join(hud)
    print("OK: %s  %s  relación %s  K=%.6f%s" % (dst, ver, ratio, k, extra))


if __name__ == "__main__":
    main()

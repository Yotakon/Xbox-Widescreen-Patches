#!/usr/bin/env python3
"""Genera los IPS del HUD 2D de PES 5 (Xbox) para "PES 5 WS.xbe" (version 2: zona 0x3FFD20, modo 9 y banderas).

Idea: todo lo 2D se dibuja con vertices XYZRHW (X, Y ya en pixeles) por la
rutina D3D 0x4DD160 (DrawVerticesUP). Se engancha su entrada. El gancho mira
la direccion de retorno (cual de las 18 llamadas es), consulta una tabla de
modos y, segun el modo, reescribe la X de los vertices antes del dibujo y la
restaura despues (los buffers del juego quedan intactos).

Modos:  0 sin cambio | 1 centrado 4:3 | 2 anclado a la izquierda
        3 anclado a la derecha | 4 auto (lado mas cercano; a pantalla
        completa no se toca) | 5 PRUEBA: X x0,5 hacia la izquierda |
        6 centrado, pero lo que cubre todo el ancho no se toca |
        7 PRUEBA: X x0,5 hacia la derecha | 8 PRUEBA: X x0,5 al centro
Con W = ancho de pantalla ([0x7DDF08]): x' = 0,75 x + off,
off = W/8 (centrado), 0 (izq), W/4 (der).

El codigo va en 0x3FFD20 (4173 bytes de una rutina de la libreria sin
ninguna referencia). El gancho ocupa los 6 primeros bytes de 0x4DD160.
"""
import os, struct, sys
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_here, 'libs'), os.path.join(_here, '..', '.work', 'libs')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
import keystone

XBE_TEXT_VA, XBE_TEXT_RAW = 0x12000, 0x2000
D3D_VA, D3D_RAW = 0x4DB680, 0x400000

def va2off(va):
    if XBE_TEXT_VA <= va < XBE_TEXT_VA + 0x3FD8A4:
        return va - XBE_TEXT_VA + XBE_TEXT_RAW
    if D3D_VA <= va < D3D_VA + 0x105F0:
        return va - D3D_VA + D3D_RAW
    raise ValueError(hex(va))

HOOK_VA = 0x4DD160
HOOK_ORIG = bytes.fromhex('558bec83ec14')      # push ebp; mov ebp,esp; sub esp,14h
HOOK_RET = 0x4DD166
CAVE = 0x3FFD20          # codigo: rutina de la libreria sin ninguna llamada (0x3FFD20-0x40012B)
CODE_MAX = 0x40B
DATA = 0x40CE80          # datos: 742 bytes de otra rutina sin referencias
CONST = DATA
FLAGS = DATA + 0x80      # byte 0: barras a ancho completo; byte 1: menu principal a la izquierda
TABLE = DATA + 0xA0
CAVE_SIZE = 742
MAX_VERTS = 128

# (direccion de la llamada a 0x4DD160, nombre provisional)
CALLS = [
    (0x18F87, 'A1'), (0x1A377, 'A2'), (0x1A66C, 'A3'), (0x1AAE3, 'A4'),
    (0x1AF22, 'A5'), (0x1B3A5, 'A6'), (0x1C42D, 'A7'), (0x1C779, 'A8'),
    (0x8A3FF, 'B1'), (0x8A600, 'B2'), (0x8C301, 'B3'), (0x8C6F1, 'B4'),
    (0x8C893, 'B5'), (0x8D029, 'B6'), (0x8D516, 'B7'), (0x8FCFA, 'B8'),
    (0x90EF5, 'B9'), (0x91BC0, 'B10'),
]

K = dict(k075=0.75, k0125=0.125, k025=0.25, k04=0.4, k06=0.6, k002=0.02,
         k098=0.98, k05=0.5, k1=1.0,
         k0045=0.045, k094=0.94, k01=0.1, k012=0.12, k00625=0.0625, k052=0.52,
         k005=0.05, k039=0.39, k082=0.82)
KADDR = {n: CONST + 4 * i for i, n in enumerate(K)}

ASM = f"""
cave:
    push ebx
    push esi
    push edi
    push ebp
    mov eax, [esp+0x10]
    mov ebx, {TABLE}
find:
    mov ecx, [ebx]
    test ecx, ecx
    jz pass
    cmp ecx, eax
    je found
    add ebx, 8
    jmp find
found:
    mov ebp, [ebx+4]
    test ebp, ebp
    jz pass
    mov edi, [esp+0x18]
    lea eax, [edi-1]
    cmp eax, {MAX_VERTS - 1}
    ja pass
    mov esi, [esp+0x1c]
    mov edx, [esp+0x20]
    sub esp, {MAX_VERTS * 4}
    movss xmm0, [esi]
    movss xmm1, xmm0
    movss xmm3, [esi+4]
    movss xmm6, xmm3
    xor ecx, ecx
    mov ebx, esi
save:
    movss xmm2, [ebx]
    movss [esp+ecx*4], xmm2
    minss xmm0, xmm2
    maxss xmm1, xmm2
    movss xmm2, [ebx+4]
    minss xmm3, xmm2
    maxss xmm6, xmm2
    add ebx, edx
    inc ecx
    cmp ecx, edi
    jb save
    cvtsi2ss xmm7, dword ptr [0x7ddf08]
    movss xmm5, [{KADDR['k075']}]
    xorps xmm4, xmm4
    cmp ebp, 2
    je apply
    cmp ebp, 3
    je right
    cmp ebp, 4
    je auto
    cmp ebp, 6
    je auto
    cmp ebp, 9
    je sprite
    cmp ebp, 5
    je sql
    cmp ebp, 7
    je sqr
    cmp ebp, 8
    je sqc
    jmp center
sql:
    movss xmm5, [{KADDR['k05']}]
    jmp apply
sqr:
    movss xmm5, [{KADDR['k05']}]
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k05']}]
    jmp apply
sqc:
    movss xmm5, [{KADDR['k05']}]
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k025']}]
    jmp apply
center:
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k0125']}]
    jmp apply
right:
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k025']}]
    jmp apply
auto:
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k002']}]
    comiss xmm0, xmm2
    ja notfull
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k098']}]
    comiss xmm1, xmm2
    jb notfull
    movss xmm5, [{KADDR['k1']}]
    jmp apply
notfull:
    cmp ebp, 6
    je center
    addss xmm0, xmm1
    mulss xmm0, [{KADDR['k05']}]
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k04']}]
    comiss xmm0, xmm2
    jb apply
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k06']}]
    comiss xmm0, xmm2
    ja right
    jmp center
sprite:
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k002']}]
    comiss xmm0, xmm2
    ja sp_bars
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k098']}]
    comiss xmm1, xmm2
    jae sp_none
sp_bars:
    cmp byte ptr [{FLAGS}], 0
    je sp_list
    cvtsi2ss xmm4, dword ptr [0x7ddf0c]
    movss xmm2, xmm4
    mulss xmm2, [{KADDR['k012']}]
    comiss xmm6, xmm2
    jbe sp_none
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k0045']}]
    comiss xmm0, xmm2
    ja sp_list
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k094']}]
    comiss xmm1, xmm2
    jb sp_list
    mulss xmm4, [{KADDR['k01']}]
    movss xmm2, xmm6
    subss xmm2, xmm3
    comiss xmm2, xmm4
    jbe sp_none
sp_list:
    cmp byte ptr [{FLAGS + 1}], 0
    je center
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k00625']}]
    comiss xmm0, xmm2
    jb center
    movss xmm2, xmm7
    mulss xmm2, [{KADDR['k052']}]
    comiss xmm1, xmm2
    ja center
    movss xmm2, xmm1
    subss xmm2, xmm0
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k005']}]
    comiss xmm2, xmm4
    jb center
    movss xmm4, xmm7
    mulss xmm4, [{KADDR['k039']}]
    comiss xmm2, xmm4
    ja center
    cvtsi2ss xmm4, dword ptr [0x7ddf0c]
    movss xmm2, xmm4
    mulss xmm2, [{KADDR['k01']}]
    comiss xmm3, xmm2
    jb center
    movss xmm2, xmm4
    mulss xmm2, [{KADDR['k082']}]
    comiss xmm6, xmm2
    ja center
    mulss xmm4, [{KADDR['k012']}]
    movss xmm2, xmm6
    subss xmm2, xmm3
    comiss xmm2, xmm4
    ja center
    xorps xmm4, xmm4
    jmp apply
sp_none:
    movss xmm5, [{KADDR['k1']}]
    xorps xmm4, xmm4
    jmp apply
apply:
    mov ebx, esi
    xor ecx, ecx
xf:
    movss xmm2, [ebx]
    mulss xmm2, xmm5
    addss xmm2, xmm4
    movss [ebx], xmm2
    add ebx, edx
    inc ecx
    cmp ecx, edi
    jb xf
    push dword ptr [esp+{MAX_VERTS * 4 + 0x20}]
    push dword ptr [esp+{MAX_VERTS * 4 + 0x20}]
    push dword ptr [esp+{MAX_VERTS * 4 + 0x20}]
    push dword ptr [esp+{MAX_VERTS * 4 + 0x20}]
    call tramp
    mov esi, [esp+{MAX_VERTS * 4 + 0x1c}]
    mov edi, [esp+{MAX_VERTS * 4 + 0x18}]
    mov edx, [esp+{MAX_VERTS * 4 + 0x20}]
    mov ebx, esi
    xor ecx, ecx
restore:
    mov eax, [esp+ecx*4]
    mov [ebx], eax
    add ebx, edx
    inc ecx
    cmp ecx, edi
    jb restore
    add esp, {MAX_VERTS * 4}
    pop ebp
    pop edi
    pop esi
    pop ebx
    ret 0x10
pass:
    pop ebp
    pop edi
    pop esi
    pop ebx
tramp:
    push ebp
    mov ebp, esp
    sub esp, 0x14
    jmp {HOOK_RET}
"""


def assemble():
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    enc, _ = ks.asm(ASM, CAVE)
    return bytes(enc)


def build(modes, bars=0, menu=0):
    """modes: dict direccion_llamada -> modo. Devuelve {offset_archivo: bytes}."""
    code = assemble()
    assert len(code) <= CODE_MAX, len(code)
    consts = b''.join(struct.pack('<f', v) for v in K.values())
    table = b''.join(struct.pack('<II', a + 5, modes.get(a, 0)) for a, _ in CALLS) + b'\0' * 8
    assert 0xA0 + len(table) <= CAVE_SIZE and len(consts) <= 0x80
    rel = struct.pack('<i', CAVE - (HOOK_VA + 5))
    return {
        va2off(HOOK_VA): b'\xE9' + rel + b'\x90',
        va2off(CAVE): code,
        va2off(CONST): consts,
        va2off(FLAGS): bytes([bars, menu]),
        va2off(TABLE): table,
    }


def ips(patches):
    out = bytearray(b'PATCH')
    for off in sorted(patches):
        data = patches[off]
        assert off != 0x454F46 and len(data) < 0x10000
        out += off.to_bytes(3, 'big') + len(data).to_bytes(2, 'big') + data
    return bytes(out + b'EOF')


def apply(xbe, patches, check_orig=True):
    d = bytearray(xbe)
    for off, data in patches.items():
        d[off:off + len(data)] = data
    return bytes(d)


# Politica por llamada (identificada con las pasadas A y B):
#   0x8D516 mallas de interfaz (fondos, cabecera, marcos, paneles, lista del menu) -> modo 9
#   el resto -> modo 6 (centrado; lo que cubre todo el ancho no se toca)
ALL = [a for a, _ in CALLS]
POLICY = {a: 6 for a in ALL}
POLICY[0x8D516] = 9
VARIANTS = {'base': dict(modes=POLICY, bars=0, menu=0),
            'barras': dict(modes=POLICY, bars=1, menu=0),
            'menu_izquierda': dict(modes=POLICY, bars=0, menu=1),
            'barras_menu': dict(modes=POLICY, bars=1, menu=1)}


def part_ips(which):
    """IPS de una sola parte: solo cambia su bandera (se puede combinar con la base y con otras partes)."""
    off = va2off(FLAGS)
    return ips({off + which: b'\x01'})


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    for name, v in VARIANTS.items():
        open(os.path.join(outdir, f'PES5_HUD_{name}.ips'), 'wb').write(ips(build(v['modes'], v['bars'], v['menu'])))
    open(os.path.join(outdir, 'PES5_HUD_parte_barras.ips'), 'wb').write(part_ips(0))
    open(os.path.join(outdir, 'PES5_HUD_parte_menu_izquierda.ips'), 'wb').write(part_ips(1))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print(len(assemble()), 'bytes de codigo (maximo', CODE_MAX, ')')

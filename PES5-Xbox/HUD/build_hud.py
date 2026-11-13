#!/usr/bin/env python3
"""Genera los IPS del HUD 2D de PES 5 (Xbox) para "PES 5 WS.xbe".

Idea: todo lo 2D se dibuja con vertices XYZRHW (X, Y ya en pixeles) por la
rutina D3D 0x4DD160 (DrawVerticesUP). Se engancha su entrada. El gancho mira
la direccion de retorno (cual de las 18 llamadas es), consulta una tabla de
modos y, segun el modo, reescribe la X de los vertices antes del dibujo y la
restaura despues (los buffers del juego quedan intactos).

Modos:  0 sin cambio | 1 centrado 4:3 | 2 anclado a la izquierda
        3 anclado a la derecha | 4 auto (lado mas cercano; a pantalla
        completa no se toca) | 5 PRUEBA: X x0,5 hacia la izquierda
Con W = ancho de pantalla ([0x7DDF08]): x' = 0,75 x + off,
off = W/8 (centrado), 0 (izq), W/4 (der).

El codigo va en 0x40CE80 (742 bytes de una rutina SSE de la libreria sin
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
CAVE = 0x40CE80
CAVE_SIZE = 742
CONST = CAVE + 0x1B0
TABLE = CAVE + 0x200
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
         k098=0.98, k05=0.5, k1=1.0)
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
    xor ecx, ecx
    mov ebx, esi
save:
    movss xmm2, [ebx]
    movss [esp+ecx*4], xmm2
    minss xmm0, xmm2
    maxss xmm1, xmm2
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
    cmp ebp, 5
    jne center
    movss xmm5, [{KADDR['k05']}]
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


def build(modes):
    """modes: dict direccion_llamada -> modo. Devuelve {offset_archivo: bytes}."""
    code = assemble()
    assert len(code) <= 0x1B0, len(code)
    consts = b''.join(struct.pack('<f', v) for v in K.values())
    table = b''.join(struct.pack('<II', a + 5, modes.get(a, 0)) for a, _ in CALLS) + b'\0' * 8
    assert 0x200 + len(table) <= CAVE_SIZE
    rel = struct.pack('<i', CAVE - (HOOK_VA + 5))
    return {
        va2off(HOOK_VA): b'\xE9' + rel + b'\x90',
        va2off(CAVE): code,
        va2off(CONST): consts,
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


# Variantes: nombre -> {llamada: modo}
ALL = [a for a, _ in CALLS]
GROUPS = {
    'test1': ALL[0:4], 'test2': ALL[4:8], 'test3': ALL[8:12],
    'test4': ALL[12:16], 'test5': ALL[16:18],
}
VARIANTS = {
    'PES5_HUD_centrado': {a: 1 for a in ALL},
    'PES5_HUD_auto': {a: 4 for a in ALL},
}
for _n, _g in GROUPS.items():
    VARIANTS[f'PES5_HUD_prueba_{_n[-1]}'] = {a: 5 for a in _g}


def main(outdir, xbe_path=None):
    os.makedirs(outdir, exist_ok=True)
    for name, modes in VARIANTS.items():
        p = build(modes)
        open(os.path.join(outdir, name + '.ips'), 'wb').write(ips(p))
        print(name, {hex(a): m for a, m in modes.items()} if len(modes) < 6 else f'{len(modes)} llamadas, modo {set(modes.values())}')
        if xbe_path:
            data = open(xbe_path, 'rb').read()
            for off in p:
                pass


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print(len(assemble()), 'bytes de codigo (maximo', 0x1B0, ')')

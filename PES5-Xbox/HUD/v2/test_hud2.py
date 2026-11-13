import sys, struct
sys.path.insert(0, '/projects/sandbox/.work/libs'); sys.path.insert(0, '/projects/sandbox/.work')
from unicorn import *
import keystone
import build_hud2 as B

RET_BASE = 0x00200000
ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
INIT = (0x11111111, 0x22222222, 0x33333333, 0x44444444)


def run(mode, xs, ys=None, bars=0, menu=0, stride=0x1C, width=640, height=480, other=None):
    n = len(xs)
    ys = ys or [100.0 + i for i in range(n)]
    pre = ks.asm(f"""
        mov ebx, 0x11111111
        mov esi, 0x22222222
        mov edi, 0x33333333
        mov ebp, 0x44444444
        push {stride}
        push {0x150000}
        push {n}
        push 6
        call 0x4DD160
    """, RET_BASE)[0]
    ret = RET_BASE + len(pre)
    B.CALLS[0] = (ret - 5, 'T')
    patches = B.build({ret - 5: mode}, bars, menu)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x3F0000, 0x30000); mu.mem_map(0x4DD000, 0x1000); mu.mem_map(0x7DD000, 0x2000)
    mu.mem_map(0x100000, 0x100000); mu.mem_map(0x200000, 0x1000)
    for va in (B.CAVE, B.CONST, B.FLAGS, B.TABLE):
        mu.mem_write(va, patches[B.va2off(va)])
    stub = ks.asm("""
        push ebx
        push esi
        push edi
        mov eax, [ebp+0x10]
        mov [0x7DE000], eax
        mov eax, [ebp+0xc]
        mov [0x7DE004], eax
        mov esi, [ebp+0x10]
        mov ecx, [ebp+0xc]
        mov edx, [ebp+0x14]
        mov edi, 0x7DE100
    cp:
        mov eax, [esi]
        mov [edi], eax
        add esi, edx
        add edi, 4
        dec ecx
        jnz cp
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret 0x10
    """, 0x4DD166)[0]
    mu.mem_write(0x4DD166, bytes(stub))
    mu.mem_write(0x7DDF08, struct.pack('<I', width)); mu.mem_write(0x7DDF0C, struct.pack('<I', height))
    data = 0x150000
    for i in range(n):
        mu.mem_write(data + i * stride, struct.pack('<ff', xs[i], ys[i]) + b'\xAA' * (stride - 8))
    mu.mem_write(0x7DE000, b'\0' * 0x400)
    caller = ks.asm(f"""
        mov ebx, 0x11111111
        mov esi, 0x22222222
        mov edi, 0x33333333
        mov ebp, 0x44444444
        push {stride}
        push {data}
        push {n}
        push 6
        call 0x4DD160
        mov [0x7DE030], ebx
        mov [0x7DE034], esi
        mov [0x7DE038], edi
        mov [0x7DE03C], ebp
        mov [0x7DE040], esp
        hlt
    """, RET_BASE)[0]
    mu.mem_write(RET_BASE, bytes(caller))
    mu.mem_write(0x4DD160, patches[B.va2off(B.HOOK_VA)])
    mu.reg_write(0x2B if False else __import__('unicorn.x86_const', fromlist=['x']).UC_X86_REG_ESP, 0x1F0000)
    try:
        mu.emu_start(RET_BASE, RET_BASE + len(caller) - 1, count=300000)
    except UcError as e:
        if 'Invalid instruction' not in str(e) and 'Unhandled CPU exception' not in str(e):
            raise
    g = lambda a: struct.unpack('<I', mu.mem_read(a, 4))[0]
    seen = [struct.unpack('<f', mu.mem_read(0x7DE100 + 4 * i, 4))[0] for i in range(n)]
    after = [struct.unpack('<f', mu.mem_read(data + i * stride, 4))[0] for i in range(n)]
    regs = (g(0x7DE030), g(0x7DE034), g(0x7DE038), g(0x7DE03C))
    return dict(seen=seen, after=after, regs=regs, esp=g(0x7DE040), hits=g(0x7DE004))


ok = True
def check(name, cond):
    global ok
    print(('OK   ' if cond else 'FALLA'), name); ok &= bool(cond)

def rect(x0, y0, x1, y1): return [x0, x1, x0, x1], [y0, y0, y1, y1]
def centered(x): return 0.75 * x + 80
def left(x): return 0.75 * x

def expect(name, mode, rc, want, bars=0, menu=0):
    xs, ys = rect(*rc)
    r = run(mode, xs, ys, bars, menu)
    f = {'centro': centered, 'izq': left, 'nada': lambda v: v}[want]
    good = all(abs(a - f(b)) < 1e-3 for a, b in zip(r['seen'], xs)) and r['after'] == xs and r['regs'] == INIT and r['esp'] == 0x1F0000
    check(f'{name} [{rc}] bars={bars} menu={menu} -> {want}', good)

if __name__ == '__main__':
    # modos antiguos siguen igual (centrado 6)
    expect('modo 6 panel', 6, (100, 100, 300, 200), 'centro')
    expect('modo 6 fondo completo', 6, (0, 0, 640, 480), 'nada')
    # modo 9, sin banderas: igual que modo 6 salvo ancho completo
    expect('modo 9 base panel', 9, (100, 100, 300, 200), 'centro')
    expect('modo 9 base fondo', 9, (0, 0, 640, 480), 'nada')
    expect('modo 9 base cabecera sin bandera', 9, (0, 0, 640, 40), 'nada')   # ancho completo: no se toca (regla antigua)
    expect('modo 9 base marco inferior sin bandera', 9, (16, 412, 622, 437), 'centro')
    expect('modo 9 base lista menu sin bandera', 9, (65, 88, 287, 108), 'centro')
    # barras
    expect('barras: marco inferior (16..622, y412..437)', 9, (16, 412, 622, 437), 'nada', bars=1)
    expect('barras: cabecera con huecos laterales (30..610, y0..40)', 9, (30, 0, 610, 40), 'nada', bars=1)
    expect('barras: pieza de cabecera estrecha (200..330, y0..42)', 9, (200, 0, 330, 42), 'nada', bars=1)
    expect('barras: panel grande no se toca como barra (12..500, y100..445)', 9, (12, 100, 500, 445), 'centro', bars=1)
    expect('barras: pieza ancha pero alta (16..622, y100..300)', 9, (16, 100, 622, 300), 'centro', bars=1)
    expect('barras: fila de lista en el centro (150..450, y200..230)', 9, (150, 200, 450, 230), 'centro', bars=1)
    # menu izquierda
    for nm, rc in (('PARTIDO', (85, 88, 197, 108)), ('LIGA MASTER', (80, 120, 245, 142)), ('LIGA', (71, 153, 131, 175)),
                   ('ENTRENAMIENTO', (65, 205, 287, 228)), ('XBOX LIVE', (100, 329, 235, 350))):
        expect(f'menu: {nm}', 9, rc, 'izq', menu=1)
    expect('menu: sin bandera sigue centrado', 9, (85, 88, 197, 108), 'centro', menu=0)
    expect('menu: panel central no se ancla (240..400)', 9, (240, 150, 400, 175), 'centro', menu=1)
    expect('menu: panel ancho no se ancla (30..330, y100..400)', 9, (30, 100, 330, 400), 'centro', menu=1)
    expect('menu: elemento a la derecha no se ancla', 9, (400, 200, 600, 225), 'centro', menu=1)
    expect('menu: elemento muy alto no se ancla (70..250, y90..300)', 9, (70, 90, 250, 300), 'centro', menu=1)
    expect('menu: pegado al borde (0..200) no se ancla (es fondo parcial)', 9, (0, 100, 200, 125), 'centro', menu=1)
    # las dos banderas juntas
    expect('ambas: marco inferior', 9, (16, 412, 622, 437), 'nada', bars=1, menu=1)
    expect('ambas: PARTIDO', 9, (85, 88, 197, 108), 'izq', bars=1, menu=1)
    # otros modos no se ven afectados por las banderas
    expect('modo 6 con banderas activas', 6, (85, 88, 197, 108), 'centro', bars=1, menu=1)
    # tabla completa: 18 llamadas con politica
    t = B.build(B.POLICY)
    check('POLICY: 0x8D516 en modo 9, el resto en modo 6', B.POLICY[0x8D516] == 9 and all(m == 6 for a, m in B.POLICY.items() if a != 0x8D516))
    # limites de vertices / stride 0x34
    xs, ys = rect(85, 88, 197, 108)
    r = run(9, xs * 32, ys * 32, 0, 1, stride=0x34)
    check('128 vertices stride 0x34 con regla de menu', abs(r['seen'][0] - 63.75) < 1e-3 and r['after'] == xs * 32)
    print('TODO OK' if ok else 'HAY FALLOS')

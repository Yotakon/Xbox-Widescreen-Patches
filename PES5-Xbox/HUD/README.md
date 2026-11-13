# PES 5 Xbox: corrección del HUD 2D (pruebas)

Se aplican sobre `PES 5 WS.xbe` (MD5 922e4e9252d3e57c0c328b53649380ab) o sobre el original con
`PES5_Xbox_widescreen.ips` + `PES5_Xbox_letterbox_fix.ips` + el byte 0x910BC0 (8B -> C3).
Dan el mismo resultado de las dos formas. **Aplica solo uno de estos IPS a la vez**: los siete
contienen el mismo gancho y se pisan entre sí. No chocan con la ampliación de caras.

## Qué hacen

Todo lo 2D se dibuja con vértices en píxeles (XYZRHW) por la rutina D3D de VA `0x4DD160`.
Los IPS enganchan esa rutina. Según qué llamada la invoque (hay 18), el gancho reescribe la X de
los vértices antes de dibujar y la restaura después. No se modifica ningún dato del juego.
El código nuevo ocupa la rutina sin uso de VA `0x40CE80` (742 bytes).

Con W = ancho de pantalla (640): `x' = 0,75 x + desplazamiento`.

| IPS | Qué hace |
|---|---|
| `PES5_HUD_centrado` | Todo el 2D en la zona 4:3 centrada (desplazamiento W/8). |
| `PES5_HUD_auto` | Cada dibujo se ancla al lado más cercano según su centro: izquierda (< 40 % del ancho), derecha (> 60 %) o centrado. Lo que cubre toda la pantalla (fondos, fundidos) no se toca. |
| `PES5_HUD_prueba_1` ... `_5` | Para identificar qué dibuja cada llamada: comprimen a la mitad (X x0,5, pegado a la izquierda) solo un grupo de llamadas. |

## Qué mirar en las pruebas

Con cada `prueba_N` abre varias pantallas (menú principal, un menú desplegable, modo editar, el
partido, repeticiones, pausa) y apunta qué elementos se ven aplastados contra la mitad izquierda.
Cada elemento solo debería aparecer en una prueba. Los grupos:

| IPS | Llamadas (dirección de la llamada a 0x4DD160) |
|---|---|
| `prueba_1` | 0x18F87, 0x1A377, 0x1A66C, 0x1AAE3 |
| `prueba_2` | 0x1AF22, 0x1B3A5, 0x1C42D, 0x1C779 |
| `prueba_3` | 0x8A3FF, 0x8A600, 0x8C301, 0x8C6F1 |
| `prueba_4` | 0x8C893, 0x8D029, 0x8D516, 0x8FCFA |
| `prueba_5` | 0x90EF5, 0x91BC0 |

Con eso se hará un IPS por parte (cada uno cambia solo 4 bytes de la tabla de modos).

## Límites conocidos

- Solo cubre las 18 llamadas a `DrawVerticesUP`. Lo que se dibuje con buffers de vértices
  (`0x4DD2D0`, `0x4DD370`) no se toca; los llamadores revisados son 3D.
- Si un dibujo tiene más de 128 vértices se deja sin tocar.
- Un elemento anclado por separado puede quedar desplazado respecto a otros del mismo menú
  (por ejemplo una barra de selección y su lista). Por eso existe el modo centrado.
- Probado solo en emulador x86 (unicorn) y comprobando los bytes; no en consola.

## Regenerar

`python3 build_hud.py <carpeta_salida>` (necesita `keystone-engine`).

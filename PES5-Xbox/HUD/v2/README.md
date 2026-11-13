# HUD 2D, versión 2 (sobre `PES 5 WS.xbe`, MD5 922e4e9252d3e57c0c328b53649380ab)

## Qué dibuja cada llamada (resultado de las pasadas A y B)

| Llamada | Qué dibuja |
|---|---|
| 0x8D516 | Mallas de interfaz: fondos, cabecera, marco de la barra inferior, paneles y la lista de imágenes del menú principal |
| 0x8D029 | Todo el texto (títulos, mensaje inferior, "Sesión iniciada", marcador) |
| 0x8FCFA | Iconos, banderas y escudos |
| 0x8A600 | Barras e iconos de "Seleccionar modo" y piezas del HUD del partido |
| 0x8C301 | Cursor azul de selección y panel de diálogo |
| 0x18F87 | Logo PES de la pantalla de carga negra |
| 0x1A66C, 0x1AAE3, 0x1A377 | Dibujo final de una textura a pantalla completa |
| 0x1C779 | Velo del fundido |

El resto de llamadas (0x1AF22, 0x1B3A5, 0x1C42D, 0x8A3FF, 0x8C6F1, 0x8C893, 0x90EF5, 0x91BC0) aún no
tienen un elemento asignado (no aparecieron en las capturas).

## Política

Todas las llamadas usan el modo 6 (centrado x' = 0,75 x + W/8; lo que cubre todo el ancho no se toca),
salvo 0x8D516, que usa el modo 9: igual que el 6, y además dos reglas opcionales según su geometría,
activadas cada una con un byte (así se prueban por separado):

| Parte | Byte (VA 0x40CF00 + n (0x40CE80 + 0x80)) | Qué hace |
|---|---|---|
| `parte_barras` | +0 | En 0x8D516, un objeto entero dentro del 12 % superior de la pantalla (cabecera), o una barra baja (< 10 % del alto) que cubra de ~4,5 % a ~94 % del ancho (marco de la barra de texto inferior) se deja sin tocar, o sea a todo el ancho. |
| `parte_menu_izquierda` | +1 | En 0x8D516, un objeto de la lista del menú principal (en la mitad izquierda, 5 %-39 % del ancho, 12 % de alto como máximo, entre el 10 % y el 82 % de la altura) se pega al borde izquierdo (x' = 0,75 x). |

El texto sigue centrado siempre, para que no se descoloque respecto a su recuadro.

## Cómo aplicarlo

1. `PES5_HUD_base.ips` sobre `PES 5 WS.xbe`: no corrige nada, solo instala el gancho (centrado con excepción de ancho completo).
2. Después, una o varias de las partes: `PES5_HUD_parte_barras.ips`, `PES5_HUD_parte_menu_izquierda.ips`.

Los IPS completos `PES5_HUD_barras.ips`, `PES5_HUD_menu_izquierda.ips` y `PES5_HUD_barras_menu.ips` ya llevan
la base y la(s) parte(s) incluidas, para quien prefiera un solo parche.

| Ejecutable (ya parcheado) | MD5 |
|---|---|
| `PES 5 WS_HUD_base.xbe` | 500782dcffd1acee7554083ef5cae113 |
| `PES 5 WS_HUD_barras.xbe` | 000392940dfa2814e2eef2733316e5da |
| `PES 5 WS_HUD_menu_izquierda.xbe` | 20afd0f13dea9be7989c0ec82c7bef04 |

## Límites

- Las reglas son por geometría y están medidas a ojo en tus capturas; pueden dejar fuera una pieza de la
  cabecera o anclar algún objeto que no sea parte del menú. Si pasa, dime en qué pantalla.
- Probado en un emulador x86 con las geometrías medidas (30 pruebas) y comprobando los bytes; no en consola.
- Código nuevo en 0x3FFD20 (rutina de la librería sin llamadas) y datos en 0x40CE80.
  Con la ampliación de caras (0x4EF7E8 y 0x578xxx) no choca.

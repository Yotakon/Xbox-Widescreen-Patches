# Identificación exacta de las llamadas de dibujo (2 pasadas)

Base: `PES 5 WS.xbe` (MD5 922e4e9252d3e57c0c328b53649380ab). Desde ahora todos los parches se aplican a ese XBE.

Cada una de las 14 llamadas por identificar recibe en cada pasada un estado: sin cambio, aplastada a la
mitad izquierda, a la mitad derecha o a la mitad central de la pantalla. Cada llamada tiene una
combinación (pasada A, pasada B) distinta, así que con una captura de cada pasada de la misma pantalla
se sabe qué llamada dibuja cada elemento. Las cuatro ya identificadas (dibujos finales y velo del
fundido) van en modo 6 (centrado, sin tocar lo de ancho completo).

| Archivo | MD5 |
|---|---|
| `PES 5 WS_ident_A.xbe` | 68cee91360b790bf615bf7ffdda10bb6 |
| `PES 5 WS_ident_B.xbe` | e495b4629cd386e13c6b18f9b910a929 |

Pantallas a capturar en cada pasada (mismo punto de la pantalla en A y en B):
menú principal, "Ajustes generales" (cabecera + barra inferior), "Selección del Uniforme",
"Configuración personal", selección de equipo y la alineación de antes del partido.
Si puedes, también el marcador y el radar durante un partido.

Tabla de decodificación (solo para quien interprete las capturas):

| Llamada | Pasada A | Pasada B |
|---|---|---|
| 0x18F87 | izquierda | sin cambio |
| 0x1AF22 | derecha | sin cambio |
| 0x1B3A5 | centro | sin cambio |
| 0x1C42D | sin cambio | izquierda |
| 0x8A3FF | sin cambio | derecha |
| 0x8A600 | sin cambio | centro |
| 0x8C301 | izquierda | izquierda |
| 0x8C6F1 | derecha | derecha |
| 0x8C893 | centro | centro |
| 0x8D029 | izquierda | derecha |
| 0x8D516 | derecha | izquierda |
| 0x8FCFA | izquierda | centro |
| 0x90EF5 | centro | izquierda |
| 0x91BC0 | derecha | centro |

Nota: `build_hud.py` se reorganizó para estos IPS (más código, constantes y tabla desplazadas). Los IPS
anteriores se siguen comportando igual, pero regenerarlos con este script da bytes distintos.

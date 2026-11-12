# PES 5 (Xbox): parches widescreen y letterbox fix

Parches IPS para el `default.xbe` original de Pro Evolution Soccer 5 de Xbox (MD5 `b574d29e94f57b48938d9587619e39b9`, 11 513 856 bytes). Se sacaron comparando ese XBE con `PES 5 WS.xbe`.

Aplica los dos para obtener el resultado probado. El orden da igual: no tocan los mismos bytes.

| Archivo | MD5 | Qué cambia |
|---|---|---|
| `PES5_Xbox_letterbox_fix.ips` | `500debe46435c493da337d3bf5a03272` | Altura de pantalla de 448 a 480 líneas (448→480, 224→240, margen 16→0), escala de pantalla 0,97→1,0, correcciones verticales del HUD (-2→-1,8667 y 0,5→0,5357) y anula la función de `0x7B870` |
| `PES5_Xbox_widescreen.ips` | `b88998328cd888fb8d742c456db661ce` | Marca de 16:9 al crear el dispositivo (`0x100`→`0x110`, D3DPRESENTFLAG_WIDESCREEN), proyección en X por 4/3 e Y por 480/448, y escala horizontal del HUD (2→1,5 y 0,5→0,6667) |

Notas:
- El widescreen también corrige la altura en la proyección (Y por 480/448), así que está pensado para usarse junto al letterbox fix.
- La división entre los dos parches se hizo analizando qué hace cada cambio. Por separado no están probados.
- Los dos usan huecos de relleno (`CC`) del `.text` para guardar constantes nuevas: offsets `0x10368`, `0x103B3`, `0x10564` y `0x105B2`.

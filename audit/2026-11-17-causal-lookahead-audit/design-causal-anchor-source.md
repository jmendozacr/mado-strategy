# Diseño: mecanismo causal correcto para el anchor M15 de Model-1

Read-only / diseño únicamente. No se modificó `detector/`, `scanner/` ni `docs/`. No se implementó código nuevo. No se ejecutó ningún backtest.

## Fase 1 — Regla documental

Fuentes leídas en su totalidad: `docs/charter-1.md`, `docs/charter-2.md`; grep dirigido sobre `docs/charter-9.md`, `docs/charter-10.md`, `docs/charter-11.md` (las charters de la receta 1AM/5AM/9AM específica).

### 1. ¿Qué máximos y mínimos pueden utilizarse como referencia para una purga Model-1?

Charter-2 [00:03:51] es explícito y da DOS categorías, no una:

> "El precio extrae liquidez al barrer por encima de un Alto o por debajo de un Bajo (**ya sean CRT High/Low o viejos Altos/Bajos**)."

Charter-11 [00:21:17-00:21:59] lo reafirma con la definición más simple y operativa de todo el corpus:

> "the entry model is Model 1: **the candle that dips below a prior low (or above a prior high)** and then gets engulfed by the following candle or candles"

Y charter-10 [00:16:23-00:16:37] da un ejemplo concreto con nombre propio: "the 5 AM candle opens, **purges the 1 AM low**, waits for Model 1 confirmation" — el nivel referenciado es simplemente el low de UNA vela nombrada (la vela de 1 AM), no un rango clasificado.

**Conclusión**: el universo de niveles válidos es "cualquier Alto o Bajo previo" — CRT High/Low (el alto/bajo de una vela-rango reconocida) O un Alto/Bajo viejo sin relación necesaria con un CRT específico. Ninguna fuente limita esto a un subconjunto clasificado.

### 2. ¿Se necesita que un CRT esté formalmente resuelto?

**No, en ninguna de las 5 charters leídas.** Charter-1 [00:06:48-00:07:03] define True Break / False Break como una DESCRIPCIÓN RETROSPECTIVA de lo que el precio hace DESPUÉS de que el CRT High/Low ya existe y ya es referenciable (el Alto/Bajo de la Vela 1 está disponible desde que esa vela cierra; "True Break" y "False Break" son las dos conductas posibles que el mercado puede tener SOBRE ese nivel ya conocido, no una condición para que el nivel exista o sea válido).

La definición operativa de Model-1 (charter-2 §30-31, charter-11 línea 113) nunca menciona clasificación, resolución, ni una ventana de velas para resolver — solo "purga" + "engulf". Ningún ejemplo gráfico (charter-2 Ejemplos 1-3, charter-9/10/11) condiciona la validez de la vela de purga a que el rango que la originó haya sido clasificado como true_break/false_break.

### 3. ¿Puede utilizarse el high/low de una vela M15 que ya cerró, aunque su CRT todavía no esté resuelto?

Sí, consistente con la respuesta a 2: el Alto/Bajo de una vela es un dato observable en el instante en que esa vela cierra (charter-1 [00:02:34], [00:05:32] — toda vela tiene Open/High/Low/Close con la misma anatomía, disponibles al cierre). Nada exige esperar a que un ciclo de 20 velas (u otro número) determine si esa vela "resolvió" como true o false break antes de poder referenciar su Alto/Bajo.

### 4. Diferencia entre CRT High/Low, viejos High/Low y swings confirmados — NO son equivalentes

Verifiqué esto contra el código, no solo contra la documentación, para no repetir el error de la ronda anterior:

| Concepto | Definición | Fuente | Disponibilidad |
|---|---|---|---|
| **CRT High/Low** | El Alto/Bajo de UNA vela específica reconocida como "Vela 1" de un Candle Range, en la temporalidad correspondiente de la tabla de alineación (charter-2 §134). | charter-1 [00:03:35] | Inmediata al cierre de esa vela — ninguna condición adicional. |
| **Viejos Altos/Bajos** | Cualquier extremo previo relevante, sin atadura necesaria a un ciclo CRT específico — categoría amplia y no algorítmicamente definida en ninguna charter. | charter-2 [00:03:51], charter-11 línea 113 ("a prior low"/"a prior high") | Inmediata — es simplemente un precio ya observado. |
| **Swing confirmado** | Pivote fractal de 3 velas: `candles[i].high > candles[i-1].high AND candles[i].high > candles[i+1].high` (`primitives/swing.py::detect_swings`, leído directamente). Requiere que la vela `i+1` YA HAYA CERRADO para confirmarse. | Código del detector, NO una charter | Retrasada 1 vela — y es un subconjunto mucho más angosto (solo pivotes locales, no cualquier Alto/Bajo). |

La única mención textual de "Swing High/Low" en charter-2 es en el contexto del **Stop Loss** (§155: "por encima del Alto/Bajo de la vela de purga, o por encima del Swing High/Low"), nunca para seleccionar el nivel que se purga. Sustituir el ancla de Model-1 por `detect_swings` (mi propuesta de la ronda anterior, correctamente bloqueada) habría introducido un filtro adicional no documentado: excluye cualquier Alto/Bajo que no sea un pivote local de 3 velas, cuando charter-1 trata a CADA vela como una referencia válida.

## Fase 2 — Análisis del código (`primitives/crt_range.py` + `causal/htf_trigger.py::confirm_in_ltf_window`)

`detect_crt_ranges` mezcla cuatro cosas que la documentación nunca ata entre sí:

1. **Niveles de precio observables** — `range_high = candles[i].high`, `range_low = candles[i].low`. Esto, y solo esto, es "CRT High/Low" según charter-1. Disponible al cierre de la vela `i`, sin dependencia del futuro.
2. **Resolución posterior** (`_resolve()`, hasta `max_lookback=20` velas) — determina CUÁNDO y CÓMO se rompe el rango. Información retrospectiva, usada en la documentación solo para DESCRIBIR el comportamiento posterior del precio, nunca para habilitar el nivel.
3. **Clasificación del modelo** (`_classify_model`: 2-candle/3-candle/multi-inside/multi-outside) — etiqueta descriptiva derivada de (2), sin mención en ninguna charter como requisito de Model-1.
4. **Selección del anchor** (en `confirm_in_ltf_window`, NO en `detect_crt_ranges`) — busca, entre los rangos de `ltf_ranges` (que YA vienen pre-filtrados por el paso 2), cuál produce el primer breach dentro de la ventana, y entre los candidatos elige el de `anchor_index` más temprano, con empate roto por `start_index` más bajo (`confirm_in_ltf_window`, líneas 188-203, leídas directamente).

**Requisitos reales de Model-1** (de la documentación): (1) existe un Alto o Bajo; (2) se barre; (3) la vela que barrió es envuelta por un cierre de cuerpo.

**Restricciones introducidas por el detector, no mandatadas por la documentación**:
- (a) El nivel solo es elegible si, en retrospectiva, alguna vela dentro de las siguientes 20 velas M15 (5 horas) lo rompe de forma clasificable — esto es **existencia condicionada al futuro**, el hallazgo central de la auditoría anterior. Un Alto/Bajo barrido 6 horas después de formarse (perfectamente válido como "viejo Alto/Bajo" según charter-2) queda excluido para siempre.
- (b) Esa ruptura debe clasificar específicamente como `true_break` o `false_break` vía el algoritmo de cierre-más-allá-del-punto-medio — un criterio más estricto que el simple "purga + engulf" que exige Model-1.
- (c) El empate entre múltiples candidatos se rompe por "anchor más temprano gana" — una regla inventada en `confirm_in_ltf_window`, nunca verificada contra el único ejemplo documental de selección entre candidatos (ver ambigüedad #2 abajo).

## Fase 3 — Alternativas de diseño causal (no implementadas)

Todas las alternativas comparten: el `anchor_index`, `direction`, `purge_target` y `origin_index` resultantes alimentan `_track_anchor` exactamente como hoy — engulf, invalidación, retest, confirmación, activación de órdenes, SL y TP quedan **intactos y sin tocar** (verificado leyendo `entries/model1.py::_track_anchor`: no depende de cómo se eligió el anchor, solo de `anchor_index`/`purge_target`/`direction`).

### Alternativa 1 — Todo Alto/Bajo previo no roto, acotado por una ventana explícita (recomendada, más fiel al texto)

Cada vela M15, al cerrar, se vuelve candidata inmediata ("abierta") como posible CRT High/Low — sin esperar clasificación. Una candidata deja de ser elegible cuando: (a) se rompe (breach), o (b) excede una ventana de antigüedad explícita (ver ambigüedad #1). La clasificación true/false-break puede seguir calculándose aparte, de forma perezosa, solo como metadato descriptivo — nunca como condición de elegibilidad.

Esto opera exactamente sobre el "any prior high/low" de charter-11 línea 113, sin inventar ningún filtro adicional.

### Alternativa 2 — Solo swings confirmados (NO recomendada, ya bloqueada)

La incluyo solo para que quede explícitamente descartada con razones, no omitida: usar `detect_swings` como única fuente introduce un filtro (pivote local de 3 velas) que ninguna charter exige para el nivel que se purga, y excluiría niveles que la producción actual SÍ considera hoy (cualquier `start_index` de `detect_crt_ranges`, es decir, cualquier vela). Cambiaría la metodología, tal como señalaste.

### Alternativa 3 — Igual a la Alternativa 1, pero reteniendo la clasificación como metadato separado

Idéntica a la Alternativa 1 en la selección del anchor; la diferencia es solo de implementación interna (si se conserva o no el cálculo de `true_break`/`false_break` para otros usos, p. ej. reportes). No cambia ninguna decisión de Model-1.

## Fase 4 — Tests propuestos (diseño, no implementados)

Principio general: dos historias que comparten exactamente el mismo pasado hasta un instante T deben producir las MISMAS decisiones del detector hasta T, sin importar cómo diverjan después.

1. **CRT que resuelve inmediatamente**: historias A y B comparten velas 0..N, donde la vela N barre un Alto previo y cierra de vuelta dentro del rango en la vela N+1 (lo que el código actual clasificaría como false_break de 2 velas). A partir de N+2 divergen: A continúa revirtiendo, B cambia de signo y termina cerrando más allá (lo que el código actual reclasificaría retroactivamente como true_break). **Esperado**: el anchor seleccionado en la vela N debe ser idéntico en A y B — el diseño nuevo no debe depender de cómo termine clasificando el rango.
2. **CRT que resuelve varias velas después** (ej. el caso real encontrado en la auditoría, `gap_bars=8`): exacto mismo principio, con la divergencia ubicada varias velas después del breach.
3. **CRT que nunca llega a resolverse** (ni siquiera dentro de las 20 velas del `max_lookback` actual): el código actual excluiría ese Alto/Bajo para siempre. El diseño nuevo debe seguir tratándolo como anchor elegible en el instante del breach, sin importar qué pase después (o si nunca "resuelve" en el sentido viejo).
4. **Retry-on-invalidation**: historias que comparten el pasado hasta una purga + engulf fallido (INVALIDATED, disparando el retry de `_track_anchor` con `current_anchor` reasignado) y divergen después. Las decisiones hasta el punto de invalidación deben ser idénticas.
5. **Barrida de un Alto/Bajo "viejo"**, más antiguo que cualquier `max_lookback` actual (ej. una vela de hace 40+ velas M15, sin relación con un CRT de 2 velas): el código actual nunca la habría hecho elegible. El resultado esperado de este test depende directamente de qué ventana de antigüedad se decida en la ambigüedad #1 — lo marco explícitamente, no lo resuelvo yo.

## Ambigüedades documentales — decisiones del usuario (2026-11-18)

1. **Ventana de antigüedad — corregida tras una segunda revisión del usuario.** Primera decisión: reutilizar `max_lookback=20` velas M15 (5h), resignificadas como ventana de ANTIGÜEDAD del nivel, no de resolución. El usuario objetó correctamente: 20 velas (5h) es MÁS que la duración de una vela feeder completa (4h = 16 velas M15), y no corresponde a nada de la arquitectura real de este recipe (1AM/5AM/9AM). Verificado contra `causal/htf_trigger.py`: las ventanas de búsqueda reales (`MODEL_1AM.window_duration=2h`/8 velas, `MODEL_9AM.window_duration=1.5h`/6 velas) ya son mucho más cortas y SÍ están sacadas de las charters (charter-8, charter-10, charter-11) — ese punto ya estaba bien. Lo que estaba mal era la ventana de antigüedad del NIVEL referenciado: charter-10/11 describen el nivel purgado como la vela feeder inmediatamente anterior completa ("the 5 AM candle... purges the 1 AM low"), y una vela feeder dura exactamente 4h = 16 velas M15. **Decisión final: 16 velas M15 (4h), no 20** — coincide exactamente con la duración de una vela feeder, a diferencia de 20, que no corresponde a nada documentado.
2. **Regla de empate entre candidatos**: el código actual elige el `anchor_index` más temprano entre todos los rangos candidatos. El único ejemplo documental de selección entre candidatos (charter-2, reacción en M, [00:21:34]) compara dos TIPOS de Model-1 (purga vs. FVG-fill), no dos rangos candidatos del mismo tipo, así que no confirma ni contradice directamente la regla actual. **Decisión: mantener earliest-anchor-wins, tie-break por `start_index` más bajo, sin cambios de comportamiento en este punto.**

## Diseño causal único, resuelto (no implementado todavía)

Con ambas decisiones fijadas, la Alternativa 1 queda completamente especificada:

- **Candidatos**: cada vela M15, al cerrar, se vuelve candidata inmediata de "Alto/Bajo previo" — sin exigir clasificación true/false-break. Deja de ser candidata cuando: (a) se rompe (breach, el mismo criterio de wick que usa `first_breach_index` hoy), o (b) transcurren **16 velas M15 (4h, una vela feeder completa)** desde que esa vela cerró sin que nadie la rompa (ventana de antigüedad, no de resolución).
- **Selección entre candidatos dentro de la ventana de búsqueda**: igual que hoy — el `anchor_index` (breach) más temprano gana; empate roto por `start_index` más bajo. La ventana de búsqueda en sí (`MODEL_1AM`/`MODEL_9AM.window_duration`, floored en `activation_instant_ts`) no cambia — ya es charter-correcta.
- **Todo lo demás permanece exactamente igual**: `_track_anchor` (engulf/invalidación/retest/confirmación), activación de órdenes, SL, TP — ninguno de estos depende de cómo se eligió el anchor, confirmado leyendo `entries/model1.py` directamente.
- **La clasificación true/false-break de `detect_crt_ranges`** deja de ser un gate de elegibilidad para Model-1; puede conservarse como metadato descriptivo para otros usos (reportes, estadísticas por tipo de modelo) sin afectar esta selección — eso es una decisión de implementación separada, no necesaria para cerrar este diseño.

Esto NO se implementó en este turno — queda a la espera de autorización explícita para pasar a código (incluyendo, antes de escribir el fix en producción, los 5 tests de la Fase 4 diseñados arriba, que deben poder expresarse y fallar/pasar contra el nuevo mecanismo antes de integrarlo).

**Nota de corrección (ronda 3, ver abajo)**: la afirmación de la línea anterior "la ventana de búsqueda en sí... no cambia — ya es charter-correcta" queda SUPERADA para el modelo 9AM específicamente — el usuario aclaró reglas operativas nuevas que amplían esa ventana. Para 1AM, esa afirmación sigue vigente sin cambios. Ver §Cierre de diseño — ronda 3.

---

# Cierre de diseño — ronda 3: reglas operativas 9AM, separación de dos modificaciones, formalización de antigüedad

Read-only / diseño únicamente. No implementado. No ejecutado backtest. No se tocó `detector/`, `scanner/`, `docs/`, ni los CSV históricos A/B1/B2/C1/C2.

## 0. Corrección encontrada durante la preparación de la implementación (antes de escribir código)

Al revisar `run_c1_c2.py` para planear qué compartir entre D1/D2/D3, encontré que mi descripción de "hoy" en §1/§4 estaba mal. Verificado leyendo `run_c1`/`run_c2` directamente: `window_close_ts = window_open_ts + ci.H4_DURATION` (4h completas) se pasa a `detect_sweep_and_key_level` HOY, para los dos modelos — es decir, la detección de barrido+Key Level YA escanea la vela feeder COMPLETA (09:00-13:00 para el 9AM), sin ningún tope explícito de activación a las 10:30. El límite efectivo de 10:30 que yo describía como "la ventana de activación de hoy" en realidad viene de otro lado: `build_causal_signal` calcula `window_end` vía `confirmation_window_utc` (10:30 para 9AM) y, si `activation_instant_ts >= window_end`, devuelve `zero_signal_reason` sin señal — es decir, hoy una activación detectada entre 10:30 y 13:00 SÍ se detecta, pero nunca produce señal porque la ventana del Modelo #1 ya cerró.

Esto cambia lo que "Modificación 2" realmente mueve:
- **Detección de activación**: hoy, implícitamente, hasta 13:00 (sin tope propio). La regla nueva le pone un tope EXPLÍCITO e independiente a las 11:00 — en términos del parámetro real (`window_close_ts` de `detect_sweep_and_key_level`), esto es más ESTRICTO que hoy (2h en vez de 4h), aunque más ancho que el límite EFECTIVO indirecto de hoy (11:00 > 10:30).
- **Ventana de Modelo #1**: hoy, cierra a las 10:30 (1.5h desde la apertura). La regla nueva la extiende hasta las 13:00 (el cierre de la propia vela feeder) — esto sí es una ampliación directa y explícita.

Implicación para D1/D2/D3: D1 (fuente nueva, ventanas viejas) debe llamar a `detect_sweep_and_key_level` exactamente como hoy (`window_close_ts = window_open_ts + H4_DURATION`) y mantener el cierre de Modelo #1 en 10:30 — ningún cambio de ventana. D2/D3 (ventanas nuevas) deben pasar `window_close_ts = window_open_ts + timedelta(hours=2)` a `detect_sweep_and_key_level` (el nuevo tope explícito de activación) Y extender el cierre de la ventana de Modelo #1 a `window_open_ts + timedelta(hours=4)` (13:00) — dos cambios de parámetro distintos, no uno.

## 1. Reglas operativas exactas — Modelo 9AM (confirmadas por el usuario)

- La vela feeder de las **5AM** (`[05:00, 09:00)` NY) establece el rango H4 de referencia — su propio Alto/Bajo, disponible en `available_at(5AM) = 09:00` NY (su propio cierre).
- La vela feeder de las **9AM** (`[09:00, 13:00)` NY) puede barrer el máximo o mínimo de la vela anterior (5AM, `i-1` — no se reabre aquí la pregunta de si 9AM también puede soup 1AM/`i-2`; eso ya estaba fuera de alcance de C1/C2 por decisión previa, §0 del diseño original).
- El barrido debe estar acompañado por un toque a un Key Level válido y causalmente disponible (mecanismo existente de `detect_sweep_and_key_level`/`key_level_credited`, sin cambios).
- **Ventana de activación**: ambas condiciones (barrido + Key Level) deben tener `available_at <= 11:00` NY. Observado con `available_at > 11:00` → fuera de ventana, el ciclo del modelo 9AM no activa (Ejemplo C).
- No se exige esperar el cierre definitivo de la vela H4 de las 9AM para activar la búsqueda de Modelo #1 (la búsqueda arranca en `activation_instant_ts`, no en `13:00`).
- No se exige que la vela de 9AM cierre nuevamente dentro del rango anterior (sin requisito de "false break" HTF — ya era así en C1/C2, se reconfirma sin cambios).
- **Ventana de confirmación de Modelo #1**: la búsqueda comienza en `max(09:00, activation_instant_ts)`. El Modelo #1 puede empezar a formarse antes de las 11:00 (si la activación ocurrió antes) y terminar de confirmarse después — el único límite real es que `available_at(confirmación) <= 13:00` NY (el cierre de la propia vela feeder de 9AM). Confirmación con `available_at == 13:00` exacto es válida (Ejemplo D, caso límite incluido); `available_at > 13:00` es inválida (Ejemplo D, caso excluido).
- Una orden solo puede colocarse después de `model1_available_ts` (= `available_at` de la vela de confirmación). La elegibilidad de fill arranca en la primera M15 posterior, vía `first_fillable_index = bisect.bisect_left(m15_timestamps, order_placed_ts)` — el contrato causal existente de `causal_intrabar.py::fill_pass_c`, sin cambios.
- La orden conserva sus reglas independientes de vencimiento/ejecución (`fill_pass_c`, `_fill_sides`, `two_heap_sweep`, `_resolve_exits` — todo sin tocar).

**Verificación de los 4 ejemplos contra esta formalización**:
- A: barrido+KL `available_at=10:45` (≤11:00, OK) → Modelo #1 confirmado `available_at=11:00` (≤13:00, OK) → **válido**.
- B: barrido intrabar a las 10:55, pero `available_at` real = cierre de la vela M15 que lo contiene = `11:00` (≤11:00, límite inclusive, OK) → Modelo #1 confirmado `available_at=11:30` (≤13:00, OK) → **válido**. Esto fija el criterio general: siempre se usa el cierre de la vela M15 que revela el dato, nunca el instante intrabar supuesto ni el open.
- C: barrido+KL con `available_at > 11:00` → **fuera de la ventana de activación**, el ciclo nunca llega a `HTF_CONDITIONS_OBSERVED`.
- D: Modelo #1 con `available_at > 13:00` → **fuera de la ventana de confirmación**, el signal nunca llega a `MODEL1_CONFIRMED_AND_AVAILABLE`.

## 2. Fuente causal del anchor M15 — antigüedad formalizada (gap-safe)

Reconfirma la Alternativa 1 (§Fase 3) con la antigüedad corregida a 16 velas M15 (4h) y, ahora, **formalizada por timestamp, no por conteo de barras** — directamente en respuesta a tu advertencia de que 16 barras separadas por huecos podrían representar más de 4 horas reales.

- **Candidatos elegibles**: cada vela M15 `i`, en el instante `origin_at = available_at(candles[i]) = candles[i].timestamp + 15min`, se vuelve candidata de "Alto/Bajo previo" con `level.high = candles[i].high`, `level.low = candles[i].low`. Sin exigir clasificación true/false-break.
- **Desde qué timestamp comienza la antigüedad**: desde `origin_at` (el cierre de la vela que origina el nivel) — nunca desde `candles[i].timestamp` (el open), consistente con el contrato `available_at` ya usado en todo este diseño.
- **Cuándo vence el nivel**: en el primer instante `T` tal que `T - origin_at > timedelta(hours=4)`. Formalmente, al evaluar en la vela `j` (con `T = available_at(candles[j])`), el nivel de la vela `i` está vencido si `available_at(candles[j]) - available_at(candles[i]) > 4h` — **comparación de timestamps reales, nunca de índices o conteo de velas**.
- **Corrección (revisión del usuario): la condición de "sigue sin ser barrido" tenía un error de límite.** La versión anterior incluía la propia vela `j` entre las velas que "no deben haber barrido" — eso es contradictorio: si `j` es precisamente la vela candidata a ser el anchor (la que produce el barrido), `j` no puede estar sujeta a la misma condición de "no rompió". Quedan DOS condiciones separadas, una para las velas estrictamente anteriores a `j` y otra para `j` misma:
  - **Máximo anterior** (dirección bajista, barrido de un Alto): ninguna vela `k` con `i < k < j` debe haber superado `level.high` (`candles[k].high <= level.high` para toda `k` en ese rango EXCLUYENDO `j`) — eso define que el nivel seguía "abierto" justo antes de `j`. Y, por separado, `candles[j].high > level.high` — eso es lo que hace que `j` sea el anchor.
  - **Mínimo anterior** (dirección alcista, barrido de un Bajo): análogo — ninguna vela `k` con `i < k < j` debe haber perforado `level.low` (`candles[k].low >= level.low` excluyendo `j`), y `candles[j].low < level.low` es lo que hace que `j` sea el anchor.
  - **Los lados High y Low son independientes**: el lado High de la vela `i` puede estar roto mientras su lado Low sigue abierto (o viceversa) — son dos candidatos separados con estado propio, nunca un único booleano "nivel roto". Esto ya era implícito en cómo `first_breach_index` se invoca hoy (siempre con `high=` XOR `low=`, nunca ambos a la vez), pero quedaba mal expresado en la prosa anterior.

  Pseudocódigo corregido (diseño únicamente, no es el código final):
  ```python
  def is_broken_by(candle, level_price, direction):
      return candle.high > level_price if direction == "bearish" else candle.low < level_price

  def side_value(candles, i, direction):
      return candles[i].high if direction == "bearish" else candles[i].low

  def find_first_valid_anchor(candles, search_start_idx, search_end_idx, direction, age=timedelta(hours=4)):
      for j in range(search_start_idx, search_end_idx + 1):
          winners = []
          for i in range(0, j):                                   # candidato: toda vela ANTERIOR a j
              if available_at(candles[j]) - available_at(candles[i]) > age:
                  continue                                        # vencido por antigüedad (timestamp, no índice)
              level_price = side_value(candles, i, direction)
              if any(is_broken_by(candles[k], level_price, direction) for k in range(i + 1, j)):
                  continue                                        # alguien ANTES de j ya lo rompió -- ya no está "abierto"
              if is_broken_by(candles[j], level_price, direction):
                  winners.append(i)                                # j mismo lo rompe -- candidato válido
          if winners:
              return (min(winners), j)                             # tie-break existente: start_index más bajo
      return None
  ```
  Nota de implementación (no bloquea el diseño): el barrido `for k in range(i+1, j)` en cada paso es solo para claridad del pseudocódigo; una implementación real mantendría un conjunto incremental de "candidatos todavía abiertos" actualizado vela a vela, en vez de recalcularlo desde cero en cada `j`.
- **Huecos de datos**: por construcción, la expiración por timestamp es inmune a huecos — si faltan velas entre `i` y `j` (fin de semana, feriado, hueco del broker), `j` sigue siendo "la siguiente vela disponible", y la comparación `available_at(j) - available_at(i) > 4h` sigue siendo la correcta en tiempo real, sin importar cuántas velas (cero, una, o muchas) haya en el medio. **Si en cambio se contaran 16 barras del ARRAY sin mirar el reloj, un hueco de varias horas haría que esas 16 barras representen mucho más de 4 horas reales — exactamente el error que señalaste.** Por eso la regla se define en timestamps, nunca en índices.
- **Caso de gap que salta por encima/debajo de un nivel**: si un hueco de datos hace que el precio "salte" de un lado al otro de `level.high/low` sin que ninguna vela registre el wick tocándolo explícitamente, la primera vela disponible tras el hueco ya tiene su propio high/low conocido — si esa vela YA está más allá del nivel, se registra como breach en esa misma vela (sin necesidad de una regla nueva: es el mismo criterio de wick, aplicado a la primera vela causalmente disponible). Incluido como caso de test explícito (§7, huecos de datos).

## 3. Máquina de estados con timestamps (Modelo 9AM; 1AM sin cambios, ver §5)

**Corrección (revisión del usuario)**: la versión anterior dibujaba `WAITING_FOR_FEEDER` como "hasta 05:00 NY" seguido directo de `FEEDER_RANGE_ESTABLISHED`, lo que se leía como si la transición ocurriera EN 05:00 (la apertura de la vela de 5AM), no en 09:00 (su cierre) — aunque el timestamp escrito al lado ya decía 09:00, el diagrama mismo era ambiguo. Se agrega el estado intermedio faltante para que ningún paso se pueda leer como gateado por `candle.timestamp` (apertura) en lugar de `available_at` (cierre):

```
WAITING_FOR_FEEDER                          hasta 05:00 NY (la vela de 5AM todavía no abrió)
  -> FEEDER_FORMING                         desde 05:00 NY -- la vela de 5AM está abierta y en formación;
                                             su propio high/low TODAVÍA NO está disponible en este tramo
  -> FEEDER_RANGE_ESTABLISHED               EXACTAMENTE en available_at(5AM) = 09:00 NY -- el cierre de
                                             la vela de 5AM, nunca su open (05:00) ni ningún instante
                                             intermedio -- el rango H4 de referencia queda disponible aquí
  -> WAITING_FOR_SWEEP_AND_KEY_LEVEL         desde 09:00 NY, walking M15 dentro de la vela 9AM en formación;
                                             cada paso usa available_at(vela M15), nunca su open
       -> HTF_CONDITIONS_OBSERVED           en activation_instant_ts = available_at(vela M15 que revela
                                             el barrido+KL), SOLO SI activation_instant_ts <= 11:00 NY
       -> [abortado, modelo 9AM no activa]  SI pasan las 11:00 NY (por available_at, no por open) sin
                                             barrido+KL observado (Ejemplo C)
  -> WAITING_FOR_MODEL1                     desde max(09:00, activation_instant_ts) hasta 13:00 NY
       (anchor M15 vía §2, candidato no vencido/no roto; luego engulf/retest/confirmación de
        _track_anchor, retry-on-invalidation incluido, SIN CAMBIOS)
       -> MODEL1_CONFIRMED_AND_AVAILABLE    en model1_available_ts = available_at(vela de confirmación),
                                             SOLO SI model1_available_ts <= 13:00 NY (Ejemplo D, límite
                                             inclusive)
       -> [abortado, sin señal]             SI pasan las 13:00 NY sin confirmación (Ejemplo D)
  -> ORDER_CONSTRUCTED_AND_PLACED           en order_placed_ts = model1_available_ts
  -> ORDER_ACTIVE                           elegibilidad de fill desde first_fillable_index (bisect),
                                             SIN CAMBIOS (fill_pass_c existente)
  -> FILLED / EXPIRED / INVALIDATED         SIN CAMBIOS (_fill_sides/two_heap_sweep/_resolve_exits)
```

**Contrato temporal, verificado explícitamente en cada transición de arriba**: la condición de avance es siempre `available_at(candle) <= decision_timestamp` (o `>` para un abort), **nunca** `candle.timestamp <= decision_timestamp`. `candle.timestamp` es la apertura; usarla directamente permitiría avanzar de estado un intervalo completo (15min en M15, 4h en el feeder) antes de que el dato realmente exista. Las dos transiciones donde esto importa más (`FEEDER_RANGE_ESTABLISHED` y `HTF_CONDITIONS_OBSERVED`) quedan anotadas arriba explícitamente con `available_at`, no con el open.

## 4. Aislamiento de las dos modificaciones + experimentos propuestos

Las dos modificaciones son independientes y no deben mezclarse silenciosamente:

- **Modificación 1 — fuente causal del anchor M15** (§2): afecta CUALQUIER modelo que use `confirm_in_ltf_window` (1AM y 9AM por igual), sin tocar ninguna ventana temporal.
- **Modificación 2 — ventanas del modelo 9AM** (§1, corregido en §0): `detect_sweep_and_key_level`'s `window_close_ts`: `window_open_ts + H4_DURATION` (4h, hoy, sin tope de activación propio) `→ window_open_ts + 2h` (tope explícito de activación a las 11:00). Ventana de Modelo #1: cierre `10:30 → 13:00` (cierre de la propia vela feeder). Dos parámetros distintos, los dos exclusivos del modelo 9AM — 1AM no se toca (§5).

Propongo 3 configuraciones experimentales nuevas, cada una ejecutada sobre ambas rejillas de velas (broker H4 / NY-feeder, como ya hacen C1/C2), manteniendo C1/C2 originales intactos como referencia:

| Config. propuesta | Fuente del anchor M15 | Ventanas 9AM | Aísla el efecto de | Estatus |
|---|---|---|---|---|
| **D1** | Nueva (§2, antigüedad 4h por timestamp) | Sin cambios (9:00-10:30, como hoy) | Solo Modificación 1 | Diagnóstico causal — mide el efecto de la fuente del anchor sola |
| **D2** | Vieja (actual, `detect_crt_ranges` + resolución) | Nuevas (9:00-11:00 / hasta 13:00) | Solo Modificación 2 | **DIAGNÓSTICO NO CAUSAL** |
| **D3** | Nueva (§2) | Nuevas (9:00-11:00 / hasta 13:00) | Ambas combinadas | **Reglas operativas acordadas para el modelo 9AM** |

- **D2 queda etiquetado explícitamente como DIAGNÓSTICO NO CAUSAL**: conserva el mecanismo de anchor viejo (`detect_crt_ranges`/resolución retrospectiva, el look-ahead que esta auditoría entera viene corrigiendo), así que su R **no se usa como evidencia de rentabilidad** bajo ninguna circunstancia — sirve únicamente para medir, por diferencia contra C1/C2, cuánto cambia el resultado por ensanchar las ventanas 9AM, aislado del efecto de la fuente del anchor. Cualquier reporte que incluya D2 debe repetir esta etiqueta junto al número, no solo en el diseño.
- **D3 representa las reglas operativas acordadas para el modelo 9AM** (§1) — no es "una tercera variante entre varias igualmente válidas": es el diseño objetivo. D1 y D2 son herramientas de diagnóstico para aislar de dónde viene cada efecto, no alternativas candidatas a adoptarse por sí solas.
- 1AM permanece sin cambios de horario en las 3 configuraciones. Usa la fuente de anchor NUEVA en D1 y D3 (model-agnóstica, igual que para 9AM); usa la fuente VIEJA en D2 (ya que D2 existe específicamente para aislar el efecto de las ventanas, no el de la fuente — para 1AM esto significa D2 es idéntico a C1/C2, porque 1AM no recibe ventanas nuevas).
- Ningún resultado de D1/D2/D3 decide por sí solo cuál variante adoptar — se reportan los 3 por separado, nunca colapsados, y la elección no se basa en el R obtenido (instrucción explícita, reforzada).

## 5. Modelo 1AM — sin cambios, incompatibilidad detectada

Las ventanas de 1AM (`MODEL_1AM.window_duration=2h`, activación y confirmación conflacionadas en el mismo span `02:00-04:00` NY) permanecen intactas, tal como se pidió. La nueva fuente de anchor M15 (§2) puede reutilizarse para 1AM sin tocar sus horarios.

**Incompatibilidad a reportar, no resuelta por mí**: bajo el principio nuevo del modelo 9AM ("la confirmación puede extenderse hasta el cierre de la propia vela feeder"), el equivalente para 1AM sería permitir confirmación hasta `05:00` NY (cierre de la vela feeder de 1AM). Pero la regla vigente de 1AM corta en `04:00` NY — una hora ANTES de su propio cierre de vela feeder, y además sin separar activación de confirmación (mismo span único de 2h para ambas, a diferencia del 9AM nuevo que las separa en 2h de activación + hasta 4h de confirmación). Esto significa que, con las reglas actuales, 1AM tiene proporcionalmente MENOS presupuesto de tiempo para confirmar que el 9AM nuevo. No sé si esto es deliberado (el comentario existente en el código ya marca la ventana de 1AM como "charter-8's own beginner-safe window", sugiriendo que podría ser intencionalmente más conservadora) o un desajuste pendiente de revisar más adelante. Lo reporto sin tocarlo.

## 6. Contratos de disponibilidad de datos

- `available_at(candle) = candle.timestamp + 15min` — único contrato de disponibilidad en todo el diseño, sin excepciones, igual que en el resto de esta auditoría (`causal_intrabar.py::available_at`).
- Toda comparación contra un límite horario (11:00, 13:00, vencimiento de nivel) se hace contra `available_at`, nunca contra el timestamp de apertura ni contra un instante intrabar supuesto — formalizado explícitamente en §1 a partir del Ejemplo B.
- El vencimiento de un nivel M15 (§2) se calcula por diferencia de timestamps reales, nunca por conteo de índices — inmune a huecos de datos por construcción.
- Ningún paso de este diseño consulta una vela con `timestamp` posterior al instante de evaluación actual — mismo principio causal de toda la auditoría, reconfirmado aquí para los dos mecanismos nuevos (antigüedad del anchor, ventanas 9AM).

## 7. Tests propuestos (diseño, no implementados — reemplaza/extiende la lista de la Fase 4)

1. Barrido+KL dentro de la ventana válida (Ejemplos A y B) — confirmación causal correcta, usando `available_at` del cierre de vela, no el intrabar.
2. Barrido+KL observado después de las 11:00 NY — rechazado (Ejemplo C).
3. Modelo #1 confirmado exactamente a las 13:00 NY — aceptado (límite inclusive, Ejemplo D positivo).
4. Modelo #1 confirmado después de las 13:00 NY — rechazado (Ejemplo D negativo).
5. CRT M15 que nunca se resuelve formalmente — igual elegible como anchor (Alternativa 1 base).
6. CRT que se resuelve varias velas después del anchor (caso real `gap_bars=8` de la auditoría anterior) — el anchor se habilita en su propio instante, sin importar la resolución posterior.
7. Retry-on-invalidation — decisiones previas a la invalidación idénticas sin importar el futuro.
8. Niveles M15 vencidos (>4h sin ser barridos) — deben dejar de ser candidatos, verificado por timestamp.
9. Huecos de datos M15 — un hueco no debe hacer que 16 barras representen más de 4h reales (§2); y un gap que salta sobre un nivel se resuelve en la primera vela disponible tras el hueco.
10. Invariancia causal general — dos historias con el mismo pasado y futuros distintos producen las mismas decisiones hasta el punto de divergencia, aplicado tanto a la fuente del anchor (ya cubierto en la Fase 4) como a las nuevas ventanas 9AM (ej.: dos historias idénticas hasta las 10:59 que divergen después deben decidir igual si el barrido+KL activó o no antes de ese instante).
11. Imposibilidad de acreditar fills antes de la colocación de la orden — reconfirmación del invariante existente (`assert idx > confirmation_index`, `fill_pass_c`) bajo el mecanismo de anchor y las ventanas nuevas, no solo bajo el mecanismo viejo.
12. **(nuevo, corrección del bug de §2)** Barrido de un Alto: una vela `j` que supera `level.high` debe producir anchor en `j`, con ninguna vela `k` (`i<k<j`) habiendo superado `level.high` antes — y simétricamente, una vela que SOLO toca/iguala `level.high` sin superarlo (`candle.high == level.high`, no `>`) NO debe producir anchor.
13. **(nuevo)** Barrido de un Bajo — análogo a 12 pero para `level.low`/perforación hacia abajo.
14. **(nuevo)** Lados independientes: una vela `i` cuyo lado High ya fue roto por una vela anterior a `j`, pero cuyo lado Low sigue abierto, debe seguir siendo candidata válida para una búsqueda en dirección alcista (barrido del Low) en `j`, aun cuando ya no sea candidata para una búsqueda en dirección bajista (barrido del High). Y viceversa. Verificar que romper un lado nunca inhabilita el otro.

## 8. Diferencias respecto a C1/C2 originales

C1/C2 (commit `a985158`, resultados en `results-c1-c2.md`) quedan **inmutables como referencia histórica** — no se tocan sus CSV ni su código. Las diferencias de D1/D2/D3 respecto a C1/C2:

- **D1 vs. C1/C2**: mismo horario 9AM/1AM; cambia únicamente qué nivel M15 puede ser el anchor (antigüedad por timestamp en vez de resolución clasificada). Esperable: más candidatos elegibles (ningún nivel se descarta por no resolver dentro de una ventana retrospectiva), posiblemente un `anchor_index` distinto en los mismos trades, o trades nuevos que antes no existían por `NO_EVALUABLE`/ausencia de rango.
- **D2 vs. C1/C2**: mismo mecanismo de anchor; cambia únicamente el horario del modelo 9AM (ventana de activación y de confirmación ampliadas). Esperable: señales 9AM que antes se perdían por activación/confirmación tardía (después de 10:30) ahora se evalúan.
- **D3 vs. C1/C2**: combina ambos — no se puede atribuir el cambio neto a una sola causa sin comparar contra D1 y D2 por separado, que es justamente el propósito de separarlos.
- Ninguna comparación usa el R resultante para decidir cuál adoptar (instrucción explícita, reconfirmada).

## 9. Ambigüedades restantes que podrían impedir una implementación fiel

1. **Asimetría 1AM/9AM** (§5): no resuelta, reportada para tu decisión antes de implementar.
2. **Segunda fuente de sweep para 9AM** (`i-2`, barrer 1AM además de 5AM): explícitamente fuera de alcance en este mensaje (el usuario solo mencionó "la vela anterior", singular) y ya estaba fuera de alcance de C1/C2 por decisión previa — lo menciono solo para que conste que sigue sin reabrirse, no para reabrirlo yo.
3. **Uso futuro de la clasificación true/false-break**: sigue sin decidirse si se conserva como metadato descriptivo en algún reporte, o se elimina por completo de la ruta de Modelo #1 — no bloquea este diseño, pero queda pendiente antes de tocar código.

## 10. Alcance y restricciones (reconfirmadas)

2015-01-01 en adelante cuando se autorice ejecución (historial previo conservado solo para warmup). Sin cambios a `detector/`, `scanner/`, `docs/`. Sin recalibración. Sin optimización. Sin backtest nuevo todavía. Sin modificar los CSV de A/B1/B2/C1/C2. SL/TP y resolución de órdenes sin cambios.

## 11. No implementado — detenido según instrucción

Nada de este diseño fue implementado ni ejecutado. `design-causal-anchor-source.md` y el seguimiento del ODD quedan actualizados. Esperando revisión y autorización explícita antes de escribir código o correr cualquier backtest.

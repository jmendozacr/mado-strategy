# Resultados D3/C2 — validación histórica 2015-01-01 a la fecha más reciente disponible

Corrida autorizada (2026-11-19) sobre el diseño causal corregido (commit `d7e37ad`). Config **D3/C2**: fuente de anchor M15 nueva (antigüedad 4h por timestamp, gap-safe) + ventanas 9AM nuevas (activación hasta 11:00 NY, confirmación hasta 13:00 NY) + grilla NY-anchored (C2). Solo D3/C2 — **D1 y D2 NO se ejecutaron** en esta ronda, según instrucción explícita.

Archivos: `trades_d3_c2_2015plus_run2.csv` (2047 filas), `funnel_2015plus_run2.csv`, `year_breakdown_2015plus_run2.csv`, `run_d3c2_all.txt` (log de la corrida), `analyze_d3_c2_2015plus.py` (script de análisis, reproducible), `analysis_d3_c2_2015plus_output.txt` (output completo), `comparison_c2_original_vs_d3_2015plus.txt`.

## 0. Optimización previa (sin alterar lógica)

`run_d1_d2_d3.py`: `detect_crt_ranges` se saltea cuando ningún config solicitado usa el anchor viejo (solo D2 lo consume, vía `old_confirm_fn(ltf_ranges)` — confirmado por grep, ninguna otra referencia existe). Demostrado sin cambio de comportamiento: reejecuté el mismo slice del smoke test anterior (D3, EST, 6 semanas) con la optimización activa y comparé contra los CSV ya commiteados — **idénticos byte a byte**, ambos brazos (C1 y C2).

## 1. Bug encontrado y corregido durante esta ronda (antes del reporte)

`main()` escribía el CSV de salida **dentro** del loop por símbolo, con un nombre que no distinguía el símbolo (`trades_{arm_name}_{output_label}.csv`) — cada símbolo pisaba al anterior para el mismo arm+label. Descubierto así: EURUSD corrió primero (sola) y se verificó bien, pero al correr USDCAD+AUDUSD juntos en una segunda invocación, AUDUSD pisó a USDCAD en disco (los números impresos en stdout de cada corrida eran correctos — ya calculados antes del `write_csv` — solo el archivo quedó mal). Corregido siguiendo el patrón ya establecido en `run_c1_c2.py`: acumular filas por arm a través de todos los símbolos, escribir una sola vez al final. Reejecutado limpio con los 3 pares juntos (`2015plus_run2`) — verificado: 2047 filas = 636 (EURUSD) + 696 (USDCAD) + 715 (AUDUSD), exactamente los mismos conteos que las corridas individuales ya habían impreso.

## 2-3. Corridas ejecutadas

EURUSD primero (2015-01-01 → última fecha disponible), verificación de cronología (0 violaciones), luego USDCAD y AUDUSD. Historial completo anterior a 2015 conservado como warmup causal (detección compartida — swings, key levels — sobre el historial completo; solo las ventanas de activación 2015+ se caminan).

## 4. Resultados por par

### EURUSD

| Métrica | Valor |
|---|---|
| Trades generados (HTF trigger+KeyLevel) | 6915 |
| Modelo #1 CONFIRMED | 1719 |
| Candidatos de población (tras R:R/SL/TP) | 1566 |
| Trades (con fill) | 636 |
| Nunca llenados (pendiente, sin fill) | 294 |
| Abiertos (pendiente, sin cerrar al final de datos) | 1 |
| Cerrados | 635 |
| Win rate | 37.17% (236/635) |
| Total R (cerrados) | **-0.2525** |
| Expectancy por trade cerrado | -0.0004 R |
| Profit factor | 0.9994 |
| Max drawdown (R, cronológico por cierre) | 48.16 |
| Costo de ejecución ya aplicado (`trading_cost_price=0.00013`, horneado en cada `r_multiple` vía `_resolve_exits`) | ~74.95 R agregados (0.1179 R/trade promedio) |

**Por modelo**: 1AM: 143 trades, wr=41.96%, total_r=+0.47, expectancy=+0.0033, pf=1.0049. 9AM: 493 trades, wr=35.77%, total_r=-0.72, expectancy=-0.0015, pf=0.9979.

**Por año** (trades cerrados, % del total de cerrados, total_r): 2015: 52 (8.2%) -8.57 · 2016: 64 (10.1%) -0.40 · 2017: 47 (7.4%) -3.12 · 2018: 62 (9.8%) **-23.21** · 2019: 50 (7.9%) -5.90 · 2020: 59 (9.3%) **+26.82** · 2021: 49 (7.7%) -2.29 · 2022: 47 (7.4%) +11.30 · 2023: 49 (7.7%) +3.00 · 2024: 47 (7.4%) -2.14 · 2025: 59 (9.3%) +15.81 · 2026: 50 (7.9%) -11.55.

**Concentración de ganancias**: con un total casi nulo (-0.25R), la "concentración porcentual" por año es matemáticamente inestable (denominador cercano a cero, porcentajes de miles de %) — no es una medida útil aquí. Lectura directa: 2020 y 2025 son los años ganadores grandes (+26.8R, +15.8R); 2018 y 2026 son los perdedores grandes (-23.2R, -11.6R); se cancelan casi exactamente.

**Distribución ganancias/pérdidas**: Wins (n=236): media +1.889R, mediana +1.787R, rango [+0.355, +5.667]. Losses (n=399): media -1.118R, mediana -1.105R, rango [-1.217, -1.025] — las pérdidas son muy uniformes (SL ajustado), las ganancias tienen cola larga hacia arriba (TP/parciales variables).

### USDCAD

| Métrica | Valor |
|---|---|
| Trades generados | 6866 |
| Modelo #1 CONFIRMED | 1803 |
| Candidatos de población | 1708 |
| Trades (con fill) | 696 |
| Nunca llenados | 316 |
| Abiertos | 1 |
| Cerrados | 695 |
| Win rate | 39.14% (272/695) |
| Total R (cerrados) | **+51.1780** |
| Expectancy por trade cerrado | +0.0736 R |
| Profit factor | 1.1055 |
| Max drawdown (R, cronológico) | 45.44 |
| Costo de ejecución ya aplicado (`trading_cost_price=0.000167`) | ~100.66 R agregados (0.1446 R/trade) |

**Por modelo**: 1AM: 207 trades, wr=39.61%, total_r=+5.96, expectancy=+0.0288, pf=1.0392. 9AM: 489 trades, wr=38.93%, total_r=+45.22, expectancy=+0.0927, pf=1.1356 — **todo el edge de USDCAD viene del modelo 9AM**.

**Por año**: 2015: 49 (7.1%) -3.00 · 2016: 57 (8.2%) **+36.88** · 2017: 48 (6.9%) -0.74 · 2018: 66 (9.5%) -12.50 · 2019: 61 (8.8%) -19.07 · 2020: 56 (8.1%) +2.56 · 2021: 76 (10.9%) +17.85 · 2022: 60 (8.6%) +17.95 · 2023: 67 (9.6%) -3.00 · 2024: 52 (7.5%) +15.05 · 2025: 51 (7.3%) +10.28 · 2026: 52 (7.5%) -11.08.

**Concentración de ganancias** (años ordenados por |contribución|, % del total_r=+51.18): 2016 +36.88 (72.1%) · 2019 -19.07 (-37.3%) · 2022 +17.95 (35.1%) · 2021 +17.85 (34.9%) · 2024 +15.05 (29.4%) · 2018 -12.50 (-24.4%) · 2026 -11.08 (-21.7%) · 2025 +10.28 (20.1%) · resto <6% cada uno. **Un solo año (2016) aporta más del 70% del resultado total — concentración alta, no un edge distribuido uniformemente.**

**Distribución**: Wins (n=272): media +1.972R, mediana +1.762R, rango [+0.259, +6.834]. Losses (n=423): media -1.147R, mediana -1.130R, rango [-1.584, -1.036].

### AUDUSD

| Métrica | Valor |
|---|---|
| Trades generados | 6137 |
| Modelo #1 CONFIRMED | 1594 |
| Candidatos de población | 1774 |
| Trades (con fill) | 715 |
| Nunca llenados | 344 |
| Abiertos | 2 |
| Cerrados | 713 |
| Win rate | 37.87% (270/713) |
| Total R (cerrados) | **+27.6775** |
| Expectancy por trade cerrado | +0.0388 R |
| Profit factor | 1.0546 |
| Max drawdown (R, cronológico) | 36.82 |
| Costo de ejecución ya aplicado (`trading_cost_price=0.00013`) | ~102.76 R agregados (0.1437 R/trade) |

**Por modelo**: 1AM: 270 trades, wr=37.55%, total_r=+2.66, expectancy=+0.0099, pf=1.0138. 9AM: 445 trades, wr=38.06%, total_r=+25.01, expectancy=+0.0563, pf=1.0800 — mismo patrón que USDCAD, **el edge se concentra en 9AM**.

**Por año**: 2015: 52 (7.3%) -11.37 · 2016: 55 (7.7%) +4.04 · 2017: 59 (8.3%) +17.71 · 2018: 73 (10.2%) **-22.16** · 2019: 52 (7.3%) +1.92 · 2020: 52 (7.3%) +3.41 · 2021: 72 (10.1%) +10.57 · 2022: 63 (8.8%) +7.35 · 2023: 62 (8.7%) -15.69 · 2024: 62 (8.7%) +17.47 · 2025: 65 (9.1%) +1.08 · 2026: 46 (6.5%) +13.36.

**Concentración**: 2018 -22.16 (-80.0%) · 2017 +17.71 (64.0%) · 2024 +17.47 (63.1%) · 2023 -15.69 (-56.7%) · 2026 +13.36 (48.3%) · 2015 -11.37 (-41.1%) · resto más chico. También alta concentración, con un año negativo grande (2018) casi compensado por dos años positivos (2017, 2024).

**Distribución**: Wins (n=270): media +1.978R, mediana +1.846R, rango [+0.371, +6.249]. Losses (n=443): media -1.143R, mediana -1.137R, rango [-1.385, -1.049].

## 5. Verificación de causalidad (sobre las 2047 filas reales, no solo tests sintéticos)

| Invariante | Violaciones |
|---|---|
| `activation_instant_ts <= model1_available_ts` (ningún barrido/Key Level usado antes de disponible) | 0 |
| `model1_available_ts == order_placed_ts` (Modelo #1 CONFIRMED antes de colocar la orden) | 0 |
| `entry_timestamp_broker >= order_placed_ts` (ningún fill antes de que la orden pueda existir) | 0 |
| 9AM: `activation_instant_ts` en hora NY `<= 11:00` | 0 |
| 9AM: `model1_available_ts` en hora NY `<= 13:00` | 0 |

Cero violaciones en las 2047 filas. El anchor M15 no depende de información futura por construcción (`find_first_valid_anchor`, verificado con 27 tests unitarios + esta corrida real).

**Asimetría 1AM pendiente**: sigue documentada y sin resolver (`design-causal-anchor-source.md` §5) — la ventana de 1AM (02:00-04:00 NY, span único sin separar activación de confirmación) no se tocó en esta ronda, tal como se pidió.

## 6. Comparación contra C2 original, misma ventana temporal y criterio de selección

Ambos filtrados a `window_open_ts >= 2015-01-01` (mismo campo de `stable_id`, mismo criterio usado en toda esta auditoría) — **nunca comparado contra el total histórico 2003-2026**.

| Par | Arm | Trades | Cerrados | WR | Total R | Expectancy |
|---|---|---|---|---|---|---|
| EURUSD | C2 original (escopeado 2015+) | 222 | 222 | 40.09% | +4.897 | +0.0221 |
| EURUSD | D3/C2 (diseño acordado) | 636 | 635 | 37.17% | **-0.253** | -0.0004 |
| USDCAD | C2 original (escopeado 2015+) | 290 | 290 | 38.97% | +2.048 | +0.0071 |
| USDCAD | D3/C2 (diseño acordado) | 696 | 695 | 39.14% | **+51.178** | +0.0736 |
| AUDUSD | C2 original (escopeado 2015+) | 345 | 344 | 38.66% | +6.559 | +0.0191 |
| AUDUSD | D3/C2 (diseño acordado) | 715 | 713 | 37.87% | **+27.677** | +0.0388 |
| **Combinado** | C2 original (escopeado 2015+) | 857 | 856 | — | +13.504 | — |
| **Combinado** | D3/C2 (diseño acordado) | 2047 | 2043 | — | +78.603 | — |

**Lectura honesta, no espinada hacia "mejoró"**: D3/C2 genera ~2.4× más trades que C2 original en la misma ventana — la fuente de anchor nueva (sin el gate de resolución retrospectiva) y las ventanas 9AM ampliadas encuentran señales que el mecanismo viejo descartaba. El R combinado es mayor, pero **no es una comparación limpia de "mismo universo, mejor ejecución"** — es una población de señales distinta y más grande. Por par: USDCAD y AUDUSD mejoran notablemente; **EURUSD empeora, pasando de +4.9R a prácticamente neutro (-0.25R)** — el par sobre el que están construidas todas las charters NO muestra edge bajo el diseño causalmente corregido y fiel a las reglas NY. Esto es exactamente el tipo de resultado que esta auditoría buscaba descubrir, no evitar.

## 7. Restricciones respetadas

Sin recalibración ni optimización de parámetros. D2 no se ejecutó ni se usó como evidencia de rentabilidad en ningún punto de esta ronda. `detector/`, `scanner/`, `docs/` sin tocar. CSV y resultados anteriores (`trades_c1.csv`, `trades_c2.csv`, `trades_arm_a.csv`, `trades_b1_*.csv`, `trades_b2.csv`, los CSV de D1/D2/D3 del smoke test EST/EDT) intactos — verificado explícitamente, ninguno fue sobrescrito por esta corrida (identificadores de corrida únicos: `2015plus_run2`).

## 8. Reconciliación

`sum(r_multiple)` recalculado directamente desde el CSV, comparado contra el total impreso por el runner en stdout durante la corrida:

| Par | CSV | Runner (stdout) | Diferencia |
|---|---|---|---|
| EURUSD | -0.2525 | -0.2525 | 0.000038 |
| USDCAD | 51.1780 | 51.1780 | 0.000012 |
| AUDUSD | 27.6775 | 27.6775 | 0.000002 |

Diferencias en el orden de redondeo de punto flotante — reconciliación exacta, sin discrepancias materiales.

## No hecho en esta ronda (por instrucción explícita)

D1 y D2 no se ejecutaron. No se recalibró nada. No se corrió sobre otras ventanas temporales. Me detengo acá, entregando solo D3/C2, para tu revisión antes de continuar con cualquier otro experimento.

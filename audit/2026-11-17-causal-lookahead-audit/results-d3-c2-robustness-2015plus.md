# Auditoría de robustez — D3/C2, 2015–2026

Auditoría read-only sobre `trades_d3_c2_2015plus_run2.csv` (2047 trades, commit `d596e65`). No se reejecutó ningún backtest, no se tocó `detector/`, `scanner/`, `docs/`, no se modificó ningún CSV/script histórico, no se recalibró ni optimizó nada. Script reproducible: `analyze_d3_c2_robustness.py`. Semilla fija: `20261119`.

**Baseline verificado intacto** (confirmado por `git status`/`git diff` antes y después de esta auditoría — cero diffs en `trades_c1.csv`, `trades_c2.csv`, `trades_arm_a.csv`, `trades_b1_*.csv`, `trades_b2.csv`, `trades_d3_c2_2015plus_run2.csv`, `funnel_2015plus_run2.csv`, `year_breakdown_2015plus_run2.csv`, `run_d1_d2_d3.py`, `analyze_d3_c2_2015plus.py`, `results-d3-c2-2015plus.md`):

| Par | Trades cerrados | Total R |
|---|---:|---:|
| EURUSD | 635 | −0.2525R |
| USDCAD | 695 | +51.1780R |
| AUDUSD | 713 | +27.6775R |
| Combinado | 2043 | +78.6030R |

Reconciliado exacto contra `sum(r_multiple)` en esta corrida (ver Fase 1).

## Fase 1 — Embudo corregido

Confirmado exactamente tu hallazgo: `candidates_built`, `never_filled`, `filled`, `skipped_no_placement` en `funnel_2015plus_run2.csv` son agregados **por par**, duplicados idénticamente en las filas 1am y 9am (verificado con un `assert` que compara ambas filas — son byte-idénticas). El reporte original (`results-d3-c2-2015plus.md`) los sumó entre modelos, duplicando el valor real.

| Par | Candidatos reales (población) | Nunca llenados |
|---|---:|---:|
| EURUSD | 783 | 147 |
| USDCAD | 854 | 158 |
| AUDUSD | 887 | 172 |

Coincide exactamente con tu tabla de verificación.

**Desglose correcto, por tipo de identificador**:
- **Genuinamente per-modelo** (cada modelo tiene su propio `FunnelCounters`, nunca duplicado): `windows_considered`, `triggers_with_key_level`, `model1_confirmed`. Ej. EURUSD: Modelo #1 CONFIRMED = 680 (1am) + 1039 (9am) = 1719.
- **Pair-level, no desglosable sin reejecutar generación de señales** (fuera de alcance — "no ejecutar nuevos backtests completos"): `candidates_built`, `never_filled`, `skipped_no_placement`. Declarado explícitamente como limitación, no inventado.
- **Ejecutadas (filled), reconstruido desde `trades.csv` directamente (ground truth, no aproximado)**: EURUSD 143(1am)+493(9am)=636 ✓ coincide con el `filled` pair-level (636). USDCAD 207+489=696 ✓. AUDUSD 270+445=715 ✓.
- **Cerradas/abiertas por modelo** (desde `trades.csv`): ver `robustness_funnel_corrected.csv`.

**Verificación de integridad de datos** (no solo en las operaciones finales):
- Colisiones `(pair, signal_id)`: **0**.
- Colisiones `stable_id`: **0**.
- Violaciones de orden temporal (`activation<=model1<=placed<=entry<=exit`): **0**.
- Discordancias entre la dirección embebida en `signal_id` y la columna `direction`: **0**.

Archivo: `robustness_funnel_corrected.csv`.

## Fase 2 — Sensibilidad a costos de ejecución

Penalización **adicional** aritmética sobre el R ya realizado (los costos reales `trading_cost_price` ya están horneados en cada `r_multiple` — no se descuentan de nuevo). **Esto es una sensibilidad aritmética, no una re-simulación de fills bajo nuevas condiciones de spread/slippage** — los escenarios son niveles de estrés para probar, no spreads reales afirmados.

| Escenario adicional | EURUSD total_r | USDCAD total_r | AUDUSD total_r | Combinado total_r |
|---|---:|---:|---:|---:|
| +0.000R | −0.253 | +51.178 | +27.677 | +78.603 |
| +0.010R | −6.603 | +44.228 | +20.547 | +58.173 |
| +0.025R | −16.128 | +33.803 | +9.852 | +27.528 |
| +0.040R | −25.653 | +23.378 | **−0.843** | **−3.117** |
| +0.050R | −32.003 | +16.428 | −7.973 | −23.547 |
| +0.100R | −63.753 | **−18.322** | −43.623 | −125.697 |

**Penalización máxima soportable antes de expectancy ≤ 0**:
- EURUSD: **0** — ya está en/bajo cero sin ninguna penalización adicional.
- USDCAD: **+0.0736R/trade**.
- AUDUSD: **+0.0388R/trade**.
- Combinado: **+0.0385R/trade**.

Por modelo: el margen de AUDUSD se agota casi todo en el modelo 9AM (1AM ya es negativo con solo +0.01R adicional). USDCAD aguanta más en 9AM, pero 1AM se vuelve negativo entre +0.025 y +0.04R.

Archivo: `robustness_cost_sensitivity.csv`.

## Fase 3 — Robustez temporal

**Años positivos/negativos**: EURUSD 4/8, USDCAD 6/6, AUDUSD 9/3, Combinado 7/5.

**Top-3/bottom-3 por contribución absoluta**: ver `robustness_year_breakdown.csv`/`robustness_half_period_split.csv` para el detalle completo por par y modelo.

**2015–2020 vs. 2021–2026** (closed, total_r):

| Par | 2015–2020 | 2021–2026 |
|---|---:|---:|
| EURUSD | −14.373 | +14.120 |
| USDCAD | +4.138 | **+47.040** |
| AUDUSD | −6.454 | **+34.132** |
| Combinado | **−16.689** | **+95.292** |

**El resultado combinado completo (+78.6R) depende casi enteramente de la segunda mitad de la muestra — la primera mitad (2015-2020) fue NETA PERDEDORA combinada (−16.7R).** Esto no es un hallazgo menor: la mitad más antigua del período evaluado no sostiene el resultado por sí sola.

**Drawdown cronológico máximo**: EURUSD 48.16R, USDCAD 45.44R, AUDUSD 36.82R, **Combinado 93.12R** — el combinado es mayor que la suma simple de ningún par individual, reflejo de la correlación encontrada en la Fase 5, no de diversificación.

**Leave-one-year-out, sistemático, los 12 años, los 4 pares** (`robustness_leave_one_year_out.csv`, 48 filas):

- **EURUSD cambia de signo al remover 8 de sus 12 años** — pero esto es consecuencia directa de que su baseline ya es prácticamente cero (−0.25R): cualquier año individual (positivo o negativo) de magnitud >0.25R voltea el signo. No es evidencia de un patrón oculto, es la firma esperada de un resultado sin edge real.
- **USDCAD y AUDUSD — ningún año individual, remov­ido, voltea el signo del resultado del par.** Esto incluye remover su año más grande (USDCAD sin 2016, AUDUSD sin 2017/2024): el resultado se reduce pero se mantiene positivo. Evidencia de que no dependen de un solo año, aunque sí están concentrados (ver Fase 2016=72% arriba).
- **Casos solicitados específicamente**:
  - USDCAD sin 2016: +51.178R → **+14.296R** (se removieron 57 trades que aportaron +36.882R).
  - AUDUSD sin 2017: +27.677R → **+9.972R** (59 trades, +17.705R).
  - AUDUSD sin 2024: +27.677R → **+10.206R** (62 trades, +17.471R).
  - EURUSD sin 2020: −0.253R → **−27.077R** (59 trades, +26.824R) — sin su único año grande positivo, EURUSD sería claramente negativo, no solo plano.

Archivos: `robustness_year_breakdown.csv`, `robustness_half_period_split.csv`, `robustness_drawdown_summary.csv`, `robustness_leave_one_year_out.csv`.

## Fase 4 — Incertidumbre estadística (bootstrap por bloques)

Bootstrap por bloques de calendario (mensual y trimestral) **con reemplazo sobre bloques, no sobre trades individuales** — las operaciones dentro de una ventana corta están plausiblemente correlacionadas (régimen de mercado compartido, señales simultáneas, confirmado en la Fase 5), así que un bootstrap i.i.d. de trades individuales subestimaría la incertidumbre real y **no se usa aquí como evidencia principal**. Semilla fija `20261119`, 5000 remuestreos por configuración.

| Par | Bloques (mensual) | IC 95% Total R (mensual) | P(expectancy ≤ 0) mensual | IC 95% Total R (trimestral) | P(expectancy ≤ 0) trimestral |
|---|---:|---|---:|---|---:|
| EURUSD | 143 | [−81.6, +81.5] | **0.509** | [−81.7, +81.0] | 0.491 |
| USDCAD | 141 | [−28.6, +133.4] | 0.106 | [−30.4, +137.1] | 0.123 |
| AUDUSD | 142 | [−51.1, +107.6] | 0.243 | [−43.0, +99.3] | 0.231 |
| Combinado | 143 | [−62.9, +219.2] | 0.132 | [−70.4, +229.6] | 0.157 |

**EURUSD: ~50% de probabilidad de expectancy ≤ 0 bajo remuestreo — estadísticamente indistinguible de ruido puro.** USDCAD tiene la mejor robustez relativa (~11-12%), AUDUSD intermedia (~23-24%), Combinado ~13-16%.

**Limitaciones declaradas explícitamente**: 141-143 bloques mensuales / 44-48 trimestrales son números PEQUEÑOS de unidades efectivamente independientes — los percentiles de cola con tan pocos bloques son necesariamente imprecisos. El procedimiento asume que los bloques son intercambiables en el tiempo (sin tendencia/cambio de régimen), lo cual puede no cumplirse (de hecho, la Fase 3 encontró una clara diferencia 2015-2020 vs 2021-2026). **Esto es una medida descriptiva de variabilidad de muestreo bajo la distribución histórica de bloques — no es prueba de rentabilidad futura ni un test de hipótesis formal.**

Archivo: `robustness_bootstrap.csv`.

## Fase 5 — Exposición simultánea y correlación

- Exposición concurrente máxima dentro de cada par: EURUSD 5, USDCAD 5, AUDUSD 4.
- **Exposición concurrente máxima combinada: 9 operaciones abiertas simultáneamente.**
- **Frecuencia de solapamiento entre pares: 65-75%** de las operaciones de cada par se solapan temporalmente con alguna operación de cada uno de los otros dos pares — los tres pares NO operan de forma independiente en el tiempo.
- Pérdidas simultáneas: **75 de 143 meses (52%)** tienen 2 o más pares con R neto negativo ese mes.
- Pares de trades solapados donde AMBOS resultan en pérdida: 26 (EURUSD-USDCAD), 37 (EURUSD-AUDUSD), 29 (USDCAD-AUDUSD).

**Por qué `sum(R)` combinado NO es una curva de cartera real** (supuestos declarados, no inventados):
- Cada R está normalizado al riesgo propio de CADA trade (su propio stop-loss) — 1R en EURUSD y 1R en AUDUSD no son la misma magnitud en moneda de cuenta a menos que el sizing lo iguale, y este backtest nunca modeló sizing, equity de cuenta ni margen.
- Con hasta 9 posiciones simultáneas, sumar R asume riesgo independiente y completamente colateralizado por trade — no es cómo se comporta una cuenta apalancada real bajo drawdown simultáneo.
- No se modelan límites de exposición del broker ni margin calls.
- 4 trades siguen abiertos al final de los datos disponibles — su R final es desconocido; la curva combinada ya incluye su entrada sin una salida real.

Archivos: `robustness_pairwise_overlap.csv`, `robustness_simultaneous_loss_months.csv`.

## Fase 6 — Sensibilidad de fills ambiguos

| Par | `ambiguous_bar` | `gap_filled` | % del total afectado | Total R excluyendo ambos (sensibilidad) | Delta |
|---|---:|---:|---:|---:|---:|
| EURUSD | 2 (−2.338R) | 2 (+0.499R) | 0.6% | +1.586 | +1.838 |
| USDCAD | 1 (+0.383R) | 5 (+2.589R) | 0.9% | +48.206 | −2.972 |
| AUDUSD | 3 (−0.032R) | 5 (+2.907R) | 1.1% | +24.803 | −2.874 |
| Combinado | 6 (−1.987R) | 12 (+5.995R) | 0.9% | +74.595 | −4.008 |

Impacto pequeño (<1.2% de las operaciones en cada par), y el delta de excluirlas no cambia el signo de ningún resultado. No se encontraron problemas de datos que alteren materialmente las conclusiones. No se modificó el motor de simulación ni se sustituyeron sus resultados — esto es puramente una medición de sensibilidad.

Archivo: `robustness_ambiguous_fill_sensitivity.csv`.

## Fase 7 — Validez fuera de muestra

**No hay ningún período que pueda llamarse honestamente "fuera de muestra" para D3/C2.** Esto ya estaba documentado en `audit/2026-11-17-eurusd-usdcad-audusd/data_split.json`/`optimization_history.csv` (auditoría previa, citada aquí, no reinventada):

- **`min_stop_distance_price`** (el piso de stop-loss, 6 pips para USDCAD/AUDUSD, 6 pips para EURUSD): calibrado mediante sweep sobre total_r, **in-sample, sin partición held-out**. USDCAD/AUDUSD: sweep sobre la ventana **2022-2026** (`data_split.json`: "NO train/validation/out-of-sample split exists... Both run/ran over 100% of the available historical CSV window"). **Esa ventana de calibración (2022-2026) está ÍNTEGRAMENTE contenida dentro del período 2015-2026 que esta auditoría está evaluando** — es decir, parte de los datos de evaluación son los mismos datos sobre los que se eligió el parámetro.
- **AUDUSD**: el sweep por total_r eligió 4 pips; el valor finalmente aplicado (6 pips) fue una decisión explícita del usuario por consistencia de margen de seguridad con los otros pares — no la salida directa de la optimización, pero tampoco una validación independiente.
- **`min_risk_reward=2.0`**: existe **la única validación walk-forward genuina** encontrada en todo el repositorio para cualquier parámetro de este recipe (3 folds expandiendo, train→test en años nunca vistos) — pero se hizo sobre una población DISTINTA y MÁS ANTIGUA (EURUSD solo, con el modelo 5AM incluido, antes de la versión final 1AM+9AM-solamente de 3 pares) y **nunca se re-ejecutó contra el recipe actual** que cubre esta auditoría.
- **El diseño causal D1/D2/D3 mismo** (el mecanismo de anchor M15, las ventanas 9AM) fue iterado y corregido observando resultados reales extraídos de este mismo período 2015-2026 (ej. la corrección EST/EDT se validó con trades reales de enero/julio 2024, dentro del rango evaluado).

**Declaración explícita (per instrucción)**: todo el histórico disponible, directa o indirectamente, ha influido tanto en los parámetros de la estrategia (piso de stop, costo de ejecución) como en el propio diseño de este experimento causal (D1/D2/D3). No existe un holdout limpio. Cualquier número reportado en esta auditoría —incluidos los +78.6R— debe leerse como **resultado in-sample**, no como validación predictiva independiente.

## Veredicto por dimensión

| Dimensión | Veredicto | Evidencia concreta |
|---|---|---|
| **1. Integridad de los resultados** | **APROBADA** | 0 colisiones signal_id/stable_id, 0 violaciones de orden temporal, reconciliación CSV-vs-runner exacta, archivos históricos verificados sin cambios (git diff vacío). El bug de embudo encontrado estaba en el script de reporte, no en los datos de trades. |
| **2. Robustez estadística** | **INCONCLUSA** | EURUSD: P(expectancy≤0)≈50% (ruido). USDCAD/AUDUSD: 11-24%, no despreciable. Combinado 13-16%. Solo 44-143 bloques disponibles — intervalos anchos, no es prueba formal. |
| **3. Resistencia a costos** | **NO APROBADA** | EURUSD ya es negativo sin penalización adicional. AUDUSD se vuelve negativo con solo +0.04R extra por trade. Combinado se vuelve negativo entre +0.025R y +0.04R — un margen delgado frente a variaciones razonables de costo de ejecución real. |
| **4. Consistencia temporal** | **NO APROBADA** | El resultado combinado depende casi enteramente de 2021-2026 (+95.3R); 2015-2020 fue neto perdedor combinado (−16.7R). EURUSD es indistinguible de ruido (8/12 años voltean el signo). Alta concentración por año incluso donde no hay dependencia de un solo año (USDCAD/AUDUSD). |
| **5. Riesgo de cartera** | **NO APROBADA** | 65-75% de solapamiento temporal entre pares, 52% de los meses con 2+ pares perdiendo simultáneamente, hasta 9 posiciones concurrentes, sin sizing/margen modelado — sumar R entre pares sobreestima la diversificación real. |
| **6. Validez fuera de muestra** | **NO APROBADA** | Documentado explícitamente: no existe holdout limpio. La ventana de calibración del stop-floor (2022-2026) se superpone con la ventana evaluada (2015-2026). La única validación walk-forward real del repo es sobre un recipe distinto y nunca se repitió para éste. |
| **7. Preparación para prueba forward en demo** | **INCONCLUSA** | No hay evidencia suficiente para un "sí" confiado (sin OOS real, costos frágiles, riesgo de cartera no modelado, EURUSD sin edge) ni para descartar un "no" categórico (USDCAD/AUDUSD muestran algo de señal, robusta a remover un año individual). Es una decisión del usuario, no algo que deba decidir yo. |

**No se declara la estrategia válida solo porque el R combinado sea positivo.** El hallazgo honesto: EURUSD no muestra edge estadísticamente distinguible de cero; USDCAD y AUDUSD muestran algo de señal que sobrevive la remoción de su año más grande, pero esa señal está concentrada en la mitad reciente de la muestra (2021-2026), es sensible a costos de ejecución moderados, y no ha sido evaluada en ningún período genuinamente fuera de muestra.

## No hecho en esta ronda

No se ejecutó D1 ni D2. No se recalibró ningún parámetro. No se modificó `detector/`, `scanner/`, `docs/`. No se sobrescribió ningún CSV o script histórico (todos los archivos de esta ronda usan el prefijo `robustness_` o son nuevos). Me detengo acá, entregando esta auditoría de robustez para tu revisión, sin continuar con optimizaciones, nuevos experimentos ni cambios de producción.

export type Lang = 'es' | 'en';

export type Dict = {
  app: {
    brand: string;
    tagline: string;
    subtitle: string;
    futureLocked: string;
    statusReview: string;
    themeDark: string;
    themeLight: string;
  };
  session: {
    label: string;
    hint: string;
    pair: string;
    model: string;
    dateNy: string;
    replayTime: string;
    utc: string;
    noticeNonEvaluable: string;
    statusNotStarted: string;
    statusInProgress: string;
    statusFinished: string;
  };
  controls: {
    start: string;
    startHint: string;
    next: string;
    nextHint: string;
    play: string;
    playHint: string;
    pause: string;
    pauseHint: string;
    finish: string;
    finishHint: string;
    lastM15: (value: string) => string;
    lastM15Empty: string;
    none: string;
  };
  chart: {
    h4Title: string;
    h4Subtitle: (suffix: string) => string;
    dailyTitle: string;
    dailySubtitle: (suffix: string) => string;
    m15Title: string;
    m15Subtitle: string;
    forming: string;
    closed: string;
    fullHistory: string;
    hint: string;
    panEarlier: (tf: string) => string;
    panLater: (tf: string) => string;
    zoomIn: (tf: string) => string;
    zoomOut: (tf: string) => string;
    availableCandles: (tf: string) => string;
    hoverHint: string;
    selectingHint: string;
    reviewHint: string;
    empty: string;
    tooltip: (time: string, zone: string, o: string, h: string, l: string, c: string, forming: boolean, gap: boolean) => string;
    formingSuffix: string;
    gapSuffix: string;
    yourLevel: string;
  };
  manualLevel: {
    label: string;
    hint: string;
    placeholder: string;
    clear: string;
  };
  decision: {
    heading: string;
    hint: string;
    stepCrtTitle: string;
    crtValid: string;
    crtValidHint: string;
    feederReference: string;
    feederReferenceHint: string;
    feederReferencePlaceholder: string;
    useFeederReference: string;
    useFeederReferenceHint: string;
    pickOnChart: string;
    pickOnChartHint: string;
    pickOnChartM15: string;
    pickOnChartM15Hint: string;
    pickArmed: string;
    sweptSide: string;
    sweptSideHint: string;
    sweepConfirmedAt: string;
    sweepConfirmedAtHint: string;
    stepKeyLevelTitle: string;
    keyLevelValid: string;
    keyLevelValidHint: string;
    keyLevelType: string;
    keyLevelTypeHint: string;
    keyLevelTypePlaceholder: string;
    keyLevelPrice: string;
    keyLevelPriceHint: string;
    keyLevelAvailableAt: string;
    keyLevelAvailableAtHint: string;
    keyLevelTouchValid: string;
    keyLevelTouchValidHint: string;
    stepModel1Title: string;
    beginConfirmationSearch: string;
    beginConfirmationSearchHint: string;
    model1Exists: string;
    model1ExistsHint: string;
    model1AnchorAt: string;
    model1AnchorAtHint: string;
    direction: string;
    directionHint: string;
    model1ConfirmedAt: string;
    model1ConfirmedAtHint: string;
    stepFinalTitle: string;
    action: string;
    actionHint: string;
    actionPlaceholder: string;
    buy: string;
    sell: string;
    wait: string;
    discard: string;
    dataIssue: string;
    entryPrice: string;
    entryPriceHint: string;
    stopLoss: string;
    stopLossHint: string;
    takeProfit: string;
    takeProfitHint: string;
    discardReason: string;
    discardReasonHint: string;
    discardReasonPlaceholder: string;
    discardInvalidCrt: string;
    discardNoSweep: string;
    discardNoKeyLevel: string;
    discardInvalidTouch: string;
    discardNoModel1: string;
    discardTiming: string;
    discardDataGap: string;
    discardOther: string;
    dataIssueReason: string;
    dataIssueReasonHint: string;
    dataIssueReasonPlaceholder: string;
    notes: string;
    notesHint: string;
    notesPlaceholder: string;
    save: string;
    historyTitle: string;
    historyEmpty: string;
    unspecified: string;
    yes: string;
    no: string;
    uncertain: string;
    high: string;
    low: string;
    both: string;
    sideNone: string;
    bullish: string;
    bearish: string;
    undetermined: string;
    decisionFallback: string;
  };
  annotation: {
    heading: string;
    hint: string;
    type: string;
    typeHint: string;
    typeKeyLevel: string;
    typeMax: string;
    typeMin: string;
    typeM15Anchor: string;
    typeHorizontal: string;
    timeframe: string;
    timeframeHint: string;
    sourceCandle: string;
    sourceCandleHint: string;
    sourceArmed: string;
    sourceSelected: (time: string) => string;
    sourceIdle: string;
    price: string;
    priceHint: string;
    levelType: string;
    levelTypeHint: string;
    levelTypePlaceholder: string;
    notes: string;
    notesHint: string;
    save: string;
    historyTitle: string;
    historyEmpty: string;
  };
  errors: {
    requestFailed: (status: number) => string;
    caseFinished: string;
    decisionSaved: string;
  };
};

const es: Dict = {
  app: {
    brand: 'Consola de Fidelidad CRT',
    tagline: 'Taller de investigación local',
    subtitle: 'Leé el mercado, una vela cerrada a la vez.',
    futureLocked: 'Datos futuros bloqueados',
    statusReview: 'Revisión humana · Etapa 1',
    themeDark: 'Oscuro',
    themeLight: 'Claro',
  },
  session: {
    label: 'Sesión histórica',
    hint: 'Elegí uno de los 30 casos del piloto. El estado muestra si ya la empezaste o la terminaste.',
    pair: 'Par',
    model: 'Modelo',
    dateNy: 'Fecha · NY',
    replayTime: 'Hora del replay',
    utc: 'UTC',
    noticeNonEvaluable: 'Este caso tiene un bloque de datos incompleto. Registrá el problema de datos y no evalúes la fidelidad de la estrategia con este caso.',
    statusNotStarted: 'sin iniciar',
    statusInProgress: 'en curso',
    statusFinished: 'finalizado',
  },
  controls: {
    start: 'Iniciar sesión',
    startHint: 'Arranca el replay en la apertura de la vela feeder de este caso.',
    next: 'Siguiente vela M15 →',
    nextHint: 'Avanza el cursor del replay 15 minutos. Nunca revela una vela antes de que cierre.',
    play: 'Reproducir',
    playHint: 'Avanza automáticamente una vela M15 cada poco más de un segundo.',
    pause: 'Pausar',
    pauseHint: 'Detiene el avance automático.',
    finish: 'Finalizar sesión',
    finishHint: 'Se habilita solo al llegar al cierre de la ventana documentada con una decisión guardada en ese instante.',
    lastM15: value => `Última M15 cerrada · ${value} UTC`,
    lastM15Empty: 'ninguna',
    none: 'Iniciá la sesión para revelar la primera vela cerrada',
  },
  chart: {
    h4Title: 'H4 · feeder NY',
    h4Subtitle: suffix => `Grilla anclada a NY · aperturas clave 9PM / 1AM / 5AM / 9AM · ${suffix}`,
    dailyTitle: 'Daily · 17:00 NY',
    dailySubtitle: suffix => `Reconstruida solo desde M15 · no es el Daily nativo del broker${suffix}`,
    m15Title: 'M15 · ejecución',
    m15Subtitle: 'Una vela entra al gráfico recién al cerrar',
    forming: 'vela actual en formación',
    closed: 'velas cerradas',
    fullHistory: ' · historial completo cargado',
    hint: 'Arrastrá o usá las flechas para revisar · Rueda o +/− para hacer zoom',
    panEarlier: tf => `Ver velas más antiguas de ${tf}`,
    panLater: tf => `Ver velas más recientes de ${tf}`,
    zoomIn: tf => `Acercar ${tf}`,
    zoomOut: tf => `Alejar ${tf}`,
    availableCandles: tf => `Velas disponibles de ${tf}`,
    hoverHint: 'Pasá el cursor sobre una vela para ver su OHLC',
    selectingHint: 'Hacé click en una vela para usarla como origen de la anotación',
    reviewHint: 'Arrastrá o usá las flechas para revisar · Rueda o +/− para hacer zoom',
    empty: 'No hay velas en esta vista',
    tooltip: (time, zone, o, h, l, c, forming, gap) =>
      `${time} ${zone} · A ${o} M ${h} m ${l} C ${c}${forming ? ' · en formación' : ''}${gap ? ' · hueco de datos' : ''}`,
    formingSuffix: ' · en formación',
    gapSuffix: ' · hueco de datos',
    yourLevel: 'Tu nivel',
  },
  manualLevel: {
    label: 'Tu marcador de precio',
    hint: 'Precio de referencia que se dibuja en los tres gráficos a la vez, sin guardarse. Usalo para comparar visualmente, no para registrar un nivel.',
    placeholder: 'Ingresá un precio para inspeccionar en todos los gráficos',
    clear: 'Borrar',
  },
  decision: {
    heading: 'Decisión: operar o descartar',
    hint: 'Esto es tu decisión final, no una marca sobre el gráfico — para eso usá "Marcá lo que ves" más abajo. Cada guardado crea un registro aparte con el cursor histórico visible en ese momento. Seguí el orden: CRT → Key Level → Modelo #1 → decisión final.',
    stepCrtTitle: 'Lectura del CRT',
    crtValid: '¿CRT válido?',
    crtValidHint: 'Según el charter: ¿el rango de la vela feeder cumple las condiciones para considerarse un CRT válido en este caso?',
    feederReference: 'Apertura feeder de referencia (hora local NY)',
    feederReferenceHint: 'Escribí la hora que verías en un reloj de Nueva York (no la hora de tu computadora). El EST/EDT se resuelve solo con la fecha del caso.',
    feederReferencePlaceholder: 'AAAA-MM-DD HH:MM',
    useFeederReference: 'Usar vela de referencia',
    useFeederReferenceHint: 'Completa automáticamente con la apertura real de la vela feeder de referencia que ya calculó el servidor, en hora NY — podés corregirla si tu lectura difiere.',
    pickOnChart: 'Elegir en el gráfico',
    pickOnChartHint: 'Hacé click en una vela de H4, Daily o M15 y se completa sola con su hora UTC real.',
    pickOnChartM15: 'Elegir en M15',
    pickOnChartM15Hint: 'Tiene que ser una vela M15 real y cerrada — hacé click directamente sobre el gráfico M15.',
    pickArmed: 'Hacé click en una vela…',
    sweptSide: 'Lado barrido',
    sweptSideHint: '¿La vela de activación barrió el máximo, el mínimo, ambos o ninguno del rango de referencia?',
    sweepConfirmedAt: 'Barrido confirmado a las (UTC)',
    sweepConfirmedAtHint: 'Hora UTC exacta en que el precio tocó y barrió el nivel, sin importar la zona horaria de tu computadora.',
    stepKeyLevelTitle: 'Key Level',
    keyLevelValid: '¿Key Level válido?',
    keyLevelValidHint: '¿El nivel que identificaste cumple con la definición documentada de Key Level del charter?',
    keyLevelType: 'Tipo de Key Level',
    keyLevelTypeHint: 'Nombralo con la terminología del charter: FVG, Order Block, Breaker, etc.',
    keyLevelTypePlaceholder: 'Tipo de nivel documentado',
    keyLevelPrice: 'Precio del Key Level',
    keyLevelPriceHint: 'El precio exacto del nivel que estás evaluando.',
    keyLevelAvailableAt: 'Disponible a las (UTC)',
    keyLevelAvailableAtHint: 'Momento UTC en que ese nivel ya estaba formado y visible, antes de la confirmación del Modelo #1.',
    keyLevelTouchValid: '¿Toque válido?',
    keyLevelTouchValidHint: '¿El precio tocó el Key Level de la forma que el charter exige para considerarlo válido?',
    stepModel1Title: 'Modelo #1',
    beginConfirmationSearch: '¿Empezás a buscar confirmación?',
    beginConfirmationSearchHint: 'Marcá si, en este instante del replay, comenzás activamente a buscar la confirmación del Modelo #1.',
    model1Exists: '¿Existe Modelo #1?',
    model1ExistsHint: '¿La secuencia de velas M15 forma un Modelo #1 válido según el charter?',
    model1AnchorAt: 'Apertura de la vela anchor M15 (UTC)',
    model1AnchorAtHint: 'Hora de apertura UTC de la vela M15 que usás como anchor. Tiene que ser una vela real ya cerrada.',
    direction: 'Dirección',
    directionHint: '¿El Modelo #1 confirmado es alcista, bajista, o todavía no podés determinarlo?',
    model1ConfirmedAt: 'Confirmado a las (UTC)',
    model1ConfirmedAtHint: 'Hora UTC en que considerás confirmado el Modelo #1, no puede ser anterior al cierre de la vela anchor.',
    stepFinalTitle: 'Decisión final',
    action: 'Acción',
    actionHint: 'Qué vas a registrar: una operación, seguir esperando, descartar la oportunidad, o reportar un problema de datos.',
    actionPlaceholder: 'Elegí una acción',
    buy: 'Comprar',
    sell: 'Vender',
    wait: 'Seguir esperando',
    discard: 'Descartar oportunidad',
    dataIssue: 'Reportar problema de datos (no evaluable)',
    entryPrice: 'Precio de entrada',
    entryPriceHint: 'El precio exacto al que entrarías. Tiene que quedar entre el stop y el target según la dirección.',
    stopLoss: 'Stop Loss',
    stopLossHint: 'El precio donde cortarías la pérdida si la operación va en contra.',
    takeProfit: 'Take Profit',
    takeProfitHint: 'El precio objetivo donde tomarías la ganancia.',
    discardReason: 'Motivo del descarte',
    discardReasonHint: 'Elegí la razón documentada por la que esta oportunidad no es válida.',
    discardReasonPlaceholder: 'Elegí un motivo',
    discardInvalidCrt: 'CRT inválido',
    discardNoSweep: 'Sin barrido válido',
    discardNoKeyLevel: 'Sin Key Level válido',
    discardInvalidTouch: 'Toque de Key Level inválido',
    discardNoModel1: 'Sin Modelo #1',
    discardTiming: 'Fuera del horario de la regla',
    discardDataGap: 'Datos faltantes',
    discardOther: 'Otro motivo documentado',
    dataIssueReason: 'Problema de datos (no es ausencia de señal)',
    dataIssueReasonHint: 'Describí qué dato falta, está mal formado o es inconsistente. Esto no significa que no había oportunidad.',
    dataIssueReasonPlaceholder: 'Describí el dato faltante, mal formado o inconsistente.',
    notes: 'Observaciones / razón',
    notesHint: 'Qué viste y por qué es importante. Si una regla del charter te resultó ambigua, anotá acá la ambigüedad y la interpretación que usaste.',
    notesPlaceholder: '¿Qué viste, y por qué es importante?',
    save: 'Guardar decisión',
    historyTitle: 'Decisiones registradas',
    historyEmpty: 'No hay ninguna decisión registrada para este caso.',
    unspecified: 'Sin especificar',
    yes: 'Sí',
    no: 'No',
    uncertain: 'Incierto',
    high: 'Máximo',
    low: 'Mínimo',
    both: 'Ambos',
    sideNone: 'Ninguno',
    bullish: 'Alcista',
    bearish: 'Bajista',
    undetermined: 'Sin determinar',
    decisionFallback: 'Decisión',
  },
  annotation: {
    heading: 'Marcá lo que ves',
    hint: 'Esto solo deja una marca visual en el gráfico (un nivel, un máximo, un anchor) — no es una decisión de operar. Independiente de D3/C2. Cada entrada guarda su timestamp y la convención horaria de la temporalidad usada.',
    type: 'Tipo',
    typeHint: 'Qué tipo de marca vas a registrar sobre el gráfico.',
    typeKeyLevel: 'Key Level (tipo documentado)',
    typeMax: 'Máximo (swing high)',
    typeMin: 'Mínimo (swing low)',
    typeM15Anchor: 'Anchor del Modelo #1 (M15)',
    typeHorizontal: 'Nivel de precio horizontal',
    timeframe: 'Temporalidad',
    timeframeHint: 'En qué gráfico (M15, H4 o Daily) vas a marcar este nivel.',
    sourceCandle: 'Vela de origen',
    sourceCandleHint: 'Hacé click para elegir la vela en el gráfico; nunca escribas la fecha a mano.',
    sourceArmed: 'Hacé click en una vela del gráfico…',
    sourceSelected: time => `Seleccionada · ${time}`,
    sourceIdle: 'Elegir en el gráfico',
    price: 'Precio',
    priceHint: 'El precio exacto del nivel u observación.',
    levelType: 'Tipo documentado',
    levelTypeHint: 'Nombralo con la terminología del charter: FVG, Order Block, Breaker, etc.',
    levelTypePlaceholder: 'FVG, Order Block, Breaker…',
    notes: 'Notas',
    notesHint: 'Cualquier aclaración adicional sobre esta marca.',
    save: 'Guardar anotación',
    historyTitle: 'Anotaciones registradas',
    historyEmpty: 'No hay ninguna anotación registrada para este caso.',
  },
  errors: {
    requestFailed: status => `Falló la solicitud: ${status}`,
    caseFinished: 'Caso finalizado. Tus decisiones registradas siguen disponibles para revisión.',
    decisionSaved: 'Decisión guardada como un nuevo registro inmutable.',
  },
};

const en: Dict = {
  app: {
    brand: 'CRT Fidelity Console',
    tagline: 'Local research workspace',
    subtitle: 'Read the market, one closed candle at a time.',
    futureLocked: 'Future data locked',
    statusReview: 'Human review · Stage 1',
    themeDark: 'Dark',
    themeLight: 'Light',
  },
  session: {
    label: 'Historical case',
    hint: 'Pick one of the 30 pilot cases. Status shows whether you have started or finished it.',
    pair: 'Pair',
    model: 'Model',
    dateNy: 'Date · NY',
    replayTime: 'Replay time',
    utc: 'UTC',
    noticeNonEvaluable: 'This case has an incomplete data bucket. Record the data problem, and do not assess strategy fidelity from this case.',
    statusNotStarted: 'not started',
    statusInProgress: 'in progress',
    statusFinished: 'finished',
  },
  controls: {
    start: 'Start case',
    startHint: "Starts the replay at this case's feeder candle open.",
    next: 'Next M15 candle →',
    nextHint: 'Advances the replay cursor 15 minutes. Never reveals a candle before it closes.',
    play: 'Play',
    playHint: 'Advances one M15 candle automatically, a bit over once a second.',
    pause: 'Pause',
    pauseHint: 'Stops automatic advance.',
    finish: 'Finish case',
    finishHint: 'Enabled only once the documented window has closed with a decision saved at that exact instant.',
    lastM15: value => `Last closed M15 open · ${value} UTC`,
    lastM15Empty: 'none',
    none: 'Start the case to reveal the first closed candle',
  },
  chart: {
    h4Title: 'H4 · NY feeder',
    h4Subtitle: suffix => `NY-anchored grid · key opens 9PM / 1AM / 5AM / 9AM · ${suffix}`,
    dailyTitle: 'Daily · 17:00 NY',
    dailySubtitle: suffix => `Reconstructed from M15 only · not the broker's native Daily${suffix}`,
    m15Title: 'M15 · execution',
    m15Subtitle: 'A candle enters the chart only after its close',
    forming: 'current candle forming',
    closed: 'closed candles',
    fullHistory: ' · full history loaded',
    hint: 'Drag or use arrows to review · Scroll or use +/- to zoom',
    panEarlier: tf => `Review earlier ${tf} candles`,
    panLater: tf => `Review later ${tf} candles`,
    zoomIn: tf => `Zoom in ${tf}`,
    zoomOut: tf => `Zoom out ${tf}`,
    availableCandles: tf => `Available ${tf} candles`,
    hoverHint: 'Hover a candle for OHLC',
    selectingHint: 'Click a candle to use it as the annotation source',
    reviewHint: 'Drag or use arrows to review · Scroll or use +/- to zoom',
    empty: 'No candles in this view',
    tooltip: (time, zone, o, h, l, c, forming, gap) =>
      `${time} ${zone} · O ${o} H ${h} L ${l} C ${c}${forming ? ' · forming' : ''}${gap ? ' · data gap' : ''}`,
    formingSuffix: ' · forming',
    gapSuffix: ' · data gap',
    yourLevel: 'Your level',
  },
  manualLevel: {
    label: 'Your price marker',
    hint: 'A reference price drawn on all three charts at once, never saved. Use it to compare visually, not to record a level.',
    placeholder: 'Enter a level to inspect on all charts',
    clear: 'Clear',
  },
  decision: {
    heading: 'Decision: trade or discard',
    hint: 'This is your final decision, not a chart mark — use "Mark what you see" below for that. Every save creates a separate entry with the visible historical cursor. Follow the order: CRT → Key Level → Model #1 → final decision.',
    stepCrtTitle: 'CRT reading',
    crtValid: 'Valid CRT?',
    crtValidHint: "Per the charter: does this feeder candle's range meet the conditions for a valid CRT in this case?",
    feederReference: 'Reference feeder open (New York local time)',
    feederReferenceHint: "Enter the clock time you'd see in New York (not your computer's time). EST/EDT is resolved from the case date alone.",
    feederReferencePlaceholder: 'YYYY-MM-DD HH:MM',
    useFeederReference: 'Use reference candle',
    useFeederReferenceHint: "Fills in the real open of the reference feeder candle the server already computed, in NY time — you can still correct it if your own reading differs.",
    pickOnChart: 'Select on chart',
    pickOnChartHint: 'Click a candle on H4, Daily, or M15 and it fills in with its real UTC time.',
    pickOnChartM15: 'Select on M15',
    pickOnChartM15Hint: 'Must be a real, closed M15 candle — click directly on the M15 chart.',
    pickArmed: 'Click a candle…',
    sweptSide: 'Swept side',
    sweptSideHint: 'Did the activation candle sweep the high, the low, both, or neither of the reference range?',
    sweepConfirmedAt: 'Sweep confirmed at (UTC)',
    sweepConfirmedAtHint: "Exact UTC time price touched and swept the level, regardless of your computer's timezone.",
    stepKeyLevelTitle: 'Key Level',
    keyLevelValid: 'Valid Key Level?',
    keyLevelValidHint: 'Does the level you identified meet the charter-documented definition of a Key Level?',
    keyLevelType: 'Key Level type',
    keyLevelTypeHint: "Name it with the charter's own terminology: FVG, Order Block, Breaker, etc.",
    keyLevelTypePlaceholder: 'Documented level type',
    keyLevelPrice: 'Key Level price',
    keyLevelPriceHint: 'The exact price of the level you are evaluating.',
    keyLevelAvailableAt: 'Available at (UTC)',
    keyLevelAvailableAtHint: 'UTC instant that level was already formed and visible, before Model #1 confirmation.',
    keyLevelTouchValid: 'Valid touch?',
    keyLevelTouchValidHint: 'Did price touch the Key Level the way the charter requires to count it valid?',
    stepModel1Title: 'Model #1',
    beginConfirmationSearch: 'Begin confirmation search?',
    beginConfirmationSearchHint: 'Mark whether, at this instant of the replay, you actively start looking for Model #1 confirmation.',
    model1Exists: 'Model #1 exists?',
    model1ExistsHint: 'Does the M15 candle sequence form a valid Model #1 per the charter?',
    model1AnchorAt: 'Anchor M15 open (UTC)',
    model1AnchorAtHint: 'UTC open time of the M15 candle you use as anchor. Must be a real, already-closed candle.',
    direction: 'Direction',
    directionHint: "Is the confirmed Model #1 bullish, bearish, or can't you tell yet?",
    model1ConfirmedAt: 'Confirmed at (UTC)',
    model1ConfirmedAtHint: 'UTC time you consider Model #1 confirmed; cannot precede the anchor candle close.',
    stepFinalTitle: 'Final decision',
    action: 'Action',
    actionHint: "What you're recording: a trade, waiting longer, discarding the opportunity, or a data problem.",
    actionPlaceholder: 'Select action',
    buy: 'Buy',
    sell: 'Sell',
    wait: 'Keep waiting',
    discard: 'Discard opportunity',
    dataIssue: 'Report data problem (not evaluable)',
    entryPrice: 'Entry price',
    entryPriceHint: 'The exact price you would enter at. Must sit between stop and target in the stated direction.',
    stopLoss: 'Stop Loss',
    stopLossHint: 'The price where you would cut the loss if the trade goes against you.',
    takeProfit: 'Take Profit',
    takeProfitHint: 'The target price where you would take profit.',
    discardReason: 'Discard reason',
    discardReasonHint: 'Pick the documented reason this opportunity is invalid.',
    discardReasonPlaceholder: 'Select reason',
    discardInvalidCrt: 'Invalid CRT',
    discardNoSweep: 'No valid sweep',
    discardNoKeyLevel: 'No valid Key Level',
    discardInvalidTouch: 'Invalid Key Level touch',
    discardNoModel1: 'No Model #1',
    discardTiming: 'Timing outside rules',
    discardDataGap: 'Missing data',
    discardOther: 'Other documented reason',
    dataIssueReason: 'Data problem (not an absence of signal)',
    dataIssueReasonHint: 'Describe the missing, malformed, or inconsistent data. This never means no opportunity existed.',
    dataIssueReasonPlaceholder: 'Describe the missing, malformed, or inconsistent data.',
    notes: 'Observations / reason',
    notesHint: "What you saw and why it matters. If a charter rule felt ambiguous, note the ambiguity and the interpretation you used.",
    notesPlaceholder: 'What did you see, and why does it matter?',
    save: 'Save decision',
    historyTitle: 'Recorded decisions',
    historyEmpty: 'No decision recorded for this case.',
    unspecified: 'Unspecified',
    yes: 'Yes',
    no: 'No',
    uncertain: 'Uncertain',
    high: 'High',
    low: 'Low',
    both: 'Both',
    sideNone: 'None',
    bullish: 'Bullish',
    bearish: 'Bearish',
    undetermined: 'Undetermined',
    decisionFallback: 'Decision',
  },
  annotation: {
    heading: 'Mark what you see',
    hint: 'This only leaves a visual mark on the chart (a level, a max, an anchor) — it is not a trading decision. Independent of D3/C2. Every entry stores its timestamp and the timeframe convention used.',
    type: 'Type',
    typeHint: 'What kind of mark you are about to record on the chart.',
    typeKeyLevel: 'Key Level (documented type)',
    typeMax: 'Max (swing high)',
    typeMin: 'Min (swing low)',
    typeM15Anchor: 'Model #1 anchor (M15)',
    typeHorizontal: 'Horizontal price level',
    timeframe: 'Timeframe',
    timeframeHint: 'Which chart (M15, H4, or Daily) you are marking this level on.',
    sourceCandle: 'Source candle',
    sourceCandleHint: 'Click to pick the candle on the chart; never type a date by hand.',
    sourceArmed: 'Click a candle on the chart…',
    sourceSelected: time => `Selected · ${time}`,
    sourceIdle: 'Select on chart',
    price: 'Price',
    priceHint: 'The exact price of the level or observation.',
    levelType: 'Documented level type',
    levelTypeHint: "Name it with the charter's own terminology: FVG, Order Block, Breaker, etc.",
    levelTypePlaceholder: 'FVG, Order Block, Breaker…',
    notes: 'Notes',
    notesHint: 'Any extra clarification about this mark.',
    save: 'Save annotation',
    historyTitle: 'Recorded annotations',
    historyEmpty: 'No annotation recorded for this case.',
  },
  errors: {
    requestFailed: status => `Request failed: ${status}`,
    caseFinished: 'Case finished. Your recorded decisions remain available for review.',
    decisionSaved: 'Decision saved as a new immutable record.',
  },
};

export const dictionaries: Record<Lang, Dict> = { es, en };

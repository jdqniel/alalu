# alalu — Quant Learning Lab

Laboratorio personal para aprender trading algorítmico desde cero. Cada archivo representa una iteración del proceso de investigación: desde una hipótesis simple hasta un simulador en tiempo real con apalancamiento.

---

## El proceso de aprendizaje

### Fase 1 — Hipótesis inicial (`main.py`)
**Concepto:** Reversión a la media con Z-Score + EMA 200 en BTC/USDT (5m).

La idea: si el precio se desvía estadísticamente de su media reciente (Z-Score extremo) pero sigue dentro de la tendencia macro (encima de EMA 200), debería volver. El backtest es vectorizado, simple, sin TP/SL explícito.

**Lo que aprendí:** Cómo construir la señal más básica. Que las comisiones importan (el `fee` devora retornos en timeframes cortos). Que el `shift(1)` evita el lookahead bias.

---

### Fase 2 — Optimización de parámetros (`grid_search.py`)
**Concepto:** El mismo modelo, pero ¿cuáles son los mejores parámetros?

Grid search sobre ventana de rolling (10, 20, 30, 50 períodos) y umbral de Z-Score (1.5 a 3.0). Timeframe subió a 1h para tener más historia sin overfitting a ruido de 5m.

**Lo que aprendí:** Que los parámetros óptimos en backtest rara vez son los mejores en producción (overfitting). Que la optimización ciega puede engañar.

---

### Fase 3 — Volumen como confirmación (`grid_search_with_volume.py`)
**Concepto:** El volumen valida el movimiento. Un spike de precio sin volumen es ruido.

Cambio importante: la estrategia invierte el signo. Ya no es reversión a la media pura sino **momentum** (Z-Score positivo = fuerza = comprar). Se añaden TP (2%) y SL (1%) explícitos, y el volumen debe superar su media rolling para confirmar.

**Lo que aprendí:** La diferencia entre reversión a la media y momentum. Cómo implementar TP/SL en un backtest trade-by-trade. Por qué el volumen filtra señales falsas.

---

### Fase 4 — Forward testing en tiempo real (`master.py`)
**Concepto:** Pasar de backtest a observación live. Sin dinero real, solo detección de señales.

Escanea 5 pares cada 15 segundos usando datos de Binance vía `ccxt`. Cuando se detecta momentum + volumen + tendencia, registra la señal en `real_time_forward_testing.csv`. El sistema de `active_signals` evita spam de alertas repetidas.

**Lo que aprendí:** La diferencia entre "funcionar en papel" y "funcionar en tiempo real". Que el manejo de estados (`active_signals`) es crítico para no inundar el log.

---

### Fase 5 — Simulación con apalancamiento 5x (`master_x5.py`)
**Concepto:** ¿Qué pasa si añado apalancamiento? Simulación de posiciones virtuales con TP 3% / SL 1.5% (equivalentes a 15% / 7.5% con 5x).

Gestiona posiciones abiertas en memoria, calcula P&L apalancado y precio de liquidación aproximado. Loguea cada entrada y salida con métricas completas.

**Lo que aprendí:** Cómo el apalancamiento amplifica tanto ganancias como pérdidas. Que el precio de liquidación en 5x está al 20% de caída. Que TP/SL son indispensables con leverage.

---

## Stack

| Herramienta | Uso |
|---|---|
| `ccxt` | Conectar con Binance (datos OHLCV en tiempo real) |
| `pandas` | Manipulación de series temporales |
| `numpy` | Cálculos vectorizados |
| `matplotlib` | Visualización (usado en exploración, comentado en código) |

## Estructura

```
alalu/
├── main.py                       # Fase 1: backtest de reversión a la media
├── grid_search.py                # Fase 2: optimización de parámetros
├── grid_search_with_volume.py    # Fase 3: momentum + volumen + TP/SL
├── master.py                     # Fase 4: scanner en tiempo real
├── master_x5.py                  # Fase 5: simulación con leverage 5x
└── real_time_forward_testing.csv # Log de señales detectadas en vivo
```

## Cómo correr

```bash
# Instalar dependencias (usa uv)
uv sync

# Correr cualquier fase
uv run main.py
uv run grid_search.py
uv run grid_search_with_volume.py

# Scanner en vivo (loop infinito, Ctrl+C para parar)
uv run master.py
uv run master_x5.py
```

> **Nota:** `master.py` y `master_x5.py` no ejecutan operaciones reales. Todo es paper trading / observación.

---

## Conceptos clave que cubre este lab

- **Z-Score**: distancia estadística del precio respecto a su media, medida en desviaciones estándar
- **EMA 200**: filtro de tendencia macro. Por encima = bullish, por debajo = bearish
- **Volume spike**: confirmación de que el movimiento tiene fuerza real detrás
- **Backtest vectorizado vs. trade-by-trade**: diferencia en precisión y complejidad
- **Lookahead bias**: usar `shift(1)` para que la señal se ejecute en la vela siguiente
- **Forward testing**: observar la estrategia en tiempo real antes de arriesgar capital
- **Apalancamiento y liquidación**: cómo el leverage amplifica el riesgo

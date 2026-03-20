# alalu — Quant Learning Lab

Laboratorio personal para aprender trading algorítmico desde cero. Cada archivo representa una iteración del proceso de investigación: desde una hipótesis simple hasta un bot en producción con dashboard profesional.

---

## El proceso de aprendizaje

### Fase 1 — Hipótesis inicial (`main.py`)
**Concepto:** Reversión a la media con Z-Score + EMA 200 en BTC/USDT (5m).

La idea: si el precio se desvía estadísticamente de su media reciente (Z-Score extremo) pero sigue dentro de la tendencia macro (encima de EMA 200), debería revertir. El backtest es vectorizado, simple, sin TP/SL explícito.

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

### Fase 6 — Bot quant de momentum (`alalu_bot/`)
**Concepto:** Rediseño completo de la estrategia con indicadores quant reales y gestión de riesgo profesional.

Reemplaza el Z-Score simple por una señal multifactor:
- **ROC** (Rate of Change): velocidad del precio, señal primaria de momentum
- **RSI**: filtro de zona (long solo entre 50–70, short entre 30–50)
- **ADX + ±DI**: confirmación de tendencia (ADX > 25) y dirección (+DI vs -DI)
- **ATR**: stop loss dinámico basado en volatilidad actual
- **Volumen**: spike de volumen como confirmación final

Añade soporte para **posiciones short** (solo en futuros 5x), **trailing stop** para dejar correr ganadores, **salida por tiempo** (máx. 60 min por trade), **circuit breaker** al 80% de drawdown, y límite de correlación (máx. 2 trades simultáneos entre pares altamente correlacionados).

**Lo que aprendí:** Que una señal multifactor reduce enormemente las entradas falsas. Que el trailing stop cambia completamente el perfil de riesgo/retorno respecto a un TP fijo. La diferencia entre operar en un mercado en tendencia (ADX > 25) y en uno lateral.

---

## Arquitectura del bot (`alalu_bot/`)

```
alalu_bot/
├── engine.py        Motor de trading — señales, entradas, salidas, estado
├── api.py           API FastAPI — expone los datos para el dashboard
└── dashboard/       Frontend React + Vite
    ├── src/
    │   ├── App.tsx                    Layout principal, polling cada 5s
    │   ├── components/
    │   │   ├── Navbar.tsx             Estado del motor, circuit breaker
    │   │   ├── MetricCard.tsx         Balances 1x / 5x / win rate
    │   │   ├── MarketTable.tsx        Tabla de indicadores en tiempo real
    │   │   └── PositionsPanel.tsx     Posiciones activas + historial
    │   ├── types.ts                   Interfaces TypeScript
    │   └── api.ts                     Fetch a /api/market y /api/portfolio
    ├── Dockerfile                     Build React + nginx
    └── nginx.conf                     Proxy /api → FastAPI
```

### Parámetros de la estrategia

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `ROC_PERIOD` | 20 | Períodos para Rate of Change |
| `ADX_THRESH` | 25 | Mínimo ADX para operar (mercado en tendencia) |
| `RSI_LONG_MIN/MAX` | 50–70 | Zona válida para longs |
| `RSI_SHORT_MIN/MAX` | 30–50 | Zona válida para shorts |
| `ROC_THRESH` | 0.5% | ROC mínimo para señal |
| `TRAILING_PCT` | 1.5% | Distancia del trailing stop desde el máximo |
| `MAX_TRADE_MINUTES` | 60 | Salida por tiempo si no cierra antes |
| `MAX_CONCURRENT_TRADES` | 2 | Límite por correlación entre cripto |
| `CIRCUIT_BREAKER_PCT` | 80% | Detener si balance 5x cae al 80% del inicial |

### Flujo de datos

```
engine.py → market_state.json ─┐
           → portfolio.json   ─┤→ api.py (:8000) → nginx (:80) → React
                                └─── volumen compartido Docker ───┘
```

---

## Deploy con Docker

Un solo comando levanta los tres servicios (motor + API + dashboard):

```bash
docker compose up --build
```

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| `engine` | — | Motor de trading (loop infinito) |
| `api` | 8000 (interno) | FastAPI, expone `/api/market` y `/api/portfolio` |
| `frontend` | **80** | Dashboard React servido por nginx |

Dashboard disponible en `http://localhost`

```bash
# Ver logs del motor en tiempo real
docker compose logs -f engine

# Detener todo
docker compose down

# Detener y borrar datos de simulación
docker compose down -v
```

---

## Desarrollo local (sin Docker)

```bash
# Instalar dependencias Python
uv sync

# Terminal 1 — motor
uv run python alalu_bot/engine.py

# Terminal 2 — API
uv run uvicorn api:app --port 8000 --app-dir alalu_bot

# Terminal 3 — frontend
cd alalu_bot/dashboard && npm install && npm run dev
```

Frontend en `http://localhost:5173`

---

## Stack

| Herramienta | Uso |
|---|---|
| `ccxt` | Datos OHLCV en tiempo real desde Binance |
| `pandas` | Manipulación de series temporales |
| `FastAPI` + `uvicorn` | API que expone el estado del bot |
| React + Vite + TypeScript | Dashboard profesional |
| Tailwind CSS | Estilos (paleta Binance dark) |
| nginx | Servidor estático + proxy inverso |
| Docker Compose | Orquestación de los 3 servicios |

---

## Estructura completa

```
alalu/
├── main.py                        Fase 1: backtest reversión a la media
├── grid_search.py                 Fase 2: optimización de parámetros
├── grid_search_with_volume.py     Fase 3: momentum + volumen + TP/SL
├── master.py                      Fase 4: scanner en tiempo real
├── master_x5.py                   Fase 5: simulación con leverage 5x
├── alalu_bot/                     Fase 6: bot quant + dashboard
│   ├── engine.py
│   ├── api.py
│   └── dashboard/
├── Dockerfile                     Imagen Python (engine + api)
├── docker-compose.yml
├── .dockerignore
└── real_time_forward_testing.csv  Log de señales del forward testing
```

---

## Conceptos clave

- **Z-Score**: distancia estadística del precio respecto a su media, en desviaciones estándar
- **EMA 200**: filtro de tendencia macro. Por encima = bullish, por debajo = bearish
- **ROC (Rate of Change)**: velocidad del movimiento de precio, señal primaria de momentum
- **RSI**: oscilador de fuerza relativa, usado como filtro de zona (no sobrecomprado/sobrevendido)
- **ADX / ±DI**: fuerza de la tendencia (ADX) y su dirección (+DI vs -DI)
- **ATR**: volatilidad real del mercado, usada para dimensionar stops dinámicos
- **Volume spike**: confirmación de que el movimiento tiene fuerza real detrás
- **Trailing stop**: stop que sigue al precio en dirección del trade; protege ganancias sin limitar el upside
- **Circuit breaker**: mecanismo de seguridad que detiene el trading ante drawdown severo
- **Backtest vectorizado vs. trade-by-trade**: diferencia en precisión y complejidad
- **Lookahead bias**: usar `shift(1)` para que la señal se ejecute en la vela siguiente
- **Forward testing**: observar la estrategia en tiempo real antes de arriesgar capital
- **Correlación entre activos**: BTC/ETH/SOL/BNB se mueven juntos — limitar trades simultáneos reduce el riesgo real

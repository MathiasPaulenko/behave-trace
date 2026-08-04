# behave-trace — Roadmap

> Objetivo: llevar behave-trace al nivel de **Playwright `--ui` mode**.
>
> Faltan tres piezas clave: ejecución interactiva desde la UI, resultados en
> tiempo real (SSE) y selección/re-run de tests individuales.

---

## Lo que falta respecto a Playwright `--ui`

| Feature | Playwright `--ui` | behave-trace actual |
| --- | --- | --- |
| Ejecutar tests desde la UI | ✅ | ❌ (solo post-mortem) |
| Resultados en tiempo real | ✅ (WebSocket) | ❌ (datos congelados) |
| Re-run solo fallos | ✅ | ❌ |
| Seleccionar tests a ejecutar | ✅ | ❌ |
| Source code real del step | ✅ | Placeholder |
| Search/filter por nombre | ✅ | ❌ (solo filtro all/failed/slow) |

---

## Fases pendientes

Cada fase es **acotada, reducida y verificable de forma independiente**.
Al final de cada fase el código compila, los tests pasan, y se puede hacer un commit aislado.

---

### Fase R1 — Endpoint `/api/source`

**Objetivo:** Mostrar el código fuente real del step en el tab Source.

**Contexto:** El frontend tiene el tab Source pero muestra un placeholder.
El `step.location` contiene `file:line` (ej. `steps/calculator.py:15`).

**Tareas:**

1. Añadir endpoint `GET /api/source?path=<path>&line=<line>&context=<n>` en `ViewerServer`.
2. El endpoint lee el archivo fuente (relativo al CWD donde se ejecutó behave) y devuelve:
   ```json
   {
     "path": "steps/calculator.py",
     "line": 15,
     "language": "python",
     "snippet": "def step_add(context):\n    context.result = ...",
     "total_lines": 42
   }
   ```
3. Devolver `context` líneas antes y después de la línea del step (default: 5).
4. Manejar errores: archivo no encontrado, permisos, path fuera del proyecto.
5. Actualizar `viewer.js` → `sourceCode()` para hacer `fetch('/api/source?...')` y mostrar el snippet.
6. Añadir syntax highlighting básico (opcional, con highlight.js desde CDN o clases CSS manuales).

**Archivos afectados:**

- `behave_trace/viewer/server.py` — nuevo endpoint
- `behave_trace/assets/js/viewer.js` — `sourceCode()` async
- `behave_trace/assets/css/viewer.css` — estilos para snippet de código
- `tests/test_server.py` — tests del nuevo endpoint

**Verificación:** `behave-trace show trace.json` → seleccionar step → tab Source muestra código real.

---

### Fase R3 — Search y filtros avanzados en el sidebar

**Objetivo:** Buscar scenarios por nombre y filtrar por tag.

**Contexto:** El sidebar actual solo tiene 3 filtros radio: All / Failed / Slow.
Playwright `--ui` tiene una caja de búsqueda que filtra el árbol de tests en tiempo real.

**Tareas:**

1. Añadir caja de búsqueda (`<input type="search">`) en el sidebar, arriba del árbol.
2. En `viewer.js`, añadir `searchQuery` al state y método `matchesSearch(scenario)`.
3. `filteredScenarios(feature)` filtra también por `searchQuery` (case-insensitive, match en nombre y tags).
4. Añadir filtro por tag: chips/dropdown con tags disponibles.
5. Añadir filtro por estado: passed/failed/skipped/undefined (checkboxes además de radio).
6. Resaltar el texto matcheado en el árbol (`<mark>`).

**Archivos afectados:**

- `behave_trace/assets/index.html` — search input, tag chips
- `behave_trace/assets/js/viewer.js` — `searchQuery`, `matchesSearch()`, `filteredScenarios()`
- `behave_trace/assets/css/viewer.css` — estilos search, chips, `<mark>`

**Verificación:** Escribir "login" en la búsqueda → el árbol muestra solo scenarios que contienen "login".

---

### Fase R6 — Resultados en tiempo real (SSE)

**Objetivo:** Mostrar el progreso de los tests mientras se ejecutan, sin esperar al final.

**Contexto:** Este es el feature más complejo y la **próxima prioridad**. Playwright `--ui`
usa WebSocket para streaming de eventos en vivo. Para behave-trace, el formatter captura
eventos secuencialmente — habría que retransmitirlos al viewer en tiempo real.

**Diseño:**

```text
behave (subprocess) → formatter → trace.json (streaming)
                                    ↓
ViewerServer ← SSE ← FileWatcher / tail del trace
    ↓
Frontend (Alpine.js) → actualiza UI en vivo
```

**Tareas:**

1. Añadir endpoint `GET /api/stream` (SSE) en `ViewerServer`.
   - SSE es más simple con stdlib (no requiere librerías extra).
   - El server hace "tail" del trace JSON a medida que behave lo escribe.
2. Modificar `TraceFormatter.close()` para escribir el trace incrementalmente
   (no solo al final). Opción A: escribir un evento por línea (JSONL temporal).
   Opción B: escribir el JSON completo pero el server hace polling del archivo.
3. En `viewer.js`, añadir `EventSource('/api/stream')` para recibir eventos:
   - `feature_start`, `scenario_start`, `step_result`, `scenario_end`, `feature_end`.
   - Actualizar el árbol y las stats en vivo.
4. Estado "running" en el frontend: spinner o indicador visual en scenarios en ejecución.
5. Auto-scroll al scenario que se está ejecutando.

**Archivos afectados:**

- `behave_trace/viewer/server.py` — endpoint SSE
- `behave_trace/formatter.py` — escritura incremental (opcional)
- `behave_trace/serializer.py` — serialización incremental (opcional)
- `behave_trace/assets/js/viewer.js` — `EventSource`, actualización en vivo
- `behave_trace/assets/index.html` — indicador "running"
- `behave_trace/assets/css/viewer.css` — estilos spinner/running

**Verificación:** `behave-trace run features/` → el árbol se va llenando a medida que behave ejecuta los tests.

---

### Fase R7 — Re-run de fallos desde la UI

**Objetivo:** Botón "Re-run failed" en el viewer que re-ejecuta solo los scenarios fallidos.

**Contexto:** Depende de Fase R6. Playwright `--ui` permite re-ejecutar tests
individuales o solo los fallidos con un botón. Para behave, se puede usar `--tags`
o `--name` para filtrar scenarios. `BehaveRunner.run_filtered()` ya existe.

**Tareas:**

1. Añadir endpoint `POST /api/rerun` en `ViewerServer` con body:
   ```json
   { "filter": "failed" | "all", "scenarios": ["Scenario name 1", "..."] }
   ```
2. El server delega a `BehaveRunner.run_filtered()` con el filtro apropiado.
3. En el frontend, añadir botón "Re-run failed" en el header.
4. Al hacer click: `fetch('/api/rerun', { method: 'POST', body: ... })`.
5. El server re-ejecuta behave y envía nuevos eventos via SSE (Fase R6).
6. El frontend reemplaza el trace actual con los nuevos resultados.

**Archivos afectados:**

- `behave_trace/viewer/server.py` — endpoint `POST /api/rerun`
- `behave_trace/runner.py` — `run_filtered()` (ya existe)
- `behave_trace/assets/js/viewer.js` — `rerunFailed()`
- `behave_trace/assets/index.html` — botón "Re-run failed"
- `behave_trace/assets/css/viewer.css` — estilos del botón

**Verificación:** Ejecutar tests → hay fallos → click "Re-run failed" → solo los fallidos se re-ejecutan.

---

### Fase R8 — Selección de tests desde la UI

**Objetivo:** Checkboxes en el árbol para seleccionar qué scenarios ejecutar.

**Contexto:** Depende de Fases R6 y R7. Playwright `--ui` permite marcar/desmarcar
tests individuales y ejecutar solo los seleccionados.

**Tareas:**

1. Añadir checkbox a cada scenario en el árbol del sidebar.
2. State `selectedScenarios: Set<string>` en `viewer.js`.
3. Botón "Run selected" en el header.
4. `POST /api/rerun` con la lista de scenarios seleccionados.
5. Persistir la selección entre re-ejecuciones (no se pierde al recargar el trace).
6. "Select all" / "Deselect all" / "Select failed" en el header del árbol.

**Archivos afectados:**

- `behave_trace/assets/index.html` — checkboxes en el árbol
- `behave_trace/assets/js/viewer.js` — `selectedScenarios`, `runSelected()`
- `behave_trace/assets/css/viewer.css` — estilos checkbox

**Verificación:** Marcar 2 scenarios → click "Run selected" → solo esos 2 se ejecutan.

---

### Fase R10 — Mejoras de UX del viewer

**Objetivo:** Pulir la experiencia visual para igualar Playwright `--ui`.

**Tareas:**

1. **Keyboard navigation** — flechas arriba/abajo para navegar steps, Enter para seleccionar.
2. **Step diff** — cuando se re-ejecuta un test, mostrar diff del resultado anterior vs nuevo.
3. **Copy step info** — botón para copiar el nombre/location del step al portapapeles.
4. **Export trace** — botón para descargar el trace JSON desde el viewer.
5. **Dark/light theme toggle** — el diseño actual es solo dark.
6. **Responsive layout** — el viewer actual no es responsive (sidebar fija 260px).
7. **Empty states mejorados** — mensajes más informativos cuando no hay screenshots, logs, etc.
8. **Tooltips** — en badges, durations, status icons.
9. **Loading state** — spinner mientras se carga el trace (traces grandes pueden tardar).

**Archivos afectados:**

- `behave_trace/assets/js/viewer.js` — keyboard handlers, copy, export
- `behave_trace/assets/index.html` — botones, toggle
- `behave_trace/assets/css/viewer.css` — light theme, responsive, tooltips

**Verificación:** Navegar con teclado, cambiar tema, exportar trace — todo funciona.

---

## Resumen de dependencias

```text
R1  (source endpoint)     ── independiente
R3  (search/filtros)      ── independiente
R6  (tiempo real SSE)     ── depende de R4 (completado)
R7  (re-run from UI)      ── depende de R6
R8  (test picking)        ── depende de R6, R7
R10 (UX improvements)     ── independiente
```

## Prioridad sugerida

1. **R6** — resultados en tiempo real (SSE). Es la feature clave para igualar `--ui`.
2. **R7, R8** — interactividad avanzada (re-run, test picking). Dependen de R6.
3. **R1, R3** — mejoras del viewer post-mortem, bajo riesgo, alto valor.
4. **R10** — pulido y features adicionales.

## Notas técnicas

- **SSE vs WebSocket**: SSE es más simple con stdlib (`http.server` puede manejarlo),
  no requiere dependencias extra. WebSocket necesitaría `websockets` o similar.
- **Escritura incremental del trace**: el formatter actual escribe todo en `close()`.
  Para tiempo real, habría que escribir eventos incrementalmente. Opción: JSONL
  temporal que el server lee con tail, y se convierte a JSON completo al final.
- **Backward compatibility**: el comando `show` debe seguir funcionando exactamente igual.
  `run` es un superconjunto — ejecuta behave + hace `show` automáticamente.

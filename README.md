# SincroLab

SincroLab es un laboratorio educativo y científico para comprender la
estabilidad transitoria de sistemas eléctricos de potencia mediante simulación,
evidencia reproducible e interpretación trazable. El core `v0.1.0-core` usa el
modelo clásico de una máquina conectada a una barra infinita (SMIB).

`0.1.0` es la versión del paquete Python; `v0.1.0-core` es el identificador del release/tag Git del core.

El alcance es deliberadamente acotado. SincroLab no representa una red
multimáquina general ni sustituye ETAP, PSS/E, PowerWorld, DIgSILENT o un
estudio operacional. La perturbación V0.1 se modela pedagógicamente mediante
cambios equivalentes de `Pmax`; no es un cálculo completo de cortocircuito,
protecciones o red.

## Capacidades del core

- Relación potencia–ángulo `Pe_pu = Pmax_pu * sin(delta_rad)` y equilibrio
  principal con validación explícita del dominio.
- Modelo clásico SMIB y swing equation para `delta_rad` y `omega_dev_pu`.
- Euler explícito y RK4 clásico implementados en el proyecto, con pruebas
  analíticas de convergencia.
- Simulación prefalla, falla y posfalla con estado continuo y eventos ubicados
  exactamente en los tiempos especificados.
- Trayectorias inmutables unidas a sus parámetros, estado inicial, red
  equivalente, horizonte y `dt_s`.
- Diagnóstico muestreado de primera oscilación con `STABLE`, `UNSTABLE` e
  `INDETERMINATE`, razones explícitas y brackets de muestras adyacentes.
- Equal Area Criterion para casos clásicos compatibles sin amortiguamiento y
  cálculo analítico del critical clearing angle.
- Evaluación temporal y búsqueda por bisección de una transición entre un
  endpoint `STABLE` y otro `UNSTABLE`.
- Cross-check independiente entre el critical clearing angle analítico y los
  ángulos de clearing de los endpoints temporales.
- Comparación del RK4 propio con `scipy.integrate.solve_ivp` como evidencia
  numérica externa exclusivamente en tests.
- Casos científicos de referencia con taxonomía explícita de evidencia.
- Explicaciones pedagógicas deterministas y tres casos guiados con predicción,
  intervención, pistas progresivas, una solución posible, comparación y
  debrief.
- API de aplicación portable, JSON estructurado, CSV de trayectorias y CLI
  textual sobre la misma ruta científica/pedagógica.

Los ángulos internos se expresan en radianes, el tiempo en segundos, las
potencias en per unit, `H` en segundos y la desviación de velocidad en pu
respecto de la velocidad síncrona eléctrica.

## Un core, varias interfaces

```text
CLI H26 / Desktop educativo H28 / Web H29 (Pyodide)
                    |
                    v
       sincrolab.application.portable
                    |
                    v
 scientific application / analysis / simulation / models / numerical
```

La fachada portable no contiene swing equation, integradores ni clasificación.
Convierte DTOs explícitos hacia los casos de uso existentes y transforma sus
resultados a tipos serializables. La CLI y el desktop H28 consumen esa fachada.
La web H29 ejecuta ese mismo contrato en Python dentro del navegador mediante Pyodide.

La API portable se publica desde `sincrolab.application` y se define en
`sincrolab.application.portable`. Sus operaciones principales son:

- `get_capabilities()`;
- `evaluate_transient(config)`;
- `list_guided_cases()`, `get_guided_case(...)`, `get_guided_hints(...)` y
  `get_guided_solution(...)`;
- `run_portable_guided_attempt(request)`;
- `list_reference_cases()`, `get_reference_case(...)` y
  `reproduce_reference_case(...)`;
- `dumps_portable(...)` y `trajectory_to_csv(...)`.

Los DTOs usan escalares, enums estables, tuplas y otros DTOs portables. JSON
convierte las series numéricas explícitamente a listas; no serializa `repr()`
de objetos Python ni arrays NumPy crudos. El round-trip versionado exige que
`schema_version` sea un entero JSON real y no acepta strings como números.

## Semántica del Critical Clearing Time

El resultado temporal H19 es un bracket:

```text
stable_t_clear_s < unstable_t_clear_s
```

El endpoint inferior fue evaluado como `STABLE` y el superior como `UNSTABLE`
por el diagnóstico muestreado H15. `time_tolerance_s` limita el ancho final de
la bisección; es un criterio de parada, no incertidumbre física, tolerancia del
integrador o barra de error del CCT. La salida portable no publica el midpoint
como CCT.

La posición del bracket depende del modelo, `dt_s`, horizonte y criterio
first-swing. El caso adversarial público muestra que una clasificación
muestreada puede cambiar cerca de la frontera al variar la resolución temporal;
ningún resultado aislado se presenta como verdad física continua.

## Instalación

Se requiere Python 3.11 o posterior y
[`uv`](https://docs.astral.sh/uv/).

Para instalar el entorno reproducible de desarrollo:

```bash
uv sync --locked --dev
```

NumPy es la única dependencia científica de runtime. Pytest y SciPy pertenecen
al grupo de desarrollo; SciPy no forma parte de la ruta del producto.

## Desktop educativo H28

H27 incorpora un shell desktop; H28 lo conecta a la API portable mediante un
único adaptador. Inicio y Casos guiados obtienen título, objetivo, dificultad y
opciones del catálogo H25/H26, sin mantener una segunda definición de los casos.

El recorrido ofrece observar, predecir, simular, intervenir, comparar y explicar.
Selecciona una predicción antes de ejecutar el baseline; después cambia únicamente
los parámetros permitidos y predice el nuevo intento. Las pistas se revelan en
orden. **Mostrar una solución** carga una posibilidad pedagógica y conserva su
explicación y limitación originales; exige otra predicción antes de simular.

La comparación conserva los resultados y cambios estructurados del workflow,
con gráficas de las muestras de `delta_rad` y `omega_dev_pu`. Los estados
`STABLE`, `UNSTABLE` e `INDETERMINATE` y sus razones proceden del núcleo;
las mayúsculas del indicador son solo formato visual. Las explicaciones H24
y el bracket H19 se muestran sin reinterpretación. El texto científico conserva
el idioma original del núcleo.

La autoevaluación pre/post es opcional. Sin respuestas completas no se asigna
puntuación. Como H26 recibe ambos conjuntos juntos, el desktop conserva las
respuestas pre antes de simular y repite exactamente la solicitud al recibir
el post; H25 calcula el score y se sustituye el registro de ese intento.
El historial vive solo en memoria: volver al catálogo permite retomar el caso
activo; seleccionar otro caso o cerrar descarta esa sesión. No hay telemetría,
archivos de progreso, identificadores personales ni marcas de tiempo.

Modo libre usa `evaluate_transient` con `H_s`, `t_clear_s`, `t_end_s` y
`dt_s` explícitos. Parte del primer caso público del catálogo y muestra los
demás parámetros retenidos, incluida la condición inicial. La validación
científica permanece en portable. La ejecución ocurre fuera del hilo Qt;
una operación activa debe finalizar antes de cerrar la ventana.

H26 expone trayectorias de ángulo y velocidad; esta vista no reconstruye
`Pe/Pm` ni añade un cálculo Equal Area. No ofrece un editor general de modelos.

PySide6 es una dependencia opcional del extra `desktop`; la instalación base y
la CLI conservan NumPy como único requisito de runtime. Para instalar y lanzar
desde este repositorio:

```bash
uv sync --locked --extra desktop
uv run --extra desktop python -m sincrolab.interfaces.desktop
```

Para un paquete ya instalado, se puede instalar `sincrolab[desktop]` y lanzar
`python -m sincrolab.interfaces.desktop`. Si falta PySide6, el lanzador devuelve
código 2 con instrucciones de instalación; importar `sincrolab` o usar la CLI
no carga Qt. El extra usa la API Qt 6 (`>=6,<7`) y `uv.lock` conserva las versiones
resueltas. Las pantallas no realizan llamadas de red ni guardan datos.

Para ejecutar las pruebas desktop (Qt offscreen, sin escritorio visible):

```bash
uv run --extra desktop pytest -q tests/test_desktop.py tests/test_desktop_boundary.py tests/test_desktop_learning.py tests/test_desktop_workflow.py
```

Las pruebas de Qt se omiten cuando el extra no está instalado; los checks de
packaging, metadatos e independencia del core se ejecutan también sin Qt.

## Web estática H29 · Python en el navegador

La web educativa ejecuta el wheel normal de SincroLab en **Pyodide 0.27.7**,
con NumPy 2.0.2 proporcionado por esa distribución. JavaScript presenta los
datos; el bridge `interfaces/web/bridge.py` delega en `application.portable`.
No existe backend científico. Un worker mantiene la interfaz disponible
durante los cálculos y permite una sola operación simultánea.

Desde la raíz del checkout (o del sdist extraído), prepara y sirve el sitio:

```bash
uv lock --check
uv build --out-dir dist/h29
uv run python web/assemble.py --wheel dist/h29/sincrolab-0.1.0-py3-none-any.whl --output dist/h29-site
uv run python -m http.server 8765 --bind 127.0.0.1 --directory dist/h29-site
```

Abre **http://127.0.0.1:8765/**. No uses `file://`. El ensamblador copia solo
los assets explícitos, el wheel y un manifest con hashes; comprueba que los
fuentes Python del wheel corresponden byte por byte al checkout. Puede
repetirse sobre su mismo output sin limpieza. Rechaza directorios con archivos
ajenos; en ese caso elige otro directorio vacío. Los outputs `dist/` no se
versionan. Para detener el servidor, pulsa **Ctrl+C** en su terminal.

Los assets y `assemble.py` forman parte del sdist mediante una lista explícita.
El wheel incluye el bridge Python; los assets web se ensamblan desde el
checkout o sdist y no se incluyen en el wheel.

### Verificar una ejecución

1. Espera a **Entorno listo**; la carga distingue Pyodide de la instalación del
   wheel. El catálogo procede de Python y no contiene soluciones anticipadas.
2. Abre **Controlled effect of inertia**, pulsa **Registrar mi predicción**,
   elige una opción y pulsa **Simular con esta predicción**.
3. En **Intervenir**, introduce `H_s=6`, pulsa **Predecir este nuevo intento**,
   selecciona `smaller excursion` y vuelve a simular.
4. **Comparar** conserva el baseline, el intento, sus cambios y ambas series.
   **Explicar** muestra el debrief, evidencia y limitaciones H24/H25. Las
   preguntas de cierre son para reflexión; la web no realiza pre/post ni
   asigna puntuaciones. El DTO conserva assessment ausente como `None`.
5. **Pista 1**, **Pista 2** y **Mostrar una solución** solicitan el contenido a
   Python solo al pulsarlos. La solución es una posibilidad pedagógica y exige
   otra predicción antes de ejecutarse.
6. En **Modo libre**, usa `H_s=3.5`, `t_clear_s=0.2`, `t_end_s=5`,
   `dt_s=0.005` y pulsa **Simular** para un resultado `STABLE`. Cambia
   `t_clear_s=0.35` para `UNSTABLE`. Para preservar un `INDETERMINATE` real,
   usa `t_clear_s=0.2` y `t_end_s=0.21`, manteniendo los otros dos valores.
7. **Descargar resultado JSON** conserva datos canónicos y trayectorias
   completas. **Información del entorno de cálculo** muestra versión de
   paquete, capacidades portable, wheel y SHA-256 comprobado en el navegador.
8. Abre la consola de desarrollo (**F12 → Console** en Chrome) y comprueba
   que no aparecen errores durante el flujo válido. Un input inválido muestra
   un error de entrada, conserva la última ejecución y nunca asigna un status
   científico al fallo.

La prueba automatizada usa Chrome ya instalado y Playwright temporal, sin
incorporarlo a las dependencias del proyecto ni descargar navegadores:

```bash
uv run pytest -q -o addopts= tests/test_web_bridge.py tests/test_web_parity.py tests/test_web_assets.py
uv run --with playwright==1.58.0 python tests/web_browser_check.py --url http://127.0.0.1:8765 --output .audit
```

El segundo comando requiere que siga activo el servidor HTTP. Genera capturas
reales y `H29_BROWSER.json` bajo `.audit/`, que debe excluirse localmente en
`.git/info/exclude`. Compara payloads, estados, configuraciones, brackets,
explicaciones y series con portable nativo. Los floats usan `atol=1e-12` y
`rtol=1e-11` para diferencias entre plataformas; no son incertidumbres físicas.
CLI y Desktop se contrastan además en la suite nativa. La CLI H26 no expone
evaluación libre arbitraria: su paridad usa guided y referencias soportadas.

### Red y límites de la web

La primera carga descarga Pyodide, su biblioteca estándar, NumPy, micropip y
packaging desde la base exacta
`https://cdn.jsdelivr.net/pyodide/v0.27.7/full/`; consulta la
[documentación oficial de Pyodide 0.27.7](https://pyodide.org/en/0.27.7/usage/quickstart.html).
El wheel y los assets se descargan del servidor estático local. No se envían
predicciones, inputs ni resultados; no hay trackers, cuentas o persistencia.
El historial se conserva solo para el caso activo en memoria y se descarta al
cambiar de caso o recargar. La web depende del CDN y **no se declara offline**.

Verificada en Chrome 152 sobre Windows, con anchos 1280, 820 y 390 px; no
implica compatibilidad universal ni soporte móvil exhaustivo. Se necesita
WebAssembly, módulos y workers. No se implementa cancelación de un cálculo;
recargar descarta la sesión. Los textos científicos H24/H25 conservan inglés.
Las gráficas muestran `delta_rad` y `omega_dev_pu` ya calculados; portable no
expone series Pe/Pm ni una operación Equal Area para esta superficie. Un
bracket CCT estrecho no prueba convergencia temporal; se preservan por separado
`dt_s` y el significado de `time_tolerance_s` como criterio de parada H19.

## API portable: ejemplo mínimo

```python
from sincrolab.application import (
    GuidedAttemptRequest,
    ParameterValueDTO,
    get_guided_case,
    run_portable_guided_attempt,
)

guided_case = get_guided_case("controlled-inertia-effect")
request = GuidedAttemptRequest(
    case_id=guided_case.case_id,
    prediction="smaller excursion",
    changes=(ParameterValueDTO(key="H_s", value=6.0),),
)
result = run_portable_guided_attempt(request)

print(result.attempted_evaluation.first_swing.status)
print(result.debrief_summary)
```

La predicción se valida antes de ejecutar H25. Sin respuestas pre/post, el
resultado indica `assessed=False`; no convierte la ausencia en `0/N`.

Una simulación portable directa usa el mismo H18/H15:

```python
from sincrolab.application import evaluate_transient, get_guided_case

config = get_guided_case("first-swing-event-evidence").baseline_config
evaluation = evaluate_transient(config)
print(evaluation.first_swing.status, evaluation.first_swing.reason)
```

## CLI

El entry point `sincrolab` usa únicamente la fachada portable:

```bash
uv run sincrolab --help
uv run sincrolab capabilities
uv run sincrolab guided list
uv run sincrolab guided show controlled-inertia-effect
uv run sincrolab guided hints late-clearing-bracket --count 1
uv run sincrolab guided run controlled-inertia-effect --prediction "smaller excursion" --set H_s=6.0
uv run sincrolab reference list
uv run sincrolab reference show stable_transient
uv run sincrolab reference run stable_transient
```

Los comandos aceptan `--json`. Los comandos `guided run` y `reference run`
también permiten `--json-output PATH` y `--csv-output PATH`; CSV contiene solo
las columnas tabulares `time_s,delta_rad,omega_dev_pu` en orden determinista.

La autoevaluación opcional usa pares completos de `--pre-answer
QUESTION=OPTION` y `--post-answer QUESTION=OPTION`. No se realiza NLP ni se
puntúa texto libre.

## Referencias científicas

`reference_cases/smib_v0_1_golden_cases.json` conserva cinco casos con una
taxonomía que distingue:

- `ANALYTIC_ORACLE`;
- `EXTERNAL_NUMERICAL_ORACLE`;
- `CROSS_CHECKED_EVIDENCE`;
- `ACCEPTED_REGRESSION`.

La fuente canónica permanece en
`reference_cases/smib_v0_1_golden_cases.json` y en sus inputs públicos. Para
que un wheel instalado no dependa del layout del repositorio, H26 incluye una
proyección empaquetada completa; una prueba de igualdad exhaustiva impide que
sus IDs, inputs, claims, tolerancias, evidence types, provenance o limitaciones
deriven silenciosamente de H23.

La API/CLI consulta los cinco casos. Stable y unstable verifican todas las
observaciones canónicas reportadas para la ejecución, no solo status/reason;
cada resultado conserva expected/observed, comparison, tolerancia, evidence
type y provenance. El campo `all_reported_observations_match_expected` resume
únicamente esos claims enumerados. El adversarial verifica una clasificación
canónica para un `dt_s` explícito. Equal Area y SciPy permanecen query-only;
`solve_ivp` sigue siendo test-only. `evidence_types_present` es solo el conjunto
de tipos encontrados en los claims del caso, no evidencia aplicable a todos.

## Arquitectura

```text
src/sincrolab/
  models/          física, parámetros y tipos de dominio
  numerical/       Euler, RK4 y utilidades genéricas
  simulation/      trayectorias, configuración y procedencia neutrales
  analysis/        first-swing, Equal Area y critical clearing angle
  application/     orquestación, aprendizaje y fachada portable
  interfaces/cli/  adaptación textual; sin solver ni clasificador propios
  interfaces/desktop/  Qt opcional; vistas, controlador y adaptador portable
  interfaces/web/      bridge JSON a portable; sin ciencia propia
web/                HTML/CSS/JS, worker Pyodide y ensamblado estático
tests/              validación analítica, física, numérica y de contratos
reference_cases/    inputs sintéticos y evidencia golden reproducible
```

El core/application no depende de Qt, PySide6, DOM, frameworks web,
networking o telemetría. Tampoco envía predicciones, intentos o progreso a
servicios externos.

## Pruebas

```bash
uv run pytest -q
uv lock --check
```

La suite cubre ecuaciones, integradores, convergencia, eventos exactos,
first-swing, Equal Area, ángulo crítico, bracket temporal, cross-checks,
sensibilidad a `dt_s`, evidencia golden, explicaciones, casos guiados, API
portable, CLI, serialización y ausencia de dependencias UI/runtime no
permitidas.

## Limitaciones

- El modelo es SMIB clásico; no representa dinámica multimáquina, AVR,
  governors, PSS o modelos síncronos de orden alto.
- La perturbación usa `Pmax` equivalente y no modela un cortocircuito general,
  Ybus, relés o protecciones completas.
- El diagnóstico first-swing clasifica una trayectoria muestreada y no
  demuestra estabilidad global, asintótica ni de oscilaciones posteriores.
- Equal Area y el critical clearing angle requieren las hipótesis documentadas,
  incluido `D_pu == 0` en la formulación actual.
- El bracket temporal no es un CCT exacto y no establece convergencia respecto
  de `dt_s` por sí solo.
- Los casos y soluciones guiadas son educativos y sintéticos; no son
  recomendaciones operacionales para una red real.
- Desktop H28 y Web H29 consumen el core existente a través de portable;
  H29 no constituye el release final del producto H30.

## Licencia y citación

SincroLab se distribuye bajo la [licencia MIT](LICENSE). La metadata de citación
está disponible en [`CITATION.cff`](CITATION.cff).

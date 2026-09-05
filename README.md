# SincroLab

SincroLab es un laboratorio educativo y científico para comprender la
estabilidad transitoria de sistemas eléctricos de potencia mediante simulación,
evidencia reproducible e interpretación trazable. El core `v0.1.0-core` usa el
modelo clásico de una máquina conectada a una barra infinita (SMIB).

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
CLI H26 / Desktop H27-H28 / Web H29
                    |
                    v
       sincrolab.application.portable
                    |
                    v
 scientific application / analysis / simulation / models / numerical
```

La fachada portable no contiene swing equation, integradores ni clasificación.
Convierte DTOs explícitos hacia los casos de uso existentes y transforma sus
resultados a tipos serializables. La CLI consume esa fachada; las interfaces
desktop y web previstas usarán el mismo contrato.

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
- H26 prepara el core y la CLI; no incluye todavía GUI desktop ni web.

## Licencia y citación

SincroLab se distribuye bajo la [licencia MIT](LICENSE). La metadata de citación
está disponible en [`CITATION.cff`](CITATION.cff).

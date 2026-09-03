# SincroLab

SincroLab es un laboratorio educativo y científico para comprender la
estabilidad transitoria de sistemas eléctricos de potencia. Su núcleo actual
usa el modelo clásico de una máquina conectada a una barra infinita (SMIB) para
relacionar física, integración numérica y evidencia reproducible.

El alcance es deliberadamente acotado: no representa una red multimáquina
general ni sustituye ETAP, PSS/E, PowerWorld, DIgSILENT o un estudio
operacional. En V0.1, la falla se modela pedagógicamente mediante cambios
equivalentes de la capacidad de transferencia `Pmax`, no mediante un cálculo
completo de cortocircuito o de red.

## Capacidades actuales

- Relación potencia–ángulo `Pe_pu = Pmax_pu * sin(delta_rad)` y equilibrio
  principal con validación explícita del dominio.
- Modelo clásico SMIB y swing equation para `delta_rad` y `omega_dev_pu`.
- Euler explícito y RK4 clásico implementados dentro del proyecto, con pruebas
  analíticas de convergencia y una malla temporal robusta.
- Simulación prefalla, falla y posfalla con `Pmax` equivalentes, estado continuo
  y eventos ubicados exactamente en los tiempos especificados.
- Trayectorias inmutables unidas a su configuración y procedencia para impedir
  que se analicen accidentalmente con parámetros de otra ejecución.
- Diagnóstico muestreado de primera oscilación con estados `STABLE`,
  `UNSTABLE` e `INDETERMINATE` y brackets de la evidencia observada.
- Equal Area Criterion clásico para casos compatibles sin amortiguamiento, y
  cálculo analítico del critical clearing angle.
- Evaluación de un clearing time concreto y búsqueda numérica del Critical
  Clearing Time (CCT) mediante bisección de un bracket temporal
  `STABLE -> UNSTABLE`.
- Cross-check independiente entre el critical clearing angle analítico y los
  ángulos de clearing de los endpoints temporales finales.
- Comparación numérica del RK4 propio con `scipy.integrate.solve_ivp` como
  referencia independiente en tests.

Los ángulos internos se expresan en radianes, el tiempo en segundos y las
potencias en per unit. La desviación de velocidad se define respecto de la
velocidad síncrona eléctrica.

## Semántica del CCT

El resultado científico principal de la búsqueda temporal es un endpoint
estable, un endpoint inestable y el ancho del bracket que los separa. El
midpoint (`cct_estimate_s`) es solo una estimación dentro de ese intervalo; no
es un “CCT exacto”.

`time_tolerance_s` limita el ancho máximo aceptado del bracket final. No es una
cota universal del error físico, una tolerancia del integrador ni evidencia de
convergencia respecto de `dt_s`.

## Solver educativo y referencia SciPy

El solver educativo principal es el RK4 clásico propio de SincroLab. SciPy
`solve_ivp` se usa exclusivamente en tests como referencia numérica
independiente: no sustituye RK4, no forma parte de la ruta principal de
simulación y no es una dependencia requerida en runtime. La referencia
transitoria también separa prefalla, falla y posfalla, y transporta estados de
SciPy a SciPy entre segmentos.

## Arquitectura

```text
src/sincrolab/
  models/          física, parámetros y tipos de dominio
  numerical/       Euler, RK4 y utilidades genéricas
  simulation/      trayectorias, configuración y procedencia neutrales
  analysis/        first-swing, Equal Area, critical clearing angle
                    y análisis científico derivado
  application/     simulación, evaluación temporal, búsqueda CCT y
                    cross-checks/orquestación
tests/              validación analítica, física, numérica y de regresión
reference_cases/    casos sintéticos reproducibles
examples/           ejemplos previstos
web/                interfaz web prevista
```

La física y los criterios científicos no pertenecen a las interfaces. En
particular, la búsqueda temporal del CCT es un caso de uso de `application/`;
el critical clearing angle analítico pertenece a `analysis/`; y
`simulation/` conserva contratos neutrales, sin convertirse en otra capa de
orquestación.

## Instalación para desarrollo

Se requiere Python 3.11 o posterior y
[`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --locked --dev
```

La dependencia de runtime es NumPy. El grupo de desarrollo/pruebas incorpora
pytest y SciPy.

## Uso básico

```python
from sincrolab.analysis import assess_smib_first_swing
from sincrolab.application import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)

parameters = SMIBParameters(
    H_s=3.5,
    D_pu=0.2,
    f_base_hz=60.0,
    Pm_pu=0.7,
)
network = SMIBTransientNetwork(
    Pmax_prefault_pu=1.2,
    Pmax_fault_pu=0.2,
    Pmax_postfault_pu=1.1,
    t_fault_s=0.1,
    t_clear_s=0.2,
)
initial_state = SMIBInitialState(
    delta_rad=initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=network.Pmax_prefault_pu,
    ),
    omega_dev_pu=0.0,
)

result = simulate_smib_transient(
    parameters,
    initial_state,
    network,
    t_start_s=0.0,
    t_end_s=5.0,
    dt_s=0.005,
)
assessment = assess_smib_first_swing(result)
print(assessment.status.value, assessment.reason.value)
```

## Pruebas

```bash
uv run pytest -q
```

La suite cubre relaciones físicas, contratos de los integradores, convergencia,
eventos exactos, casos de referencia, first-swing, Equal Area, critical
clearing angle, evaluación/búsqueda temporal, cross-checks y comparación con
SciPy. El mismo comando se ejecuta en GitHub Actions.

## Limitaciones actuales

- El modelo es el SMIB clásico; no representa dinámica multimáquina ni modelos
  síncronos de orden alto.
- La falla es un equivalente mediante `Pmax`, no un cortocircuito general.
- El diagnóstico first-swing no demuestra estabilidad global, asintótica ni de
  oscilaciones posteriores.
- Equal Area y el critical clearing angle requieren hipótesis específicas,
  entre ellas `D_pu == 0` en la formulación actual.
- El CCT temporal depende del modelo, la configuración, `dt_s`, el horizonte y
  el criterio first-swing. La sensibilidad sistemática a `dt_s` corresponde al
  siguiente hito y aún no está caracterizada.
- CLI, desktop y web todavía no están terminados.

## Metodología de desarrollo con IA

Herramientas de IA asisten en implementación, refactorización y pruebas. El
autor define y revisa los modelos, las hipótesis y los criterios, y audita de
forma consciente la corrección matemática, física y numérica del proyecto.

## Licencia

SincroLab se distribuye bajo la [licencia MIT](LICENSE).

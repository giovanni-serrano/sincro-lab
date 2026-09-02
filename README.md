# SincroLab

SincroLab es un laboratorio educativo, abierto y ligero para estudiar la
estabilidad transitoria de sistemas eléctricos de potencia. Conecta relaciones
físicas, integración numérica y evidencia reproducible mediante el modelo
clásico de una máquina conectada a una barra infinita (SMIB).

El proyecto está en desarrollo hacia la versión 0.1. El núcleo actual es
funcional y está cubierto por pruebas; todavía no incluye CLI ni interfaces
desktop o web.

## Capacidades actuales

- Relación potencia–ángulo `Pe_pu = Pmax_pu * sin(delta_rad)`.
- Equilibrio principal `asin(Pm_pu / Pmax_prefault_pu)` con validación de
  dominio.
- Modelo clásico SMIB y swing equation para `delta_rad` y `omega_dev_pu`.
- Euler explícito y RK4 clásico implementados en el proyecto, con pruebas
  analíticas y evidencia de sus órdenes de convergencia.
- Malla temporal determinista con paso final acortado cuando corresponde.
- Simulación RK4 de la secuencia prefalla, falla y posfalla mediante tres
  capacidades `Pmax` equivalentes y fronteras de evento exactas.
- Casos sintéticos reproducibles estable, cercano al límite, inestable y
  adversarial frente a resolución temporal.
- Diagnóstico muestreado de primera oscilación con resultados `STABLE`,
  `UNSTABLE` o `INDETERMINATE` y brackets de la evidencia observada.

Los ángulos internos se expresan en radianes, el tiempo en segundos y las
potencias en per unit. La desviación de velocidad es relativa a la velocidad
síncrona eléctrica. Los integradores numéricos son independientes del dominio
eléctrico.

## Instalación para desarrollo

Se requiere Python 3.11 o posterior y [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --locked --dev
```

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

El resultado transitorio conserva de forma inmutable la trayectoria y la
configuración que la produjo. El análisis consume ese único resultado para no
combinar accidentalmente una trayectoria con otros parámetros o red.

## Pruebas

```bash
uv run pytest
```

La suite verifica relaciones físicas conocidas, contratos de entrada/salida,
Euler y RK4 frente a soluciones analíticas, convergencia, continuidad y
fronteras de eventos, casos de referencia y diagnóstico de primera oscilación.
El mismo comando se ejecuta en GitHub Actions.

## Estructura

```text
src/sincrolab/
  models/          relaciones físicas y tipos de dominio
  numerical/       Euler, RK4 y malla temporal independientes del dominio
  simulation/      resultados y procedencia neutrales
  application/     orquestación de simulaciones SMIB
  analysis/        diagnóstico muestreado de primera oscilación
tests/              pruebas unitarias, analíticas y de regresión
reference_cases/    casos sintéticos reproducibles
examples/           ejemplos reproducibles previstos
web/                interfaz web prevista
```

## Alcance y limitaciones

SincroLab implementa un SMIB clásico educativo. La falla se representa mediante
un cambio por tramos de `Pmax`; no es un cálculo general de cortocircuito ni un
modelo de una red real. El diagnóstico actual clasifica la primera excursión a
partir de muestras discretas: no demuestra estabilidad global o asintótica y
puede depender de `dt_s` cerca de la frontera.

Todavía no se implementan criterio de áreas iguales, ángulo crítico, CCT,
comparación con SciPy, exportación, CLI ni interfaces de usuario. SincroLab no
sustituye estudios operacionales ni herramientas comerciales.

## Metodología de desarrollo

SincroLab utiliza herramientas de IA como apoyo en implementación,
refactorización y pruebas. Las decisiones sobre modelos, supuestos y criterios
científicos, así como la revisión de la corrección matemática, física y
numérica del núcleo, forman parte del proceso de revisión del autor.

## Licencia

SincroLab se distribuye bajo la [licencia MIT](LICENSE).

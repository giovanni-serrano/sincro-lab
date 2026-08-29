# SincroLab

SincroLab es un laboratorio educativo, abierto y ligero para estudiar la
estabilidad transitoria de sistemas eléctricos de potencia. El proyecto busca
conectar las ecuaciones, los métodos numéricos y la interpretación física en
experimentos reproducibles.

El desarrollo se encuentra en una etapa temprana de la versión 0.1. El código
actual proporciona fundamentos físicos y numéricos verificables; todavía no
implementa una simulación transitoria completa de una máquina síncrona conectada
a barra infinita (Single Machine Infinite Bus, SMIB) ni interfaces de usuario.

## Capacidades actuales

- Relación potencia-ángulo clásica `Pe_pu = Pmax_pu * sin(delta_rad)`.
- Cálculo del ángulo de equilibrio prefalla mediante
  `asin(Pm_pu / Pmax_prefault_pu)`, con validación explícita del dominio.
- Integrador Euler explícito genérico para estados escalares y vectores NumPy.
- Malla temporal determinista que alcanza exactamente el final del intervalo,
  incluso cuando el último paso debe acortarse.
- Pruebas de valores conocidos, entradas inválidas, sistemas escalares y
  vectoriales, y disminución del error de Euler al reducir el paso.

Los ángulos usados por el núcleo físico se expresan en radianes y las potencias
en per unit (pu). El integrador numérico es independiente del dominio eléctrico.

## Instalación para desarrollo

Se requiere Python 3.11 o posterior y
[`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --locked --dev
```

## Uso básico

```python
from sincrolab.models import electrical_power_pu, initial_equilibrium_angle_rad
from sincrolab.numerical import explicit_euler

delta0_rad = initial_equilibrium_angle_rad(
    Pm_pu=0.8,
    Pmax_prefault_pu=1.6,
)
Pe_pu = electrical_power_pu(delta_rad=delta0_rad, Pmax_pu=1.6)

times_s, states = explicit_euler(
    lambda _time_s, state: state,
    y0=1.0,
    t_start=0.0,
    t_end=1.0,
    dt=0.1,
)
```

## Pruebas

```bash
uv run pytest
```

La suite compara las implementaciones con valores analíticos conocidos y
verifica sus contratos de entrada y salida. El mismo comando se ejecuta en
GitHub Actions.

## Estructura

```text
src/sincrolab/
  models/          relaciones físicas implementadas
  numerical/       métodos numéricos independientes del dominio
tests/              pruebas unitarias y numéricas
examples/           ejemplos reproducibles previstos
reference_cases/    casos de referencia previstos
web/                interfaz web prevista
```

## Alcance y limitaciones

SincroLab es software educativo en desarrollo. El estado actual no incluye la
ecuación de oscilación completa, secuencias prefalla/falla/posfalla, análisis de
estabilidad, interfaz gráfica ni aplicación web. Tampoco modela una red eléctrica
real ni sustituye estudios operacionales o herramientas comerciales.

## Estado y próximos pasos

La relación potencia-ángulo, el equilibrio inicial y Euler explícito están
implementados y cubiertos por pruebas. Las siguientes etapas incorporarán RK4,
el modelo dinámico SMIB, eventos de perturbación, análisis de estabilidad,
validación independiente e interfaces educativas.

## Licencia

SincroLab se distribuye bajo la [licencia MIT](LICENSE).

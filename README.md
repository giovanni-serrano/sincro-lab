# SincroLab

**Estabilidad transitoria: de la ecuación al experimento.**

Laboratorio educativo de sistemas eléctricos de potencia que conecta simulación,
visualización e interpretación física con el modelo clásico **SMIB**: una máquina
síncrona conectada a una barra infinita. Un único núcleo Python alimenta la web,
el escritorio y la línea de comandos.

[**Presentación del proyecto**](https://giovanni-serrano.github.io/sincro-lab/presentation.html) ·
[**Abrir el laboratorio**](https://giovanni-serrano.github.io/sincro-lab/) ·
[Guía técnica](docs/TECHNICAL_GUIDE.md) · [Licencia MIT](LICENSE)

## Qué puedes explorar

- **Observar y predecir:** comprender el ángulo del rotor y anticipar su respuesta
  antes de conocer el resultado.
- **Simular e interpretar:** seguir la primera oscilación, el balance de potencia
  y las etapas prefalla, falla y posfalla.
- **Intervenir y comparar:** cambiar parámetros permitidos, conservar el intento
  inicial y explicar qué cambió a partir de evidencia calculada.
- **Aprender con apoyo:** casos guiados, pistas progresivas y una solución
  pedagógica posible disponible a petición del estudiante.

La web incluye una experiencia de experimentación sobre el tiempo de despeje,
material de fundamentos y un modo libre. El cálculo ocurre en Python dentro del
navegador mediante **Pyodide 0.27.7**. No existe backend científico.
Los intentos y predicciones permanecen en memoria durante la sesión; no hay
cuentas, telemetría ni envío de resultados a terceros. La primera carga requiere
Internet para descargar el entorno de ejecución.

## Ingeniería y evidencia

| Aspecto | Implementación |
| --- | --- |
| Física | Relación potencia–ángulo y swing equation con unidades explícitas |
| Métodos numéricos | Euler y RK4 propios; eventos de falla y despeje en su instante especificado |
| Análisis | Primera oscilación, Equal Area y ángulo crítico bajo hipótesis compatibles |
| Tiempo crítico de despeje | Búsqueda acotada y bisección con extremos evaluados |
| Verificación independiente | Comparación con `scipy.integrate.solve_ivp` en tests |
| Reproducibilidad | Casos sintéticos de referencia, convergencia y sensibilidad al paso temporal |
| Diseño | API de aplicación portable; interfaces sin duplicar ecuaciones ni criterios |
| Calidad | Pruebas automatizadas y CI en GitHub Actions |

SciPy es una referencia de desarrollo; el solver del producto usa RK4 propio.
NumPy es la única dependencia científica del core. PySide6 es opcional.

## Ejecutar el proyecto

Requisitos: **Python ≥ 3.11** y [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/giovanni-serrano/sincro-lab.git
cd sincro-lab
git switch develop/v0.1-product
uv sync --locked --dev
uv run sincrolab reference run stable_transient
```

Para explorar el catálogo y un intento guiado:

```bash
uv run sincrolab guided list
uv run sincrolab guided run controlled-inertia-effect --prediction "smaller excursion" --set H_s=6.0
```

### Escritorio

```bash
uv sync --locked --dev --extra desktop
uv run --extra desktop python -m sincrolab.interfaces.desktop
```

El escritorio ofrece casos guiados, predicción, comparación de intentos y modo
libre. H27 incorpora un shell desktop; las revisiones posteriores conectan la
experiencia al mismo contrato científico y pedagógico del core.

### Web estática H29 y experiencia actual

Para servir localmente el mismo paquete que utiliza la web pública:

```bash
uv build --out-dir dist/web
uv run python web/assemble.py --wheel dist/web/sincrolab-0.1.0-py3-none-any.whl --output dist/site
uv run python -m http.server 8765 --bind 127.0.0.1 --directory dist/site
```

Abre `http://127.0.0.1:8765/presentation.html` para la presentación o
`http://127.0.0.1:8765/` para el laboratorio. Se necesita HTTP; abrir el HTML
como archivo no carga el simulador. El ensamblador verifica que el wheel
corresponda a los fuentes del checkout y registra sus hashes.

## Arquitectura

```text
Web · Pyodide          Desktop · PySide6          CLI
      \                       |                 /
                 API de aplicación portable
                            |
           Simulación y aprendizaje compartidos
                            |
        Modelos · Métodos numéricos · Análisis
```

| Directorio | Responsabilidad |
| --- | --- |
| [`models`](src/sincrolab/models/) | Ecuaciones, parámetros y tipos físicos |
| [`numerical`](src/sincrolab/numerical/) | Integradores genéricos |
| [`simulation`](src/sincrolab/simulation/) | Trayectorias y procedencia de la ejecución |
| [`analysis`](src/sincrolab/analysis/) | Diagnósticos y análisis derivados |
| [`application`](src/sincrolab/application/) | Casos de uso, aprendizaje y contrato portable |
| [`interfaces`](src/sincrolab/interfaces/) y [`web`](web/) | Presentación y adaptación de datos |
| [`reference_cases`](reference_cases/) y [`tests`](tests/) | Evidencia reproducible y regresiones |

El núcleo devuelve datos y explicaciones deterministas; no depende de widgets
Qt ni del DOM. Las interfaces ejecutan el mismo modelo y conservan la
configuración asociada a cada trayectoria.

## Alcance científico

Los ángulos internos están en radianes; el tiempo y `H`, en segundos; las
potencias y la desviación de velocidad, en per unit.

El diagnóstico devuelve `STABLE`, `UNSTABLE` o `INDETERMINATE` según la evidencia
muestreada de **primera oscilación**. No demuestra estabilidad global,
asintótica ni de oscilaciones posteriores.

La salida temporal conserva un intervalo:

```text
stable_t_clear_s < unstable_t_clear_s
```

`time_tolerance_s` limita el ancho final de la bisección; no es una incertidumbre
física ni un error del integrador. El resultado depende del modelo, `dt_s`,
horizonte y criterio de diagnóstico. Equal Area requiere las hipótesis
documentadas, incluido amortiguamiento nulo en la formulación actual.

La falla se representa mediante cambios de `Pmax` equivalente: **no es un cálculo completo de cortocircuito**.
No se incluyen dinámica multimáquina, AVR, governor, PSS ni protección general.
SincroLab es educativo y no sustituye un estudio operacional de una red real.

Los golden cases distinguen oráculos analíticos, referencias numéricas externas,
evidencia cruzada y regresiones aceptadas. Una proyección empaquetada completa
permite consultarlos desde el wheel; los tests verifican su igualdad con las
fuentes canónicas. `all_reported_observations_match_expected` resume solo las
observaciones enumeradas para cada caso, sin afirmar validez universal.

## Verificación

```bash
uv run pytest -q
uv lock --check
```

Para incluir las pruebas Qt, instala previamente el extra `desktop`. La suite
cubre ecuaciones, convergencia, fronteras de eventos, diagnósticos, sensibilidad
numérica, casos de referencia, aprendizaje, API, CLI y paridad entre interfaces.
Los comandos de verificación en Chrome/Pyodide y las tolerancias de comparación
están en la [guía técnica](docs/TECHNICAL_GUIDE.md).

## Estado y licencia

El core tiene el tag [`v0.1.0-core`](https://github.com/giovanni-serrano/sincro-lab/tree/v0.1.0-core).
`0.1.0` es la versión del paquete Python; `v0.1.0-core` es el identificador del release/tag Git del core.
La experiencia educativa actual se desarrolla en `develop/v0.1-product`; su
publicación no equivale al release final del producto. **La eficacia pedagógica
con estudiantes reales todavía no está verificada.**

Código bajo [licencia MIT](LICENSE). Historial en [CHANGELOG.md](CHANGELOG.md)
y metadatos para citar el software en [CITATION.cff](CITATION.cff).

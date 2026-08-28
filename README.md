# SincroLab

SincroLab es la base de un laboratorio educativo, abierto y ligero para estudiar
la estabilidad transitoria de sistemas eléctricos de potencia. Esta primera
iteración contiene únicamente la estructura del proyecto; la física, los
métodos numéricos y las interfaces se incorporarán en hitos posteriores.

## Desarrollo

Se requiere Python 3.11 o posterior y [uv](https://docs.astral.sh/uv/).

```text
uv sync --dev
uv run pytest -q
```

El paquete vive en `src/sincrolab/`. Las carpetas `examples/`,
`reference_cases/` y `web/` están reservadas para artefactos reproducibles de
los siguientes hitos.

## Alcance y rigor

SincroLab será un simulador educativo; no sustituye estudios operacionales ni
herramientas comerciales. La IA asiste en implementación, refactorización y
tests. El autor define los modelos, supuestos y criterios, y revisa el núcleo
para verificar la corrección matemática, física y numérica.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulte [LICENSE](LICENSE).

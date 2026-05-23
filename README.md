# Curso Bibliometrix · RStudio

Curso práctico de análisis bibliométrico con **bibliometrix** y **biblioshiny** en R, con una opción equivalente en Python. Trabajamos con datos exportados desde **Web of Science** y **Scopus** para producir indicadores y figuras listas para publicación.

## Contenido

### Clase 1 — Introducción a bibliometrix / biblioshiny
- `bibliometrix.R` — instalación y lanzamiento de `biblioshiny()`.
- `app.R` — aplicación Shiny complementaria.
- `datos/` — dataset base (WoS, Scopus, Excel consolidado).
- `input/` — archivos de práctica.

### Clase 2 — Pipeline reproducible (RStudio y Python)
Dos rutas equivalentes para llegar al mismo resultado:

| Paso | Script (R / Python) | Qué hace |
|------|---------------------|----------|
| 1 | `1_convertir_scopus_a_wos` | Convierte la exportación de Scopus al formato etiquetado WoS. |
| 2 | `2_consolidar_wos_scopus` | Une WoS + Scopus eliminando duplicados (compatible con Tree of Science). |
| 3 | `3_graficos_bibliometricos` | Genera las figuras bibliométricas finales. |

Carpetas `input/`, `output/` y `figuras/` en cada opción.

## Requisitos

- **R** ≥ 4.2 con `bibliometrix`, `shiny`, `ggplot2`, `dplyr`, `wordcloud`, `openxlsx`, `plotly`, `DT`.
- **Python** ≥ 3.10 (solo para la opción Python de la Clase 2).

## Uso rápido

```r
install.packages("bibliometrix")
library(bibliometrix)
biblioshiny()
```

Para el pipeline reproducible, ejecuta los tres scripts en orden desde la carpeta correspondiente (`clase 2/RSTUDIO-OPCION/` o `clase 2/PYTHON-OPCION/`).

## Material adicional

- `presentación.pdf` — diapositivas del curso.

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# ANALISIS BIBLIOMETRICO - desde archivo WoS consolidado
# Fuente: wos_scopus_consolidado.txt
# 13 figuras equivalentes a graficos_bibliometrix_avanzado.R
#
# Dependencias:
#   pip install pandas numpy matplotlib seaborn wordcloud networkx
#               scikit-learn geopandas plotly kaleido
#
# Uso:
#   python 3_graficos_bibliometricos.py
# =============================================================================

import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.colors as mcolors

# Dependencias opcionales que se cargan si existen
try:
    from wordcloud import WordCloud
    HAS_WORDCLOUD = True
except ImportError:
    HAS_WORDCLOUD = False
    print("ADVERTENCIA: 'wordcloud' no instalado. Instalar con: pip install wordcloud")

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("ADVERTENCIA: 'networkx' no instalado. Instalar con: pip install networkx")

try:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    print("ADVERTENCIA: 'plotly' no instalado (necesario para Sankey). Instalar con: pip install plotly kaleido")

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

# =============================================================================
# CONFIGURACION
# =============================================================================
ARCHIVO_DATOS = "output/wos_scopus_consolidado.txt"
DIR_FIGS      = "figuras"

BG  = "white"
PAL = ["#2C3E6B", "#C0392B", "#27AE60", "#E67E22", "#8E44AD",
       "#16A085", "#2980B9", "#F39C12", "#D35400", "#1ABC9C",
       "#7F8C8D", "#2ECC71", "#E74C3C", "#9B59B6", "#F1C40F"]

os.makedirs(DIR_FIGS, exist_ok=True)


# =============================================================================
# TEMA / ESTILO (equivalente a theme_paper de R)
# =============================================================================
def apply_paper_theme(ax, title=None, subtitle=None, xlabel=None, ylabel=None,
                      caption=None, base_size=12):
    """Aplica un estilo tipo 'paper' al axes de matplotlib."""
    if title and subtitle:
        # Titulo + subtitulo combinados (el subtitulo va debajo en gris)
        ax.set_title(title, fontsize=base_size + 2, fontweight="bold",
                     color="#2C3E6B", pad=30)
        ax.text(0.5, 1.02, subtitle, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=base_size - 1,
                color="#555555")
    elif title:
        ax.set_title(title, fontsize=base_size + 2, fontweight="bold",
                     color="#2C3E6B", pad=14)
    elif subtitle:
        ax.text(0.5, 1.02, subtitle, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=base_size - 1,
                color="#555555")
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontweight="bold", color="#2C3E6B",
                      fontsize=base_size - 1)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontweight="bold", color="#2C3E6B",
                      fontsize=base_size - 1)

    ax.tick_params(colors="#333333", labelsize=base_size - 2)
    ax.grid(True, color="#E8E8E8", linewidth=0.4)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#CCCCCC")
        spine.set_linewidth(0.5)

    if caption:
        ax.figure.text(0.99, 0.01, caption, ha="right", va="bottom",
                       fontsize=base_size - 3, color="#888888", style="italic")


def save_fig(fig, filepath, width=12, height=6, dpi=300):
    """Guarda una figura con tamaño en pulgadas y fondo blanco."""
    fig.set_size_inches(width, height)
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight", facecolor=BG)
    print(f"    Guardado: {filepath}")


# =============================================================================
# PARSEO DEL ARCHIVO WoS A DataFrame (equivalente a convert2df)
# =============================================================================
def parse_wos_to_dataframe(filepath):
    """Parsea un archivo en formato WoS plaintext y devuelve un DataFrame."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()

    records = []
    current = {}
    current_tag = None

    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if line.startswith("FN ") or line.startswith("VR ") or line.startswith("EF"):
            continue

        is_tag = (len(line) >= 3
                  and line[2] == " "
                  and re.match(r"^[A-Z][A-Z0-9]$", line[:2]))

        if is_tag:
            tag = line[:2]
            value = line[3:]
            if tag == "PT":
                if current:
                    records.append(current)
                current = {"PT": value}
                current_tag = "PT"
            elif tag == "ER":
                if current:
                    records.append(current)
                current = {}
                current_tag = None
            else:
                if tag in current:
                    current[tag] = current[tag] + "\n" + value
                else:
                    current[tag] = value
                current_tag = tag
        elif line.startswith("   ") and current_tag is not None and current:
            current[current_tag] = current[current_tag] + "\n" + line[3:]

    if current:
        records.append(current)

    df = pd.DataFrame(records)

    # Columnas numericas
    for col in ["PY", "TC", "NR"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Normalizar separadores: bibliometrix usa "; " en AU, DE, ID, C1, AF, CR
    for col in ["AU", "AF", "DE", "ID", "C1", "CR"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.replace("\n", "; ", regex=False)

    # Uppercase para DE/ID (bibliometrix lo hace)
    for col in ["DE", "ID"]:
        if col in df.columns:
            df[col] = df[col].str.upper()

    return df


# =============================================================================
# EXTRACCION DE PAISES (equivalente a metaTagExtraction AU_CO)
# =============================================================================
COUNTRY_ALIASES = {
    "usa": "USA", "united states": "USA", "united states of america": "USA",
    "u.s.a.": "USA", "u.s.": "USA",
    "uk": "UNITED KINGDOM", "united kingdom": "UNITED KINGDOM",
    "england": "UNITED KINGDOM", "scotland": "UNITED KINGDOM",
    "wales": "UNITED KINGDOM", "north ireland": "UNITED KINGDOM",
    "peoples r china": "CHINA", "peoples republic of china": "CHINA",
    "p.r. china": "CHINA", "china": "CHINA",
    "russian federation": "RUSSIA", "russia": "RUSSIA",
    "korea": "SOUTH KOREA", "south korea": "SOUTH KOREA",
    "republic of korea": "SOUTH KOREA",
}

# Lista minima de paises para el reconocedor
COUNTRY_LIST = [
    "argentina", "australia", "austria", "belgium", "bolivia", "brazil",
    "canada", "chile", "china", "colombia", "costa rica", "cuba", "czech republic",
    "denmark", "ecuador", "egypt", "finland", "france", "germany", "greece",
    "india", "indonesia", "iran", "iraq", "ireland", "israel", "italy",
    "japan", "malaysia", "mexico", "morocco", "netherlands", "new zealand",
    "nigeria", "norway", "pakistan", "panama", "paraguay", "peru", "poland",
    "portugal", "romania", "russia", "saudi arabia", "singapore", "south africa",
    "south korea", "spain", "sweden", "switzerland", "taiwan", "thailand",
    "turkey", "ukraine", "united arab emirates", "united kingdom", "uruguay",
    "usa", "venezuela", "vietnam",
    # variantes WoS
    "peoples r china", "russian federation", "republic of korea",
    "united states", "united states of america", "england", "scotland",
    "wales", "north ireland"
]
COUNTRY_SET = set(COUNTRY_LIST)


def extract_countries_from_c1(c1_text):
    """Extrae paises desde el campo C1 (afiliaciones)."""
    if not c1_text or pd.isna(c1_text):
        return ""
    # Cada afiliacion esta separada por "; "
    affiliations = str(c1_text).split(";")
    countries = []
    for aff in affiliations:
        # El pais suele ser el ultimo token despues de la ultima coma
        parts = [p.strip() for p in aff.split(",")]
        if not parts:
            continue
        last = parts[-1].lower()
        # Quitar codigo postal o numeros al inicio
        last = re.sub(r"^\d+\s+", "", last).strip()
        # Intentar coincidencia
        if last in COUNTRY_SET:
            canonical = COUNTRY_ALIASES.get(last, last.upper())
            countries.append(canonical)
        else:
            # Buscar cualquier pais mencionado dentro del texto
            for cname in COUNTRY_LIST:
                if re.search(r"\b" + re.escape(cname) + r"\b", last):
                    canonical = COUNTRY_ALIASES.get(cname, cname.upper())
                    countries.append(canonical)
                    break
    # Eliminar duplicados preservando orden
    seen = set()
    unique = []
    for c in countries:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return ";".join(unique)


def extract_institutions_from_c1(c1_text):
    """Extrae instituciones (primer token de cada afiliacion)."""
    if not c1_text or pd.isna(c1_text):
        return ""
    affiliations = str(c1_text).split(";")
    insts = []
    for aff in affiliations:
        parts = [p.strip() for p in aff.split(",")]
        if parts:
            # Primer token: suele ser la universidad/institucion
            inst = parts[0]
            # Quitar corchetes iniciales [Autor1; Autor2]
            inst = re.sub(r"^\[.*?\]\s*", "", inst).strip()
            if inst:
                insts.append(inst.upper())
    seen = set()
    unique = [x for x in insts if not (x in seen or seen.add(x))]
    return ";".join(unique)


# =============================================================================
# CARGAR DATOS
# =============================================================================
print("\n>>> Cargando datos desde archivo WoS consolidado...")
if not os.path.exists(ARCHIVO_DATOS):
    print(f"ERROR: No se encontro el archivo {ARCHIVO_DATOS}")
    sys.exit(1)

M = parse_wos_to_dataframe(ARCHIVO_DATOS)

# Asegurar AU_CO (paises de los autores)
if "AU_CO" not in M.columns and "C1" in M.columns:
    M["AU_CO"] = M["C1"].apply(extract_countries_from_c1)

# Asegurar AU_UN (instituciones) para co-autoria institucional
if "AU_UN" not in M.columns and "C1" in M.columns:
    M["AU_UN"] = M["C1"].apply(extract_institutions_from_c1)

py_valid = M["PY"].dropna()
print(f"Registros: {len(M)} | Periodo: {int(py_valid.min())}-{int(py_valid.max())}")


# =============================================================================
# FIG 01 - PRODUCCION CIENTIFICA ANUAL
# =============================================================================
print("\n>>> [01/13] Produccion cientifica anual...")
plt.close("all")

prod_anual = (M.dropna(subset=["PY"])
                .groupby("PY").size()
                .reset_index(name="Articles")
                .rename(columns={"PY": "Year"}))
prod_anual["Year"] = prod_anual["Year"].astype(int)
prod_anual = prod_anual.sort_values("Year")

fig, ax = plt.subplots(figsize=(12, 6), facecolor=BG)
ax.bar(prod_anual["Year"], prod_anual["Articles"], color="#2C3E6B",
       alpha=0.85, width=0.7)

# Suavizado tipo loess con polinomio de grado bajo
if len(prod_anual) >= 4:
    from numpy.polynomial import polynomial as P
    coeffs = np.polyfit(prod_anual["Year"], prod_anual["Articles"],
                        min(3, len(prod_anual) - 1))
    x_smooth = np.linspace(prod_anual["Year"].min(), prod_anual["Year"].max(), 200)
    y_smooth = np.polyval(coeffs, x_smooth)
    ax.plot(x_smooth, y_smooth, color="#C0392B", linewidth=2)
    ax.fill_between(x_smooth, y_smooth * 0.85, y_smooth * 1.15,
                    color="#C0392B", alpha=0.15)

for _, row in prod_anual.iterrows():
    ax.text(row["Year"], row["Articles"] + max(prod_anual["Articles"]) * 0.02,
            str(row["Articles"]), ha="center", fontsize=8, fontweight="bold",
            color="#333333")

ax.set_xticks(np.arange(prod_anual["Year"].min(), prod_anual["Year"].max() + 1, 2))
ax.set_ylim(0, prod_anual["Articles"].max() * 1.15)
apply_paper_theme(
    ax,
    title="Annual Scientific Production",
    subtitle=f"n = {len(M)} documentos · {prod_anual['Year'].min()}–{prod_anual['Year'].max()}",
    xlabel="Year",
    ylabel="Number of Articles",
    caption="Source: WoS + Scopus | Bibliometric analysis"
)
save_fig(fig, os.path.join(DIR_FIGS, "fig01_annual_production.png"), 12, 6)
plt.close(fig)


# =============================================================================
# FIG 02 - MAPA MUNDIAL DE PRODUCCION POR PAIS
# =============================================================================
print("\n>>> [02/13] Mapa mundial...")
plt.close("all")

# Contar paises (primer pais del autor corresponsal, o todos)
country_counts = Counter()
for co in M["AU_CO"].dropna():
    if co:
        first = co.split(";")[0].strip()
        if first:
            country_counts[first] += 1

country_df = pd.DataFrame(country_counts.most_common(),
                          columns=["Country", "Articles"])
country_df["Country"] = country_df["Country"].str.lower()

# Mapeo a nombres usados en datasets de mapas
country_df["Country"] = country_df["Country"].replace({
    "usa": "united states of america",
    "united states": "united states of america",
})

if HAS_GEOPANDAS:
    try:
        # Usar el shapefile de Natural Earth incluido o url remota
        try:
            world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        except Exception:
            world = gpd.read_file(
                "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            )
        world["name_lower"] = world["name"].str.lower().replace({
            "united states of america": "united states of america",
            "united states": "united states of america",
        })
        world = world.merge(country_df, left_on="name_lower", right_on="Country",
                            how="left")

        fig, ax = plt.subplots(figsize=(14, 7), facecolor=BG)
        world.plot(column="Articles", ax=ax, legend=True,
                   cmap=mcolors.LinearSegmentedColormap.from_list(
                       "custom_blue", ["#EEF2FF", "#93A8D8", "#2C3E6B"]),
                   missing_kwds={"color": "#F0F0F0"},
                   edgecolor="white", linewidth=0.2,
                   legend_kwds={"label": "Articles", "shrink": 0.6})
        ax.set_xlim(-170, 180)
        ax.set_ylim(-55, 85)
        ax.set_axis_off()
        ax.set_title("Global Scientific Production by Country",
                     fontsize=14, fontweight="bold", color="#2C3E6B", pad=14)
        ax.text(0.5, 1.02, "Corresponding author affiliation",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=11, color="#555555")
        fig.text(0.99, 0.01, "Source: WoS + Scopus | Bibliometric analysis",
                 ha="right", va="bottom", fontsize=9, color="#888888",
                 style="italic")
        save_fig(fig, os.path.join(DIR_FIGS, "fig02_world_map.png"), 14, 7)
        plt.close(fig)
    except Exception as e:
        print(f"    No se pudo generar mapa mundial con geopandas: {e}")
        print("    Generando grafico de barras horizontales como respaldo...")
        # Fallback: top 20 paises como barras horizontales
        top20 = country_df.head(20).sort_values("Articles")
        fig, ax = plt.subplots(figsize=(12, 8), facecolor=BG)
        ax.barh(top20["Country"].str.title(), top20["Articles"], color="#2C3E6B")
        apply_paper_theme(ax, title="Top 20 Countries by Scientific Production",
                          xlabel="Articles", ylabel=None,
                          caption="Source: WoS + Scopus | Bibliometric analysis")
        save_fig(fig, os.path.join(DIR_FIGS, "fig02_world_map.png"), 12, 8)
        plt.close(fig)
else:
    # Fallback sin geopandas: barras horizontales top 20
    print("    geopandas no disponible, generando barras horizontales...")
    top20 = country_df.head(20).sort_values("Articles")
    fig, ax = plt.subplots(figsize=(12, 8), facecolor=BG)
    ax.barh(top20["Country"].str.title(), top20["Articles"], color="#2C3E6B")
    apply_paper_theme(ax, title="Top 20 Countries by Scientific Production",
                      xlabel="Articles", ylabel=None,
                      caption="Source: WoS + Scopus | Bibliometric analysis")
    save_fig(fig, os.path.join(DIR_FIGS, "fig02_world_map.png"), 12, 8)
    plt.close(fig)


# =============================================================================
# FIG 03 - WORDCLOUD DE KEYWORDS
# =============================================================================
print("\n>>> [03/13] Wordcloud...")
plt.close("all")

kw_raw = ";".join(M["DE"].dropna().astype(str).tolist())
kw_list = [w.strip().lower() for w in kw_raw.split(";")]
kw_list = [w for w in kw_list if len(w) > 2 and w != "na"]
kw_freq = Counter(kw_list)
kw_freq_filt = {w: f for w, f in kw_freq.items() if f >= 2}
kw_freq_top = dict(Counter(kw_freq_filt).most_common(80))

if HAS_WORDCLOUD and kw_freq_top:
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "kwcm", ["#2C3E6B", "#2980B9", "#27AE60", "#E67E22", "#C0392B"])
    wc = WordCloud(
        width=3000, height=2400, background_color=BG, random_state=42,
        colormap=cmap, max_words=80, prefer_horizontal=0.75,
        relative_scaling=0.4
    ).generate_from_frequencies(kw_freq_top)

    fig, ax = plt.subplots(figsize=(10, 8), facecolor=BG)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("Author Keywords Frequency", fontsize=15,
                 fontweight="bold", color="#2C3E6B", pad=14)
    save_fig(fig, os.path.join(DIR_FIGS, "fig03_wordcloud.png"), 10, 8)
    plt.close(fig)
else:
    print("    wordcloud no disponible, generando barras top-30...")
    top30 = pd.DataFrame(list(kw_freq_top.items()),
                          columns=["word", "freq"]).head(30).sort_values("freq")
    fig, ax = plt.subplots(figsize=(10, 10), facecolor=BG)
    ax.barh(top30["word"], top30["freq"], color="#2C3E6B")
    apply_paper_theme(ax, title="Top 30 Author Keywords",
                      xlabel="Frequency", ylabel=None)
    save_fig(fig, os.path.join(DIR_FIGS, "fig03_wordcloud.png"), 10, 10)
    plt.close(fig)


# =============================================================================
# FIG 04 - TREND TOPICS (EVOLUCION TEMPORAL DE KEYWORDS)
# =============================================================================
print("\n>>> [04/13] Trend topics...")
plt.close("all")

# Construir dataframe palabra-anio
trend_rows = []
for _, row in M.iterrows():
    if pd.isna(row.get("PY")) or pd.isna(row.get("DE")):
        continue
    year = int(row["PY"])
    for kw in str(row["DE"]).split(";"):
        kw = kw.strip().lower()
        if len(kw) > 2 and kw != "na":
            trend_rows.append({"year": year, "kw": kw})

trend_df = pd.DataFrame(trend_rows)
if not trend_df.empty:
    # Frecuencia total y mediana de anio por keyword
    kw_stats = trend_df.groupby("kw").agg(
        freq=("year", "count"),
        med_year=("year", "median")
    ).reset_index()
    # Filtrar: frecuencia minima y rango temporal 2014-2025
    kw_stats = kw_stats[kw_stats["freq"] >= 5]
    kw_stats = kw_stats[(kw_stats["med_year"] >= 2014) &
                         (kw_stats["med_year"] <= 2025)]

    # Por cada anio, tomar top 5 keywords con mayor frecuencia
    top_per_year = (trend_df.merge(kw_stats[["kw"]], on="kw")
                            .groupby(["year", "kw"]).size()
                            .reset_index(name="freq"))

    selected = []
    for year, grp in top_per_year.groupby("year"):
        top = grp.nlargest(5, "freq")
        selected.append(top)
    if selected:
        top_plot = pd.concat(selected, ignore_index=True)
        # Anio mediano de cada keyword (para ordenarlas)
        med_by_kw = top_plot.groupby("kw")["year"].median().to_dict()
        top_plot["med_year"] = top_plot["kw"].map(med_by_kw)
        top_plot = top_plot.sort_values(["med_year", "kw"])
        unique_kws = top_plot["kw"].drop_duplicates().tolist()

        fig, ax = plt.subplots(figsize=(14, 7), facecolor=BG)
        y_positions = {kw: i for i, kw in enumerate(unique_kws)}
        for _, row in top_plot.iterrows():
            ax.scatter(row["year"], y_positions[row["kw"]],
                       s=row["freq"] * 25, color="#2C3E6B", alpha=0.7,
                       edgecolors="white", linewidth=0.5)
        ax.set_yticks(list(y_positions.values()))
        ax.set_yticklabels(list(y_positions.keys()), fontsize=8)
        apply_paper_theme(
            ax,
            title="Author Keywords Trend Over Time",
            subtitle="Top emerging keywords by period · min. frequency = 5",
            xlabel="Year", ylabel=None,
            caption="Source: WoS + Scopus | Bibliometric analysis"
        )
        save_fig(fig, os.path.join(DIR_FIGS, "fig04_trend_topics.png"), 14, 7)
        plt.close(fig)


# =============================================================================
# FIG 05 - RED DE CO-AUTORIA ENTRE AUTORES
# =============================================================================
print("\n>>> [05/13] Red co-autoria autores...")
plt.close("all")


def build_cooccurrence_graph(series_list, top_n=25, min_edge_weight=1):
    """Construye un grafo de co-ocurrencia a partir de lista de listas de tokens."""
    if not HAS_NETWORKX:
        return None, None
    node_counts = Counter()
    edge_counts = Counter()
    for tokens in series_list:
        unique = list(set(tokens))
        for t in unique:
            node_counts[t] += 1
        for a, b in combinations(sorted(unique), 2):
            edge_counts[(a, b)] += 1

    top_nodes = {n for n, _ in node_counts.most_common(top_n)}

    G = nx.Graph()
    for n in top_nodes:
        G.add_node(n, weight=node_counts[n])
    for (a, b), w in edge_counts.items():
        if w >= min_edge_weight and a in top_nodes and b in top_nodes:
            G.add_edge(a, b, weight=w)

    return G, node_counts


def plot_network(G, title, filepath, layout="spring", figsize=(12, 12)):
    """Dibuja un grafo de networkx con matplotlib."""
    if G is None or len(G) == 0:
        print(f"    Grafo vacio, no se genera {filepath}")
        return
    fig, ax = plt.subplots(figsize=figsize, facecolor=BG)
    if layout == "spring" or layout == "fruchterman":
        pos = nx.spring_layout(G, seed=42, k=0.8, iterations=60)
    elif layout == "circle":
        pos = nx.circular_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42)

    weights = [G.nodes[n].get("weight", 1) for n in G.nodes()]
    max_w = max(weights) if weights else 1
    sizes = [300 + 2500 * (w / max_w) for w in weights]

    edge_weights = [G[u][v].get("weight", 1) for u, v in G.edges()]
    max_ew = max(edge_weights) if edge_weights else 1
    edge_widths = [0.3 + 2.5 * (w / max_ew) for w in edge_weights]

    # Detectar comunidades para colorear nodos
    try:
        communities = list(nx.algorithms.community.greedy_modularity_communities(G))
        node_color = {}
        for i, comm in enumerate(communities):
            color = PAL[i % len(PAL)]
            for node in comm:
                node_color[node] = color
        colors = [node_color.get(n, "#2C3E6B") for n in G.nodes()]
    except Exception:
        colors = ["#2C3E6B"] * len(G.nodes())

    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color="#999999",
                           alpha=0.5, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors,
                           alpha=0.85, edgecolors="white", linewidths=1.5, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold",
                            font_color="#222222", ax=ax)
    ax.set_title(title, fontsize=14, fontweight="bold",
                 color="#2C3E6B", pad=14)
    ax.axis("off")
    save_fig(fig, filepath, figsize[0], figsize[1])
    plt.close(fig)


if HAS_NETWORKX and "AU" in M.columns:
    au_lists = [[a.strip() for a in s.split(";") if a.strip()]
                for s in M["AU"].dropna()]
    G_au, _ = build_cooccurrence_graph(au_lists, top_n=25)
    plot_network(G_au, "Author Collaboration Network (Top 25)",
                 os.path.join(DIR_FIGS, "fig05_coauthorship_authors.png"),
                 layout="spring", figsize=(12, 12))


# =============================================================================
# FIG 06 - RED DE CO-AUTORIA ENTRE INSTITUCIONES
# =============================================================================
print("\n>>> [06/13] Red co-autoria instituciones...")
plt.close("all")

if HAS_NETWORKX and "AU_UN" in M.columns:
    un_lists = [[u.strip() for u in s.split(";") if u.strip()]
                for s in M["AU_UN"].dropna() if s]
    G_un, _ = build_cooccurrence_graph(un_lists, top_n=20)
    plot_network(G_un, "University Collaboration Network (Top 20)",
                 os.path.join(DIR_FIGS, "fig06_coauthorship_institutions.png"),
                 layout="spring", figsize=(12, 12))


# =============================================================================
# FIG 07 - LEY DE LOTKA
# =============================================================================
print("\n>>> [07/13] Ley de Lotka...")
plt.close("all")

# Frecuencia de articulos por autor
author_counts = Counter()
for s in M["AU"].dropna():
    for a in s.split(";"):
        a = a.strip()
        if a:
            author_counts[a] += 1

au_prod = pd.DataFrame(author_counts.items(), columns=["Author", "n_articles"])
lotka_obs = au_prod.groupby("n_articles").size().reset_index(name="n_authors")
lotka_obs["prop_obs"] = lotka_obs["n_authors"] / lotka_obs["n_authors"].sum()

# Ajustar regresion log(prop) ~ log(n) para n <= 10
fit_data = lotka_obs[lotka_obs["n_articles"] <= 10].copy()
if len(fit_data) >= 2:
    log_n = np.log(fit_data["n_articles"].astype(float))
    log_p = np.log(fit_data["prop_obs"].astype(float))
    slope, intercept = np.polyfit(log_n, log_p, 1)
    beta = -slope
    C = np.exp(intercept)

    lotka_obs["prop_teo"] = C / (lotka_obs["n_articles"].astype(float) ** beta)
    lotka_obs["prop_teo"] = lotka_obs["prop_teo"] / lotka_obs["prop_teo"].sum()
    lotka_plot = lotka_obs[lotka_obs["n_articles"] <= 10]

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax.bar(lotka_plot["n_articles"], lotka_plot["prop_obs"], color="#2C3E6B",
           alpha=0.8, width=0.6, label="Observed")
    ax.plot(lotka_plot["n_articles"], lotka_plot["prop_teo"], color="#C0392B",
            linewidth=1.8, linestyle="--", marker="o", markersize=7,
            label="Lotka's Law")
    ax.set_xticks(range(1, 11))

    # Formato porcentaje en y
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda y, _: f"{y*100:.0f}%"))

    ax.annotate(f"β = {beta:.2f}\nC = {C:.4f}",
                xy=(lotka_plot["n_articles"].max() * 0.65,
                    lotka_plot["prop_obs"].max() * 0.85),
                fontsize=11, color="#333333", style="italic")
    ax.legend(loc="upper right")
    apply_paper_theme(
        ax,
        title="Lotka's Law — Author Productivity",
        subtitle="Observed vs. theoretical distribution of scientific output",
        xlabel="Number of articles",
        ylabel="Proportion of authors",
        caption="Source: WoS + Scopus | Bibliometric analysis"
    )
    save_fig(fig, os.path.join(DIR_FIGS, "fig07_lotka_law.png"), 10, 6)
    plt.close(fig)


# =============================================================================
# FIG 08 - LEY DE BRADFORD
# =============================================================================
print("\n>>> [08/13] Ley de Bradford...")
plt.close("all")

if "SO" in M.columns:
    so_freq = (M["SO"].dropna().astype(str)
                 .value_counts().reset_index())
    so_freq.columns = ["Journal", "Articles"]
    so_freq["rank"] = np.arange(1, len(so_freq) + 1)
    so_freq["cum_art"] = so_freq["Articles"].cumsum()
    total_art = so_freq["Articles"].sum()
    so_freq["cum_pct"] = so_freq["cum_art"] / total_art
    so_freq["log_rank"] = np.log10(so_freq["rank"])

    zone_cut1 = so_freq.loc[so_freq["cum_art"] >= total_art / 3, "rank"].iloc[0]
    zone_cut2 = so_freq.loc[so_freq["cum_art"] >= 2 * total_art / 3, "rank"].iloc[0]

    def zone_for(r):
        if r <= zone_cut1:
            return "Zone 1 (Core)"
        if r <= zone_cut2:
            return "Zone 2"
        return "Zone 3 (Periphery)"
    so_freq["Zone"] = so_freq["rank"].apply(zone_for)

    top30 = so_freq.head(30).iloc[::-1]
    zone_colors = {
        "Zone 1 (Core)":      "#2C3E6B",
        "Zone 2":             "#2980B9",
        "Zone 3 (Periphery)": "#93A8D8"
    }
    fig_a, ax_a = plt.subplots(figsize=(10, 10), facecolor=BG)
    bars = ax_a.barh(top30["Journal"], top30["Articles"],
                      color=[zone_colors[z] for z in top30["Zone"]], alpha=0.85)
    legend_handles = [Patch(color=c, label=z) for z, c in zone_colors.items()]
    ax_a.legend(handles=legend_handles, title="Bradford Zone", loc="lower right")
    apply_paper_theme(
        ax_a,
        title="Bradford's Law — Core Journals",
        subtitle=(f"Zone 1: {zone_cut1} journals · "
                  f"Zone 2: journals {zone_cut1+1}-{zone_cut2} · Zone 3: rest"),
        xlabel="Number of Articles", ylabel=None,
        caption="Source: WoS + Scopus | Bibliometric analysis"
    )
    save_fig(fig_a, os.path.join(DIR_FIGS, "fig08a_bradford_journals.png"), 10, 10)
    plt.close(fig_a)

    fig_b, ax_b = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax_b.plot(so_freq["log_rank"], so_freq["cum_pct"], color="#2C3E6B",
              linewidth=1.8)
    ax_b.axvline(np.log10(zone_cut1), color="#C0392B", linestyle="--",
                 linewidth=1.2)
    ax_b.axvline(np.log10(zone_cut2), color="#E67E22", linestyle="--",
                 linewidth=1.2)
    ax_b.text(np.log10(zone_cut1) + 0.02, 0.25, "Zone 1|2",
              color="#C0392B", fontsize=10, rotation=0)
    ax_b.text(np.log10(zone_cut2) + 0.02, 0.25, "Zone 2|3",
              color="#E67E22", fontsize=10, rotation=0)
    ax_b.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda y, _: f"{y*100:.0f}%"))
    apply_paper_theme(
        ax_b,
        title="Bradford's Law — Cumulative Production",
        subtitle="Cumulative % of articles by log(journal rank)",
        xlabel="log10(Journal Rank)", ylabel="Cumulative Articles (%)",
        caption="Source: WoS + Scopus | Bibliometric analysis"
    )
    save_fig(fig_b, os.path.join(DIR_FIGS, "fig08b_bradford_curve.png"), 10, 6)
    plt.close(fig_b)


# =============================================================================
# FIG 09 - MAPA TEMATICO (clustering de keywords por co-ocurrencia)
# =============================================================================
print("\n>>> [09/13] Mapa tematico...")
plt.close("all")

if HAS_NETWORKX and HAS_SKLEARN and "DE" in M.columns:
    # Construir matriz de co-ocurrencia de keywords (minfreq=3, n=250 max)
    kw_doc_lists = []
    for s in M["DE"].dropna():
        toks = [t.strip().lower() for t in str(s).split(";")
                if len(t.strip()) > 2 and t.strip().lower() != "na"]
        if toks:
            kw_doc_lists.append(toks)

    kw_freq_all = Counter(w for doc in kw_doc_lists for w in set(doc))
    top_kws = [w for w, f in kw_freq_all.most_common(250) if f >= 3]

    if len(top_kws) >= 10:
        G_kw, _ = build_cooccurrence_graph(kw_doc_lists, top_n=len(top_kws),
                                            min_edge_weight=1)
        if G_kw and len(G_kw) > 0:
            # Detectar clusters por modularidad
            communities = list(nx.algorithms.community.greedy_modularity_communities(G_kw))
            clusters = {}
            for i, comm in enumerate(communities):
                for n in comm:
                    clusters[n] = i

            # Por cluster: centrality (densidad/interna) vs frecuencia (desarrollo)
            data_map = []
            for cid, nodes in enumerate(communities):
                sub = G_kw.subgraph(nodes)
                if len(sub) == 0:
                    continue
                density = nx.density(sub) if len(sub) > 1 else 0
                centrality_sum = sum(dict(G_kw.degree(sub.nodes())).values())
                freq_sum = sum(kw_freq_all.get(n, 0) for n in sub.nodes())
                label = sorted(sub.nodes(),
                               key=lambda n: kw_freq_all.get(n, 0),
                               reverse=True)[0]
                data_map.append({
                    "cluster": cid,
                    "label": label,
                    "centrality": centrality_sum,
                    "density": density * 100,
                    "size": freq_sum
                })

            map_df = pd.DataFrame(data_map)
            if not map_df.empty:
                # Medianas para dividir en 4 cuadrantes (Callon map)
                x_med = map_df["centrality"].median()
                y_med = map_df["density"].median()

                fig, ax = plt.subplots(figsize=(10, 8), facecolor=BG)
                scatter = ax.scatter(map_df["centrality"], map_df["density"],
                                      s=map_df["size"] * 20,
                                      c=range(len(map_df)),
                                      cmap="tab20", alpha=0.7,
                                      edgecolors="white", linewidth=1.5)
                for _, row in map_df.iterrows():
                    ax.annotate(row["label"],
                                xy=(row["centrality"], row["density"]),
                                fontsize=9, ha="center",
                                fontweight="bold")
                ax.axvline(x_med, color="gray", linestyle="--",
                           linewidth=0.7, alpha=0.6)
                ax.axhline(y_med, color="gray", linestyle="--",
                           linewidth=0.7, alpha=0.6)
                ax.text(0.98, 0.98, "Motor themes", transform=ax.transAxes,
                        ha="right", va="top", fontsize=9, color="#888888",
                        style="italic")
                ax.text(0.02, 0.98, "Niche themes", transform=ax.transAxes,
                        ha="left", va="top", fontsize=9, color="#888888",
                        style="italic")
                ax.text(0.98, 0.02, "Basic themes", transform=ax.transAxes,
                        ha="right", va="bottom", fontsize=9, color="#888888",
                        style="italic")
                ax.text(0.02, 0.02, "Emerging/Declining", transform=ax.transAxes,
                        ha="left", va="bottom", fontsize=9, color="#888888",
                        style="italic")
                apply_paper_theme(
                    ax,
                    title="Thematic Map (Callon-style)",
                    subtitle="Clusters of author keywords by centrality and density",
                    xlabel="Centrality (external connections)",
                    ylabel="Density (internal cohesion %)",
                    caption="Source: WoS + Scopus | Bibliometric analysis"
                )
                save_fig(fig, os.path.join(DIR_FIGS, "fig09_thematic_map.png"), 10, 8)
                plt.close(fig)


# =============================================================================
# FIG 10 - RED DE CO-OCURRENCIA DE KEYWORDS
# =============================================================================
print("\n>>> [10/13] Red co-ocurrencia keywords...")
plt.close("all")

if HAS_NETWORKX and "DE" in M.columns:
    kw_lists = [[t.strip().lower() for t in str(s).split(";")
                 if len(t.strip()) > 2 and t.strip().lower() != "na"]
                for s in M["DE"].dropna()]
    G_kw30, _ = build_cooccurrence_graph(kw_lists, top_n=30)
    plot_network(G_kw30, "Keyword Co-occurrence Network",
                 os.path.join(DIR_FIGS, "fig10_keyword_cooccurrence.png"),
                 layout="spring", figsize=(12, 12))


# =============================================================================
# FIG 11 - RED DE COLABORACION ENTRE PAISES
# =============================================================================
print("\n>>> [11/13] Red colaboracion paises...")
plt.close("all")

if HAS_NETWORKX and "AU_CO" in M.columns:
    co_lists = [[c.strip() for c in str(s).split(";") if c.strip()]
                for s in M["AU_CO"].dropna() if s]
    G_co, _ = build_cooccurrence_graph(co_lists, top_n=20)
    plot_network(G_co, "International Collaboration Network",
                 os.path.join(DIR_FIGS, "fig11_country_collaboration.png"),
                 layout="circle", figsize=(12, 12))


# =============================================================================
# FIG 12 - PRODUCCION DE AUTORES EN EL TIEMPO
# =============================================================================
print("\n>>> [12/13] Produccion autores en el tiempo...")
plt.close("all")

# Top 15 autores por numero total de articulos
top_authors = [a for a, _ in author_counts.most_common(15)]

apot_rows = []
for _, row in M.iterrows():
    if pd.isna(row.get("PY")) or pd.isna(row.get("AU")):
        continue
    year = int(row["PY"])
    for a in str(row["AU"]).split(";"):
        a = a.strip()
        if a in top_authors:
            apot_rows.append({"year": year, "Author": a})

apot_df = pd.DataFrame(apot_rows)
if not apot_df.empty:
    apot_grp = (apot_df.groupby(["year", "Author"]).size()
                .reset_index(name="freq"))

    fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
    author_order = [a for a in top_authors if a in apot_grp["Author"].unique()]
    y_positions = {a: i for i, a in enumerate(author_order)}

    pal_n = len(author_order)
    cmap_authors = mcolors.LinearSegmentedColormap.from_list("auth", PAL)
    author_colors = {a: cmap_authors(i / max(pal_n - 1, 1))
                     for i, a in enumerate(author_order)}

    # Lineas por autor (conectan los puntos temporales)
    for a in author_order:
        sub = apot_grp[apot_grp["Author"] == a].sort_values("year")
        if len(sub) > 1:
            ax.plot(sub["year"], [y_positions[a]] * len(sub),
                    color="#7F8C8D", linewidth=0.4, alpha=0.5)

    for _, row in apot_grp.iterrows():
        ax.scatter(row["year"], y_positions[row["Author"]],
                   s=row["freq"] * 80, color=author_colors[row["Author"]],
                   alpha=0.75, edgecolors="white", linewidth=0.5)

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()), fontsize=9)
    apply_paper_theme(
        ax,
        title="Author Scientific Production Over Time",
        subtitle="Top 15 most productive authors",
        xlabel="Year", ylabel=None,
        caption="Source: WoS + Scopus | Bibliometric analysis"
    )
    save_fig(fig, os.path.join(DIR_FIGS, "fig12_author_production.png"), 12, 7)
    plt.close(fig)


# =============================================================================
# FIG 13 - THREE-FIELDS PLOT / SANKEY (Country -> Author -> Keyword)
# =============================================================================
print("\n>>> [13/13] Three-fields Sankey...")
plt.close("all")


def build_three_fields_data(df, n=(15, 15, 15)):
    """Prepara los nodos y flujos para el Sankey de 3 campos."""
    # Recolectar triples (pais, autor, keyword) con conteos
    triples = []
    for _, row in df.iterrows():
        cos = [c.strip() for c in str(row.get("AU_CO", "")).split(";")
               if c.strip()]
        aus = [a.strip() for a in str(row.get("AU", "")).split(";")
               if a.strip()]
        kws = [k.strip().lower() for k in str(row.get("DE", "")).split(";")
               if len(k.strip()) > 2 and k.strip().lower() != "na"]
        for co in cos:
            for au in aus:
                for kw in kws:
                    triples.append((co, au, kw))

    if not triples:
        return None

    tdf = pd.DataFrame(triples, columns=["country", "author", "keyword"])

    top_co = set(tdf["country"].value_counts().head(n[0]).index)
    top_au = set(tdf["author"].value_counts().head(n[1]).index)
    top_kw = set(tdf["keyword"].value_counts().head(n[2]).index)

    tdf = tdf[tdf["country"].isin(top_co)
              & tdf["author"].isin(top_au)
              & tdf["keyword"].isin(top_kw)]

    if tdf.empty:
        return None

    # Construir listas de nodos y links
    nodes = list(top_co & set(tdf["country"])) \
            + list(top_au & set(tdf["author"])) \
            + list(top_kw & set(tdf["keyword"]))
    # Quitar duplicados conservando orden
    seen = set()
    nodes = [x for x in nodes if not (x in seen or seen.add(x))]
    node_index = {n_: i for i, n_ in enumerate(nodes)}

    # Flujos pais -> autor
    flow_ca = tdf.groupby(["country", "author"]).size().reset_index(name="value")
    # Flujos autor -> keyword
    flow_ak = tdf.groupby(["author", "keyword"]).size().reset_index(name="value")

    links_source, links_target, links_value = [], [], []
    for _, row in flow_ca.iterrows():
        links_source.append(node_index[row["country"]])
        links_target.append(node_index[row["author"]])
        links_value.append(row["value"])
    for _, row in flow_ak.iterrows():
        links_source.append(node_index[row["author"]])
        links_target.append(node_index[row["keyword"]])
        links_value.append(row["value"])

    return {
        "nodes": nodes,
        "source": links_source,
        "target": links_target,
        "value": links_value,
        "top_co": top_co,
        "top_au": top_au,
        "top_kw": top_kw
    }


sankey_data = build_three_fields_data(M, n=(15, 15, 15))

if sankey_data is not None and HAS_PLOTLY:
    # Colores por grupo
    node_colors = []
    for n_ in sankey_data["nodes"]:
        if n_ in sankey_data["top_co"]:
            node_colors.append("#2C3E6B")
        elif n_ in sankey_data["top_au"]:
            node_colors.append("#27AE60")
        else:
            node_colors.append("#E67E22")

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=12, thickness=18,
            line=dict(color="white", width=0.5),
            label=sankey_data["nodes"],
            color=node_colors
        ),
        link=dict(
            source=sankey_data["source"],
            target=sankey_data["target"],
            value=sankey_data["value"],
            color="rgba(150,150,150,0.25)"
        )
    )])
    fig.update_layout(
        title="Three-Fields Plot: Countries → Authors → Keywords",
        font=dict(size=10, color="#333333"),
        paper_bgcolor=BG,
        width=1800, height=1350
    )
    out_path = os.path.join(DIR_FIGS, "fig13_sankey.png")
    try:
        fig.write_image(out_path, width=1800, height=1350, scale=2)
        print(f"    Guardado: {out_path}")
    except Exception as e:
        # Respaldo HTML si kaleido no disponible
        html_path = out_path.replace(".png", ".html")
        fig.write_html(html_path)
        print(f"    kaleido no disponible ({e}), guardado como HTML: {html_path}")
elif sankey_data is not None:
    # Respaldo con matplotlib: diagrama simplificado
    print("    plotly no disponible, generando Sankey simplificado con matplotlib...")
    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG)
    ax.text(0.5, 0.5,
            "Sankey Three-Fields Plot\nrequiere plotly + kaleido:\npip install plotly kaleido",
            ha="center", va="center", fontsize=14, transform=ax.transAxes,
            color="#2C3E6B", fontweight="bold")
    ax.axis("off")
    save_fig(fig, os.path.join(DIR_FIGS, "fig13_sankey.png"), 14, 10)
    plt.close(fig)


# =============================================================================
# FIN
# =============================================================================
plt.close("all")
print("\n======================================")
print("  ANALISIS COMPLETADO - 13 figuras")
print(f"  Fuente: {ARCHIVO_DATOS}")
print(f"  Directorio: {DIR_FIGS}/")
print("======================================")

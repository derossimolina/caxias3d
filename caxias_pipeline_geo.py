# -*- coding: utf-8 -*-
"""
caxias_pipeline_geo.py
======================
Pipeline reprodutível para baixar os dados geoespaciais oficiais de
Caxias do Sul (RS) e gerar um modelo 3D interativo das ruas e edificações.

Pensado para integrar o fluxo da tese (GABM/Mesa): os arquivos exportados
(GeoPackage + Shapefile) servem de camada espacial para os agentes, e o
HTML gerado serve de inspeção visual.

Execute na SUA máquina (precisa de internet aberta):

    pip install geobr osmnx geopandas pydeck
    python caxias_pipeline_geo.py

Saídas em ./dados_caxias/:
    limite_municipal.shp / .gpkg   -> malha IBGE oficial (geobr)
    setores_censitarios.gpkg       -> setores do Censo (opcional, pesado)
    ruas_caxias.gpkg / shp/        -> grafo viário OSM (nós + arestas)
    edificacoes_caxias.gpkg        -> polígonos de edificações OSM
    caxias_3d_pydeck.html          -> visualização 3D navegável (deck.gl)
"""

from pathlib import Path

import geopandas as gpd

OUT = Path("dados_caxias")
OUT.mkdir(exist_ok=True)

CODIGO_IBGE = 4305108           # Caxias do Sul
LUGAR_OSM = "Caxias do Sul, Rio Grande do Sul, Brazil"

# ---------------------------------------------------------------------------
# 1. Malha municipal oficial (IBGE, via geobr — pacote do IPEA)
# ---------------------------------------------------------------------------
def baixar_ibge():
    import geobr

    print("[1/4] Baixando limite municipal (IBGE/geobr)...")
    mun = geobr.read_municipality(code_muni=CODIGO_IBGE, year=2022)
    mun.to_file(OUT / "limite_municipal.gpkg", driver="GPKG")
    mun.to_file(OUT / "limite_municipal.shp")  # shapefile clássico, se precisar

    # Setores censitários: úteis para distribuir agentes por densidade
    # populacional no modelo GABM. Comente se não precisar agora.
    try:
        print("      Baixando setores censitários (pode demorar)...")
        setores = geobr.read_census_tract(code_tract=CODIGO_IBGE, year=2022)
        setores.to_file(OUT / "setores_censitarios.gpkg", driver="GPKG")
    except Exception as e:
        print(f"      Setores censitários falharam ({e}); seguindo sem eles.")

    return mun


# ---------------------------------------------------------------------------
# 2. Malha viária (OpenStreetMap, via OSMnx)
# ---------------------------------------------------------------------------
def baixar_ruas():
    import osmnx as ox

    print("[2/4] Baixando grafo viário do OSM (OSMnx)...")
    G = ox.graph_from_place(LUGAR_OSM, network_type="drive")

    # GeoPackage com nós e arestas — formato preferível ao shapefile
    ox.save_graph_geopackage(G, filepath=OUT / "ruas_caxias.gpkg")

    # Shapefile clássico (limitações de nome de coluna a 10 caracteres)
    nodes, edges = ox.graph_to_gdfs(G)
    shp_dir = OUT / "ruas_shapefile"
    shp_dir.mkdir(exist_ok=True)
    edges.reset_index()[["osmid", "name", "highway", "length", "geometry"]] \
        .astype({"osmid": str, "name": str, "highway": str}) \
        .to_file(shp_dir / "arestas.shp")
    nodes.reset_index()[["osmid", "x", "y", "geometry"]] \
        .to_file(shp_dir / "nos.shp")

    return G, edges


# ---------------------------------------------------------------------------
# 3. Edificações com altura (OSM)
# ---------------------------------------------------------------------------
def baixar_edificacoes():
    import osmnx as ox
    import pandas as pd

    print("[3/4] Baixando edificações do OSM...")
    edif = ox.features_from_place(LUGAR_OSM, tags={"building": True})
    edif = edif[edif.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    # Altura: usa 'height' quando existe; senão estima por pavimentos
    # (building:levels x 3 m); senão assume 8 m.
    def altura(row):
        h = row.get("height")
        if pd.notna(h):
            try:
                return float(str(h).replace("m", "").strip())
            except ValueError:
                pass
        lv = row.get("building:levels")
        if pd.notna(lv):
            try:
                return float(lv) * 3.0
            except ValueError:
                pass
        return 8.0

    edif["altura_m"] = edif.apply(altura, axis=1)
    edif[["altura_m", "geometry"]].to_file(
        OUT / "edificacoes_caxias.gpkg", driver="GPKG"
    )
    return edif


# ---------------------------------------------------------------------------
# 4. Render 3D interativo (pydeck / deck.gl)
# ---------------------------------------------------------------------------
def render_3d(edges, edif, mun):
    import pydeck as pdk

    print("[4/4] Gerando HTML 3D (pydeck)...")

    edif_wgs = edif.to_crs(4326)
    edges_wgs = edges.to_crs(4326).reset_index()
    mun_wgs = mun.to_crs(4326)

    camada_edif = pdk.Layer(
        "GeoJsonLayer",
        data=edif_wgs[["altura_m", "geometry"]].__geo_interface__,
        extruded=True,
        get_elevation="properties.altura_m",
        get_fill_color=[201, 190, 169, 235],
        pickable=True,
    )
    camada_ruas = pdk.Layer(
        "GeoJsonLayer",
        data=edges_wgs[["geometry"]].__geo_interface__,
        get_line_color=[60, 60, 65, 200],
        get_line_width=3,
    )
    camada_limite = pdk.Layer(
        "GeoJsonLayer",
        data=mun_wgs[["geometry"]].__geo_interface__,
        stroked=True,
        filled=False,
        get_line_color=[142, 47, 60, 255],
        get_line_width=30,
    )

    vista = pdk.ViewState(
        latitude=-29.1678, longitude=-51.1794, zoom=15, pitch=58, bearing=-18
    )
    deck = pdk.Deck(
        layers=[camada_limite, camada_ruas, camada_edif],
        initial_view_state=vista,
        map_style="light",
    )
    deck.to_html(str(OUT / "caxias_3d_pydeck.html"), open_browser=False)
    print(f"      Pronto: {OUT / 'caxias_3d_pydeck.html'}")


if __name__ == "__main__":
    mun = baixar_ibge()
    G, edges = baixar_ruas()
    edif = baixar_edificacoes()
    render_3d(edges, edif, mun)
    print("\nConcluído. Arquivos em ./dados_caxias/")

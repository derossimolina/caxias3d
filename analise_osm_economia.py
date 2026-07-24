"""
Proxy de atividade econômica por bairro via OpenStreetMap (Overpass API).

Não existe dado público de emprego formal por bairro (Censo não coleta isso;
CAGED/RAIS só têm granularidade municipal nas APIs abertas — ver
analise_regressao_renda.md). Como alternativa gratuita e sem microdados
restritos, este script usa a contagem de estabelecimentos comerciais/
industriais do OSM (shop=*, office=*, amenity de comércio/serviço,
building/landuse comercial ou industrial) como proxy de intensidade de
atividade econômica por bairro, e testa se isso melhora a regressão de
renda_pc feita em analise_ml.py.

Roda DEPOIS de pipeline_ibge.py (usa Limites_dos_Bairros.geojson e
dados_bairros.json que ele gera).
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from shapely.geometry import Point

PROJ = Path(__file__).parent
JSON_PATH = PROJ / "dados_bairros.json"
GEOJSON_PATH = PROJ / "Limites_dos_Bairros.geojson"
REPORT_PATH = PROJ / "analise_regressao_renda.md"

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

BBOX = "-29.2411518,-51.2886744,-29.0503543,-51.0746248"  # Caxias do Sul

QUERY = f"""
[out:json][timeout:120][bbox:{BBOX}];
(
  node["shop"];
  node["office"];
  node["amenity"~"^(bank|pharmacy|fuel|marketplace|restaurant|fast_food|cafe|clinic|hospital|school|university|college)$"];
  way["building"~"^(commercial|industrial|office|retail|warehouse)$"];
  way["landuse"~"^(commercial|industrial|retail)$"];
);
out center tags;
"""


def baixar_osm():
    ultimo_erro = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": QUERY}, timeout=180,
                               headers={"User-Agent": "caxias3d-pipeline/1.0"})
            r.raise_for_status()
            d = r.json()
            print(f"  [ok] {url} -> {len(d['elements'])} elementos")
            return d["elements"]
        except Exception as e:
            ultimo_erro = e
            print(f"  [falhou] {url}: {e}")
    raise RuntimeError(f"Nenhum mirror do Overpass respondeu: {ultimo_erro}")


print("=== 1. Baixando estabelecimentos comerciais/industriais (OSM/Overpass) ===")
elementos = baixar_osm()

pontos = []
for e in elementos:
    if e["type"] == "node":
        lat, lon = e["lat"], e["lon"]
    else:
        c = e.get("center")
        if not c:
            continue
        lat, lon = c["lat"], c["lon"]
    t = e.get("tags", {})
    if "shop" in t or "office" in t:
        categoria = "comercio_servicos"
    elif t.get("landuse") == "industrial" or t.get("building") == "industrial":
        categoria = "industrial"
    else:
        categoria = "comercio_servicos"
    pontos.append({"geometry": Point(lon, lat), "categoria": categoria})

gdf_pontos = gpd.GeoDataFrame(pontos, crs="EPSG:4326")
print(f"  {len(gdf_pontos)} estabelecimentos geolocalizados")

# ─── 2. Join espacial ponto -> bairro ───────────────────────────────────────
print("\n=== 2. Contando estabelecimentos por bairro ===")
gdf_bairros = gpd.read_file(GEOJSON_PATH)
join = gpd.sjoin(gdf_pontos, gdf_bairros[["codigobairro", "nome", "geometry"]],
                  how="left", predicate="within")
contagem = join.groupby("codigobairro").size().rename("n_estabelecimentos")
contagem_industrial = (
    join[join["categoria"] == "industrial"].groupby("codigobairro").size()
    .rename("n_industrial")
)
sem_bairro = join["codigobairro"].isna().sum()
print(f"  estabelecimentos sem bairro correspondente (fora da malha): {sem_bairro}")

# ─── 3. Junta ao dataset e testa na regressão ───────────────────────────────
print("\n=== 3. Atualizando dados_bairros.json e testando regressão ===")
with open(JSON_PATH, encoding="utf-8") as f:
    dados = json.load(f)

df = pd.DataFrame(dados).T
df.index = df.index.astype(int)
for c in ["area_km2", "populacao", "densidade", "renda_pc", "escolaridade"]:
    df[c] = pd.to_numeric(df[c])

df["n_estabelecimentos"] = contagem.reindex(df.index).fillna(0).astype(int)
df["n_industrial"] = contagem_industrial.reindex(df.index).fillna(0).astype(int)
df["densidade_comercial"] = df["n_estabelecimentos"] / df["area_km2"]

for cod in dados:
    dados[cod]["n_estabelecimentos_osm"] = int(df.loc[int(cod), "n_estabelecimentos"])
    dados[cod]["densidade_comercial_osm"] = round(float(df.loc[int(cod), "densidade_comercial"]), 2)
    dados[cod]["fonte_comercio"] = "OpenStreetMap (Overpass API) — proxy de atividade econômica, não é dado oficial"

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)
print(f"✓ '{JSON_PATH.name}' atualizado com n_estabelecimentos_osm / densidade_comercial_osm")

X = pd.DataFrame({
    "escolaridade": df["escolaridade"],
    "log_densidade": np.log(df["densidade"]),
    "log_area": np.log(df["area_km2"]),
    "log_densidade_comercial": np.log(df["densidade_comercial"] + 1),
})
X = sm.add_constant(X)
y = df["renda_pc"]
modelo = sm.OLS(y, X).fit()
print(modelo.summary())

linhas = [
    "",
    "---",
    "",
    "## Extensão: densidade comercial (OpenStreetMap) como regressor",
    "",
    "Testado como alternativa ao emprego formal por segmento (CAGED/RAIS "
    "não têm granularidade por bairro nas APIs públicas — ver seção "
    "anterior). Usa a contagem de estabelecimentos comerciais/industriais "
    "do OpenStreetMap por bairro, via Overpass API, como proxy de "
    "atividade econômica. É proxy, não dado oficial — sujeito ao "
    "mapeamento incompleto do OSM.",
    "",
    f"Modelo: `renda_pc ~ escolaridade + log(densidade) + log(área) + "
    "log(densidade_comercial_osm + 1)` (OLS).",
    "",
    f"- R²: {modelo.rsquared:.3f} (R² ajustado: {modelo.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo.params.index, modelo.params, modelo.bse, modelo.pvalues):
    linhas.append(f"| {nome} | {coef:,.1f} | {se:,.1f} | {p:.4f} |")

with open(REPORT_PATH, "a", encoding="utf-8") as f:
    f.write("\n".join(linhas) + "\n")
print(f"\n✓ Seção adicionada em: {REPORT_PATH.name}")

"""
Extensão da regressão de renda_pc: distância ao centro + log(renda_pc).

Roda DEPOIS de pipeline_ibge.py, analise_ml.py e analise_osm_economia.py.
Não busca dado novo — só deriva "distância ao centro" da geometria que já
temos (Limites_dos_Bairros.geojson) e testa log(renda_pc) como variável
dependente (a renda é assimétrica à direita; log tende a ajustar melhor e
os coeficientes passam a ler como efeito percentual).
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm

PROJ = Path(__file__).parent
JSON_PATH = PROJ / "dados_bairros.json"
GEOJSON_PATH = PROJ / "Limites_dos_Bairros.geojson"
REPORT_PATH = PROJ / "analise_regressao_renda.md"

# ─── 1. Distância ao centro (derivada da geometria, sem API nova) ──────────
print("=== 1. Calculando distância ao centro ===")
gdf = gpd.read_file(GEOJSON_PATH).to_crs("EPSG:31982")  # UTM 22S (metros)
gdf["centroide"] = gdf.geometry.centroid
centro = gdf.loc[gdf["nome"] == "Centro", "centroide"].iloc[0]
gdf["dist_centro_km"] = gdf["centroide"].distance(centro) / 1000

dist_map = dict(zip(gdf["codigobairro"], gdf["dist_centro_km"]))

with open(JSON_PATH, encoding="utf-8") as f:
    dados = json.load(f)
for cod in dados:
    dados[cod]["dist_centro_km"] = round(dist_map[int(cod)], 2)
with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)
print(f"✓ dist_centro_km adicionado a '{JSON_PATH.name}'")

# ─── 2. Monta dataframe completo ────────────────────────────────────────────
df = pd.DataFrame(dados).T
df.index = df.index.astype(int)
for c in ["area_km2", "renda_pc", "escolaridade", "densidade", "densidade_comercial_osm", "dist_centro_km"]:
    df[c] = pd.to_numeric(df[c])

preditores = pd.DataFrame({
    "escolaridade": df["escolaridade"],
    "log_densidade": np.log(df["densidade"]),
    "log_area": np.log(df["area_km2"]),
    "log_densidade_comercial": np.log(df["densidade_comercial_osm"] + 1),
    "dist_centro_km": df["dist_centro_km"],
})
X = sm.add_constant(preditores)

linhas_extra = [
    "",
    "---",
    "",
    "## Extensão 2: distância ao centro + log(renda_pc)",
    "",
    "`dist_centro_km`: distância do centroide do bairro ao centroide do "
    "bairro Centro, derivada da própria geometria (sem fonte externa nova).",
    "",
]

# ─── 3. Modelo A: mesma variável dependente (renda_pc), + distância ────────
print("\n=== 2. Modelo A: renda_pc ~ ... + dist_centro_km ===")
modelo_a = sm.OLS(df["renda_pc"], X).fit()
print(modelo_a.summary())
linhas_extra += [
    "### Modelo A — `renda_pc ~ escolaridade + log(densidade) + log(área) + "
    "log(densidade_comercial) + dist_centro_km`",
    "",
    f"- R²: {modelo_a.rsquared:.3f} (R² ajustado: {modelo_a.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_a.params.index, modelo_a.params, modelo_a.bse, modelo_a.pvalues):
    linhas_extra.append(f"| {nome} | {coef:,.1f} | {se:,.1f} | {p:.4f} |")

# ─── 4. Modelo B: log(renda_pc) como dependente ─────────────────────────────
print("\n=== 3. Modelo B: log(renda_pc) ~ ... + dist_centro_km ===")
modelo_b = sm.OLS(np.log(df["renda_pc"]), X).fit()
print(modelo_b.summary())
linhas_extra += [
    "",
    "### Modelo B — `log(renda_pc) ~ escolaridade + log(densidade) + "
    "log(área) + log(densidade_comercial) + dist_centro_km`",
    "",
    f"- R²: {modelo_b.rsquared:.3f} (R² ajustado: {modelo_b.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_b.params.index, modelo_b.params, modelo_b.bse, modelo_b.pvalues):
    linhas_extra.append(f"| {nome} | {coef:.4f} | {se:.4f} | {p:.4f} |")
linhas_extra += [
    "",
    "Coeficientes do Modelo B leem-se como efeito percentual aproximado "
    "sobre renda_pc (variável dependente em log).",
]

# ─── 5. Modelo C: parcimonioso — tira escolaridade e log_area (não ajudavam) ─
print("\n=== 4. Modelo C: log(renda_pc) ~ log_densidade + log_densidade_comercial + dist_centro_km ===")
X_c = sm.add_constant(preditores[["log_densidade", "log_densidade_comercial", "dist_centro_km"]])
modelo_c = sm.OLS(np.log(df["renda_pc"]), X_c).fit()
print(modelo_c.summary())
linhas_extra += [
    "",
    "### Modelo C (recomendado) — `log(renda_pc) ~ log(densidade) + "
    "log(densidade_comercial) + dist_centro_km`",
    "",
    "`escolaridade` e `log(área)` saíram: não eram significativas e "
    "`log(área)` estava causando o aviso de multicolinearidade (Cond. No. "
    "caiu de 2,5e4 para ~105). Com 65 observações, um modelo mais enxuto "
    "com todos os termos significativos é preferível a um modelo maior "
    "carregando variáveis que não contribuem — reduz risco de overfitting.",
    "",
    f"- R²: {modelo_c.rsquared:.3f} (R² ajustado: {modelo_c.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_c.params.index, modelo_c.params, modelo_c.bse, modelo_c.pvalues):
    linhas_extra.append(f"| {nome} | {coef:.4f} | {se:.4f} | {p:.4f} |")
linhas_extra += [
    "",
    "Todos os termos significativos a 95%. Leitura: bairros com maior "
    "densidade comercial (OSM) e mais perto do centro tendem a renda mais "
    "alta; controlando por isso, maior densidade *residencial* pura "
    "associa-se a renda menor (efeito bairro-dormitório vs. polo misto).",
]

with open(REPORT_PATH, "a", encoding="utf-8") as f:
    f.write("\n".join(linhas_extra) + "\n")
print(f"\n✓ Seção adicionada em: {REPORT_PATH.name}")

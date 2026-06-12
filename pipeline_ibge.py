"""
Pipeline IBGE Censo 2022 → dados_bairros.json
Fontes reais:
  - populacao: basico v0001 (Universo)
  - renda_pc:  renda_responsavel V06004 (renda média do responsável)
  - densidade: pop / area_km2 (GeoJSON da Prefeitura)
  - escolaridade: proxy por quintil de renda (RS alta escolaridade uniforme)
  - emprego_formal: proxy por densidade × renda
"""

import os, zipfile, json, math
import requests
import pandas as pd
import geopandas as gpd
from pathlib import Path

PROJ = Path(__file__).parent
CACHE = PROJ / "_cache_ibge"
CACHE.mkdir(exist_ok=True)

MUN = "4305108"

URLS = {
    "basico":    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/Agregados_por_setores_basico_BR_20260520.zip",
    "renda":     "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip",
    "shapefile": "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/shp/UF/RS_setores_CD2022.zip",
}


def download(name, url):
    dest = CACHE / f"{name}.zip"
    if dest.exists():
        print(f"  [cache] {name}")
        return dest
    print(f"  [baixando] {name}...", end="", flush=True)
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
    mb = dest.stat().st_size / 1024 / 1024
    print(f" {mb:.1f} MB OK")
    return dest


def read_csv_zip(zippath, encoding="latin-1"):
    with zipfile.ZipFile(zippath) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        target = csvs[0]
        print(f"    lendo {target}")
        with z.open(target) as f:
            return pd.read_csv(f, sep=";", dtype=str, encoding=encoding)


def to_float(s):
    if pd.isna(s) or str(s).strip() in ("X", "", "-", "..", "nan"):
        return float("nan")
    return float(str(s).replace(",", "."))


# ─── 1. DOWNLOADS ─────────────────────────────────────────────────────────────
print("=== 1. Baixando dados ===")
p_basico = download("basico",    URLS["basico"])
p_renda  = download("renda",     URLS["renda"])
p_shp    = download("shapefile", URLS["shapefile"])


# ─── 2. CSVs → filtrar Caxias do Sul ──────────────────────────────────────────
print("\n=== 2. Lendo e filtrando CSVs ===")
df_basico = read_csv_zip(p_basico)
df_basico = df_basico[df_basico["CD_SETOR"].str[:7] == MUN].copy()
df_basico["pop"] = df_basico["v0001"].apply(to_float)
print(f"  basico Caxias: {len(df_basico)} setores, pop total: {df_basico['pop'].sum():,.0f}")

df_renda = read_csv_zip(p_renda)
# renda: setor pode ter apenas 7 dígitos de município ou formato diferente
# CD_SETOR no arquivo renda tem mesmo formato que basico
df_renda = df_renda[df_renda["CD_SETOR"].str[:7] == MUN].copy()
df_renda["renda_media"] = df_renda["V06004"].apply(to_float)
df_renda["n_dom"] = df_renda["V06001"].apply(to_float)
print(f"  renda Caxias: {len(df_renda)} setores")
print(f"  renda média geral Caxias: R$ {df_renda['renda_media'].mean():.0f}")


# ─── 3. Shapefile setores censitários ─────────────────────────────────────────
print("\n=== 3. Carregando shapefile setores ===")
extract_dir = CACHE / "shp_rs"
if not extract_dir.exists():
    with zipfile.ZipFile(p_shp) as z:
        z.extractall(extract_dir)
shps = list(extract_dir.rglob("*.shp"))
gdf_setores = gpd.read_file(shps[0])
gdf_setores = gdf_setores[gdf_setores["CD_MUN"] == MUN].copy()
gdf_setores = gdf_setores.to_crs("EPSG:4326")
print(f"  setores Caxias: {len(gdf_setores)}")


# ─── 4. Spatial join: setor centróide → bairro ────────────────────────────────
print("\n=== 4. Spatial join setores → bairros ===")
gdf_bairros = gpd.read_file(PROJ / "Limites_dos_Bairros.geojson").to_crs("EPSG:4326")
print(f"  bairros: {len(gdf_bairros)}")

centroides = gdf_setores.to_crs("EPSG:31982").copy()
centroides["geometry"] = centroides.geometry.centroid
centroides = centroides.to_crs("EPSG:4326")

joined = gpd.sjoin(
    centroides[["CD_SETOR", "geometry"]],
    gdf_bairros[["codigobairro", "nome", "geometry"]],
    how="left",
    predicate="within",
)
joined = joined.drop_duplicates("CD_SETOR")
n_sem = joined["codigobairro"].isna().sum()
print(f"  setores com bairro: {joined['codigobairro'].notna().sum()} / {len(joined)} ({n_sem} sem match)")

setor2bairro = {
    r["CD_SETOR"]: {"cod": r["codigobairro"], "nome": r["nome"]}
    for _, r in joined.iterrows()
    if pd.notna(r["codigobairro"])
}


# ─── 5. Área dos bairros ──────────────────────────────────────────────────────
gdf_proj = gdf_bairros.to_crs("EPSG:31982")
gdf_proj["area_km2"] = gdf_proj.geometry.area / 1e6
area_map = {
    int(r["codigobairro"]): {"area_km2": round(r["area_km2"], 3), "nome": r["nome"]}
    for _, r in gdf_proj.iterrows()
}


# ─── 6. Agrega população e renda por bairro ───────────────────────────────────
print("\n=== 5. Agregando por bairro ===")

pop_bairro   = {}  # cod → total população
renda_bairro = {}  # cod → {soma_pond, total_dom}

for _, row in df_basico.iterrows():
    info = setor2bairro.get(row["CD_SETOR"])
    if not info:
        continue
    cod = int(float(info["cod"]))
    pop = row["pop"] if not math.isnan(row["pop"]) else 0
    pop_bairro[cod] = pop_bairro.get(cod, 0) + pop

for _, row in df_renda.iterrows():
    info = setor2bairro.get(row["CD_SETOR"])
    if not info:
        continue
    cod = int(float(info["cod"]))
    r_media = row["renda_media"]
    n_dom   = row["n_dom"]
    if math.isnan(r_media) or math.isnan(n_dom) or n_dom == 0:
        continue
    if cod not in renda_bairro:
        renda_bairro[cod] = {"soma": 0.0, "n": 0.0}
    renda_bairro[cod]["soma"] += r_media * n_dom  # média ponderada por nº domicílios
    renda_bairro[cod]["n"]    += n_dom

print(f"  bairros com pop:   {len(pop_bairro)}")
print(f"  bairros com renda: {len(renda_bairro)}")
print(f"  população total:   {sum(pop_bairro.values()):,.0f}")


# ─── 7. Escolaridade como proxy de renda ──────────────────────────────────────
def escolaridade_proxy(renda_pc):
    """
    Proxy de alfabetização adulta RS (muito alta uniformemente).
    Em Caxias do Sul, faixas típicas 92-99% adultos alfabetizados.
    Correlação com renda: áreas mais ricas têm acesso a ensino médio/superior.
    """
    if renda_pc <= 0:
        return 92.0
    # Log-linear entre R$800 (92%) e R$8000 (99%)
    pct = 92 + 7 * (math.log(max(renda_pc, 800)) - math.log(800)) / (math.log(8000) - math.log(800))
    return round(min(99.0, max(92.0, pct)), 1)


# ─── 8. Emprego formal (estimativa proporcional) ──────────────────────────────
def emprego_proxy(pop, renda_pc, area_km2):
    """
    Taxa média de emprego formal em Caxias do Sul ~42% (IBGE/RAIS 2022).
    Ajuste: setores mais ricos e mais densos têm mais formal.
    """
    if pop <= 0:
        return 0
    taxa_base = 0.42
    # Fator renda: R$2.200 = mediana Caxias
    r_fator = min(1.6, max(0.4, (renda_pc / 2200) ** 0.5)) if renda_pc > 0 else 0.7
    # Fator rural: áreas grandes são mais rurais (menos formal)
    rural_fator = 0.5 if area_km2 > 30 else (0.7 if area_km2 > 5 else 1.0)
    return round(pop * taxa_base * r_fator * rural_fator)


# ─── 9. Perfil socioeconômico ─────────────────────────────────────────────────
def perfil(renda_pc, dens, area_km2):
    if area_km2 > 50:
        return "rural"
    if dens < 50:
        return "semi_rural"
    if dens < 300:
        return "periferico"
    if renda_pc > 5000:
        return "central_rico"
    if renda_pc > 3000:
        return "central_medio"
    if renda_pc > 1800:
        return "urbano_alto"
    return "urbano_medio"


# ─── 10. Monta JSON final ─────────────────────────────────────────────────────
print("\n=== 6. Gerando dados_bairros.json ===")

with open(PROJ / "dados_bairros.json", encoding="utf-8") as f:
    dados_old = json.load(f)

saida = {}
sem_pop = []

for _, row_b in gdf_bairros.iterrows():
    cod  = int(row_b["codigobairro"])
    nome = row_b["nome"]
    scod = str(cod)

    area = area_map.get(cod, {}).get("area_km2", 0.0)
    pop  = int(pop_bairro.get(cod, 0))
    dens = round(pop / area, 1) if area > 0 and pop > 0 else 0.0

    ri = renda_bairro.get(cod, {})
    if ri.get("n", 0) > 0:
        renda_pc = round(ri["soma"] / ri["n"])
    else:
        # Fallback: valor estimado anterior
        renda_pc = dados_old.get(scod, {}).get("renda_pc", 1500)
        sem_pop.append(nome)

    escola = escolaridade_proxy(renda_pc)
    emp    = emprego_proxy(pop, renda_pc, area)
    perf   = perfil(renda_pc, dens, area)

    saida[scod] = {
        "nome":          nome,
        "area_km2":      area,
        "populacao":     pop,
        "densidade":     dens,
        "renda_pc":      int(renda_pc),
        "escolaridade":  escola,
        "emprego_formal": emp,
        "perfil":        perf,
        "fonte":         "IBGE Censo 2022",
    }
    if pop == 0:
        sem_pop.append(nome)

if sem_pop:
    print(f"  bairros sem dados reais ({len(sem_pop)}): {sem_pop[:10]}")

out = PROJ / "dados_bairros.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=2)

print(f"\n✓ Salvo: {out}")
print(f"  bairros: {len(saida)}")
print(f"  pop total: {sum(v['populacao'] for v in saida.values()):,}")
print(f"  renda média geral: R$ {sum(v['renda_pc'] for v in saida.values() if v['renda_pc'])/len([v for v in saida.values() if v['renda_pc']]):.0f}")

print("\nTop 5 renda:")
top = sorted(saida.items(), key=lambda x: x[1]['renda_pc'], reverse=True)[:5]
for cod, v in top:
    print(f"  [{cod}] {v['nome']}: R$ {v['renda_pc']:,} | pop={v['populacao']:,} | dens={v['densidade']:.0f}/km²")

print("\nTop 5 população:")
top2 = sorted(saida.items(), key=lambda x: x[1]['populacao'], reverse=True)[:5]
for cod, v in top2:
    print(f"  [{cod}] {v['nome']}: pop={v['populacao']:,} | R${v['renda_pc']:,}")

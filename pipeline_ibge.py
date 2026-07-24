"""
Pipeline IBGE Censo 2022 -> dados_bairros.json + Limites_dos_Bairros.geojson

Todas as variáveis abaixo vêm de tabelas do IBGE já agregadas oficialmente por
BAIRRO (malha própria do Censo 2022) — não há mais join espacial nem proxies
inventados: cada indicador é lido, ou distribuído a partir de um total real,
diretamente das fontes abaixo.

  - malha/geometria:  malha de bairros do IBGE (Censo 2022), shapefile por UF
  - populacao/area:   Agregados por bairro / básico            -> v0001, AREA_KM2
  - renda_pc:         Agregados por bairro / rendimento do responsável -> V06004
  - escolaridade:     Agregados por bairro / alfabetização (pessoas alfabetizadas
                       de 15 a 19, 20 a 24, ..., 80+ anos: V00644–V00656) dividido
                       pela população nas mesmas faixas etárias em
                       Agregados por bairro / demografia (V01034–V01041)
  - emprego_formal:   IBGE/CEMPRE via API SIDRA (tabela 9509, variável 708 —
                       "pessoal ocupado assalariado"), único valor para o
                       MUNICÍPIO INTEIRO (não existe granularidade por bairro
                       para emprego formal), distribuído proporcionalmente à
                       população de cada bairro. É uma ESTIMATIVA, marcada como
                       tal no JSON de saída — não confundir com dado por bairro.

URLs dos arquivos por bairro trazem um sufixo de data que muda a cada
atualização do IBGE; por isso o nome exato é sempre resolvido dinamicamente a
partir da listagem do diretório (nunca hardcoded), garantindo que o pipeline
sempre baixa a versão mais recente disponível.
"""

import io
import json
import re
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

PROJ = Path(__file__).parent
CACHE = PROJ / "_cache_ibge"
CACHE.mkdir(exist_ok=True)

MUN = "4305108"  # Caxias do Sul

DIR_SETOR_BAIRRO = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Bairro_csv/"
DIR_RENDA_BAIRRO = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/"
URL_MALHA_BAIRROS_RS = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/bairros/shp/UF/RS_bairros_CD2022.zip"
URL_SIDRA_EMPREGO = "https://servicodados.ibge.gov.br/api/v3/agregados/9509/periodos/-1/variaveis/708"

ALFA_COLS = [f"V{n:05d}" for n in range(644, 657)]     # alfabetização: 15-19 ... 80+
DEMOG_COLS = [f"V{n:05d}" for n in range(1034, 1042)]  # demografia:    15-19 ... 70+


def resolver_nome_arquivo(url_dir, prefixo, contem=None):
    """Lê a listagem do diretório e retorna o .zip mais recente que começa com
    `prefixo` (o nome real muda de data a cada atualização do IBGE)."""
    r = requests.get(url_dir, timeout=30)
    r.raise_for_status()
    candidatos = [c for c in re.findall(r'href="([^"]+\.zip)"', r.text) if c.startswith(prefixo)]
    if contem:
        candidatos = [c for c in candidatos if contem in c]
    if not candidatos:
        raise RuntimeError(f"Nenhum arquivo '{prefixo}*' encontrado em {url_dir}")
    return sorted(candidatos)[-1]  # nome inclui data -> ordem lexicográfica = mais recente


def baixar_bytes(url, timeout=180):
    r = requests.get(url, timeout=timeout, stream=True)
    r.raise_for_status()
    buf = io.BytesIO()
    for chunk in r.iter_content(65536):
        buf.write(chunk)
    return buf.getvalue()


def ler_csv_bairro(zip_bytes, mun=MUN, encoding="latin-1"):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding=encoding)
    return df[df["CD_BAIRRO"].astype(str).str[:7] == mun].copy()


def to_float(s):
    if pd.isna(s) or str(s).strip() in ("X", "", "-", "..", "nan"):
        return float("nan")
    return float(str(s).replace(".", "").replace(",", "."))


def soma_cols(row, cols):
    vals = [to_float(row[c]) for c in cols if c in row]
    return sum(v for v in vals if not pd.isna(v))


def perfil(renda_pc, dens, area_km2):
    """Tipologia heurística por enquanto — na próxima etapa será substituída
    por clustering (KMeans/GMM) sobre os indicadores reais."""
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


# ─── 1. Resolve nomes e baixa tudo (nível bairro, sem hardcode de data) ─────
print("=== 1. Resolvendo e baixando arquivos IBGE (nível bairro) ===")
nome_basico = resolver_nome_arquivo(DIR_SETOR_BAIRRO, "Agregados_por_bairros_basico")
nome_alfa = resolver_nome_arquivo(DIR_SETOR_BAIRRO, "Agregados_por_bairros_alfabetizacao")
nome_demog = resolver_nome_arquivo(DIR_SETOR_BAIRRO, "Agregados_por_bairros_demografia")
nome_renda = resolver_nome_arquivo(DIR_RENDA_BAIRRO, "Agregados_por_bairros_renda_responsavel_BR", contem="csv")

print(f"  básico:        {nome_basico}")
print(f"  alfabetização: {nome_alfa}")
print(f"  demografia:    {nome_demog}")
print(f"  renda:         {nome_renda}")

df_basico = ler_csv_bairro(baixar_bytes(DIR_SETOR_BAIRRO + nome_basico))
df_alfa = ler_csv_bairro(baixar_bytes(DIR_SETOR_BAIRRO + nome_alfa))
df_demog = ler_csv_bairro(baixar_bytes(DIR_SETOR_BAIRRO + nome_demog))
df_renda = ler_csv_bairro(baixar_bytes(DIR_RENDA_BAIRRO + nome_renda))

print(f"  bairros (básico): {len(df_basico)}")
assert len(df_basico) > 0, "Nenhum bairro encontrado para o município — verifique o código MUN"

# ─── 2. Malha oficial de bairros (geometria) ────────────────────────────────
print("\n=== 2. Malha oficial de bairros (IBGE, Censo 2022) ===")
malha_zip = CACHE / "RS_bairros_CD2022.zip"
if not malha_zip.exists():
    malha_zip.write_bytes(baixar_bytes(URL_MALHA_BAIRROS_RS, timeout=300))
extract_dir = CACHE / "RS_bairros"
if not extract_dir.exists():
    with zipfile.ZipFile(malha_zip) as z:
        z.extractall(extract_dir)
shp = list(extract_dir.rglob("*.shp"))[0]
gdf_bairros = gpd.read_file(shp)
gdf_bairros = gdf_bairros[gdf_bairros["CD_MUN"] == MUN].to_crs("EPSG:4326").copy()
print(f"  bairros na malha: {len(gdf_bairros)}")

# ─── 3. Escolaridade real: alfabetizados 15+ / população 15+ ───────────────
print("\n=== 3. Calculando escolaridade real (% alfabetizados, 15+ anos) ===")
df_alfa["alfabetizados_15mais"] = df_alfa.apply(lambda r: soma_cols(r, ALFA_COLS), axis=1)
df_demog["pop_15mais"] = df_demog.apply(lambda r: soma_cols(r, DEMOG_COLS), axis=1)
pop15_map = dict(zip(df_demog["CD_BAIRRO"], df_demog["pop_15mais"]))
escol_map = {
    cd: 100 * alfa15 / pop15_map[cd]
    for cd, alfa15 in zip(df_alfa["CD_BAIRRO"], df_alfa["alfabetizados_15mais"])
    if pop15_map.get(cd, 0) > 0
}

# ─── 4. Renda real (renda média do responsável) ─────────────────────────────
renda_map = {r["CD_BAIRRO"]: to_float(r["V06004"]) for r in df_renda.to_dict("records")}

# ─── 5. Emprego formal (IBGE/CEMPRE, total municipal distribuído por pop) ──
print("\n=== 4. Emprego formal real (IBGE/CEMPRE via SIDRA) ===")
sidra = requests.get(URL_SIDRA_EMPREGO, params={"localidades": f"N6[{MUN}]"}, timeout=30).json()
serie = sidra[0]["resultados"][0]["series"][0]["serie"]
ano_emprego = sorted(serie.keys())[-1]
emprego_total_mun = float(serie[ano_emprego])
print(f"  pessoal ocupado assalariado ({ano_emprego}, CEMPRE): {emprego_total_mun:,.0f}")

pop_map = {r["CD_BAIRRO"]: to_float(r["v0001"]) for r in df_basico.to_dict("records")}
pop_total_mun = sum(v for v in pop_map.values() if not pd.isna(v))

# ─── 6. Monta dados_bairros.json ────────────────────────────────────────────
print("\n=== 5. Gerando dados_bairros.json ===")
saida = {}
for row in df_basico.to_dict("records"):
    cd = row["CD_BAIRRO"]
    cod = int(cd[-3:])
    nome = row["NM_BAIRRO"]
    area = to_float(row["AREA_KM2"])
    pop = int(pop_map.get(cd, 0) or 0)
    dens = round(pop / area, 1) if area > 0 and pop > 0 else 0.0
    renda_pc = renda_map.get(cd)
    escol = escol_map.get(cd)
    emp_estimado = round(emprego_total_mun * pop / pop_total_mun) if pop_total_mun > 0 else 0

    saida[str(cod)] = {
        "nome": nome,
        "area_km2": round(area, 3),
        "populacao": pop,
        "densidade": dens,
        "renda_pc": int(round(renda_pc)) if renda_pc and not pd.isna(renda_pc) else None,
        "escolaridade": round(escol, 1) if escol and not pd.isna(escol) else None,
        "emprego_formal": emp_estimado,
        "perfil": perfil(renda_pc or 0, dens, area),
        "fonte": "IBGE Censo 2022 (agregados por bairro)",
        "emprego_formal_estimado": True,
        "fonte_emprego": f"IBGE/CEMPRE {ano_emprego} (tabela 9509, pessoal ocupado assalariado) "
                          f"— total municipal ({emprego_total_mun:,.0f}) distribuído proporcionalmente à população",
    }

sem_renda = [v["nome"] for v in saida.values() if v["renda_pc"] is None]
sem_escol = [v["nome"] for v in saida.values() if v["escolaridade"] is None]
if sem_renda:
    print(f"  bairros sem renda (sigilo estatístico, poucos domicílios): {sem_renda}")
if sem_escol:
    print(f"  bairros sem escolaridade (sigilo estatístico): {sem_escol}")

codigos = [v for v in saida]
assert len(codigos) == len(set(codigos)), "Códigos de bairro colidiram ao truncar CD_BAIRRO"

out_json = PROJ / "dados_bairros.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=2)
print(f"\n✓ Salvo: {out_json}  ({len(saida)} bairros)")

# ─── 7. Geometria (mesma malha usada para agregar os dados) ────────────────
print("\n=== 6. Gerando Limites_dos_Bairros.geojson (malha oficial IBGE) ===")
gdf_out = gdf_bairros.copy()
gdf_out["codigobairro"] = gdf_out["CD_BAIRRO"].str[-3:].astype(int)
gdf_out["nome"] = gdf_out["NM_BAIRRO"]
gdf_out = gdf_out[["codigobairro", "nome", "geometry"]]

out_geojson = PROJ / "Limites_dos_Bairros.geojson"
gdf_out.to_file(out_geojson, driver="GeoJSON")
print(f"✓ Salvo: {out_geojson}  ({len(gdf_out)} bairros)")

# ─── 8. Resumo ───────────────────────────────────────────────────────────────
print(f"\npop total: {sum(v['populacao'] for v in saida.values()):,}")
rendas = [v["renda_pc"] for v in saida.values() if v["renda_pc"]]
print(f"renda média geral: R$ {sum(rendas)/len(rendas):.0f}")

print("\nTop 5 renda:")
for cod, v in sorted(saida.items(), key=lambda x: x[1]["renda_pc"] or 0, reverse=True)[:5]:
    print(f"  [{cod}] {v['nome']}: R$ {v['renda_pc']:,} | pop={v['populacao']:,} | dens={v['densidade']:.0f}/km²")

print("\nTop 5 população:")
for cod, v in sorted(saida.items(), key=lambda x: x[1]["populacao"], reverse=True)[:5]:
    print(f"  [{cod}] {v['nome']}: pop={v['populacao']:,} | R${v['renda_pc']:,}")

"""
Eleições 2026 em Caxias do Sul, no grão do local de votação.

Fontes:
- TSE, votação por seção (presidente, arquivo nacional; deputado federal, arquivo do RS)
- TSE, eleitorado por local de votação (coordenadas)
- IBGE Censo 2022, agregados e malha de setores (renda do responsável, população,
  favelas e comunidades urbanas — atributo NM_FCU)
- Prefeitura de Caxias do Sul, Lei 8.741/2021, limites dos bairros
  (shapefile já no repositório) e ZEIS do PDDI (dadosabertos.caxias.rs.gov.br)

O JSON gerado alimenta os indicadores eleitorais de index.html.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy import stats
from shapely.geometry import box

PROJ = Path(__file__).parent
CACHE = PROJ / "_cache_tse"
IBGE = PROJ / "_cache_ibge"
MUN_IBGE = "4305108"
SIGLA = {
    "10": "REPUBLICANOS", "11": "PP", "12": "PDT", "13": "PT", "14": "MISSÃO",
    "15": "MDB", "16": "PSTU", "18": "REDE", "20": "PODE", "22": "PL",
    "23": "CIDADANIA", "25": "PRD", "27": "DC", "30": "NOVO", "35": "DEMOCRATA",
    "36": "AGIR", "40": "PSB", "43": "PV", "44": "UNIÃO", "45": "PSDB",
    "50": "PSOL", "55": "PSD", "65": "PCdoB", "70": "AVANTE", "77": "SOLIDARIEDADE",
    "80": "UP",
}
NOME_PARTIDO = {
    "10": "Republicanos", "11": "Progressistas", "12": "PDT", "13": "PT",
    "14": "Partido Missão", "15": "MDB", "16": "PSTU", "18": "Rede",
    "20": "Podemos", "22": "PL", "23": "Cidadania", "25": "PRD", "27": "DC",
    "30": "Novo", "35": "Democrata", "36": "Agir", "40": "PSB", "43": "PV",
    "44": "União Brasil", "45": "PSDB", "50": "PSOL", "55": "PSD",
    "65": "PCdoB", "70": "Avante", "77": "Solidariedade", "80": "UP",
}


def como_lista(valor) -> list:
    if isinstance(valor, (list, tuple)):
        return [x for x in valor if isinstance(x, str) and x]
    if isinstance(valor, str):
        return [p.strip() for p in valor.split("|") if p.strip()]
    return []


def titulo(texto: str) -> str:
    miudas = {"de", "da", "do", "das", "dos", "e"}
    partes = str(texto).strip().title().split()
    return " ".join(
        p if i == 0 or p.lower() not in miudas else p.lower()
        for i, p in enumerate(partes)
    )


def ler_votos(zip_path: Path, cargos: set[str]) -> pd.DataFrame:
    cols = [
        "NR_TURNO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO",
        "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO",
        "NM_LOCAL_VOTACAO", "DS_LOCAL_VOTACAO_ENDERECO",
    ]
    partes = []
    with zipfile.ZipFile(zip_path) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as f:
            for chunk in pd.read_csv(
                f, sep=";", dtype=str, encoding="latin1", usecols=cols, chunksize=500_000
            ):
                sub = chunk[chunk["NM_MUNICIPIO"].str.upper() == "CAXIAS DO SUL"]
                sub = sub[sub["CD_CARGO"].isin(cargos)]
                if len(sub):
                    partes.append(sub)
    if not partes:
        raise RuntimeError(f"Nenhum voto de Caxias em {zip_path.name} para cargos {cargos}")
    df = pd.concat(partes, ignore_index=True)
    for col in ("NR_TURNO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "QT_VOTOS"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["NR_VOTAVEL"] = df["NR_VOTAVEL"].str.replace(r"\.0$", "", regex=True)
    return df.dropna(subset=["NR_ZONA", "NR_LOCAL_VOTACAO", "QT_VOTOS"])


def codigo_partido(nr: str) -> str | None:
    if not nr or not str(nr).isdigit():
        return None
    if nr in {"95", "96", "97"}:
        return None
    if len(nr) <= 2:
        return nr.zfill(2)
    return nr.zfill(4)[:2]


def agregar_presidente(df: pd.DataFrame) -> pd.DataFrame:
    pres = df[df["CD_CARGO"] == "1"].copy()
    pres = pres[~pres["NR_VOTAVEL"].isin(["95", "96", "97"])]
    g = (
        pres.groupby(["NR_TURNO", "NR_ZONA", "NR_LOCAL_VOTACAO", "NR_VOTAVEL", "NM_VOTAVEL"], as_index=False)
        ["QT_VOTOS"].sum()
    )
    return g


def agregar_deputado(df: pd.DataFrame) -> pd.DataFrame:
    dep = df[(df["CD_CARGO"] == "6") & (df["NR_TURNO"] == 1)].copy()
    dep["partido"] = dep["NR_VOTAVEL"].map(codigo_partido)
    dep = dep.dropna(subset=["partido"])
    g = (
        dep.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO", "partido"], as_index=False)
        ["QT_VOTOS"].sum()
    )
    return g


def resumo_presidente(grupo: pd.DataFrame) -> dict:
    grupo = grupo.sort_values("QT_VOTOS", ascending=False)
    validos = int(grupo["QT_VOTOS"].sum())
    topo = grupo.iloc[0]
    votos = {str(r.NR_VOTAVEL): int(r.QT_VOTOS) for r in grupo.itertuples()}
    lula = votos.get("13", 0)
    flavio = votos.get("22", 0)
    urna = {"13": "Lula", "22": "Flávio Bolsonaro"}

    def pct(v):
        return round(100 * v / validos, 2) if validos else None

    return {
        "vencedor": urna.get(str(topo.NR_VOTAVEL), titulo(str(topo.NM_VOTAVEL))),
        "numero": str(topo.NR_VOTAVEL),
        "partido": SIGLA.get(str(topo.NR_VOTAVEL), ""),
        "votos": int(topo.QT_VOTOS),
        "pct": pct(int(topo.QT_VOTOS)),
        "validos": validos,
        "lula": lula,
        "flavio": flavio,
        "lula_pct": pct(lula),
        "flavio_pct": pct(flavio),
    }


def ler_locais() -> pd.DataFrame:
    zpath = CACHE / "eleitorado_local_votacao_2026.zip"
    with zipfile.ZipFile(zpath) as z:
        with z.open("eleitorado_local_votacao_2026_RS.csv") as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding="latin1")
    df = df[df["NM_MUNICIPIO"].str.upper() == "CAXIAS DO SUL"].copy()
    for col in ("NR_ZONA", "NR_LOCAL_VOTACAO", "NR_SECAO", "QT_ELEITOR_SECAO"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["NR_LATITUDE"] = pd.to_numeric(df["NR_LATITUDE"].str.replace(",", "."), errors="coerce")
    df["NR_LONGITUDE"] = pd.to_numeric(df["NR_LONGITUDE"].str.replace(",", "."), errors="coerce")
    # Um local pode repetir por seção e, às vezes, por turno. Fica a coordenada válida.
    ok = df["NR_LATITUDE"].between(-30.2, -28.6) & df["NR_LONGITUDE"].between(-51.8, -50.6)
    df["_coord_ok"] = ok
    df["NR_TURNO"] = pd.to_numeric(df["NR_TURNO"], errors="coerce")
    # A mesma seção aparece nos dois turnos. Eleitores e seções entram uma vez.
    df = df.sort_values(["_coord_ok", "NR_TURNO"], ascending=[False, False])
    df = df.drop_duplicates(["NR_ZONA", "NR_LOCAL_VOTACAO", "NR_SECAO"])
    locais = (
        df.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO"], as_index=False)
        .agg(
            nome=("NM_LOCAL_VOTACAO", "first"),
            endereco=("DS_ENDERECO", "first"),
            bairro_tse=("NM_BAIRRO", "first"),
            lat=("NR_LATITUDE", "first"),
            lon=("NR_LONGITUDE", "first"),
            eleitores=("QT_ELEITOR_SECAO", "sum"),
            secoes=("NR_SECAO", "nunique"),
            coord_ok=("_coord_ok", "max"),
        )
    )
    return locais


def num(serie: pd.Series) -> pd.Series:
    """Aceita decimal com ponto (arquivos de setor) ou com vírgula (arquivos de bairro)."""
    s = serie.astype(str).str.strip()
    virgula = s.str.contains(",", na=False)
    s = s.where(~virgula, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


def chave_nome(texto: str) -> str:
    import unicodedata
    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return " ".join(base.replace("-", " ").split())


def nome_exibicao(texto: str, ibge_por_chave: dict[str, str]) -> str:
    """A malha da lei vem sem acento em parte dos nomes. Reaproveita o nome do IBGE quando é o mesmo bairro."""
    k = chave_nome(texto)
    manual = {
        "sao pelegrino": "São Pelegrino",
        "por do sol": "Pôr do Sol",
        "seculo xx": "Século XX",
        "santa lucia": "Santa Lúcia",
        "nossa senhora da conceicao": "Nossa Senhora da Conceição",
        "jardim iracema": "Jardim Iracema",
        "jardim das hortensias": "Jardim das Hortênsias",
        "colina sorriso": "Colina Sorriso",
        "vila lobos": "Vila Lobos",
        "vila verde": "Vila Verde",
        "belo horizonte": "Belo Horizonte",
    }
    if k in manual:
        return manual[k]
    if k in ibge_por_chave:
        return ibge_por_chave[k]
    return titulo(texto)


def indicadores_municipais(mun: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    """Recorta população, renda e alfabetização do IBGE sobre o bairro da Lei 8.741."""
    shp = next((IBGE / "shp_rs").glob("*.shp"))
    setores = gpd.read_file(shp)
    setores = setores[setores["CD_MUN"] == MUN_IBGE].to_crs(4326).copy()

    with zipfile.ZipFile(IBGE / "basico.zip") as z:
        bas = pd.read_csv(z.open(z.namelist()[0]), sep=";", dtype=str, encoding="latin1")
    bas.columns = [c.strip('"') for c in bas.columns]
    bas = bas[bas["CD_MUN"] == MUN_IBGE][["CD_SETOR", "v0001", "NM_BAIRRO", "NM_FCU"]].copy()
    bas["pop"] = num(bas["v0001"])

    with zipfile.ZipFile(IBGE / "renda.zip") as z:
        renda = pd.read_csv(z.open(z.namelist()[0]), sep=";", dtype=str, encoding="latin1")
    renda.columns = [c.strip('"') for c in renda.columns]
    renda["CD_SETOR"] = renda["CD_SETOR"].str.replace(r"\.0$", "", regex=True)
    renda["responsaveis"] = num(renda["V06001"])
    renda["renda_resp"] = num(renda["V06004"])

    dados = json.loads((PROJ / "dados_bairros.json").read_text(encoding="utf-8"))
    escol_por_nome = {chave_nome(v["nome"]): v["escolaridade"] for v in dados.values()}

    setores = setores.merge(bas[["CD_SETOR", "pop"]], on="CD_SETOR", how="left")
    setores = setores.merge(renda[["CD_SETOR", "responsaveis", "renda_resp"]], on="CD_SETOR", how="left")
    setores["escolaridade_ibge"] = setores["NM_BAIRRO"].map(
        lambda s: escol_por_nome.get(chave_nome(s)) if isinstance(s, str) else None
    )
    setores["fcu"] = setores["NM_FCU"].fillna("").str.strip()

    cent = setores.copy()
    cent["geometry"] = cent.geometry.representative_point()
    dentro = gpd.sjoin(
        cent[["CD_SETOR", "pop", "responsaveis", "renda_resp", "escolaridade_ibge", "fcu", "NM_BAIRRO", "geometry"]],
        mun[["nome", "geometry"]],
        how="inner",
        predicate="within",
    )

    def renda_pond(g):
        m = g["renda_resp"].notna() & g["responsaveis"].gt(0)
        if not m.any():
            return np.nan
        return np.average(g.loc[m, "renda_resp"], weights=g.loc[m, "responsaveis"])

    def escol_pond(g):
        m = g["escolaridade_ibge"].notna() & g["pop"].gt(0)
        if not m.any():
            return np.nan
        return np.average(g.loc[m, "escolaridade_ibge"], weights=g.loc[m, "pop"])

    linhas = []
    for nome, g in dentro.groupby("nome"):
        fcus = sorted({x for x in g["fcu"] if x})
        linhas.append({
            "nome": nome,
            "populacao_ibge": int(g["pop"].fillna(0).sum()),
            "renda_responsavel": None if pd.isna(renda_pond(g)) else int(round(renda_pond(g))),
            "escolaridade": None if pd.isna(escol_pond(g)) else round(float(escol_pond(g)), 1),
            "fcu_nomes": fcus,
            "favela": bool(fcus),
            "setores": int(len(g)),
            "cobertura_renda": round(100 * g.loc[g["renda_resp"].notna(), "responsaveis"].sum() / g["responsaveis"].sum(), 1)
            if g["responsaveis"].sum() else 0,
        })
    ind = pd.DataFrame(linhas)
    mun = mun.merge(ind, on="nome", how="left")
    mun["populacao_ibge"] = mun["populacao_ibge"].fillna(0).astype(int)
    mun["area_km2"] = (mun.to_crs(31982).area / 1e6).round(3)
    mun["densidade"] = (mun["populacao_ibge"] / mun["area_km2"]).round(1)

    # Periferia: leitura do IBGE, não uma classe oficial.
    # Bairro urbano (não é distrito rural extenso) no quartil inferior da renda do responsável.
    urbano = mun["area_km2"].lt(20) & mun["densidade"].ge(500) & mun["renda_responsavel"].notna()
    corte = mun.loc[urbano, "renda_responsavel"].quantile(0.25)
    mun["periferia"] = urbano & mun["renda_responsavel"].le(corte)
    mun["corte_renda_periferia"] = int(corte)

    fcu = setores[setores["fcu"] != ""].copy()
    fcu_diss = fcu.dissolve(by="fcu", aggfunc={"pop": "sum"})
    fcu_diss = fcu_diss.reset_index().rename(columns={"fcu": "nome", "pop": "populacao"})
    fcu_diss["populacao"] = fcu_diss["populacao"].fillna(0).astype(int)
    fcu_diss["geometry"] = fcu_diss.geometry.simplify(0.00008, preserve_topology=True)

    auditoria_fcu = {
        "n_comunidades": int(len(fcu_diss)),
        "populacao": int(fcu_diss["populacao"].sum()),
        "nomes": fcu_diss.sort_values("populacao", ascending=False)[["nome", "populacao"]]
        .to_dict("records"),
    }
    return mun, fcu_diss, auditoria_fcu


def carregar_zeis() -> gpd.GeoDataFrame:
    """ZEIS do PDDI. O serviço da prefeitura listado no portal responde 500 na consulta."""
    url = (
        "https://gis.caxias.rs.gov.br/server/rest/services/Hosted/ZoneamentoUrbano/"
        "FeatureServer/40/query"
    )
    try:
        r = requests.get(url, params={
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": 200,
        }, timeout=40)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        features = data.get("features") or []
        if not features:
            raise RuntimeError("camada ZEIS sem feições")
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        gdf["geometry"] = gdf.geometry.simplify(0.0001, preserve_topology=True)
        return gdf
    except Exception as exc:
        print(f"  ZEIS indisponível ({exc.__class__.__name__}). O mapa segue sem essa camada.")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


def auditar_ibge(mun: gpd.GeoDataFrame) -> dict:
    dados = json.loads((PROJ / "dados_bairros.json").read_text(encoding="utf-8"))
    ibge_por_chave = {}
    for v in dados.values():
        ibge_por_chave.setdefault(chave_nome(v["nome"]), v["nome"])
    oficiais_por_chave = {}
    for nome in mun["nome"]:
        oficiais_por_chave.setdefault(chave_nome(nome), nome)
    pop_json = sum(v["populacao"] for v in dados.values())
    ratios = {
        round(v["emprego_formal"] / v["populacao"], 5)
        for v in dados.values() if v["populacao"]
    }
    escol = [v["escolaridade"] for v in dados.values() if v["escolaridade"] is not None]
    return {
        "bairros_ibge": len(dados),
        "bairros_lei_8741": int(len(mun)),
        "so_na_lei": sorted(
            oficiais_por_chave[k] for k in oficiais_por_chave.keys() - ibge_por_chave.keys()
        ),
        "so_no_ibge": sorted(
            ibge_por_chave[k] for k in ibge_por_chave.keys() - oficiais_por_chave.keys()
        ),
        "populacao_malha_ibge": pop_json,
        "populacao_sobre_bairros_oficiais": int(mun["populacao_ibge"].sum()),
        "escolaridade_min": min(escol),
        "escolaridade_max": max(escol),
        "escolaridade_quase_100": sum(v >= 99.5 for v in escol),
        "emprego_e_proporcional_a_populacao": max(ratios) - min(ratios) < 0.002,
        "renda_e_do_responsavel": True,
        "nota_renda": (
            "V06004 do Censo 2022 é o rendimento nominal médio mensal das pessoas "
            "responsáveis com rendimento, não a renda per capita."
        ),
        "nota_escolaridade": (
            "Percentual de pessoas alfabetizadas de 15 anos ou mais. As faixas de "
            "alfabetização (V00644–V00656) e de demografia (V01034–V01041) cobrem "
            "a mesma população de 15+, em agrupamentos diferentes. Em Caxias o "
            "indicador fica entre 96,3% e 100% — variação pequena, esperada numa "
            "cidade do Sul com alfabetização quase universal."
        ),
        "nota_emprego": (
            "Não existe emprego formal por bairro na fonte pública usada. O valor "
            "do mapa atual reparte o total municipal do CEMPRE pela população, "
            "então não distingue a economia de um bairro da de outro."
        ),
        "nota_malha": (
            "A malha do IBGE tem 65 bairros estatísticos. A Lei municipal 8.741/2021 "
            "delimita 77. Os nomes divergem em São Pelegrino (lei) / São Peregrino "
            "(IBGE) e em Jardim das Hortênsias / Hortências, e 15 bairros da lei não "
            "têm polígono próprio no IBGE. Neste mapa os indicadores foram "
            "reagregados pelos setores censitários sobre o polígono da lei."
        ),
        "dados_abertos_municipio": (
            "O portal dadosabertos.caxias.rs.gov.br (ArcGIS Hub da DIGEO) publica a "
            "malha da Lei 8.741, o Censo 2022 por setor, o zoneamento do PDDI "
            "(incluindo a ZEIS) e o mapa de população por bairro. Não publica "
            "RAIS/CAGED nem renda por bairro além do que o IBGE já divulga."
        ),
        "nota_zeis": (
            "A camada ZEIS do PDDI (Lei 589/2019, layer 40 do zoneamento) consta no "
            "portal, mas em 28/10/2026 a consulta ao FeatureServer devolveu erro de "
            "banco. A classificação deste mapa usa as comunidades do IBGE e o quartil "
            "de renda, sem o polígono da ZEIS. ZEIS não é o mesmo que favela."
        ),
    }


def correlacao(locais: list[dict]) -> dict:
    rows = [
        x for x in locais
        if x.get("renda") and x.get("t2") and x["t2"].get("flavio_pct") is not None
    ]
    renda = np.array([x["renda"] for x in rows], dtype=float)
    flavio = np.array([x["t2"]["flavio_pct"] for x in rows], dtype=float)
    pesos = np.array([x["t2"]["validos"] for x in rows], dtype=float)
    spearman = stats.spearmanr(renda, flavio)

    # Uma observação por bairro do IBGE, para não repetir a mesma renda.
    por_bairro: dict[str, dict] = {}
    for x in rows:
        b = x.get("bairro_ibge") or x["bairro"]
        slot = por_bairro.setdefault(b, {"flavio": 0, "validos": 0, "renda": x["renda"]})
        slot["flavio"] += x["t2"]["flavio"]
        slot["validos"] += x["t2"]["validos"]
    bairros = [v for v in por_bairro.values() if v["validos"] > 0]
    br = np.array([v["renda"] for v in bairros], dtype=float)
    bf = np.array([100 * v["flavio"] / v["validos"] for v in bairros], dtype=float)
    bw = np.array([v["validos"] for v in bairros], dtype=float)
    spearman_b = stats.spearmanr(br, bf)

    def pearson_pond(x, y, w):
        w = w / w.sum()
        mx, my = np.sum(w * x), np.sum(w * y)
        cov = np.sum(w * (x - mx) * (y - my))
        sx = np.sqrt(np.sum(w * (x - mx) ** 2))
        sy = np.sqrt(np.sum(w * (y - my) ** 2))
        return float(cov / (sx * sy)) if sx and sy else None

    ordem = np.argsort(renda)
    n = len(rows)
    quartis = []
    rotulos = ["1º quartil · menor renda", "2º quartil", "3º quartil", "4º quartil · maior renda"]
    for i, rotulo in enumerate(rotulos):
        fatia = ordem[int(i * n / 4): int((i + 1) * n / 4)]
        if len(fatia) == 0:
            continue
        vv = pesos[fatia].sum()
        flavio_v = sum(rows[j]["t2"]["flavio"] for j in fatia)
        lula_v = sum(rows[j]["t2"]["lula"] for j in fatia)
        quartis.append({
            "rotulo": rotulo,
            "n_locais": int(len(fatia)),
            "renda_min": int(renda[fatia].min()),
            "renda_max": int(renda[fatia].max()),
            "pct_flavio": round(100 * flavio_v / vv, 1),
            "pct_lula": round(100 * lula_v / vv, 1),
        })

    def bloco(pred):
        sel = [x for x in rows if pred(x)]
        vv = sum(x["t2"]["validos"] for x in sel) or 1
        return {
            "n_locais": len(sel),
            "pct_flavio": round(100 * sum(x["t2"]["flavio"] for x in sel) / vv, 1),
            "pct_lula": round(100 * sum(x["t2"]["lula"] for x in sel) / vv, 1),
        }

    favela = bloco(lambda x: x.get("favela"))
    resto = bloco(lambda x: not x.get("favela"))
    peri = bloco(lambda x: x.get("periferia"))
    return {
        "n_locais": int(len(rows)),
        "n_bairros_ibge": int(len(bairros)),
        "spearman_locais": round(float(spearman.statistic), 3),
        "spearman_locais_p": float(spearman.pvalue),
        "spearman_bairros": round(float(spearman_b.statistic), 3),
        "spearman_bairros_p": float(spearman_b.pvalue),
        "pearson_ponderado_bairros": round(pearson_pond(br, bf, bw), 3),
        "quartis": quartis,
        "favela": favela,
        "fora_de_favela": resto,
        "periferia": peri,
    }


def main():
    print("=== votos ===")
    pres = agregar_presidente(ler_votos(CACHE / "votacao_secao_2026_BR.zip", {"1"}))
    dep = agregar_deputado(ler_votos(CACHE / "votacao_secao_2026_RS.zip", {"6"}))
    print(f"  presidente: {len(pres):,} linhas de local/candidato  turnos {sorted(pres.NR_TURNO.unique())}")
    print(f"  deputado federal: {len(dep):,} linhas de local/partido")

    totais = {}
    for turno, nome_a, nome_b, num_a, num_b in (
        (1, "flavio", "lula", "22", "13"),
        (2, "flavio", "lula", "22", "13"),
    ):
        fat = pres[pres["NR_TURNO"] == turno]
        totais[f"t{turno}"] = {
            nome_a: int(fat.loc[fat["NR_VOTAVEL"] == num_a, "QT_VOTOS"].sum()),
            nome_b: int(fat.loc[fat["NR_VOTAVEL"] == num_b, "QT_VOTOS"].sum()),
            "validos": int(fat["QT_VOTOS"].sum()),
        }
        print(f"  turno {turno}: {totais[f't{turno}']}")

    locais_df = ler_locais()
    print(f"  locais no cadastro: {len(locais_df)}  com coordenada: {int(locais_df.coord_ok.sum())}")

    print("=== território ===")
    mun = gpd.read_file(PROJ / "Limites_dos_Bairros.zip").to_crs(4326)
    dados = json.loads((PROJ / "dados_bairros.json").read_text(encoding="utf-8"))
    ibge_por_chave = {}
    renda_ibge = {}
    for v in dados.values():
        chave = chave_nome(v["nome"])
        ibge_por_chave.setdefault(chave, v["nome"])
        renda_ibge[chave] = v["renda_pc"]
    mun["nome"] = mun["nome"].map(lambda s: nome_exibicao(s, ibge_por_chave))
    repetidos = mun.loc[mun["nome"].duplicated(), "nome"].tolist()
    if repetidos:
        raise RuntimeError(f"nomes de bairro repetidos depois do acento: {repetidos}")
    mun, fcu, auditoria_fcu = indicadores_municipais(mun)
    zeis = carregar_zeis()
    print(f"  ZEIS: {len(zeis)} polígonos")
    if len(zeis):
        bate = gpd.sjoin(mun[["nome", "geometry"]], zeis[["geometry"]], how="inner", predicate="intersects")
        mun["zeis"] = mun["nome"].isin(set(bate["nome"]))
    else:
        mun["zeis"] = False

    ibge_shp = next((IBGE / "RS_bairros").rglob("*.shp"))
    ibge = gpd.read_file(ibge_shp)
    ibge = ibge[ibge["CD_MUN"] == MUN_IBGE].to_crs(4326)

    pontos = locais_df[locais_df["coord_ok"]].copy()
    pontos = gpd.GeoDataFrame(
        pontos,
        geometry=gpd.points_from_xy(pontos["lon"], pontos["lat"]),
        crs="EPSG:4326",
    )
    pontos = gpd.sjoin(pontos, mun[["nome", "renda_responsavel", "escolaridade", "periferia", "favela", "zeis", "fcu_nomes", "geometry"]], how="left", predicate="within")
    pontos = pontos.rename(columns={"nome_right": "bairro"})
    pontos = pontos.drop(columns=[c for c in pontos.columns if c.startswith("index_")], errors="ignore")
    # sjoin pode duplicar ponto na borda; fica o primeiro
    pontos = pontos.drop_duplicates(["NR_ZONA", "NR_LOCAL_VOTACAO"])
    pontos["dist_bairro_m"] = 0.0
    pontos["bairro_aproximado"] = False
    sem_bairro = pontos["bairro"].isna()
    if sem_bairro.any():
        # Distância em metros. Em graus, o sjoin_nearest erra o vizinho.
        origem = pontos.loc[sem_bairro, ["NR_ZONA", "NR_LOCAL_VOTACAO", "geometry"]].to_crs(31982)
        origem = origem.reset_index().rename(columns={"index": "_idx"})
        mun_m = mun.to_crs(31982)
        perto = gpd.sjoin_nearest(
            origem,
            mun_m[["nome", "renda_responsavel", "escolaridade", "periferia", "favela", "zeis", "fcu_nomes", "geometry"]],
            how="left",
            distance_col="dist_m",
        )
        perto = perto.drop(columns=[c for c in perto.columns if str(c).startswith("index_")], errors="ignore")
        perto = perto.drop_duplicates(["NR_ZONA", "NR_LOCAL_VOTACAO"])
        longe = perto["dist_m"].fillna(9e9) > 1500
        perto.loc[longe, ["periferia", "favela", "zeis"]] = False
        perto.loc[longe, ["renda_responsavel", "escolaridade"]] = np.nan
        nomes_fcu = [
            [] if eh_longe else como_lista(valor)
            for valor, eh_longe in zip(perto["fcu_nomes"], longe)
        ]
        for (_, row), nomes in zip(perto.iterrows(), nomes_fcu):
            idx = row["_idx"]
            pontos.at[idx, "bairro"] = row["nome"]
            pontos.at[idx, "renda_responsavel"] = row["renda_responsavel"]
            pontos.at[idx, "escolaridade"] = row["escolaridade"]
            pontos.at[idx, "periferia"] = bool(row["periferia"]) if pd.notna(row["periferia"]) else False
            pontos.at[idx, "favela"] = bool(row["favela"]) if pd.notna(row["favela"]) else False
            pontos.at[idx, "zeis"] = bool(row["zeis"]) if pd.notna(row["zeis"]) else False
            pontos.at[idx, "fcu_nomes"] = nomes
            pontos.at[idx, "dist_bairro_m"] = float(row["dist_m"])
            pontos.at[idx, "bairro_aproximado"] = True
        print(f"  locais fora do polígono, atribuídos ao bairro mais próximo: {int(sem_bairro.sum())}")
        print(f"  distância máxima dessa atribuição: {perto['dist_m'].max():.0f} m")
        print(f"  atribuições além de 1,5 km (sem copiar periferia nem favela): {int(longe.sum())}")
    ibge_s = gpd.sjoin(
        pontos[["NR_ZONA", "NR_LOCAL_VOTACAO", "geometry"]],
        ibge[["NM_BAIRRO", "geometry"]],
        how="left",
        predicate="within",
    ).drop_duplicates(["NR_ZONA", "NR_LOCAL_VOTACAO"])
    pontos = pontos.merge(
        ibge_s[["NR_ZONA", "NR_LOCAL_VOTACAO", "NM_BAIRRO"]],
        on=["NR_ZONA", "NR_LOCAL_VOTACAO"],
        how="left",
    )
    def nome_ibge(valor):
        if not isinstance(valor, str):
            return None
        return ibge_por_chave.get(chave_nome(valor), titulo(valor))

    pontos["bairro_ibge"] = pontos["NM_BAIRRO"].map(nome_ibge)
    pontos["renda_ibge"] = pontos["NM_BAIRRO"].map(
        lambda s: renda_ibge.get(chave_nome(s)) if isinstance(s, str) else None
    )

    # Dentro de uma comunidade urbana, mesmo que o bairro inteiro não seja favela.
    if len(fcu):
        dentro_fcu = gpd.sjoin(
            pontos[["NR_ZONA", "NR_LOCAL_VOTACAO", "geometry"]],
            fcu[["nome", "geometry"]],
            how="left",
            predicate="within",
        ).drop_duplicates(["NR_ZONA", "NR_LOCAL_VOTACAO"])
        pontos = pontos.merge(
            dentro_fcu[["NR_ZONA", "NR_LOCAL_VOTACAO", "nome"]].rename(columns={"nome": "fcu_local"}),
            on=["NR_ZONA", "NR_LOCAL_VOTACAO"],
            how="left",
        )
    else:
        pontos["fcu_local"] = None

    def turno_do_local(zona, local, turno):
        g = pres[(pres.NR_TURNO == turno) & (pres.NR_ZONA == zona) & (pres.NR_LOCAL_VOTACAO == local)]
        if g.empty:
            return None
        return resumo_presidente(g)

    def dep_do_local(zona, local):
        g = dep[(dep.NR_ZONA == zona) & (dep.NR_LOCAL_VOTACAO == local)]
        if g.empty:
            return None
        g = g.sort_values("QT_VOTOS", ascending=False)
        validos = int(g["QT_VOTOS"].sum())
        topo = g.iloc[0]
        codigo = str(topo.partido)
        return {
            "sigla": SIGLA.get(codigo, codigo),
            "nome": NOME_PARTIDO.get(codigo, codigo),
            "numero": codigo,
            "votos": int(topo.QT_VOTOS),
            "pct": round(100 * int(topo.QT_VOTOS) / validos, 1) if validos else None,
            "validos": validos,
        }

    locais = []
    sem_coord = 0
    for row in locais_df.itertuples(index=False):
        zona, local = int(row.NR_ZONA), int(row.NR_LOCAL_VOTACAO)
        t1, t2 = turno_do_local(zona, local, 1), turno_do_local(zona, local, 2)
        if t1 is None and t2 is None:
            continue
        extra = pontos[(pontos.NR_ZONA == zona) & (pontos.NR_LOCAL_VOTACAO == local)]
        info = extra.iloc[0] if len(extra) else None
        if not row.coord_ok or info is None:
            sem_coord += 1
            continue
        fcu_nomes = como_lista(info.fcu_nomes)
        fcu_local = info.fcu_local if isinstance(getattr(info, "fcu_local", None), str) else None
        aproximado = bool(getattr(info, "bairro_aproximado", False))
        dist_m = getattr(info, "dist_bairro_m", 0)
        locais.append({
            "id": f"{zona}-{local}",
            "zona": zona,
            "local": local,
            "nome": titulo(row.nome),
            "endereco": titulo(row.endereco) if isinstance(row.endereco, str) else "",
            "bairro_tse": titulo(row.bairro_tse) if isinstance(row.bairro_tse, str) else "",
            "bairro": info.bairro if isinstance(info.bairro, str) else "",
            "bairro_ibge": info.bairro_ibge if isinstance(info.bairro_ibge, str) else None,
            "bairro_aproximado": aproximado,
            "dist_bairro_m": int(round(float(dist_m))) if aproximado and pd.notna(dist_m) else None,
            "lat": round(float(row.lat), 6),
            "lon": round(float(row.lon), 6),
            "eleitores": int(row.eleitores or 0),
            "secoes": int(row.secoes or 0),
            "renda": int(info.renda_ibge) if pd.notna(info.renda_ibge) else (
                int(info.renda_responsavel) if pd.notna(info.renda_responsavel) else None
            ),
            "escolaridade": None if pd.isna(info.escolaridade) else float(info.escolaridade),
            # Favela no local só quando o ponto cai dentro do polígono da comunidade.
            "favela": bool(fcu_local),
            "fcu": fcu_local,
            "fcu_no_bairro": fcu_nomes,
            "periferia": bool(info.periferia) if pd.notna(info.periferia) else False,
            "zeis": bool(info.zeis) if pd.notna(info.zeis) else False,
            "t1": t1,
            "t2": t2,
            "deputado": dep_do_local(zona, local),
        })

    print(f"  locais no mapa: {len(locais)}  sem coordenada ou sem voto: {sem_coord}")

    def placar(chave):
        from collections import Counter
        c = Counter()
        for x in locais:
            bloco = x.get(chave)
            if bloco:
                c[bloco["vencedor"]] += 1
        return dict(c)

    analise = correlacao(locais)
    q1, q4 = analise["quartis"][0], analise["quartis"][-1]
    diff = round(q4["pct_flavio"] - q1["pct_flavio"], 1)
    if abs(analise["spearman_bairros"]) < 0.2:
        forca = "fraca"
    elif abs(analise["spearman_bairros"]) < 0.4:
        forca = "moderada"
    else:
        forca = "forte"
    def br(valor, casas=1):
        return f"{valor:.{casas}f}".replace(".", ",")

    sinal = f"{diff:+.1f}".replace(".", ",")
    if q1["pct_flavio"] > 50 and q4["pct_flavio"] > 50:
        efeito = (
            f"A renda não muda quem vence: Flávio Bolsonaro ficou à frente nos quatro "
            f"quartis. Ela muda a margem. No quartil de menor renda, ele teve "
            f"{br(q1['pct_flavio'])}% dos votos válidos dos locais; no de maior renda, "
            f"{br(q4['pct_flavio'])}% ({sinal} pontos)."
        )
    else:
        efeito = (
            f"No quartil de menor renda, Flávio teve {br(q1['pct_flavio'])}% dos votos "
            f"válidos dos locais; no de maior renda, {br(q4['pct_flavio'])}% ({sinal} pontos)."
        )
    fav = analise["favela"]
    fora = analise["fora_de_favela"]
    peri = analise["periferia"]
    dentro = [x for x in locais if x.get("favela")]
    if dentro and len(dentro) <= 8:
        lista_fcu = "; ".join(f"{x['nome']}, na comunidade {x['fcu']}" for x in dentro)
        aviso_fcu = (
            f" São {len(dentro)} locais: {lista_fcu}. "
            f"O percentual descreve esses pontos."
        )
    else:
        aviso_fcu = ""
    p_txt = f"{analise['spearman_bairros_p']:.4f}"
    if analise["spearman_bairros_p"] < 0.0001:
        p_txt = "< 0,0001"
    analise["leitura"] = (
        f"A associação entre a renda do responsável pelo domicílio (Censo 2022) e o "
        f"percentual de Flávio Bolsonaro no 2º turno, medida entre bairros do IBGE, "
        f"é {forca} (Spearman = {br(analise['spearman_bairros'], 3)}, p {p_txt}). {efeito} "
        f"Nos locais que caem dentro de uma favela ou comunidade urbana do IBGE, "
        f"Flávio teve {br(fav['pct_flavio'])}% ({fav['n_locais']} locais); fora delas, "
        f"{br(fora['pct_flavio'])}% ({fora['n_locais']} locais).{aviso_fcu} "
        f"Nos locais de bairros urbanos do quartil inferior de renda, "
        f"{br(peri['pct_flavio'])}% ({peri['n_locais']} locais). "
        f"É correlação ecológica: a renda é do bairro em 2022, e o eleitor não vota "
        f"obrigatoriamente no bairro onde mora. O número não diz que a renda de uma "
        f"pessoa determina o voto dela."
    )

    renda_vals = [x["renda"] for x in locais if x.get("renda")]
    renda_max = max(renda_vals) if renda_vals else 0
    print(f"  renda máxima atribuída a um local: R$ {renda_max}")
    if renda_max > 25000:
        raise RuntimeError(
            f"renda ainda implausível para média mensal do responsável: {renda_max}"
        )
    referencia = {"t1": (166880, 71514), "t2": (182748, 92035)}
    for turno, (flavio_ref, lula_ref) in referencia.items():
        if totais[turno]["flavio"] != flavio_ref or totais[turno]["lula"] != lula_ref:
            raise RuntimeError(f"totais do turno {turno} divergem do TSE: {totais[turno]}")

    auditoria = auditar_ibge(mun)
    auditoria["favelas"] = auditoria_fcu
    auditoria["conferencia_tse"] = {
        "t1_flavio_lula": [totais["t1"]["flavio"], totais["t1"]["lula"]],
        "t2_flavio_lula": [totais["t2"]["flavio"], totais["t2"]["lula"]],
        "referencia_divulgada": {
            "t1": [166880, 71514],
            "t2": [182748, 92035],
        },
    }

    mun_out = mun.copy()
    mun_out["geometry"] = mun_out.geometry.simplify(0.00012, preserve_topology=True)
    mun_out["fcu_nomes"] = mun_out["fcu_nomes"].apply(
        lambda v: " | ".join(v) if isinstance(v, list) else ""
    )
    mun_out["periferia"] = mun_out["periferia"].fillna(False).astype(bool)
    mun_out["favela"] = mun_out["favela"].fillna(False).astype(bool)
    mun_out["zeis"] = mun_out["zeis"].fillna(False).astype(bool)
    keep = [
        "nome", "area_km2", "populacao_ibge", "densidade", "renda_responsavel",
        "escolaridade", "periferia", "favela", "zeis", "fcu_nomes", "geometry",
    ]
    mun_out[keep].to_file(PROJ / "bairros_oficiais.geojson", driver="GeoJSON")
    fcu.to_file(PROJ / "fcu_ibge.geojson", driver="GeoJSON")
    if len(zeis):
        zeis[["geometry"]].to_file(PROJ / "zeis.geojson", driver="GeoJSON")

    payload = {
        "meta": {
            "municipio": "Caxias do Sul",
            "eleicao": "Eleições gerais de 2026",
            "fontes": [
                "TSE, votação por seção eleitoral, 2026",
                "TSE, eleitorado por local de votação, 2026",
                "IBGE, Censo Demográfico 2022, setores e favelas e comunidades urbanas",
                "Prefeitura de Caxias do Sul, Lei 8.741/2021 e ZEIS do PDDI",
            ],
            "nota_periferia": (
                "Periferia aqui não é uma classe do IBGE. É o quartil inferior da "
                "renda do responsável entre os bairros urbanos da Lei 8.741 "
                "(área menor que 20 km² e densidade de pelo menos 500 hab/km²)."
            ),
            "nota_favela": (
                "Favela segue o recorte do IBGE de Favelas e Comunidades Urbanas. "
                "Vale o polígono da comunidade. Um bairro que contém uma comunidade "
                "não vira, inteiro, uma favela."
            ),
        },
        "corte_renda_periferia": int(mun["corte_renda_periferia"].dropna().iloc[0]),
        "totais": totais,
        "vencedores_locais": {"t1": placar("t1"), "t2": placar("t2")},
        "auditoria": auditoria,
        "analise": analise,
        "periferia": sorted(mun.loc[mun["periferia"] == True, "nome"].tolist()),
        "favelas_bairros": sorted(mun.loc[mun["favela"] == True, "nome"].tolist()),
        "zeis_bairros": sorted(mun.loc[mun["zeis"] == True, "nome"].tolist()),
        "locais": locais,
    }
    (PROJ / "dados_eleicao.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n✓ {len(locais)} locais → dados_eleicao.json")
    print("vencedores t1", payload["vencedores_locais"]["t1"])
    print("vencedores t2", payload["vencedores_locais"]["t2"])
    print("corte periferia", payload["corte_renda_periferia"])
    print(analise["leitura"])
    print("periferia", payload["periferia"])
    print("favelas (bairro contém comunidade)", payload["favelas_bairros"])
    print("só na lei", auditoria["so_na_lei"])
    print("só no ibge", auditoria["so_no_ibge"])
    lula_t2 = [
        (x["nome"], x["bairro"], x["t2"]["pct"], x["fcu"], x["periferia"])
        for x in locais if x.get("t2") and x["t2"]["numero"] == "13"
    ]
    print("locais do Lula no 2º turno", lula_t2)


if __name__ == "__main__":
    main()

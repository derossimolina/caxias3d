"""
Prefeito de 2024 em Caxias do Sul, no local de votação, e regressão
da renda sobre o voto de 2024 e de 2026.

A unidade da regressão é o bairro do IBGE. A renda não varia dentro do
bairro, então um ponto por local de votação só repetiria o mesmo número.
O peso é o total de votos válidos do bairro.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from pipeline_eleicoes import NOME_PARTIDO, SIGLA, chave_nome, codigo_partido, titulo

PROJ = Path(__file__).parent
ZIP_2024 = PROJ / "_cache_tse" / "votacao_secao_2024_RS.zip"
SAIDA = PROJ / "dados_eleicao.json"

REFERENCIA_T2 = {"adilo": 116730, "scalco": 110476}


def br(valor, casas=1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def p_txt(p: float) -> str:
    if p < 0.001:
        return "p < 0,001"
    return "p = " + f"{p:.3f}".replace(".", ",")


def nome_candidato(nm: str, partido: str) -> str:
    base = chave_nome(nm)
    if "adilo" in base:
        return "Adiló"
    if "scalco" in base:
        return "Scalco"
    if "denise" in base:
        return "Denise Pessôa"
    if "gremel" in base:
        return "Felipe Gremelmaier"
    return titulo(nm)


def ler_prefeito() -> pd.DataFrame:
    cols = [
        "NR_TURNO", "NM_MUNICIPIO", "NR_ZONA", "CD_CARGO",
        "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO",
    ]
    partes = []
    with zipfile.ZipFile(ZIP_2024) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as f:
            for chunk in pd.read_csv(
                f, sep=";", dtype=str, encoding="latin1", usecols=cols, chunksize=400_000
            ):
                sub = chunk[chunk["NM_MUNICIPIO"].str.upper() == "CAXIAS DO SUL"]
                sub = sub[sub["CD_CARGO"] == "11"]
                if len(sub):
                    partes.append(sub)
    if not partes:
        raise RuntimeError("Nenhum voto a prefeito de Caxias em 2024")
    df = pd.concat(partes, ignore_index=True)
    for col in ("NR_TURNO", "NR_ZONA", "NR_LOCAL_VOTACAO", "QT_VOTOS"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["NR_VOTAVEL"] = df["NR_VOTAVEL"].str.replace(r"\.0$", "", regex=True)
    df = df.dropna(subset=["NR_ZONA", "NR_LOCAL_VOTACAO", "QT_VOTOS"])
    df["partido"] = df["NR_VOTAVEL"].map(codigo_partido)
    df = df.dropna(subset=["partido"])
    return df


def resumo_turno(g: pd.DataFrame) -> dict:
    votos = (
        g.groupby(["partido", "NM_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()
        .sort_values("QT_VOTOS", ascending=False)
    )
    validos = int(votos["QT_VOTOS"].sum())
    topo = votos.iloc[0]
    codigo = str(topo.partido)

    def pct(v):
        return round(100 * int(v) / validos, 2) if validos else None

    def linha(partido_cod, apelido):
        fat = votos[votos["partido"] == partido_cod]
        v = int(fat["QT_VOTOS"].sum()) if len(fat) else 0
        return v, pct(v)

    adilo, adilo_pct = linha("45", "Adiló")
    scalco, scalco_pct = linha("22", "Scalco")
    por_partido = votos.groupby("partido")["QT_VOTOS"].sum()
    return {
        "vencedor": nome_candidato(str(topo.NM_VOTAVEL), codigo),
        "partido": SIGLA.get(codigo, codigo),
        "partido_nome": NOME_PARTIDO.get(codigo, codigo),
        "numero": codigo,
        "votos": int(topo.QT_VOTOS),
        "pct": pct(int(topo.QT_VOTOS)),
        "validos": validos,
        "adilo": adilo,
        "scalco": scalco,
        "adilo_pct": adilo_pct,
        "scalco_pct": scalco_pct,
        "votos_por_partido": {str(k): int(v) for k, v in por_partido.items()},
    }


def por_local(df: pd.DataFrame) -> dict[str, dict]:
    saida = {}
    for (zona, local), g in df.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO"]):
        bloco = {}
        for turno, gt in g.groupby("NR_TURNO"):
            bloco[f"t{int(turno)}"] = resumo_turno(gt)
        saida[f"{int(zona)}-{int(local)}"] = bloco
    return saida


def totais_cidade(df: pd.DataFrame) -> dict:
    out = {}
    for turno, g in df.groupby("NR_TURNO"):
        out[f"t{int(turno)}"] = resumo_turno(g)
    return out


def agregar_bairros(locais: list[dict], cov: dict[str, dict]) -> list[dict]:
    slots: dict[str, dict] = {}
    for loc in locais:
        nome = loc.get("bairro_ibge")
        if not isinstance(nome, str) or not nome:
            continue
        chave = chave_nome(nome)
        slot = slots.setdefault(chave, {
            "nome": cov.get(chave, {}).get("nome", nome),
            "flavio_t1": 0, "validos_pres_t1": 0,
            "flavio_t2": 0, "lula_t2": 0, "validos_pres_t2": 0,
            "scalco_t1": 0, "validos_pref_t1": 0,
            "votos_partido_t1": {},
            "scalco_t2": 0, "adilo_t2": 0, "validos_pref_t2": 0,
        })
        t1, t2 = loc.get("t1") or {}, loc.get("t2") or {}
        if t1.get("validos"):
            slot["flavio_t1"] += t1.get("flavio") or 0
            slot["validos_pres_t1"] += t1["validos"]
        if t2.get("validos"):
            slot["flavio_t2"] += t2.get("flavio") or 0
            slot["lula_t2"] += t2.get("lula") or 0
            slot["validos_pres_t2"] += t2["validos"]
        pref = loc.get("pref") or {}
        p1, p2 = pref.get("t1") or {}, pref.get("t2") or {}
        if p1.get("validos"):
            slot["scalco_t1"] += p1.get("scalco") or 0
            slot["validos_pref_t1"] += p1["validos"]
            for part, v in (p1.get("votos_por_partido") or {}).items():
                slot["votos_partido_t1"][part] = slot["votos_partido_t1"].get(part, 0) + int(v)
        if p2.get("validos"):
            slot["scalco_t2"] += p2.get("scalco") or 0
            slot["adilo_t2"] += p2.get("adilo") or 0
            slot["validos_pref_t2"] += p2["validos"]

    linhas = []
    for chave, slot in slots.items():
        base = cov.get(chave)
        if not base or base.get("renda_pc") is None or base.get("dist_centro_km") is None:
            continue
        if not slot["validos_pres_t2"] or not slot["validos_pref_t2"]:
            continue

        def pct(num, den):
            return round(100 * num / den, 2) if den else None

        partido_t1 = (
            max(slot["votos_partido_t1"], key=slot["votos_partido_t1"].get)
            if slot["votos_partido_t1"] else None
        )
        flavio = pct(slot["flavio_t2"], slot["validos_pres_t2"])
        scalco = pct(slot["scalco_t2"], slot["validos_pref_t2"])
        linhas.append({
            "nome": base["nome"],
            "renda": base["renda_pc"],
            "densidade": base["densidade"],
            "escolaridade": base["escolaridade"],
            "dist_centro_km": base["dist_centro_km"],
            "flavio_t1": pct(slot["flavio_t1"], slot["validos_pres_t1"]),
            "flavio_t2": flavio,
            "lula_t2": pct(slot["lula_t2"], slot["validos_pres_t2"]),
            "validos_2026": slot["validos_pres_t2"],
            "scalco_t2": scalco,
            "adilo_t2": pct(slot["adilo_t2"], slot["validos_pref_t2"]),
            "validos_2024": slot["validos_pref_t2"],
            "partido_pref_t1": partido_t1,
            "partido_pref_t1_sigla": SIGLA.get(partido_t1, partido_t1) if partido_t1 else None,
            "delta_pl": round(flavio - scalco, 2),
        })
    return linhas


def coef_dict(modelo, nomes: dict[str, str]) -> list[dict]:
    ci = modelo.conf_int()
    linhas = []
    for nome in modelo.params.index:
        beta = float(modelo.params[nome])
        se = float(modelo.bse[nome])
        p = float(modelo.pvalues[nome])
        linhas.append({
            "variavel": nomes.get(nome, nome),
            "beta": round(beta, 3),
            "ep": round(se, 3),
            "p": p,
            "ic_inf": round(float(ci.loc[nome, 0]), 3),
            "ic_sup": round(float(ci.loc[nome, 1]), 3),
        })
    return linhas


def ajustar(df: pd.DataFrame, ycol: str, wcol: str, controles: list[str]):
    y = df[ycol].astype(float)
    X = sm.add_constant(df[controles].astype(float))
    w = df[wcol].astype(float)
    return sm.WLS(y, X, weights=w).fit(cov_type="HC1")


def vif_max(df: pd.DataFrame, controles: list[str]) -> float:
    X = sm.add_constant(df[controles].astype(float))
    vals = [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]
    return float(max(vals)) if vals else 1.0


def pontos(valor: float) -> str:
    n = abs(valor)
    unidade = "ponto percentual" if n < 2 else "pontos percentuais"
    return f"{br(n)} {unidade}"


def frase_renda(rotulo: str, modelo) -> str:
    beta = float(modelo.params["renda_mil"])
    lo, hi = modelo.conf_int().loc["renda_mil"]
    sentido = "a mais" if beta >= 0 else "a menos"
    return (
        f"Para {rotulo}, cada R$ 1.000 a mais na renda do responsável se associa a "
        f"{pontos(beta)} {sentido} "
        f"(IC 95% {br(float(lo))} a {br(float(hi))}, {p_txt(float(modelo.pvalues['renda_mil']))})."
    )


def main():
    if not ZIP_2024.exists() or ZIP_2024.stat().st_size < 90_000_000:
        raise RuntimeError(f"Arquivo de 2024 ausente ou incompleto: {ZIP_2024}")

    print("=== prefeito 2024 ===")
    votos = ler_prefeito()
    cidade = totais_cidade(votos)
    for turno, bloco in cidade.items():
        print(
            f"  {turno}: {bloco['vencedor']} ({bloco['partido']}) {bloco['pct']}%  "
            f"Adiló {bloco['adilo']}  Scalco {bloco['scalco']}  válidos {bloco['validos']}"
        )
    t2 = cidade["t2"]
    if t2["adilo"] != REFERENCIA_T2["adilo"] or t2["scalco"] != REFERENCIA_T2["scalco"]:
        raise RuntimeError(
            f"2º turno de 2024 divergiu do divulgado: Adiló {t2['adilo']} Scalco {t2['scalco']}"
        )

    locais_2024 = por_local(votos)
    dados = json.loads(SAIDA.read_text(encoding="utf-8"))
    ids = {x["id"] for x in dados["locais"]}
    casados = [i for i in locais_2024 if i in ids]
    sem_2026 = sorted(set(locais_2024) - ids)
    print(f"  locais 2024: {len(locais_2024)}  casados com 2026: {len(casados)}  só em 2024: {len(sem_2026)}")

    comparacao = {"pl_e_pl": 0, "psdb_e_pl": 0, "psdb_e_pt": 0, "pl_e_pt": 0, "sem_par": 0}
    for loc in dados["locais"]:
        pref = locais_2024.get(loc["id"])
        loc["pref"] = pref
        p2 = (pref or {}).get("t2")
        pres = loc.get("t2")
        if not p2 or not pres:
            comparacao["sem_par"] += 1
            continue
        par = (p2["partido"], pres["partido"])
        if par == ("PL", "PL"):
            comparacao["pl_e_pl"] += 1
        elif par == ("PSDB", "PL"):
            comparacao["psdb_e_pl"] += 1
        elif par == ("PSDB", "PT"):
            comparacao["psdb_e_pt"] += 1
        elif par == ("PL", "PT"):
            comparacao["pl_e_pt"] += 1

    bairros_json = json.loads((PROJ / "dados_bairros.json").read_text(encoding="utf-8"))
    cov = {}
    for v in bairros_json.values():
        cov[chave_nome(v["nome"])] = v

    bairros = agregar_bairros(dados["locais"], cov)
    df = pd.DataFrame(bairros)
    df["renda_mil"] = df["renda"] / 1000
    df["dens_mil"] = df["densidade"] / 1000
    controles = ["renda_mil", "dens_mil", "dist_centro_km"]
    escol_sd = float(df["escolaridade"].std(ddof=0)) if df["escolaridade"].notna().sum() > 2 else 0
    nota_escol = (
        "A alfabetização de 15 anos ou mais varia pouco entre os bairros "
        f"(desvio-padrão {br(escol_sd)} ponto), então ficou de fora da regressão."
    )
    vif = vif_max(df, controles)
    nomes = {
        "const": "Intercepto",
        "renda_mil": "Renda do responsável (R$ mil)",
        "dens_mil": "Densidade (mil hab/km²)",
        "dist_centro_km": "Distância ao centro (km)",
    }

    m_flavio_biv = ajustar(df, "flavio_t2", "validos_2026", ["renda_mil"])
    m_flavio = ajustar(df, "flavio_t2", "validos_2026", controles)
    m_scalco_biv = ajustar(df, "scalco_t2", "validos_2024", ["renda_mil"])
    m_scalco = ajustar(df, "scalco_t2", "validos_2024", controles)
    m_delta = ajustar(df, "delta_pl", "validos_2026", controles)

    def pacote(modelo, desfecho, peso):
        return {
            "desfecho": desfecho,
            "peso": peso,
            "n_bairros": int(modelo.nobs),
            "r2": round(float(modelo.rsquared), 3),
            "r2_ajustado": round(float(modelo.rsquared_adj), 3),
            "coeficientes": coef_dict(modelo, nomes),
        }

    vif_nota = (
        f"O maior VIF entre os controles é {br(vif, 2)}. "
        + ("Há colinearidade relevante." if vif >= 5 else "A colinearidade entre os controles é moderada.")
    )
    beta = float(m_delta.params["renda_mil"])
    lo, hi = m_delta.conf_int().loc["renda_mil"]
    sentido = "maior" if beta >= 0 else "menor"
    leitura = (
        f"Regressão linear múltipla, ponderada pelos votos válidos, com um ponto por bairro do IBGE "
        f"(N = {int(m_flavio.nobs)}). Controles: densidade e distância ao centro. {nota_escol} {vif_nota} "
        f"{frase_renda('Flávio Bolsonaro no 2º turno de 2026', m_flavio)} "
        f"Sem os controles, o coeficiente era {br(float(m_flavio_biv.params['renda_mil']))} "
        f"({p_txt(float(m_flavio_biv.pvalues['renda_mil']))}). "
        f"R² ajustado do modelo múltiplo: {br(float(m_flavio.rsquared_adj), 3)}. "
        f"{frase_renda('Scalco (PL) no 2º turno para prefeito em 2024', m_scalco)} "
        f"Sem os controles, {br(float(m_scalco_biv.params['renda_mil']))} "
        f"({p_txt(float(m_scalco_biv.pvalues['renda_mil']))}). "
        f"R² ajustado: {br(float(m_scalco.rsquared_adj), 3)}. "
        f"A fatia do PL em 2026, menos a fatia do PL em 2024, é {pontos(beta)} {sentido} "
        f"a cada R$ 1.000 de renda (IC 95% {br(float(lo))} a {br(float(hi))}, "
        f"{p_txt(float(m_delta.pvalues['renda_mil']))}). "
        f"O teste descreve bairros, não eleitores: a renda é a do domicílio em 2022 e a pessoa "
        f"não vota obrigatoriamente no bairro onde mora."
    )

    dados["prefeito_2024"] = {
        "eleicao": "Eleições municipais de 2024",
        "fonte": "TSE, votação por seção eleitoral, 2024, cargo de prefeito",
        "totais": cidade,
        "locais_2024": len(locais_2024),
        "casados_com_2026": len(casados),
        "so_em_2024": sem_2026,
        "comparacao_locais": comparacao,
    }
    for loc in dados["locais"]:
        pref = loc.get("pref") or {}
        for turno in pref.values():
            if isinstance(turno, dict):
                turno.pop("votos_por_partido", None)
    dados["bairros"] = bairros
    dados["regressao"] = {
        "unidade": "bairro do IBGE",
        "metodo": "WLS com erro-padrão HC1",
        "controles": [nomes[c] for c in controles],
        "nota_escolaridade": nota_escol,
        "vif_max": round(vif, 2),
        "flavio_2026_bivariada": pacote(m_flavio_biv, "% de Flávio no 2º turno de 2026", "votos válidos de 2026"),
        "flavio_2026": pacote(m_flavio, "% de Flávio no 2º turno de 2026", "votos válidos de 2026"),
        "scalco_2024_bivariada": pacote(m_scalco_biv, "% de Scalco (PL) no 2º turno de 2024", "votos válidos de 2024"),
        "scalco_2024": pacote(m_scalco, "% de Scalco (PL) no 2º turno de 2024", "votos válidos de 2024"),
        "delta_pl": pacote(m_delta, "Flávio 2026 menos Scalco 2024, em pontos", "votos válidos de 2026"),
        "leitura": leitura,
    }
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    print(leitura)
    print("comparacao", comparacao)
    print(f"bairros na regressão: {len(df)}")


if __name__ == "__main__":
    main()

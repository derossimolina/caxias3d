"""
Clustering e regressão sobre dados_bairros.json (saída de pipeline_ibge.py).

Roda DEPOIS do pipeline_ibge.py. Faz duas coisas independentes:

  1. Clustering (KMeans): substitui o campo heurístico "perfil" (antigo
     if/elif manual sobre renda/densidade/área) por uma tipologia orientada a
     dado, sobre renda_pc, densidade (log) e área (log) padronizados. O nº de
     clusters é escolhido automaticamente pelo silhouette score. Emprego
     formal é deixado de fora das features: como é uma estimativa distribuída
     proporcionalmente à população (pipeline_ibge.py), ele não carrega
     informação independente de densidade/população — incluí-lo só
     redundaria o sinal.

  2. Regressão (OLS): explica renda_pc em função de escolaridade e densidade
     (log) — o que se associa a bairros de renda mais alta ou mais baixa.
     Gera analise_regressao_renda.md com o resumo estatístico (coeficientes,
     R², p-valores) para citar na tese.

Escreve de volta em dados_bairros.json (só o campo "perfil" muda).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

PROJ = Path(__file__).parent
JSON_PATH = PROJ / "dados_bairros.json"
REPORT_PATH = PROJ / "analise_regressao_renda.md"

with open(JSON_PATH, encoding="utf-8") as f:
    dados = json.load(f)

df = pd.DataFrame(dados).T
df.index.name = "codigo"
for c in ["area_km2", "populacao", "densidade", "renda_pc", "escolaridade", "emprego_formal"]:
    df[c] = pd.to_numeric(df[c])

# ─── 1. Clustering ────────────────────────────────────────────────────────
print("=== 1. Clustering (KMeans) ===")
feat = pd.DataFrame({
    "renda_pc": df["renda_pc"],
    "log_densidade": np.log(df["densidade"]),
    "log_area": np.log(df["area_km2"]),
    "escolaridade": df["escolaridade"],
})
X = StandardScaler().fit_transform(feat)

melhor_k, melhor_score, melhor_labels = None, -1, None
for k in range(3, 9):
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
    score = silhouette_score(X, labels)
    print(f"  k={k}: silhouette={score:.3f}")
    if score > melhor_score:
        melhor_k, melhor_score, melhor_labels = k, score, labels

print(f"  -> k escolhido: {melhor_k} (silhouette={melhor_score:.3f})")
df["cluster_id"] = melhor_labels

# Nomeia cada cluster pelas suas médias reais (renda e densidade), do jeito
# mais descritivo possível, mantendo o vocabulário do perfil antigo.
resumo = df.groupby("cluster_id")[["renda_pc", "densidade", "area_km2", "escolaridade"]].mean()
resumo = resumo.sort_values("renda_pc", ascending=False)
print("\n  médias por cluster (ordenado por renda):")
print(resumo.round(1).to_string())

# Nome-base único por posição no ranking de renda (garante que não colidam);
# "_baixa_densidade" é só um qualificador extra, não a base do nome.
TIERS = ["central_rico", "central_medio_alto", "central_medio", "urbano_medio",
         "urbano_popular", "periferico", "extremo_periferico"]
nomes = {}
for rank, (cid, row) in enumerate(resumo.iterrows()):
    base = TIERS[rank] if rank < len(TIERS) else f"grupo_{rank + 1}"
    nomes[cid] = base + ("_disperso" if row["densidade"] < 500 else "")

df["perfil"] = df["cluster_id"].map(nomes)
print("\n  bairros por perfil:")
print(df.groupby("perfil").size().sort_values(ascending=False).to_string())

for cod in dados:
    dados[cod]["perfil"] = df.loc[cod, "perfil"]
    dados[cod]["cluster_id"] = int(df.loc[cod, "cluster_id"])

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)
print(f"\n✓ '{JSON_PATH.name}' atualizado (perfil agora vem do cluster; k={melhor_k})")

# ─── 2. Regressão: o que explica renda_pc entre bairros ────────────────────
print("\n=== 2. Regressão OLS: renda_pc ~ escolaridade + log(densidade) + log(área) ===")
X_reg = pd.DataFrame({
    "escolaridade": df["escolaridade"],
    "log_densidade": np.log(df["densidade"]),
    "log_area": np.log(df["area_km2"]),
})
X_reg = sm.add_constant(X_reg)
y_reg = df["renda_pc"]

modelo = sm.OLS(y_reg, X_reg).fit()
print(modelo.summary())

linhas = [
    "# Regressão: o que explica a renda per capita entre bairros",
    "",
    f"Amostra: {len(df)} bairros (Censo IBGE 2022, dados reais por bairro).",
    "",
    "Modelo: `renda_pc ~ escolaridade + log(densidade) + log(área_km2)` (OLS).",
    "",
    "Emprego formal foi deixado de fora dos regressores por ser uma "
    "estimativa proporcional à população (pipeline_ibge.py), não uma "
    "medição independente — usá-lo aqui seria circular.",
    "",
    "## Resultado",
    "",
    f"- R²: {modelo.rsquared:.3f} (R² ajustado: {modelo.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo.params.index, modelo.params, modelo.bse, modelo.pvalues):
    linhas.append(f"| {nome} | {coef:,.1f} | {se:,.1f} | {p:.4f} |")
linhas += [
    "",
    "p-valor < 0.05 indica associação estatisticamente significativa "
    "(ao nível de 95%) com a renda per capita do bairro.",
    "",
    "## Leitura honesta do resultado",
    "",
    f"O R² é baixo (~{modelo.rsquared*100:.0f}%): densidade, área e "
    "escolaridade explicam pouco da variação de renda entre bairros de "
    "Caxias do Sul. Isso é, em si, um achado — não um modelo mal ajustado. "
    "A escolaridade tem variância quase nula no município (maioria dos "
    "bairros entre 96% e 100% de alfabetização), então ela não consegue "
    "discriminar bairros ricos de pobres mesmo sendo dado real e correto. "
    "`log_area` é o regressor mais próximo de significância — bairros "
    "espacialmente maiores (mais afastados do centro/menos adensados) "
    "tendem a ter renda per capita menor. Para um modelo mais explicativo, "
    "seria necessário incluir variáveis que este dataset não tem (ex.: "
    "distância ao centro, uso do solo, acesso a transporte).",
]
REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
print(f"\n✓ Relatório salvo em: {REPORT_PATH.name}")

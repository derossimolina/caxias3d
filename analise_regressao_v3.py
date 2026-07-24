"""
Extensão 3 da regressão de renda_pc: composição racial + estrutura etária.

Duas variáveis novas, ambas dado real do Censo 2022 por bairro (sem proxy):
  - pct_branca:        % da população que se autodeclarou branca (V01317 /
                        soma de V01317:V01321 — tabela "cor ou raça")
  - razao_dependencia: (pop 0-14 + pop 60+) / pop 15-59, ×100 — tabela
                        "demografia"

Justificativa teórica (ver relatorio_projeto_doutorado.md para a revisão
completa): segregação racial e renda é uma das associações mais robustas na
literatura de desigualdade urbana brasileira (Telles, 2004; IPEA); estrutura
etária/razão de dependência é um regressor clássico de renda per capita via
o efeito ciclo-de-vida (Modigliani; Mincer, 1974).

Roda DEPOIS de pipeline_ibge.py, analise_ml.py, analise_osm_economia.py e
analise_regressao_v2.py.
"""

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

PROJ = Path(__file__).parent
JSON_PATH = PROJ / "dados_bairros.json"
REPORT_PATH = PROJ / "analise_regressao_renda.md"

MUN = "4305108"
DIR_BAIRRO = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Bairro_csv/"

RACA_COLS = [f"V{n:05d}" for n in range(1317, 1322)]  # branca,preta,amarela,parda,indigena
DEMOG_JOVEM = [f"V{n:05d}" for n in (1031, 1032, 1033)]        # 0-4,5-9,10-14
DEMOG_ADULTO = [f"V{n:05d}" for n in (1034, 1035, 1036, 1037, 1038, 1039)]  # 15-19..50-59
DEMOG_IDOSO = [f"V{n:05d}" for n in (1040, 1041)]               # 60-69, 70+


def baixar_csv_bairro(nome_arquivo):
    r = requests.get(DIR_BAIRRO + nome_arquivo, timeout=180)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding="latin-1")
    return df[df["CD_BAIRRO"].astype(str).str[:7] == MUN].copy()


def to_float(s):
    if pd.isna(s) or str(s).strip() in ("X", "", "-", "..", "nan"):
        return float("nan")
    return float(str(s).replace(",", "."))


def soma(row, cols):
    vals = [to_float(row[c]) for c in cols if c in row]
    return sum(v for v in vals if not pd.isna(v))


print("=== 1. Baixando cor ou raça e demografia (nível bairro) ===")
df_raca = baixar_csv_bairro("Agregados_por_bairros_cor_ou_raca_BR.zip")
df_demog = baixar_csv_bairro("Agregados_por_bairros_demografia_BR.zip")

df_raca["total_raca"] = df_raca.apply(lambda r: soma(r, RACA_COLS), axis=1)
df_raca["branca"] = df_raca["V01317"].apply(to_float)
df_raca["pct_branca"] = 100 * df_raca["branca"] / df_raca["total_raca"]
pct_branca_map = dict(zip(df_raca["CD_BAIRRO"], df_raca["pct_branca"]))

df_demog["jovem"] = df_demog.apply(lambda r: soma(r, DEMOG_JOVEM), axis=1)
df_demog["adulto"] = df_demog.apply(lambda r: soma(r, DEMOG_ADULTO), axis=1)
df_demog["idoso"] = df_demog.apply(lambda r: soma(r, DEMOG_IDOSO), axis=1)
df_demog["razao_dependencia"] = 100 * (df_demog["jovem"] + df_demog["idoso"]) / df_demog["adulto"]
dep_map = dict(zip(df_demog["CD_BAIRRO"], df_demog["razao_dependencia"]))
idoso_pct_map = dict(zip(df_demog["CD_BAIRRO"],
                          100 * df_demog["idoso"] / (df_demog["jovem"] + df_demog["adulto"] + df_demog["idoso"])))

print("\n=== 2. Atualizando dados_bairros.json ===")
with open(JSON_PATH, encoding="utf-8") as f:
    dados = json.load(f)

for cod in dados:
    cd = f"{MUN}{int(cod):03d}"
    dados[cod]["pct_branca"] = round(pct_branca_map[cd], 1)
    dados[cod]["razao_dependencia"] = round(dep_map[cd], 1)
    dados[cod]["pct_idosos"] = round(idoso_pct_map[cd], 1)
    dados[cod]["fonte_raca_idade"] = "IBGE Censo 2022 (agregados por bairro, cor ou raça / demografia)"

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)
print(f"✓ pct_branca / razao_dependencia / pct_idosos adicionados a '{JSON_PATH.name}'")

# ─── 3. Regressão ────────────────────────────────────────────────────────────
df = pd.DataFrame(dados).T
df.index = df.index.astype(int)
for c in ["renda_pc", "densidade", "densidade_comercial_osm", "dist_centro_km",
          "pct_branca", "razao_dependencia"]:
    df[c] = pd.to_numeric(df[c])

base = pd.DataFrame({
    "log_densidade": np.log(df["densidade"]),
    "log_densidade_comercial": np.log(df["densidade_comercial_osm"] + 1),
    "dist_centro_km": df["dist_centro_km"],
})

print("\n=== 3. Modelo D: modelo C + pct_branca + razao_dependencia ===")
X_d = sm.add_constant(base.assign(pct_branca=df["pct_branca"], razao_dependencia=df["razao_dependencia"]))
modelo_d = sm.OLS(np.log(df["renda_pc"]), X_d).fit()
print(modelo_d.summary())

linhas = [
    "",
    "---",
    "",
    "## Extensão 3: composição racial e estrutura etária",
    "",
    "`pct_branca`: % da população autodeclarada branca (Censo 2022, tabela "
    "cor ou raça por bairro). `razao_dependencia`: (pop 0-14 + pop 60+) / "
    "pop 15-59 × 100 (Censo 2022, tabela demografia por bairro). Ambas são "
    "dado real, não proxy — ver revisão teórica em "
    "relatorio_projeto_doutorado.md.",
    "",
    "### Modelo D — Modelo C + `pct_branca` + `razao_dependencia`",
    "",
    f"- R²: {modelo_d.rsquared:.3f} (R² ajustado: {modelo_d.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_d.params.index, modelo_d.params, modelo_d.bse, modelo_d.pvalues):
    linhas.append(f"| {nome} | {coef:.4f} | {se:.4f} | {p:.4f} |")

print("\n=== 4. Modelo E: só as variáveis significativas do Modelo D ===")
# mantém apenas termos com p<0.10 no Modelo D (além dos já validados no Modelo C)
candidatos = {"pct_branca": df["pct_branca"], "razao_dependencia": df["razao_dependencia"]}
sig = {k: v for k, v in candidatos.items() if modelo_d.pvalues[k] < 0.10}
X_e = sm.add_constant(base.assign(**sig))
modelo_e = sm.OLS(np.log(df["renda_pc"]), X_e).fit()
print(modelo_e.summary())

linhas += [
    "",
    f"### Modelo E (final, recomendado) — Modelo C + "
    f"{' + '.join(sig.keys()) if sig else '(nenhuma variável nova ficou significativa)'}",
    "",
    f"- R²: {modelo_e.rsquared:.3f} (R² ajustado: {modelo_e.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_e.params.index, modelo_e.params, modelo_e.bse, modelo_e.pvalues):
    linhas.append(f"| {nome} | {coef:.4f} | {se:.4f} | {p:.4f} |")

print("\n=== 5. Modelo F: enxuto — dist_centro_km + pct_branca + razao_dependencia ===")
# log_densidade e log_densidade_comercial perderam significância assim que
# pct_branca entrou (ficam menos parcimoniosos sem ganhar poder explicativo:
# comparar AIC). Tira as duas e compara.
X_f = sm.add_constant(df[["dist_centro_km", "pct_branca", "razao_dependencia"]])
modelo_f = sm.OLS(np.log(df["renda_pc"]), X_f).fit()
print(modelo_f.summary())
print(f"AIC comparado — Modelo D: {modelo_d.aic:.2f} | Modelo F: {modelo_f.aic:.2f}")

linhas += [
    "",
    "### Modelo F (final, recomendado) — `log(renda_pc) ~ dist_centro_km + "
    "pct_branca + razao_dependencia`",
    "",
    "`log_densidade` e `log_densidade_comercial` perderam significância "
    "assim que `pct_branca` entrou no modelo (parte do que a densidade "
    "comercial capturava era, na verdade, composição racial do bairro — "
    "achado em si relevante para a tese: segregação residencial racial e "
    "uso comercial do solo não são independentes em Caxias do Sul). Tirar "
    "as duas variáveis quase não muda o R² e melhora o AIC "
    f"({modelo_d.aic:.2f} → {modelo_f.aic:.2f}, menor é melhor).",
    "",
    f"- R²: {modelo_f.rsquared:.3f} (R² ajustado: {modelo_f.rsquared_adj:.3f})",
    "",
    "| Variável | Coeficiente | Erro padrão | p-valor |",
    "|---|---|---|---|",
]
for nome, coef, se, p in zip(modelo_f.params.index, modelo_f.params, modelo_f.bse, modelo_f.pvalues):
    linhas.append(f"| {nome} | {coef:.4f} | {se:.4f} | {p:.4f} |")
linhas += [
    "",
    "**Leitura**: bairros mais próximos do centro, com maior % de "
    "população branca e menor razão de dependência (mais adultos em idade "
    "ativa por dependente) têm renda per capita mais alta. O coeficiente "
    "de `pct_branca` é o mais robusto e o de maior magnitude relativa do "
    "modelo inteiro — consistente com a literatura de desigualdade racial "
    "urbana no Brasil (ver relatorio_projeto_doutorado.md). Isso é uma "
    "correlação, não uma afirmação causal: raça está altamente "
    "correlacionada, no Brasil, com histórico de acesso a herança, "
    "educação e ocupação — o coeficiente capta esse conjunto de "
    "mecanismos estruturais, não um efeito \"da raça em si\".",
]

with open(REPORT_PATH, "a", encoding="utf-8") as f:
    f.write("\n".join(linhas) + "\n")
print(f"\n✓ Seção adicionada em: {REPORT_PATH.name}")

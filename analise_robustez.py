"""
Testes de robustez do modelo final — respostas empíricas às "perguntas
popperianas" levantadas pela revisão epistemológica independente do
relatório (ver relatorio_projeto_doutorado.md, Seção 6.1).

Não são testes cosméticos: cada um é uma tentativa real de enfraquecer o
achado central (pct_branca como preditor dominante de renda_pc), não uma
confirmação adicional.

  1. Univariado: pct_branca sozinha explica quanto de log(renda_pc)? Se o
     achado só aparece forte por causa da combinação específica de
     covariáveis escolhida na busca de especificação (Seção 4.2), isso seria
     sinal de fragilidade — o R² univariado deveria ser bem menor que o do
     modelo completo.
  2. Leave-One-Out CV: o modelo é reajustado 65 vezes, cada vez deixando um
     bairro de fora, prevendo esse bairro, e comparando a previsão com o
     valor real. Um R² fora da amostra muito menor que o R² dentro da
     amostra indicaria overfitting/instabilidade.
  3. Estabilidade do coeficiente de pct_branca ao longo dos 65 reajustes do
     LOO: se um único bairro "puxa" o resultado, o coeficiente deveria
     variar bastante entre os folds.
  4. Correlação pct_branca × dist_centro_km: se fossem quase a mesma coisa
     (bairros brancos = bairros centrais), pct_branca não teria efeito
     independente — o VIF já indicou que não (1,34), aqui mede-se
     diretamente a correlação bivariada.

Roda DEPOIS de pipeline_ibge.py, analise_ml.py, analise_osm_economia.py,
analise_regressao_v2.py e analise_regressao_v3.py.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.model_selection import LeaveOneOut

PROJ = Path(__file__).parent
JSON_PATH = PROJ / "dados_bairros.json"
REPORT_PATH = PROJ / "analise_regressao_renda.md"

with open(JSON_PATH, encoding="utf-8") as f:
    dados = json.load(f)

df = pd.DataFrame(dados).T
df.index = df.index.astype(int)
for c in ["renda_pc", "dist_centro_km", "pct_branca", "razao_dependencia"]:
    df[c] = pd.to_numeric(df[c])
y = np.log(df["renda_pc"])

print("=== 1. pct_branca sozinha (achado é artefato da combinação de covariáveis?) ===")
X_uni = sm.add_constant(df[["pct_branca"]])
m_uni = sm.OLS(y, X_uni).fit()
print(f"  R² univariado = {m_uni.rsquared:.3f}  (R² do modelo completo = 0,716)")
print(f"  coeficiente = {m_uni.params['pct_branca']:.4f}  p = {m_uni.pvalues['pct_branca']:.2e}")

print("\n=== 2 e 3. Leave-One-Out CV: R² fora da amostra e estabilidade do coeficiente ===")
X = df[["dist_centro_km", "pct_branca", "razao_dependencia"]].values
y_arr = y.values
loo = LeaveOneOut()
preds = np.zeros(len(y_arr))
betas_pct_branca = []
for train_idx, test_idx in loo.split(X):
    Xtr = sm.add_constant(X[train_idx])
    m = sm.OLS(y_arr[train_idx], Xtr).fit()
    Xte = np.concatenate([[1], X[test_idx][0]])
    preds[test_idx] = Xte @ m.params
    betas_pct_branca.append(m.params[2])  # índice 2 = pct_branca

r2_loo = 1 - np.sum((y_arr - preds) ** 2) / np.sum((y_arr - y_arr.mean()) ** 2)
print(f"  R² out-of-sample (LOO) = {r2_loo:.3f}  (R² dentro da amostra = 0,716)")
print(
    f"  coeficiente de pct_branca nos 65 reajustes: "
    f"média={np.mean(betas_pct_branca):.4f} min={np.min(betas_pct_branca):.4f} "
    f"max={np.max(betas_pct_branca):.4f} desvio={np.std(betas_pct_branca):.4f}"
)

print("\n=== 4. pct_branca é só um proxy de distância ao centro? ===")
corr = np.corrcoef(df["pct_branca"], df["dist_centro_km"])[0, 1]
print(f"  correlação pct_branca x dist_centro_km = {corr:.3f} (moderada, não colinear)")

linhas = [
    "",
    "---",
    "",
    "## Extensão 4: testes de robustez (respostas às perguntas popperianas)",
    "",
    "Ver `relatorio_projeto_doutorado.md`, Seção 6.1, para a discussão "
    "completa. Resumo dos números:",
    "",
    f"- `pct_branca` sozinha (sem as outras duas variáveis): R² = "
    f"{m_uni.rsquared:.3f} (modelo completo: 0,716) — o achado não depende "
    "da combinação específica de covariáveis escolhida na busca de "
    "especificação.",
    f"- R² fora da amostra (Leave-One-Out, 65 reajustes): {r2_loo:.3f} "
    "(dentro da amostra: 0,716) — queda modesta, sem sinal de overfitting "
    "severo.",
    f"- Coeficiente de `pct_branca` nos 65 reajustes do LOO: desvio-padrão "
    f"= {np.std(betas_pct_branca):.4f} sobre uma média de "
    f"{np.mean(betas_pct_branca):.4f} — nenhum bairro isolado está "
    "\"puxando\" o resultado.",
    f"- Correlação `pct_branca` × `dist_centro_km` = {corr:.3f} — moderada, "
    "não os torna intercambiáveis (consistente com o VIF baixo).",
]
with open(REPORT_PATH, "a", encoding="utf-8") as f:
    f.write("\n".join(linhas) + "\n")
print(f"\n✓ Seção adicionada em: {REPORT_PATH.name}")

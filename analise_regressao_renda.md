# Regressão: o que explica a renda per capita entre bairros

Amostra: 65 bairros (Censo IBGE 2022, dados reais por bairro).

Modelo: `renda_pc ~ escolaridade + log(densidade) + log(área_km2)` (OLS).

Emprego formal foi deixado de fora dos regressores por ser uma estimativa proporcional à população (pipeline_ibge.py), não uma medição independente — usá-lo aqui seria circular.

## Resultado

- R²: 0.092 (R² ajustado: 0.048)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | -12,589.6 | 40,878.3 | 0.7591 |
| escolaridade | 174.9 | 417.2 | 0.6765 |
| log_densidade | -80.5 | 203.2 | 0.6933 |
| log_area | -457.3 | 235.1 | 0.0563 |

p-valor < 0.05 indica associação estatisticamente significativa (ao nível de 95%) com a renda per capita do bairro.

## Leitura honesta do resultado

O R² é baixo (~9%): densidade, área e escolaridade explicam pouco da variação de renda entre bairros de Caxias do Sul. Isso é, em si, um achado — não um modelo mal ajustado. A escolaridade tem variância quase nula no município (maioria dos bairros entre 96% e 100% de alfabetização), então ela não consegue discriminar bairros ricos de pobres mesmo sendo dado real e correto. `log_area` é o regressor mais próximo de significância — bairros espacialmente maiores (mais afastados do centro/menos adensados) tendem a ter renda per capita menor. Para um modelo mais explicativo, seria necessário incluir variáveis que este dataset não tem (ex.: distância ao centro, uso do solo, acesso a transporte).
---

## Extensão: densidade comercial (OpenStreetMap) como regressor

Testado como alternativa ao emprego formal por segmento (CAGED/RAIS não têm granularidade por bairro nas APIs públicas — ver seção anterior). Usa a contagem de estabelecimentos comerciais/industriais do OpenStreetMap por bairro, via Overpass API, como proxy de atividade econômica. É proxy, não dado oficial — sujeito ao mapeamento incompleto do OSM.

Modelo: `renda_pc ~ escolaridade + log(densidade) + log(área) + log(densidade_comercial_osm + 1)` (OLS).

- R²: 0.413 (R² ajustado: 0.374)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | -31,654.2 | 33,314.2 | 0.3458 |
| escolaridade | 387.5 | 340.3 | 0.2593 |
| log_densidade | -685.4 | 195.8 | 0.0009 |
| log_area | -177.4 | 196.8 | 0.3708 |
| log_densidade_comercial | 1,026.4 | 179.3 | 0.0000 |

---

## Extensão 2: distância ao centro + log(renda_pc)

`dist_centro_km`: distância do centroide do bairro ao centroide do bairro Centro, derivada da própria geometria (sem fonte externa nova).

### Modelo A — `renda_pc ~ escolaridade + log(densidade) + log(área) + log(densidade_comercial) + dist_centro_km`

- R²: 0.487 (R² ajustado: 0.444)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | -36,697.0 | 31,447.6 | 0.2479 |
| escolaridade | 466.3 | 321.9 | 0.1527 |
| log_densidade | -881.1 | 196.3 | 0.0000 |
| log_area | 0.3 | 195.2 | 0.9988 |
| log_densidade_comercial | 862.2 | 178.0 | 0.0000 |
| dist_centro_km | -249.0 | 85.1 | 0.0049 |

### Modelo B — `log(renda_pc) ~ escolaridade + log(densidade) + log(área) + log(densidade_comercial) + dist_centro_km`

- R²: 0.519 (R² ajustado: 0.479)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | -0.7329 | 7.1959 | 0.9192 |
| escolaridade | 0.1048 | 0.0737 | 0.1601 |
| log_densidade | -0.2216 | 0.0449 | 0.0000 |
| log_area | 0.0074 | 0.0447 | 0.8696 |
| log_densidade_comercial | 0.2103 | 0.0407 | 0.0000 |
| dist_centro_km | -0.0642 | 0.0195 | 0.0017 |

Coeficientes do Modelo B leem-se como efeito percentual aproximado sobre renda_pc (variável dependente em log).

### Modelo C (recomendado) — `log(renda_pc) ~ log(densidade) + log(densidade_comercial) + dist_centro_km`

`escolaridade` e `log(área)` saíram: não eram significativas e `log(área)` estava causando o aviso de multicolinearidade (Cond. No. caiu de 2,5e4 para ~105). Com 65 observações, um modelo mais enxuto com todos os termos significativos é preferível a um modelo maior carregando variáveis que não contribuem — reduz risco de overfitting.

- R²: 0.502 (R² ajustado: 0.477)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | 9.5287 | 0.3287 | 0.0000 |
| log_densidade | -0.1956 | 0.0385 | 0.0000 |
| log_densidade_comercial | 0.2036 | 0.0403 | 0.0000 |
| dist_centro_km | -0.0594 | 0.0184 | 0.0020 |

Todos os termos significativos a 95%. Leitura: bairros com maior densidade comercial (OSM) e mais perto do centro tendem a renda mais alta; controlando por isso, maior densidade *residencial* pura associa-se a renda menor (efeito bairro-dormitório vs. polo misto).

---

## Extensão 3: composição racial e estrutura etária

`pct_branca`: % da população autodeclarada branca (Censo 2022, tabela cor ou raça por bairro). `razao_dependencia`: (pop 0-14 + pop 60+) / pop 15-59 × 100 (Censo 2022, tabela demografia por bairro). Ambas são dado real, não proxy — ver revisão teórica em relatorio_projeto_doutorado.md.

### Modelo D — Modelo C + `pct_branca` + `razao_dependencia`

- R²: 0.730 (R² ajustado: 0.707)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | 7.0173 | 0.5233 | 0.0000 |
| log_densidade | -0.0496 | 0.0393 | 0.2115 |
| log_densidade_comercial | 0.0682 | 0.0400 | 0.0937 |
| dist_centro_km | -0.0328 | 0.0146 | 0.0285 |
| pct_branca | 0.0247 | 0.0036 | 0.0000 |
| razao_dependencia | -0.0063 | 0.0027 | 0.0238 |

### Modelo E (final, recomendado) — Modelo C + pct_branca + razao_dependencia

- R²: 0.730 (R² ajustado: 0.707)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | 7.0173 | 0.5233 | 0.0000 |
| log_densidade | -0.0496 | 0.0393 | 0.2115 |
| log_densidade_comercial | 0.0682 | 0.0400 | 0.0937 |
| dist_centro_km | -0.0328 | 0.0146 | 0.0285 |
| pct_branca | 0.0247 | 0.0036 | 0.0000 |
| razao_dependencia | -0.0063 | 0.0027 | 0.0238 |

### Modelo F (final, recomendado) — `log(renda_pc) ~ dist_centro_km + pct_branca + razao_dependencia`

`log_densidade` e `log_densidade_comercial` perderam significância assim que `pct_branca` entrou no modelo (parte do que a densidade comercial capturava era, na verdade, composição racial do bairro — achado em si relevante para a tese: segregação residencial racial e uso comercial do solo não são independentes em Caxias do Sul). Tirar as duas variáveis quase não muda o R² e melhora o AIC (-35.74 → -36.60, menor é melhor).

- R²: 0.716 (R² ajustado: 0.702)

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| const | 6.4459 | 0.2182 | 0.0000 |
| dist_centro_km | -0.0327 | 0.0086 | 0.0003 |
| pct_branca | 0.0282 | 0.0028 | 0.0000 |
| razao_dependencia | -0.0050 | 0.0026 | 0.0601 |

**Leitura**: bairros mais próximos do centro, com maior % de população branca e menor razão de dependência (mais adultos em idade ativa por dependente) têm renda per capita mais alta. O coeficiente de `pct_branca` é o mais robusto e o de maior magnitude relativa do modelo inteiro — consistente com a literatura de desigualdade racial urbana no Brasil (ver relatorio_projeto_doutorado.md). Isso é uma correlação, não uma afirmação causal: raça está altamente correlacionada, no Brasil, com histórico de acesso a herança, educação e ocupação — o coeficiente capta esse conjunto de mecanismos estruturais, não um efeito "da raça em si".

---

## Extensão 4: testes de robustez (respostas às perguntas popperianas)

Ver `relatorio_projeto_doutorado.md`, Seção 6.1, para a discussão completa. Resumo dos números:

- `pct_branca` sozinha (sem as outras duas variáveis): R² = 0.640 (modelo completo: 0,716) — o achado não depende da combinação específica de covariáveis escolhida na busca de especificação.
- R² fora da amostra (Leave-One-Out, 65 reajustes): 0.669 (dentro da amostra: 0,716) — queda modesta, sem sinal de overfitting severo.
- Coeficiente de `pct_branca` nos 65 reajustes do LOO: desvio-padrão = 0.0004 sobre uma média de 0.0282 — nenhum bairro isolado está "puxando" o resultado.
- Correlação `pct_branca` × `dist_centro_km` = -0.282 — moderada, não os torna intercambiáveis (consistente com o VIF baixo).

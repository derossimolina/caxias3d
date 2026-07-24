# Determinantes espaciais da renda intraurbana em Caxias do Sul (RS): uma análise exploratória a partir de dados do Censo 2022 por bairro

**Projeto:** caxias3d — modelagem geoespacial e agent-based (GABM/Mesa) de Caxias do Sul
**Autor:** J. de Rossi Molina
**Data:** julho de 2026
**Status:** documento de trabalho — análise exploratória para avaliação como linha de pesquisa de doutorado

---

## 1. Resumo

Este documento reporta uma análise exploratória da distribuição espacial de
renda per capita entre os 65 bairros de Caxias do Sul (RS), usando dados
oficiais do Censo Demográfico 2022 do IBGE agregados por bairro, complementados
por um proxy de densidade comercial extraído do OpenStreetMap. Um modelo de
regressão linear (OLS) foi construído incrementalmente, partindo de
regressores geográficos simples (R² = 0,09) até um modelo final com três
variáveis — distância ao centro, composição racial e razão de dependência
etária — que explica **71,6% da variância da renda per capita entre bairros**
(R² ajustado = 0,702). O achado mais robusto é que a proporção de população
branca do bairro é o preditor de maior magnitude e significância estatística
(p < 0,001), superando em poder explicativo variáveis de forma urbana
(densidade, distância ao centro) isoladamente. Esse resultado é consistente
com a literatura estabelecida sobre desigualdade racial e segregação
residencial no Brasil, e abre uma agenda de pesquisa concreta — descrita na
Seção 7 — para aprofundamento em nível de doutorado.

## 2. Motivação e problema de pesquisa

O projeto `caxias3d` nasceu como um pipeline de dados geoespaciais (malha
viária, edificações, limites administrativos) para alimentar um modelo
baseado em agentes (GABM, via Mesa) de Caxias do Sul. A pergunta que motiva
este documento é anterior à modelagem baseada em agentes: **o que explica a
distribuição desigual de renda entre os bairros da cidade?** Compreender os
determinantes estruturais da renda intraurbana é pré-requisito para
parametrizar agentes heterogêneos de forma realista em um GABM, e é também
uma pergunta de pesquisa com valor próprio na literatura de economia urbana e
de desigualdade racial brasileira.

Caxias do Sul é um caso relevante por ser uma cidade média industrial do
interior do Rio Grande do Sul, com colonização predominantemente italiana e
um perfil demográfico atipicamente branco para o padrão nacional (a média
municipal de `pct_branca` ponderada por população é de 76,3%, variando de
51,9% a 91,0% entre bairros — uma faixa de variação ampla o suficiente para
sustentar o teste estatístico, apesar da média municipal alta) — o que
permite testar se a associação entre
composição racial e renda observada em outras cidades brasileiras (em geral
com populações mais diversas) se reproduz mesmo em um contexto demográfico
distinto.

## 3. Dados e fontes

Todas as variáveis usadas são dado real (não estimado/proxy) por bairro,
exceto onde indicado:

| Variável | Fonte | Nível de agregação | Real ou proxy |
|---|---|---|---|
| `renda_pc` (renda média do responsável) | IBGE, Censo 2022, tabela "Rendimento do responsável" | Bairro | Real |
| `escolaridade` (% alfabetizados 15+) | IBGE, Censo 2022, tabelas "Alfabetização" e "Demografia" | Bairro | Real |
| `densidade`, `area_km2`, `populacao` | IBGE, Censo 2022, tabela "Básico" | Bairro | Real |
| `pct_branca` | IBGE, Censo 2022, tabela "Cor ou raça" | Bairro | Real |
| `razao_dependencia` | IBGE, Censo 2022, tabela "Demografia" | Bairro | Real (derivada) |
| `dist_centro_km` | Geometria oficial do IBGE (malha de bairros, Censo 2022) | Bairro | Derivada, sem fonte externa |
| `densidade_comercial_osm` | OpenStreetMap, via Overpass API | Bairro | **Proxy** (mapeamento colaborativo, cobertura desigual) |
| `emprego_formal` | IBGE/CEMPRE (SIDRA, tabela 9509) | Município, distribuído por população | **Estimativa** (sem granularidade real por bairro) |

A malha geográfica usada é a malha oficial de bairros do IBGE do Censo 2022
(65 bairros), não a malha da Prefeitura Municipal (77 bairros, Lei
8.741/2021) — a escolha se deu porque apenas a malha do IBGE tem dado
censitário diretamente agregado por bairro, eliminando a necessidade de join
espacial (ver `pipeline_ibge.py`). Uma limitação decorrente: a malha de
bairros do IBGE cobre apenas a área urbanizada/loteada da cidade — cerca de
92% da população municipal está dentro de algum bairro da malha; o restante
(zona rural dispersa) fica fora da análise.

## 4. Métodos

### 4.1 Clustering

Aplicou-se K-Means sobre `renda_pc`, `log(densidade)`, `log(área)` e
`escolaridade`, padronizados (z-score). O número de clusters foi escolhido
por silhouette score, testando k de 3 a 8 (MacQueen, 1967; Rousseeuw, 1987).
O resultado (k=5) substituiu uma classificação heurística anterior
(if/elif manual sobre limiares arbitrários de renda/densidade) por uma
tipologia orientada a dado — ver `analise_ml.py`.

### 4.2 Regressão

A variável dependente é `log(renda_pc)` (log escolhido pela assimetria
positiva da distribuição de renda, um padrão bem documentado desde Pareto,
1896, e recorrente na literatura de economia do trabalho). A construção do
modelo foi incremental e documentada passo a passo em
`analise_regressao_renda.md`, adicionando regressores em ordem de
disponibilidade/custo de obtenção e removendo os que perdiam significância
estatística a cada rodada — um procedimento próximo à seleção *backward*
clássica (Draper & Smith, 1998), com a ressalva de que, dado N=65, a
comparação de modelos usou também o critério de informação de Akaike (AIC)
para penalizar complexidade e reduzir risco de overfitting.

## 5. Resultados

### 5.1 Evolução do modelo

| Modelo | Regressores | R² | R² ajustado |
|---|---|---|---|
| 1 | escolaridade + log(densidade) + log(área) | 0,092 | 0,048 |
| 2 | + densidade comercial (OSM) | 0,417 | 0,378 |
| 3 | + distância ao centro | 0,522 | 0,482 |
| 4 | apenas log(densidade) + log(densidade comercial) + distância ao centro | 0,504 | 0,480 |
| 5 | + % população branca + razão de dependência | 0,731 | 0,708 |
| **6 (final)** | **distância ao centro + % população branca + razão de dependência** | **0,716** | **0,702** |

O detalhamento completo de cada modelo (coeficientes, erros-padrão,
p-valores, diagnósticos de resíduos) está em `analise_regressao_renda.md`.

### 5.2 Modelo final

```
log(renda_pc) = 6,446 − 0,033 · dist_centro_km + 0,028 · pct_branca − 0,005 · razao_dependencia
```

| Variável | Coeficiente | Erro padrão | p-valor |
|---|---|---|---|
| Constante | 6,446 | 0,218 | < 0,001 |
| `dist_centro_km` | −0,033 | 0,009 | < 0,001 |
| `pct_branca` | +0,028 | 0,003 | < 0,001 |
| `razao_dependencia` | −0,005 | 0,003 | 0,060 |

N = 65 bairros. R² = 0,716; R² ajustado = 0,702. Resíduos aproximadamente
normais (Jarque-Bera p = 0,32). Sem evidência de multicolinearidade
problemática: o Fator de Inflação da Variância (VIF) de cada regressor é
baixo — `dist_centro_km` = 1,11, `pct_branca` = 1,34, `razao_dependencia` =
1,33 —, bem abaixo dos limiares usuais de preocupação (5 ou 10; Wooldridge,
2015). O "Cond. No." reportado pelo `statsmodels` para este modelo (957) não
deve ser comparado diretamente ao limiar clássico de 30 (Belsley, Kuh &
Welsch, 1980): esse limiar vale para o *condition index* calculado sobre
variáveis padronizadas e sem a constante, enquanto o `statsmodels` calcula
sobre a matriz de regressores crua, incluindo a constante — o que infla o
número por diferença de escala entre as variáveis, não por colinearidade
real. Recalculado corretamente (variáveis padronizadas, sem constante), o
condition index deste modelo é 1,8 — bem abaixo de 30 —, consistente com os
VIFs. Ainda assim, o valor bruto do `statsmodels` é útil para comparação
*relativa* entre modelos: caiu de ~24.700 (Modelo 1, com `log(área)`) para
957 (modelo final), confirmando que remover `log(área)` reduziu a
colinearidade introduzida por ela.

### 5.3 Achado central

`pct_branca` é, isoladamente, a variável de maior poder explicativo do
modelo — mais forte que forma urbana (densidade, distância ao centro) e mais
forte que escolaridade (que, em Caxias do Sul, tem variância quase nula:
96–100% de alfabetização em todos os bairros, um efeito-teto que a torna
estatisticamente inútil como discriminador de renda, apesar de ser dado real
e correto).

## 6. Discussão e limitações

**Correlação, não causalidade.** O coeficiente de `pct_branca` não deve ser
lido como "a raça causa renda". No Brasil, raça está historicamente
correlacionada com acesso desigual a herança, educação, redes de emprego e
concentração espacial por políticas urbanas e habitacionais historicamente
excludentes (Telles, 2004; Villaça, 2001) — o coeficiente captura esse feixe
de mecanismos estruturais, não um efeito unicausal.

**Falácia ecológica.** Todas as variáveis são agregadas por bairro, não por
indivíduo ou domicílio. Uma correlação observada no nível do bairro não
implica necessariamente a mesma relação no nível individual (Robinson,
1950) — este é talvez o limite metodológico mais importante do desenho atual,
e o primeiro ponto a resolver caso o projeto avance para doutorado (ver
Seção 7).

**Tamanho de amostra.** N=65 é adequado para um modelo de 3 regressores por
regras de bolso usuais (ex. Green, 1991: N ≥ 50 + 8k para R² geral, aqui
50+24=74 — ligeiramente acima do N disponível, um sinal de que o modelo está
no limite superior do que a amostra sustenta com confiança), mas é pequeno
para testar especificações mais ricas (interações, nível de flexibilidade
não-linear) sem risco real de overfitting. Cada nova variável testada neste
projeto foi avaliada tanto por R² quanto por AIC exatamente por essa razão.

**Emprego formal não é dado real por bairro.** Como documentado em
`pipeline_ibge.py` e nas seções anteriores de `analise_regressao_renda.md`,
não existe fonte pública com granularidade de bairro para emprego formal
(CAGED/RAIS têm apenas nível municipal nas APIs abertas). A variável
`emprego_formal` no dataset é uma estimativa distribuída proporcionalmente à
população e foi deliberadamente excluída de todas as regressões por
circularidade.

**Densidade comercial é proxy, não dado oficial.** A contagem de
estabelecimentos do OpenStreetMap depende do quanto cada bairro foi mapeado
por voluntários — pode haver viés sistemático (bairros centrais/de classe
média tendem a ser mais editados no OSM) que não é possível separar, com os
dados atuais, de uma diferença real de atividade econômica.

**Possível causalidade reversa / simultaneidade.** É plausível que
`dist_centro_km` e `pct_branca` sejam eles próprios resultado de processos
históricos de valorização fundiária e mercado imobiliário que também
determinam renda — nesse caso, a regressão captura um equilíbrio de longo
prazo, não uma cadeia causal unidirecional.

## 7. Agenda de pesquisa (linhas para doutorado / paper)

1. **Segregação racial residencial e renda em cidades médias do interior do
   Sul do Brasil.** A literatura de segregação racial urbana no Brasil é
   concentrada em grandes metrópoles (São Paulo, Rio de Janeiro, Salvador —
   Telles, 2004; Marques & Torres, 2005). Caxias do Sul, com composição racial
   atípica para o padrão nacional, é um caso pouco explorado e
   potencialmente informativo por contraste.

2. **Do bairro ao indivíduo: resolver a falácia ecológica.** Cruzar os
   agregados por bairro com microdados do Censo (setor censitário, ainda
   mais desagregado) ou com dados amostrais (PNAD Contínua, restrita a
   nível estadual/metropolitano) para testar se a relação sobrevive em
   nível mais fino — ou desenhar um estudo com dados de domicílio
   (ex. releases futuras de microdados identificados do Censo 2022) seria o
   passo metodológico mais importante para elevar o rigor causal do
   argumento.

3. **Econometria espacial.** O modelo atual é OLS "ingênuo": não testa
   autocorrelação espacial dos resíduos (Moran's I) nem modela
   explicitamente que bairros vizinhos tendem a se parecer (Anselin, 1988).
   Um modelo de defasagem espacial (*spatial lag*) ou erro espacial
   (*spatial error*) é o próximo passo metodológico natural, e é um tema
   com tradição consolidada e citável (Anselin & Rey, 2014).

4. **Integração com o GABM (Mesa).** Os clusters e coeficientes deste
   modelo podem parametrizar a geração de população sintética de agentes
   heterogêneos (renda, raça, idade) no modelo baseado em agentes já em
   desenvolvimento no projeto — ligando a análise estatística exploratória a
   uma ferramenta de simulação de políticas urbanas (ex.: simular efeitos de
   uma intervenção de mobilidade ou habitação sobre a distribuição espacial
   de renda). Ver Batty (2013) e Crooks et al. (2019) para o enquadramento
   metodológico de ABM em estudos urbanos.

5. **Replicação temporal.** O Censo 2010 permite testar se os mesmos
   determinantes (sobretudo composição racial) explicavam a renda por bairro
   há uma década, e se a magnitude do efeito mudou — um desenho
   quase-longitudinal que fortalece (ou desafia) a robustez do achado atual.

## 8. Referências

ALONSO, W. **Location and Land Use: Toward a General Theory of Land Rent**. Cambridge, MA: Harvard University Press, 1964.

ANSELIN, L. **Spatial Econometrics: Methods and Models**. Dordrecht: Kluwer Academic Publishers, 1988.

ANSELIN, L.; REY, S. J. **Modern Spatial Econometrics in Practice: A Guide to GeoDa, GeoDaSpace and PySAL**. Chicago: GeoDa Press, 2014.

ARIAS, O.; YAMADA, G.; TEJERINA, L. Education, family background and racial earnings inequality in Brazil. **International Journal of Manpower**, v. 25, n. 3/4, p. 355–374, 2004.

BATTY, M. **The New Science of Cities**. Cambridge, MA: MIT Press, 2013.

BELSLEY, D. A.; KUH, E.; WELSCH, R. E. **Regression Diagnostics: Identifying Influential Data and Sources of Collinearity**. New York: Wiley, 1980.

CROOKS, A.; MALLESON, N.; MANLEY, E.; HEPPENSTALL, A. **Agent-Based Modelling and Geographical Information Systems: A Practical Primer**. London: Sage, 2019.

DRAPER, N. R.; SMITH, H. **Applied Regression Analysis**. 3. ed. New York: Wiley, 1998.

FUJITA, M.; KRUGMAN, P.; VENABLES, A. J. **The Spatial Economy: Cities, Regions, and International Trade**. Cambridge, MA: MIT Press, 1999.

GLAESER, E. L. **Cities, Agglomeration, and Spatial Equilibrium**. Oxford: Oxford University Press, 2008.

GREEN, S. B. How many subjects does it take to do a regression analysis? **Multivariate Behavioral Research**, v. 26, n. 3, p. 499–510, 1991.

HAIR, J. F.; BLACK, W. C.; BABIN, B. J.; ANDERSON, R. E. **Multivariate Data Analysis**. 8. ed. Andover: Cengage Learning, 2019.

IBGE — INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. **Censo Demográfico 2022: metodologia**. Rio de Janeiro: IBGE, 2023.

MACQUEEN, J. Some methods for classification and analysis of multivariate observations. In: **Proceedings of the 5th Berkeley Symposium on Mathematical Statistics and Probability**, v. 1, p. 281–297, 1967.

MARQUES, E.; TORRES, H. (org.). **São Paulo: Segregação, Pobreza e Desigualdades Sociais**. São Paulo: Senac, 2005.

MINCER, J. **Schooling, Experience, and Earnings**. New York: National Bureau of Economic Research, 1974.

MODIGLIANI, F.; BRUMBERG, R. Utility analysis and the consumption function: an interpretation of cross-section data. In: KURIHARA, K. K. (org.). **Post-Keynesian Economics**. New Brunswick: Rutgers University Press, 1954.

MUTH, R. F. **Cities and Housing**. Chicago: University of Chicago Press, 1969.

OSORIO, R. G. **A desigualdade racial da pobreza no Brasil**. Texto para Discussão n. 2510. Brasília: IPEA, 2019.

PAIXÃO, M.; CARVANO, L. M. (org.). **Relatório Anual das Desigualdades Raciais no Brasil**. Rio de Janeiro: LAESER/UFRJ, 2008.

PARETO, V. **Cours d'Économie Politique**. Lausanne: F. Rouge, 1896.

ROBINSON, W. S. Ecological correlations and the behavior of individuals. **American Sociological Review**, v. 15, n. 3, p. 351–357, 1950.

ROUSSEEUW, P. J. Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. **Journal of Computational and Applied Mathematics**, v. 20, p. 53–65, 1987.

TELLES, E. E. **Race in Another America: The Significance of Skin Color in Brazil**. Princeton: Princeton University Press, 2004.

VILLAÇA, F. **Espaço Intra-Urbano no Brasil**. São Paulo: Studio Nobel, 2001.

WOOLDRIDGE, J. M. **Introductory Econometrics: A Modern Approach**. 6. ed. Boston: Cengage Learning, 2015.

---

## Apêndice: reprodutibilidade

Todo o pipeline é reprodutível a partir do repositório do projeto:

```
pipeline_ibge.py           # baixa dados reais do IBGE por bairro, gera dados_bairros.json
analise_ml.py               # clustering (KMeans) + regressão inicial
analise_osm_economia.py     # densidade comercial via OpenStreetMap/Overpass
analise_regressao_v2.py     # distância ao centro + log(renda)
analise_regressao_v3.py     # composição racial + estrutura etária, modelo final
```

Saída estatística completa (todos os modelos, coeficientes e diagnósticos):
`analise_regressao_renda.md`.

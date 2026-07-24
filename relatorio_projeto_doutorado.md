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
regressão linear (OLS) foi construído incrementalmente, partindo de uma
especificação inicial simples (escolaridade e forma urbana, R² = 0,08) até
um modelo final com três variáveis — distância ao centro, composição racial
e razão de dependência etária — que explica **71,6% da variância de
log(renda per capita) entre bairros** (R² ajustado = 0,702). O achado mais
robusto é que a proporção de população branca do bairro é o preditor de
maior peso padronizado do modelo final (beta = 0,795, quase 3× o peso de
`dist_centro_km`) e o mais significativo estatisticamente (p < 0,001) — ver
Seção 5.3. Esse resultado é consistente com a literatura estabelecida sobre
desigualdade racial e segregação residencial no Brasil, e abre uma agenda de
pesquisa concreta — descrita na Seção 7 — para aprofundamento em nível de
doutorado. Como qualquer resultado de uma busca de especificação exploratória
sobre um único conjunto de dados (Seção 4.2), este achado deve ser lido como
corroboração provisória, não confirmação definitiva — a Seção 7 propõe
justamente testá-lo de novo, de forma mais rigorosa, com outros dados e
métodos.

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
95,2% da população municipal está dentro de algum bairro da malha (441.199
de um total municipal de 463.501 pelo Censo 2022, tabela "Básico" agregada
por município); o restante — 4,8%, cerca de 22 mil pessoas, majoritariamente
zona rural dispersa — fica fora da análise.

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

### 5.0 Clustering

O K-Means (Seção 4.1) convergiu para k=5 clusters, cada um com um perfil
socioeconômico distinto (renda e densidade médias):

| Cluster | Bairros (n) | Renda média | Densidade média |
|---|---|---|---|
| `central_rico` | 17 | R$ 5.626 | 6.103 hab/km² |
| `central_medio` | 15 | R$ 3.572 | 543 hab/km² |
| `urbano_medio` | 5 | R$ 3.488 | 6.573 hab/km² |
| `urbano_popular` | 27 | R$ 3.040 | 3.362 hab/km² |
| `central_medio_alto_disperso` | 1 | R$ 3.585 | 39 hab/km² |

Dois pontos chamam atenção: o cluster `central_rico` (17 bairros) tem renda
média quase o dobro do `urbano_popular` (27 bairros, o maior grupo), e
`urbano_medio` e `central_medio` têm rendas parecidas (R$ 3.488 vs. R$
3.572) apesar de densidades muito diferentes (6.573 vs. 543 hab/km²). Isso
não é um teste formal — é uma leitura qualitativa de apenas 2 dos 5
clusters, e a Seção 5.0 já declara que este clustering não alimenta a
regressão — mas aponta na mesma direção do teste formal feito nas Seções
5.1 (o salto de R² ao entrar `pct_branca`) e 5.3 (comparação de betas
padronizados): densidade sozinha não separa bem grupos de renda parecida
em Caxias do Sul. O cluster de 1 bairro isolado
(`central_medio_alto_disperso`) reflete um caso atípico (baixíssima
densidade, mas renda mediana) que provavelmente merece inspeção individual
antes de qualquer uso desses clusters para gerar população sintética no
GABM (Seção 7, item 4) — um cluster de tamanho 1 não é uma categoria
estatisticamente estável.

Este clustering substituiu uma classificação heurística anterior (if/elif
manual sobre limiares arbitrários de renda/densidade) por uma tipologia
orientada a dado, mas não foi usado como insumo da regressão da Seção 5.1
em diante — são duas análises complementares, não sequenciais.

### 5.1 Evolução do modelo

Todos os modelos abaixo usam a mesma variável dependente, `log(renda_pc)`,
para serem comparáveis entre si por R² — nas primeiras rodadas exploratórias
(documentadas em `analise_regressao_renda.md`) alguns desses mesmos modelos
foram testados também com `renda_pc` bruta, o que dá números de R²
diferentes (não comparáveis) para a mesma especificação; os valores abaixo
foram recalculados de forma consistente especificamente para esta tabela.

| Modelo | Regressores | R² | R² ajustado | AIC |
|---|---|---|---|---|
| 1 | escolaridade + log(densidade) + log(área) | 0,084 | 0,039 | 39,6 |
| 2 | + densidade comercial (OSM) | 0,431 | 0,393 | 10,6 |
| 3 | + distância ao centro | 0,519 | 0,479 | 1,7 |
| 4 | apenas log(densidade) + log(densidade comercial) + distância ao centro (tira escolaridade e log(área), não significativas) | 0,502 | 0,477 | 0,0 |
| 5 | + % população branca + razão de dependência | 0,730 | 0,707 | −35,7 |
| **6 (final)** | **distância ao centro + % população branca + razão de dependência** (tira log(densidade) e log(densidade comercial), não significativas em 5) | **0,716** | **0,702** | **−36,6** |

O modelo 6 tem R² marginalmente menor que o modelo 5 (0,716 vs. 0,730) — a
escolha do modelo 6 como final não é sobre maximizar R², e sim sobre
parcimônia: com duas variáveis a menos, o AIC melhora (menor é melhor:
−36,6 vs. −35,7). Uma ressalva de precisão: `razao_dependencia` tem p=0,060
no modelo final — não atinge o limiar convencional de 5% usado no resto
deste documento, embora esteja próximo. Ela foi mantida porque sua inclusão
melhora o AIC (−36,6 com ela vs. −34,8 sem ela) e porque tem um mecanismo
teórico plausível independente do ajuste estatístico: razão de dependência
mais alta significa mais dependentes (crianças e idosos) por adulto em
idade ativa no bairro, o que tende a reduzir a renda disponível por pessoa
no domicílio mesmo sem mudar a renda de quem trabalha — um efeito
composicional/demográfico (Modigliani & Brumberg, 1954; Mincer, 1974), não
um artefato do ajuste. Isso não substitui o fato de que a decisão de
mantê-la foi tomada depois de ver o p-valor (ver Seção 6.1, resposta 3) —
o mecanismo teórico é uma justificativa a priori para *testar* a variável,
não para *mantê-la* apesar do resultado.

O detalhamento completo de cada modelo (coeficientes, erros-padrão,
p-valores, diagnósticos de resíduos) está em `analise_regressao_renda.md` —
nota-se que os números lá batem com os daqui apenas para os modelos que já
usavam `log(renda_pc)` desde o início (a partir da "Extensão 2"); os
primeiros dois modelos foram recalculados aqui com DV consistente.

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
VIFs.

O valor bruto do `statsmodels` também é útil para comparação *relativa*
entre modelos, mas exige cuidado para não atribuir uma queda a uma variável
errada quando mais de uma muda ao mesmo tempo. Do Modelo 3 (`escolaridade` +
`log(densidade)` + `log(área)` + densidade comercial + distância ao centro;
Cond. No. ≈ 24.800) para o Modelo 4 (tira `escolaridade` e `log(área)`;
Cond. No. ≈ 105) duas variáveis saem ao mesmo tempo — não dá para atribuir a
queda a uma delas sem testar cada uma isoladamente. Ao fazer esse teste
(remover só uma de cada vez a partir do Modelo 3): tirar apenas `log(área)`
já derruba o Cond. No. para ≈ 110; tirar apenas `escolaridade` o mantém em
≈ 24.600, praticamente inalterado. Ou seja, `log(área)` era de fato a quase
totalidade da fonte de colinearidade bruta nesse trecho da cadeia — mas essa
é uma conclusão de um teste isolado à parte, não uma inferência direta da
comparação Modelo 3 → Modelo 4.

Essa mesma cautela vale, com mais força, para a comparação entre o Modelo 1
e o modelo final: nenhum Cond. No. do Modelo 1 é reportado neste documento
(o valor de ≈24.800 citado acima é do Modelo 3, não do Modelo 1), e entre um
e outro seis variáveis distintas mudam — saem `escolaridade`, `log(área)` e
`log(densidade)`; entram densidade comercial, distância ao centro,
`pct_branca` e `razao_dependencia` (sendo densidade comercial removida de
volta no passo final, junto com `log(densidade)`; `pct_branca` e
`razao_dependencia` permanecem no modelo final — ver Tabela 5.1 e a equação
acima). O Cond. No. nem cai de forma monotônica ao longo dessa cadeia: sobe
de 105 (Modelo 4) para 2.328 (Modelo 5) ao entrar `pct_branca`/
`razao_dependencia`, antes de cair para 957 no modelo final ao sair
`log(densidade)`/densidade comercial. Não há, portanto, uma atribuição de
causa única defensável para a diferença entre o Cond. No. do Modelo 1 e o
do modelo final — o dado relevante e já demonstrado é apenas que o modelo
final (957) está longe de ser preocupante por VIF e pelo condition index
corretamente calculado (1,8), independentemente de qual comparação de
Cond. No. bruto se queira fazer.

### 5.3 Achado central

Os coeficientes da Seção 5.2 não são diretamente comparáveis em magnitude
entre si — estão em unidades diferentes (`dist_centro_km` em quilômetros,
`pct_branca` em pontos percentuais, `razao_dependencia` em outra escala de
pontos percentuais). Para comparar a força relativa de cada preditor de
forma válida, recalculou-se o modelo final com todas as variáveis
padronizadas (z-score), obtendo coeficientes beta:

| Variável | Beta padronizado | p-valor |
|---|---|---|
| `pct_branca` | 0,795 | < 0,001 |
| `dist_centro_km` | −0,274 | < 0,001 |
| `razao_dependencia` | −0,151 | 0,060 |

`pct_branca` é, de fato, o preditor dominante do modelo por uma margem
considerável — quase três vezes o peso padronizado de `dist_centro_km` — não
apenas o mais significativo. `escolaridade` não é comparável aqui porque não
faz parte do modelo final: foi descartada ainda no Modelo 4 (Seção 5.1) por
não ser significativa em nenhuma especificação testada, um efeito plausível
de teto estatístico (em Caxias do Sul a alfabetização de 15+ anos varia
apenas entre 96% e 100% conforme o bairro), mas essa é uma leitura
qualitativa da ausência de variância, não uma comparação de coeficientes
dentro do mesmo modelo.

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

**Tamanho de amostra.** Green (1991) propõe duas regras de bolso distintas
para N mínimo, e é importante não misturá-las: N ≥ 50 + 8k para testar o R²
geral do modelo, e N ≥ 104 + k para testar coeficientes individuais. Com
k=3, isso dá 74 e 107, respectivamente. N=65 fica abaixo dos dois limiares,
mas a diferença importa: a maioria das afirmações deste documento (p-valor
de cada variável, comparação de betas padronizados na Seção 5.3) é sobre
coeficientes individuais — o teste mais exigente (107) — não sobre o R² do
modelo como um todo. N=65 está bem abaixo de 107, um sinal mais sério de
que os p-valores e a ordenação de importância entre as três variáveis devem
ser lidos com cautela, não apenas como "no limite" da amostra disponível.
Isso não invalida os resultados, mas reforça que este é um estudo
exploratório a ser testado de novo com mais dados (Seção 7), não uma
estimativa definitiva. A amostra também é pequena para testar
especificações mais ricas (interações, termos não-lineares) sem risco real
de overfitting — por isso cada variável testada neste projeto foi avaliada
por R² e por AIC, não só por p-valor.

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

### 6.1 Respostas às perguntas popperianas

Uma revisão epistemológica independente deste documento fechou com quatro
perguntas endereçadas diretamente a este achado. Respondê-las exigiu rodar testes novos, não só qualificar o texto —
os números estão em `analise_robustez.py` e na seção "Extensão 4" de
`analise_regressao_renda.md`.

**1. Dado que o modelo foi construído por busca de especificação
(adicionar/remover variáveis por significância e AIC), `pct_branca` teria
alguma chance de não ter emergido como achado central, ou qualquer variável
testada acabaria lá?**
Testável, e testado: `pct_branca` sozinha, sem `dist_centro_km` nem
`razao_dependencia`, explica R² = 0,640 de um R² total de 0,716 no modelo
completo — ou seja, o achado não depende da combinação específica de
covariáveis que sobrou no fim da busca; ele é dominante mesmo como preditor
único. Isso não prova que nenhuma variável testada "teria alguma chance" —
não há como testar isso retroativamente sem pré-registro — mas mostra que,
*neste* achado específico, o resultado não é um artefato frágil da ordem em
que as variáveis entraram ou saíram do modelo.

**2. Existe alguma especificação testada que enfraqueceria o achado sobre
raça, e que não foi reportada (viés de confirmação por omissão)?**
Não — nenhuma das especificações testadas e reportadas neste documento
enfraquece `pct_branca`. Mas a pergunta certa não é só "o que já foi
testado", é "o que ainda não foi tentado que poderia refutar". Três testes
novos foram rodados especificamente para tentar isso: (a) validação cruzada
Leave-One-Out — R² fora da amostra cai de 0,716 para 0,669, uma queda
modesta, não um colapso; (b) estabilidade do coeficiente de `pct_branca` nos
65 reajustes do LOO — desvio-padrão de 0,0004 sobre uma média de 0,0282,
ou seja, nenhum bairro isolado sustenta o resultado sozinho; (c) correlação
`pct_branca` × `dist_centro_km` = −0,282 — moderada, não os torna a mesma
coisa medida duas vezes. Nenhum desses três testes enfraqueceu o achado.
Isso é evidência a favor, mas não é uma tentativa exaustiva de refutação:
não foram testadas interações (`pct_branca` × `dist_centro_km`), termos
não-lineares, nem uma especificação com erros-padrão robustos a
heterocedasticidade espacial — essas continuam como avenidas genuinamente
abertas para enfraquecer o achado, não descartadas.

**3. `razao_dependencia` (p=0,060) foi mantida por um critério definido
antes de ver o resultado, ou depois?**
Depois — e é importante dizer isso sem meias palavras. A Seção 4.2 descreve
um procedimento exploratório (remover por significância, comparar por AIC),
não um teste confirmatório com critérios de inclusão pré-registrados. A
decisão de manter `razao_dependencia` foi tomada depois de ver que sua
inclusão melhora o AIC (Seção 5.1) e depois de ver seu p-valor específico
(0,060) — não antes. Isso é intrínseco a um estudo exploratório sobre um
único conjunto de dados, e é exatamente o tipo de grau de liberdade do
pesquisador que motiva a Seção 7, item 5 (replicação temporal): qualquer
estudo confirmatório subsequente deveria pré-registrar o critério de
inclusão de variáveis antes de olhar os dados — a resposta 4, a seguir,
aplica esse pré-registro na prática.

**4. Que resultado, na replicação temporal com o Censo 2010 (Seção 7, item
5), contaria como evidência *contra* a robustez do achado, e não só como
mais uma corroboração se o sinal se repetir?**
Critério definido agora, antes de rodar essa replicação (o pré-registro que
a pergunta 3 identificou como faltante, aplicado aqui): contaria como
evidência contra (a) o beta padronizado de `pct_branca` cair abaixo de 0,3
(menos da metade do valor atual, 0,795) mesmo mantendo significância, (b)
`pct_branca` perder significância a 5% no modelo 2010, ou (c) o sinal do
coeficiente inverter. Qualquer um desses três resultados seria reportado
como enfraquecimento do achado, não reinterpretado para "salvá-lo" — a
alternativa (mudar a explicação teórica post-hoc para acomodar um resultado
que contraria a expectativa, sem base independente) seria imunização ad hoc
e vai contra o espírito desta seção.

## 7. Agenda de pesquisa (linhas para doutorado / paper)

1. **Segregação racial residencial e renda em cidades médias do interior do
   Sul do Brasil.** A literatura sobre segregação urbana especificamente —
   como a de Marques & Torres (2005) — é concentrada em grandes metrópoles
   (o estudo deles é sobre São Paulo); a literatura mais ampla sobre
   desigualdade racial no Brasil, incluindo Telles (2004), é de escopo
   nacional mas também tem seu material empírico dominado por grandes
   centros urbanos. Caxias do Sul, cidade média com composição racial
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

IBGE — INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. **Censo Demográfico 2022**. Rio de Janeiro: IBGE, 2023. Disponível em: https://www.ibge.gov.br/estatisticas/sociais/trabalho/22827-censo-demografico-2022.html. Acesso em: 24 jul. 2026.

MACQUEEN, J. Some methods for classification and analysis of multivariate observations. In: **Proceedings of the 5th Berkeley Symposium on Mathematical Statistics and Probability**, v. 1, p. 281–297, 1967.

MARQUES, E.; TORRES, H. (org.). **São Paulo: Segregação, Pobreza e Desigualdades Sociais**. São Paulo: Senac, 2005.

MINCER, J. **Schooling, Experience, and Earnings**. New York: National Bureau of Economic Research, 1974.

MODIGLIANI, F.; BRUMBERG, R. Utility analysis and the consumption function: an interpretation of cross-section data. In: KURIHARA, K. K. (org.). **Post-Keynesian Economics**. New Brunswick: Rutgers University Press, 1954.

MUTH, R. F. **Cities and Housing**. Chicago: University of Chicago Press, 1969.

OSORIO, R. G. **A desigualdade racial da pobreza no Brasil**. Texto para Discussão n. 2487. Brasília: IPEA, 2019.

PAIXÃO, M.; CARVANO, L. M. (org.). **Relatório Anual das Desigualdades Raciais no Brasil, 2007-2008**. Rio de Janeiro: Garamond/LAESER-UFRJ, 2008.

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
analise_robustez.py         # testes de robustez (LOO-CV, univariado, correlação)
```

Saída estatística completa (todos os modelos, coeficientes e diagnósticos):
`analise_regressao_renda.md`.

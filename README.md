# Caxias 3D

Mapa 3D interativo de Caxias do Sul (RS) com dados socioeconômicos reais por
bairro (Censo IBGE 2022), mais uma linha de análise exploratória (clustering
e regressão) sobre os determinantes espaciais da renda per capita entre
bairros.

**Site**: `index.html` — mapa interativo (satélite + choropleth) com 4
indicadores por bairro: renda, densidade, escolaridade e emprego formal.

## Estrutura

### Pipeline de dados (IBGE)

```
pipeline_ibge.py
```

Baixa dados reais do Censo Demográfico 2022, já agregados oficialmente por
bairro pelo IBGE (sem join espacial nem proxies inventados), e gera:

- `dados_bairros.json` — indicadores por bairro
- `Limites_dos_Bairros.geojson` — malha oficial de bairros do IBGE (65
  bairros)

Fontes por indicador:

| Indicador | Fonte | Real ou estimado |
|---|---|---|
| população, área, densidade | IBGE Censo 2022, tabela "Básico" | Real |
| renda per capita | IBGE Censo 2022, tabela "Rendimento do responsável" | Real |
| escolaridade (% alfabetizados 15+) | IBGE Censo 2022, tabelas "Alfabetização" + "Demografia" | Real |
| emprego formal | IBGE/CEMPRE via SIDRA (tabela 9509) | Estimativa — total municipal distribuído proporcionalmente à população (não existe granularidade por bairro nas fontes públicas) |

As URLs de download são resolvidas dinamicamente a partir da listagem do
diretório do FTP do IBGE (o nome dos arquivos muda de data a cada
atualização) — o pipeline sempre baixa a versão mais recente disponível.

### Análise: clustering e regressão

```
analise_ml.py               # clustering (KMeans) do perfil socioeconômico + regressão inicial
analise_osm_economia.py     # densidade comercial por bairro via OpenStreetMap (Overpass API)
analise_regressao_v2.py     # distância ao centro (derivada da geometria) + log(renda)
analise_regressao_v3.py     # composição racial + estrutura etária — modelo final
```

Rodar nessa ordem, depois de `pipeline_ibge.py`. Cada script escreve de
volta em `dados_bairros.json` (novos campos) e acrescenta uma seção em
`analise_regressao_renda.md` com o resultado estatístico completo.

O modelo final (R² = 0,716, ajustado 0,702) explica renda per capita por
bairro a partir de distância ao centro, % de população branca e razão de
dependência etária. Ver a análise completa, com revisão de literatura e
discussão de limitações, em:

- [`relatorio_projeto_doutorado.md`](relatorio_projeto_doutorado.md) — documento de trabalho completo (também espelhado no Obsidian, em `Projetos/Caxias em 3D - Dimensões Sociais e Econômicas de uma grande cidade.md`)
- [`analise_regressao_renda.md`](analise_regressao_renda.md) — saída bruta de cada modelo testado

### Geoespacial complementar

```
caxias_pipeline_geo.py
```

Baixa malha viária e edificações (OpenStreetMap/OSMnx) e o limite municipal
(IBGE/geobr) para gerar uma visualização 3D navegável (deck.gl) —
`caxias_3d.html`. Pensado para alimentar um modelo baseado em agentes
(GABM, via Mesa) futuro.

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 pipeline_ibge.py
python3 analise_ml.py
python3 analise_osm_economia.py
python3 analise_regressao_v2.py
python3 analise_regressao_v3.py

python3 -m http.server 8787   # depois abrir http://localhost:8787
```

## Limitações conhecidas

- A malha de bairros do IBGE cobre só a área urbanizada/loteada — cerca de
  4,8% da população municipal (zona rural dispersa) fica fora da análise.
- `emprego_formal` é estimativa, não medição por bairro (ver tabela acima).
- `densidade_comercial_osm` é proxy de atividade econômica via OpenStreetMap
  — sujeito a viés de cobertura do mapeamento colaborativo.
- A regressão é OLS transversal (N=65, um único ano) — correlação, não
  causalidade. Discussão completa em `relatorio_projeto_doutorado.md`.

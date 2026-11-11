# Olist — Inteligência Logística e Experiência do Cliente

Projeto de portfólio para investigar atrasos nas entregas e sua associação com as avaliações dos clientes.

## Objetivo

Identificar segmentos que devem ser priorizados em uma investigação operacional, considerando volume de atrasos, gravidade e avaliações baixas.

## Status

Auditoria dos nove CSVs e primeira tabela analítica por pedido concluídas e validadas. O dashboard, a análise aprofundada e a implantação AWS são etapas futuras. Os dados da Olist são históricos e as cargas incrementais serão demonstradas por simulação documentada.

## Tecnologias

Python 3.13, SQL com DuckDB, Excel, Power BI e Git. A implantação demonstrativa na AWS com Terraform depende da confirmação da elegibilidade ao plano gratuito.

## Preparar o ambiente

```powershell
conda create -n portfolio-dados python=3.13 pip --override-channels -c conda-forge -y
conda activate portfolio-dados
python -m pip install -r requirements.txt
python -m ipykernel install --user --name portfolio-dados --display-name "Python (portfolio-dados)"
```

Se o ambiente já existir, comece pela ativação. No VS Code, selecione o interpretador ou kernel `Python (portfolio-dados)`.

## Obter os dados

```powershell
python src/download_data.py
```

O script baixa o arquivo público do Kaggle e extrai os nove CSVs esperados em `data/raw`. Os dados ficam fora do histórico Git. Se o Kaggle exigir login, baixe o ZIP pela página da base e execute `python src/download_data.py --archive "CAMINHO_DO_ZIP"`.

Fonte original de Olist e colaboradores, Brazilian E-Commerce Public Dataset by Olist, disponível no [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Consulte a licença e os termos na página original antes de redistribuir os dados.

## Estrutura

| Pasta | Conteúdo previsto |
|---|---|
| `data/raw` | CSVs originais, ignorados pelo Git |
| `data/processed` | Dados tratados, ignorados pelo Git |
| `src` | Scripts de ingestão e processamento |
| `notebooks` | Investigação e gráficos |
| `sql` | Modelo analítico e consultas |
| `tests` | Testes do processamento |
| `excel` | Auditoria e reconciliação |
| `dashboards` | Relatório Power BI |
| `infra` | Infraestrutura AWS em Terraform |
| `docs` | Definições de indicadores e decisões |

## Próximas entregas

1. Reconciliar indicadores no Excel e no Power BI.
2. Investigar atrasos por mês e UF e cobertura das avaliações.
3. Demonstrar cargas incrementais mensais.
4. Documentar os resultados e, se elegível, executar a demonstração AWS gratuita.

## Executar auditoria e construir a tabela

```powershell
conda activate portfolio-dados
python src/build_analytics.py
python -m pytest tests -q
```

O script executa `sql/build_orders.sql` no DuckDB. O relatório público está em [docs/data_audit.md](docs/data_audit.md) e as regras em [docs/metric_rules.md](docs/metric_rules.md).

`data/processed/current.json` informa a versão local ativa. Dentro dela ficam `olist.duckdb` (fontes, `analytics_orders` e `reconciliation`), `orders.parquet`, `reconciliation.csv`, `audit.json` e `audit.md`. Os arquivos de dados ficam fora do GitHub.

Primeiro resultado histórico com as regras documentadas: 99.441 pedidos preservados, 96.470 elegíveis e 6.534 atrasados, ou 6,77% dos elegíveis. A data prometida é interpretada como um dia de calendário.

## Custo

A execução local usa ferramentas já disponíveis no computador. A licença do Excel deve estar válida. A demonstração na AWS exige verificação prévia do plano gratuito e dos serviços disponíveis na conta. A publicação inicial do portfólio pode usar o GitHub e imagens do Power BI Desktop.

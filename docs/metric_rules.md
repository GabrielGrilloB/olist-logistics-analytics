# Regras da primeira tabela analítica

Uma linha representa um pedido da tabela original, incluindo cancelados e pedidos incompletos. O cruzamento usa `LEFT JOIN` para preservar todos os pedidos. Itens, pagamentos e geolocalização são auditados, mas ficam fora desse cruzamento para preservar a granularidade.

## Entregas

- `delivery_eligible` exige status `delivered`, compra, entrega e previsão preenchidas, entrega após ou no instante da compra e dia prometido após ou no dia da compra.
- `is_late` compara os dias de calendário. Entregas no dia prometido são pontuais mesmo quando o horário passa de meia-noite. Não há conversão de fuso, pois a fonte não fornece um fuso explícito para cada registro.
- `delay_days` é a diferença de dias entre entrega e previsão, limitada a zero para entregas antecipadas. Para pedidos inelegíveis, atraso e dias ficam nulos.
- A taxa de atraso divide pedidos atrasados pelos pedidos elegíveis, com os mesmos filtros de mês e UF. O mês usado na reconciliação é o da compra.
- Data em formato inválido bloqueia a publicação. Ausência de datas é documentada e afeta a elegibilidade.

## Avaliações

- A nota é vinculada pelo pedido. Quando há múltiplas respostas, a mais recente por `review_answer_timestamp` é escolhida.
- Os desempates usam data de criação, identificador, nota e comentários em ordem decrescente. Essa regra garante resultado estável e representa uma escolha técnica documentada.
- `review_count` mantém a quantidade original de avaliações do pedido.
- Nota 1 ou 2 é avaliação baixa. Uma nota ausente permanece nula.
- A proporção de avaliações baixas usa somente pedidos com nota válida. Para comparar pontuais e atrasados, restrinja primeiro aos pedidos elegíveis e apresente a cobertura de avaliações de cada grupo.
- Associação entre atraso e nota não demonstra causalidade.

## Auditoria e publicação local

`audit.json` contém linhas, colunas, ausências por campo, duplicatas, chaves, referências órfãs e datas com formato inválido nos nove CSVs. Duplicatas e ausência de chave em entidades com chave definida bloqueiam a publicação. A geolocalização permite linhas repetidas e as avaliações permitem múltiplas linhas por pedido.

Referências órfãs nas relações de pedidos, itens, pagamentos, clientes, vendedores e produtos bloqueiam a publicação. Categorias sem tradução são registradas e mantidas na fonte.

O Python recalcula elegibilidade, atraso e duração usando pandas e compara com o resultado do SQL. Também confere a quantidade e o conjunto de IDs, a unicidade e os totais da reconciliação.

Cada versão local tem identificação SHA-256 calculada a partir dos nove arquivos, do código de processamento, do SQL e das dependências registradas. A versão só é publicada depois das validações. `data/processed/current.json` aponta para a versão ativa e é substituído atomicamente. Uma falha anterior a essa troca mantém a versão ativa anterior.

Executar novamente as mesmas entradas verifica os dados outra vez e conserva o mesmo identificador, sem acrescentar pedidos. Versões antigas ficam disponíveis localmente. Use os arquivos da versão indicada por `current.json` para consumir uma saída completa.

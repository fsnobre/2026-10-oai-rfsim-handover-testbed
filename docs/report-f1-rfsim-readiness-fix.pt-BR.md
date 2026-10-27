# Relatório da correção de inicialização e prontidão da F1 em RFsim

> Tradução para o português. O original em inglês é o [report-f1-rfsim-readiness-fix.md](report-f1-rfsim-readiness-fix.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Relatório
>
> **Contexto:** [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md), [F03 — Regras de operação do RFsim com múltiplas células](foundation-f03-rfsim-multicell-operations.pt-BR.md) e [F04 — Enumerações de configuração e temporização de rádio na OAI](foundation-f04-oai-config-enums-and-timing.pt-BR.md)

**Data:** 19 de junho de 2026
**Escopo:** topologia de handover F1 intra-gNB
**Status:** implementado e validado de ponta a ponta

## Resumo executivo

O testbed F1 informava `SUMMARY: PASS` sempre que os contêineres estavam
rodando e a porta Telnet da CU estava alcançável. Isso não provava que o UE havia
se sincronizado com uma célula, estabelecido uma conexão RRC, se registrado no
5GC ou criado uma sessão PDU.

A falha observada tinha quatro causas relacionadas:

1. As duas DUs estavam configuradas para se conectar ao RFsim em `127.0.0.1:4043`. Dentro de um
   contêiner de DU, esse endereço se refere à própria DU, e não ao servidor RFsim do UE.
2. A DU1 vinculava sua interface F1 a `127.0.0.1`, impedindo uma associação F1
   válida entre o contêiner e a CU.
3. O UE ficava inicialmente exposto aos dois transmissores RFsim antes de concluir
   a conexão à DU0, o que tornava a sincronização inicial pouco confiável.
4. A janela de resposta do acesso aleatório configurada era curta demais para o atraso
   de escalonamento observado no RFsim. A DU detectava o PRACH, mas rejeitava o agendamento da Msg2
   porque ele ficava um slot fora da janela permitida.

A correção ajusta o endereçamento do RFsim e da F1, aumenta a janela de resposta
do acesso aleatório, escalona a inicialização das DUs para que o UE se conecte pela DU0 antes de a DU1 iniciar
e torna a prontidão do plano de dados do UE uma condição obrigatória de inicialização e de status.

A validação final demonstrou que:

- as duas DUs se conectaram ao servidor RFsim do UE;
- as duas DUs concluíram o F1 Setup com a CU;
- o UE estabeleceu uma conexão RRC e uma sessão PDU;
- a `oaitun_ue1` recebeu `10.0.0.2`;
- o UE alcançou `192.168.71.135` pela `oaitun_ue1`;
- o handover F1 da PCI 0 para a PCI 1 foi concluído com sucesso; e
- a conectividade do plano de dados do UE continuou disponível após o handover.

## Sintomas iniciais

Depois que o `scripts/up.sh` terminou, a verificação pós-inicialização informou:

```text
[WARN] oaitun_ue1 not yet present — UE has not established a PDU session
[WARN] UE cannot reach 192.168.71.135 via oaitun_ue1
```

Ao mesmo tempo, o `scripts/status.sh` informava todos os contêineres como rodando, o endpoint
Telnet da CU como alcançável e:

```text
SUMMARY: PASS
```

A tentativa de handover F1 produziu:

```text
no single UE in RRC present
```

Esses resultados só eram internamente inconsistentes porque a definição de status existente
media a disponibilidade dos processos, e não a prontidão funcional.

## Achados do diagnóstico

### 1. O UE nunca chegou à CU nem ao AMF

O AMF mostrava a CU/gNB como conectada, mas sua tabela de UEs estava vazia. A CU também
informava que não conseguia encontrar um UE em RRC.

O log do UE mostrava repetidamente:

```text
synch Failed
```

Isso estabeleceu que a falha inicial estava abaixo do NAS e do 5GC. As credenciais
do assinante, a configuração da DNN e a configuração da sessão PDU ainda nem estavam
no caminho de execução.

### 2. As duas DUs se conectavam ao próprio endereço de loopback

Os logs das DUs mostravam repetidamente:

```text
Trying to connect to 127.0.0.1:4043
connect() to 127.0.0.1:4043 failed, errno(111)
```

O UE é o servidor RFsim e escuta na porta `4043` em
`192.168.70.181`. Portanto, as DUs precisam usar esse endereço de contêiner. Os endereços de
loopback dos contêineres Docker são locais ao namespace e não podem se referir a outro
contêiner.

A substituição explícita pelo loopback também tinha precedência sobre o valor correto
`serveraddr = "192.168.70.181"` do `conf-du.conf`.

### 3. A DU1 usava o loopback para a F1

A DU1 era iniciada com:

```text
--MACRLCs.[0].local_n_address 127.0.0.1
```

Seus logs mostravam falhas repetidas de SCTP:

```text
Connect failed: Network is unreachable
```

O endereço F1 correto da DU1 é o seu endereço na rede Docker,
`192.168.70.172`.

### 4. Iniciar as duas DUs antes da conexão perturbava a sincronização inicial

Depois de corrigida a conectividade do RFsim, as duas DUs se conectaram com sucesso ao servidor
RFsim do UE. No entanto, iniciar a DU1 antes de o UE se conectar à DU0 causava falhas
repetidas na decodificação de PBCH e SIB1.

Parar a DU1 permitia ao UE:

- decodificar o PBCH;
- sincronizar-se com a PCI 0; e
- decodificar o SIB1.

Isso confirmou que o registro inicial precisava ser concluído na célula de origem
antes de habilitar a célula de destino.

### 5. O acesso aleatório excedia a janela de resposta configurada

Com apenas a DU0 ativa, a DU detectava toda transmissão de PRACH do UE, mas registrava:

```text
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
```

A resposta chegava depois de 11 slots, enquanto a janela configurada permitia 10.

O `ra_ResponseWindow` é representado na configuração da OAI como um índice de enumeração,
e não como uma contagem literal de slots. O mapeamento relevante é:

| Valor de configuração | Janela |
|---:|---:|
| `4` | 10 slots |
| `5` | 20 slots |

Um teste intermediário com o valor literal `8` foi rejeitado pelo codificador de RACH
da OAI. Definir o valor como `5` selecionou a próxima janela válida, de 20 slots, e
permitiu que o acesso aleatório fosse concluído.

## Mudanças implementadas

### Configuração do Docker e do rádio

#### `gnb-docker-compose.yaml`

As duas DUs agora se conectam explicitamente ao servidor RFsim do UE:

```yaml
--rfsimulator.[0].serveraddr 192.168.70.181
```

A DU1 agora vincula a F1 ao seu endereço real na rede Docker:

```yaml
--MACRLCs.[0].local_n_address 192.168.70.172
```

O endereçamento explícito do RFsim foi mantido, embora o `conf-du.conf` contenha o
mesmo endereço. Os testes mostraram que a opção de linha de comando `--rfsim` inicializa
o endpoint do cliente em `127.0.0.1` nesta imagem da OAI; portanto, confiar apenas no
valor do arquivo de configuração não é seguro.

#### `conf-du.conf`

A enumeração da janela de resposta do acesso aleatório foi alterada de:

```text
ra_ResponseWindow = 4;
```

para:

```text
ra_ResponseWindow = 5;
```

Isso muda a janela efetiva de 10 slots para 20 slots.

### Sequência de inicialização e prontidão

#### `scripts/up.sh`

A inicialização da F1 agora segue esta sequência:

1. Executar as verificações de preflight conforme a topologia.
2. Iniciar o CN da OAI.
3. Verificar se o Compose criou as duas redes Docker necessárias com a
   sub-rede e a propriedade esperadas.
4. Iniciar a CU.
5. Iniciar o UE e a DU0.
6. Aguardar até que o UE estabeleça sua sessão PDU e alcance a rede de dados
   externa.
7. Iniciar a DU1.
8. Verificar se a DU1 e o UE continuam estáveis.
9. Verificar novamente a conectividade do plano de dados do UE.
10. Informar o sucesso da inicialização.

A principal mudança de comportamento é que a inicialização não pode ter sucesso só porque
o `nr-uesoftmodem` está rodando.

### Auxiliares de prontidão compartilhados

#### `scripts/lib.sh`

Foram adicionados os seguintes auxiliares:

- `core_docker_network_specs`
- `docker_network_exists`
- `validate_core_docker_network`
- `ue_data_interface_ip`
- `ue_data_plane_reachable`

Eles centralizam a validação da propriedade das redes e as verificações do plano de dados do UE, para que
o preflight, a inicialização e o status usem definições consistentes.

### Semântica do status

#### `scripts/status.sh`

O `SUMMARY: PASS` agora exige:

- que todos os contêineres críticos existam e estejam rodando;
- que o endpoint Telnet da CU ou da gNB de origem esteja alcançável;
- que a `oaitun_ue1` exista e tenha um endereço IPv4; e
- que o destino da rede de dados configurado esteja alcançável pela interface do UE
  configurada.

Na execução F1 validada, o status informou:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

### Propagação de erros do handover

#### `scripts/trigger_handover.sh`

O script agora captura a resposta do Telnet da CU e retorna um código de saída diferente de zero
quando a CU informa que não existe UE elegível em RRC. Antes, ele imprimia o
erro, mas ainda terminava com sucesso do ponto de vista do shell.

Respostas detectadas:

- `no single UE`
- `could not find any UE`
- `no UE in RRC`

### Preflight e propriedade das redes Docker

O mesmo trabalho também corrigiu o tratamento da propriedade das redes Docker:

- O Compose do CN da OAI é responsável por criar as duas redes Docker.
- Uma rede ausente é informativa durante o preflight.
- Uma rede preexistente é verificada quanto ao driver bridge, à sub-rede esperada e aos
  rótulos de propriedade do Compose.
- A inicialização verifica as redes logo após iniciar o CN da OAI.
- Os arquivos Compose da RAN continuam usando as redes como redes externas.

As redes necessárias são:

| Rede | Sub-rede | Chave no Compose do CN |
|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` |

Isso impede que redes criadas manualmente com configurações de IPAM incompatíveis
causem falhas na inicialização do Compose.

## Procedimento de validação e evidências

### Verificações estáticas

As seguintes verificações passaram:

```bash
bash -n scripts/lib.sh \
  scripts/preflight_check.sh \
  scripts/up.sh \
  scripts/status.sh \
  scripts/trigger_handover.sh \
  scripts/run_smoke_test.sh

docker compose -f oai-cn5g/docker-compose.yaml config --quiet
docker compose -f gnb-docker-compose.yaml config --quiet
git diff --check
```

Todas as configurações Compose das topologias de RAN também foram validadas durante o trabalho
de propriedade das redes.

### Validação da inicialização

A inicialização corrigida produziu:

```text
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Starting DU1
...
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Startup readiness gates passed.
```

O diagnóstico pós-inicialização então informou zero problemas:

```text
[PASS] oaitun_ue1 present with IP: 10.0.0.2
[PASS] UE can reach 192.168.71.135 via oaitun_ue1
=== Post-start check: 0 issue(s) ===
```

### Validação da F1 e do RRC

A CU aceitou as duas DUs:

- DU0, célula `12345678`, PCI 0;
- DU1, célula `11111111`, PCI 1.

A CU então registrou o registro do UE e o estabelecimento da sessão PDU para o UE 1.

### Validação do handover

O comando de disparo retornou:

```text
RRC F1 handover triggered for UE 1
```

Os logs da CU confirmaram:

```text
Handover triggered for UE 1 ... towards cell 11111111 ... PCI 1
HO acknowledged: Send reconfiguration for UE 1
handover for UE 1 ... complete!
```

Após o handover, o `scripts/status.sh f1` ainda informava:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

## Abordagens rejeitadas ou intermediárias

Vários testes intermediários foram úteis para o diagnóstico, mas não foram mantidos:

- Remover o endereço explícito do RFsim e confiar no `conf-du.conf` não
  funcionou, porque o `--rfsim` redefinia o endpoint do cliente para `127.0.0.1`.
- Iniciar as duas DUs antes da conexão do UE causou falhas na decodificação de PBCH/SIB1.
- A opção `rfsimulator.hanging-workaround`, encontrada em arquivos de topologia mais novos,
  não é suportada pela imagem atual do UE F1 e causou um aborto por opção desconhecida.
- Definir `ra_ResponseWindow` com o valor literal `8` era inválido, porque o campo é
  um índice de enumeração. O valor `5` é a seleção correta para uma janela de 20 slots.

Esses testes são relevantes ao atualizar as imagens da OAI, porque o suporte a opções e o
comportamento de temporização do RFsim podem mudar entre compilações.

## Orientações operacionais

Use o comando de inicialização normal:

```bash
./scripts/up.sh f1
```

Não considere a inicialização bem-sucedida a menos que ela chegue a:

```text
[up] Startup readiness gates passed.
```

Verifique a prontidão funcional com:

```bash
./scripts/status.sh f1
```

O status precisa mostrar tanto um endereço de sessão PDU do UE quanto o plano de dados alcançável.

Dispare o handover com:

```bash
./scripts/trigger_handover.sh f1
```

O comando agora falha explicitamente se nenhum UE estiver elegível para o handover.

## Considerações restantes

- Os health checks dos contêineres ainda verificam apenas a existência do processo. A prontidão funcional
  é garantida pelo `up.sh` e pelo `status.sh`, o que é adequado, porque uma DU pode
  estar rodando intencionalmente antes do registro do UE.
- Os avisos sobre o Tailscale continuam sendo apenas orientativos. O Tailscale estava ativo durante a
  validação final e não impediu o acesso ao Telnet da CU nem o handover.
- A verificação de conflito de interfaces do host no preflight pode identificar as bridges criadas pelo Compose,
  `oai-cn5g` e `oai-internet`, como interfaces não Docker. É um
  problema de qualidade do aviso e não afeta esta correção.
- Futuras atualizações das imagens da OAI devem repetir as verificações de conexão do RFsim, acesso aleatório,
  sessão PDU e plano de dados após o handover, porque a temporização e as opções de linha de comando
  suportadas podem mudar.

## Arquivos alterados

| Arquivo | Finalidade |
|---|---|
| `conf-du.conf` | Aumentar a janela de resposta do RA |
| `gnb-docker-compose.yaml` | Corrigir os endereços RFsim das DUs e o endereço F1 da DU1 |
| `scripts/lib.sh` | Acrescentar auxiliares de prontidão de rede e do UE |
| `scripts/preflight_check.sh` | Validar o Compose e as redes de propriedade do CN |
| `scripts/up.sh` | Escalonar a inicialização da F1 e exigir a prontidão do plano de dados |
| `scripts/status.sh` | Incluir as verificações de sessão PDU e do plano de dados |
| `scripts/trigger_handover.sh` | Propagar as falhas de handover sem UE |
| `scripts/run_smoke_test.sh` | Passar a topologia ao preflight |

## Conclusão

O problema original não era uma falha de configuração do 5GC nem do assinante. Era uma
combinação de endereçamento local ao contêiner incorreto, ordem de inicialização do rádio insegura,
uma janela de resposta do acesso aleatório insuficiente e verificações de prontidão
que mediam processos, e não o comportamento do serviço.

O testbed corrigido agora usa a prontidão funcional como critério de sucesso.
O caminho F1 completo — sincronização de RF, acesso aleatório, RRC, registro, sessão
PDU, conectividade do plano de usuário, handover e conectividade após o handover — foi
validado com sucesso.

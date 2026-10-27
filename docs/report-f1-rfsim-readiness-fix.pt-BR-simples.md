# Relatório da correção da subida e da prontidão do F1 em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [report-f1-rfsim-readiness-fix.md](report-f1-rfsim-readiness-fix.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** relatório
>
> **Contexto:** [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md), [F03 — Regras para várias células no rfsim](foundation-f03-rfsim-multicell-operations.pt-BR-simples.md) e [F04 — Valores enumerados da configuração da OAI e tempos de rádio](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md)

**Data:** 19/06/2026
**Escopo:** topologia de handover F1 (intra-gNB)
**Situação:** implementado e validado de ponta a ponta

## Resumo executivo

Antes, o testbed F1 mostrava `SUMMARY: PASS` sempre que os contêineres estavam rodando e a porta Telnet da CU respondia. Isso não provava que o UE tinha:

- se sincronizado com uma célula;
- aberto uma conexão RRC;
- se registrado no núcleo 5G;
- criado uma sessão PDU.

A falha observada tinha quatro causas ligadas entre si:

1. As duas DUs estavam configuradas para se conectar ao rfsim em `127.0.0.1:4043`. Dentro de um contêiner de DU, esse endereço é a própria DU, e não o servidor rfsim no UE.
2. A DU1 ligava a interface F1 a `127.0.0.1`. Isso impedia uma associação F1 válida entre o contêiner e a CU.
3. No começo, o UE recebia os dois transmissores do rfsim antes de concluir a conexão com a DU0. Isso tornava a sincronização inicial instável.
4. A janela de resposta do acesso aleatório era curta demais para o atraso de escalonamento observado no rfsim. A DU detectava o PRACH, mas recusava agendar a Msg2, porque ela ficava um slot fora da janela permitida.

A correção:

- acerta os endereços do rfsim e do F1;
- aumenta a janela de resposta do acesso aleatório;
- sobe as DUs em etapas, para o UE se conectar pela DU0 antes de a DU1 subir;
- torna a prontidão do plano de usuário do UE uma condição obrigatória da subida e do estado.

A validação final mostrou que:

- as duas DUs se conectaram ao servidor rfsim no UE;
- as duas DUs concluíram o F1 Setup com a CU;
- o UE abriu uma conexão RRC e uma sessão PDU;
- a `oaitun_ue1` recebeu o endereço `10.0.0.2`;
- o UE alcançou `192.168.71.135` pela `oaitun_ue1`;
- o handover F1 do PCI 0 para o PCI 1 terminou com sucesso;
- o plano de usuário do UE continuou disponível depois do handover.

## Sintomas iniciais

Depois que o `scripts/up.sh` terminou, a verificação pós-subida mostrou:

```text
[WARN] oaitun_ue1 not yet present — UE has not established a PDU session
[WARN] UE cannot reach 192.168.71.135 via oaitun_ue1
```

Ao mesmo tempo, o `scripts/status.sh` mostrou todos os contêineres rodando e o Telnet da CU respondendo, e concluiu:

```text
SUMMARY: PASS
```

A tentativa de handover F1 retornou:

```text
no single UE in RRC present
```

Esses resultados só pareciam contraditórios porque a definição de estado da época media se os processos estavam rodando, e não se o sistema funcionava.

## O que o diagnóstico encontrou

### 1. O UE nunca chegou à CU nem ao AMF

O AMF mostrava a CU/gNB conectada, mas a tabela de UEs estava vazia. A CU também informava que não encontrava nenhum UE em RRC.

O log do UE mostrava, repetidas vezes:

```text
synch Failed
```

Isso mostrou que a falha inicial estava abaixo do NAS e do núcleo 5G. As credenciais do assinante, o DNN e a configuração da sessão PDU ainda nem tinham sido usados.

### 2. As duas DUs se conectavam ao próprio endereço de loopback

Os logs das DUs mostravam, repetidas vezes:

```text
Trying to connect to 127.0.0.1:4043
connect() to 127.0.0.1:4043 failed, errno(111)
```

O UE é o servidor do rfsim e escuta na porta `4043`, em `192.168.70.181`. Por isso, as DUs precisam usar esse endereço de contêiner. O endereço de loopback de um contêiner Docker só vale dentro dele. Ele não aponta para outro contêiner.

Além disso, o endereço de loopback informado na linha de comando prevalecia sobre o valor correto, `serveraddr = "192.168.70.181"`, do `conf-du.conf`.

### 3. A DU1 usava o loopback no F1

A DU1 subia com:

```text
--MACRLCs.[0].local_n_address 127.0.0.1
```

Os logs dela mostravam falhas repetidas de SCTP:

```text
Connect failed: Network is unreachable
```

O endereço F1 correto da DU1 é o endereço dela na rede Docker, `192.168.70.172`.

### 4. Subir as duas DUs antes da conexão atrapalhou a sincronização inicial

Depois de corrigir a conexão com o rfsim, as duas DUs se conectaram ao servidor rfsim no UE. Mas, com a DU1 subindo antes de o UE se conectar à DU0, a decodificação do PBCH e do SIB1 falhava repetidas vezes.

Com a DU1 parada, o UE conseguiu:

- decodificar o PBCH;
- se sincronizar com o PCI 0;
- decodificar o SIB1.

Isso confirmou que o registro inicial precisava terminar na célula de origem antes de ligar a célula de destino.

### 5. O acesso aleatório passou da janela de resposta configurada

Só com a DU0 ativa, a DU detectava todas as transmissões de PRACH do UE, mas registrava:

```text
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
```

A resposta chegava depois de 11 slots. A janela configurada permitia 10.

Na configuração da OAI, o `ra_ResponseWindow` é um índice de uma lista de valores, e não o número de slots. A correspondência relevante é:

| Valor na configuração | Janela |
|---:|---:|
| `4` | 10 slots |
| `5` | 20 slots |

Um teste intermediário com o valor literal `8` foi recusado pelo codificador de RACH da OAI. O valor `5` escolheu a janela válida seguinte, de 20 slots, e permitiu concluir o acesso aleatório.

## Mudanças feitas

### Configuração do Docker e do rádio

#### `gnb-docker-compose.yaml`

As duas DUs agora se conectam de forma explícita ao servidor rfsim no UE:

```yaml
--rfsimulator.[0].serveraddr 192.168.70.181
```

A DU1 agora liga o F1 ao endereço real dela na rede Docker:

```yaml
--MACRLCs.[0].local_n_address 192.168.70.172
```

O endereço do rfsim continua explícito, mesmo com o mesmo endereço no `conf-du.conf`. Os testes mostraram que, nesta imagem da OAI, a opção `--rfsim` define o endereço do cliente como `127.0.0.1`. Por isso, não é seguro confiar só no valor do arquivo de configuração.

#### `conf-du.conf`

O índice da janela de resposta do acesso aleatório mudou de:

```text
ra_ResponseWindow = 4;
```

para:

```text
ra_ResponseWindow = 5;
```

Isso muda a janela efetiva de 10 para 20 slots.

### Ordem de subida e prontidão

#### `scripts/up.sh`

A subida do F1 agora segue esta ordem:

1. Executa as verificações prévias da topologia.
2. Sobe o núcleo 5G da OAI.
3. Confere se o Compose criou as duas redes Docker necessárias, com a sub-rede e o dono esperados.
4. Sobe a CU.
5. Sobe o UE e a DU0.
6. Espera o UE criar a sessão PDU e alcançar a rede de dados externa.
7. Sobe a DU1.
8. Confere se a DU1 e o UE continuam estáveis.
9. Confere de novo o plano de usuário do UE.
10. Informa que a subida deu certo.

A principal mudança de comportamento: a subida não pode dar certo só porque o `nr-uesoftmodem` está rodando.

### Funções de prontidão compartilhadas

#### `scripts/lib.sh`

Foram acrescentadas estas funções:

- `core_docker_network_specs`
- `docker_network_exists`
- `validate_core_docker_network`
- `ue_data_interface_ip`
- `ue_data_plane_reachable`

Elas concentram a validação do dono das redes e as conferências do plano de usuário do UE. Assim, a verificação prévia, a subida e o estado usam as mesmas definições.

### Significado do estado

#### `scripts/status.sh`

Agora, o `SUMMARY: PASS` exige que:

- todos os contêineres críticos existam e estejam rodando;
- o Telnet da CU ou da gNB de origem responda;
- a `oaitun_ue1` exista e tenha endereço IPv4;
- o destino configurado na rede de dados responda pela interface configurada do UE.

Na execução F1 validada, o estado mostrou:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

### Repasse dos erros do handover

#### `scripts/trigger_handover.sh`

O script agora guarda a resposta do Telnet da CU. Se a CU informar que não há UE elegível em RRC, ele retorna um código de saída diferente de zero. Antes, ele mostrava o erro, mas, para o shell, terminava com sucesso.

Respostas detectadas:

- `no single UE`
- `could not find any UE`
- `no UE in RRC`

### Verificação prévia e dono das redes Docker

O mesmo trabalho também corrigiu o tratamento do dono das redes Docker:

- O Compose do núcleo 5G da OAI cria as duas redes Docker.
- Na verificação prévia, a falta de uma rede só é informada.
- Uma rede que já existe é conferida quanto ao driver bridge, à sub-rede esperada e às etiquetas de dono do Compose.
- A subida confere as redes logo depois de subir o núcleo 5G.
- Os arquivos Compose da RAN continuam usando as redes como redes externas.

As redes necessárias são:

| Rede | Sub-rede | Chave no Compose do núcleo 5G |
|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` |

Isso impede que redes criadas à mão, com configuração de endereços incompatível, façam a subida do Compose falhar.

## Procedimento de validação e evidências

### Conferências estáticas

Estas conferências passaram:

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

As configurações Compose de todas as topologias da RAN também foram validadas durante o trabalho sobre o dono das redes.

### Validação da subida

A subida corrigida mostrou:

```text
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Starting DU1
...
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Startup readiness gates passed.
```

Em seguida, o diagnóstico pós-subida não encontrou nenhum problema:

```text
[PASS] oaitun_ue1 present with IP: 10.0.0.2
[PASS] UE can reach 192.168.71.135 via oaitun_ue1
=== Post-start check: 0 issue(s) ===
```

### Validação do F1 e do RRC

A CU aceitou as duas DUs:

- DU0, célula `12345678`, PCI 0;
- DU1, célula `11111111`, PCI 1.

Depois, a CU registrou o registro e a criação da sessão PDU do UE 1.

### Validação do handover

O comando de handover retornou:

```text
RRC F1 handover triggered for UE 1
```

Os logs da CU confirmaram:

```text
Handover triggered for UE 1 ... towards cell 11111111 ... PCI 1
HO acknowledged: Send reconfiguration for UE 1
handover for UE 1 ... complete!
```

Depois do handover, o `scripts/status.sh f1` ainda mostrava:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

## Abordagens descartadas ou intermediárias

Vários testes intermediários ajudaram no diagnóstico, mas não ficaram na solução:

- Tirar o endereço explícito do rfsim e confiar no `conf-du.conf` não funcionou. O `--rfsim` voltava o endereço do cliente para `127.0.0.1`.
- Subir as duas DUs antes da conexão do UE causou falhas na decodificação do PBCH e do SIB1.
- A opção `rfsimulator.hanging-workaround`, presente em arquivos de topologias mais novas, não existe na imagem atual do UE do F1. Ela fez o processo parar por opção desconhecida.
- O valor literal `8` no `ra_ResponseWindow` era inválido, porque o campo é um índice. O valor `5` é a escolha correta para uma janela de 20 slots.

Esses testes importam ao atualizar as imagens da OAI. As opções aceitas e os tempos do rfsim podem mudar de uma versão para outra.

## Orientação de operação

Use o comando normal de subida:

```bash
./scripts/up.sh f1
```

Só considere a subida bem-sucedida se ela chegar a:

```text
[up] Startup readiness gates passed.
```

Confira a prontidão funcional com:

```bash
./scripts/status.sh f1
```

O estado deve mostrar o endereço da sessão PDU do UE e o plano de usuário respondendo.

Comande o handover com:

```bash
./scripts/trigger_handover.sh f1
```

Agora, o comando falha de forma explícita se nenhum UE puder fazer o handover.

## Pontos que continuam em aberto

- Os health checks dos contêineres ainda só conferem se o processo existe. A prontidão funcional fica a cargo do `up.sh` e do `status.sh`. Isso é adequado, porque uma DU pode estar rodando de propósito antes do registro do UE.
- Os avisos do Tailscale continuam sendo só avisos. O Tailscale estava ativo na validação final e não impediu o acesso ao Telnet da CU nem o handover.
- A verificação prévia de conflitos de interface pode apontar as bridges criadas pelo Compose, `oai-cn5g` e `oai-internet`, como interfaces que não são do Docker. É um problema de qualidade dos avisos e não afeta esta correção.
- Nas próximas atualizações das imagens da OAI, repita as conferências de conexão com o rfsim, de acesso aleatório, de sessão PDU e do plano de usuário depois do handover. Os tempos e as opções de linha de comando aceitas podem mudar.

## Arquivos alterados

| Arquivo | Finalidade |
|---|---|
| `conf-du.conf` | Aumentar a janela de resposta do acesso aleatório |
| `gnb-docker-compose.yaml` | Corrigir os endereços do rfsim nas DUs e o endereço F1 da DU1 |
| `scripts/lib.sh` | Acrescentar funções de prontidão das redes e do UE |
| `scripts/preflight_check.sh` | Validar o Compose e as redes criadas pelo núcleo 5G |
| `scripts/up.sh` | Subir o F1 em etapas e exigir a prontidão do plano de usuário |
| `scripts/status.sh` | Incluir a conferência da sessão PDU e do plano de usuário |
| `scripts/trigger_handover.sh` | Repassar as falhas de handover sem UE |
| `scripts/run_smoke_test.sh` | Passar a topologia para a verificação prévia |

## Conclusão

O problema original não era uma falha de configuração do núcleo 5G nem do assinante. Ele vinha de uma soma de fatores:

- endereços errados, válidos só dentro do contêiner;
- ordem insegura de subida dos rádios;
- janela de resposta do acesso aleatório curta demais;
- verificações de prontidão que mediam processos, e não o funcionamento do serviço.

O testbed corrigido agora usa a prontidão funcional como critério de sucesso. Todo o caminho do F1 foi validado com sucesso: sincronização de rádio, acesso aleatório, RRC, registro, sessão PDU, plano de usuário, handover e conectividade depois do handover.

## Notas das sessões de desenvolvimento: resultado de referência do handover F1 em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [record-development-history.md](../en/record-development-history.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** registro histórico
>
> **Leitura prévia:** nenhuma

### 1. O problema inicial

O ponto de partida era uma montagem de handover F1 da OpenAirInterface (OAI) no simulador de rádio (rfsim), executada à mão. O objetivo foi transformá-la em um **testbed de pesquisa que pode ser reproduzido**.

Você já tinha validado à mão o tutorial de handover da OAI, com:

```text
1 UE
2 DUs
1 CU
1 núcleo 5G da OAI
1 UPF fixo
handover F1 manual pelo Telnet da CU
```

O comando manual de handover era:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

O objetivo da pesquisa ainda não era a troca dinâmica do UPF nem a integração com DRL ou xApps. Limitamos de propósito o primeiro marco a:

```text
UPF em posição fixa
handover F1 manual ou por script
subida que pode ser repetida
verificações automáticas de prontidão
coleta de métricas
organização dos logs e dos resultados
```

Essa simplificação foi boa. Ela criou um resultado de referência estável antes de acrescentar DRL, GNN, controle por xApp ou vários UPFs.

---

### 2. Criação do repositório e da automação

Criamos um repositório novo:

```text
oai-rfsim-handover-testbed
```

A primeira grande tarefa foi transformar os arquivos do tutorial da OAI em um projeto mais limpo. Ele passou a ter scripts de automação, pastas de experimentos, logs, métricas e resultados.

Os nomes dos serviços e contêineres ficaram mais curtos, sem o prefixo `oai-`:

```text
amf
smf
upf
cu
du0
du1
nr-ue
ext-dn
```

A primeira camada de automação tinha scripts como:

```text
scripts/up.sh
scripts/down.sh
scripts/restart.sh
scripts/status.sh
scripts/wait_ready.sh
scripts/trigger_handover.sh
scripts/collect_logs.sh
scripts/run_smoke_test.sh
```

O primeiro fluxo reproduzia o seu processo manual:

```text
subir o núcleo 5G
subir a CU
subir a DU0
subir a DU1
conferir se o nr-ue está rodando
comandar o handover
coletar os logs e os dados da execução
```

Uma nota de operação importante: **o Tailscale podia atrapalhar o comando `nc`** usado no handover. Os scripts passaram a avisar quando o Tailscale parecia ativo.

---

### 3. Melhorias na prontidão e na ordem de subida

No começo, os contêineres subiam um depois do outro. Você notou, com razão, que a documentação da OAI recomenda esperar alguns serviços ficarem saudáveis antes de subir os componentes que dependem deles.

Então, melhoramos a subida com etapas de espera limitadas:

```text
subir o núcleo 5G
esperar AMF, SMF e UPF saudáveis ou rodando
subir a CU
esperar a CU rodando e a porta Telnet respondendo
subir a DU0
esperar a DU0 rodando
subir a DU1
esperar a DU1 e o nr-ue rodando
```

Isso deixou o testbed mais robusto. Também reduziu o risco de falhas falsas por subir componentes cedo demais.

---

### 4. Primeiro handover automático bem-sucedido

Com os scripts de automação prontos, você executou o teste rápido com sucesso.

Os scripts conferiram:

```text
amf: running
smf: running
upf: running
cu: running
du0: running
du1: running
nr-ue: running
Telnet da CU em 192.168.70.150:9090 respondendo
```

O comando de handover funcionou pelo script:

```text
RRC F1 handover triggered for UE 1
```

Isso validou o primeiro marco importante:

```text
tutorial manual de handover da OAI → fluxo de handover automático e reproduzível
```

---

### 5. Pipeline de métricas de ping e o primeiro problema

O passo seguinte foi coletar métricas do plano de usuário durante o handover. Acrescentamos a captura de ping em torno do evento de handover.

A primeira versão tentava enviar ping, de dentro do `nr-ue`, para:

```text
192.168.71.135
```

Mas o ping não gerou amostras válidas. O resumo mostrou:

```text
packets_transmitted: 0
packets_received: 0
```

Investigamos dentro do `nr-ue`. O UE estava registrado e tinha uma sessão PDU:

```text
oaitun_ue1: 10.0.0.2/24
```

Mas a rota padrão ainda passava pela `eth0` do Docker, e não pelo túnel do UE.

Por isso, acrescentamos a opção de prender o ping à interface do túnel do UE:

```bash
ping -I oaitun_ue1 ...
```

Nesse ponto, o ping para `8.8.8.8` funcionou. Isso confirmou que o plano de usuário do UE estava funcionando.

---

### 6. Espera pelo plano de usuário do UE

Acrescentamos uma verificação própria do plano de usuário do UE antes de medir o handover.

O novo script testa, repetidas vezes, se o UE alcança o destino do ping pela interface da sessão PDU:

```bash
docker exec nr-ue ping -I oaitun_ue1 -c 1 -W 1 <destino>
```

Assim, o teste rápido não comanda o handover com o plano de usuário do UE ainda fora do ar.

Essa foi uma melhoria importante de método, porque:

```text
contêiner rodando      ≠ UE registrado
UE registrado          ≠ sessão PDU utilizável
sessão PDU utilizável  ≠ destino da métrica alcançável
```

---

### 7. Erro no analisador e correção

Com a captura de ping funcionando, encontramos um problema no analisador.

O `ping.csv` tinha muitas amostras ICMP. Mas o resumo mostrava, de forma errada, só:

```text
packets_transmitted: 2
packets_received: 2
```

A causa: o analisador lia as estatísticas do teste inicial de ping, e não as da captura longa.

Corrigimos o analisador para que:

```text
packets_received = número de linhas de resposta ICMP lidas
packets_transmitted = estatística final da captura ou o maior icmp_seq
as estatísticas do teste inicial são ignoradas
```

Depois da correção, o analisador passou a mostrar valores certos, como:

```text
packets_transmitted: 64
packets_received: 63
parsed_reply_count: 63
```

---

### 8. Primeiro resultado de referência repetido, com 8.8.8.8

Antes de corrigir o acesso à rede de dados local, o teste repetido usava:

```text
destino: 8.8.8.8
interface: oaitun_ue1
```

Uma execução com `RUNS=5` deu:

```text
5/5 execuções aprovadas
interrupção média: cerca de 221,81 ms
perda média de pacotes: cerca de 1,245%
```

Isso provou que o pipeline de métricas funcionava. Mas `8.8.8.8` não era ideal, porque o RTT pela internet trazia ruído.

Então, decidimos corrigir o acesso ao `ext-dn` local.

---

### 9. Diagnóstico do acesso ao ext-dn

O destino local na rede de dados era:

```text
ext-dn: 192.168.71.135
```

No começo, o UE não conseguia fazer ping no `ext-dn`, embora alcançasse a internet pelo UPF.

Criamos:

```text
scripts/diagnose_dn_reachability.sh
```

Esse script de diagnóstico coletava:

```text
docker ps
redes Docker
endereços IP dos contêineres
rotas
testes de ping
estado do iptables e do nft
estado do encaminhamento no sysctl
```

O primeiro diagnóstico mostrou:

```text
UE → internet: passa
UE → ext-dn: falha
UE → túnel do UPF: passa
ext-dn → UE: inconsistente no começo
UPF → ext-dn: ambíguo ou falha
```

Também descobrimos que o contêiner `upf` não tinha o programa `ping`. Por isso, as falhas de ping no UPF não podiam ser tratadas como falhas reais de rede.

Mais tarde, o script de diagnóstico passou a mostrar:

```text
tool_missing
```

em vez de relatar, de forma errada, uma falha de rede quando o `ping` faltava.

---

### 10. Causa raiz: UPF fora da rede de tráfego

Examinamos a topologia do Compose. O `ext-dn` estava ligado às duas redes:

```text
public_net: 192.168.70.135
traffic_net: 192.168.71.135
```

Mas o `upf` só estava ligado a:

```text
public_net: 192.168.70.134
```

Então, o UPF não tinha interface na rede de tráfego `192.168.71.0/26`.

Você também se lembrou de um problema antigo da OAI com rfsim: a ordem das interfaces no Docker podia variar, a menos que o `interface_name` fosse configurado de forma explícita.

Atualizamos o `oai-cn5g/docker-compose.yaml` para:

```text
upf:
  public_net  → eth0 → 192.168.70.134
  traffic_net → eth1 → 192.168.71.134

ext-dn:
  public_net  → eth0 → 192.168.70.135
  traffic_net → eth1 → 192.168.71.135
```

Depois de reiniciar a pilha com `down --volumes` e `up`, o acesso à rede de dados local funcionou:

```text
UE → ext-dn: passa
ext-dn → UE: passa
UE → túnel do UPF: passa
```

Esse foi um resultado-chave da depuração.

---

### 11. O ext-dn local virou o destino padrão do teste rápido

Com o acesso à rede de dados local corrigido, o destino padrão do ping mudou de:

```text
8.8.8.8
```

para:

```text
192.168.71.135
```

com:

```text
interface: oaitun_ue1
```

Isso deixou o experimento mais adequado do ponto de vista científico, porque tirou a variação do caminho pela internet.

A alternativa continuou disponível:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh
```

---

### 12. Resultado de referência final, repetido, com a rede de dados local

Depois da troca para o `ext-dn` local, você executou:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh
```

O resultado foi:

```text
5/5 execuções aprovadas
perda de pacotes: 0,0%
interrupção estimada média: 207,0664 ms
desvio-padrão da interrupção estimada: 22,3375 ms
interrupção mínima: 170,576 ms
interrupção máxima: 238,949 ms
média do primeiro ping depois do handover: 93,309 ms
```

Esse virou o primeiro resultado de referência limpo do testbed de handover F1 em rfsim.

Ele está documentado em:

```text
docs/en/report-baseline-results.md
```

A interpretação do resultado de referência foi:

```text
A automação consegue, de forma repetida, subir e validar o testbed de handover F1 da OAI em rfsim, comandar o handover F1 pela interface Telnet da CU e manter a conectividade do plano de usuário do UE até o ext-dn local, sem perda de pacotes nas cinco execuções.
```

Uma limitação conhecida continua:

```text
O RTT ainda inclui efeitos do rfsim, do Docker, do escalonamento do computador e picos de processamento.
```

Assim, a métrica de interrupção do handover é útil. Mas o RTT ainda não deve ser lido como uma latência limpa do protocolo.

---

### 13. Suporte opcional ao iperf e solução

Em seguida, começamos a acrescentar o suporte opcional ao `iperf3`, para medir o plano de usuário com um tráfego mais rico.

O Codex acrescentou:

```text
scripts/check_iperf_support.sh
scripts/run_iperf_test.sh
tools/parse_iperf.py
```

O `nr-ue` e o `ext-dn` tinham o `iperf3`.

Mas os testes iperf em TCP e em UDP falharam. O comando gerado para o cliente era:

```bash
docker exec nr-ue iperf3 -J -c 192.168.71.135 -t 10 -u
```

O problema provável era que o `iperf3` não passava, de forma obrigatória, pela sessão PDU do UE. O `iperf3` instalado não aceitava `--bind-dev`. Por isso, a correção seguinte deveria usar o IP de origem:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135
```

Em UDP:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135 -u -b 1M
```

Esse caminho foi concluído em 19/06/2026:

- O script agora usa como origem do cliente o endereço do UE encontrado na `oaitun_ue1`.
- O destino do iperf no ext-dn que funciona é `192.168.70.135`. O UPF entrega o fluxo TCP ou UDP no endereço público do ext-dn. Com `192.168.71.135`, a conexão de controle do iperf ficava assimétrica.

O teste rápido agora pode rodar o iperf ao mesmo tempo que o ping, durante o handover, com `IPERF_ENABLED=1`. O resumo de cada execução inclui vazão, jitter, perda e retransmissões. As execuções repetidas juntam essas métricas. O iperf continua opcional, a menos que `IPERF_REQUIRED=1` esteja definido.

---

### 14. Problemas que tive ao procurar ou conferir informações antigas

Houve algumas limitações práticas durante o trabalho:

```text
1. Algumas buscas no GitHub não retornaram nada logo depois que você enviou os arquivos.
   Pareceu atraso na indexação ou arquivo ainda não enviado.

2. Eu conseguia examinar os arquivos que estavam no repositório do GitHub, mas não as mudanças locais antes do envio.

3. Usei principalmente o histórico desta conversa, as saídas de comando que você colou e o repositório do GitHub.
   Não reconstruí em detalhe as conversas antigas e separadas.

4. Mais tarde, alguns arquivos de execução passaram a ser ignorados de propósito pelo .gitignore.
   Por isso, os resumos futuros devem usar saídas coladas escolhidas, documentos com commit ou resultados selecionados, e não todas as pastas brutas das execuções.

5. O primeiro diagnóstico do UPF foi ambíguo, porque o contêiner do UPF não tinha o `ping`.
   Corrigimos isso separando `tool_missing` de uma falha real de acesso.
```

Não resta incerteza importante sobre o fluxo principal. A medição opcional com iperf agora está integrada e validada em UDP e em TCP. O trabalho futuro é caracterizar os experimentos, e não mais fazer o transporte básico funcionar.

---


## Conclusão resumida, em formato de relatório

Neste trabalho, transformamos um tutorial de handover F1 da OAI em rfsim, executado à mão, em um testbed de pesquisa que pode ser reproduzido. O testbed final automatiza:

- a subida dos contêineres;
- a validação da prontidão;
- o comando manual do handover F1 pela interface Telnet da CU;
- a coleta de logs e de métricas;
- os experimentos repetidos;
- a documentação do resultado de referência.

Identificamos e corrigimos vários problemas práticos:

- a ordem de subida;
- a prontidão do plano de usuário do UE;
- a escolha errada do destino e da interface do ping;
- a leitura errada das estatísticas de ping pelo analisador;
- a falha de acesso à rede de dados local;
- o UPF fora da rede de tráfego;
- a ordem variável das interfaces no Docker.

O testbed corrigido agora usa um destino `ext-dn` local pela interface da sessão PDU do UE. Ele produziu um resultado de referência repetido com 5/5 handovers bem-sucedidos, 0% de perda de pacotes e cerca de 207 ms de interrupção estimada média. A medição opcional com iperf agora usa o IP da sessão PDU do UE como origem, roda ao mesmo tempo que o handover e é agregada nos experimentos repetidos.

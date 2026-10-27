## Notas das sessões de desenvolvimento — referência do handover F1 em RFsim

> Tradução para o português. O original em inglês é o [record-development-history.md](record-development-history.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Registro histórico
>
> **Leitura obrigatória:** nenhuma

### 1. Problema inicial em que começamos a trabalhar

O ponto de partida foi a necessidade de transformar uma **montagem de handover F1 no RFsimulator da OpenAirInterface executada manualmente** num **testbed de pesquisa reproduzível**.

Você já havia validado manualmente o tutorial de handover da OAI com:

```text
1 UE
2 DUs
1 CU
1 5GC da OAI
1 UPF estática
handover F1 manual pelo Telnet da CU
```

O comando manual de handover era:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

O objetivo de pesquisa ainda não era a realocação dinâmica da UPF nem a integração com DRL/xApp. Limitamos intencionalmente o primeiro marco a:

```text
posicionamento estático da UPF
handover F1 manual/por script
inicialização repetível
verificações automatizadas de prontidão
coleta de métricas
organização de logs/resultados
```

Essa foi uma boa simplificação, porque criou uma referência estável antes de acrescentar DRL/GNN, controle por xApp ou lógica com várias UPFs.

---

### 2. Criação do repositório e da automação

Criamos um novo repositório:

```text
oai-rfsim-handover-testbed
```

A primeira grande tarefa foi transformar os arquivos do tutorial da OAI numa estrutura de projeto mais limpa, com scripts de automação, pastas de experimentos, logs, métricas e resultados.

Os nomes dos serviços/contêineres foram simplificados dos nomes longos `oai-*` para:

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

A primeira camada de automação incluía scripts como:

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

O fluxo inicial reproduzia o seu processo manual:

```text
iniciar o núcleo
iniciar a CU
iniciar a DU0
iniciar a DU1
verificar se o nr-ue está rodando
disparar o handover
coletar logs e metadados da execução
```

Uma observação operacional importante foi que **o Tailscale podia interferir no comando `nc`** usado para disparar o handover. Os scripts foram atualizados para avisar quando o Tailscale parecesse ativo.

---

### 3. Melhorias na prontidão e na ordem de inicialização

No começo, os contêineres eram iniciados um após o outro. Você apontou corretamente que a documentação da OAI recomenda esperar que alguns serviços fiquem saudáveis antes de iniciar os componentes dependentes.

Melhoramos então a lógica de inicialização com verificações de prontidão com tempo limite:

```text
iniciar o 5GC
aguardar AMF/SMF/UPF saudáveis ou rodando
iniciar a CU
aguardar a CU rodando e a porta Telnet alcançável
iniciar a DU0
aguardar a DU0 rodando
iniciar a DU1
aguardar a DU1 e o nr-ue rodando
```

Isso tornou o testbed mais robusto e reduziu o risco de falsas falhas causadas por iniciar componentes cedo demais.

---

### 4. Primeiro handover automatizado bem-sucedido

Depois que os scripts de automação foram criados, você executou o teste rápido com sucesso.

Os scripts verificaram:

```text
amf: running
smf: running
upf: running
cu: running
du0: running
du1: running
nr-ue: running
CU Telnet 192.168.70.150:9090 reachable
```

O disparo do handover funcionou pelo script:

```text
RRC F1 handover triggered for UE 1
```

Isso validou o primeiro marco importante:

```text
tutorial manual de handover da OAI → fluxo de handover automatizado e reproduzível
```

---

### 5. Pipeline de métricas de ping e primeiro problema

O passo seguinte foi coletar métricas do plano de dados durante o handover. Acrescentamos a captura de ping em torno do evento de handover.

A primeira implementação tentava pingar:

```text
192.168.71.135
```

de dentro do `nr-ue`, mas o ping não produzia amostras válidas. O resumo mostrava:

```text
packets_transmitted: 0
packets_received: 0
```

Investigamos dentro do `nr-ue` e descobrimos que o UE estava registrado e tinha uma sessão PDU:

```text
oaitun_ue1: 10.0.0.2/24
```

mas a rota padrão ainda passava pela `eth0` do Docker, e não pelo túnel do UE.

Então acrescentamos suporte para vincular o ping à interface do túnel do UE:

```bash
ping -I oaitun_ue1 ...
```

Nesse ponto, o ping para `8.8.8.8` funcionou, confirmando que o plano de dados do UE estava funcional.

---

### 6. Verificação de prontidão do plano de dados do UE

Acrescentamos uma verificação específica de prontidão do plano de dados do UE antes de coletar as métricas do handover.

O novo script testava repetidamente se o UE conseguia alcançar o destino de ping configurado pela interface da sessão PDU:

```bash
docker exec nr-ue ping -I oaitun_ue1 -c 1 -W 1 <target>
```

Isso impediu que o teste rápido disparasse o handover quando o plano de dados do UE não estava pronto.

Foi uma melhoria metodológica importante, porque:

```text
contêiner rodando      ≠ UE registrado
UE registrado          ≠ sessão PDU utilizável
sessão PDU utilizável  ≠ destino da métrica alcançável
```

---

### 7. Bug no parser e correção

Depois que a captura de ping funcionou, encontramos um problema no parser.

O arquivo `ping.csv` tinha muitas amostras ICMP, mas o resumo informava incorretamente apenas:

```text
packets_transmitted: 2
packets_received: 2
```

A causa era que o parser estava lendo as estatísticas da pré-verificação do ping, em vez das da captura longa.

Corrigimos o parser para que:

```text
packets_received = número de linhas de resposta ICMP processadas
packets_transmitted = estatísticas finais da captura ou maior icmp_seq
as estatísticas da pré-verificação são ignoradas
```

Depois da correção, o parser passou a informar corretamente valores como:

```text
packets_transmitted: 64
packets_received: 63
parsed_reply_count: 63
```

---

### 8. Primeira referência repetida usando 8.8.8.8

Antes de corrigir o alcance da DN local, o teste repetido usava:

```text
target: 8.8.8.8
interface: oaitun_ue1
```

Uma execução repetida com `RUNS=5` produziu:

```text
5/5 execuções aprovadas
interrupção média: ~221,81 ms
perda de pacotes média: ~1,245%
```

Isso provou que o pipeline de métricas funcionava, mas `8.8.8.8` não era ideal, porque o RTT da internet introduzia ruído.

Decidimos então corrigir o alcance do `ext-dn` local.

---

### 9. Diagnóstico do alcance do ext-dn

O destino da DN local era:

```text
ext-dn: 192.168.71.135
```

No início, o UE não conseguia pingar o `ext-dn`, embora conseguisse alcançar a internet pela UPF.

Criamos:

```text
scripts/diagnose_dn_reachability.sh
```

Esse script de diagnóstico coletava:

```text
docker ps
docker networks
container IP addresses
routes
ping probes
iptables/nft state
sysctl forwarding state
```

O primeiro diagnóstico mostrou:

```text
UE → internet: passou
UE → ext-dn: falhou
UE → tun da UPF: passou
ext-dn → UE: inicialmente inconsistente
UPF → ext-dn: ambíguo/falhou
```

Também descobrimos que o contêiner `upf` não tinha o binário `ping`, de modo que as falhas de ping na UPF não podiam ser classificadas como falhas reais de rede.

Mais tarde, o script de diagnóstico foi melhorado para informar:

```text
tool_missing
```

em vez de informar incorretamente uma falha de rede quando o `ping` estava ausente.

---

### 10. Causa raiz: UPF não conectada à rede de tráfego

Inspecionamos a topologia do Compose e descobrimos que o `ext-dn` estava conectado às duas redes:

```text
public_net: 192.168.70.135
traffic_net: 192.168.71.135
```

mas a `upf` estava conectada apenas a:

```text
public_net: 192.168.70.134
```

Portanto, a UPF não tinha interface na rede de tráfego `192.168.71.0/26`.

Você também se lembrou de um problema antigo da OAI/RFsim em que a ordem das interfaces do Docker podia ser não determinística, a menos que `interface_name` fosse configurado explicitamente.

Atualizamos o `oai-cn5g/docker-compose.yaml` para que:

```text
upf:
  public_net  → eth0 → 192.168.70.134
  traffic_net → eth1 → 192.168.71.134

ext-dn:
  public_net  → eth0 → 192.168.70.135
  traffic_net → eth1 → 192.168.71.135
```

Depois de reiniciar a pilha com `down --volumes` e `up`, o alcance da DN local funcionou:

```text
UE → ext-dn: passou
ext-dn → UE: passou
UE → tun da UPF: passou
```

Esse foi um resultado-chave da depuração.

---

### 11. O ext-dn local se tornou o destino padrão do teste rápido

Depois que o alcance da DN local foi corrigido, mudamos o destino de ping padrão de:

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

Isso tornou o experimento mais adequado cientificamente, porque eliminou a variabilidade do caminho pela internet.

A alternativa continuou disponível:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh
```

---

### 12. Referência repetida final com a DN local

Depois de passar para o `ext-dn` local, você executou:

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
média do primeiro ping após o handover: 93,309 ms
```

Essa se tornou a primeira referência limpa do testbed de handover F1 em RFsim.

Nós a documentamos em:

```text
docs/report-baseline-results.md
```

A referência foi interpretada assim:

```text
A automação consegue iniciar e validar repetidamente o testbed de handover F1 da OAI em RFsim, disparar o handover F1 pela interface Telnet da CU e preservar a conectividade do plano de dados do UE com o ext-dn local, sem perda de pacotes, ao longo de cinco execuções.
```

Uma limitação conhecida permanece:

```text
O RTT ainda inclui o RFsim, o Docker, o escalonamento do host e picos de processamento.
```

Portanto, a métrica de interrupção do handover é útil, mas o RTT ainda não deve ser interpretado como latência limpa do protocolo.

---

### 13. Suporte opcional ao iperf e solução

Começamos então a acrescentar suporte opcional ao `iperf3`, para uma medição mais rica do tráfego do plano de usuário.

O Codex acrescentou:

```text
scripts/check_iperf_support.sh
scripts/run_iperf_test.sh
tools/parse_iperf.py
```

Tanto o `nr-ue` quanto o `ext-dn` tinham o `iperf3` disponível.

No entanto, os testes iperf TCP e UDP falharam. O comando do cliente gerado era:

```bash
docker exec nr-ue iperf3 -J -c 192.168.71.135 -t 10 -u
```

O provável problema era que o `iperf3` não estava sendo forçado a passar pela sessão PDU do UE. Como o `iperf3` instalado não suportava `--bind-dev`, a próxima correção deveria usar a vinculação pelo IP de origem:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135
```

Para UDP:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135 -u -b 1M
```

Esse caminho foi concluído em 19 de junho de 2026. O executor agora vincula o cliente ao endereço do UE descoberto na `oaitun_ue1`. O destino do ext-dn que funciona para o iperf é `192.168.70.135`, porque a UPF entrega o fluxo TCP/UDP no endereço do lado público do ext-dn; usar `192.168.71.135` produzia uma conexão de controle do iperf assimétrica.

O fluxo do teste rápido agora pode rodar o iperf simultaneamente com o ping durante o handover, usando `IPERF_ENABLED=1`. Os resumos de cada execução incluem os campos de vazão, jitter, perda e retransmissões, e as execuções repetidas agregam essas métricas. O iperf continua opcional, a menos que `IPERF_REQUIRED=1` esteja definido.

---

### 14. Problemas que tive ao pesquisar ou validar informações antigas

Houve algumas limitações práticas durante o percurso:

```text
1. Algumas buscas no GitHub não retornaram resultados logo depois que você enviou os arquivos.
   Isso parecia atraso na indexação ou arquivo ainda não enviado.

2. Eu conseguia inspecionar os arquivos presentes no repositório do GitHub, mas não as mudanças apenas locais antes de você enviá-las.

3. Eu me baseei principalmente no histórico do chat atual, nas saídas de comandos que você colou e no repositório do GitHub.
   Não fiz uma reconstrução ampla a partir de outros chats antigos.

4. Alguns artefatos de execução passaram a ser ignorados intencionalmente pelo .gitignore mais tarde; por isso, resumos futuros devem se basear em saídas coladas selecionadas, documentos versionados ou resultados curados, e não em todos os diretórios brutos de execução.

5. O resultado inicial do diagnóstico da UPF era ambíguo, porque o contêiner da UPF não incluía o `ping`.
   Corrigimos isso distinguindo `tool_missing` de uma falha real de alcance.
```

Não resta nenhuma incerteza importante sobre o fluxo principal. A medição opcional com iperf está agora integrada e validada para UDP e TCP; o trabalho futuro é de caracterização experimental, e não de habilitação básica do transporte.

---


## Conclusão concisa, em estilo de relatório

Ao longo deste trabalho, convertemos um tutorial de handover F1 no RFsimulator da OAI, executado manualmente, num testbed de pesquisa reproduzível. O testbed final automatiza a inicialização dos contêineres, a validação da prontidão, o disparo manual do handover F1 pela interface Telnet da CU, a coleta de logs e métricas, os experimentos repetidos e a documentação da referência. Identificamos e corrigimos vários problemas práticos: a ordem de inicialização, a prontidão do plano de dados do UE, a escolha incorreta do destino/interface do ping, a classificação errada das estatísticas de ping pelo parser, a falha de alcance da DN local, a falta de conexão da UPF à rede de tráfego e o não determinismo da ordem das interfaces do Docker. O testbed corrigido agora suporta um destino `ext-dn` local pela interface PDU do UE e produziu uma referência repetida com 5/5 handovers bem-sucedidos, 0% de perda de pacotes e interrupção média estimada do handover de aproximadamente 207 ms. A medição opcional baseada em iperf agora se vincula ao IP PDU do UE, roda simultaneamente durante o handover e é agregada nos experimentos repetidos.

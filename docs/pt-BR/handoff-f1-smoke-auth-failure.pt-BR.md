# Handoff: falha no painel do OAI RFsim / teste rápido F1

> Tradução para o português. O original em inglês é o [handoff-f1-smoke-auth-failure.md](../en/handoff-f1-smoke-auth-failure.md). Em caso de divergência, prevalece o original.

> **Resolução (03/07/2026):** o bloqueio central descrito aqui — a falha de autenticação
> `CONTEXT_NOT_FOUND` no AMF/AUSF para o IMSI `001010000000001` — foi
> **resolvido** pela correção do seed de assinantes no PR #17 (apelidos de autenticação numéricos e com prefixo
> `imsi-`). Valide o seed com `python3 scripts/validate_cn_subscriber.py`;
> veja "F1 smoke-test subscriber diagnostics" em `dashboard/README.md`. A observação sobre a estabilidade
> da consulta passiva ao telnet da CU continua relevante e é tratada mantendo a
> consulta ao telnet desativada por padrão. Este documento é mantido como contexto
> histórico.

Data: 01/07/2026
Repositório: `fsnobre/oai-rfsim-handover-testbed`
Branch atual no último teste: `main`
`main` atual no último estado conhecido: `75b025c Fix dashboard frontend React plugin config (#16)`
Topologia relevante: `f1` / RFsim / divisão CU-DU
Sintoma principal: o teste rápido F1 chega à etapa de prontidão do plano de dados do UE, mas a `oaitun_ue1` nunca é criada dentro do `oai-nr-ue`, então o teste atinge o tempo limite.

---

## 1. Resumo executivo

O painel em si agora é renderizado e consegue disparar ações, após a correção da configuração ausente do plugin React do Vite no PR #16. O teste rápido F1 disparado pelo painel expôs então vários problemas de implantação/execução, alguns corrigidos localmente e outros ainda pendentes como mudanças permanentes no repositório.

O bloqueio funcional atual não é o painel React nem a sincronização básica de rádio do RFsim. O bloqueio atual é que o UE chega ao estabelecimento de rádio/RRC, o AMF recebe o Registration Request do IMSI `001010000000001`, mas a autenticação no AMF/AUSF falha com:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

Como o registro/autenticação falha, o UE nunca conclui o NAS/estabelecimento da sessão PDU, e a `oaitun_ue1` nunca é criada. O teste rápido então atinge o tempo limite em:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

Há também um bug de estabilidade separado no painel: a consulta passiva ao telnet da CU envia comandos `help` repetidos ao servidor telnet da CU da OAI, o que antes fez a CU falhar com:

```text
*** buffer overflow detected ***: terminated
```

Esse problema da consulta ao telnet ainda deve ser corrigido de forma independente, porque pode desestabilizar a CU da OAI durante o uso do painel.

---

## 2. Problemas conhecidos já resolvidos

### 2.1 Painel em branco / tela azul após o PR #15

Sintoma:

- O navegador mostrava apenas o fundo escuro/azul.
- O erro anterior no console era:

```text
ReferenceError: React is not defined
```

Diagnóstico:

- O `dashboard/frontend/vite.config.js` estava ausente na `main`.
- O `@vitejs/plugin-react` existia no `package.json`, mas o Vite não estava configurado para usá-lo.

Correção:

- O PR #16 acrescentou:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

Status:

- O PR #16 foi incorporado com squash.
- Última `main` conhecida: `75b025c Fix dashboard frontend React plugin config (#16)`.
- O painel agora é renderizado.

Recompilação limpa recomendada após esta correção:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed
git checkout main
git pull

docker compose -f dashboard/docker-compose.dashboard.yml down
docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend

DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

---

### 2.2 Ações do painel desabilitadas

Sintoma:

```text
Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.
```

Diagnóstico:

- A `DASHBOARD_ENABLE_ACTIONS` é lida pelo backend na inicialização.
- Defini-la depois que o backend já está rodando não altera o backend em execução.

Correção/uso:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

ou recrie apenas o backend:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Status:

- Funciona quando o backend é iniciado com a variável já definida.

---

### 2.3 `/dev/net/tun` visível no host, mas não dentro do backend do painel

Sintoma no teste rápido F1 disparado pelo painel:

```text
[FAIL] /dev/net/tun missing — sudo modprobe tun
```

A verificação no host mostrou que o TUN existe:

```bash
sudo modprobe tun
lsmod | grep '^tun'
ls -l /dev/net/tun
```

Saída:

```text
crw-rw-rw- 1 root root 10, 200 ... /dev/net/tun
```

Diagnóstico:

- O contêiner do backend do painel executa o teste rápido por meio do acesso ao socket do Docker.
- `network_mode: host` não expõe automaticamente o `/dev/net/tun` dentro do contêiner do backend do painel.
- O script de preflight verifica `[[ -c /dev/net/tun ]]` no contexto em que roda, que, para as ações disparadas pelo painel, é o contêiner do backend.

Contorno local que funcionou:

```yaml
# dashboard/docker-compose.dashboard.local.yml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Inicie com os dois arquivos Compose:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Verificação:

```bash
docker exec oai-dashboard-backend sh -lc 'ls -l /dev/net/tun; test -c /dev/net/tun && echo TUN_VISIBLE'
```

Status:

- O override local corrigiu a falha do preflight.
- Ainda é recomendado um PR permanente: montar o `/dev/net/tun` no `dashboard-backend`.

---

### 2.4 Divergência de caminho de bind mount no Docker-outside-of-Docker

Sintoma após a correção do TUN:

```text
Error response from daemon: failed to create task for container:
error mounting "/repo/oai-cn5g/conf/config.yaml" to rootfs at "/openair-nrf/etc/config.yaml":
mount src=/repo/oai-cn5g/conf/config.yaml ... not a directory
```

Diagnóstico:

- O contêiner do backend do painel vê o repositório em `/repo`.
- Ele controla o daemon Docker do host por meio de `/var/run/docker.sock`.
- Os bind mounts do Docker são interpretados pelo daemon do host, e não pelo sistema de arquivos do contêiner do backend.
- O host não tem o repositório em `/repo`; o caminho real é:

```text
/home/nobre/Documents/repos/oai-rfsim-handover-testbed
```

Contorno local que funcionou:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed
REPO="$(pwd)"

cat > dashboard/docker-compose.dashboard.local.yml <<EOF
services:
  dashboard-backend:
    environment:
      DASHBOARD_REPO_ROOT: ${REPO}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ${REPO}:${REPO}:ro
      - ${REPO}/results:${REPO}/results:rw
    devices:
      - /dev/net/tun:/dev/net/tun
EOF
```

Inicie com os dois arquivos Compose:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Verificação:

```bash
docker exec oai-dashboard-backend sh -lc \
  'echo DASHBOARD_REPO_ROOT=$DASHBOARD_REPO_ROOT; ls -l "$DASHBOARD_REPO_ROOT/oai-cn5g/conf/config.yaml"; ls -l /dev/net/tun'
```

Status:

- O override local corrigiu a falha de bind mount.
- Ainda é recomendada uma correção permanente no repositório: o backend do painel deve usar o caminho do repositório no host quando for comandar o daemon Docker do host.

---

## 3. Problema pendente A: a consulta passiva ao telnet pelo painel pode derrubar a CU da OAI

### Sintoma observado

Durante o uso do painel, os logs da CU mostravam comandos telnet `help` repetidos:

```text
[TELNETSRV] Command received: readc 5 filled 5 "help"
[TELNETSRV] Telnet Client disconnected.
...
*** buffer overflow detected ***: terminated
[INFO  tini (1)] Main child exited with signal (with signal 'Aborted')
```

O AMF então mostrava:

```text
gNB Status: Disconnected
UE State: 5GMM-DEREGISTERED
```

### Diagnóstico

O backend do painel atualmente chama `telnet_poller.poll()` a cada montagem de estado. O `telnet_poller.poll()` envia `help` ao servidor telnet da CU para descobrir os comandos suportados. O intervalo de consulta padrão do painel é de 1 segundo, o que pode resultar em aproximadamente um comando `help` por segundo enquanto o painel estiver aberto.

Isso parece desestabilizar o servidor telnet da CU da OAI e pode fazer o processo da CU abortar.

### Correção recomendada

Criar uma correção urgente no painel:

- Adicionar `DASHBOARD_ENABLE_TELNET_POLLING=false|true`.
- Usar `false` como padrão.
- Quando for false, não chamar `TelnetPoller.poll()` a partir do `build_state()`.
- Retornar um estado de telnet seguro e explícito, informando que a consulta passiva ao telnet está desativada.
- Manter as ações explícitas separadas; testes rápidos e disparos de handover devem continuar funcionando quando `DASHBOARD_ENABLE_ACTIONS=true`.
- Se a consulta ao telnet for ativada para depuração, não enviar `help` a cada consulta. Acrescentar cache/limite de taxa, com intervalo mínimo de pelo menos 30 segundos, de preferência 60 segundos ou mais.

---

## 4. Problema pendente B: o teste rápido F1 atinge o tempo limite porque a autenticação do UE falha

### Resultado do teste rápido no terminal

Comando:

```bash
./scripts/run_smoke_test.sh
```

Resultado:

```text
[up] Waiting for UE registration and data plane (180s)
[ue-data] attempt 1: not ready (180s remaining)
...
[ue-data] attempt 60: not ready (0s remaining)
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

### Estado das interfaces do UE

Dentro do `oai-nr-ue`:

```text
eth0: 192.168.70.181/26
eth1: 192.168.71.181/26
default via 192.168.70.129 dev eth0
Device "oaitun_ue1" does not exist.
```

Portanto, a falha do ping é esperada: o teste rápido aguarda a `oaitun_ue1`, mas ela nunca aparece.

### Logs do UE

Linhas relevantes do log do UE:

```text
imsi = "001010000000001";
dnn= "oai";
nssai_sst=1;
will request PDU session ID 10, type 1, DNN oai, NSSAI 1.ffffff
Generate Initial NAS Message: Registration Request
Received NAS_DOWNLINK_DATA_IND type FGS_REGISTRATION_REJECT
Received Registration reject message too short
```

### Logs do AMF

Linhas relevantes do log do AMF:

```text
Received IMSI 001010000000001
A new UE (IMSI 001010000000001) has been successfully added!
5GMM-REGISTERED
Start to generate Authentication Vectors
Get Authentication Vectors from AUSF
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Could not parse UE Authentication from Json
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

Interpretação:

- O UE chega ao AMF.
- O AMF decodifica o Registration Request e o IMSI.
- O AMF pede vetores de autenticação ao AUSF.
- A consulta no AUSF/UDM/UDR retorna `CONTEXT_NOT_FOUND`.
- O AMF envia o Registration Reject.
- O UE nunca conclui a autenticação.
- Nenhuma sessão PDU é estabelecida.
- A `oaitun_ue1` nunca é criada.

Isso aponta para um problema no banco de dados de assinantes/inicialização, e não para um problema básico de RFsim/DU.

### Estado da DU/RFsim

Os logs da DU mostram que o lado de rádio/RRC está vivo:

```text
UE RNTI ... in-sync
average RSRP -43
BLER 0.00000
LCID 1: TX 18 RX 44 bytes
```

Portanto, o enlace de rádio do RFsim não é o bloqueio principal.

### Observação suspeita de apoio

O `docker ps` mostrava:

```text
mysql Up ... (unhealthy)
```

embora os outros serviços do núcleo estivessem saudáveis. Isso deve ser investigado, porque a consulta de assinante/autenticação depende do conteúdo do banco de dados do CN e do acesso do UDR/UDM/AUSF.

---

## 5. Problema de glob do zsh encontrado

Este comando falhou:

```bash
grep -RniE '...' conf-nr-ue.conf oai-cn5g/conf oai-cn5g/*.sql oai-cn5g/database
```

Erro:

```text
zsh: no matches found: oai-cn5g/*.sql
```

Esse é o comportamento do `zsh` com globs sem correspondência. Use `find` em vez disso:

```bash
find conf-nr-ue.conf oai-cn5g -type f \
  \( -name '*.conf' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' -o -name '*.json' \) \
  -print0 \
| xargs -0 grep -RniE 'imsi|key|opc|op |dnn|sst|sd|nssai|internet|00101|0000000001|000000001'
```

---

## 6. Próximas verificações manuais recomendadas

Execute estas verificações a partir da raiz do repositório depois do teste rápido com falha, enquanto os contêineres ainda existem.

### 6.1 Parar o backend do painel para isolar o teste rápido da OAI

```bash
docker stop oai-dashboard-backend
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd ~/Documents/repos/oai-rfsim-handover-testbed
./scripts/run_smoke_test.sh
```

Isso garante que a consulta ao telnet pelo painel não esteja influenciando o comportamento da CU.

### 6.2 Verificar os bancos de dados do MySQL

Tente primeiro a senha de root `linux`, porque ela é comum nas implantações docker-compose da OAI:

```bash
docker exec mysql sh -lc 'mysql -uroot -plinux -e "SHOW DATABASES;"'
```

Se isso falhar, inspecione o Compose/ambiente em busca das credenciais:

```bash
docker inspect mysql --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -Ei 'MYSQL|MARIADB|DATABASE|USER|PASSWORD'
```

Depois, liste os bancos com a senha real.

### 6.3 Verificar as tabelas

Supondo que o nome do banco seja `oai_db`:

```bash
docker exec mysql sh -lc 'mysql -uroot -plinux oai_db -e "SHOW TABLES;"'
```

### 6.4 Procurar o IMSI/SUPI do UE em todas as tabelas

```bash
docker exec mysql sh -lc '
mysql -uroot -plinux oai_db -N -e "SHOW TABLES" |
while read t; do
  echo "=== $t ==="
  mysql -uroot -plinux oai_db -e "SELECT * FROM \`$t\` LIMIT 5;" 2>/dev/null | grep -i "001010000000001\|imsi-001010000000001" || true
done
'
```

### 6.5 Verificar as tabelas de autenticação/assinatura

```bash
docker exec mysql sh -lc '
mysql -uroot -plinux oai_db -e "
SHOW TABLES LIKE \"%Authentication%\";
SHOW TABLES LIKE \"%authentication%\";
SHOW TABLES LIKE \"%Subscription%\";
SHOW TABLES LIKE \"%subscription%\";
"
'
```

### 6.6 Verificar o arquivo SQL de inicialização no repositório

```bash
find oai-cn5g -type f -name '*.sql' -print
find oai-cn5g -type f -name '*.sql' -print0 \
| xargs -0 grep -RniE '001010000000001|imsi-001010000000001|AuthenticationSubscription|authentication|subscription|fec86ba6eb70|opc|key|dnn|sst|sd|oai'
```

### 6.7 Se o assinante não estiver no banco, recriar o volume do banco do CN

Faça isto somente se este banco de laboratório for descartável:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed

docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd oai-cn5g
docker compose down -v
docker compose up -d mysql
docker logs -f mysql
```

Aguarde a inicialização do MySQL e, então:

```bash
docker compose up -d
cd ..
./scripts/run_smoke_test.sh
```

Aviso: `docker compose down -v` apaga o volume do banco do CN e quaisquer assinantes personalizados armazenados nele.

---

## 7. Correções permanentes sugeridas para o repositório

### 7.1 Implantação do backend do painel

Adicionar o `/dev/net/tun` ao `dashboard-backend`:

```yaml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Tratar também a divergência entre o caminho do repositório no host e `/repo` quando o backend usa o socket Docker do host:

- Ou exigir um arquivo de override local para a implantação de desenvolvimento.
- Ou alterar o Compose/a documentação para que `DASHBOARD_REPO_ROOT` use o caminho do repositório visível no host e o backend monte o repositório no mesmo caminho absoluto.
- O requisito principal: os caminhos passados às ações do Docker Compose precisam ser válidos no daemon Docker do host.

### 7.2 Consulta passiva ao telnet pelo painel

Acrescentar um comportamento seguro do telnet:

- Consulta passiva ao telnet desativada por padrão.
- Os comandos de ação explícitos continuam habilitados quando as ações estão habilitadas.
- Acrescentar uma variável de ambiente e documentação no README.
- Se ativada, limitar a taxa e guardar em cache o `help`/a descoberta de capacidades.

### 7.3 Diagnóstico do teste rápido

Melhorar a saída de falha quando a prontidão do plano de dados do UE falhar:

Quando o `wait_ue_data_ready.sh` atingir o tempo limite, imprimir automaticamente:

```bash
docker exec oai-nr-ue ip -4 addr
docker exec oai-nr-ue ip route
docker logs --tail=120 oai-nr-ue
docker logs --tail=160 oai-amf | grep -Ei 'authentication|context_not_found|registration|reject|imsi|ausf|udm|udr|supi|dnn|slice|nssai'
```

O modo de falha atual teria sido diagnosticado muito mais rapidamente se o script tivesse impresso:

```text
oaitun_ue1 missing
AUSF returned CONTEXT_NOT_FOUND for imsi-001010000000001
```

### 7.4 Verificação de banco/assinante no preflight

Considerar acrescentar uma verificação opcional de preflight que confirme que o assinante `001010000000001` existe no banco de dados antes de executar o teste rápido.

---

## 8. Prompt do Codex para análise/correção

Use o prompt abaixo com o Codex.

```text
You are working in repository fsnobre/oai-rfsim-handover-testbed.

We need you to analyze and propose/fix the current F1 RFsim smoke-test failure and also account for two dashboard deployment/runtime issues discovered during testing.

Current repo main:
- main includes PR #16: Fix dashboard frontend React plugin config.
- Dashboard renders now.
- F1 smoke can be launched, but does not complete.

Relevant local deployment context:
- Repo path on host:
  /home/nobre/Documents/repos/oai-rfsim-handover-testbed
- Dashboard is normally run with:
  DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
- Local compose override was needed to make dashboard-triggered Docker actions work:
  services:
    dashboard-backend:
      environment:
        DASHBOARD_REPO_ROOT: /home/nobre/Documents/repos/oai-rfsim-handover-testbed
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock:ro
        - /home/nobre/Documents/repos/oai-rfsim-handover-testbed:/home/nobre/Documents/repos/oai-rfsim-handover-testbed:ro
        - /home/nobre/Documents/repos/oai-rfsim-handover-testbed/results:/home/nobre/Documents/repos/oai-rfsim-handover-testbed/results:rw
      devices:
        - /dev/net/tun:/dev/net/tun

Issue 1 already diagnosed:
- Host has /dev/net/tun, but dashboard-backend did not see it.
- network_mode: host does not expose /dev devices.
- Add /dev/net/tun device mount to dashboard-backend or document required local override.

Issue 2 already diagnosed:
- Dashboard backend controls host Docker daemon via /var/run/docker.sock.
- If backend sees repo at /repo, Docker Compose bind mounts are sent to the host daemon as /repo/...
- Host does not have repo at /repo, causing bind mount failure:
  error mounting "/repo/oai-cn5g/conf/config.yaml" ... not a directory
- Need a robust documented solution or compose support so action paths are host-visible paths.

Issue 3 already diagnosed:
- Passive dashboard telnet polling may destabilize OAI CU.
- CU logs showed repeated:
  Command received: readc 5 filled 5 "help"
- Then CU crashed:
  *** buffer overflow detected ***: terminated
- Root cause appears to be dashboard/backend/collectors/telnet_poller.py sending "help" on every poll, while dashboard/backend/main.py calls telnet_poller.poll() during each state build. Default DASHBOARD_POLL_INTERVAL_SECONDS is 1 second.
- Required fix:
  - Add DASHBOARD_ENABLE_TELNET_POLLING=false|true, default false.
  - When false, build_state() must not call telnet_poller.poll().
  - Return an explicit telnet state saying passive polling is disabled.
  - Keep explicit actions (smoke run, handover trigger) separate.
  - If enabled, rate-limit and cache capability discovery; do not send help every second.

Current main smoke failure from terminal:
Command:
  ./scripts/run_smoke_test.sh

Failure:
  [up] Waiting for UE registration and data plane (180s)
  ...
  [ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s

Inside oai-nr-ue:
  eth0 192.168.70.181/26
  eth1 192.168.71.181/26
  default via 192.168.70.129 dev eth0
  Device "oaitun_ue1" does not exist.

UE logs:
  imsi = "001010000000001";
  dnn= "oai";
  nssai_sst=1;
  will request PDU session ID 10, type 1, DNN oai, NSSAI 1.ffffff
  Generate Initial NAS Message: Registration Request
  Received NAS_DOWNLINK_DATA_IND type FGS_REGISTRATION_REJECT
  Received Registration reject message too short

AMF logs:
  Received IMSI 001010000000001
  A new UE (IMSI 001010000000001) has been successfully added!
  Start to generate Authentication Vectors
  Get Authentication Vectors from AUSF
  Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
  Could not parse UE Authentication from Json
  Request Authentication Vectors failure
  Create Registration Reject and send to UE

DU logs:
  UE RNTI ... in-sync
  average RSRP -43
  BLER 0.00000
  LCID 1: TX 18 RX 44 bytes

Interpretation:
- RFsim/DU radio is working.
- UE reaches AMF.
- AMF asks AUSF/UDM/UDR for auth vectors.
- AUSF returns CONTEXT_NOT_FOUND for the subscriber/SUPI.
- AMF sends Registration Reject.
- UE never authenticates; PDU session is not established; oaitun_ue1 is never created.
- This is likely a CN DB/subscriber initialization or subscriber mismatch problem.
- docker ps also showed mysql as unhealthy.

Tasks:
1. Inspect repo configs:
   - conf-nr-ue.conf
   - gnb-docker-compose.yaml
   - oai-cn5g/docker-compose.yaml
   - oai-cn5g/database/oai_db.sql
   - oai-cn5g/conf/*.yaml
   - any DB init/health scripts
2. Confirm that subscriber IMSI/SUPI 001010000000001 / imsi-001010000000001 is present in oai_db.sql with matching authentication credentials, DNN, slice/NSSAI.
3. Confirm that the MySQL container is initialized from the expected SQL file.
4. Determine why AUSF returns CONTEXT_NOT_FOUND:
   - missing subscriber in DB?
   - wrong DB name?
   - SQL init not run because existing stale volume?
   - MySQL unhealthy or UDR cannot access data?
   - SUPI format mismatch: 001010000000001 vs imsi-001010000000001?
   - DNN/slice mismatch?
5. Propose and implement repo fixes where appropriate:
   - If DB init SQL is wrong/missing subscriber, patch it.
   - If smoke scripts should recreate/validate DB for lab use, add a safe documented command or preflight check.
   - Add a diagnostic to wait_ue_data_ready.sh or smoke failure path that detects missing oaitun_ue1 and prints focused UE/AMF/AUSF/UDM/UDR/MySQL hints.
   - Add preflight or validation for expected subscriber presence if feasible.
6. Separately implement dashboard safe telnet polling:
   - DASHBOARD_ENABLE_TELNET_POLLING default false.
   - no passive telnet commands unless enabled.
   - rate limit/caching if enabled.
7. Separately implement or document dashboard backend runtime requirements:
   - /dev/net/tun mount
   - host-visible repo path when using host Docker socket
   - local override example.

Validation commands:
  python3 -m compileall dashboard/backend
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
  docker compose -f dashboard/docker-compose.dashboard.yml config
  cd dashboard/frontend && npm install && npm run build
  cd ../..
  git diff --check

Manual diagnostics to include in final answer:
  docker exec mysql sh -lc 'mysql -uroot -p<password> -e "SHOW DATABASES;"'
  docker exec mysql sh -lc 'mysql -uroot -p<password> oai_db -e "SHOW TABLES;"'
  docker exec mysql sh -lc 'mysql -uroot -p<password> oai_db -N -e "SHOW TABLES" | while read t; do echo === $t ===; mysql -uroot -p<password> oai_db -e "SELECT * FROM \`$t\` LIMIT 5;" 2>/dev/null | grep -i "001010000000001\|imsi-001010000000001" || true; done'

Manual smoke after fixes:
  docker stop oai-dashboard-backend || true
  docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true
  ./scripts/run_smoke_test.sh

Success criteria:
- UE registration succeeds.
- oaitun_ue1 appears inside oai-nr-ue.
- wait_ue_data_ready.sh passes.
- F1 smoke advances past UE data-plane readiness.
- Dashboard no longer sends repeated "help" commands to CU by default.
- Dashboard-triggered smoke no longer fails due to missing /dev/net/tun or /repo bind-mount path mismatch.
```

---

## 9. Ordem de prioridade recomendada atual

1. Corrigir/desativar a consulta passiva ao telnet da CU pelo painel. Isso impede que o painel desestabilize a OAI durante a depuração.
2. Verificar o estado do assinante no MySQL e por que o AUSF retorna `CONTEXT_NOT_FOUND`.
3. Se o banco estiver desatualizado, recriar o volume do banco do CN e testar de novo.
4. Se o SQL de inicialização do banco estiver errado, corrigir o repositório.
5. Acrescentar um diagnóstico melhor do teste rápido para a `oaitun_ue1` ausente.
6. Tornar a implantação do backend do painel robusta quanto ao `/dev/net/tun` e aos caminhos do repositório visíveis no host.


---

## 10. Correções de acompanhamento aplicadas em `codex/f1-smoke-dashboard-runtime-fixes`

Data de aplicação: 01/07/2026
Branch: `codex/f1-smoke-dashboard-runtime-fixes`

Esta seção registra as mudanças concretas feitas no repositório após a investigação acima, por que cada mudança foi feita e como foi validada.

### 10.1 Consulta passiva ao telnet da CU pelo painel desativada por padrão

Arquivos alterados:

- `dashboard/backend/config.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/telnet_poller.py`
- `dashboard/docker-compose.dashboard.yml`
- `dashboard/README.md`

O que mudou:

- Adicionada a `DASHBOARD_ENABLE_TELNET_POLLING`, com padrão `false`.
- O `build_state()` e o `/api/ues` agora usam um auxiliar `current_telnet_state()`.
- Quando a consulta ao telnet está desativada, o backend não chama `telnet_poller.poll()` e retorna um estado de telnet explícito:

```text
Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- Se a consulta ao telnet for ativada intencionalmente, o `TelnetPoller` agora:
  - guarda em cache o último resultado da consulta por 5 segundos;
  - guarda em cache a descoberta de comandos/capacidades do telnet por 300 segundos;
  - evita enviar `help` a cada atualização de estado de 1 segundo do painel.

Motivo:

- Os logs da CU mostravam comandos telnet repetidos originados no painel:

```text
Command received: readc 5 filled 5 "help"
```

- Mais tarde, a CU falhou com:

```text
*** buffer overflow detected ***: terminated
```

- A observabilidade passiva não deve desestabilizar a CU da OAI. As ações explícitas de teste rápido e de handover continuam separadas da consulta passiva ao telnet.

Validação:

- A compilação do backend passou:

```bash
python3 -m compileall dashboard/backend
```

- O teste rápido dos endpoints do painel, com as ações habilitadas e a configuração padrão do telnet, confirmou que a consulta ao telnet estava desativada:

```text
/api/topology ok
telnet_enabled= False
telnet_summary= Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- As validações completas do painel passaram:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
```

### 10.2 Montagem do `/dev/net/tun` acrescentada ao backend do painel

Arquivos alterados:

- `dashboard/docker-compose.dashboard.yml`
- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`
- `dashboard/README.md`

O que mudou:

- Acrescentada esta montagem de dispositivo ao `dashboard-backend` no arquivo Compose base do painel:

```yaml
devices:
  - /dev/net/tun:/dev/net/tun
```

- Acrescentado o `tun_device` às verificações de execução das ações expostas por `/api/actions/capabilities`.
- Atualizada a validação da Fase 4 para incluir a nova chave de verificação de execução.

Motivo:

- `network_mode: host` não expõe os nós de dispositivo do host dentro do contêiner do backend do painel.
- Os testes rápidos disparados pelo painel executam o preflight dentro do `dashboard-backend`, então o script precisa ver o `/dev/net/tun` ali.
- Sem a montagem do dispositivo, o preflight falha mesmo quando o próprio host tem o TUN disponível.

Validação:

- O compose config mostrou a montagem do dispositivo no serviço renderizado:

```text
devices:
  - source: /dev/net/tun
    target: /dev/net/tun
    permissions: rwm
```

- O teste rápido do painel em execução, com as ações habilitadas, informou todas as verificações de execução como verdadeiras, incluindo `tun_device`:

```text
runtime_checks= {
  'bash': True,
  'docker': True,
  'docker_compose': True,
  'nc': True,
  'ip': True,
  'ss': True,
  'ping': True,
  'docker_socket': True,
  'tun_device': True,
  'results_writable': True,
  'trigger_script_exists': True,
  'smoke_script_exists': True,
  'repeated_smoke_script_exists': True
}
```

### 10.3 Override de ações do painel visível no host acrescentado

Arquivos alterados:

- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/README.md`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`

O que mudou:

- Acrescentado um override de exemplo versionado para implantações do painel com ações habilitadas:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- O override define:

```yaml
DASHBOARD_REPO_ROOT: ${DASHBOARD_HOST_REPO_ROOT}
```

- Ele monta o repositório dentro do contêiner do backend no mesmo caminho absoluto que tem no host.
- Ele mantém o repositório somente leitura, exceto `results/`, que continua gravável.
- Acrescentado o `docker_socket` às verificações de execução das ações.

Motivo:

- O backend controla o daemon Docker do host por meio de `/var/run/docker.sock`.
- Os bind mounts do Docker Compose são avaliados pelo daemon do host, e não dentro do contêiner do backend.
- Se o backend executar as ações a partir de `/repo`, o daemon do host tenta montar `/repo/...`, que não existe no host, e falha com erros como:

```text
error mounting "/repo/oai-cn5g/conf/config.yaml" ... not a directory
```

- A correção robusta é executar as ações do painel com `DASHBOARD_REPO_ROOT` definido como um caminho absoluto visível no host.

Validação:

- O Compose base do painel foi renderizado com sucesso:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml config
```

- O override host-actions foi renderizado com sucesso:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml config
```

- O backend foi iniciado pelo override host-actions documentado, com as ações habilitadas, e foi verificado:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
```

### 10.4 Apelidos de autenticação `imsi-` acrescentados ao seed do banco do CN

Arquivos alterados:

- `oai-cn5g/database/oai_db.sql`
- `scripts/validate_cn_subscriber.py`
- `scripts/preflight_check.sh`
- `oai-cn5g/healthscripts/mysql-healthcheck.sh`
- `dashboard/README.md`

O que mudou:

- Preservadas as linhas de autenticação existentes com IMSI numérico:

```text
001010000000001
001010000000002
001010000000003
001010000000004
```

- Acrescentados os apelidos de autenticação canônicos em formato de string SUPI:

```text
imsi-001010000000001
imsi-001010000000002
imsi-001010000000003
imsi-001010000000004
```

- Acrescentado o `scripts/validate_cn_subscriber.py` para verificar estaticamente que o seed SQL contém:
  - a linha de autenticação com IMSI numérico para `001010000000001`;
  - o apelido de autenticação `imsi-001010000000001`;
  - a chave `fec86ba6eb707ed08905757b1bb44b8f`;
  - o OPC `C42449363BBAD02B66D16BC975D77CC1`;
  - a DNN `oai`;
  - a fatia SST `1` / SD `FFFFFF`.

- Esse validador foi ligado ao `scripts/preflight_check.sh`.
- Corrigido o `mysql-healthcheck.sh` para que um seed de autenticação RFsim ausente deixe o MySQL não saudável, em vez de ser redefinido como saudável.

Motivo:

- A configuração do UE usa o IMSI numérico `001010000000001`.
- A falha observada no AMF/AUSF foi:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

- Isso é coerente com o AUSF/UDM/UDR buscando os dados de autenticação pela string SUPI canônica `imsi-001010000000001`, enquanto o banco continha apenas as linhas numéricas.
- Quando a autenticação falha, o registro NAS é rejeitado, nenhuma sessão PDU é estabelecida e a `oaitun_ue1` nunca aparece.

Validação:

- A validação estática do assinante passou:

```bash
python3 scripts/validate_cn_subscriber.py
```

Saída:

```text
[PASS] RFsim subscriber seed contains numeric and imsi-prefixed auth aliases, DNN oai, and SST 1 / SD FFFFFF
```

- O preflight durante o teste rápido manual informou:

```text
[PASS] RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice
```

- Um teste rápido F1 novo criou um novo contêiner MySQL a partir do seed SQL corrigido, e o MySQL ficou saudável:

```text
[ready] oai-amf: healthy
[ready] oai-smf: healthy
[ready] oai-upf: healthy
```

### 10.5 Diagnóstico focado para o tempo limite do plano de dados do UE acrescentado

Arquivos alterados:

- `scripts/wait_ue_data_ready.sh`
- `dashboard/README.md`

O que mudou:

- Ao atingir o tempo limite, o `wait_ue_data_ready.sh` agora verifica se a `oaitun_ue1` existe dentro do `oai-nr-ue`.
- Ele imprime trechos focados de log recente de:
  - `oai-nr-ue`
  - `oai-amf`
  - `oai-ausf`
  - `oai-udm`
  - `oai-udr`
- Ele imprime o estado/a saúde do contêiner MySQL e consulta a `AuthenticationSubscription` por:
  - `001010000000001`
  - `imsi-001010000000001`
- Ele imprime dicas de próximos passos para `CONTEXT_NOT_FOUND`, MySQL desatualizado/não saudável e problemas de sessão PDU/DNN/fatia.

Motivo:

- A falha original do teste rápido informava apenas um tempo limite do ping:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

- Essa mensagem esconde a distinção real entre:
  - falha de rádio/RRC;
  - falha de registro/autenticação NAS;
  - falha no estabelecimento da sessão PDU;
  - falha de roteamento do plano de dados.

- Neste caso, o lado do rádio estava vivo, mas a autenticação NAS falhou. O caminho de falha deve levar o operador imediatamente às evidências do UE/AMF/AUSF/UDM/UDR/MySQL.

Validação:

- A validação de sintaxe do shell passou:

```bash
bash -n scripts/wait_ue_data_ready.sh scripts/preflight_check.sh oai-cn5g/healthscripts/mysql-healthcheck.sh
```

- O teste rápido manual bem-sucedido não acionou o caminho de tempo limite, que é o resultado esperado após a correção do seed do banco.
- A sintaxe dos comandos de diagnóstico foi inspecionada e corrigida antes da validação final.

### 10.6 Verificações de capacidade das ações em execução atualizadas

Arquivos alterados:

- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`

O que mudou:

- O `/api/actions/capabilities` agora inclui:

```text
docker_socket
tun_device
```

Motivo:

- Para as ações iniciadas pelo painel, o backend precisa conseguir falar com o daemon Docker do host e precisa ver o `/dev/net/tun`.
- Esses são pré-requisitos operacionais; por isso, a interface/API deve expô-los como verificações de execução.

Validação:

- A validação da Fase 4 foi atualizada e passou:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
```

- O teste rápido do endpoint em execução confirmou que as duas verificações eram verdadeiras:

```text
'docker_socket': True
'tun_device': True
```

### 10.7 Validação manual do teste rápido F1 após as correções

Comando executado:

```bash
docker stop oai-dashboard-backend || true
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true
./scripts/run_smoke_test.sh
```

Observação importante:

- Nenhum contêiner de núcleo/RAN estava presente antes da execução, exceto os contêineres parados do painel; por isso, o MySQL foi inicializado do zero a partir do `oai_db.sql` corrigido.
- Se já existir um contêiner MySQL desatualizado, pode ser necessário recriá-lo para que ele incorpore as mudanças do seed SQL:

```bash
./scripts/down.sh f1 --volumes
```

Saída de validação observada:

```text
[PASS] RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice
[ready] oai-amf: healthy
[ready] oai-smf: healthy
[ready] oai-upf: healthy
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[PASS] oaitun_ue1 present with IP: 10.0.0.2
[PASS] UE can reach 192.168.71.135 via oaitun_ue1
RRC F1 handover triggered for UE 1
```

Artefato da execução:

```text
results/runs/20260701_084915_f1_handover_smoke
```

Métricas de resumo do `summary.json`:

```text
status=pass
ue_data_ready=True
handover_triggered=True
estimated_interruption_ms=200.924
packet_loss_percent=0.0
rtt_avg_ms=12.121538461538462
ping_metrics_valid=True
```

Conclusão:

- O registro do UE foi bem-sucedido.
- A `oaitun_ue1` apareceu dentro do `oai-nr-ue` com o IP `10.0.0.2`.
- A prontidão do plano de dados do UE passou.
- O teste rápido F1 avançou além da falha anterior e foi concluído com sucesso.
- O comando de handover F1 foi aceito.

### 10.8 Conjunto completo de comandos de validação executado após as correções

Comandos executados com sucesso:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
python3 scripts/validate_cn_subscriber.py
docker compose -f dashboard/docker-compose.dashboard.yml config
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml config
cd dashboard/frontend && npm install && npm run build
git diff --check
```

Resultado do build do frontend:

```text
vite v6.4.3 building for production...
✓ built
```

Teste rápido dos endpoints do painel com o override host-actions:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build dashboard-backend
```

Endpoints verificados:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
telnet_enabled= False
```

O backend do painel com ações habilitadas foi parado após esta validação, para não ficar exposto.

### 10.9 Status atualizado dos itens antes pendentes

Item antes pendente | Status atual
--- | ---
Desativar/corrigir a consulta passiva ao telnet da CU | Implementado. O padrão é desativado; o modo ativado tem limite de taxa e guarda em cache a descoberta via `help`.
Verificar/corrigir o seed do banco de assinantes | Implementado. Acrescentados os apelidos de autenticação `imsi-` e a validação estática.
Tratar o diagnóstico de MySQL desatualizado/não saudável | Melhorado. O healthcheck valida os apelidos de autenticação do RFsim; o caminho de tempo limite imprime o diagnóstico do MySQL/assinante. Contêineres desatualizados existentes ainda podem precisar de uma reinicialização explícita.
Melhorar o diagnóstico da `oaitun_ue1` ausente | Implementado no `wait_ue_data_ready.sh`.
Disponibilizar o `/dev/net/tun` para as ações do painel | Implementado no Compose base do painel.
Tratar a divergência de caminho com o socket Docker do host | Documentado e suportado com `dashboard/docker-compose.dashboard.host-actions.example.yml`.
Validar o teste rápido F1 de ponta a ponta | Concluído com sucesso na execução `20260701_084915_f1_handover_smoke`.

### 10.10 Observações operacionais restantes

- Se o MySQL já existir a partir de um seed antigo, editar o `oai_db.sql` não basta. Recrie o contêiner/volume do banco do núcleo para reinicializar o laboratório:

```bash
./scripts/down.sh f1 --volumes
```

- Mantenha a consulta passiva ao telnet desativada, a menos que seja realmente necessária:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=false
```

- Para as ações disparadas pelo painel, use o override host-actions, para que os bind mounts do Compose da OAI sejam visíveis no host:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- O teste rápido manual bem-sucedido deixou a pilha F1 da OAI rodando quando esta seção foi escrita. Pare-a ao terminar com:

```bash
./scripts/down.sh f1
```

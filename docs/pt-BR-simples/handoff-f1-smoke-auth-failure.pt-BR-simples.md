# Passagem de contexto: falha do teste rápido F1 em rfsim pelo painel web

> Tradução para o português em Linguagem Simples. O original em inglês é o [handoff-f1-smoke-auth-failure.md](../en/handoff-f1-smoke-auth-failure.md). Se houver diferença entre os dois, vale o original.

> **Solução (03/07/2026):** o bloqueio central descrito aqui foi **resolvido**. Era a falha de autenticação `CONTEXT_NOT_FOUND` no AMF e no AUSF para o IMSI `001010000000001`. A correção da carga inicial de assinantes, no PR #17, acrescentou os registros de autenticação com o IMSI numérico e com o prefixo `imsi-`. Valide a carga com `python3 scripts/validate_cn_subscriber.py`. Veja "F1 smoke-test subscriber diagnostics" no `dashboard/README.md`.
>
> A nota sobre a estabilidade da consulta periódica pelo Telnet da CU continua valendo. A solução é manter essa consulta desligada por padrão. Este documento fica como contexto histórico.

Data: 01/07/2026
Repositório: `fsnobre/oai-rfsim-handover-testbed`
Branch no último teste: `main`
Último estado conhecido do main: `75b025c Fix dashboard frontend React plugin config (#16)`
Topologia: `f1` / rfsim / divisão CU-DU
Sintoma principal: o teste rápido F1 chega à espera pelo plano de usuário do UE, mas a `oaitun_ue1` nunca é criada dentro do `oai-nr-ue`. Por isso, o teste estoura o tempo.

---

## 1. Resumo executivo

O painel web agora aparece e consegue iniciar ações. Isso veio da correção da configuração do plugin React do Vite, que faltava, no PR #16. Em seguida, o teste rápido F1 iniciado pelo painel mostrou vários problemas de implantação e de execução. Alguns foram corrigidos no computador local. Outros ainda esperam virar mudanças permanentes no repositório.

O bloqueio atual não está no painel React nem na sincronização básica de rádio do rfsim. O bloqueio está aqui:

1. O UE chega à configuração de rádio e de RRC.
2. O AMF recebe o Registration Request do IMSI `001010000000001`.
3. A autenticação no AMF e no AUSF falha com:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

Como o registro e a autenticação falham, o UE nunca conclui o NAS nem cria a sessão PDU, e a `oaitun_ue1` nunca é criada. O teste rápido então estoura o tempo em:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

Há também um erro separado de estabilidade do painel. A consulta periódica pelo Telnet da CU envia comandos `help` repetidos ao servidor Telnet da CU da OAI. Antes, isso derrubou a CU com:

```text
*** buffer overflow detected ***: terminated
```

Esse problema da consulta pelo Telnet ainda deve ser corrigido à parte, porque pode deixar a CU da OAI instável durante o uso do painel.

---

## 2. Problemas conhecidos já resolvidos

### 2.1 Painel em branco, só com fundo azul, depois do PR #15

Sintoma:

- O navegador mostrava só o fundo escuro, azulado.
- O erro anterior no console era:

```text
ReferenceError: React is not defined
```

Diagnóstico:

- O `dashboard/frontend/vite.config.js` não existia no `main`.
- O `@vitejs/plugin-react` estava no `package.json`, mas o Vite não estava configurado para usá-lo.

Correção:

- O PR #16 acrescentou:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

Situação:

- O PR #16 entrou com *squash merge*.
- Último `main` conhecido: `75b025c Fix dashboard frontend React plugin config (#16)`.
- O painel agora aparece.

Recompilação limpa recomendada depois desta correção:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed
git checkout main
git pull

docker compose -f dashboard/docker-compose.dashboard.yml down
docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend

DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

---

### 2.2 Ações do painel desligadas

Sintoma:

```text
Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.
```

Diagnóstico:

- O backend lê a `DASHBOARD_ENABLE_ACTIONS` quando sobe.
- Definir a variável depois que o backend já está rodando não muda nada.

Correção e uso:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

ou recrie só o backend:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Situação:

- Funciona quando o backend sobe com a variável já definida.

---

### 2.3 O `/dev/net/tun` existe no computador, mas não dentro do backend do painel

Sintoma no teste rápido F1 iniciado pelo painel:

```text
[FAIL] /dev/net/tun missing — sudo modprobe tun
```

A conferência no computador mostrou que o TUN existe:

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

- O contêiner do backend do painel roda o teste rápido pelo acesso ao socket do Docker.
- O `network_mode: host` não mostra automaticamente o `/dev/net/tun` dentro do contêiner do backend.
- A verificação prévia confere `[[ -c /dev/net/tun ]]` no lugar onde roda. Nas ações iniciadas pelo painel, esse lugar é o contêiner do backend.

Solução local que funcionou:

```yaml
# dashboard/docker-compose.dashboard.local.yml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Suba com os dois arquivos Compose:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Conferência:

```bash
docker exec oai-dashboard-backend sh -lc 'ls -l /dev/net/tun; test -c /dev/net/tun && echo TUN_VISIBLE'
```

Situação:

- O arquivo local corrigiu a falha da verificação prévia.
- Ainda se recomenda um PR permanente: montar o `/dev/net/tun` no `dashboard-backend`.

---

### 2.4 Caminho errado nas montagens, com o Docker controlado de fora do contêiner

Sintoma depois da correção do TUN:

```text
Error response from daemon: failed to create task for container:
error mounting "/repo/oai-cn5g/conf/config.yaml" to rootfs at "/openair-nrf/etc/config.yaml":
mount src=/repo/oai-cn5g/conf/config.yaml ... not a directory
```

Diagnóstico:

- O contêiner do backend vê o repositório em `/repo`.
- Ele controla o Docker do computador por `/var/run/docker.sock`.
- Quem interpreta as montagens do Docker é o Docker do computador, e não o sistema de arquivos do contêiner do backend.
- O computador não tem o repositório em `/repo`. O caminho real é:

```text
/home/nobre/Documents/repos/oai-rfsim-handover-testbed
```

Solução local que funcionou:

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

Suba com os dois arquivos Compose:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Conferência:

```bash
docker exec oai-dashboard-backend sh -lc \
  'echo DASHBOARD_REPO_ROOT=$DASHBOARD_REPO_ROOT; ls -l "$DASHBOARD_REPO_ROOT/oai-cn5g/conf/config.yaml"; ls -l /dev/net/tun'
```

Situação:

- O arquivo local corrigiu a falha de montagem.
- Ainda se recomenda uma correção permanente no repositório: quando o backend do painel controlar o Docker do computador, ele deve usar o caminho do repositório no computador.

---

## 3. Problema pendente A: a consulta periódica pelo Telnet pode derrubar a CU da OAI

### Sintoma observado

Durante o uso do painel, os logs da CU mostraram comandos `help` repetidos pelo Telnet:

```text
[TELNETSRV] Command received: readc 5 filled 5 "help"
[TELNETSRV] Telnet Client disconnected.
...
*** buffer overflow detected ***: terminated
[INFO  tini (1)] Main child exited with signal (with signal 'Aborted')
```

Depois, o AMF mostrou:

```text
gNB Status: Disconnected
UE State: 5GMM-DEREGISTERED
```

### Diagnóstico

Hoje, o backend do painel chama `telnet_poller.poll()` em toda montagem do estado. O `telnet_poller.poll()` envia `help` ao servidor Telnet da CU para descobrir os comandos aceitos. O intervalo padrão de consulta do painel é de 1 segundo. Assim, com o painel aberto, a CU pode receber cerca de um `help` por segundo.

Isso parece deixar o servidor Telnet da CU da OAI instável e pode fazer o processo da CU parar.

### Correção recomendada

Criar uma correção rápida no painel:

- Acrescentar `DASHBOARD_ENABLE_TELNET_POLLING=false|true`, com padrão `false`.
- Com `false`, não chamar `TelnetPoller.poll()` a partir do `build_state()`.
- Retornar um estado Telnet explícito e seguro, dizendo que a consulta periódica está desligada.
- Manter as ações explícitas separadas. Os testes rápidos e os comandos de handover devem continuar funcionando com `DASHBOARD_ENABLE_ACTIONS=true`.
- Se a consulta for ligada para depuração, não enviar `help` a cada consulta. Acrescentar cache e limite de frequência, com intervalo mínimo de 30 segundos, de preferência 60 segundos ou mais.

---

## 4. Problema pendente B: o teste rápido F1 estoura o tempo porque a autenticação do UE falha

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

Então, a falha do ping é esperada: o teste rápido espera a `oaitun_ue1`, mas ela nunca aparece.

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

1. O UE chega ao AMF.
2. O AMF decodifica o Registration Request e o IMSI.
3. O AMF pede ao AUSF os vetores de autenticação.
4. A busca no AUSF, no UDM e no UDR retorna `CONTEXT_NOT_FOUND`.
5. O AMF envia o Registration Reject.
6. O UE nunca conclui a autenticação.
7. Nenhuma sessão PDU é criada.
8. A `oaitun_ue1` nunca é criada.

Isso aponta para um problema na base de assinantes ou na carga inicial dela, e não para um problema básico do rfsim ou da DU.

### Estado da DU e do rfsim

Os logs da DU mostram o lado de rádio e de RRC funcionando:

```text
UE RNTI ... in-sync
average RSRP -43
BLER 0.00000
LCID 1: TX 18 RX 44 bytes
```

Então, o enlace de rádio do rfsim não é o bloqueio principal.

### Observação suspeita

O `docker ps` mostrou:

```text
mysql Up ... (unhealthy)
```

Os outros serviços do núcleo 5G estavam saudáveis. Investigue isso, porque a busca do assinante e a autenticação dependem do conteúdo da base do núcleo 5G e do acesso do UDR, do UDM e do AUSF a ela.

---

## 5. Problema com globs no zsh

Este comando falhou:

```bash
grep -RniE '...' conf-nr-ue.conf oai-cn5g/conf oai-cn5g/*.sql oai-cn5g/database
```

Erro:

```text
zsh: no matches found: oai-cn5g/*.sql
```

É o comportamento do `zsh` com um glob sem correspondência. Use o `find`:

```bash
find conf-nr-ue.conf oai-cn5g -type f \
  \( -name '*.conf' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' -o -name '*.json' \) \
  -print0 \
| xargs -0 grep -RniE 'imsi|key|opc|op |dnn|sst|sd|nssai|internet|00101|0000000001|000000001'
```

---

## 6. Próximas conferências manuais recomendadas

Execute estes comandos na raiz do repositório, depois do teste rápido que falhou, com os contêineres ainda presentes.

### 6.1 Parar o backend do painel para isolar o teste rápido da OAI

```bash
docker stop oai-dashboard-backend
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd ~/Documents/repos/oai-rfsim-handover-testbed
./scripts/run_smoke_test.sh
```

Assim, a consulta pelo Telnet do painel não influencia a CU.

### 6.2 Conferir as bases do MySQL

Tente primeiro a senha de root `linux`, comum nas implantações Docker Compose da OAI:

```bash
docker exec mysql sh -lc 'mysql -uroot -plinux -e "SHOW DATABASES;"'
```

Se falhar, procure as credenciais no Compose e no ambiente:

```bash
docker inspect mysql --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -Ei 'MYSQL|MARIADB|DATABASE|USER|PASSWORD'
```

Depois, liste as bases com a senha real.

### 6.3 Conferir as tabelas

Supondo que a base se chame `oai_db`:

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

### 6.5 Conferir as tabelas de autenticação e de assinatura

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

### 6.6 Conferir o arquivo SQL de carga inicial no repositório

```bash
find oai-cn5g -type f -name '*.sql' -print
find oai-cn5g -type f -name '*.sql' -print0 \
| xargs -0 grep -RniE '001010000000001|imsi-001010000000001|AuthenticationSubscription|authentication|subscription|fec86ba6eb70|opc|key|dnn|sst|sd|oai'
```

### 6.7 Se o assinante faltar na base, recriar o volume da base do núcleo 5G

> **CUIDADO:** Só faça isto se a base deste laboratório puder ser descartada. O `docker compose down -v` apaga o volume da base do núcleo 5G e todos os assinantes personalizados guardados nele.

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed

docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd oai-cn5g
docker compose down -v
docker compose up -d mysql
docker logs -f mysql
```

Espere o MySQL terminar de inicializar. Depois:

```bash
docker compose up -d
cd ..
./scripts/run_smoke_test.sh
```

---

## 7. Correções permanentes sugeridas para o repositório

### 7.1 Implantação do backend do painel

Acrescente o `/dev/net/tun` ao `dashboard-backend`:

```yaml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Resolva também a diferença entre o caminho do repositório no computador e o `/repo`, quando o backend usa o socket do Docker do computador. Opções:

- exigir um arquivo Compose local para a implantação de desenvolvimento; ou
- mudar o Compose e a documentação para que a `DASHBOARD_REPO_ROOT` use o caminho do repositório no computador, e o backend monte o repositório no mesmo caminho absoluto.

O requisito-chave: os caminhos passados às ações do Docker Compose devem valer para o Docker do computador.

### 7.2 Consulta periódica pelo Telnet no painel

Acrescente um comportamento seguro do Telnet:

- consulta periódica desligada por padrão;
- comandos de ação explícitos continuam ligados quando as ações estão ligadas;
- variável de ambiente e documentação no README;
- se ligada, limite de frequência e cache da descoberta de capacidades pelo `help`.

### 7.3 Diagnóstico do teste rápido

Melhore a saída de erro quando a espera pelo plano de usuário do UE falhar.

Quando o `wait_ue_data_ready.sh` estourar o tempo, mostre automaticamente:

```bash
docker exec oai-nr-ue ip -4 addr
docker exec oai-nr-ue ip route
docker logs --tail=120 oai-nr-ue
docker logs --tail=160 oai-amf | grep -Ei 'authentication|context_not_found|registration|reject|imsi|ausf|udm|udr|supi|dnn|slice|nssai'
```

A falha atual teria sido diagnosticada muito mais rápido se o script tivesse mostrado:

```text
oaitun_ue1 missing
AUSF returned CONTEXT_NOT_FOUND for imsi-001010000000001
```

### 7.4 Conferência prévia da base e do assinante

Avalie acrescentar uma verificação prévia opcional, que confira se o assinante `001010000000001` existe na base antes do teste rápido.

---

## 8. Prompt para o Codex analisar e corrigir

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

## 9. Ordem de prioridade recomendada na época

1. Corrigir ou desligar a consulta periódica pelo Telnet da CU no painel. Isso impede que o painel deixe a OAI instável durante a depuração.
2. Conferir o estado do assinante no MySQL e descobrir por que o AUSF retorna `CONTEXT_NOT_FOUND`.
3. Se a base estiver desatualizada, recriar o volume da base do núcleo 5G e testar de novo.
4. Se o SQL de carga inicial estiver errado, corrigir o repositório.
5. Melhorar o diagnóstico do teste rápido quando faltar a `oaitun_ue1`.
6. Tornar a implantação do backend do painel robusta quanto ao `/dev/net/tun` e aos caminhos do repositório no computador.


---

## 10. Correções feitas no branch `codex/f1-smoke-dashboard-runtime-fixes`

Data: 01/07/2026
Branch: `codex/f1-smoke-dashboard-runtime-fixes`

Esta seção registra as mudanças concretas feitas no repositório depois da investigação acima. Ela diz por que cada mudança foi feita e como foi validada.

### 10.1 Consulta periódica pelo Telnet da CU desligada por padrão

Arquivos alterados:

- `dashboard/backend/config.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/telnet_poller.py`
- `dashboard/docker-compose.dashboard.yml`
- `dashboard/README.md`

O que mudou:

- Foi criada a `DASHBOARD_ENABLE_TELNET_POLLING`, com padrão `false`.
- O `build_state()` e o `/api/ues` agora usam uma função auxiliar `current_telnet_state()`.
- Com a consulta desligada, o backend não chama `telnet_poller.poll()` e retorna um estado Telnet explícito:

```text
Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- Se a consulta for ligada de propósito, o `TelnetPoller` agora:
  - guarda o último resultado por 5 segundos;
  - guarda a descoberta de comandos e capacidades do Telnet por 300 segundos;
  - não envia `help` a cada atualização de 1 segundo do painel.

Motivo:

- Os logs da CU mostraram comandos Telnet repetidos vindos do painel:

```text
Command received: readc 5 filled 5 "help"
```

- Depois, a CU caiu com:

```text
*** buffer overflow detected ***: terminated
```

- A observação passiva não pode deixar a CU da OAI instável. As ações explícitas de teste rápido e de handover ficam separadas da consulta periódica pelo Telnet.

Validação:

- A compilação do backend passou:

```bash
python3 -m compileall dashboard/backend
```

- Um teste dos endpoints do painel, com as ações ligadas e o Telnet no valor padrão, confirmou a consulta desligada:

```text
/api/topology ok
telnet_enabled= False
telnet_summary= Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- Todas as validações do painel passaram:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
```

### 10.2 Montagem do `/dev/net/tun` no backend do painel

Arquivos alterados:

- `dashboard/docker-compose.dashboard.yml`
- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`
- `dashboard/README.md`

O que mudou:

- Esta montagem de dispositivo foi acrescentada ao `dashboard-backend`, no arquivo Compose base do painel:

```yaml
devices:
  - /dev/net/tun:/dev/net/tun
```

- O `tun_device` entrou nas conferências de execução das ações, mostradas em `/api/actions/capabilities`.
- A validação da fase 4 passou a incluir a nova chave.

Motivo:

- O `network_mode: host` não mostra os dispositivos do computador dentro do contêiner do backend.
- Os testes rápidos iniciados pelo painel rodam a verificação prévia dentro do `dashboard-backend`. Por isso, o script precisa ver o `/dev/net/tun` ali.
- Sem a montagem, a verificação prévia falha, mesmo com o TUN disponível no computador.

Validação:

- A configuração do Compose mostrou a montagem no serviço gerado:

```text
devices:
  - source: /dev/net/tun
    target: /dev/net/tun
    permissions: rwm
```

- Um teste do painel rodando, com as ações ligadas, mostrou todas as conferências como verdadeiras, inclusive o `tun_device`:

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

### 10.3 Arquivo Compose de exemplo para ações com caminhos do computador

Arquivos alterados:

- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/README.md`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`

O que mudou:

- Foi incluído no repositório um arquivo Compose de exemplo para implantações do painel com ações ligadas:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- Esse arquivo define:

```yaml
DASHBOARD_REPO_ROOT: ${DASHBOARD_HOST_REPO_ROOT}
```

- Ele monta o repositório, dentro do contêiner do backend, no mesmo caminho absoluto do computador.
- Ele mantém o repositório só para leitura, menos `results/`, que continua com permissão de escrita.
- O `docker_socket` entrou nas conferências de execução das ações.

Motivo:

- O backend controla o Docker do computador por `/var/run/docker.sock`.
- O Docker do computador interpreta as montagens do Docker Compose, e não o contêiner do backend.
- Se o backend roda as ações a partir de `/repo`, o Docker do computador tenta montar `/repo/...`. Esse caminho não existe no computador, e a montagem falha com erros como:

```text
error mounting "/repo/oai-cn5g/conf/config.yaml" ... not a directory
```

- A correção robusta é rodar as ações do painel com a `DASHBOARD_REPO_ROOT` apontando para um caminho absoluto que existe no computador.

Validação:

- A configuração Compose base do painel foi gerada com sucesso:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml config
```

- A configuração com o arquivo de exemplo também foi gerada com sucesso:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml config
```

- O backend subiu com o arquivo de exemplo documentado e com as ações ligadas. A conferência mostrou:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
```

### 10.4 Registros de autenticação com o prefixo `imsi-` na carga inicial da base do núcleo 5G

Arquivos alterados:

- `oai-cn5g/database/oai_db.sql`
- `scripts/validate_cn_subscriber.py`
- `scripts/preflight_check.sh`
- `oai-cn5g/healthscripts/mysql-healthcheck.sh`
- `dashboard/README.md`

O que mudou:

- Os registros de autenticação com o IMSI numérico foram mantidos:

```text
001010000000001
001010000000002
001010000000003
001010000000004
```

- Foram acrescentados registros equivalentes, com o SUPI no formato de texto canônico:

```text
imsi-001010000000001
imsi-001010000000002
imsi-001010000000003
imsi-001010000000004
```

- Foi criado o `scripts/validate_cn_subscriber.py`. Ele confere, sem rodar nada, se o SQL de carga inicial tem:
  - o registro de autenticação com o IMSI numérico `001010000000001`;
  - o registro equivalente `imsi-001010000000001`;
  - a chave `fec86ba6eb707ed08905757b1bb44b8f`;
  - o OPC `C42449363BBAD02B66D16BC975D77CC1`;
  - o DNN `oai`;
  - o slice com SST `1` e SD `FFFFFF`.

- Esse validador entrou no `scripts/preflight_check.sh`.
- O `mysql-healthcheck.sh` foi corrigido. Agora, se faltar a carga de autenticação do rfsim, o MySQL continua marcado como não saudável, em vez de voltar a saudável.

Motivo:

- A configuração do UE usa o IMSI numérico `001010000000001`.
- A falha observada no AMF e no AUSF foi:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

- Isso é coerente com o AUSF, o UDM e o UDR buscarem os dados de autenticação pelo SUPI canônico `imsi-001010000000001`, enquanto a base só tinha os registros numéricos.
- Quando a autenticação falha, o registro NAS é recusado, nenhuma sessão PDU é criada, e a `oaitun_ue1` nunca aparece.

Validação:

- A validação estática do assinante passou:

```bash
python3 scripts/validate_cn_subscriber.py
```

Saída:

```text
[PASS] RFsim subscriber seed contains numeric and imsi-prefixed auth aliases, DNN oai, and SST 1 / SD FFFFFF
```

- A verificação prévia, durante o teste rápido manual, mostrou:

```text
[PASS] RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice
```

- Um teste rápido F1 do zero criou um contêiner MySQL novo, a partir do SQL corrigido, e o MySQL ficou saudável:

```text
[ready] oai-amf: healthy
[ready] oai-smf: healthy
[ready] oai-upf: healthy
```

### 10.5 Diagnóstico focado quando a espera pelo plano de usuário estoura o tempo

Arquivos alterados:

- `scripts/wait_ue_data_ready.sh`
- `dashboard/README.md`

O que mudou:

- Quando o tempo estoura, o `wait_ue_data_ready.sh` agora confere se a `oaitun_ue1` existe dentro do `oai-nr-ue`.
- Ele mostra trechos recentes e focados dos logs de:
  - `oai-nr-ue`
  - `oai-amf`
  - `oai-ausf`
  - `oai-udm`
  - `oai-udr`
- Ele mostra o estado e a saúde do contêiner MySQL e consulta a tabela `AuthenticationSubscription` para:
  - `001010000000001`
  - `imsi-001010000000001`
- Ele mostra dicas de próximos passos para `CONTEXT_NOT_FOUND`, para MySQL desatualizado ou não saudável e para problemas de sessão PDU, DNN ou slice.

Motivo:

- A falha original do teste rápido só mostrava o tempo esgotado do ping:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

- Essa mensagem esconde a diferença real entre:
  - falha de rádio ou de RRC;
  - falha de registro ou de autenticação no NAS;
  - falha na criação da sessão PDU;
  - falha de rota no plano de usuário.

- Neste caso, o lado de rádio funcionava, mas a autenticação NAS falhava. O caminho de falha deve levar o operador direto às evidências do UE, do AMF, do AUSF, do UDM, do UDR e do MySQL.

Validação:

- A validação da sintaxe do shell passou:

```bash
bash -n scripts/wait_ue_data_ready.sh scripts/preflight_check.sh oai-cn5g/healthscripts/mysql-healthcheck.sh
```

- O teste rápido manual bem-sucedido não passou pelo caminho do tempo esgotado. Esse é o resultado esperado depois da correção da carga inicial da base.
- A sintaxe dos comandos de diagnóstico foi revisada e corrigida antes da validação final.

### 10.6 Conferências de execução das ações atualizadas

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

- Nas ações iniciadas pelo painel, o backend precisa falar com o Docker do computador e ver o `/dev/net/tun`.
- São pré-requisitos de operação. Por isso, a interface e a API devem mostrá-los como conferências de execução.

Validação:

- A validação da fase 4 foi atualizada e passou:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
```

- Um teste do endpoint rodando confirmou as duas conferências como verdadeiras:

```text
'docker_socket': True
'tun_device': True
```

### 10.7 Validação manual do teste rápido F1 depois das correções

Comando executado:

```bash
docker stop oai-dashboard-backend || true
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true
./scripts/run_smoke_test.sh
```

Nota importante:

- Antes da execução, não havia contêineres do núcleo 5G nem da RAN, só os contêineres parados do painel. Por isso, o MySQL foi inicializado do zero a partir do `oai_db.sql` corrigido.
- Se já existir um contêiner MySQL desatualizado, talvez seja preciso recriá-lo para usar as mudanças do SQL:

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

Pasta da execução:

```text
results/runs/20260701_084915_f1_handover_smoke
```

Métricas do `summary.json`:

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

- O registro do UE deu certo.
- A `oaitun_ue1` apareceu dentro do `oai-nr-ue`, com o IP `10.0.0.2`.
- A espera pelo plano de usuário do UE passou.
- O teste rápido F1 passou da falha anterior e terminou com sucesso.
- O comando de handover F1 foi aceito.

### 10.8 Conjunto completo de validações executado depois das correções

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

Resultado da compilação do frontend:

```text
vite v6.4.3 building for production...
✓ built
```

Teste dos endpoints do painel com o arquivo de exemplo para ações:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build dashboard-backend
```

Endpoints conferidos:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
telnet_enabled= False
```

O backend do painel com as ações ligadas foi parado depois desta validação, para não ficar exposto.

### 10.9 Situação atual dos itens antes pendentes

| Item antes pendente | Situação atual |
|---|---|
| Desligar ou corrigir a consulta periódica pelo Telnet da CU | Feito. O padrão é desligado. Quando ligada, tem limite de frequência e guarda em cache a descoberta pelo `help`. |
| Conferir e corrigir a carga inicial de assinantes | Feito. Foram acrescentados os registros `imsi-` e a validação estática. |
| Diagnóstico de MySQL desatualizado ou não saudável | Melhorado. O health check valida os registros de autenticação do rfsim. O caminho do tempo esgotado mostra o diagnóstico do MySQL e do assinante. Contêineres antigos ainda podem precisar ser recriados de forma explícita. |
| Melhorar o diagnóstico da falta da `oaitun_ue1` | Feito no `wait_ue_data_ready.sh`. |
| Disponibilizar o `/dev/net/tun` às ações do painel | Feito no Compose base do painel. |
| Tratar a diferença de caminhos com o socket do Docker do computador | Documentado e suportado com o `dashboard/docker-compose.dashboard.host-actions.example.yml`. |
| Validar o teste rápido F1 de ponta a ponta | Concluído com sucesso na execução `20260701_084915_f1_handover_smoke`. |

### 10.10 Notas de operação que continuam valendo

- Se o MySQL já existir com uma carga antiga, editar o `oai_db.sql` não basta. Recrie o contêiner e o volume da base do núcleo 5G para reiniciar o laboratório:

```bash
./scripts/down.sh f1 --volumes
```

- Mantenha a consulta periódica pelo Telnet desligada, a menos que precise dela:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=false
```

- Nas ações iniciadas pelo painel, use o arquivo de exemplo para ações. Assim, as montagens do Compose da OAI usam caminhos que existem no computador:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- Quando esta seção foi escrita, o teste rápido manual bem-sucedido tinha deixado a pilha F1 da OAI rodando. Pare-a ao terminar com:

```bash
./scripts/down.sh f1
```

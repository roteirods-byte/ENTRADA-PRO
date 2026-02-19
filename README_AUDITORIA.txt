BLOCO AUDITORIA (ENTRADA-PRO) - TOP10

Objetivo
- Medir resultado real dos sinais do TOP10 (WIN/LOSS/EXPIRED) + PNL% real
- Gerar JSON pronto para visualização em audit.html (front não calcula)

Arquivos incluídos neste ZIP
- worker/engine/audit_top10.py        (motor)
- worker/worker_audit_top10.py        (loop 5 min)
- site/audit.html                     (painel)
- api/PATCH_server_js.txt             (patch mínimo de rota)

Arquivos gerados em runtime (no servidor)
- data/audit/top10_open.json
- data/audit/top10_closed.jsonl
- data/audit/top10_summary.json

Como instalar (resumo)
1) Copiar arquivos para o repo ENTRADA-PRO
2) Commit + push no GitHub
3) No servidor, pull do repo
4) systemd: entrada-pro-audit.service já aponta para worker/worker_audit_top10.py
5) Aplicar patch no api/server.js e restart do serviço entrada-pro-api
6) Abrir: https://trader-entrada.duckdns.org/audit.html

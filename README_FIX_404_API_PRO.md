PATCH R2 — Corrige 404 em /api/pro (Nginx pode estar removendo /api/ e virando /pro)

O que muda:
- Adiciona rotas compatíveis SEM /api:
  /pro, /top10, /audit
- Mantém as rotas oficiais existentes:
  /api/pro, /api/top10, /api/audit

Por que resolve:
- Seu console mostra GET /api/pro -> 404 e a resposta é "Cannot GET /pro".
  Isso indica que o Nginx está repassando /api/pro como /pro.
  Com este patch, /pro passa a devolver o mesmo JSON do /api/pro.

Como aplicar:
1) No seu repo ENTRADA-PRO, substitua o arquivo:
   api/server.js
   pelo arquivo deste patch.
2) Faça commit/push e rode seu deploy do projeto.

Como validar (no navegador):
- Abra: https://paineljorge.duckdns.org/full.html
- DevTools Console deve parar de mostrar 404 para /api/pro.
- A tabela deve carregar itens.

Como validar (curl):
- https://paineljorge.duckdns.org/api/health
- https://paineljorge.duckdns.org/api/pro  (deve virar JSON, não "Cannot GET /pro")

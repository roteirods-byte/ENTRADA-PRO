PATCH ENTRADA-PRO (R1) — conserto do 404 em /api/pro

O que corrige:
- Quando o NGINX faz proxy de /api/* -> /* (proxy_pass com barra final), /api/pro chega no Node como /pro.
- O Node tinha /api/pro, mas NÃO tinha /pro. Resultado: "Cannot GET /pro" e painel vazio (404).

Mudança mínima:
- Adiciona rotas de compatibilidade: /pro, /top10, /audit (sem alterar as rotas /api/* existentes).

Como aplicar (no repo ENTRADA-PRO):
1) Substituir o arquivo: api/server.js
2) Commit + deploy.

Validação:
- Abrir no navegador:
  https://paineljorge.duckdns.org/api/pro   (deve retornar JSON)
  https://paineljorge.duckdns.org/api/health (já funciona)
- No painel full.html: não pode ter erro 404 em api/pro no Console.

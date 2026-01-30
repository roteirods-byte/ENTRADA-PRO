Você escolheu manter o site oficial:

https://paineljorge.duckdns.org/full.html
https://paineljorge.duckdns.org/top10.html
https://paineljorge.duckdns.org/audit.html

Este pacote corrige:
1) Certificado errado (CN) no paineljorge.duckdns.org
2) Conflitos no nginx (server duplicado)
3) 502 por proxy para porta morta (8090)

Como aplicar:
1) Copie esta pasta para a VM (ou extraia o ZIP nela).
2) Rode: bash scripts/apply_fix.sh

Opcional:
- Use site/index.html como “3 orelhas” (abas).

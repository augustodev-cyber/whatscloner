#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

printf '\n[+] Verificando Python...\n'
python3 --version
printf '\n[+] Instalando dependencias Python...\n'
python3 -m pip install --break-system-packages --user --upgrade -r requirements.txt
printf '\n[+] Instalando Chromium do Playwright...\n'
python3 -m playwright install chromium
mkdir -p data
chmod +x run.sh
printf '\n[+] Instalacao concluida. Configure DEFAULT_SOURCE_URL no app.py e execute ./run.sh\n'

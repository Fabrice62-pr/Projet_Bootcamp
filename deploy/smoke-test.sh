#!/usr/bin/env bash
# Tests apres deploiement : chaque service repond, et refuse les appels non autorises.
# Lance par GitHub Actions apres chaque deploiement ; utilisable aussi a la main :
#   bash deploy/smoke-test.sh
set -uo pipefail

CORE_URL=${CORE_URL:-https://app-hospiplan-core.azurewebsites.net}
ENGINE_URL=${ENGINE_URL:-https://hospiplan-engine-anp6.swedencentral.cloudapp.azure.com}
NOTIF_URL=${NOTIF_URL:-https://func-hospiplan-notif.azurewebsites.net}
REPORT_URL=${REPORT_URL:-https://func-hospiplan-report.azurewebsites.net}

failures=0
body=$(mktemp)

# Attend qu'un service reponde le code attendu (demarrage a froid : jusqu'a 5 min).
wait_for() {
  local name=$1 url=$2 expect=$3 code=000
  for _ in $(seq 1 30); do
    code=$(curl -s -o "$body" -w '%{http_code}' --max-time 30 "$url")
    if [ "$code" = "$expect" ]; then echo "OK     $name (HTTP $code)"; return 0; fi
    sleep 10
  done
  echo "ECHEC  $name : HTTP $code, attendu $expect"; head -c 300 "$body"; echo
  failures=$((failures + 1))
}

# Verification unique (le service est deja reveille).
check() {
  local name=$1 expect=$2; shift 2
  local code
  code=$(curl -s -o "$body" -w '%{http_code}' --max-time 30 "$@")
  if [ "$code" = "$expect" ]; then echo "OK     $name (HTTP $code)"
  else echo "ECHEC  $name : HTTP $code, attendu $expect"; head -c 300 "$body"; echo; failures=$((failures + 1)); fi
}

echo "== Disponibilite"
wait_for "Core /health/ (base de donnees joignable)" "$CORE_URL/health/" 200
wait_for "Moteur /health (HTTPS)"                     "$ENGINE_URL/health" 200
wait_for "Notifications /api/health"                  "$NOTIF_URL/api/health" 200
wait_for "Reporting /api/health"                      "$REPORT_URL/api/health" 200

echo "== Securite"
check "Core : API reservee aux utilisateurs connectes" 403 "$CORE_URL/api/staff/"
check "Core : API interne reservee aux microservices"  403 "$CORE_URL/api/internal/planning-report/?week_start=2026-11-16"
check "Core : pages protegees par la connexion"        302 "$CORE_URL/planning/"
check "Moteur : cle API exigee"                         401 -X POST -H 'Content-Type: application/json' -d '{}' "$ENGINE_URL/v1/solve"
check "Notifications : cle API exigee"                  401 "$NOTIF_URL/api/notifications"
check "Reporting : cle API exigee"                      401 "$REPORT_URL/api/reports/planning"

rm -f "$body"
if [ "$failures" -gt 0 ]; then echo "$failures verification(s) en echec."; exit 1; fi
echo "Tous les services sont operationnels."

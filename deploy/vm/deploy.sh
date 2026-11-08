#!/usr/bin/env bash
# Deploiement du moteur de planning sur la VM.
#
# Installe en /opt/hospiplan/deploy.sh. C'est la SEULE commande que la cle SSH
# de GitHub Actions peut executer (option command= de authorized_keys) : pas de
# shell, pas de tunnel. GitHub envoie uniquement le SHA du commit a deployer.
#
# Usage manuel (cle admin) : /opt/hospiplan/deploy.sh <sha-du-commit>
set -euo pipefail

REPO=https://github.com/Fabrice62-pr/Projet_Bootcamp.git
BASE=/opt/hospiplan

SHA="${SSH_ORIGINAL_COMMAND:-${1:-}}"
if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Refuse : un SHA de commit complet (40 caracteres hexadecimaux) est attendu." >&2
  exit 2
fi

# Un seul deploiement a la fois.
exec 9>"$BASE/deploy.lock"
flock -n 9 || { echo "Un deploiement est deja en cours." >&2; exit 3; }

if [ ! -d "$BASE/src/.git" ]; then
  git clone --quiet "$REPO" "$BASE/src"
fi
cd "$BASE/src"
git fetch --quiet origin "$SHA"
git checkout --quiet --force "$SHA"

cd deploy/vm
docker compose --env-file "$BASE/.env" up -d --build --remove-orphans
docker image prune -f >/dev/null

echo "Moteur deploye : $SHA"

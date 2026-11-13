#!/usr/bin/env bash
# Laboratorio Moodle local para el sistema de alerta temprana (adaptado de SEGTI-Edu).
# Todas las órdenes son idempotentes: `up` deja Moodle arrancado, instalado y configurado.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
RUNTIME="${REPO_ROOT}/.runtime"
MOODLE_DIR="${RUNTIME}/moodle"
DOCKER_DIR="${RUNTIME}/moodle-docker"
GENERATED="${RUNTIME}/generated"
source "${REPO_ROOT}/infra/moodle/versions.env"
ENV_FILE="${REPO_ROOT}/.env.local"
if [[ ! -f "${ENV_FILE}" ]]; then cp "${REPO_ROOT}/.env.local.example" "${ENV_FILE}"; chmod 600 "${ENV_FILE}"; fi
set -a; source "${ENV_FILE}"; set +a

export COMPOSE_PROJECT_NAME=alerta_moodle
export MOODLE_DOCKER_WWWROOT="${MOODLE_DIR}"
export MOODLE_DOCKER_DB="${DB_TYPE}"
export MOODLE_DOCKER_DB_VERSION="${DB_VERSION}"
export MOODLE_DOCKER_PHP_VERSION="${PHP_VERSION}"
export MOODLE_DOCKER_BROWSER=chrome MOODLE_DOCKER_BROWSER_NAME=chrome MOODLE_DOCKER_BROWSER_TAG=4
export MOODLE_DOCKER_TIMEOUT_FACTOR=1
export MOODLE_DOCKER_WEB_HOST=localhost
export MOODLE_DOCKER_WEB_PORT="${MOODLE_WEB_PORT}"
export MOODLE_WEB_PORT_NUMBER="${MOODLE_WEB_PORT##*:}"
export MOODLE_DOCKER_DB_PORT="${MOODLE_DB_PORT}"
export MOODLE_ADMINER_PORT
export ALERTA_REPO_ROOT="${REPO_ROOT}"
export ALERTA_PYTHON_VERSION="${PYTHON_VERSION}"
export ASSETDIR="${DOCKER_DIR}/assets"
MOODLE_URL="http://localhost:${MOODLE_WEB_PORT_NUMBER}"

compose() {
  docker compose \
    -f "${DOCKER_DIR}/base.yml" \
    -f "${DOCKER_DIR}/service.mail.yml" \
    -f "${DOCKER_DIR}/db.pgsql.yml" \
    -f "${DOCKER_DIR}/db.pgsql.port.yml" \
    -f "${DOCKER_DIR}/webserver.port.yml" \
    -f "${REPO_ROOT}/infra/moodle/compose/local.yml" "$@"
}
php_cli() { compose exec -T webserver php "$@"; }
require_command() { command -v "$1" >/dev/null || { echo "ERROR: se requiere $1" >&2; exit 1; }; }

checkout_exact() {
  local dir="$1" remote="$2" commit="$3"
  if [[ ! -d "${dir}/.git" ]]; then
    mkdir -p "${dir}"; git -C "${dir}" init -q; git -C "${dir}" remote add origin "${remote}"
    git -C "${dir}" config remote.origin.promisor true
    git -C "${dir}" config remote.origin.partialclonefilter blob:none
  fi
  git -C "${dir}" config core.fileMode false  # la partición no guarda permisos
  if ! git -C "${dir}" cat-file -e "${commit}^{commit}" 2>/dev/null; then
    git -C "${dir}" -c http.lowSpeedLimit=1 -c http.lowSpeedTime=600 fetch --depth=1 --filter=blob:none origin "${commit}"
  fi
  [[ "$(git -C "${dir}" rev-parse HEAD 2>/dev/null)" == "${commit}" ]] || git -C "${dir}" checkout -q --detach "${commit}"
  [[ "$(git -C "${dir}" rev-parse HEAD)" == "${commit}" ]] || { echo "ERROR: commit incorrecto en ${dir}" >&2; exit 1; }
}

bootstrap() {
  require_command docker; require_command git; docker compose version >/dev/null
  mkdir -p "${GENERATED}"
  checkout_exact "${MOODLE_DIR}" https://github.com/moodle/moodle.git "${MOODLE_COMMIT}"
  checkout_exact "${DOCKER_DIR}" https://github.com/moodlehq/moodle-docker.git "${MOODLE_DOCKER_COMMIT}"
  cp "${DOCKER_DIR}/config.docker-template.php" "${MOODLE_DIR}/config.php"
  ln -sfn ../config.php "${MOODLE_DIR}/public/config.php"
  echo "Código listo: Moodle ${MOODLE_BRANCH} (${MOODLE_COMMIT:0:10})."
}

is_installed() {
  compose exec -T db psql -U moodle -d moodle -tAc "select to_regclass('public.m_config') is not null" 2>/dev/null | grep -q t
}

install_lab() {
  if is_installed; then echo "Moodle ya está instalado."; else
    php_cli admin/cli/install_database.php --agree-license \
      --fullname="Alerta temprana · Moodle de desarrollo" --shortname=ALERTA-MOODLE \
      --adminuser="${MOODLE_ADMIN_USER}" --adminpass="${MOODLE_ADMIN_PASSWORD}" \
      --adminemail="${MOODLE_ADMIN_EMAIL}" --lang="${MOODLE_LANG:-es}"
  fi
  for setting in "timezone=${MOODLE_TIMEZONE:-America/Havana}" enablecompletion=1 enablewebservices=1 \
                 webserviceprotocols=rest; do
    php_cli admin/cli/cfg.php --name="${setting%%=*}" --set="${setting#*=}"
  done
  # Sin mensajes de bienvenida al matricular: los cursos de prueba matriculan a cientos de estudiantes
  php_cli admin/cli/cfg.php --component=enrol_manual --name=sendcoursewelcomemessage --set=0
  php_cli admin/cli/upgrade.php --non-interactive >/dev/null  # instala plugins nuevos del repo, si los hay
  install_langpack "${MOODLE_LANG:-es}"
}

install_langpack() {
  # download.moodle.org puede no ser accesible (403 desde Cuba): si hay una copia en
  # .runtime/langpacks/<idioma> se copia a moodledata; si no, langpack.php intenta descargarla.
  local lang="$1" cache="${RUNTIME}/langpacks/$1"
  if [[ "${lang}" != en && -d "${cache}" ]]; then
    compose exec -T webserver mkdir -p /var/www/moodledata/lang
    compose cp "${cache}" webserver:/var/www/moodledata/lang/
    compose exec -T webserver chown -R www-data:www-data "/var/www/moodledata/lang/${lang}"
  fi
  php_cli /opt/alerta/langpack.php "${lang}"
}

configure() {
  php_cli /opt/alerta/configure.php
}

check() {
  local token
  token="$(sed -n 's/^MOODLE_TOKEN=//p' "${GENERATED}/rest.env")"
  curl -fsS "${MOODLE_URL}/webservice/rest/server.php" -d wstoken="${token}" \
    -d wsfunction=core_webservice_get_site_info -d moodlewsrestformat=json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'userid' in d, d; print(f\"WS REST: {d['username']} (id {d['userid']}), {len(d['functions'])} funciones, Moodle {d['release']}\")"
}

up() {
  bootstrap
  compose up -d --wait
  install_lab
  configure
  check
  echo "Moodle listo en ${MOODLE_URL} (admin: ${MOODLE_ADMIN_USER}). Credenciales del WS: .runtime/generated/rest.env"
}

reset_lab() {
  [[ "${MOODLE_RESET_CONFIRM:-}" == YES ]] || { echo "Borra la base de datos y moodledata. Use MOODLE_RESET_CONFIRM=YES" >&2; exit 2; }
  compose down --volumes --remove-orphans
}

case "${1:-}" in
  bootstrap) bootstrap ;;
  up) up ;;
  install) install_lab ;;
  configure) configure ;;
  check) check ;;
  status) compose ps ;;
  audit) php_cli /opt/alerta/audit.php > "${GENERATED}/moodle-runtime.json"; echo "${GENERATED}/moodle-runtime.json" ;;
  logs) compose logs -f --tail=200 ;;
  shell) compose exec webserver bash ;;
  php) shift; php_cli "$@" ;;
  down) compose down ;;
  reset) reset_lab ;;
  *) echo "Uso: $0 {up|down|status|check|configure|install|bootstrap|audit|logs|shell|php ARGS|reset}" >&2; exit 2 ;;
esac

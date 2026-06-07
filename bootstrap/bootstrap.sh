#!/bin/sh
set -eu

fail() {
  echo "[eona-mcp bootstrap] ERROR: $*" >&2
  exit 1
}

log() {
  printf '[eona-mcp bootstrap] %s\n' "$*" >&2
}

human_color() {
  code="$1"
  if [ -t 2 ] && [ -z "${NO_COLOR:-}" ]; then
    printf '\033[%sm' "$code"
  fi
}

human_section() {
  printf '\n[%s]\n\n' "$1" >&2
}

human_pending() {
  printf '%s...\n' "$1" >&2
}

human_done() {
  label="$1"
  status="${2:-done}"
  printf '%s... %s%s%s\n' "$label" "$(human_color 32)" "$status" "$(human_color 0)" >&2
}

display_path() {
  path="$1"
  case "$path" in
    "$HOME") printf '~\n' ;;
    "$HOME"/*) printf '~/%s\n' "${path#"$HOME"/}" ;;
    *) printf '%s\n' "$path" ;;
  esac
}

usage() {
  cat >&2 <<'EOF'
Usage: bootstrap.sh [options]

Installs the EONA MCP surface and provisions the sibling sealed EONA CLI runtime.

Options:
  --family-root DIR        EONA family root. Defaults to ~/.eona.
  --install-dir DIR        MCP install root. Defaults to <family-root>/eona-mcp.
  --cli-install-dir DIR    CLI install root. Defaults to <family-root>/eona-cli.
  --workspace-dir DIR      Shared workspace. Defaults to <family-root>/workspace.
  --project-id ID          MCP project id. Defaults to EONA_PROJECT_ID or my-photos.
  --session-id ID          MCP session id. Defaults to EONA_SESSION_ID or default_session.
  --sources-json JSON      Source paths JSON array. Defaults to EONA_SOURCES_JSON or [].
  --project-description TEXT
                           Optional MCP project description.
  --source-root DIR        Install MCP files from this source root instead of
                           auto-detecting or downloading a release archive.
  --mcp-archive-url URL    MCP release archive URL for stdin bootstrap mode.
  --cli-bootstrap-url URL  CLI bootstrap URL. Defaults to https://cli.eona.dev/bootstrap.sh.
  --cli-version VERSION    Pass a specific CLI version to the CLI bootstrap.
  --cli-artifact-url URL   Pass a CLI artifact base URL to the CLI bootstrap.
  --repair-cli             Run the CLI bootstrap even when bin/eona already exists.
  --allow-cli-downgrade    Allow repair to replace a newer local CLI with the
                           requested bootstrap version.
  --skip-cli               Install only the MCP surface.
  -h, --help               Show this help.
EOF
}

shell_quote() {
  printf "'"
  printf '%s' "$1" | sed "s/'/'\\\\''/g"
  printf "'\n"
}

json_field() {
  json_path="$1"
  field="$2"
  perl -MJSON::PP - "$json_path" "$field" <<'PERL'
my ($path, $field) = @ARGV;
open my $fh, '<', $path or exit 1;
my $raw = do { local $/; <$fh> };
close $fh;
my $payload = eval { JSON::PP::decode_json($raw) } or exit 1;
my @parts = split /\./, $field;
my $value = $payload;
for my $part (@parts) {
    exit 1 unless ref($value) eq 'HASH' && exists $value->{$part};
    $value = $value->{$part};
}
exit 1 if ref($value) || !defined($value);
print $value;
PERL
}

download() {
  url="$1"
  output="$2"
  command -v curl >/dev/null 2>&1 || fail "curl is required to download $url"
  curl -fL --retry 3 --retry-delay 1 -o "$output" "$url"
}

source_root_valid() {
  source_root="$1"
  [ -f "${source_root}/pyproject.toml" ] && [ -d "${source_root}/src/eona_mcp" ]
}

detect_script_source_root() {
  script_path="$0"
  [ -n "$script_path" ] && [ "$script_path" != "sh" ] && [ "$script_path" != "bash" ] && [ "$script_path" != "-" ] || return 1
  [ -f "$script_path" ] || return 1
  script_dir="$(cd "$(dirname "$script_path")" && pwd)"
  candidate="$(cd "${script_dir}/.." && pwd)"
  source_root_valid "$candidate" || return 1
  printf '%s\n' "$candidate"
}

download_mcp_source_root() {
  archive_url="$1"
  cache_dir="$2"
  [ -n "$archive_url" ] || fail "stdin bootstrap requires --mcp-archive-url or EONA_MCP_ARCHIVE_URL"
  command -v tar >/dev/null 2>&1 || fail "tar is required to extract MCP archive"
  mkdir -p "$cache_dir" || fail "could not create MCP bootstrap cache: $cache_dir"
  archive_path="${cache_dir}/eona-mcp-bootstrap.tar.gz"
  staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/eona-mcp-bootstrap.XXXXXX")" || fail "could not create MCP bootstrap staging directory"
  human_pending "archive downloading"
  download "$archive_url" "$archive_path" || fail "could not download MCP archive: $archive_url"
  human_done "archive downloading"
  human_pending "extracting"
  tar -xzf "$archive_path" -C "$staging_dir" || fail "could not extract MCP archive: $archive_path"
  human_done "extracting"
  candidate="$(find "$staging_dir" -maxdepth 2 -type f -name pyproject.toml -print | head -n 1)"
  [ -n "$candidate" ] || fail "MCP archive did not contain pyproject.toml"
  candidate="$(cd "$(dirname "$candidate")" && pwd)"
  source_root_valid "$candidate" || fail "MCP archive did not contain src/eona_mcp"
  printf '%s\n' "$candidate"
}

copy_path() {
  source_root="$1"
  install_dir="$2"
  relpath="$3"
  [ -e "${source_root}/${relpath}" ] || return 0
  rm -rf "${install_dir}/${relpath}"
  mkdir -p "$(dirname "${install_dir}/${relpath}")"
  cp -a "${source_root}/${relpath}" "${install_dir}/${relpath}"
}

install_mcp_surface() {
  source_root="$1"
  install_dir="$2"
  [ -f "${source_root}/pyproject.toml" ] || fail "source root missing pyproject.toml: ${source_root}"
  [ -d "${source_root}/src/eona_mcp" ] || fail "source root missing src/eona_mcp: ${source_root}"

  mkdir -p "$install_dir"
  for relpath in \
    agent \
    bin \
    contracts \
    src \
    LICENSE \
    README.md \
    pyproject.toml; do
    copy_path "$source_root" "$install_dir" "$relpath"
  done
  printf 'eona-mcp\n' >"${install_dir}/.eona-mcp-product"
}

write_env_file() {
  install_dir="$1"
  family_root="$2"
  cli_install_dir="$3"
  workspace_dir="$4"
  project_id="$5"
  session_id="$6"
  sources_json="$7"
  project_description="$8"
  env_file="${install_dir}/eona-mcp.env"

  cat >"$env_file" <<EOF
# Generated by EONA MCP bootstrap.
export EONA_FAMILY_ROOT=$(shell_quote "$family_root")
export EONA_MCP_INSTALL_ROOT=$(shell_quote "$install_dir")
export EONA_CLI_INSTALL_ROOT=$(shell_quote "$cli_install_dir")
export EONA_MCP_WORKSPACE=$(shell_quote "$workspace_dir")
export EONA_CLI=$(shell_quote "${cli_install_dir%/}/bin/eona")

# Project defaults for stdio/http MCP launches.
if [ -z "\${EONA_PROJECT_ID:-}" ]; then export EONA_PROJECT_ID=$(shell_quote "$project_id"); fi
if [ -z "\${EONA_SESSION_ID:-}" ]; then export EONA_SESSION_ID=$(shell_quote "$session_id"); fi
if [ -z "\${EONA_SOURCES_JSON:-}" ]; then export EONA_SOURCES_JSON=$(shell_quote "$sources_json"); fi
EOF
  if [ -n "$project_description" ]; then
    printf 'if [ -z "${EONA_PROJECT_DESCRIPTION:-}" ]; then export EONA_PROJECT_DESCRIPTION=%s; fi\n' "$(shell_quote "$project_description")" >>"$env_file"
  fi
}

write_stdio_launcher() {
  install_dir="$1"
  launcher_path="${install_dir}/eona-mcp-stdio.sh"

  cat >"$launcher_path" <<EOF
#!/bin/sh
set -eu
exec $(shell_quote "${install_dir%/}/bin/eona-mcp") "\$@"
EOF
  chmod +x "$launcher_path"
}

prepare_mcp_project() {
  install_dir="$1"
  family_root="$2"
  cli_install_dir="$3"
  workspace_dir="$4"
  project_id="$5"
  session_id="$6"
  sources_json="$7"
  project_description="$8"

  command -v python3 >/dev/null 2>&1 || fail "python3 is required to prepare the MCP project"
  if should_prepare_sources "$sources_json"; then
    log "Preparing MCP project ${project_id}/${session_id}"
  else
    log "Inspecting MCP project ${project_id}/${session_id}"
  fi
  EONA_FAMILY_ROOT="$family_root" \
  EONA_MCP_INSTALL_ROOT="$install_dir" \
  EONA_CLI_INSTALL_ROOT="$cli_install_dir" \
  EONA_MCP_WORKSPACE="$workspace_dir" \
  EONA_CLI="${cli_install_dir%/}/bin/eona" \
  EONA_PROJECT_ID="$project_id" \
  EONA_SESSION_ID="$session_id" \
  EONA_SOURCES_JSON="$sources_json" \
  EONA_PROJECT_DESCRIPTION="$project_description" \
  PYTHONPATH="${install_dir}/src${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m eona_mcp.start_project --prepare-only --marker-dir "${workspace_dir}/.eona-mcp-prepare"
}

print_install_section() {
  install_dir="$1"
  cli_executable="$2"
  launcher_path="$3"
  cyan="$(human_color 36)"
  reset="$(human_color 0)"

  human_section "INSTALL"
  printf 'path %s%s%s\n' "$cyan" "$(display_path "$install_dir")" "$reset" >&2
  printf 'eona-cli %s%s%s\n' "$cyan" "$(display_path "$cli_executable")" "$reset" >&2
  printf 'stdio %s%s%s\n' "$cyan" "$(display_path "$launcher_path")" "$reset" >&2
}

should_prepare_sources() {
  sources_json="$1"
  python3 -c 'import json,sys; payload=json.loads(sys.argv[1]); sys.exit(0 if isinstance(payload, list) and len(payload) > 0 else 1)' "$sources_json"
}

provision_cli() {
  cli_install_dir="$1"
  cli_bootstrap_url="$2"
  cli_version="$3"
  cli_artifact_url="$4"

  command -v curl >/dev/null 2>&1 || fail "curl is required to provision eona-cli"
  cli_bootstrap_path="$(mktemp "${TMPDIR:-/tmp}/eona-cli-bootstrap.XXXXXX")" || fail "could not create CLI bootstrap temp file"
  download "$cli_bootstrap_url" "$cli_bootstrap_path" || fail "could not download CLI bootstrap: $cli_bootstrap_url"
  set -- --no-copy "$cli_install_dir"
  if [ -n "$cli_artifact_url" ]; then
    set -- --artifact-url "$cli_artifact_url" "$@"
  fi
  if [ -n "$cli_version" ]; then
    set -- --version "$cli_version" "$@"
  fi
  sh "$cli_bootstrap_path" "$@"
}

cli_version() {
  executable="$1"
  "$executable" --version 2>/dev/null | awk '{print $NF}' | head -n 1
}

version_gt() {
  left="$1"
  right="$2"
  [ -n "$left" ] && [ -n "$right" ] || return 1
  awk -v left="$left" -v right="$right" '
    function normalize(value) {
      sub(/^[^0-9]*/, "", value)
      sub(/[^0-9.].*$/, "", value)
      return value
    }
    BEGIN {
      left = normalize(left)
      right = normalize(right)
      split(left, l, ".")
      split(right, r, ".")
      for (i = 1; i <= 4; i++) {
        lv = (l[i] == "" ? 0 : l[i]) + 0
        rv = (r[i] == "" ? 0 : r[i]) + 0
        if (lv > rv) exit 0
        if (lv < rv) exit 1
      }
      exit 1
    }
  '
}

version_lt() {
  local left="$1"
  local right="$2"
  version_gt "$right" "$left"
}

guard_cli_repair_version() {
  executable="$1"
  target_version="$2"
  allow_downgrade="$3"
  [ -x "$executable" ] || return 0
  [ "$allow_downgrade" -eq 0 ] || return 0

  current_version="$(cli_version "$executable")"
  if version_gt "$current_version" "$target_version"; then
    fail "refusing to replace newer eona-cli ${current_version} with bootstrap target ${target_version}; pass --allow-cli-downgrade to override"
  fi
}

cli_needs_upgrade() {
  executable="$1"
  min_version="$2"
  [ -x "$executable" ] || return 0

  current_version="$(cli_version "$executable")"
  [ -n "$current_version" ] || return 0
  version_lt "$current_version" "$min_version"
}

EONA_MCP_PRODUCTION_VERSION="0.0.15"
CLI_MIN_VERSION="0.1.1"
DEFAULT_CLI_BOOTSTRAP_VERSION="0.1.1"
SOURCE_ROOT="${EONA_MCP_SOURCE_ROOT:-}"
MCP_ARTIFACT_URL="${EONA_MCP_ARTIFACT_URL:-https://mcp.eona.dev}"
MCP_ARCHIVE_URL="${EONA_MCP_ARCHIVE_URL:-}"
BOOTSTRAP_CACHE="${EONA_MCP_BOOTSTRAP_CACHE:-${HOME}/.cache/eona-mcp}"
FAMILY_ROOT="${EONA_FAMILY_ROOT:-${HOME}/.eona}"
MCP_INSTALL_DIR="${EONA_MCP_INSTALL_ROOT:-}"
CLI_INSTALL_DIR="${EONA_CLI_INSTALL_ROOT:-}"
WORKSPACE_DIR="${EONA_MCP_WORKSPACE:-}"
CLI_BOOTSTRAP_URL="${EONA_CLI_BOOTSTRAP_URL:-https://cli.eona.dev/bootstrap.sh}"
CLI_VERSION=""
CLI_ARTIFACT_URL="${EONA_CLI_ARTIFACT_URL:-}"
PROJECT_ID="${EONA_PROJECT_ID:-my-photos}"
SESSION_ID="${EONA_SESSION_ID:-default_session}"
SOURCES_JSON="${EONA_SOURCES_JSON:-[]}"
PROJECT_DESCRIPTION="${EONA_PROJECT_DESCRIPTION:-}"
REPAIR_CLI=0
ALLOW_CLI_DOWNGRADE=0
SKIP_CLI=0

while [ $# -gt 0 ]; do
  case "$1" in
    --family-root)
      [ $# -ge 2 ] || fail "missing value for --family-root"
      FAMILY_ROOT="$2"
      shift 2
      ;;
    --install-dir|--mcp-install-dir)
      [ $# -ge 2 ] || fail "missing value for $1"
      MCP_INSTALL_DIR="$2"
      shift 2
      ;;
    --cli-install-dir)
      [ $# -ge 2 ] || fail "missing value for --cli-install-dir"
      CLI_INSTALL_DIR="$2"
      shift 2
      ;;
    --workspace-dir)
      [ $# -ge 2 ] || fail "missing value for --workspace-dir"
      WORKSPACE_DIR="$2"
      shift 2
      ;;
    --project-id)
      [ $# -ge 2 ] || fail "missing value for --project-id"
      PROJECT_ID="$2"
      shift 2
      ;;
    --session-id)
      [ $# -ge 2 ] || fail "missing value for --session-id"
      SESSION_ID="$2"
      shift 2
      ;;
    --sources-json)
      [ $# -ge 2 ] || fail "missing value for --sources-json"
      SOURCES_JSON="$2"
      shift 2
      ;;
    --project-description)
      [ $# -ge 2 ] || fail "missing value for --project-description"
      PROJECT_DESCRIPTION="$2"
      shift 2
      ;;
    --source-root)
      [ $# -ge 2 ] || fail "missing value for --source-root"
      SOURCE_ROOT="$2"
      shift 2
      ;;
    --mcp-archive-url)
      [ $# -ge 2 ] || fail "missing value for --mcp-archive-url"
      MCP_ARCHIVE_URL="$2"
      shift 2
      ;;
    --cli-bootstrap-url)
      [ $# -ge 2 ] || fail "missing value for --cli-bootstrap-url"
      CLI_BOOTSTRAP_URL="$2"
      shift 2
      ;;
    --cli-version)
      [ $# -ge 2 ] || fail "missing value for --cli-version"
      CLI_VERSION="$2"
      shift 2
      ;;
    --cli-artifact-url)
      [ $# -ge 2 ] || fail "missing value for --cli-artifact-url"
      CLI_ARTIFACT_URL="$2"
      shift 2
      ;;
    --repair-cli)
      REPAIR_CLI=1
      shift
      ;;
    --allow-cli-downgrade)
      ALLOW_CLI_DOWNGRADE=1
      shift
      ;;
    --skip-cli)
      SKIP_CLI=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      fail "unsupported option: $1"
      ;;
    *)
      fail "unexpected argument: $1"
      ;;
  esac
done

human_section "DOWNLOAD"
if [ -n "$SOURCE_ROOT" ]; then
  human_pending "source root checking"
  SOURCE_ROOT="$(cd "$SOURCE_ROOT" && pwd)"
  source_root_valid "$SOURCE_ROOT" || fail "invalid MCP source root: $SOURCE_ROOT"
  human_done "source root checking"
else
  human_pending "source root checking"
  if SOURCE_ROOT="$(detect_script_source_root)"; then
    human_done "source root checking"
  else
    human_done "source root checking" "not found"
    MCP_ARCHIVE_URL="${MCP_ARCHIVE_URL:-${MCP_ARTIFACT_URL%/}/releases/${EONA_MCP_PRODUCTION_VERSION}/eona-mcp/eona-mcp-${EONA_MCP_PRODUCTION_VERSION}.tar.gz}"
    SOURCE_ROOT="$(download_mcp_source_root "$MCP_ARCHIVE_URL" "$BOOTSTRAP_CACHE")"
  fi
fi

CLI_DEPENDENCY_CONTRACT="${SOURCE_ROOT}/contracts/eona-cli-dependency.json"
if [ -f "$CLI_DEPENDENCY_CONTRACT" ]; then
  CLI_MIN_VERSION="$(json_field "$CLI_DEPENDENCY_CONTRACT" compatibility.min_version)" || fail "dependency contract missing compatibility.min_version"
fi
CLI_BOOTSTRAP_CONTRACT="${SOURCE_ROOT}/contracts/eona-cli-bootstrap.json"
if [ -f "$CLI_BOOTSTRAP_CONTRACT" ]; then
  DEFAULT_CLI_BOOTSTRAP_VERSION="$(json_field "$CLI_BOOTSTRAP_CONTRACT" version)" || fail "bootstrap contract missing version"
fi
CLI_VERSION="${CLI_VERSION:-${EONA_CLI_BOOTSTRAP_VERSION:-$DEFAULT_CLI_BOOTSTRAP_VERSION}}"

FAMILY_ROOT="$(mkdir -p "$FAMILY_ROOT" && cd "$FAMILY_ROOT" && pwd -P)"
MCP_INSTALL_DIR="${MCP_INSTALL_DIR:-${FAMILY_ROOT}/eona-mcp}"
CLI_INSTALL_DIR="${CLI_INSTALL_DIR:-${FAMILY_ROOT}/eona-cli}"
WORKSPACE_DIR="${WORKSPACE_DIR:-${FAMILY_ROOT}/workspace}"

mkdir -p "$WORKSPACE_DIR"
WORKSPACE_DIR="$(cd "$WORKSPACE_DIR" && pwd -P)"
mkdir -p "$(dirname "$MCP_INSTALL_DIR")" "$(dirname "$CLI_INSTALL_DIR")"

install_mcp_surface "$SOURCE_ROOT" "$MCP_INSTALL_DIR"
MCP_INSTALL_DIR="$(cd "$MCP_INSTALL_DIR" && pwd -P)"
write_env_file "$MCP_INSTALL_DIR" "$FAMILY_ROOT" "$CLI_INSTALL_DIR" "$WORKSPACE_DIR" "$PROJECT_ID" "$SESSION_ID" "$SOURCES_JSON" "$PROJECT_DESCRIPTION"
write_stdio_launcher "$MCP_INSTALL_DIR"

CLI_EXECUTABLE="${CLI_INSTALL_DIR%/}/bin/eona"

if [ "$SKIP_CLI" -eq 1 ]; then
  log "Skipped eona-cli provisioning"
elif [ -x "$CLI_EXECUTABLE" ] && [ "$REPAIR_CLI" -ne 1 ] && ! cli_needs_upgrade "$CLI_EXECUTABLE" "$CLI_MIN_VERSION"; then
  log "Using existing eona-cli at ${CLI_EXECUTABLE}"
else
  log "Provisioning eona-cli into ${CLI_INSTALL_DIR}"
  guard_cli_repair_version "$CLI_EXECUTABLE" "$CLI_VERSION" "$ALLOW_CLI_DOWNGRADE"
  provision_cli "$CLI_INSTALL_DIR" "$CLI_BOOTSTRAP_URL" "$CLI_VERSION" "$CLI_ARTIFACT_URL"
fi

print_install_section "$MCP_INSTALL_DIR" "$CLI_EXECUTABLE" "${MCP_INSTALL_DIR}/eona-mcp-stdio.sh"

if should_prepare_sources "$SOURCES_JSON"; then
  prepare_mcp_project "$MCP_INSTALL_DIR" "$FAMILY_ROOT" "$CLI_INSTALL_DIR" "$WORKSPACE_DIR" "$PROJECT_ID" "$SESSION_ID" "$SOURCES_JSON" "$PROJECT_DESCRIPTION"
else
  prepare_mcp_project "$MCP_INSTALL_DIR" "$FAMILY_ROOT" "$CLI_INSTALL_DIR" "$WORKSPACE_DIR" "$PROJECT_ID" "$SESSION_ID" "$SOURCES_JSON" "$PROJECT_DESCRIPTION"
fi

log "Installed EONA MCP to ${MCP_INSTALL_DIR}"
log "Workspace: ${WORKSPACE_DIR}"
log "Project: ${PROJECT_ID}/${SESSION_ID}"
log "Stdio MCP command: ${MCP_INSTALL_DIR}/eona-mcp-stdio.sh"
printf '\n%sbootstrap succeeded%s\n' "$(human_color 32)" "$(human_color 0)" >&2
printf 'For more details about EONA MCP, please read README.md.\n' >&2

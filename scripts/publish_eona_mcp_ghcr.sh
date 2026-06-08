#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[publish-eona-mcp-ghcr] ERROR: $*" >&2
  exit 1
}

log() {
  echo "[publish-eona-mcp-ghcr] $*" >&2
}

usage() {
  cat >&2 <<'EOF'
Usage: publish_eona_mcp_ghcr.sh [options]

Builds and publishes the EONA MCP Docker image to GHCR.

By default this pushes:
  ghcr.io/eona-dev/eona-mcp:<VERSION>

Options:
  --image IMAGE          GHCR image name without tag.
                         Defaults to ghcr.io/eona-dev/eona-mcp.
  --version VERSION      Image version tag. Defaults to VERSION file.
  --platform PLATFORM    Docker platform. Defaults to linux/arm64.
  --latest              Also publish/update the :latest tag.
  --force-bundles        Rebuild release bundles even when expected archives exist.
  --cli-archive PATH     Forward an existing EONA CLI Linux archive to the builder.
  --mcp-archive PATH     Forward an existing EONA MCP archive to the builder.
  --build-script PATH    Docker build script. Defaults to ../scripts/build_eona_mcp_docker.sh
                         relative to the parent project directory.
  --dry-run              Print the publish commands without running them.
  -h, --help             Show this help.

Environment:
  EONA_MCP_GHCR_IMAGE
  EONA_MCP_DOCKER_PLATFORM
  EONA_MCP_DOCKER_BUILD_SCRIPT
  EONA_CLI_RELEASE_ARCHIVE
  EONA_MCP_RELEASE_ARCHIVE
EOF
}

normalize_version() {
  local value="$1"
  value="${value#v}"
  if [[ ! "${value}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    fail "invalid semantic version: $1"
  fi
  printf '%s\n' "${value}"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required"
}

run() {
  log "+ $*"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    "$@"
  fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTER_REPO_DIR="$(cd "${MCP_REPO_DIR}/.." && pwd)"

IMAGE="${EONA_MCP_GHCR_IMAGE:-ghcr.io/eona-dev/eona-mcp}"
PLATFORM="${EONA_MCP_DOCKER_PLATFORM:-linux/arm64}"
BUILD_SCRIPT="${EONA_MCP_DOCKER_BUILD_SCRIPT:-${OUTER_REPO_DIR}/scripts/build_eona_mcp_docker.sh}"
VERSION=""
LATEST=0
FORCE_BUNDLES=0
DRY_RUN=0
CLI_ARCHIVE="${EONA_CLI_RELEASE_ARCHIVE:-}"
MCP_ARCHIVE="${EONA_MCP_RELEASE_ARCHIVE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      [[ $# -ge 2 ]] || fail "missing value for --image"
      IMAGE="${2%:}"
      shift 2
      ;;
    --version)
      [[ $# -ge 2 ]] || fail "missing value for --version"
      VERSION="$(normalize_version "$2")"
      shift 2
      ;;
    --platform)
      [[ $# -ge 2 ]] || fail "missing value for --platform"
      PLATFORM="$2"
      shift 2
      ;;
    --latest)
      LATEST=1
      shift
      ;;
    --force-bundles)
      FORCE_BUNDLES=1
      shift
      ;;
    --cli-archive)
      [[ $# -ge 2 ]] || fail "missing value for --cli-archive"
      CLI_ARCHIVE="$2"
      shift 2
      ;;
    --mcp-archive)
      [[ $# -ge 2 ]] || fail "missing value for --mcp-archive"
      MCP_ARCHIVE="$2"
      shift 2
      ;;
    --build-script)
      [[ $# -ge 2 ]] || fail "missing value for --build-script"
      BUILD_SCRIPT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      fail "unsupported option: $1"
      ;;
    *)
      fail "unexpected argument: $1"
      ;;
  esac
done

[[ -f "${MCP_REPO_DIR}/VERSION" ]] || fail "missing VERSION file: ${MCP_REPO_DIR}/VERSION"
VERSION="${VERSION:-$(normalize_version "$(tr -d '[:space:]' < "${MCP_REPO_DIR}/VERSION")")}"
[[ -x "${BUILD_SCRIPT}" ]] || fail "build script is not executable: ${BUILD_SCRIPT}"
[[ "${IMAGE}" == ghcr.io/* ]] || fail "--image must point at ghcr.io"
[[ "${IMAGE}" != *:* ]] || fail "--image should not include a tag; use --version for the tag"

require_command docker

if [[ "${DRY_RUN}" -eq 0 ]]; then
  docker buildx version >/dev/null 2>&1 || fail "docker buildx is required"
  if ! docker manifest inspect "${IMAGE}:${VERSION}" >/dev/null 2>&1; then
    log "No existing ${IMAGE}:${VERSION} manifest found, or GHCR auth is not available."
    log "If publish fails, run: docker login ghcr.io"
  fi
fi

build_args=(
  "${BUILD_SCRIPT}"
  --image "${IMAGE}:${VERSION}"
  --platform "${PLATFORM}"
  --push
)

if [[ "${FORCE_BUNDLES}" -eq 1 ]]; then
  build_args+=(--force-bundles)
fi
if [[ -n "${CLI_ARCHIVE}" ]]; then
  build_args+=(--cli-archive "${CLI_ARCHIVE}")
fi
if [[ -n "${MCP_ARCHIVE}" ]]; then
  build_args+=(--mcp-archive "${MCP_ARCHIVE}")
fi

log "Publishing ${IMAGE}:${VERSION}"
run "${build_args[@]}"

if [[ "${LATEST}" -eq 1 ]]; then
  log "Publishing ${IMAGE}:latest from ${IMAGE}:${VERSION}"
  run docker buildx imagetools create -t "${IMAGE}:latest" "${IMAGE}:${VERSION}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "Dry run complete; no images were pushed."
else
  log "Published ${IMAGE}:${VERSION}"
  if [[ "${LATEST}" -eq 1 ]]; then
    log "Published ${IMAGE}:latest"
  fi
fi

# shellcheck shell=bash
# shellcheck disable=SC2034  # RG and IMAGES are used by the scripts that source this file
# Shared by build-push.sh and infra/deploy.sh: the one list of images and
# container apps, so building and deploying can never disagree about what this
# project ships. Sourced, not executed.

ACR=acrchatbotfredheda
RG=rg-chatbot

# "<acr repository>|<container app>|<dockerfile>|<build context>", in the
# order the apps are built. The Dockerfile path is relative to the repo root;
# the context is the folder the image is built from.
IMAGES=(
  "blogstudio-web|ca-blogstudio-web|frontend/Dockerfile|frontend"
  "blogstudio-api|ca-blogstudio-api|backend/Dockerfile.studio|backend"
  "blogapi|ca-blogapi|backend/Dockerfile.blogapi|backend"
)

# True for a full 40-character lowercase hex git SHA, the only tag the deploy
# flow builds and deploys.
is_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]]
}

# True if <repo>:<tag> exists in the registry.
image_exists() {
  az acr repository show -n "$ACR" --image "$1:$2" -o none >/dev/null 2>&1
}

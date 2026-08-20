#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-}"

if [[ -z "$TARGET_DIR" ]]; then
  echo "用法: bash SAFE_RESTORE_TO_EXISTING_PROJECT.sh /path/to/existing/medical-rag"
  exit 2
fi

mkdir -p "$TARGET_DIR"

# Source/application directories: replace with the complete restored version.
for dir in apps src scripts doc tests deployment migrations; do
  rm -rf "$TARGET_DIR/$dir"
  cp -a "$SOURCE_DIR/$dir" "$TARGET_DIR/$dir"
done

# Root source/configuration files. Do not touch .env, .git, or generated data.
for file in \
  pyproject.toml README.md REPLACE_README.md .env.example .gitignore \
  Makefile Makefile.v1 docker-compose.yml docker-compose.rag-v1.yml \
  Dockerfile.rag-v1 run.py; do
  if [[ -e "$SOURCE_DIR/$file" ]]; then
    cp -a "$SOURCE_DIR/$file" "$TARGET_DIR/$file"
  fi
done

# Only add missing data directory placeholders; never delete/overwrite runtime files.
mkdir -p "$TARGET_DIR/data/knowledge/inbox" "$TARGET_DIR/data/eval" "$TARGET_DIR/data/synthetic"

cat <<'EOF'
完整源码恢复完成。
已保留目标项目中的：
  - .git/
  - .env
  - data/ 中原有运行数据

下一步：
  pip install -e ".[product,dev]"
  pytest -q
  python scripts/preflight_v1.py
  python run.py

然后另开终端：
  cd apps/web
  npm install
  npm run dev
EOF

#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   bash RECOVER_HYPERTENSION_2024_KNOWLEDGE_DATA.sh [PDF路径]
# 如果不传 PDF 路径，默认寻找：
#   data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf

ROOT_DIR="$(pwd)"
DEFAULT_PDF='data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf'
PDF_PATH="${1:-$DEFAULT_PDF}"
OUT_DIR='data/processed/hypertension_2024'
MILVUS_DIR='data/milvus'
MILVUS_DB='data/milvus/medical_rag.db'

if [[ ! -f "pyproject.toml" || ! -d "src/medical_rag" || ! -d "scripts" ]]; then
  echo 'ERROR: 请在 medical-rag 项目根目录执行本脚本。' >&2
  exit 2
fi

if [[ ! -f "$PDF_PATH" ]]; then
  echo "ERROR: 找不到源 PDF：$PDF_PATH" >&2
  echo '请先把《中国高血压防治指南(2024年修订版).pdf》放入 data/knowledge/inbox/，' >&2
  echo '或把 PDF 的完整路径作为第一个参数传给本脚本。' >&2
  exit 3
fi

mkdir -p data/knowledge/inbox "$OUT_DIR" "$MILVUS_DIR"

# 如果目标目录已有残留文件，不直接删除，先做时间戳备份。
if find "$OUT_DIR" -mindepth 1 -maxdepth 1 -type f | grep -q . 2>/dev/null; then
  TS="$(date +%Y%m%d_%H%M%S)"
  BACKUP_DIR="${OUT_DIR}_before_rebuild_${TS}"
  echo "检测到旧的/残留处理结果，先备份到：$BACKUP_DIR"
  cp -a "$OUT_DIR" "$BACKUP_DIR"
fi

printf '\n==============================\n'
printf '1/5 重新解析与清洗 PDF\n'
printf '==============================\n'
python scripts/parse_pdf.py \
  "$PDF_PATH" \
  --output-dir "$OUT_DIR"

printf '\n==============================\n'
printf '2/5 重新切分知识片段（Chunk，文本切块）\n'
printf '==============================\n'
python scripts/chunk_document.py \
  "$OUT_DIR/cleaned_document.json" \
  --output-dir "$OUT_DIR" \
  --target-chars 800 \
  --max-chars 1200 \
  --min-chars 180 \
  --overlap-chars 120

printf '\n==============================\n'
printf '3/5 重新生成 Embedding（向量表示）\n'
printf '==============================\n'
python scripts/embed_chunks.py \
  "$OUT_DIR/chunks.json" \
  --output-dir "$OUT_DIR" \
  --model BAAI/bge-m3 \
  --device mps \
  --batch-size 8 \
  --max-seq-length 2048

printf '\n==============================\n'
printf '4/5 重建 Milvus（向量数据库）\n'
printf '==============================\n'
python scripts/ingest_milvus.py \
  "$OUT_DIR/chunks.json" \
  --embeddings "$OUT_DIR/embeddings.npy" \
  --manifest "$OUT_DIR/embedding_manifest.json" \
  --uri "$MILVUS_DB" \
  --collection medical_rag_chunks_v1 \
  --batch-size 100 \
  --recreate \
  --output-dir "$OUT_DIR"

printf '\n==============================\n'
printf '5/5 自动核验关键恢复结果\n'
printf '==============================\n'
python - <<'PY'
import json
from pathlib import Path
import numpy as np

base = Path('data/processed/hypertension_2024')
required = [
    'parsed_document.json',
    'cleaned_document.json',
    'parse_report.json',
    'tables.json',
    'table_quality_report.json',
    'chunks.json',
    'chunk_report.json',
    'embeddings.npy',
    'embedding_manifest.json',
    'embedding_report.json',
    'milvus_ingest_report.json',
]
missing = [name for name in required if not (base / name).exists()]
if missing:
    raise SystemExit(f'恢复失败，缺少文件: {missing}')

parse_report = json.loads((base/'parse_report.json').read_text(encoding='utf-8'))
chunk_report = json.loads((base/'chunk_report.json').read_text(encoding='utf-8'))
manifest = json.loads((base/'embedding_manifest.json').read_text(encoding='utf-8'))
emb = np.load(base/'embeddings.npy', allow_pickle=False)

summary = {
    'page_count': parse_report.get('page_count'),
    'table_count': parse_report.get('table_count'),
    'chunk_count': chunk_report.get('chunk_count'),
    'narrative_chunk_count': chunk_report.get('narrative_chunk_count'),
    'table_chunk_count': chunk_report.get('table_chunk_count'),
    'table_raw_fallback_chunk_count': chunk_report.get('table_raw_fallback_chunk_count'),
    'embedding_model': manifest.get('model_name'),
    'embedding_dimension': manifest.get('dimension'),
    'embedding_shape': list(emb.shape),
    'milvus_db_exists': Path('data/milvus/medical_rag.db').exists(),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))

# 这些是此前该指南在当前项目中的已验证基线；仅做提示，不因小版本差异强制失败。
expected = {
    'page_count': 98,
    'chunk_count': 500,
    'narrative_chunk_count': 484,
    'table_chunk_count': 16,
    'table_raw_fallback_chunk_count': 5,
    'embedding_dimension': 1024,
}
for key, value in expected.items():
    actual = summary.get(key)
    if actual != value:
        print(f'WARNING: {key} 当前={actual!r}，历史已验证值={value!r}')
PY

printf '\n==============================\n'
printf '启动前检查\n'
printf '==============================\n'
python scripts/preflight_v1.py

printf '\n恢复完成。接下来运行：\n'
printf '  python run.py\n'
printf '\n如果前端已经启动，刷新页面即可。\n'

#!/bin/bash
# flash_attn 스텁 dist-info 복구. /tmp 가 비워지면 매번 필요하다.
set -u
F=/tmp/fake_flash_attn
echo "  복구 전: 스텁디렉터리 $([ -d $F ] && echo 있음 || echo 없음) · dist-info $(ls -d $F/flash_attn-*.dist-info 2>/dev/null | wc -l)개"
mkdir -p $F/flash_attn $F/flash_attn-2.0.0.dist-info
cat > $F/flash_attn/__init__.py <<'PYX'
__version__ = "2.0.0"
PYX
cat > $F/flash_attn-2.0.0.dist-info/METADATA <<'MDX'
Metadata-Version: 2.1
Name: flash-attn
Version: 2.0.0
Summary: stub so transformers can resolve distribution metadata
MDX
echo "flash_attn" > $F/flash_attn-2.0.0.dist-info/top_level.txt
echo "" > $F/flash_attn-2.0.0.dist-info/RECORD
echo "  복구 후: dist-info $(ls -d $F/flash_attn-*.dist-info 2>/dev/null | wc -l)개"

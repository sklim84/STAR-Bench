import pathlib, sys
p = pathlib.Path("_experiments/scripts/run_benchmark_gf.sh")
s = p.read_text(encoding="utf-8")
if "GROUP_GF_4B" in s:
    print("  이미 패치됨"); sys.exit(0)
block = '''GROUP_GF_4B=(
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
)
GROUP_GF_35BA3B=(
    "qwen36-35b-a3b|Qwen/Qwen3.6-35B-A3B|qwen3_xml|--max-model-len 32768|Qwen/Qwen3.6-35B-A3B"
)
GROUP_SMOKE=('''
if "GROUP_SMOKE=(" not in s:
    print("  FAIL: GROUP_SMOKE 앵커 없음"); sys.exit(1)
s = s.replace("GROUP_SMOKE=(", block, 1)
anchor = '    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;'
if anchor not in s:
    print("  FAIL: SMOKE case 앵커 없음"); sys.exit(1)
s = s.replace(anchor,
    '    GF_4B) MODELS=("${GROUP_GF_4B[@]}") ;;\n'
    '    GF_35BA3B) MODELS=("${GROUP_GF_35BA3B[@]}") ;;\n' + anchor, 1)
p.write_text(s, encoding="utf-8")
print("  패치 적용 완료")

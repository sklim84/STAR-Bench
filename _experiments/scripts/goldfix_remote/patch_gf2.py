import pathlib, sys
p = pathlib.Path("_experiments/scripts/run_benchmark_gf2.sh")
s = p.read_text(encoding="utf-8")
if "GROUP_GF_36_27B" in s:
    print("  이미 패치됨"); sys.exit(0)
block = '''GROUP_GF_36_27B=(
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
)
GROUP_SMOKE=('''
s = s.replace("GROUP_SMOKE=(", block, 1)
anchor = '    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;'
if anchor not in s:
    print("  FAIL: 앵커 없음"); sys.exit(1)
s = s.replace(anchor, '    GF_36_27B) MODELS=("${GROUP_GF_36_27B[@]}") ;;\n' + anchor, 1)
p.write_text(s, encoding="utf-8")
print("  패치 적용 완료")

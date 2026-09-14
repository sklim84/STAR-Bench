import pathlib, sys
p = pathlib.Path("_experiments/scripts/run_benchmark_gf3.sh")
s = p.read_text(encoding="utf-8")
if "GROUP_GF_KAN_I" in s:
    print("  이미 패치됨"); sys.exit(0)
block = '''GROUP_GF_KAN_I=(
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-instruct"
)
GROUP_GF_KAN_T=(
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-thinking-2601"
)
GROUP_SMOKE=('''
s = s.replace("GROUP_SMOKE=(", block, 1)
anchor = '    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;'
if anchor not in s:
    print("  FAIL: 앵커 없음"); sys.exit(1)
s = s.replace(anchor,
    '    GF_KAN_I) MODELS=("${GROUP_GF_KAN_I[@]}") ;;\n'
    '    GF_KAN_T) MODELS=("${GROUP_GF_KAN_T[@]}") ;;\n' + anchor, 1)
p.write_text(s, encoding="utf-8")
print("  패치 적용 완료")

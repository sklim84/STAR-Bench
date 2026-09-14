import pathlib, sys
p = pathlib.Path("_experiments/scripts/run_benchmark_fin2.sh")
s = p.read_text(encoding="utf-8")
if "GROUP_KAN2_I" in s: print("  이미 패치됨"); sys.exit(0)
block = '''GROUP_KAN2_I=(
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|functionary_v3_llama_31|--enforce-eager --max-model-len 32768|kakaocorp/kanana-2-30b-a3b-instruct"
)
GROUP_KAN2_T=(
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|functionary_v3_llama_31|--enforce-eager --max-model-len 32768|kakaocorp/kanana-2-30b-a3b-thinking-2601"
)
GROUP_SMOKE=('''
s = s.replace("GROUP_SMOKE=(", block, 1)
a = '    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;'
if a not in s: print("  FAIL 앵커"); sys.exit(1)
s = s.replace(a, '    KAN2_I) MODELS=("${GROUP_KAN2_I[@]}") ;;\n    KAN2_T) MODELS=("${GROUP_KAN2_T[@]}") ;;\n' + a, 1)
p.write_text(s, encoding="utf-8"); print("  패치 완료")

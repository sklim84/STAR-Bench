import pathlib, sys
p = pathlib.Path("_experiments/scripts/run_benchmark_fin.sh")
s = p.read_text(encoding="utf-8")
if "GROUP_FIN_Q35_27B" in s:
    print("  이미 패치됨"); sys.exit(0)
block = '''GROUP_FIN_Q35_27B=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
)
GROUP_FIN_Q36_27B=(
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
)
GROUP_FIN_KAN_I=(
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-instruct"
)
GROUP_FIN_KAN_T=(
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-thinking-2601"
)
GROUP_SMOKE=('''
s = s.replace("GROUP_SMOKE=(", block, 1)
a = '    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;'
if a not in s: print("  FAIL: 앵커 없음"); sys.exit(1)
s = s.replace(a,
  '    FIN_Q35_27B) MODELS=("${GROUP_FIN_Q35_27B[@]}") ;;\n'
  '    FIN_Q36_27B) MODELS=("${GROUP_FIN_Q36_27B[@]}") ;;\n'
  '    FIN_KAN_I) MODELS=("${GROUP_FIN_KAN_I[@]}") ;;\n'
  '    FIN_KAN_T) MODELS=("${GROUP_FIN_KAN_T[@]}") ;;\n' + a, 1)
p.write_text(s, encoding="utf-8"); print("  패치 완료")

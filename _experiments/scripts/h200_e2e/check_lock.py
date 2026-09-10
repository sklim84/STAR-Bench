import json, glob, collections
R="/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench/_experiments"
for tag in ["real","oracle"]:
    for f in glob.glob(f"{R}/results_mt_smoke_{tag}/eval/*.json"):
        d=json.load(open(f))
        tot=err=lock=0; kinds=collections.Counter()
        for s in d.get("scenarios",[]):
            for t in s.get("turns",[]):
                for r in (t.get("executed_results") or []):
                    tot+=1
                    txt=json.dumps(r, ensure_ascii=False)
                    if "Could not set lock" in txt: lock+=1
                    if '"error"' in txt or "Error" in txt:
                        err+=1
                        for k in ["Could not set lock","Memgraph","neo4j","invalid literal","KeyError","not found"]:
                            if k in txt: kinds[k]+=1; break
                        else: kinds["기타"]+=1
        print(f"{tag:7s} 도구실행 {tot:4d} · 에러 {err:3d} ({err/tot*100 if tot else 0:.1f}%) · DuckDB락 {lock}")
        if kinds: print("        에러 내역:", dict(kinds))

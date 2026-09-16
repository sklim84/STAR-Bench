# Superseded analysis scripts (R2C-007)

These four scripts produced figures the manuscript no longer builds from, under
the same file names, and two of them wrote into a manuscript checkout outside
this repository. Running one during a regeneration replaced a paper figure with
a different plot and said nothing about it.

They are kept for provenance, they are not part of
`python -m _experiments.scripts.regenerate_analysis`, and each now writes into
`_experiments/figures/archive/` rather than `_experiments/figures/`.

| script | why it is here | what replaced it |
|---|---|---|
| `RQ3_turnwise_real.py` | wrote `fig_turnwise_line.png`, the name `fig:multiturn` builds from, with a six-model plot | `generate_new_figures.py` owns that figure; per-turn numbers come from `RQ3_error_propagation.py` and `RQ_oracle_vs_real.py` |
| `generate_paper_figures.py` | the 54-model figure set (`fig1`..`fig6`), from before the 28-configuration cohort | `RQ1_model_bar.py`, `RQ1_confusion_heatmap.py`, `generate_subdomain_radar.py`, `generate_fig4_scatter_v2.py` |
| `generate_bfcl_comparison.py` | saved a different correlation under the manuscript's `fig_bfcl_vs_aml` name | nothing: D14 removed the BFCL comparison from the paper |
| `plot_bfcl_vs_aml.py` | same figure name, and it read a fixed `/tmp` file | nothing (D14); the input is now `--pairs <json>` |

The manuscript copy is a separate, explicit step:

```
python -m _experiments.scripts.regenerate_analysis --copy-to-manuscript ../STAR-Bench-manu/figures
```

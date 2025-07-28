import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

program_labels = ['diffutils-3.7', 'findutils-4.7.0', 'gawk-5.1.0', 'gcal-4.1', 'grep-3.6', 'sed-4.8']
program_keys   = ['diff', 'find', 'gawk', 'gcal', 'grep', 'sed']

tools          = ['Human', 'FeatMaker', 'HOMI', 'SymTuner', 'KLEE-aaqc']
tool_suffixes  = ['human', 'featmaker', 'homi', 'symtuner', 'klee-aaqc']

base_dir = '/TowardImprovingSE/klee_output_folder/cov_results/'

values = []
for prog in program_keys:
    row = []
    for suf in tool_suffixes:
        csv_path = f"{base_dir}{suf}_{prog}_cov_result.csv"
        df = pd.read_csv(csv_path)
        mean_cov = df['Total Coverage'].mean()
        row.append(mean_cov)
    values.append(row)

styles = {
    'Human':     {'color': '#B0BEC5', 'hatch': '',    'edgecolor': 'black'},
    'FeatMaker': {'color': '#42A5F5', 'hatch': 'xx',  'edgecolor': 'black'},
    'HOMI':      {'color': '#FFA726', 'hatch': '//',  'edgecolor': 'black'},
    'SymTuner':  {'color': '#66BB6A', 'hatch': '',    'edgecolor': 'black'},
    'KLEE-aaqc': {'color': '#26A69A', 'hatch': '--',  'edgecolor': 'black'},
}

plt.rcParams['font.family'] = 'Times New Roman'
fig, ax = plt.subplots(figsize=(14, 8))
width = 0.17
x = np.arange(len(program_labels))

for i, tool in enumerate(tools):
    style = styles.get(tool, {'color': 'gray', 'hatch': '', 'edgecolor': 'black'})
    heights = [v[i] for v in values]
    ax.bar(
        x + i * width,
        heights,
        width,
        label=tool,
        color=style['color'],
        hatch=style['hatch'],
        edgecolor=style['edgecolor']
    )

ax.set_ylabel('Branch Coverage', fontsize=26)
ax.set_xticks(x + width * (len(tools) - 1) / 2)
ax.set_xticklabels(program_labels, rotation=0, ha='center', fontsize=24)
ax.tick_params(axis='y', labelsize=22)
ax.set_xlabel('')
ax.grid(True, which='major', axis='y', linestyle=':', linewidth=0.5, color='gray', alpha=0.7)
ax.set_axisbelow(True)
ax.legend(loc='upper right', fontsize=24)

plt.tight_layout()
plt.savefig("All_tools_branch_coverage.pdf", format="pdf")
plt.show()

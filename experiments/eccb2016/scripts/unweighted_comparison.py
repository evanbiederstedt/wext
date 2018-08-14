#!/usr/bin/env python3

 #Load required modules
import matplotlib
matplotlib.use('Agg')
import sys, os, argparse, json, matplotlib.pyplot as plt, numpy as np, seaborn as sns, pandas as pd
from scipy.stats import spearmanr
plt.style.use('ggplot')
from helper import add_y_equals_x

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-ef', '--exact_files', type=str, required=True, nargs='*')
parser.add_argument('-sf', '--saddlepoint_files', type=str, required=True, nargs='*')
parser.add_argument('-c', '--cancers', type=str, required=True, nargs='*')
parser.add_argument('-ff', '--figure_file', type=str, required=True)
args = parser.parse_args(sys.argv[1:])

assert( len(args.exact_files) == len(args.saddlepoint_files) == len(args.cancers) )

# Load the runtimes and P-values
exactPval, exactRuntime             = dict(), dict()
saddlepointPval, saddlepointRuntime = dict(), dict()
for cancer, exact_file in zip(args.cancers, args.exact_files):
    with open(exact_file, 'r') as IN:
        obj = json.load(IN)
        exactPval[cancer] = obj['setToPval']
        exactRuntime[cancer] = obj['setToRuntime']

num_exact = sum(1 for c in args.cancers for M in list(exactPval[c].keys()))

for cancer, saddlepoint_file in zip(args.cancers, args.saddlepoint_files):
    with open(saddlepoint_file, 'r') as IN:
        obj = json.load(IN)
        saddlepointPval[cancer] = obj['setToPval']
        saddlepointRuntime[cancer] = obj['setToRuntime']

num_saddlepoint = sum(1 for c in args.cancers for M in list(saddlepointPval[c].keys()))
print('* Loaded {} exact sets and {} saddlepoint sets...'.format(num_exact, num_saddlepoint))

# Construct the arrays of data
saddlepoint_pvals, exact_pvals, items = [], [], []
for cancer in args.cancers:
    sets = set(saddlepointPval[cancer].keys()) & set(exactPval[cancer].keys())
    for M in sets:
        saddlepoint_pvals.append( saddlepointPval[cancer][M] )
        exact_pvals.append( exactPval[cancer][M] )
        items.append( {"Method": "Tail enumeration/CoMEt", "Cancer": cancer,
                       "Runtime (seconds)": exactRuntime[cancer][M]} )
        items.append( {"Method": "Saddlepoint approximation", "Cancer": cancer,
                       "Runtime (seconds)": saddlepointRuntime[cancer][M]} )

df = pd.DataFrame(items)

print('* Testing {} triples in the intersection (ignoring sets with invalid P-values)...'.format(len(saddlepoint_pvals)))

# Output spearman correlations between the saddlepoint and exact
rho, pval = spearmanr(exact_pvals, saddlepoint_pvals)
print('-' * 80)
print('CORRELATION')
print("Spearman's Rho: {}\nSpearman's P-value: {}\n".format(rho, pval))

# Set up the figure
fig, (ax1, ax2) = plt.subplots(1, 2)
fig.set_size_inches(10, 5)

# Create a P-value scatter plot
ax1.plot( exact_pvals, saddlepoint_pvals, 'o', c='r', alpha=0.5, mew=0.0, ms=3)
ax1.set_xlabel('R-exclusivity (tail enumeration/CoMEt) $p$-value')
ax1.set_ylabel('R-exclusivity (saddlepoint approximation) $p$-value')
ax1.set_xscale('log')
ax1.set_yscale('log')
add_y_equals_x(ax1)

# Create a runtime violin plot
sns.boxplot(x="Cancer", y="Runtime (seconds)", hue="Method", hue_order=["Tail enumeration/CoMEt", "Saddlepoint approximation"], data=df, ax=ax2)
ax2.set_yscale('log')

# Output to file
plt.tight_layout()
plt.savefig(args.figure_file)

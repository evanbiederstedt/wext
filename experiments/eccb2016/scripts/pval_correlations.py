#!/usr/bin/env python3

# Load required modules
import sys, os, argparse, pandas as pd
from scipy.stats import spearmanr
from itertools import combinations
from helper import aligned_plaintext_table

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-pf', '--pairs_files', type=str, required=True, nargs='*')
parser.add_argument('-c', '--cancers', type=str, required=True, nargs='*')
parser.add_argument('-np', '--num_permutations', type=int, required=True)
args = parser.parse_args(sys.argv[1:])

# Load the pairs files
items = []
for cancer, pairs_file in zip(args.cancers, args.pairs_files):
    with open(pairs_file, 'r') as IN:
        arrs = [ l.rstrip('\n').split('\t') for l in IN if not l.startswith('#') ]
        for arr in arrs:
            raw_permutational_pval = float(arr[8])
            items.append( {"Method": "Fisher's exact test", "P-value": float(arr[6]), "Cancer": cancer, "Runtime (secs)": float(arr[7]) })
            items.append( {"Method": "Weighted (exact test)", "P-value": float(arr[2]), "Cancer": cancer, "Runtime (secs)": float(arr[3]) })
            items.append( {"Method": "Weighted (saddlepoint)", "P-value": float(arr[4]), "Cancer": cancer, "Runtime (secs)": float(arr[5]) })
            permutation_pval = raw_permutational_pval if raw_permutational_pval != 0 else 1./args.num_permutations
            items.append( {"Method": "Permutational", "P-value": permutation_pval, "Raw P-value": raw_permutational_pval, "Cancer": cancer })

df = pd.DataFrame(items)

# Compute the correlations with permutational
# permutational_pvals_with_zeros = list(df.loc[df['Method'] == 'Permutational']['Raw P-value'])
# all_indices =
tests       = ["Permutational", "Fisher's exact test", "Weighted (exact test)", "Weighted (saddlepoint)"]
for val, indices in [("All", []), (0, 1./args.num_permutations), (1./args.num_permutations, 2)]:
    tbl = [list(tests)]
    for t1 in tests:
        t1_pvals = list(df.loc[df['Method'] == t1]['P-value'])
        row = []
        for t2 in tests:
            if t1 == t2:
                row.append('--')
            else:
                t2_pvals = list(df.loc[df['Method'] == t2]['P-value'])
                rho, pval = spearmanr(t1_pvals, t2_pvals)
                row.append(rho)
        tbl.append(row)

    print('-' * 80)
    print('CORRELATIONS ({})'.format(val))
    print(aligned_plaintext_table('\n'.join([ '\t'.join(map(str, row)) for row in tbl ])))

permutational_pvals_no_zeros = [ p for p in permutational_pvals_with_zeros if p > 0 ]
for method in ["Fisher's exact test", "Weighted (exact test)", "Weighted (saddlepoint)"]:
    pvals = list(df.loc[df['Method'] == method]['P-value'])
    print('Correlation:', method, 'with Permutational')
    rho, pval = spearmanr(permutational_pvals, pvals)
    print('\tIncluding P < {}: N={}, \\rho={}, P={}'.format(1./args.num_permutations, len(pvals), rho, pval))
    pvals_no_zeros = [ p for i, p in enumerate(pvals) if permutational_pvals_with_zeros[i] > 0 ]
    rho, pval = spearmanr(permutational_pvals_no_zeros, pvals_no_zeros)
    print('\tWithout P < {}: N={}, \\rho={}, P={}'.format(1./args.num_permutations, len(pvals_no_zeros), rho, pval))

# Compute the correlations of weighted saddlepoint and exact test
weighted_exact_pvals = list(df.loc[df['Method'] == 'Weighted (exact test)']['P-value'])
weighted_saddlepoint_pvals = list(df.loc[df['Method'] == 'Weighted (saddlepoint)']['P-value'])
rho, pval = spearmanr(weighted_exact_pvals, weighted_saddlepoint_pvals)

print('Correlation of weighted exact test and saddlepoint (all P-values)')
print('\tN={}, \\rho: {}, P={}'.format(len(weighted_exact_pvals), rho, pval))

tail_weighted_exact_pvals = [ p for p in weighted_exact_pvals if p < 1e-4 ]
rho, pval = spearmanr(tail_weighted_exact_pvals, [ p for i, p in enumerate(weighted_saddlepoint_pvals) if weighted_exact_pvals[i] < 1e-4])
print('Correlation of weighted exact test and saddlepoint (P < 0.0001)')
print('\tN={}, \\rho: {}, P={}'.format(len(tail_weighted_exact_pvals), rho, pval))

rho, pval = spearmanr(tail_weighted_exact_pvals, [ p for i, p in enumerate(permutational_pvals) if weighted_exact_pvals[i] < 1e-4])
print('Correlation of weighted exact test and permutational (P < 0.0001)')
print('\tN={}, \\rho: {}, P={}'.format(len(tail_weighted_exact_pvals), rho, pval))

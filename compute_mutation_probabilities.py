#!/usr/bin/env python3

# Load required modules
import sys, os, argparse, json, numpy as np, multiprocessing as mp, random
from collections import defaultdict

# Load the weighted exclusivity test
this_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(this_dir)
from wext import *

# Argument parser
def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mf', '--mutation_file', type=str, required=True)
    parser.add_argument('-wf', '--weights_file', type=str, required=False, default=None)
    parser.add_argument('-pd', '--permutation_directory', type=str, required=False)
    parser.add_argument('-np', '--num_permutations', type=int, required=True)
    parser.add_argument('-si', '--start_index', type=int, required=False, default=1)
    parser.add_argument('-q', '--swap_multiplier', type=int, required=False, default=100)
    parser.add_argument('-nc', '--num_cores', type=int, required=False, default=1)
    parser.add_argument('-s', '--seed', type=int, required=False, default=None)
    parser.add_argument('-v', '--verbose', type=int, required=False, default=1, choices=list(range(5)))
    return parser

def permute_matrices_wrapper(args): 
    return permute_matrices(*args)

def permute_matrices(edge_list, max_swaps, max_tries, seeds, verbose, m, n, num_edges, indexToGene, indexToPatient):
    # Initialize our output
    observed     = np.zeros((m, n))
    permutations = []
    for seed in seeds:
        # Permute the edge list
        permuted_edge_list = bipartite_edge_swap(edge_list, max_swaps, max_tries, seed, verbose,
                                                 m, n, num_edges)

        # Recover the mapping of mutations from the permuted edge list
        geneToCases  = defaultdict(set)
        indices = []
        for edge in permuted_edge_list:
            gene, patient = indexToGene[edge[0]], indexToPatient[edge[1]]
            geneToCases[gene].add(patient)
            indices.append( (edge[0]-1, edge[1]-1) )

        # Record the permutation
        observed[list(zip(*indices))] += 1.
        geneToCases = dict( (g, list(cases)) for g, cases in iter(list(geneToCases.items())) )
        permutations.append( dict(geneToCases=geneToCases, permutation_number=seed) )

    return observed/float(len(seeds)), permutations

def postprocess_weight_matrix(P, r, s):
    assert np.shape(P)==(len(r), len(s))

    # Find indices corresponding to entries of weight matrix with same marginals
    marginals_to_indices = defaultdict(list)
    for i, r_i in enumerate(r):
        for j, s_j in enumerate(s):
            marginals_to_indices[(r_i, s_j)].append((i, j))

    # Average weights over entries of weight matrix with same marginals
    P_mean = np.zeros(np.shape(P))
    for marginals, indices in list(marginals_to_indices.items()):
        mean_value = float(sum(P[i, j] for i, j in indices))/float(len(indices))
        for i, j in indices:
            P_mean[i, j] = mean_value

    return P_mean

def run( args ):
    # Do some additional argument checking
    if not args.weights_file and not args.permutation_directory:
        sys.stderr.write('You must set the weights file or permutation directory, '\
                         'otherwise nothing will be output.')
        sys.exit(1)

    # Load mutation data
    if args.verbose > 0:
        print('* Loading mutation data...')

    mutation_data = load_mutation_data( args.mutation_file )
    genes, all_genes, patients, geneToCases, patientToMutations, params, hypermutators = mutation_data

    geneToObserved = dict( (g, len(cases)) for g, cases in iter(list(geneToCases.items())) )
    patientToObserved = dict( (p, len(muts)) for p, muts in iter(list(patientToMutations.items())) )
    geneToIndex = dict( (g, i+1) for i, g in enumerate(all_genes) )
    indexToGene = dict( (i+1, g) for i, g in enumerate(all_genes) )
    patientToIndex = dict( (p, j+1) for j, p in enumerate(patients) )
    indexToPatient = dict( (j+1, p) for j, p in enumerate(patients) )

    edges = set()
    for gene, cases in list(geneToCases.items()):
        for patient in cases:
            edges.add( (geneToIndex[gene], patientToIndex[patient]) )

    edge_list = np.array(sorted(edges), dtype=np.int)

    # Run the bipartite edge swaps
    if args.verbose > 0:
        print('* Permuting matrices...')

    m = len(all_genes)
    n = len(patients)
    num_edges = len(edges)
    max_swaps = int(args.swap_multiplier*num_edges)
    max_tries = 10**9
    if args.seed is not None:
        random.seed(args.seed)
    seeds = random.sample(list(range(1, 2*10**9)), args.num_permutations)

    # Run the bipartite edge swaps in parallel if more than one core indicated
    num_cores = min(args.num_cores if args.num_cores != -1 else mp.cpu_count(), args.num_permutations)
    if num_cores != 1:
        pool = mp.Pool(num_cores)
        map_fn = pool.map
    else:
        map_fn = map

    wrapper_args = [ (edge_list, max_swaps, max_tries, seeds[i::num_cores], 0, m,
                      n, num_edges, indexToGene, indexToPatient) for i in range(num_cores) ]
    results = map_fn(permute_matrices_wrapper, wrapper_args)

    if num_cores != 1:
        pool.close()
        pool.join()

    # Create the weights file
    if args.weights_file:
        if args.verbose > 0:
            print('* Saving weights file...')

        # Allow for small accumulated numerical errors
        tol = 1e3*max(m, n)*args.num_permutations*np.finfo(np.float64).eps

        # Merge the observeds
        observeds = [ observed for observed, _ in results ]
        P = np.add.reduce(observeds) / float(len(observeds))

        # Verify the weights
        for g, obs in list(geneToObserved.items()):
            assert( np.abs(P[geneToIndex[g]-1].sum() - obs) < tol)

        for p, obs in list(patientToObserved.items()):
            assert( np.abs(P[:, patientToIndex[p]-1].sum() - obs) < tol)

        # Construct mutation matrix to compute marginals
        A = np.zeros(np.shape(P), dtype=np.int)
        for i, j in edge_list:
            A[i-1, j-1] = 1
        r = np.sum(A, 1)
        s = np.sum(A, 0)

        # Post-process weight matrix to assign same weight to entries with same marginals
        P = postprocess_weight_matrix(P, r, s)

        # Verify the weights again
        for g, obs in list(geneToObserved.items()):
            assert( np.abs(P[geneToIndex[g]-1].sum() - obs) < tol)

        for p, obs in list(patientToObserved.items()):
            assert( np.abs(P[:, patientToIndex[p]-1].sum() - obs) < tol)

        # Add pseudocounts to entries with no mutations observed; unlikely or impossible after post-processing step
        P[P == 0] = 1./(2. * args.num_permutations)

        # Output to file.
        # The rows/columns preserve the order given by the mutation file.
        np.save(args.weights_file, P)

    # Save the permuted mutation data
    if args.permutation_directory:
        output_prefix = args.permutation_directory + '/permuted-mutations-{}.json'
        if args.verbose > 0:
            print('* Saving permuted mutation data...')

        for _, permutation_list in results:
            for permutation in permutation_list:
                # Output in adjacency list format
                with open(output_prefix.format(permutation['permutation_number']), 'w') as OUT:
                    permutation['params'] = params
                    json.dump( permutation, OUT )

if __name__ == '__main__': 
    run( get_parser().parse_args(sys.argv[1:]) )

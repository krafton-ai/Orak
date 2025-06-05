import pandas as pd
import ast
import argparse
import json
import os
import numpy as np

# --------------------
# Compute Composite 0–100 Scores with Trial-Level Grades
# --------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='Compute composite 0-100 grades per trial from a score_table CSV using user-provided benchmarks.'
    )
    parser.add_argument(
        'input_path',
        help='Path to the input score_table CSV file'
    )
    parser.add_argument(
        '--weights',
        default='{"multiple_choice":1, "cross_examination_1":4, "cross_examination_2":2, "cross_examination_3":3}',
        help='JSON string mapping each task to its difficulty weight'
    )
    parser.add_argument(
        '--benchmarks',
        default='{"multiple_choice":[3,25], "cross_examination_1":[1,11], "cross_examination_2":[1,3], "cross_examination_3":[1,4]}',
        help='JSON string mapping each task to [best_score, best_steps] benchmarks'
    )
    parser.add_argument(
        '--alpha',
        type=float,
        default=0.7,
        help='Blend factor between accuracy (A) and speed (B)'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load parameters
    weights = json.loads(args.weights)
    benchmarks = json.loads(args.benchmarks)
    alpha = args.alpha

    # Prepare tasks, max_scores and best_steps
    tasks = list(weights.keys())
    max_scores = {t: benchmarks[t][0] for t in tasks}
    best_steps = {t: benchmarks[t][1] for t in tasks}
    total_weight = sum(weights.values())

    # Determine output path
    dirpath   = os.path.dirname(args.input_path)
    basename  = os.path.basename(args.input_path)
    out_name  = basename.replace('score_table', 'score_grade')
    output_path = os.path.join(dirpath, out_name)

    # Read input CSV
    df = pd.read_csv(args.input_path)

    # For each task, parse Scores/Steps into lists
    for task in tasks:
        df[f'{task}_scores_list'] = df[f'{task}_Scores'].apply(ast.literal_eval)
        df[f'{task}_steps_list']  = df[f'{task}_Steps'].apply(ast.literal_eval)

    # Compute trial-level composite grades
    grades_list = []
    for idx, row in df.iterrows():
        # Determine number of trials from first task
        n_trials = len(row[f'{tasks[0]}_scores_list'])
        comp_grades = []
        for j in range(n_trials):
            # compute weighted accuracy A_j and speed B_j
            A_j = 0.0
            B_j = 0.0
            for t in tasks:
                # accuracy and speed for trial j
                if row[f'{t}_scores_list'][j] == 0:
                    p_ij = 0
                    s_ij = 0
                else:
                    p_ij = row[f'{t}_scores_list'][j] / max_scores[t]
                    s_ij = best_steps[t] / row[f'{t}_steps_list'][j]
                A_j += weights[t] * p_ij
                B_j += weights[t] * s_ij
            # normalize by total weight
            A_j /= total_weight
            B_j /= total_weight
            # composite grade 0-100
            comp = 100 * (alpha * A_j + (1 - alpha) * B_j)
            comp_grades.append(comp)
        grades_list.append(comp_grades)

    # Attach trial-level grades list
    df['Composite_Grades'] = grades_list

    # Compute statistics and format summary
    summaries = []
    for comp in grades_list:
        arr = np.array(comp)
        avg       = np.mean(arr)
        pop_std   = np.std(arr, ddof=0)
        samp_std  = np.std(arr, ddof=1) if len(arr) > 1 else 0.0
        summaries.append(f"{avg:.1f}±{pop_std:.1f}({samp_std:.1f})")
    df['Composite_Grade'] = summaries

    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"Composite trial-level grades saved to: {output_path}")

if __name__ == '__main__':
    main()

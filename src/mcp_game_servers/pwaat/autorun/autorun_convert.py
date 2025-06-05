#!/usr/bin/env python3
import re
import csv
import os
import argparse
import numpy as np
from collections import OrderedDict

def parse_file(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # ignore execution summary
    main = content.split('# Execution Time Summary')[0]
    # split run summaries
    blocks = re.split(r"# Run Summary \[\d+/\d+\] -+-+\n", main)[1:]

    parsed = []
    task_order = []

    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        # headers
        ts_match = re.search(r"Timestamp:\s*(\S+)", lines[0])
        if not ts_match:
            continue
        ts = ts_match.group(1)
        task = re.search(r"Task:\s*(\S+)", lines[1]).group(1)
        llm = re.search(r"LLMName:\s*(\S+)", lines[2]).group(1)
        agt = re.search(r"AgentType:\s*(\S+)", lines[3]).group(1)
        if task not in task_order:
            task_order.append(task)

        # locate trial header and metric start
        idx = lines.index('Trial,Score,FinalStep,TimeSec')
        # find where metrics begin
        metric_start = len(lines)
        for j in range(idx+1, len(lines)):
            if lines[j].startswith('Score Average'):
                metric_start = j
                break
        # trial lines between idx+1 and metric_start
        raw_scores, raw_steps, raw_times = [], [], []
        scores, steps, times = [], [], []
        for tl in lines[idx+1:metric_start]:
            parts = tl.split(',')
            if len(parts) < 4:
                continue
            _, s_str, f_str, t_str = parts[0], parts[1], parts[2], parts[3]
            raw_scores.append(s_str)
            raw_steps.append(f_str)
            raw_times.append(t_str)
            scores.append(float(s_str))
            steps.append(float(f_str))
            times.append(float(t_str))

        # parse printed metrics if present
        printed = {}
        for ml in lines[metric_start:metric_start+3]:
            if ml.startswith('Score Average'):
                printed['score_avg'], printed['score_pop'], printed['score_samp'] = map(float, re.findall(r"[-+]?[0-9]*\.?[0-9]+", ml))
            elif ml.startswith('FinalStep Average'):
                printed['fs_avg'], printed['fs_pop'], printed['fs_samp'] = map(float, re.findall(r"[-+]?[0-9]*\.?[0-9]+", ml))
            elif ml.startswith('TimeSec Average'):
                printed['time_avg'], printed['time_pop'], printed['time_samp'] = map(float, re.findall(r"[-+]?[0-9]*\.?[0-9]+", ml))

        # recalc metrics
        def std(arr, ddof): return np.std(arr, ddof=ddof)
        calc = {
            'score_avg': np.mean(scores) if scores else 0.0,
            'score_pop': std(scores, ddof=0) if scores else 0.0,
            'score_samp': std(scores, ddof=1) if len(scores)>1 else 0.0,
            'fs_avg': np.mean(steps) if steps else 0.0,
            'fs_pop': std(steps, ddof=0) if steps else 0.0,
            'fs_samp': std(steps, ddof=1) if len(steps)>1 else 0.0,
            'time_avg': np.mean(times) if times else 0.0,
            'time_pop': std(times, ddof=0) if times else 0.0,
            'time_samp': std(times, ddof=1) if len(times)>1 else 0.0
        }

        # final metrics: use calc if printed missing or mismatch
        final = {}
        for k in ['score_avg','score_pop','score_samp','fs_avg','fs_pop','fs_samp','time_avg','time_pop','time_samp']:
            if k in printed:
                val_print = printed[k]
                val_calc = calc[k]
                final[k] = val_print if abs(val_print - val_calc) < 1e-6 else val_calc
            else:
                final[k] = calc[k]

        parsed.append({
            'AgentType': agt,
            'LLMName': llm,
            'Task': task,
            'score': final['score_avg'],
            'score_pop': final['score_pop'],
            'score_samp': final['score_samp'],
            'fs': final['fs_avg'],
            'fs_pop': final['fs_pop'],
            'fs_samp': final['fs_samp'],
            'time': final['time_avg'],
            'time_pop': final['time_pop'],
            'time_samp': final['time_samp'],
            'raw_scores': raw_scores,
            'raw_steps': raw_steps,
            'raw_times': raw_times
        })
    return parsed, task_order


def fmt_avg(v):
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.4f}".rstrip('0').rstrip('.')

def fmt_std(v):
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v))}.0"
    return f"{v:.4f}".rstrip('0').rstrip('.')


def write_csv(parsed, task_order, output_path):
    cols = ['AgentType','LLMName']
    for task in task_order:
        cols += [
            f"{task}_Score",
            f"{task}_Step",
            f"{task}_Time",
            f"{task}_Scores",
            f"{task}_Steps",
            f"{task}_Times"
        ]
    groups = OrderedDict()
    for entry in parsed:
        key = (entry['AgentType'], entry['LLMName'])
        if key not in groups:
            groups[key] = {'AgentType': entry['AgentType'], 'LLMName': entry['LLMName']}
        task = entry['Task']
        sc = f"{fmt_avg(entry['score'])}±{fmt_std(entry['score_pop'])}({fmt_std(entry['score_samp'])})"
        st = f"{fmt_avg(entry['fs'])}±{fmt_std(entry['fs_pop'])}({fmt_std(entry['fs_samp'])})"
        tm = f"{fmt_avg(entry['time'])}±{fmt_std(entry['time_pop'])}({fmt_std(entry['time_samp'])})"
        rs = '[' + ', '.join(entry['raw_scores']) + ']'
        rstep = '[' + ', '.join(entry['raw_steps']) + ']'
        rt = '[' + ', '.join(entry['raw_times']) + ']'
        groups[key][f"{task}_Score"] = sc
        groups[key][f"{task}_Step"] = st
        groups[key][f"{task}_Time"] = tm
        groups[key][f"{task}_Scores"] = rs
        groups[key][f"{task}_Steps"] = rstep
        groups[key][f"{task}_Times"] = rt

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for data in groups.values():
            row = [data.get(c, '') for c in cols]
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description='Convert run summary TXT to wide CSV')
    parser.add_argument('input', help='Path to score card .txt')
    args = parser.parse_args()
    inp = args.input
    base = os.path.splitext(os.path.basename(inp))[0]
    out = os.path.join(os.path.dirname(inp) or '.', f'{base}_score_table.csv')
    parsed, tasks = parse_file(inp)
    write_csv(parsed, tasks, out)
    print(f"Saved: {out}")

if __name__ == '__main__':
    # uv run autorun_convert.py 20250505_012502_openai_pwaat_score_card.txt
    main()
#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import time
import glob
import json
import csv
from datetime import datetime
import statistics
from tqdm import tqdm


def get_avg_std(arr):
    """
    Returns (average, population_std, sample_std) rounded to 3 decimals.
    """
    if not arr:
        return 0.0, 0.0, 0.0
    avg = statistics.mean(arr)
    pop_std = statistics.pstdev(arr)
    sample_std = statistics.stdev(arr) if len(arr) > 1 else 0.0
    return round(avg, 4), round(pop_std, 4), round(sample_std, 4)


def main():
    parser = argparse.ArgumentParser(
        description='Run Task×LLM×AgentType combinations multiple times and record scores.'
    )
    parser.add_argument(
        '--trials', '-t', type=int, default=3,
        help='Number of trials per Task×LLM×AgentType (default: 3)'
    )
    parser.add_argument(
        '--suffix', type=str, default='',
        help='Suffix to be inserted in the output file names (default: empty)'
    )
    args = parser.parse_args()
    Trials = args.trials
    suffix = f"_{args.suffix}" if args.suffix else ""

    # Start measuring total execution time
    total_start_time = time.time()

    # Configuration
    TaskList      = ['multiple_choice', 'cross_examination_1', 'cross_examination_2', 'cross_examination_3']
    LLMNameList   = ["o3-mini", "gpt-4o-mini"]
    AgentTypeList = ['reflection_agent']
    Config        = './src/mcp_agent_client/configs/pwaat/config.yaml'
    AutorunDir    = './logs/autorun'
    OutputDir     = './logs/autorun_score_card'

    # Model-specific API base URLs
    MODEL_API_URLS = {
        "meta-llama/Llama-3.2-1B-Instruct": "http://100.66.7.22:3201/v1",
        "meta-llama/Llama-3.2-3B-Instruct": "http://100.66.7.22:3203/v1",
        "nvidia/Nemotron-Mini-4B-Instruct": "http://100.66.7.22:8084/v1",
        "nvidia/Mistral-NeMo-Minitron-8B-Instruct": "http://100.66.7.22:8084/v1",
        "Qwen/Qwen2.5-3B-Instruct": "http://100.66.7.22:2503/v1",
        "Qwen/Qwen2.5-7B-Instruct": "http://100.66.7.22:2507/v1",
    }

    # Ensure directories exist
    os.makedirs(AutorunDir, exist_ok=True)
    os.makedirs(OutputDir, exist_ok=True)

    # Prepare filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ScoreFile = os.path.join(OutputDir, f"{timestamp}{suffix}_score_card.txt")
    TableFile = os.path.join(OutputDir, f"{timestamp}{suffix}_score_table.csv")

    # Clean up old JSONs
    for fpath in glob.glob(os.path.join(AutorunDir, 'final_score_*.json')):
        try:
            os.remove(fpath)
        except OSError:
            pass

    results = []

    # Calculate total number of runs (Task × LLM × AgentType combinations)
    total_runs = len(LLMNameList) * len(AgentTypeList) * len(TaskList)
    run_cnt = 0

    # Main loops
    for LLM in tqdm(LLMNameList, desc="LLM", leave=False):
        for Agent in tqdm(AgentTypeList, desc="Agent"):
            row = {'AgentType': Agent, 'LLMName': LLM}

            for Task in tqdm(TaskList, desc="Task", leave=False):
                run_cnt += 1
                scoreArr = []
                stepArr  = []
                timeArr  = []

                # Write header for this Task
                with open(ScoreFile, 'a', encoding='utf8') as sf:
                    sf.write(f'# Run Summary [{run_cnt}/{total_runs}] ------------------------------------------------------------\n')
                    sf.write(f'Timestamp: {timestamp}\n')
                    sf.write(f'Task: {Task}\n')
                    sf.write(f'LLMName: {LLM}\n')
                    sf.write(f'AgentType: {Agent}\n')
                    sf.write('Trial,Score,FinalStep,TimeSec\n')

                # Trials
                for i in range(1, Trials + 1):
                    print(f"[ {Task} | {LLM} | {Agent} ] Trial {i}/{Trials}")

                    # remove old JSON
                    for old in glob.glob(os.path.join(AutorunDir, 'final_score_*.json')):
                        try:
                            os.remove(old)
                        except OSError:
                            pass

                    start = time.time()
                    cmd = [
                        'uv', 'run', './scripts/mcp_play_game.py',
                        '--config', Config,
                        f'env.task={Task}',
                        f'agent.llm_name={LLM}',
                        f'agent.agent_type={Agent}'
                    ]
                    
                    # Add API base URL if specified for the model
                    if LLM in MODEL_API_URLS:
                        cmd.append(f'agent.api_base_url={MODEL_API_URLS[LLM]}')
                    
                    subprocess.run(cmd, check=True)
                    elapsed = round(time.time() - start, 3)

                    # wait for JSON
                    json_file = None
                    deadline = time.time() + 10
                    while time.time() < deadline:
                        files = glob.glob(os.path.join(AutorunDir, 'final_score_*.json'))
                        if files:
                            files.sort(key=os.path.getmtime)
                            json_file = files[-1]
                            break
                        time.sleep(1)

                    if json_file and os.path.exists(json_file):
                        with open(json_file, 'r', encoding='utf8') as jf:
                            data = json.load(jf)
                        try:
                            os.remove(json_file)
                        except OSError:
                            pass
                        s = int(data.get('score', 0))
                        p = int(data.get('final_step', 0))
                    else:
                        raise ValueError('JSON not found')

                    scoreArr.append(s)
                    stepArr.append(p)
                    timeArr.append(elapsed)

                    with open(ScoreFile, 'a', encoding='utf8') as sf:
                        sf.write(f"{i},{s},{p},{elapsed}\n")

                # Compute statistics
                avgScore, popStdScore, sampleStdScore = get_avg_std(scoreArr)
                avgStep,  popStdStep,  sampleStdStep  = get_avg_std(stepArr)
                avgTime,  popStdTime,  sampleStdTime  = get_avg_std(timeArr)

                with open(ScoreFile, 'a', encoding='utf8') as sf:
                    sf.write(f"\nScore Average: {avgScore}, PopStdDev: {popStdScore}, SampleStdDev: {sampleStdScore}\n")
                    sf.write(f"FinalStep Average: {avgStep}, PopStdDev: {popStdStep}, SampleStdDev: {sampleStdStep}\n")
                    sf.write(f"TimeSec Average: {avgTime}, PopStdDev: {popStdTime}, SampleStdDev: {sampleStdTime}\n\n")

                # Add to row
                row[f"{Task}_Score"] = f"{avgScore}±{popStdScore}({sampleStdScore})"
                row[f"{Task}_Step"]  = f"{avgStep}±{popStdStep}({sampleStdStep})"
                row[f"{Task}_Time"]  = f"{avgTime}±{popStdTime}({sampleStdTime})"
                # Store individual trial scores and steps
                row[f"{Task}_Scores"] = scoreArr
                row[f"{Task}_Steps"] = stepArr
                row[f"{Task}_Times"] = timeArr

            results.append(row)

    # Write summary table
    if os.path.exists(TableFile):
        os.remove(TableFile)

    # Prepare header with individual trial columns
    header = ['AgentType', 'LLMName']
    for Task in TaskList:
        header.extend([
            f"{Task}_Score", f"{Task}_Step", f"{Task}_Time",
            f"{Task}_Scores", f"{Task}_Steps", f"{Task}_Times"  # Individual trial scores, steps, and times
        ])

    with open(TableFile, 'w', encoding='utf8', newline='') as tf:
        writer = csv.writer(tf)
        writer.writerow(header)
        for r in results:
            row_data = [r.get(col, '') for col in ['AgentType', 'LLMName']]
            for Task in TaskList:
                # Add average scores and steps
                row_data.extend([
                    r.get(f"{Task}_Score", ''),
                    r.get(f"{Task}_Step", ''),
                    r.get(f"{Task}_Time", '')
                ])
                # Add individual trial scores, steps, and times
                scores = r.get(f"{Task}_Scores", [])
                steps = r.get(f"{Task}_Steps", [])
                times = r.get(f"{Task}_Times", [])
                row_data.extend([
                    scores,  # Directly use the list of floats
                    steps,   # Directly use the list of floats
                    times    # Directly use the list of floats
                ])
            writer.writerow(row_data)

    # Calculate total execution time
    total_execution_time = time.time() - total_start_time
    total_trials_time = sum(sum(r.get(f"{Task}_Times", [])) for r in results for Task in TaskList)

    # Write total execution time to score card
    with open(ScoreFile, 'a', encoding='utf8') as sf:
        sf.write('\n# Execution Time Summary -------------------------------------------------\n')
        sf.write(f'Total Trials Execution Time: {total_trials_time:.2f} seconds\n')
        sf.write(f'Total Script Execution Time: {total_execution_time:.2f} seconds\n')

    print(f"\nComplete! Result files:\n  - {ScoreFile}\n  - {TableFile}")


if __name__ == '__main__':
    main()

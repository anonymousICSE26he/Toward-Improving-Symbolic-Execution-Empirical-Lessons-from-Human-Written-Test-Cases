import os
import math, time
import re
import argparse
import pickle
import csv
import json
import sys
import signal
from tempfile import NamedTemporaryFile
import shutil

def timeout_handler(signum, frame):
    print("Process exceeded 300 minutes. Exiting.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(300 * 60)

_re_visit_line = re.compile(r"\s*(\d+):\s*\d+:.*")
_re_branch    = re.compile(r"branch\s+\S+\s+taken\s+(\d+)%")
_re_func      = re.compile(r"\s*function\s+\S+\s+called\s+(\d+)")


parser = argparse.ArgumentParser(description='Run KLEE replay and calculate coverage for specified programs.')
parser.add_argument('--src_dir', type=str, required=True, help='Path to the source directory containing KLEE output.')
parser.add_argument('--gcov_num', type=int, required=True, help='Number to replace in the gcov directory path.')

args = parser.parse_args()

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config_data = json.load(f)

def count_directories(path):
    try:
        items = os.listdir(path)
        directories = [item for item in items if os.path.isdir(os.path.join(path, item))]
        return len(directories)
    except FileNotFoundError:
        return "The specified path does not exist."
    except Exception as e:
        return f"An error occurred: {e}"

def find_ktest_files(src_dir):
    def extract_numbers_homi(file_name):
        iteration_match = re.search(r'\d+__tc_dirs', file_name)
        test_match = re.search(r'test(\d+)\.ktest', file_name)
        if iteration_match and test_match:
            iteration_number = int(iteration_match.group(0).split('__')[0])
            test_number = int(test_match.group(1))
            return (iteration_number, test_number)
        else:
            return (float('inf'), float('inf'))

    def extract_numbers_default(file_name):
        iteration_match = re.search(r'/iteration(\d+)', file_name)
        test_match = re.search(r'test(\d+)\.ktest', file_name)
        if iteration_match and test_match:
            iteration_number = int(iteration_match.group(1))
            test_number = int(test_match.group(1))
            return (iteration_number, test_number)
        else:
            return (float('inf'), float('inf'))

    def extract_numbers_featmaker(file_name):
        iteration_match = re.search(r'/iteration-(\d+)', file_name)
        test_match = re.search(r'test(\d+)\.ktest', file_name)
        if iteration_match and test_match:
            iteration_number = int(iteration_match.group(1))
            test_number = int(test_match.group(1))
            return (iteration_number, test_number)
        else:
            return (float('inf'), float('inf'))

    ktest_files = []

    if 'homi' in src_dir.lower():
        extract_function = extract_numbers_homi
    elif 'featmaker' in src_dir.lower() or 'symtuner' in src_dir.lower():
        extract_function = extract_numbers_featmaker
    else:
        extract_function = extract_numbers_default

    if 'featmaker' in src_dir.lower() and 'seeds' not in src_dir.lower():
        for iteration_dir in os.listdir(src_dir):
            if re.match(r'iteration-(\d+)', iteration_dir):
                iteration_path = os.path.join(src_dir, iteration_dir)
                if os.path.isdir(iteration_path):
                    for sub_folder in range(20):
                        sub_folder_path = os.path.join(iteration_path, str(sub_folder))
                        if os.path.isdir(sub_folder_path):
                            for file_name in os.listdir(sub_folder_path):
                                if file_name.endswith('.ktest'):
                                    ktest_files.append(os.path.join(sub_folder_path, file_name))

    elif 'symtuner' in src_dir.lower():
        for iteration_dir in os.listdir(src_dir):
            if re.match(r'iteration-(\d+)', iteration_dir):
                klee_out_dir = os.path.join(src_dir, iteration_dir)
                if os.path.isdir(klee_out_dir):
                    for file_name in os.listdir(klee_out_dir):
                        if file_name.endswith('.ktest'):
                            ktest_files.append(os.path.join(klee_out_dir, file_name))

    

    elif 'homi' in src_dir.lower():
        for item in os.listdir(src_dir):
            if ('__tc_dirs' in item or 'iteration' in item):
                klee_out_dir = os.path.join(src_dir, item)
                if os.path.isdir(klee_out_dir):
                    for file_name in os.listdir(klee_out_dir):
                        if file_name.endswith('.ktest'):
                            ktest_files.append(os.path.join(klee_out_dir, file_name))
                            
    else:
        for iteration_dir in os.listdir(src_dir):
            if re.match(r'iteration-(\d+)', iteration_dir):
                klee_out_dir = os.path.join(src_dir, iteration_dir)
                if os.path.isdir(klee_out_dir):
                    for file_name in os.listdir(klee_out_dir):
                        if file_name.endswith('.ktest'):
                            ktest_files.append(os.path.join(klee_out_dir, file_name))

    return sorted(ktest_files, key=extract_function)


def count_switches_with_nonzero_branch(gcov_path):
    switch_re = re.compile(r'\d+:\s+\d+:\s+.*\bswitch\b')
    branch_re = re.compile(r'branch\s+\d+\s+taken\s+(\d+)%')

    count = 0

    with open(gcov_path, 'r', encoding='utf-8', errors='ignore') as f:
        in_switch = False
        found_nonzero = False
        brace_depth = 0
        has_entered_block = False

        for line in f:
            if not in_switch and switch_re.search(line):
                in_switch        = True
                found_nonzero    = False
                brace_depth      = 0
                has_entered_block = False

            if in_switch:
                opens  = line.count('{')
                closes = line.count('}')
                if opens > 0:
                    has_entered_block = True
                brace_depth += opens - closes

                m = branch_re.search(line)
                if m and int(m.group(1)) != 0:
                    found_nonzero = True

                if has_entered_block and brace_depth <= 0:
                    if found_nonzero:
                        count += 1
                    in_switch = False

    return count

def branch_handler(ktest_gcov, branch_visit_count, function_data):
    with open(ktest_gcov, 'r', errors='ignore') as f:
        lines = f.readlines()

    condition_visit_count = 0
    src_name = ""
    line_number = 0

    current_function = None
    function_branch_total = 0
    function_branch_taken = 0

    for line in lines:
        if "-:    0:Source:" in line:
            src_name = line.split('/')[-1].strip().replace('-:    0:Source:', '')
        
        elif re.match(r'\s*\d+:\s*\d+:', line):
            if "#####" in line:
                continue
            parts = line.split(":")
            try:
                condition_visit_count = int(parts[0].strip())
                line_number = int(parts[1].strip())
            except ValueError:
                condition_visit_count = 0
                line_number = 0

        elif line.lstrip().startswith("function") and "called" in line:
            tokens = line.split()
            function_name = tokens[1]

            if current_function is not None and function_name != current_function:
                if function_branch_total > 0:
                    coverage = (function_branch_taken / function_branch_total) * 100
                else:
                    coverage = 0.0
                function_data.append([src_name, current_function, coverage, function_branch_taken, function_branch_total])
                current_function = function_name
                function_branch_total = 0
                function_branch_taken = 0
            elif current_function is None:
                current_function = function_name
                function_branch_total = 0
                function_branch_taken = 0
            else:
                pass

        elif "branch" in line and "taken" in line:
            parts = line.split()
            branch_id = parts[1]
            taken_percentage_str = parts[3].replace('%', '')
            try:
                taken_percentage = float(taken_percentage_str)
            except ValueError:
                taken_percentage = 0.0

            if math.isnan(condition_visit_count) or math.isnan(taken_percentage):
                branch_visits = 0
                print(f"NaN detected in {src_name} {line_number} {branch_id}")
            else:
                branch_visits = int(condition_visit_count * (taken_percentage / 100))

            if branch_visits > 0:
                branch_key = f"{src_name} {line_number} {branch_id}"
                branch_visit_count[branch_key] = branch_visit_count.get(branch_key, 0) + branch_visits

            if current_function is not None:
                function_branch_total += 1
                if "never executed" not in line and taken_percentage > 0:
                    function_branch_taken += 1

        else:
            continue

    if current_function is not None:
        if function_branch_total > 0:
            coverage = (function_branch_taken / function_branch_total) * 100
        else:
            coverage = 0.0
        function_data.append([src_name, current_function, coverage, function_branch_taken, function_branch_total])

    return branch_visit_count

def cal_coverage(cov_file):
    coverage = 0
    total_coverage = 0
    with open(cov_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if "Taken at least" in line:
                data = line.split(':')[1]
                percent = float(data.split('% of ')[0])
                total_branches = float((data.split('% of ')[1]).strip())
                covered_branches = int(percent * total_branches / 100)
                coverage += covered_branches
                total_coverage += total_branches
    print("----------------Results--------------------------------------------")
    print("-------------------------------------------------------------------")
    print(f"The number of covered branches: {coverage}")
    print(f"The number of total branches: {int(total_coverage)}")
    print("-------------------------------------------------------------------")
    return coverage

src_dir = args.src_dir
gcov_num = args.gcov_num

program = next((key for key in config_data if key in src_dir.lower()), 'unknown')

if program == 'unknown':
    print("Error: Program name could not be determined from src_dir.")
    exit(1)

tool_name = [tool for tool in ['homi', 'featmaker', 'symtuner', 'klee-aaqc'] if tool in src_dir.lower()]
tool_suffix = tool_name[0] if tool_name else 'unknown'

if tool_suffix == 'featmaker' and 'depth' in src_dir.lower():
    tool_suffix = 'klee'

switch_counts = []

lower_src = src_dir.lower()

nxargs_match = re.search(r'(humanArgs)', src_dir, re.IGNORECASE)
nxargs_suffix = f"_{nxargs_match.group(1)}" if nxargs_match else ""

regex_match = re.search(r'(regex)', src_dir, re.IGNORECASE)
regex_suffix = f"_{regex_match.group(1)}" if regex_match else ""

rep_match = re.search(r'(rep\d+)', src_dir, re.IGNORECASE)
rep_suffix = f"_{rep_match.group(1)}" if rep_match else ""


switch_suffix = ""
switch_match = re.search(r'(switch)', src_dir, re.IGNORECASE)
if switch_match:
    switch_suffix = f"_{switch_match.group(1).lower()}"



settings = config_data[program]

gcov_dir = settings['gcov_dir'].replace('<gcov_num>', str(gcov_num))
rm_cmd = settings['rm_cmd']
replay_cmd = settings['replay_cmd']
cov_cmd = settings['cov_cmd']


arguments_dir = (
    f"{settings['arguments_dir']}_arguments_"
    f"{tool_suffix}"        
    f"{nxargs_suffix}{regex_suffix}"
    f"_{program}{switch_suffix}{rep_suffix}"  

)

csv_filename = (
    f"/TowardImprovingSE/klee_output_folder/{program}/branch_visit_count/"
    f"{tool_suffix}_{program}{switch_suffix}"
    f"{regex_suffix}{nxargs_suffix}{rep_suffix}_branch_visit_count.csv"
)


cov_result_filename = (
    f"/TowardImprovingSE/klee_output_folder/cov_results/"
    f"{tool_suffix}_{program}{switch_suffix}"
    f"{regex_suffix}{nxargs_suffix}_cov_result.csv"
)


cov_result_file = cov_result_filename

os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
os.makedirs(os.path.dirname(function_csv_filename), exist_ok=True)
os.makedirs(os.path.dirname(cov_result_file), exist_ok=True)

ktest_files_list = find_ktest_files(src_dir)

print(len(ktest_files_list))

coverage_list = []
branch_visit_count = {}
function_data = []

print(f"Processing program: {program}")
os.chdir(gcov_dir)

if not os.path.exists(arguments_dir):
    os.makedirs(arguments_dir)

os.system(rm_cmd)

for i, file_path in enumerate(ktest_files_list):
    os.chdir(gcov_dir)
    cmd = replay_cmd + file_path + f' 2> {arguments_dir}/arguments{i}.txt'
    os.system(cmd)
    if program =='sed':
        os.chdir(os.path.dirname(gcov_dir))
        
    os.system(cov_cmd)

    if i == 0:
        start_time = os.path.getctime(file_path)

    elapsed_time = round(os.path.getctime(file_path) - start_time, 3)
    coverage = cal_coverage("cov_result")
    coverage_list.append(coverage)

gcov_dir_upper = os.path.dirname(gcov_dir)
if program == 'gawk':
    gcov_dir_upper = gcov_dir
    
for root, dirs, files in os.walk(gcov_dir_upper):
    for file in files:
        if file.endswith('.gcov'):
            ktest_gcov = os.path.join(root, file)
            cnt_switch = count_switches_with_nonzero_branch(ktest_gcov)
            switch_counts.append(cnt_switch)
            branch_visit_count = branch_handler(ktest_gcov, branch_visit_count, function_data)

if os.path.exists(csv_filename):
    os.remove(csv_filename)

with open(csv_filename, 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(['Branch Identifier', 'Visit Count'])
    for branch, count in branch_visit_count.items():
        csv_writer.writerow([branch, count])

if switch_counts:
    average_switch = sum(switch_counts) / len(switch_counts)
else:
    average_switch = 0.0


total_coverage = coverage_list[-1]

if os.path.exists(cov_result_file):
    temp_file = NamedTemporaryFile('w', newline='', delete=False)
    with open(cov_result_file, 'r', newline='') as rf, temp_file:
        reader = csv.DictReader(rf)
        fieldnames = reader.fieldnames or []
        if 'Average Taken Switch' not in fieldnames:
            fieldnames.append('Average Taken Switch')
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            if not (
                row['Tool'] == tool_suffix and
                row['Program'] == program and
                row['Repetition'] == rep_suffix
            ):
                writer.writerow(row)

        writer.writerow({
            'Tool': tool_suffix,
            'Program': program,
            'Repetition': rep_suffix,
            'Total Coverage': total_coverage,
            'Average Taken Switch': round(average_switch, 2)
        })
    shutil.move(temp_file.name, cov_result_file)

else:
    with open(cov_result_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Tool', 'Program', 'Repetition', 'Total Coverage', 'Average Taken Switch'])
        writer.writerow([tool_suffix, program, rep_suffix, total_coverage, round(average_switch, 2)])

print(f"Coverage result updated in {cov_result_file}")  
import os, argparse, time, signal, json, re, csv, math
import subprocess as sp
import math
import pickle
import json


parser = argparse.ArgumentParser(description='Run KLEE replay and calculate coverage for specified programs.')
parser.add_argument('--testcase_file', type=str, required=True, help='Testcase file input.')
parser.add_argument('--gcov_num', type=int, required=True, help='Number to replace in the gcov directory path.')
dangerous = re.compile(
    r'\b(rm|chmod|chown|mv|rmdir|unlink)\b|'               
    r'\bsed\b.*?\s+-i(\S*)?\s+.*(\*|\.\/sed|\b[a-zA-Z0-9._-]*sed\b)'  


args = parser.parse_args()

# Load configuration from JSON file
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config_data = json.load(f)
class TimeoutException(Exception):
    pass

def handler(signum, frame):
    raise TimeoutException()

# Function to handle branches from .gcov files and count visitations
# Additionally extracts function coverage data for aggregation
def branch_handler(ktest_gcov, branch_visit_count, function_data):
    with open(ktest_gcov, 'r', errors='ignore') as f:
        lines = f.readlines()

    condition_visit_count = 0
    src_name = ""
    line_number = 0

    # 현재 처리 중인 함수 블록 관련 변수
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

    return branch_visit_count

def save_branch_visit_count_to_csv(branch_visit_count, csv_filename):
    with open(csv_filename, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['Branch Identifier', 'Visit Count'])
        for branch, count in branch_visit_count.items():
            csv_writer.writerow([branch, count])
    
def run_testcase(file_name, branch_visit_count, function_data):
    with open(file_name, 'r') as f:
        testcases = [l.strip() for l in f.readlines()]
    os.chdir(gcov_dir)
    print(rm_cmd)
    os.system(rm_cmd)
    bc_list = []
    print("----------------Run Test-Cases-------------------------------------")
    print("-------------------------------------------------------------------")
    for i, tc in enumerate(testcases):
        # os.system(rm_cmd)
        if dangerous.search(tc):
            print(f"Skipping potentially dangerous test case: {tc!r}")
            continue
        os.chdir(gcov_dir)
        print(tc)
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(3)  
        try:
            _ = sp.run(tc, stdout=sp.PIPE, stderr=sp.PIPE, shell=True, check=True)
        except TimeoutException:
            print("Process took too long, moving to the next test case")
        except sp.CalledProcessError as e:
            print(f"An error occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            signal.alarm(0) 
    
        gcov_file = "cov_result"
        running = os.getcwd()
        os.system(cov_cmd)
        print("-------------------------------------------------------------------")
        bc_list.append(cal_coverage(gcov_file))
            
    for root, dirs, files in os.walk(gcov_dir):
        for file in files:
            if file.endswith('.gcov'):
                ktest_gcov = os.path.join(root, file)
                branch_visit_count = branch_handler(ktest_gcov, branch_visit_count,function_data)
        
    return bc_list

def cal_coverage(cov_file):
    coverage=0
    total_coverage=0
    with open(cov_file, 'r') as f:
        lines= f.readlines()
        for line in lines:
            if "Taken at least" in line:
                data=line.split(':')[1]
                percent=float(data.split('% of ')[0])
                total_branches=float((data.split('% of ')[1]).strip())
                covered_branches=int(percent*total_branches/100)
                
                coverage=coverage + covered_branches    
                total_coverage=total_coverage + total_branches 
    print("----------------Results--------------------------------------------")
    print("-------------------------------------------------------------------")
    print("The number of covered branches: "+str(coverage))
    print("The number of total branches: "+str(int(total_coverage)))
    print("-------------------------------------------------------------------")
    return coverage



testcase_file = args.testcase_file
gcov_num = args.gcov_num
program = next((key for key in config_data if key in testcase_file.lower()), 'unknown')

settings = config_data[program]
tool_suffix = 'human'
gcov_dir = settings['gcov_dir'].replace('<gcov_num>', str(gcov_num))

rm_cmd = settings['rm_cmd']
replay_cmd = settings['replay_cmd']
cov_cmd = settings['cov_cmd']


if program == 'unknown':
    print("Error: Program name could not be determined from src_dir.")
    exit(1)


csv_filename = f"/TowardImprovingSE/klee_output_folder/{program}/branch_visit_count/{tool_suffix}_{program}_branch_visit_count.csv"
cov_result_filename = (
    f"/TowardImprovingSE/klee_output_folder/cov_results/"
    f"{tool_suffix}_{program}_cov_result.csv"
)
os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
os.makedirs(os.path.dirname(cov_result_file), exist_ok=True)
coverage_list = []
branch_visit_count = {}
function_data = []

print(f"Processing program: {program}")
os.chdir(gcov_dir)

os.system(rm_cmd)

bc_result = run_testcase(testcase_file, branch_visit_count, function_data)

if os.path.exists(csv_filename):
    os.remove(csv_filename)

with open(csv_filename, 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(['Branch Identifier', 'Visit Count'])
    for branch, count in branch_visit_count.items():
        csv_writer.writerow([branch, count])

with open(cov_result_filename, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Tool', 'Program', 'Total Coverage'])
    writer.writerow(['Human', program, bc_result[-1]])



print(f"Branch visit count saved to {csv_filename}")
print(f"Coverage result updated in {cov_result_file}") 

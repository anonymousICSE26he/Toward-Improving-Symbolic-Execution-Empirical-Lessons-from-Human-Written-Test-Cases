# Toward Improving Symbolic Execution: Empirical Lessons from Human‑Written Test Cases

**Repository for reproducibility – symbolic executors' test cases and human's.**

* **LLVM version**: 6.0.0
* **Coverage metrics**: Branch coverage and the number of `switch` statements were computed using `gcov`.
* **Branch coverage across all methods** (measured with `gcov`) is identical to the attached JPEG: `All_tool_branch_coverage.jpeg`. Per–test case values that underlie the figure are the same as those reported in `docs/All_tools_branch_coverage.pdf`.
* **Test case data download**: Available via Dropbox – [https://www.dropbox.com/scl/fo/vs0gbyv3iyqvxk5be5t0e/ADumGmvWRze-4sAhgKAppos?rlkey=vc4x2qzhon8cim5au3d4qqmqh\&st=lrf2newr\&dl=0](https://www.dropbox.com/scl/fo/vs0gbyv3iyqvxk5be5t0e/ADumGmvWRze-4sAhgKAppos?rlkey=vc4x2qzhon8cim5au3d4qqmqh&st=lrf2newr&dl=0)

![Branch coverage across all methods](All_tool_branch_coverage.jpeg)

---

## Reproduction Steps (to obtain branch coverage and other experimental data)

1. **Download test cases**
   Download the test case archive from the Dropbox link above and extract it. A typical layout is:

   ```text
   testcases/
     ICSE2026Data/
       featmaker_experiments/24hours_rep1/diff/result/
       featmaker_experiments/24hours_rep2/...
       homi_experiments/experiments/result_24hours_rep1/1homi_diff_nurs:cpicnt_tc_dir/
       symtuner_experiments/benchmarks/24hours_rep1/KLEE_SymTuner_diff
       klee-aaqc_experiments/result/24hours_rep1/diff
       ...
   ```

2. **Clone this repository and rename the folder to `TowardImprovingSE`**

   ```bash
   git clone <THIS_REPO_URL>
   mv Toward-Improving-Symbolic-Execution-Empirical-Lessons-from-Human-Written-Test-Cases TowardImprovingSE
   cd TowardImprovingSE
   ```

3. **Build benchmarks**

   ```bash
   bash benchmarks/make-benchmark.sh
   ```

4. **Replay symbolic‑executor test cases**
   Use `tools_replay.py` for each tool and repetition (`rep1`–`rep5`).

   * **FeatMaker**: set `--src_dir` **to the `result` folder**.

     ```bash
     python3 tools_replay.py \
       --src_dir=testcases/ICSE2026Data/featmaker_experiments/24hours_rep1/diff/result \
       --gcov_num=1
     ```
   * **Other symbolic executors (HOMI, SymTuner, KLEE‑aaqc, …)**: set `--src_dir` **up to the program folder** (do **not** include `result`).

     ```bash
     python3 tools_replay.py \
       --src_dir=testcases/ICSE2026Data/symtuner_experiments/benchmarks/24hours_rep1/KLEE_SymTuner_diff \
       --gcov_num=1
     ```
   * Repeat for `rep1` through `rep5` by changing the path accordingly.

5. **Replay human test cases**

   ```bash
   python3 human_replay.py --testcase_file=testcases/diff_testcases/merged_testcases.txt --gcov_num=2
   ```

6. **Draw the overall branch‑coverage comparison plot**
   After all replays finish, run:

   ```bash
   python3 draw_bc_histogram.py
   ```

   This produces a plot that matches the JPEG shown above.

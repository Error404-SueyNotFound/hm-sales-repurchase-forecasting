"""Full entry point: run this file in Spyder or the project virtual environment.

Generate model scores, charts, and analysis reports in a new numbered run directory.
This script does not interact with or close the Spyder application."""
import contextlib
import sys
import traceback
from pathlib import Path

# Load project modules independently of the current Spyder working directory.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest import next_output_dir, run_backtest
from analyze_forecasts import analyze


class Tee:
    """Write console output to both the original stream and a persistent log file."""
    def __init__(self, original, log):
        self.original, self.log = original, log

    def write(self, text):
        self.original.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self):
        self.original.flush()
        self.log.flush()


def main():
    output = next_output_dir()
    with (output / "run_log.txt").open("w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            try:
                run_backtest(output)
                analyze(output)
                print("\n全部完成。结果保存在：", output)
            except Exception:
                traceback.print_exc()
                raise


if __name__ == "__main__":
    main()

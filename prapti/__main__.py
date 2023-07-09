"""
    Invoke tool for generating markdown chat responses

    Usage: `python -m prapti`
"""
import time
start_time = time.perf_counter() # start timing execution as early as possible
import sys

from . import tool

def timed_main():
    exit_code = tool.main()
    end_time = time.perf_counter()
    total_time = (end_time - start_time)
    print(f"Total execution time: {total_time:.6f} seconds")
    return exit_code

if __name__ == "__main__":
    exit_code = timed_main()
    sys.exit(exit_code)

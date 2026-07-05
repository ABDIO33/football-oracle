import sys
import io

# Force UTF-8 encoding for all output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Also fix logging
import logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Now import and run the actual script
import runpy
import os

script = sys.argv[1]
sys.argv = sys.argv[1:]  # pass rest of args

# Set env
os.environ['PYTHONIOENCODING'] = 'utf-8'

runpy.run_path(script, run_name='__main__')

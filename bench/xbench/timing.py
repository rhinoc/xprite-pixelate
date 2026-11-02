"""Repeated single-worker timing on the existing speed suite. CLI and worker paths differ."""
import json, os, statistics, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run
import methods

os.environ['RAYON_NUM_THREADS'] = '1'
cases = run.build('speed', None)
results = {}
for name in ('xprite', 'spritefusion'):
    method = methods.METHODS[name]()
    rows = []
    try:
        # Explicit warmup of the worker, binary, and data path.
        warm = np.load(run.CACHE / 'speed' / (cases[0]['key'] + '.npz'))['img']
        initial = method.run(warm)
        if initial.error: raise RuntimeError(initial.error)
        for i, case in enumerate(cases):
            img = np.load(run.CACHE / 'speed' / (case['key'] + '.npz'))['img']
            samples = []
            for rep in range(3):
                start = time.perf_counter(); r = method.run(img); wall = time.perf_counter() - start
                samples.append({'wall_s': wall, 'reported_s': r.seconds, 'error': r.error, 'refused': r.refused})
            rows.append({'key': case['key'], 'side': case['side'], 'samples': samples})
            if (i+1)%10 == 0: print(name, i+1, '/', len(cases), flush=True)
    finally:
        method.close()
    results[name] = rows
    (run.RESULTS / 'speed' / 'timing-repeated.json').write_text(json.dumps(results, indent=2))

import sys
import time

print("[1] Python started:", sys.version, flush=True)
t0 = time.time()

try:
    import numpy as np
    print(f"[2] numpy loaded in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print("[2] numpy error:", e, flush=True)

t1 = time.time()
try:
    import scipy
    print(f"[3] scipy loaded in {time.time()-t1:.2f}s", flush=True)
except Exception as e:
    print("[3] scipy error:", e, flush=True)

t2 = time.time()
try:
    import sklearn
    print(f"[4] sklearn loaded in {time.time()-t2:.2f}s", flush=True)
except Exception as e:
    print("[4] sklearn error:", e, flush=True)

t3 = time.time()
try:
    from sklearn.ensemble import IsolationForest
    print(f"[5] IsolationForest loaded in {time.time()-t3:.2f}s")
    clf = IsolationForest(n_estimators=50, random_state=42, n_jobs=1)
    X = [[1.0, 2.0], [1.1, 2.1], [0.9, 1.9], [5.0, 5.0]]
    clf.fit(X)
    scores = clf.decision_function([[1.0, 2.0], [5.0, 5.0]])
    preds = clf.predict([[1.0, 2.0], [5.0, 5.0]])
    print(f"[6] Fit and predict completed in {time.time()-t3:.2f}s: scores={scores}, preds={preds}")
except Exception as e:
    print("[5] IsolationForest error:", e)

print("TOTAL TIME:", time.time()-t0)

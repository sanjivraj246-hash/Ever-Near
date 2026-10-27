import subprocess
import sys
import time

# Ensure immediate stdout flushing
sys.stdout.reconfigure(line_buffering=True)

test_files = [
    "test_phase5_database.py",
    "test_combined_phase_d.py",
    "test_combined_phase_c.py",
    "test_combined_phase_b.py",
    "verify_combined_phase_a.py",
    "test_auth.py",
    "test_communication_system.py",
    "test_family_connection.py",
    "test_real_functional_system.py",
    "test_user_journey_simulation.py",
    "test_gate_e2e_sequence.py",
    "test_phase4_backend.py",
    "test_e2e.py",
    "verify_live_system.py",
    "test_multi_user_production.py",
    "test_auth_upgrade.py",
    "test_checkin_flow.py",
    "test_final_e2e_journey.py",
    "verify_user_mandatory_flows.py"
]

results = []
passed_count = 0
failed_count = 0

print("="*70)
print("EVER NEAR AI: COMPREHENSIVE TEST SUITE EXECUTION ON POSTGRESQL 18")
print("="*70)

for tf in test_files:
    t0 = time.time()
    res = subprocess.run(
        [sys.executable, tf],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    dt = time.time() - t0
    if res.returncode == 0:
        results.append((tf, "PASS", dt, None))
        passed_count += 1
        print(f"  [PASS] {tf:<32} ({dt:.2f}s)")
    else:
        results.append((tf, "FAIL", dt, res.stderr or res.stdout))
        failed_count += 1
        print(f"  [FAIL] {tf:<32} ({dt:.2f}s)")
        print(f"         Error: {(res.stderr or res.stdout)[-300:].strip()}")

print("="*70)
print(f"SUMMARY: {passed_count} suites PASSED, {failed_count} suites FAILED out of {len(test_files)}")
print("="*70)

sys.exit(0 if failed_count == 0 else 1)

"""Argon2id Benchmark Script for CivicLens Authentication.

Measures hash verification latency on current hardware (Windows 11, Intel i3)
and recommends parameters targeting ~150 to 500 ms for DoS resistance vs responsiveness.
"""

import time
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

def benchmark_parameters(time_cost: int, memory_cost: int, parallelism: int, rounds: int = 5):
    ph = PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=32,
        salt_len=16,
    )
    test_password = "CorrectHorseBatteryStaple123!"
    
    # Measure hash creation
    hash_times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        hashed = ph.hash(test_password)
        hash_times.append((time.perf_counter() - t0) * 1000)
        
    # Measure verification
    verify_times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        ph.verify(hashed, test_password)
        verify_times.append((time.perf_counter() - t0) * 1000)
        
    avg_hash = sum(hash_times) / rounds
    avg_verify = sum(verify_times) / rounds
    return avg_hash, avg_verify

def main():
    print("=" * 60)
    print("CivicLens Argon2id Password Hashing Benchmark")
    print("=" * 60)
    
    candidates = [
        # (time_cost, memory_cost_kib, parallelism)
        (2, 65536, 1),
        (3, 65536, 1),
        (1, 65536, 1),
        (2, 32768, 1),
        (3, 32768, 1),
    ]
    
    best_config = None
    best_diff = 999999
    target_ms = 250.0  # Sweet spot between 150ms and 500ms
    
    print(f"{'TimeCost':<10} {'Mem(KiB)':<12} {'Parallel':<10} {'Hash(ms)':<12} {'Verify(ms)':<12}")
    print("-" * 60)
    
    for tc, mc, p in candidates:
        avg_hash, avg_verify = benchmark_parameters(tc, mc, p)
        print(f"{tc:<10} {mc:<12} {p:<10} {avg_hash:<12.2f} {avg_verify:<12.2f}")
        
        diff = abs(avg_verify - target_ms)
        if diff < best_diff and 100 <= avg_verify <= 500:
            best_diff = diff
            best_config = (tc, mc, p, avg_verify)
            
    print("-" * 60)
    if best_config:
        tc, mc, p, v_time = best_config
        print(f"Recommended Configuration on this machine:")
        print(f"  time_cost = {tc}")
        print(f"  memory_cost = {mc} KiB ({mc//1024} MB)")
        print(f"  parallelism = {p}")
        print(f"  Average Verify Latency: {v_time:.2f} ms (Target 150-500 ms)")
    else:
        print("Defaulting to safe baseline: time_cost=3, memory_cost=65536, parallelism=1")

if __name__ == "__main__":
    main()

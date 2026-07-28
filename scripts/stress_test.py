#!/usr/bin/env python3
"""
Stress Testing Script for Tesserae V6 Search Concurrency

This script simulates multiple concurrent heavy searches hitting the Tesserae backend
to verify that the concurrency gate (SearchSlot and memory checks) works as expected.

Usage:
  python3 scripts/stress_test.py [num_concurrent] [--url URL]

Examples:
  python3 scripts/stress_test.py 5                          # 5 searches against localhost:8080
  python3 scripts/stress_test.py 8 --url https://marvin.example.com  # 8 searches against Marvin

Prerequisites:
  - The Tesserae backend must be running at the target URL
  - You must have some texts in the database. The script attempts to search for
    "lucan.bellum_civile.part.1" against itself.
"""

import sys
import time
import argparse
import requests
import threading

DEFAULT_URL = "http://localhost:8080"

# Sample search payload
PAYLOAD = {
    "source": "lucan.bellum_civile.part.1",
    "target": "lucan.bellum_civile.part.1",
    "language": "la",
    "settings": {
        "match_type": "fusion",
        "min_matches": 2
    }
}


def run_search(thread_id, search_url, results):
    """Run a single search and record its result."""
    print(f"[Thread {thread_id}] Starting search...")
    start_time = time.time()
    
    try:
        response = requests.post(search_url, json=PAYLOAD, timeout=600)
        
        elapsed = time.time() - start_time
        if response.status_code == 200:
            print(f"[Thread {thread_id}] SUCCESS in {elapsed:.1f}s")
            results.append({"thread": thread_id, "status": "success", "time": elapsed})
        else:
            print(f"[Thread {thread_id}] ERROR {response.status_code} in {elapsed:.1f}s: {response.text[:100]}")
            results.append({"thread": thread_id, "status": "error", "code": response.status_code, "time": elapsed})
            
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        print(f"[Thread {thread_id}] FAILED in {elapsed:.1f}s: {e}")
        results.append({"thread": thread_id, "status": "exception", "time": elapsed})


def main():
    parser = argparse.ArgumentParser(description="Stress test Tesserae V6 search concurrency")
    parser.add_argument("num_concurrent", nargs="?", type=int, default=5,
                        help="Number of concurrent searches to launch (default: 5)")
    parser.add_argument("--url", default=DEFAULT_URL,
                        help=f"Base URL of the Tesserae server (default: {DEFAULT_URL})")
    args = parser.parse_args()

    search_url = f"{args.url}/api/search"
    num_concurrent = args.num_concurrent

    print(f"Target server: {args.url}")
    print(f"Starting stress test with {num_concurrent} concurrent searches...")
    
    threads = []
    results = []
    
    start_time = time.time()
    
    # Launch threads
    for i in range(num_concurrent):
        t = threading.Thread(target=run_search, args=(i+1, search_url, results))
        threads.append(t)
        t.start()
        # Small stagger to simulate organic traffic
        time.sleep(0.1)
        
    # Wait for all threads to complete
    for t in threads:
        t.join()
        
    total_elapsed = time.time() - start_time
    
    print("\n" + "="*40)
    print("STRESS TEST RESULTS")
    print("="*40)
    print(f"Target:              {args.url}")
    print(f"Total time elapsed:  {total_elapsed:.1f}s")
    
    successes = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]
    exceptions = [r for r in results if r["status"] == "exception"]
    
    print(f"Successful searches: {len(successes)}")
    print(f"API Errors:          {len(errors)}")
    print(f"Connection Failures: {len(exceptions)}")
    
    print("\nNote: To observe queue behavior in real-time, open the Admin Performance Tab")
    print("while this script is running. You should see active searches hit the max limit,")
    print("and subsequent requests waiting in the queue.")

if __name__ == "__main__":
    main()

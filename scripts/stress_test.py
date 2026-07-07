#!/usr/bin/env python3
"""
Stress Testing Script for Tesserae V6 Search Concurrency

This script simulates multiple concurrent heavy searches hitting the Tesserae backend
to verify that the concurrency gate (SearchSlot and memory checks) works as expected.

Usage:
  python3 scripts/stress_test.py [num_concurrent]

Prerequisites:
  - The Tesserae backend must be running locally (e.g. at http://localhost:5000)
  - You must have some texts in the database. The script attempts to search for "test"
    in the source text "lucan.bellum_civile.part.1".
"""

import sys
import time
import requests
import threading

# Adjust this URL to point to your local development server if different
BASE_URL = "http://localhost:8080"
SEARCH_URL = f"{BASE_URL}/api/search"

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


def run_search(thread_id, results):
    """Run a single search and record its result."""
    print(f"[Thread {thread_id}] Starting search...")
    start_time = time.time()
    
    try:
        # We use a POST request since /api/search takes search parameters in the body.
        # Note: Depending on whether the search route is standard or SSE streaming, 
        # this script tests the standard connection capacity. 
        # For actual SSE streams, you'd need a client that supports SSE to observe "queued" events.
        response = requests.post(SEARCH_URL, json=PAYLOAD, timeout=600)
        
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
    num_concurrent = 5
    if len(sys.argv) > 1:
        try:
            num_concurrent = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 stress_test.py [num_concurrent]")
            sys.exit(1)

    print(f"Starting stress test with {num_concurrent} concurrent searches...")
    
    threads = []
    results = []
    
    start_time = time.time()
    
    # Launch threads
    for i in range(num_concurrent):
        t = threading.Thread(target=run_search, args=(i+1, results))
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
    print(f"Total time elapsed: {total_elapsed:.1f}s")
    
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

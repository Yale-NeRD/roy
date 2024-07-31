import pytest
import ray
import time
import threading

from test_utils import *
from roy_on_ray import RoySet

@pytest.fixture(scope="module", autouse=True)
def ray_init_shutdown():
    ray_fresh_start()
    yield
    time.sleep(1)
    print("Shutting down Ray...", flush=True)
    ray_shutdown()

@pytest.fixture
def royset():
    return RoySet()

def test_add(royset):
    royset.add(1)
    assert 1 in royset
    royset.flush()

def test_len(royset):
    assert len(royset) == 0
    royset.add(1)
    assert len(royset) == 1
    royset.flush()

def test_contains(royset):
    royset.add(1)
    assert 1 in royset
    assert 2 not in royset
    royset.flush()

def test_remove(royset):
    royset.add(1)
    royset.remove(1)
    assert 1 not in royset
    royset.flush()

def test_repr(royset):
    royset.add(1)
    assert repr(royset) == "RoySet({1})"
    royset.flush()

def test_multiple_add(royset):
    royset.add(1)
    royset.add(2)
    assert 1 in royset
    assert 2 in royset
    royset.flush()

def test_add_duplicate(royset):
    royset.add(1)
    royset.add(1)
    assert len(royset) == 1
    royset.flush()

def test_multiple_remove(royset):
    royset.add(1)
    royset.add(2)
    royset.remove(1)
    assert 1 not in royset
    assert 2 in royset
    royset.flush()

def test_concurrent_access(royset):
    num_threads = 5
    num_entries_per_thread = 10

    def insert_entries(start_index):
        with royset:
            print(f"Thread {start_index} started", flush=True)
            for i in range(start_index, start_index + num_entries_per_thread):
                royset.add(i)
            print(f"Thread {start_index} inserted {num_entries_per_thread} entries | length: {len(royset)}", flush=True)
            royset.flush()
        print(f"Thread {start_index} done", flush=True)

    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=insert_entries, args=(i * num_entries_per_thread,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print(f"Length: {len(royset)}", flush=True)
    assert len(royset) == num_threads * num_entries_per_thread
    royset.flush()

def test_aggressive_concurrent_access_with_overlap(royset):
    num_threads = 5
    num_entries_per_thread = 10
    iterations = 10
    overlap_factor = 3  # Determines the amount of overlap between threads
    unique_entries_per_iteration = num_entries_per_thread * overlap_factor

    def insert_entries(start_index):
        for iteration in range(iterations):
            with royset:
                print(f"Thread {start_index} iteration {iteration} started", flush=True)
                for i in range(start_index, start_index + num_entries_per_thread):
                    royset.add(i % unique_entries_per_iteration + iteration * num_entries_per_thread * num_threads)
                print(f"Thread {start_index} iteration {iteration} inserted {num_entries_per_thread} entries | length: {len(royset)}", flush=True)
                royset.flush()
            print(f"Thread {start_index} iteration {iteration} done", flush=True)

    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=insert_entries, args=(i * num_entries_per_thread,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Calculate expected length accounting for overlapping
    expected_length = unique_entries_per_iteration * iterations
    print(f"Length: {len(royset)}", flush=True)
    assert len(royset) == expected_length
    royset.flush()

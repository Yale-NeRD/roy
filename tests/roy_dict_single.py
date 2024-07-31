import pytest
import ray
import time
import threading

from test_utils import *
from roy_on_ray import RoyDict

@pytest.fixture(scope="module", autouse=True)
def ray_init_shutdown():
    ray_fresh_start()
    yield
    time.sleep(1)
    ray.shutdown()

# == TESTS ==
def test_setitem():
    roydict = RoyDict()
    roydict['key1'] = 'value1'
    assert roydict['key1'] == 'value1'
    roydict.flush()

def test_len():
    roydict = RoyDict()
    assert len(roydict) == 0
    roydict['key1'] = 'value1'
    assert len(roydict) == 1
    roydict.flush()

def test_contains():
    roydict = RoyDict()
    roydict['key1'] = 'value1'
    assert 'key1' in roydict
    assert 'key2' not in roydict
    roydict.flush()

def test_delitem():
    roydict = RoyDict()
    roydict['key1'] = 'value1'
    del roydict['key1']
    assert 'key1' not in roydict
    roydict.flush()

def test_clear():
    roydict = RoyDict()
    roydict['key1'] = 'value1'
    roydict['key2'] = 'value2'
    roydict.clear()
    assert len(roydict) == 0
    roydict.flush()

def test_update_value():
    roydict = RoyDict()
    roydict['key1'] = 'value1'
    roydict['key1'] = 'value2'
    assert roydict['key1'] == 'value2'
    roydict.flush()

def test_non_existent_key():
    roydict = RoyDict()
    try:
        roydict['nonexistent']
        assert False, "KeyError not raised"
    except KeyError:
        pass
    roydict.flush()

def test_large_insertions():
    roydict = RoyDict()
    num_entries = 10000
    for i in range(num_entries):
        roydict[f'key{i}'] = f'value{i}'
    assert len(roydict) == num_entries
    for i in range(num_entries):
        assert roydict[f'key{i}'] == f'value{i}'
    roydict.flush()

# == multi threading tests ==
def test_concurrent_access():
    roydict = RoyDict()
    num_threads = 5
    num_entries_per_thread = 10

    def insert_entries(start_index):
        with roydict: 
            print(f"Thread {start_index} started", flush=True)
            for i in range(start_index, start_index + num_entries_per_thread):
                roydict[i] = f'value{i}'
            print(f"Thread {start_index} inserted {num_entries_per_thread} entries | length: {len(roydict)}", flush=True)
            roydict.flush()
        print(f"Thread {start_index} done", flush=True)

    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=insert_entries, args=(i * num_entries_per_thread,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print(f"Length: {len(roydict)}", flush=True)
    assert len(roydict) == num_threads * num_entries_per_thread
    roydict.flush()


def test_concurrent_taking_turn():
    roydict = RoyDict()
    num_threads = 5
    num_entries_per_thread = 10
    num_round = 2
    barrier = threading.Barrier(num_threads)

    def insert_entries(start_index, num_round, data_per_round):
        for round in range(num_round):
            with roydict: 
                print(f"Thread {start_index} started", flush=True)
                for i in range(start_index, start_index + num_entries_per_thread):
                    roydict[i + round * data_per_round] = f'value{i + round * data_per_round}'
                print(f"Thread {start_index} inserted {num_entries_per_thread} entries | length: {len(roydict)}", flush=True)
            barrier.wait()
        print(f"Thread {start_index} done", flush=True)

    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=insert_entries, args=(i * num_entries_per_thread, num_round, num_entries_per_thread * num_threads))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print(f"Length: {len(roydict)}", flush=True)
    assert len(roydict) == num_threads * num_entries_per_thread * num_round
    roydict.flush()

import pytest
import ray
import sys
import os
import time

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)
sys.path.append(parent_directory + '/cpproy')
sys.path.append(parent_directory + '/roytypes')

# from roytypes import RoySet, RoyList, remote, remote_worker
from roytypes import RoyList

@pytest.fixture(scope="module", autouse=True)
def ray_init_shutdown():
    ray.init(runtime_env={"py_modules": [parent_directory + "/roytypes"]})
    yield
    time.sleep(3)
    ray.shutdown()

@pytest.fixture
def roylist():
    # wait for the previous test to finish
    time.sleep(1)
    return RoyList()
    # TODO: Support for the multiple instances

def test_append(roylist):
    roylist.append(1)
    assert roylist[0] == 1

def test_len(roylist):
    assert len(roylist) == 0
    roylist.append(1)
    assert len(roylist) == 1

def test_contains(roylist):
    roylist.append(1)
    assert 1 in roylist
    assert 2 not in roylist

def test_remove(roylist):
    roylist.append(1)
    roylist.remove(1)
    assert 1 not in roylist

def test_clear(roylist):
    roylist.append(1)
    roylist.append(2)
    roylist.clear()
    assert len(roylist) == 0
import pytest
import ray
import time

from test_utils import *
from roy_on_ray import RoyList

@pytest.fixture(scope="module", autouse=True)
def ray_init_shutdown():
    ray_fresh_start()
    yield
    time.sleep(1)
    ray.shutdown()

@pytest.fixture
def roylist():
    return RoyList()
    # TODO: Support for the multiple instances

def test_append(roylist):
    roylist.append(1)
    assert roylist[0] == 1
    roylist.flush()

def test_len(roylist):
    assert len(roylist) == 0
    roylist.append(1)
    assert len(roylist) == 1
    roylist.flush()

def test_contains(roylist):
    roylist.append(1)
    assert 1 in roylist
    assert 2 not in roylist
    roylist.flush()

def test_remove(roylist):
    roylist.append(1)
    roylist.remove(1)
    assert 1 not in roylist
    roylist.flush()

def test_clear(roylist):
    roylist.append(1)
    roylist.append(2)
    roylist.clear()
    assert len(roylist) == 0
    roylist.flush()

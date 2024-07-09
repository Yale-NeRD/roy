import pytest
import ray
import time

from test_utils import ray_fresh_start
from roytypes import RoySet

@pytest.fixture(scope="module", autouse=True)
def ray_init_shutdown():
    ray_fresh_start()
    yield
    time.sleep(1)
    ray.shutdown()

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

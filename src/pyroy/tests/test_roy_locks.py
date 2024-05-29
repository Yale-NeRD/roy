import pytest
import multiprocessing
import time
import roy
from roy import connect, initialize_test_env, clean_test_env, Mutex, SharedMemorySingleton

ip_addr_str = "127.0.0.1:50017"

@pytest.fixture(scope="session", autouse=True)
def server():
    SharedMemorySingleton.reset_instance()
    server_process = initialize_test_env(ip_addr_str)
    yield server_process
    clean_test_env(server_process)

@roy.remote(lock=Mutex)
class RoyTestClass:
    def __init__(self, value=None):
        if value is not None:
            self.value = value
    def custom_ftn(self, arg):
        return arg

class TestMutexLocks:
    @pytest.fixture(autouse=True)
    def setup(self, server):
        connect(ip_addr_str)

    def test_my_class(self):
        handle_key = "test_roy_locks.test_handle"

        # I to M
        my_instance = RoyTestClass("initial_value")
        my_instance.lock()

        # M to I
        roy_handle = my_instance.roy_handle
        roy.set_remote_object(handle_key, roy_handle)
        print("roy_handle:", roy_handle)
        my_instance.unlock()

        # I to M and waiting
        def lock_and_update():
            roy_handle = roy.get_remote_object(handle_key)
            assert roy_handle is not None
            # get remote object with lock
            my_instance = roy.get_remote_object_with_lock(roy_handle)
            assert my_instance is not None
            assert my_instance.value == "initial_value"
            time.sleep(5)
            my_instance.value = "new_value"
            my_instance.unlock()
            print("Value updated to new_value")

        client_process = multiprocessing.Process(target=lock_and_update)
        client_process.start()
        time.sleep(1)

        # Try to get the object with lock and modify,
        # but it should be after unlock inside lock_and_update
        # Getting value without lock (non-blocking and get the stale value)
        my_instance = roy.get_remote_object(roy_handle)
        assert my_instance is not None
        assert my_instance.value == "initial_value"
        # Getting value with lock (blocking and get the up-to-date value)
        my_instance = roy.get_remote_object_with_lock(roy_handle)
        assert my_instance is not None
        assert my_instance.value == "new_value"
        my_instance.value = "new_value_2"
        my_instance.unlock()

        # final checks
        roy_handle = roy.get_remote_object(handle_key)
        assert roy_handle is not None
        my_instance = roy.get_remote_object_with_lock(roy_handle)
        assert my_instance is not None
        assert my_instance.value == "new_value_2"
        
if __name__ == '__main__':
    pytest.main()

import pytest
import multiprocessing
import roy
import time
from roy import connect, initialize_test_env, clean_test_env, Mutex, SharedMemorySingleton

ip_addr_str = "127.0.0.1:50016"

@pytest.fixture(scope="module", autouse=True)
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

class TestMultipleClients:
    @pytest.fixture(autouse=True)
    def setup(self, server):
        connect(ip_addr_str)

    def test_my_class(self):
        handle_key = "test_roy_multiclient.test_handle"
        def client_1():
            my_instance = RoyTestClass("initial_value")
            my_instance.lock()
            assert str(my_instance) != ""
            assert my_instance.value == "initial_value"
            my_instance.value = "new_value"
            my_float = roy.remote(list([3.14]))
            my_instance.lists = [my_float, 2, roy.remote(list([123]))]
            # test if the access to non-existing attribute raises AttributeError
            with pytest.raises(AttributeError):
                print(my_instance.non_existing_value)
            assert my_instance.value == "new_value"
            roy_handle = my_instance.roy_handle
            roy.set_remote_object(handle_key, roy_handle)
            print("roy_handle:", roy_handle)
            my_instance.unlock()

        def client_2():
            my_instance = RoyTestClass()
            # print(my_instance)
            # print(my_instance.key)
            # print(my_instance.value)
            with pytest.raises(AttributeError):
                my_instance.value

        def client_3():
            # getting handle, assuming it is already set
            # and others do not modify this value (i.e., no lock)
            roy_handle = roy.get_remote_object(handle_key)
            assert roy_handle is not None
            # get remote object with lock
            my_instance = roy.get_remote_object_with_lock(roy_handle)
            assert my_instance is not None
            assert my_instance.value == "new_value"
            assert my_instance.custom_ftn("arg2") == "arg2"
            assert my_instance.lists[0] == [3.14]
            assert my_instance.lists[2][0] == 123
            print(my_instance.lists)
            my_instance.unlock()

        client_process = multiprocessing.Process(target=client_1)
        client_process.start()
        time.sleep(2)
        client_process = multiprocessing.Process(target=client_2)
        client_process.start()
        time.sleep(2)
        client_process = multiprocessing.Process(target=client_3)
        client_process.start()
        time.sleep(2)
        client_process.join()
        # final checks
        roy_handle = roy.get_remote_object(handle_key)
        assert roy_handle is not None
        my_instance = roy.get_remote_object_with_lock(roy_handle)
        assert my_instance is not None
        my_float = my_instance.lists[2].lock()
        assert my_instance.lists[0][0] == 3.14
        assert my_instance.lists[2][0] == 123
        print("TestMultipleClients done")

if __name__ == '__main__':
    pytest.main()

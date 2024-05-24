import pytest
import multiprocessing
import roy
from roy import connect, start_server, stop_server
import time

ip_addr_str = "127.0.0.1:50016"

def initialize_env():
    # start server in a separate process
    server_process = multiprocessing.Process(target=start_server, args=(ip_addr_str,))
    server_process.start()
    time.sleep(1) # wait for the server to start
    return server_process

def clean_env(server_process):
    stop_server()
    server_process.terminate()

@pytest.fixture(scope="session", autouse=True)
def server():
    server_process = initialize_env()
    yield server_process
    clean_env(server_process)

@roy.remote
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
        handle_key = "test_roy_multiplient.test_handle"
        def client_1():
            my_instance = RoyTestClass("initial_value")
            assert str(my_instance) != ""
            assert my_instance.value == "initial_value"
            my_instance.value = "new_value"
            # test if the access to non-existing attribute raises AttributeError
            with pytest.raises(AttributeError):
                my_instance.non_existing_value
            assert my_instance.value == "new_value"
            roy_handle = my_instance.roy_handle
            roy.set_remote_object(handle_key, roy_handle)
            print("roy_handle:", roy_handle)

        def client_2():
            my_instance = RoyTestClass()
            # print(my_instance)
            # print(my_instance.key)
            # print(my_instance.value)
            with pytest.raises(AttributeError):
                my_instance.value

        def client_3():
            roy_handle = roy.get_remote_object(handle_key)
            assert roy_handle is not None
            my_instance = roy.get_remote(roy_handle)
            assert my_instance is not None
            assert my_instance.value == "new_value"
            assert my_instance.custom_ftn("arg2") == "arg2"

        client_process = multiprocessing.Process(target=client_1)
        client_process.start()
        time.sleep(2)
        client_process = multiprocessing.Process(target=client_2)
        client_process.start()
        time.sleep(2)
        client_process = multiprocessing.Process(target=client_3)
        client_process.start()
        time.sleep(2)

if __name__ == '__main__':
    pytest.main()

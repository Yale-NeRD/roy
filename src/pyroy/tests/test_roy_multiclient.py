import pytest
import multiprocessing
import roy
from roy import connect, start_server, stop_server, SharedMemorySingleton
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

class TestMultipleClients:
    @pytest.fixture(autouse=True)
    def setup(self, server):
        connect(ip_addr_str)

    def test_my_class(self):
        @roy.remote
        class TestClass:
            def __init__(self, value=None):
                if value is not None:
                    self.value = value
            def custom_ftn(self, arg):
                return arg
        def client_1():
            my_instance = TestClass("initial_value")
            assert str(my_instance) != ""
            assert my_instance.value == "initial_value"
            my_instance.value = "new_value"
            # test if the access to non-existing attribute raises AttributeError
            with pytest.raises(AttributeError):
                my_instance.non_existing_value
            assert my_instance.value == "new_value"

        def client_2():
            my_instance = TestClass()
            # print(my_instance)
            # print(my_instance.key)
            # print(my_instance.value)
            with pytest.raises(AttributeError):
                my_instance.value
            assert my_instance.roy_handle == "roy_ftn.TestClass.1"
        def client_3():
            my_instance = roy.get_remote("roy_ftn.TestClass.0")
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

import pytest
import multiprocessing
from roy import remote, connect, start_server, stop_server, SharedMemorySingleton
import time

def initialize_env():
    # start server in a separate process
    server_process = multiprocessing.Process(target=start_server)
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

class TestRemoteDecorator:
    @pytest.fixture(autouse=True)
    def setup(self, server):
        self.shared_memory = SharedMemorySingleton()
        connect()

    def test_my_class(self):
        @remote
        class TestClass:
            def __init__(self, value):
                self.value = value
            def custom_ftn(self, arg):
                return arg

        # print("TestClass:", TestClass.__setattr__)
        my_instance = TestClass("initial_value")
        assert str(my_instance) != ""
        assert my_instance.value == "initial_value"
        my_instance.value = "new_value"
        # test if the access to non-existing attribute raises AttributeError
        with pytest.raises(AttributeError):
            my_instance.non_existing_value
        assert my_instance.value == "new_value"
        # check if the custom function can work
        assert my_instance.custom_ftn("arg") == "arg"

if __name__ == '__main__':
    pytest.main()

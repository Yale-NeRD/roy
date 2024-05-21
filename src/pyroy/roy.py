import roy_shmem
import inspect

class SharedMemorySingleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = roy_shmem.SharedMemory()
        return cls._instance

class RemoteValue:
    def __init__(self, shared_memory, key, initial_value):
        self.shared_memory = shared_memory
        self.key = key
        self._write(initial_value)

    def _read(self):
        result = self.shared_memory.read(self.key)
        return result if result is not None else ""

    def _write(self, value):
        self.shared_memory.write(self.key, value)

    def __str__(self):
        return self._read()

    def __repr__(self):
        return repr(self._read())

    def __eq__(self, other):
        return self._read() == other

    def __ne__(self, other):
        return self._read() != other

    def __setattr__(self, name, value):
        if name in ["shared_memory", "key"]:
            super().__setattr__(name, value)
        else:
            self._write(value)

    def __getattr__(self, name):
        if name == "value":
            return self._read()
        raise AttributeError(f"'RemoteValue' object has no attribute '{name}'")

class RemoteProxy:
    def __init__(self, key, instance):
        print(f"RemoteProxy({key}, {instance})")
        print("instance::super: ", super(type(instance), instance).__dict__)
        self.default_attrs = ["shared_memory", "key", "instance"]
        self.shared_memory = SharedMemorySingleton()
        self.key = key
        self.instance = instance

    def get_attribute_from_shmem(self, name):
        print(f"__getattr__({name})")
        try:
            if name == "default_attrs" or name in self.default_attrs:
                # return proxy's attribute
                if name in self.__dict__:
                    return self.__dict__[name]
                return getattr(self, name)
            # Since this is redirected from self.instance.__getattr__,
            # we need to call the super class's __getattr__
            # - self.instance is always WrappedClass instance
            # if super(type(self.instance), self.instance).__dict__.get(name):
            #     attr = super(type(self.instance), self.instance).__dict__[name]

            #     # TODO: experimental support for functions
            #     if callable(attr):
            #         # wrapper to call shared memory write
            #         def method_proxy(*args, **kwargs):
            #             result = attr(*args, **kwargs)
            #             self.shared_memory.write(f"{self.key}.{name}", result)
            #             return result
            #         return method_proxy
            #     else:
            #         err_msg = f"'{super(type(self.instance))}' should not have non-callable attr: '{name}'"
            #         err_msg += f"\nother than {self.default_attrs}"
            #         raise AttributeError(err_msg)
            if name in self.instance.__dict__ and callable(self.instance.__dict__[name]):
                # wrapper to call shared memory write
                def method_proxy(*args, **kwargs):
                    result = self.instance.__dict__[name](*args, **kwargs)
                    # self.shared_memory.write(f"{self.key}.{name}", result)
                    return result
                return method_proxy

            # Normal attirbute
            attr = self.shared_memory.read(f"{self.key}.{name}")
            if attr is None:
                raise KeyError()
            return attr
        except KeyError:
            raise AttributeError(f"{super(type(self.instance))} object has no attribute '{name}'")

    def set_attribute_to_shmem(self, name, value):
        print(f"__setattr__({name}, '{value}')")
        if name == "default_attrs" or name in self.default_attrs:
            setattr(self, name, value)
        else:
            # TODO: add support for functions
            self.instance.__dict__[name] = value
            if not callable(value):
                self.shared_memory.write(f"{self.key}.{name}", value)

# for @remote decorator
def remote(obj):
    if inspect.isfunction(obj):
        def wrapped_function(*args, **kwargs):
            shared_memory = SharedMemorySingleton()
            key = str(id(wrapped_function))
            result = obj(*args, **kwargs)
            shared_memory.write(key, result)
            return result
        return wrapped_function

    elif inspect.isclass(obj):
        class WrappedClass(obj):
            def __init__(self, *args, **kwargs):
                # setup remote proxy
                key = str(id(self))
                # set remote_proxy
                self.remote_proxy = RemoteProxy(key, self)
                print("remote_proxy.dict: ", self.remote_proxy.__dict__)
                # initialize the class. Any attribute set inside the class
                # will be set in the shared memory
                super().__init__(*args, **kwargs)
                # self.__dict__.update(self.remote_proxy.__dict__)
                print("WrappedClass.dict: ", self.__dict__)

            def __setattr__(self, name, value):
                if name == 'remote_proxy':
                    self.__dict__['remote_proxy'] = value
                else:
                    self.remote_proxy.set_attribute_to_shmem(name, value)

            def __getattr__(self, name):
                if name == 'remote_proxy':
                    return self.__dict__['remote_proxy']
                else:
                    return self.remote_proxy.get_attribute_from_shmem(name)
        return WrappedClass

    else:
        raise TypeError("Unsupported type for @remote decorator")

# connect to the server
def connect(server_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().connect_server(server_address)

def start_server(binding_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().start_server(binding_address)

def stop_server():
    SharedMemorySingleton().stop_server()

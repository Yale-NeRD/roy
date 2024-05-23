import roy_shmem
import inspect
import pickle

ROY_FUNCTION_PREFIX = "roy_ftn"

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
            # TODO: caching support

            #
            # TODO: function support - check and do pickle
            #

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
            raise AttributeError(
                f"{super(type(self.instance))} object has no attribute '{name}'")

    def set_attribute_to_shmem(self, name, value):
        print(f"__setattr__({name}, '{value}')")
        if name == "default_attrs" or name in self.default_attrs:
            setattr(self, name, value)
        else:
            # TODO: add support for functions
            if not callable(value):
                self.shared_memory.write(f"{self.key}.{name}", value)
            else:
                # pickle the function and send it to the shared memory
                raise NotImplementedError("Function is not supported yet")
                # serialized_function = pickle.dumps(value)
                # self.shared_memory.write(f"{self.key}.{name}", serialized_function)

def get_remote_handle(object_name, handle=None):
    # get the name of object if handle is None
    # TODO: check with the server to retrieve a new handle
    handle_base = f"{ROY_FUNCTION_PREFIX}.{object_name}" if handle is None else handle
    new_handle = SharedMemorySingleton().get_next_availble_handle(handle_base)
    return new_handle

def set_remote_object(handle: str, instance):
    SharedMemorySingleton().set_handle_object(handle, pickle.dumps(instance))

def get_remote_object(handle):
    data = SharedMemorySingleton().get_handle_object(handle)
    if data is None:
        return None
    # Convert list of bytes to a byte string
    return pickle.loads(bytes(data))

class WrappedClassTemplate:
    def __init__(self, *args, **kwargs):
        # Recognize the original class's name
        print("Obj: ", self.__class__.__bases__[1].__name__)
        # setup remote proxy
        handle = get_remote_handle(self.__class__.__bases__[1].__name__)
        # set remote_proxy
        self.remote_proxy = RemoteProxy(key=handle, instance=self)
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
        if name == 'roy_handle':
            return self.remote_proxy.key
        else:
            return self.remote_proxy.get_attribute_from_shmem(name)

    def __getstate__(self):
        # Custom pickling logic for WrappedClass
        state = self.__dict__.copy()
        # Remove the remote_proxy attribute for pickling
        del state['remote_proxy']
        # Return the state with the key to recreate the remote_proxy on unpickling
        state['remote_proxy_key'] = self.remote_proxy.key
        return state

    def __setstate__(self, state):
        # Custom unpickling logic for WrappedClass
        remote_proxy_key = state.pop('remote_proxy_key')
        # Restore the state
        self.__dict__.update(state)
        # Recreate the remote_proxy after unpickling
        self.remote_proxy = RemoteProxy(key=remote_proxy_key, instance=self)

def create_wrapped_class(cls, handle=None):
    class_name = f"Wrapped{cls.__name__}"
    bases = (WrappedClassTemplate, cls)
    # Create the class using type()
    WrappedClass = type(class_name, bases, {})
    # Register the class in the module's global scope
    globals()[class_name] = WrappedClass
    return WrappedClass

def remote_decorator(obj, handle=None):
    # error nothing has been specified
    if inspect.isfunction(obj):
        raise NotImplementedError("Function is not supported yet")
    elif inspect.isclass(obj):
        return create_wrapped_class(obj, handle)
    else:
        raise TypeError("Unsupported type for @remote decorator")

# def remote(obj=None, *, handle: str = None):
#     # error nothing has been specified
#     if obj is None and handle is None:
#         raise ValueError("Nothing has been specified for @remote decorator")
#     # for the case the user specifies the handle, e.g., @remote(handle="TestClass"),
#     # so there is no object to decorate
#     if obj is None and handle is not None:
#         # return new decorator with the given handle embedded
#         def remote_decorator_wrapper(obj):
#             return remote_decorator(obj, handle)
#         return remote_decorator_wrapper
#     # if there is an object to decorate,
#     # e.g., @remote def test_class: ...
#     else:
#         return remote_decorator(obj, handle)

def remote(obj):
    return remote_decorator(obj, None)

def set_remote(instance):
    handle = instance.roy_handle
    set_remote_object(handle, instance)
    return handle

def get_remote(handle: str):
    return get_remote_object(handle)
    # TODO: check the type ot see if it is a function

# connect to the server
def connect(server_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().connect_server(server_address)

def start_server(binding_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().start_server(binding_address)

def stop_server():
    SharedMemorySingleton().stop_server()

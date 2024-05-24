import roy_shmem
import inspect
import cloudpickle

# insert the current directory to the path
import sys
import os
current_directory = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_directory)

from roy_types.roy_float import create_float_instance

ROY_FUNCTION_PREFIX = "roy_ftn"

class SharedMemorySingleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = roy_shmem.SharedMemory()
        return cls._instance

def set_remote_object(handle: str, instance):
    SharedMemorySingleton().set_handle_object(handle, cloudpickle.dumps(instance))

def get_remote_object(handle):
    data = SharedMemorySingleton().get_handle_object(handle)
    if data is None:
        return None
    # Convert list of bytes to a byte string
    loaded = cloudpickle.loads(bytes(data))
    print("Loaded: ", loaded)
    loaded = patch_builtin_class(loaded)
    # TODO: rewire remote_proxy
    return loaded

def get_remote_object_with_lock(handle):
    return get_remote_object(handle).lock()

def patch_builtin_class(instance):
    # print("Patch built-in class:", dir(instance), isinstance(instance, float))
    if isinstance(instance, float):
        instance = create_float_instance(instance)
        # instance.__dict__['__iadd__'] = lambda self, other: instance.__class__(float(self) + other)
    return instance

class RemoteProxy:
    def __init__(self, key, instance):
        # print(f"RemoteProxy for {key}: {instance.wrapped_obj}")
        self._default_attrs = ["_key", "_instance", "_function_dict"]
        self._key = key
        self._function_dict = {}
        self._instance = instance

    def get_ray_handle(self):
        return self._key

    def get_attribute_from_shmem(self, name):
        print(f"__getattr__({name})")
        try:
            if name == "_default_attrs" or name in self._default_attrs:
                # return proxy's attribute
                if name in self.__dict__:
                    return self.__dict__[name]
                return getattr(self, name)
            # TODO: caching support

            # Normal attirbute
            attr = get_remote_object(f"{self._key}.{name}")
            if attr is None:
                raise KeyError()
            if callable(attr):
                raise NotImplementedError("Functions cannot be fetched dynamically")

            # print(f"Get attr: {attr}")
            return attr
        except KeyError:
            raise AttributeError(
                f"{type(self._instance.wrapped_obj)} object has no attribute '{name}'"\
                if self._instance.__dict__.get('wrapped_obj') is not None\
                else f"Wrapped instance in {type(self._instance)} has no attribute '{name}'"
            )

    def set_attribute_to_shmem(self, name, value):
        print(f"__setattr__({name}, '{value}')")
        if name == "_default_attrs" or name in self._default_attrs:
            setattr(self, name, value)
        else:
            # TODO: add support for functions
            if not callable(value):
                set_remote_object(f"{self._key}.{name}", value)
            else:
                # cloudpickle the function and send it to the shared memory
                raise NotImplementedError("Functions cannot be added dynamically")

def create_wrapper_class(cls, roy_handle=None):
    class RoyRemoteObject(cls):
        def __init__(self, *args, new_handle=None, **kwargs):
            nonlocal cls
            nonlocal roy_handle
            # Recognize the original class's name
            if new_handle is not None:
                handle = new_handle
            else:
                handle = get_remote_handle(cls.__name__)
            # set remote_proxy
            self.__dict__['remote_proxy'] = RemoteProxy(key=handle, instance=self)
            self.__dict__['roy_handle'] = handle
            # self.__dict__['wrapped_obj'] = cls(*args, **kwargs)
            # print("Wrapped object:", self.__dict__['wrapped_obj'], ", Id:", id(self.__dict__['wrapped_obj'].__class__))
            # print("Class:", cls, ", Id:", id(cls))
            
            if hasattr(cls, '__init__'):
                try:
                    super().__init__(*args, **kwargs)
                except TypeError:
                    pass
            set_remote_object(handle, self)

        # TODO: dummy lock, unlock with only data not locking
        def lock(self):
            recreate_remote_object(self, get_remote_object(self.__dict__['roy_handle']))
            # print("Locked: ", self)
            return self

        def unlock(self):
            set_remote_object(self.__dict__['roy_handle'], self)
            return self

    # return create_wrapped_class(obj, handle)
    # RoyRemoteObject.__module__ = cls.__module__
    RoyRemoteObject.__module__ = cls.__module__
    RoyRemoteObject.__name__ = cls.__name__
    globals()[RoyRemoteObject.__name__] = RoyRemoteObject
    print(RoyRemoteObject.__module__, ":", RoyRemoteObject.__name__)
    return RoyRemoteObject

def get_remote_handle(object_name, handle=None):
    # get the name of object if handle is None
    # TODO: check with the server to retrieve a new handle
    handle_base = f"{ROY_FUNCTION_PREFIX}.{object_name}" if handle is None else handle
    new_handle = SharedMemorySingleton().get_next_availble_handle(handle_base)
    return new_handle

def create_remote_object(obj, cls):
    '''
    Create a new object from a remote object class.
    @obj: instance of class to be wrapped
    @cls: class of the object to be wrapped
    @return: new instance of the class under wrapper class
    '''
    if hasattr(obj, '__dict__'):
        new_obj = cls()
        new_obj.__dict__.update(obj.__dict__)
    else:
        # built in types
        new_obj = cls(obj)
        # print("Built-in type:", dir(new_obj))
    return new_obj

def recreate_remote_object(obj, remote_obj):
    '''
    Recreate a new object from a remote object.
    All local attributes will be updated with the remote object's attributes
    @obj: target instance of remote class that will be retrieved
    @remote_obj: source remote instance
    @return: obj of which attributes are updated with remote_obj
    '''
    # assert remote_obj.__dict__.get('wrapped_obj') is not None
    print("Recreate remote object", obj, "<-", remote_obj)
    if isinstance(obj, list):
        obj.clear()
        obj.extend(remote_obj)
    elif isinstance(obj, dict):
        obj.clear()
        obj.update(remote_obj)
    elif isinstance(obj, tuple):
        # Tuples are immutable, replace the wrapped_obj
        print("Immutable class(Tuple) cannot be locked")
    elif isinstance(obj, set):
        obj.clear()
        obj.update(remote_obj)
    elif isinstance(obj, frozenset):
        # Frozensets are immutable, replace the wrapped_obj
        print("Immutable class(Frozenset) cannot be locked")
    elif isinstance(obj, str):
        # Strings are immutable, replace the wrapped_obj
        print("Immutable class(String) cannot be locked")
    elif isinstance(obj, int):
        # Integers are immutable, replace the wrapped_obj
        print("Immutable class(Integer) cannot be locked")
    elif isinstance(obj, float):
        # Floats are immutable, replace the wrapped_obj
        print("Immutable class(Float) cannot be locked")
    elif isinstance(obj, complex):
        # Complex numbers are immutable, replace the wrapped_obj
        print("Immutable class(Complex) cannot be locked")
    elif isinstance(obj, bool):
        # Booleans are immutable, replace the wrapped_obj
        print("Immutable class(Boolean) cannot be locked")
    elif isinstance(obj, bytes):
        # Bytes are immutable, replace the wrapped_obj
        print("Immutable class(Bytes) cannot be locked")
    elif isinstance(obj, bytearray):
        obj.clear()
        obj.extend(remote_obj)
    elif isinstance(obj, memoryview):
        # Memoryview objects are immutable, replace the wrapped_obj
        print("Immutable class(Memoryview) cannot be locked")
    else:
        # If it's not a built-in type and __dict__ is not avilable,
        # it's unsupported
        if not hasattr(obj, '__dict__') or not hasattr(remote_obj, '__dict__'):
            raise NotImplementedError(f"Unsupported type ({obj.__class__}) for remote object")
    return obj

def _remote_decorator(obj, _handle=None):
    # error nothing has been specified
    if inspect.isfunction(obj):
        raise NotImplementedError("Function is not supported yet")
    elif inspect.isclass(obj):
        return create_wrapper_class(obj)
    elif obj is not type:
        print("Create remote object from instance")
        # now it is an instance
        cls = create_wrapper_class(obj.__class__)
        return create_remote_object(obj, cls)
    else:
        raise TypeError("Unsupported type for @remote decorator")

def remote(obj):
    return _remote_decorator(obj, None)

def set_remote(instance):
    handle = instance.roy_handle
    set_remote_object(handle, instance)
    return handle

def get_remote(handle: str):
    return get_remote_object(handle)
    # TODO: check the type to see if it is a function

# connect to the server
def connect(server_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().connect_server(server_address)

def start_server(binding_address: str = "127.0.0.1:50015"):
    SharedMemorySingleton().start_server(binding_address)

def stop_server():
    SharedMemorySingleton().stop_server()

import roy_shmem
import inspect

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
    def __init__(self, shared_memory, key, instance):
        self.shared_memory = shared_memory
        self.key = key
        self.instance = instance

    def __getattr__(self, name):
        try:
            attr = getattr(self.instance, name)
            if callable(attr):
                def method_proxy(*args, **kwargs):
                    result = attr(*args, **kwargs)
                    self.shared_memory.write(self.key + "." + name, result)
                    return result
                return method_proxy
            else:
                return attr
        except AttributeError:
            # Return the attribute from shared memory if not found in the instance
            return self.shared_memory.read(self.key + "." + name)

    def __setattr__(self, name, value):
        if name in ["shared_memory", "key", "instance"]:
            super().__setattr__(name, value)
        else:
            setattr(self.instance, name, value)
            self.shared_memory.write(self.key + "." + name, value)

def remote(obj):
    if inspect.isfunction(obj):
        raise TypeError("Function is not supported to be in shared memory. Use class instead.")

    elif inspect.isclass(obj):
        class WrappedClass(obj):
            def __init__(self, *args, **kwargs):
                shared_memory = roy_shmem.SharedMemory()
                key = str(id(self))
                super().__init__(*args, **kwargs)
                remote_proxy = RemoteProxy(shared_memory, key, self)
                self.__dict__.update(remote_proxy.__dict__)
        return WrappedClass

    else:
        raise TypeError("Unsupported type for @remote decorator")

from functools import wraps
def remote(cls):
    original_init = cls.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._auto_managed_attrs = []

        # Dynamically find attributes to manage
        if self.__dict__ is not None:
            for attr_name in self.__dict__:
                attr = getattr(self, attr_name)
                if hasattr(attr, '__enter__') and callable(getattr(attr, '__enter__'))\
                    and hasattr(attr, '__exit__') and callable(getattr(attr, '__exit__')):
                    self._auto_managed_attrs.append(attr)

    def __enter__(self):
        # TODO: lock it self first; lock attr following the alphabetic order to prevent deadlock
        for attr in self._auto_managed_attrs:
            attr.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for attr in self._auto_managed_attrs:
            attr.__exit__(exc_type, exc_val, exc_tb)
        return False

    def flush(self):
        # TODO: logging with Loguru
        print(f"INFO: manually flushing {self.__class__.__name__}")
        for attr in self._auto_managed_attrs:
            if hasattr(attr, 'flush') and callable(getattr(attr, 'flush')):
                print(f"* Flushing {attr.__class__.__name__}")
                attr.flush()

    setattr(cls, '__init__', new_init)
    setattr(cls, '__enter__', __enter__)
    setattr(cls, '__exit__', __exit__)
    setattr(cls, 'roy_flush', flush)
    return cls


class RoyLock:
    def __init__(self) -> None:
        pass

# TODO: for now, they are used just for naming
# The actual implementation is in the Rust library
class Mutex(RoyLock):
    def __init__(self):
        self.__name__ = "Mutex"
        super().__init__()  # nothing to initialize


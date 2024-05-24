
def create_float_instance(instance):
    # check if it is a roy object
    assert instance.__dict__.get('roy_handle') is not None
    if instance.__class__.__name__ == 'RoyFloat':
        return instance

    # to override the built-in float operators
    class RoyFloat(instance.__class__):
        def __init__(self, instance, new_handle=None):
            super().__init__()
            self.roy_handle = new_handle or instance.roy_handle

        def __iadd__(self, other):
            result = super().__add__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __add__(self, other):
            result = super().__add__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __radd__(self, other):
            result = super().__radd__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __isub__(self, other):
            result = super().__sub__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __sub__(self, other):
            result = super().__sub__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rsub__(self, other):
            result = super().__rsub__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __imul__(self, other):
            result = super().__mul__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __mul__(self, other):
            result = super().__mul__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rmul__(self, other):
            result = super().__rmul__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __itruediv__(self, other):
            result = super().__truediv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __truediv__(self, other):
            result = super().__truediv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rtruediv__(self, other):
            result = super().__rtruediv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __ifloordiv__(self, other):
            result = super().__floordiv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __floordiv__(self, other):
            result = super().__floordiv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rfloordiv__(self, other):
            result = super().__rfloordiv__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __imod__(self, other):
            result = super().__mod__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __mod__(self, other):
            result = super().__mod__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rmod__(self, other):
            result = super().__rmod__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __ipow__(self, other):
            result = super().__pow__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __pow__(self, other, modulo=None):
            result = super().__pow__(other, modulo)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __rpow__(self, other):
            result = super().__rpow__(other)
            return RoyFloat(result, new_handle=self.roy_handle)

        def __neg__(self):
            result = super().__neg__()
            return RoyFloat(result, new_handle=self.roy_handle)

        def __pos__(self):
            result = super().__pos__()
            return RoyFloat(result, new_handle=self.roy_handle)

        def __abs__(self):
            result = super().__abs__()
            return RoyFloat(result, new_handle=self.roy_handle)

    return RoyFloat(instance, new_handle=instance.roy_handle)

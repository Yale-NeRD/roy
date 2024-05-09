from roy import remote

def test_my_class():
    @remote
    class TestClass:
        def __init__(self, value):
            self.value = value

    my_instance = TestClass("initial_value")
    assert str(my_instance) != ""
    assert my_instance.value == "initial_value"
    my_instance.value = "new_value"
    assert my_instance.value == "new_value"

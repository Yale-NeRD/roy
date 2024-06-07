
import pickle
import uuid

def get_unique_id():
    return str(uuid.uuid4())

class ListchunkRef:
    def __init__(self, id, list_chunk_ref) -> None:
        self.id = id
        self.list_chunk = list_chunk_ref

    def __repr__(self) -> str:
        return f"ListchunkRef(id={self.id}, list_chunk={hex(id(self.list_chunk))}"

class ElementList():
    def __init__(self, list_chunk: list) -> None:
        print(f"List chunk: {list_chunk}")
        self.raw_list = list_chunk

    def __getattr__(self, name):
        # print(f"Attribute: {name}")
        if name == "raw_list":
            self.raw_list = None
            return self.raw_list
        return getattr(self.raw_list, name)

    def __len__(self):
        return len(self.raw_list)

    def __name__(self):
        return self.raw_list.__name__

class CustomList:
    def __init__(self, existing_list = None, chunk_size = 20) -> None:
        self.elements = []
        self.chunk_size = chunk_size
        self.length = 0
        if existing_list is not None:
            if not isinstance(existing_list, list):
                print(f"Only list is supported — given type: {type(existing_list)}")
            
            self.__newchunks__(existing_list)

    def __newchunks__(self, existing_list):
        if len(existing_list) <= self.chunk_size:
            existing_list = ElementList()
            self.list_chunk = [ListchunkRef(get_unique_id(), existing_list)]
            self.elements = [existing_list]
            self.length = len(existing_list)
        else:
            self.list_chunk = []
            for idx in range(0, len(existing_list), self.chunk_size):
                chunk = existing_list[idx:idx + self.chunk_size]
                chunk = ElementList(chunk)
                self.list_chunk.append(ListchunkRef(get_unique_id(), chunk))
                self.elements.append(chunk)
                self.length += len(chunk)

    def __addchunk__(self, chunk):
        if len(self.elements) == 0:
            chunk = ElementList(chunk)
            self.list_chunk = [ListchunkRef(get_unique_id(), chunk)]
            self.elements = [chunk]
            self.length = len(chunk)
        else:
            if len(self.elements[-1]) + len(chunk) <= self.chunk_size:
                self.elements[-1].extend(chunk)
                self.length += len(chunk)
            else:
                chunk = ElementList(chunk)
                self.list_chunk.append(ListchunkRef(get_unique_id(), chunk))
                self.elements.append(chunk)
                self.length += len(chunk)

    def __getstate__(self):
        state = self.__dict__.copy()
        # Add other attributes to the state
        state['other_attribute'] = self.__dir__()
        # Don't pickle the 'elements' attribute
        del state['elements']
        print("State:", state)
        return state

    def __getelements__(self):
        return [pickle.dumps(chunk) for chunk in self.elements]

    def __setelements__(self, elements):
        self.elements = [pickle.loads(chunk) for chunk in elements]

    def __setstate__(self, state):
        # Restore instance attributes (i.e., chunk_size)
        self.__dict__.update(state)
        # Unpickled objects won't have 'elements' attribute, so we need to set it
        self.elements = []
        # Restore other attributes
        self.__dir__ = state['other_attribute']

    def append(self, item):
        self.__newchunks__([item])

    def len(self):
        return self.length

    def pop(self, index = -1):
        if len(self.elements) == 0:
            return None

        res = None
        # at the end
        if index == -1:
            try:
                res = self.elements[-1].pop()
                self.length -= 1
            except IndexError:
                res = None
            if len(self.elements[-1]) == 0:
                self.elements.pop()
                self.list_chunk.pop()
            return res

        # in the middle
        acc_index = 0
        for ch_idx, chunk in enumerate(self.elements):
            if acc_index + len(chunk) > index:
                res = chunk.pop(index - acc_index)
                self.length -= 1
                if len(chunk) == 0:
                    self.elements.remove(chunk)
                    self.list_chunk.pop(ch_idx)
                return res
            acc_index += len(chunk)
        return res

if __name__ == "__main__":
    list_example = list([idx for idx in range(100)])
    custom_list = CustomList(list_example)
    custom_list.pop(5)
    custom_list.pop(20)
    custom_list.pop(70)
    print(custom_list.elements)
    print(custom_list.list_chunk)
    # for item in list_example.__dir__():
    #     print(f"Item: {item}, Callable: {callable(getattr(list_example, item))}")

    pickled_custom_list = pickle.dumps(custom_list)
    pickled_elements = custom_list.__getelements__()

    restored_custom_list = pickle.loads(pickled_custom_list)
    # restored_custom_list.__setelements__(pickled_elements)
    print(restored_custom_list.elements)
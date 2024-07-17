import pytest
import multiprocessing
import time
import random
import sys
import os

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)

import pyroy.roy as roy
import ray  # `pip install ray` for this example

def initialize_env():
    # start server in a separate process
    server_process = multiprocessing.Process(target=roy.start_server)
    server_process.start()
    time.sleep(1) # wait for the server to start
    return server_process

def clean_env(server_process):
    roy.stop_server()
    server_process.terminate()

@roy.remote
class PiResultContainer:
    def __init__(self):
        self.result = [0.]

if __name__ == '__main__':
    # start server in a separate process
    server_proc = initialize_env()

    # connect to the server for this process
    roy.connect()
    ray.init(runtime_env={"py_modules": [parent_directory + "/pyroy"]})
    try:
        num_tasks = 1

        # Method 1: using a list (mutable object)
        counters = roy.remote(list([0 for _ in range(num_tasks)]))
        print("Counters:", dir(counters))
        roy_handle = counters.roy_handle
        print("Roy handle for variable:", roy_handle)

        # Method 2: using a class
        my_instance = PiResultContainer()
        print("Instance:", my_instance)
        roy_handle_cls = my_instance.roy_handle
        print("Roy handle for class:", roy_handle_cls)

        # Method 3: immutable object (replacing with a new object, instead of in-place update)
        my_instance = roy.remote(float(0.))
        roy_handle_immutable = my_instance.roy_handle

        # define function to compute pi
        @ray.remote
        def sampling_task(task_id, num_samples, roy_handle):
            inside = 0.
            for _ in range(num_samples):
                x = random.uniform(-1, 1)
                y = random.uniform(-1, 1)
                if x**2 + y**2 <= 1:
                    inside += 1
            # collect the result
            roy.connect()
            # Update counter with Method 1, via variable
            local_instance = roy.get_remote_object_with_lock(roy_handle)
            if local_instance is not None: # object can be get and acquired lock
                local_instance[task_id] = inside / num_samples
                local_instance.unlock()
            # Update counter with Method 2, via class
            local_instance = roy.get_remote_object_with_lock(roy_handle_cls)
            if local_instance is not None:
                local_instance.result[task_id] = inside / num_samples
                local_instance.unlock()
            # Update counter with Method 3, via immutable object
            local_instance = roy.get_remote_object_with_lock(roy_handle_immutable)
            if local_instance is not None:
                local_instance += inside / num_samples
                local_instance.unlock()
            # Return result in an orignal Ray's way
            return inside

        # launch tasks
        num_samples_per_task = 10000
        results = [sampling_task.remote(id, num_samples_per_task, roy_handle) for id in range(num_tasks)]

        # Ray's way to get the results
        pi_estimate = 4 * sum(ray.get(results)) / (num_tasks * num_samples_per_task)

        # Method 1 (varible) to get the results
        counters.lock()
        print("Counters:", counters)
        pi_estimate_roy = 4 * sum(counters) / num_tasks
        counters.unlock()

        # Method 2 (class) to get the results
        counters = roy.get_remote_object_with_lock(roy_handle_cls)
        pi_estimate_roy_cls = 4 * counters.result[0] / num_tasks
        counters.unlock()

        # Method 3 (immutable object) to get the results
        counters = roy.get_remote_object_with_lock(roy_handle_immutable)
        pi_estimate_immutable = 4 * counters / num_tasks
        counters.unlock()

        # Print the results for comparison
        print("Estimated pi:", pi_estimate)
        print("Estimated pi using roy variables:", pi_estimate_roy)
        print("Estimated pi using roy with class:", pi_estimate_roy_cls)
        print("Estimated pi using roy with immutable object:", pi_estimate_immutable)
        assert abs(pi_estimate - pi_estimate_roy) < 1e-6
        assert abs(pi_estimate - pi_estimate_roy_cls) < 1e-6
        assert abs(pi_estimate - pi_estimate_immutable) < 1e-6

    finally:
        clean_env(server_proc)

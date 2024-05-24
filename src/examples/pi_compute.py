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

if __name__ == '__main__':
    # start server in a separate process
    server_proc = initialize_env()

    # connect to the server for this process
    roy.connect()
    ray.init(runtime_env={"py_modules": [parent_directory + "/pyroy"]})
    try:
        # define function to compute pi
        num_tasks = 1
        @roy.remote
        class PiResultContainer:
            def __init__(self):
                self.result = 0.
        my_instance = PiResultContainer()
        print("Instance:", my_instance)
        roy_handle = my_instance.roy_handle
        print("Roy handle:", roy_handle)

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
            my_instance = roy.get_remote(roy_handle)
            if my_instance is not None:
                my_instance.result += inside / num_samples
            print(f"Task {task_id} done: {inside / num_samples}")
            return inside

        num_samples_per_task = 10000
        results = [sampling_task.remote(id, num_samples_per_task, roy_handle) for id in range(num_tasks)]
        pi_estimate = 4 * sum(ray.get(results)) / (num_tasks * num_samples_per_task)
        pi_estimate_roy = 4 * sum([my_instance.result]) / num_tasks
        print("Estimated pi:", pi_estimate)
        print("Estimated pi using roy:", pi_estimate_roy)

    finally:
        clean_env(server_proc)

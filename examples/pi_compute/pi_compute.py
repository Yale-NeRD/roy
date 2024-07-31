import random
import ray
from roy_on_ray import RoyDict

if __name__ == '__main__':
    num_tasks = 8

    # connect to the server for this process
    ray.init()

    # Create a container to store the results
    counters = RoyDict({i: 0 for i in range(num_tasks)}, num_chunks=num_tasks)

    # Print the initial state
    # Note) Expensive operation since it fetches all remote objects to print
    with counters as container:
        print("Counters:", container)
    # The following will cause error (sometime not immeidately but eventually)
    # print("Counters:", counters)

    # Define function to compute pi
    @ray.remote
    def sampling_task(task_id, num_samples, result_container):
        inside = 0.
        for _ in range(num_samples):
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            if x**2 + y**2 <= 1:
                inside += 1
        # Collecting values via mutable object
        with result_container as container:
            container[task_id] = inside
        # Collecting values via return
        return inside

    # Launch tasks
    num_samples_per_task = 10000
    results = [sampling_task.remote(id, num_samples_per_task, counters) for id in range(num_tasks)]

    # Results from returns
    pi_estimate = 4 * sum(ray.get(results)) / (num_tasks * num_samples_per_task)

    # Results from the mutable shared object
    with counters as container:
        pi_estimate_roy = 4 * sum(counters.values()) / (num_tasks * num_samples_per_task)

    # Print the results for comparison
    print("Estimated pi using ray returns:", pi_estimate)
    print("Estimated pi using roy variables:", pi_estimate_roy)

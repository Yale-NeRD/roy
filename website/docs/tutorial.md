---
sidebar_position: 1
---

# Roy Tutorial

Let's get started with Roy and learn how to program with mutable remote objects!

Roy provides built-in classes for remote but _mutable_ object that can be used in Ray tasks. Currently, they are `RoyList`, `RoyDict`, and `RoySet`.

:::info

We assume that you have a running Ray cluster. If you don't have one, please refer to the [Ray documentation](https://docs.ray.io/en/latest/index.html) to set up a Ray cluster.

You can check the status as follows in the terminal:

```bash
ray status
```

We also assume that you already installed the `roy-on-ray` package. If not, please install it via pip:

```bash
pip install roy-on-ray
```

:::

## Simple distributed counter example (to compute π)

Let's take a look at a simple example of using `RoyDict` to count the frequency of words in a list.
We will use the Monte Carlo method to estimate the value of π.

### Initialization

Let's first import required libraries including Roy and Ray.

```python
import random
import ray
from roy_on_ray import RoyDict
```

Inside our main function, we will first initialize Ray and define a counter object as a `RoyDict`.
Each key will be the task ID and the value will be the number of samples that fall inside the unit circle.

```python
    # Number of workers
    num_tasks = 8

    # Initialize Ray
    ray.init()

    # Create a container to store the results
    counters = RoyDict({i: 0 for i in range(num_tasks)}, num_chunks=num_tasks)
```

### Basic use of Roy data structures

To print out values in the Roy-provided data structures, developers need to use the `with` statement to access the data. It will internally lock the object and ensures data consistency (only a single process can access the data at a time).

```python
    # Print the initial state
    # Note) Expensive operation since it fetches all remote objects to print
    with counters as container:
        print("Counters:", container)
```

Now we define ray tasks for Monte Carlo sampling. Note that we are collecting the results in two ways: one is by updating the shared object and the other is by returning the value.

```python
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
```

:::note
For now, since we are doing a single round of result reporting, there might be no significant difference between those two ways of collecting the results. However, for more complex use cases, using mutable objects is useful to simplify your operations. For example, if you want to update the progress of each task periodically in the middle of a long-running task, you can update the progress/status via mutable objects (or define a Ray Actor that exposes remote function calls for such updates).
:::

### Collecting results

Finally, we launch the tasks, collect the results, and compare the results from the two methods.

```python
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
```

### Putting things together

```python
import random
import ray
from roy_on_ray import RoyDict

if __name__ == '__main__':
    # Number of workers
    num_tasks = 8

    # Initialize Ray
    ray.init()

    # Create a container to store the results
    counters = RoyDict({i: 0 for i in range(num_tasks)}, num_chunks=num_tasks)

    # Print the initial state
    # Note) Expensive operation since it fetches all remote objects to print
    with counters as container:
        print("Counters:", container)
    # NOTE) The following will cause error (sometime not immeidately but eventually)
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
```

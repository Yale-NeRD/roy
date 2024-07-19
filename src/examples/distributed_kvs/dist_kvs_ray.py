import ray
from typing import Any, List
import random
import string
import asyncio
import time
import yaml
import numpy as np

# Load configuration from config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Print configuration
print(f"Configuration: {config}")

total_requests = config['total_requests']
total_clients = config['total_clients']
total_keys = config['total_keys']
value_size = config['value_size']
overlap_ratio = config['overlap_ratio']
set_ratio = config['set_ratio']
num_workers = config['num_workers']

# Generate keys
all_keys = [''.join(random.choices(string.ascii_letters + string.digits, k=10)) for _ in range(total_keys)]
shared_keys = all_keys[:int(total_keys * overlap_ratio)]
private_keys = all_keys[int(total_keys * overlap_ratio):]
value = ''.join(random.choices(string.ascii_letters + string.digits, k=value_size))

# Initialize Ray
ray.init(ignore_reinit_error=True)

# Define the distributed key-value store class
@ray.remote
class KeyValueStore:
    def __init__(self):
        self.store = {}

    def set(self, key: str, value: Any):
        self.store[key] = value

    def get(self, key: str) -> Any:
        return self.store.get(key, None)

    def delete(self, key: str):
        if key in self.store:
            del self.store[key]

# Create workers based on the number of workers specified in the config
workers = [KeyValueStore.remote() for _ in range(num_workers)]

# Hash function to distribute keys among workers
def get_worker(key: str) -> int:
    return hash(key) % num_workers

# Frontend server class
class FrontendServer:
    def __init__(self, workers):
        self.workers = workers

    async def set(self, key: str, value: Any):
        worker_id = get_worker(key)
        await self.workers[worker_id].set.remote(key, value)

    async def get(self, key: str) -> Any:
        worker_id = get_worker(key)
        return await self.workers[worker_id].get.remote(key)

    async def delete(self, key: str):
        worker_id = get_worker(key)
        await self.workers[worker_id].delete.remote(key)

# Create an instance of the frontend server
frontend_server = FrontendServer(workers)

# Define a client actor to generate random requests
@ray.remote
class ClientActor:
    def __init__(self, client_id: int, frontend_server):
        self.client_id = client_id
        self.frontend_server = frontend_server
        self.request_count = 0
        self.total_requests = 0
        self.latencies = []

    async def run(self, num_requests: int):
        self.total_requests = num_requests
        for _ in range(num_requests):
            operation = random.random()
            key = random.choice(shared_keys if random.random() < overlap_ratio else private_keys)

            start_time = time.time()
            if operation < set_ratio:
                await self.frontend_server.set(key, value)
            else:
                await self.frontend_server.get(key)
            end_time = time.time()

            self.request_count += 1
            self.latencies.append((end_time - start_time) * 1000)  # Convert latency to milliseconds

    def get_request_count(self) -> int:
        return self.request_count

    def is_finished(self) -> bool:
        return self.request_count >= self.total_requests

    def get_latencies(self) -> List[float]:
        return self.latencies

# Run multiple clients
async def start_clients(frontend_server, num_clients: int, num_requests: int):
    clients = [ClientActor.remote(client_id, frontend_server) for client_id in range(num_clients)]
    tasks = [client.run.remote(num_requests // num_clients) for client in clients]
    return clients, tasks

# Throughput reporting function
async def report_throughput(clients):
    last_time = time.time()
    last_counts = [0] * len(clients)

    while True:
        await asyncio.sleep(1)
        current_time = time.time()
        elapsed_time = current_time - last_time

        counts = ray.get([client.get_request_count.remote() for client in clients])
        total_counts = sum(counts)
        interval_counts = total_counts - sum(last_counts)
        throughput = interval_counts / elapsed_time

        print(f"Throughput: {throughput:.2f} requests/second")

        if all(ray.get([client.is_finished.remote() for client in clients])):
            break

        last_time = current_time
        last_counts = counts

# Calculate and print latency statistics
def print_latency_statistics(latencies):
    latencies = np.array(latencies)
    avg_latency = np.mean(latencies)
    median_latency = np.median(latencies)
    p90_latency = np.percentile(latencies, 90)
    p99_latency = np.percentile(latencies, 99)

    print(f"Average latency: {avg_latency:.2f} ms")
    print(f"Median latency: {median_latency:.2f} ms")
    print(f"90th percentile latency: {p90_latency:.2f} ms")
    print(f"99th percentile latency: {p99_latency:.2f} ms")

# Benchmarking function
async def benchmark(total_requests: int, total_clients: int):
    clients, client_tasks = await start_clients(frontend_server, total_clients, total_requests)
    reporting_task = asyncio.create_task(report_throughput(clients))
    
    # Wait for all clients to finish
    await asyncio.gather(*client_tasks)
    
    # Wait for reporting task to complete
    await reporting_task

    # Gather latencies from all clients
    latencies = []
    for client in clients:
        latencies.extend(ray.get(client.get_latencies.remote()))

    # Print latency statistics
    print_latency_statistics(latencies)

# Run the benchmark with the configuration parameters
asyncio.run(benchmark(total_requests, total_clients))

# Shutdown Ray
ray.shutdown()

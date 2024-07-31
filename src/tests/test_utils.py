import ray, time
import sys, os

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)
sys.path.append(parent_directory + '/cpproy')
sys.path.append(parent_directory + '/roytypes')

def ray_fresh_start():
    retry_count = 0
    # check ray is already running
    while ray.is_initialized():
        # wait for ray to shutdown
        time.sleep(1)
        print("Waiting for ray to shutdown from the previous test case...")
        retry_count += 1
        if retry_count > 5:
            print("Ray did not shutdown properly. Exiting...")
            ray.shutdown()

    ray.init(runtime_env={"py_modules": [parent_directory + "/roytypes"]})

def ray_shutdown():
    ray.shutdown()
    print("Ray shutdown complete", flush=True)
    retry_count = 0
    while ray.is_initialized():
        # wait for ray to shutdown
        time.sleep(1)
        print("Waiting for ray to shutdown from the previous test case...")
        retry_count += 1
        if retry_count > 3:
            print("Ray did not shutdown properly. Exiting...")
            ray.shutdown()

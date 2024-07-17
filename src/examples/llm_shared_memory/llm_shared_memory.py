import multiprocessing
import sys
import os
import signal

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)
import pyroy.roy as roy


# Define your signal handler
def signal_handler(sig, frame):
    print('Signal received, stopping...')
    agent_kid.terminate()  # Terminate the process
    agent_elder.terminate()  # Terminate the process
    server_proc.terminate()  # Terminate the server process
    print('All processes terminated.')

# Install the signal handler
signal.signal(signal.SIGINT, signal_handler)

def run_llama_cpp(agent_id, prompt="Answer No.", status_handle=None, append_to_status=False):
    
    assert status_handle is not None
    from llama_cpp import Llama
    roy.connect()
    status_instance = roy.get_remote_object(status_handle)

    # Model ref: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf
    llm = Llama(
    model_path=".models/Phi-3-mini-4k-instruct-q4.gguf",  # path to GGUF file
    n_ctx=4096,  # The max sequence length to use - note that longer sequence lengths require much more resources
    n_threads=8, # The number of CPU threads to use, tailor to your system and the resulting performance
    n_threads_batch=8,
    # n_gpu_layers=0, # The number of layers to offload to GPU, if you have GPU acceleration available. Set to 0 if no GPU acceleration is available on your system.
    )

    # prompt = "How to explain Internet to a medieval knight? Use only up to 3 sentences."
    status_instance.lock()
    prev_value = status_instance.shared_memory[-1]

    # Simple inference example
    output = llm(
    f"<|user|>\n{prompt}{prev_value}<|end|>\n<|assistant|>",
    max_tokens=256,  # Generate up to 256 tokens
    stop=["<|end|>"], 
    echo=True,  # Whether to echo the prompt
    stream=True)
    # )

    # Iterate over the streamed output and print each chunk
    simple_output = ""
    for chunk in output:
        print(chunk['choices'][0]['text'], end='', flush=True)
        simple_output += chunk['choices'][0]['text']
    # simple_output = output['choices'][0]['text']
    status_instance.shared_memory[-1] = simple_output
    status_instance.unlock()

    print(simple_output)
    # if append_to_status:
    #     status_instance.lock()
    #     status_instance.shared_memory.append(simple_output)
    #     status_instance.unlock()


@roy.remote
class OvermindStatus:
    def __init__(self):
        self.shared_memory = []

if __name__ == '__main__':
    # start server in a separate process
    server_proc = roy.initialize_test_env()

    # connect to the server for this process
    roy.connect()
    agent_kid = None
    agent_elder = None
    try:
        # define the overmind status
        overmind_status = OvermindStatus()
        # overmind_status = roy.remote(float(100))
        overmind_status.lock()
        overmind_status.shared_memory.append("Current value is 1000")
        overmind_status.unlock()

        status_handle = overmind_status.get_handle()
        command = "Add a random number between 10 and 20 to the given input. SIMPLY ADD THE NUMBER WITHOUT FURTHER EXPLANATION."

        agent_kid = multiprocessing.Process(target=run_llama_cpp, args=(1, f"You are a fake calculater. Do the computation inversely. Given query: {command}", status_handle, False))
        agent_kid.start()

        agent_elder = multiprocessing.Process(target=run_llama_cpp, args=(2, f"You are a honest calculater. Given query: {command}", status_handle, False))
        agent_elder.start()

        agent_kid.join()
        agent_elder.join()

        # check the shared memory
        print("Shared memory across agents:")
        overmind_status.lock()
        print(overmind_status.shared_memory)
        overmind_status.unlock()

    finally:
        if agent_kid is not None:
            agent_kid.terminate()
        if agent_elder is not None:
            agent_elder.terminate()
        roy.clean_test_env(server_proc)

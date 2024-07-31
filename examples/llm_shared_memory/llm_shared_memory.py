import os, time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Get the API key from environment variables
# NOTE) place your PERPLEXITY_API_KEY in .env file
# e.g., PERPLEXITY_API_KEY=your_api_key_start_with_pplx-...
api_key = os.getenv('PERPLEXITY_API_KEY')

import ray
import requests

# We use RoyList as a shared memory across agents
from roy_on_ray import RoyList, remote

# llm_config structure
llm_config = {
    # "model": "llama3",
    # "model": "llama-3-8b-instruct",
    # "model": "llama-3-sonar-small-32k-chat",
    "model": "llama-3.1-70b-instruct",
    "system_prompt":
        "# General instructions:\n"
        "- Following your role, write a paragraph referring to the shared memory toward the goal.\n"
        # "Do not keep adding new thoughout, unless the directions suggested in the previous thoughts are finished.\n"
        # "- You can finish or add your thoughts for the suggestions in the shared memory.\n"
        "- Choose the most underdeveloped or interesting topic from the shared memory.\n"
        "- Do not repeat the same topic or similar ideas.\n"
        "- Assume that your answer will be automatically added to the shared memory.\n"
        "- If needed, refer to the other Agent's thoughts in the shared memory.\n"
        "- Example: \"Based on the previous task A, let's do the survey on topic B."
        "Topic B is ... (definition, sub-categories, interesting insights, challenges, potential solutions, etc.)\"\n",
    # "url": "http://localhost:11434/api/generate"
    "url": "https://api.perplexity.ai/chat/completions"
}

agent_roles = [
    "You are a highly creative and innovative thinker. Your role is to generate novel and valuable ideas, concepts, and suggestions, inspired from the data stored in the shared memory. You should think outside the box to provide groundbreaking solutions and improvements. Your paragraph must contain three sentences of which clearly and concisely explain an idea to explore.",
    "You are a knowledgeable and writer. Your primary responsibility is to write clear, detailed, and insightful explanations for a chosen single idea from the shared memory. Follow top-down approach: your paragraph must contain (1) topic sentence, (2) three supporting details, (3) evidence that backs up the supporting details, and conclusion.",
    "You are a meticulous and analytical reviewer. Your task is to critically evaluate and rigorously analyze the ideas and suggestions stored in the shared memory. You should assess their feasibility, effectiveness, and potential impact to ensure the highest quality outcomes."
]

def query_llm(llm_config, prompt):
    payload = {
            "model": llm_config["model"],
            "messages": prompt,
        }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    response = requests.post(llm_config["url"], json=payload, headers=headers)
    if response.status_code != 200:
        err = f"Error: {response.status_code}, {response.text}"
        print(err, flush=True)
        return err

    # model_response = response.json()['response']  # ollama
    model_response = response.json()['choices'][0]['message']['content']
    print(model_response, flush=True)
    return model_response

# See the similarity with the single-threaded program
@ray.remote
class Worker:
    def __init__(
        self, 
        id, shared_memory, llm_config,
        agent_role="You are a helpful and collaborative assistant who creates insightful explanations for the data stored in the shared memory."
        ):
        self.id = id
        self.shared_state = shared_memory
        self.llm_config = llm_config
        self.agent_role = agent_role

    # Based on the shared memory, create a new task and execute it
    def do_task(self):
        prompt_from_shared_memory = ""
        with self.shared_state:
            prompt_from_shared_memory = [
                {
                    "role": "system",
                    "content": 
                        "\n# Agent specific role information\n"
                        + f"- Your Role:{self.agent_role}\n"
                        + f"- Your Agent Id: {self.id}\n"
                        + self.llm_config["system_prompt"]
                        + "\n\n# SHARED MEMORY ACROSS AI AGENTS:\n" + "\n".join(self.shared_state),
                },
                {
                    "role": "user",
                    "content": "First summarize the topic you choose from the memory and then create a paragraph."
                }
            ]
        # print(prompt_from_shared_memory, flush=True)

        model_response = query_llm(self.llm_config, prompt_from_shared_memory)
        time.sleep(1)
        with self.shared_state:
            self.shared_state.append(f'Agent {self.id}: ' + model_response)
        return model_response

# Ray version of shared memory
@ray.remote
class SharedMemory:
    def __init__(self):
        self.shared_memory = list()

    def get(self):
        return self.shared_memory

    def append(self, value):
        self.shared_memory.append(value)

@ray.remote
class RayWorker:
    def __init__(
        self, 
        id, shared_memory, llm_config,
        agent_role="You are a helpful and collaborative assistant who creates insightful explanations for the data stored in the shared memory."
        ):
        self.id = id
        self.shared_state = shared_memory
        self.llm_config = llm_config
        self.agent_role = agent_role

    # Based on the shared memory, create a new task and execute it
    def do_task(self):
        shared_state = ray.get(self.shared_state.get.remote())
        prompt_from_shared_memory = [
            {
                "role": "system",
                "content": 
                    "\n# Agent specific role information\n"
                    + f"- Your Role:{self.agent_role}\n"
                    + f"- Your Agent Id: {self.id}\n"
                    + self.llm_config["system_prompt"]
                    + "\n\n# SHARED MEMORY ACROSS AI AGENTS:\n" + "\n".join(shared_state),
            },
            {
                "role": "user",
                "content": "First summarize the topic you choose from the memory and then create a paragraph."
            }
        ]
        # print(prompt_from_shared_memory, flush=True)
        model_response = query_llm(self.llm_config, prompt_from_shared_memory)
        ray.get(self.shared_state.append.remote(f'Agent {self.id}: ' + model_response))
        return model_response

# Example usage
mode = "roy"    # "roy" or "ray"
if __name__ == "__main__":
    try:
        time_start = time.time()
        num_agents = 3
        num_iteration = 3

        ray.init()
        if mode == "roy":
            shared_memory = RoyList()
            with shared_memory:
                shared_memory.append("Goal: Survey on distributed shared memory.")
            ai_agents = [Worker.remote(id, shared_memory, llm_config, agent_roles[id]) for id in range(num_agents)]
            for iteration in range(num_iteration):
                print(f"\n\nIteration {iteration + 1}::", flush=True)
                tasks = [agent.do_task.remote() for agent in ai_agents]
                ray.get(tasks)

            print("\n\nFinal shared memory::", flush=True)
            with shared_memory:
                print(f"Length: {len(shared_memory)}", flush=True)
                for entry in shared_memory:
                    print(f"###\n{entry}", flush=True)
        elif mode == "ray":
            shared_memory_ray = SharedMemory.remote()
            shared_memory = ray.get(shared_memory_ray.append.remote("Goal: Survey on distributed shared memory."))
            ai_agents = [RayWorker.remote(id, shared_memory_ray, llm_config, agent_roles[id]) for id in range(num_agents)]
            for iteration in range(num_iteration):
                print(f"\n\nIteration {iteration + 1}::", flush=True)
                tasks = [agent.do_task.remote() for agent in ai_agents]
                ray.get(tasks)

            print("\n\nFinal shared memory::", flush=True)
            # get up to date list
            shared_memory = ray.get(shared_memory_ray.get.remote())
            print(f"Length: {len(shared_memory)}", flush=True)
            for entry in shared_memory:
                print(f"###\n{entry}", flush=True)
        
    finally:
        # print time
        time_end = time.time()
        print(f"\n\nTime taken: {time_end - time_start} seconds.", flush=True)
        ray.shutdown()

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained("TheBloke/SOLAR-10.7B-Instruct-v1.0-GPTQ")

# Load the model
model = AutoModelForCausalLM.from_pretrained("TheBloke/SOLAR-10.7B-Instruct-v1.0-GPTQ", device_map="auto")

# Generate text
prompt = "Here is a prompt to start the generation"
input_ids = tokenizer.encode(prompt, return_tensors="pt")

output_ids = model.generate(input_ids, max_length=200, do_sample=True, top_p=0.95, top_k=0)[0]
output_text = tokenizer.decode(output_ids, skip_special_tokens=True)

print(output_text)
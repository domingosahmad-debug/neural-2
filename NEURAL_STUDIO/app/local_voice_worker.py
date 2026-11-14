"""One bounded CPU answer; model is released when this process exits."""
import json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.tools/helper-python'))
from llama_cpp import Llama

def main():
 data=json.loads(sys.stdin.read(30000));path=root/'.models/Qwen3-0.6B-Q8_0.gguf'
 if not path.is_file():raise ValueError('The local helper model has not been installed on this PC')
 start=time.monotonic();llm=Llama(model_path=str(path),n_ctx=2048,n_threads=2,n_batch=128,n_gpu_layers=0,verbose=False)
 prompt='<|im_start|>system\nYou are Relay, a concise studio assistant. The human is Tony. Address him as Tony. Use supplied facts. Say when uncertain. Only supplied validated UI controls exist; no direct tools or editing, no invented facts or abilities. Answer in under 100 words.<|im_end|>\n<|im_start|>user\n'+str(data['prompt'])[-6200:]+'\n/no_think<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
 text='';tokens=0
 for chunk in llm(prompt,max_tokens=200,temperature=.3,top_p=.9,stream=True,stop=['<|im_end|>']):
  text+=chunk['choices'][0].get('text','');tokens+=1
  if time.monotonic()-start>50:break
 llm.close();print(json.dumps({'text':text.strip(),'output_tokens':tokens,'elapsed_seconds':round(time.monotonic()-start,2),'gpu_layers':0,'cpu_threads':2,'unloaded_on_exit':True}))

if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'error':str(e)[:500]}));sys.exit(1)

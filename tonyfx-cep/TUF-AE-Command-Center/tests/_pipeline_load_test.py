import time,psutil,os,torch
from transformers import T5EncoderModel,BitsAndBytesConfig
from diffusers import LTXImageToVideoPipeline
t=time.time(); q=BitsAndBytesConfig(load_in_8bit=True)
te=T5EncoderModel.from_pretrained(r"C:\Users\TUF\Documents\TonyFX Local Engine\models\video\huggingface\models--Lightricks--LTX-Video\snapshots\8984fa25007f376c1a299016d0957a37a2f797bb",subfolder="text_encoder",quantization_config=q,low_cpu_mem_usage=True,local_files_only=True)
print("text",round(time.time()-t,1),round(psutil.Process().memory_info().rss/1024**3,2),flush=True)
p=LTXImageToVideoPipeline.from_pretrained(r"C:\Users\TUF\Documents\TonyFX Local Engine\models\video\huggingface\models--Lightricks--LTX-Video\snapshots\8984fa25007f376c1a299016d0957a37a2f797bb",text_encoder=te,dtype=torch.bfloat16,low_cpu_mem_usage=True,local_files_only=True)
print("pipeline",round(time.time()-t,1),round(psutil.Process().memory_info().rss/1024**3,2),flush=True)
p.enable_sequential_cpu_offload(); print("offload_ok",flush=True)

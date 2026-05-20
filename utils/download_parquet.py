# 00_download_parquet.py
from huggingface_hub import hf_hub_download
import os

def download_dataset(local_dir: str = "../data"):
    os.makedirs(local_dir, exist_ok=True)
    hf_hub_download(
        repo_id="OrneCorsetti/mcd-austral-clinical-trials",
        filename="clinical_trials.parquet",
        repo_type="dataset",
        local_dir=local_dir
    )
    print("✅ Descarga completa")
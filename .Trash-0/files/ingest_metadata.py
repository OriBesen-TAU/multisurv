import os
import glob
import pymongo
import pandas as pd
from tqdm import tqdm

# 1) Adjust these paths to your Windows host mount inside Docker:
BASE_DIR = r"/mnt/data/Processed_Data"        # inside the container this maps to D:/user/…
MONGO_URI = "mongodb://mongo:27017"           # if running from another container
# If running from your laptop over VPN, use: mongodb://<lab-host-ip>:27017

# 2) Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client["multimodal_metadata"]

# 3) For each modality folder, read every TSV and upsert into a collection
modalities = {
    "clinical": "Clinical",
    "cnv":      "CNV",
    "dnam":     "DNAm",
    "mirna":    "miRNA-seq",
    "mrna":     "RNA-seq",
    "wsi":      "WSI"
}

for coll_name, folder in modalities.items():
    coll = db[coll_name]
    path = os.path.join(BASE_DIR, folder, "*.tsv")
    files = glob.glob(path)
    print(f"Ingesting {len(files)} files into collection `{coll_name}`…")
    for f in tqdm(files):
        df = pd.read_csv(f, sep="\t", dtype=str)
        # Assume each TSV has a unique patient ID column, e.g. "submitter_id"
        pid = df.columns[1]  # or df['submitter_id'][0], adjust as needed
        # Convert DataFrame to dictionary
        doc = {
            "patient_id": os.path.splitext(os.path.basename(f))[0],
            "data": df.to_dict(orient="list")
        }
        # Upsert by patient_id
        coll.replace_one({"patient_id": doc["patient_id"]}, doc, upsert=True)

print("✅ Done ingesting all metadata.")

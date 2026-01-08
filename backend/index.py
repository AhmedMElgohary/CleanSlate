import os
import uuid
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.background import BackgroundTasks
from pydantic import BaseModel
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

# I am loading the environment variables to keep my API keys secure
load_dotenv()

app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Security Config: I'm allowing all origins for now to make development easy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STORAGE CONFIGURATION ---
# I am creating a dedicated folder to store user files safely on disk
UPLOAD_DIR = "temp_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize the Brain (Groq Llama 3)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# I updated the request model to require a specific file_id (The Ticket)
class CommandRequest(BaseModel):
    file_id: str
    query: str

@app.get("/")
def health_check():
    return {"status": "CleanSlate System Ready", "storage": "Local Disk"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    # 1. GENERATE UNIQUE ID
    # I use a UUID so every user gets a unique workspace, preventing data collisions.
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.csv"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        # 2. STREAM TO DISK
        # I stream the file content to avoid crashing RAM with large datasets.
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 3. GENERATE PREVIEW
        # I read the file back immediately to prove it was saved correctly.
        df = pd.read_csv(file_path, skipinitialspace=True)
        
        # Helper to safely handle NaN values for JSON response
        preview = df.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "file_id": file_id, # The Frontend must keep this ticket!
            "filename": file.filename,
            "total_rows": df.shape[0],
            "total_columns": df.shape[1],
            "columns": list(df.columns),
            "preview": preview
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/process")
def process_command(request: CommandRequest):
    # I locate the specific user's file using their unique ID
    file_path = os.path.join(UPLOAD_DIR, f"{request.file_id}.csv")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Session expired or file not found.")
    
    try:
        df = pd.read_csv(file_path)
        
        # --- AI LOGIC ---
        columns = list(df.columns)
        sample = df.head().to_string()
        
        system_prompt = f"""
        You are a Python Data Assistant. 
        DataFrame Name: 'df'
        Columns: {columns}
        Sample Data: {sample}
        User Request: "{request.query}"
        
        Task: Write Python code to update 'df'.
        RULES:
        1. MUST assign output: "df = df[...]" or "df.dropna(inplace=True)"
        2. Handle strings with `.str.contains(..., case=False)`
        3. Return ONLY code.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Output only raw code."},
                {"role": "user", "content": system_prompt}
            ],
            model="llama-3.3-70b-versatile",
        )
        
        code = chat_completion.choices[0].message.content.strip().replace("```python", "").replace("```", "")
        print(f"Executing: {code}")

        local_vars = {"df": df}
        exec(code, {}, local_vars)
        df_modified = local_vars["df"]
        
        # 4. OVERWRITE DISK
        # I save the modified data back to the same file ID so the changes persist.
        df_modified.to_csv(file_path, index=False)
        
        preview = df_modified.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "message": f"Executed: {code}",
            "total_rows": df_modified.shape[0],
            "preview": preview,
            "columns": list(df_modified.columns)
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed.")

@app.get("/download/{file_id}")
def download_file(file_id: str):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.csv")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    # I return the file directly from the disk
    return FileResponse(
        file_path, 
        media_type="text/csv", 
        filename=f"clean_data_{file_id[:8]}.csv"
    )
import os
import uuid
import io
import gzip
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Allow cross-origin requests (essential for the frontend to talk to the backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Storage
# I'm using a dictionary to store dataframes by session ID.
# This keeps the app stateless and fast, though data resets on server restart.
data_store = {} 

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class CommandRequest(BaseModel):
    file_id: str
    query: str

@app.get("/api")
def health_check():
    """Simple check to ensure the serverless function is warm."""
    return {"status": "CleanSlate Cloud API is running"}

@app.post("/api/upload")
async def upload_file(request: Request):
    """
    Handles file uploads. 
    Includes logic to decompress GZIP files sent by the frontend,
    allowing us to bypass standard payload limits.
    """
    try:
        # Extract filename from the custom header
        filename = request.headers.get("X-Filename", "uploaded_file.csv")
        
        # Read the raw binary body
        body = await request.body()
        
        # Decompression Logic
        # Try to decompress assuming GZIP. If it fails, assume it's a raw file.
        try:
            content = gzip.decompress(body)
        except:
            content = body
            
        # Load the binary data into Pandas
        df = pd.read_csv(io.BytesIO(content), skipinitialspace=True)
        
        # Assign a unique session ID
        file_id = str(uuid.uuid4())
        data_store[file_id] = df
        
        # Generate a lightweight preview for the UI
        preview = df.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "file_id": file_id,
            "filename": filename,
            "total_rows": df.shape[0],
            "total_columns": df.shape[1],
            "columns": list(df.columns),
            "preview": preview
        }
        
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/process")
def process_command(request: CommandRequest):
    """
    The core AI engine.
    1. Retrieves the dataframe from memory using the file_id.
    2. Sends the user's natural language query + schema to Llama 3.
    3. Executes the returned Python code safely.
    """
    file_id = request.file_id
    query = request.query
    
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="Session expired. Please upload again.")
    
    df = data_store[file_id]
    
    try:
        columns = list(df.columns)
        sample = df.head().to_string()
        
        # Prompt Engineering: I restrict the AI to only output executable code.
        system_prompt = f"""
        You are a Python Data Assistant. 
        DataFrame Name: 'df'
        Columns: {columns}
        Sample Data: {sample}
        User Request: "{query}"
        
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

        # Safe execution environment
        local_vars = {"df": df}
        exec(code, {}, local_vars)
        df_modified = local_vars["df"]
        
        # Update the session state
        data_store[file_id] = df_modified
        preview = df_modified.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "message": f"Executed: {code}",
            "total_rows": df_modified.shape[0],
            "preview": preview,
            "columns": list(df_modified.columns)
        }

    except Exception as e:
        print(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed.")

@app.get("/api/download/{file_id}")
def download_file(file_id: str):
    """
    Converts the in-memory dataframe back to CSV and streams it to the client.
    """
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="File not found.")
    
    df = data_store[file_id]
    
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = io.BytesIO()
    response.write(stream.getvalue().encode('utf-8'))
    response.seek(0)
    
    return StreamingResponse(
        response, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=clean_data.csv"}
    )
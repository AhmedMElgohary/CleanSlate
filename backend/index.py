import os
import uuid
import io
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS to allow all origins (adjust for production if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Storage Configuration ---
# Using in-memory dictionary for serverless deployment (Vercel)
# Keys are Session IDs (UUIDs) to ensure user isolation.
data_store = {} 

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class CommandRequest(BaseModel):
    file_id: str
    query: str

@app.get("/api")
def health_check():
    """Simple health check endpoint."""
    return {"status": "CleanSlate Cloud API is running"}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Handles CSV file uploads.
    Reads file into memory and assigns a unique Session ID.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    try:
        # Read file content into byte stream
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents), skipinitialspace=True)
        
        # Generate unique Session ID
        file_id = str(uuid.uuid4())
        
        # Store DataFrame in memory
        data_store[file_id] = df
        
        # Generate preview (first 5 rows)
        preview = df.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "file_id": file_id,
            "filename": file.filename,
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
    Processes natural language queries using Llama-3.
    Updates the DataFrame in memory based on the generated Python code.
    """
    file_id = request.file_id
    query = request.query
    
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="Session expired. Please upload again.")
    
    df = data_store[file_id]
    
    try:
        # Prepare context for the LLM
        columns = list(df.columns)
        sample = df.head().to_string()
        
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

        # Generate code via Groq
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Output only raw code."},
                {"role": "user", "content": system_prompt}
            ],
            model="llama-3.3-70b-versatile",
        )
        
        # Extract and clean code
        code = chat_completion.choices[0].message.content.strip().replace("```python", "").replace("```", "")
        print(f"Executing: {code}")

        # Execute code in safe local scope
        local_vars = {"df": df}
        exec(code, {}, local_vars)
        df_modified = local_vars["df"]
        
        # Update state
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
    Converts the DataFrame back to CSV and streams it to the client.
    """
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="File not found.")
    
    df = data_store[file_id]
    
    # Convert DataFrame to CSV string
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    # Prepare byte stream for response
    response = io.BytesIO()
    response.write(stream.getvalue().encode('utf-8'))
    response.seek(0)
    
    return StreamingResponse(
        response, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=clean_data.csv"}
    )
import os
import uuid
import io
import gzip
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
from groq import Groq
from dotenv import load_dotenv
import traceback

load_dotenv()

app = FastAPI()

# Allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Storage
data_store = {} 

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class CommandRequest(BaseModel):
    file_id: str
    query: str

@app.get("/api")
def health_check():
    return {"status": "CleanSlate Cloud API is running"}

@app.post("/api/upload")
async def upload_file(request: Request):
    try:
        filename = request.headers.get("X-Filename", "uploaded_file.csv")
        body = await request.body()
        
        # Decompression Logic
        try:
            content = gzip.decompress(body)
        except:
            content = body
            
        df = pd.read_csv(io.BytesIO(content), skipinitialspace=True)
        
        file_id = str(uuid.uuid4())
        data_store[file_id] = df
        
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
    file_id = request.file_id
    query = request.query
    
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="Session expired. Please upload again.")
    
    df = data_store[file_id]
    
    # Initialize 'code' so it exists even if the AI fails early
    code = "No code generated"

    try:
        # Instead of random rows, we show the Structure + The Junk + The Stats
        buffer = io.StringIO()
        df.info(buf=buffer)
        df_info = buffer.getvalue()
        
        head_rows = df.head(5).to_string()
        tail_rows = df.tail(5).to_string()
        
        # Safe sampling for description (don't crash on small files)
        try:
            description = df.describe().to_string()
        except:
            description = "No numeric data"
        
        # 2. STRICT SYSTEM PROMPT (The Fix for Reliability) 🛡️
        system_prompt = f"""
        You are a Python Data Expert. 
        DataFrame Name: 'df'
        
        # DATA PROFILE:
        {df_info}
        
        # STATISTICAL SUMMARY:
        {description}

        # DATA PREVIEW (Head):
        {head_rows}

        # DATA PREVIEW (Tail - Check for footer junk):
        {tail_rows}
        
        # USER REQUEST: "{query}"
        
        # YOUR TASK:
        Write Python code to clean or transform 'df' in-place.
        
        # ⚠️ CRITICAL RULES:
        1. IF DATES (Convert/Format):
           # Always use this exact 2-step process:
           df['col'] = pd.to_datetime(df['col'], errors='coerce') 
           df['col'] = df['col'].dt.strftime('%d/%m/%Y') # Change format code as requested
           
        2. 🎯 FOCUS: Execute ONLY the user's specific request. Do NOT spontaneously clean other columns (dates, currency) unless explicitly asked.
        3. 🛡️ SAFETY: When doing string operations (split, replace), ALWAYS handle missing values (NaN). 
           - BEST PRACTICE: Use the .str accessor (e.g., df['col'].str.split(...)) which handles NaNs automatically.
        4. 🐍 ALIASES: You have access to 'pd' (pandas) and 'np' (numpy).IF DUPLICATES:
           
        5. duplicates: df = df.drop_duplicates(inplace=True)
           
        5. GENERAL:
           - Return ONLY valid Python code. No markdown.
           - Do NOT re-load the file.
        """

        # 3. Call Groq with Temperature=0 (The Fix for "10 Clicks") ❄️
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Output only raw code."},
                {"role": "user", "content": system_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0, # Zero Creativity = 100% Stability
        )
        
        code = chat_completion.choices[0].message.content.strip()
        code = code.replace("```python", "").replace("```", "").strip()
        
        # Print code to terminal so you can verify it
        print(f"Executing: {code}")

        # 4. Execute with 'pd' passed in
        local_vars = {
            "df": df, 
            "pd": pd, 
            "pandas": pd, 
            "np": np, 
            "numpy": np
        } 
        exec(code, {}, local_vars)
        df_modified = local_vars["df"]
        
        data_store[file_id] = df_modified
        preview = df_modified.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "message": f"Executed: {code}",
            "generated_code": code,
            "total_rows": df_modified.shape[0],
            "preview": preview,
            "columns": list(df_modified.columns)
        }

    except Exception as e:
        error_msg = str(e)
        full_trace = traceback.format_exc()
        print(f"❌ Error: {error_msg}")
        
        # RETURN ERROR AS JSON SO FRONTEND SEES IT
        return JSONResponse(
            status_code=500, 
            content={
                "error": error_msg,
                "failed_code": code,
                "trace": full_trace
            }
        )

@app.get("/api/download/{file_id}")
def download_file(file_id: str):
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
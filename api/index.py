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
        # 1. Get Filename & Content
        filename = request.headers.get("X-Filename", "uploaded_file.csv")
        body = await request.body()
        
        # 2. Decompression Logic
        try:
            content = gzip.decompress(body)
        except:
            content = body
            
        # 3. Smart Reader
        file_stream = io.BytesIO(content)
        df = None
        error_log = []

        # Strategy A: Trust the filename extension first
        if filename.lower().endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(file_stream)
            except Exception as e:
                error_log.append(f"Excel read failed: {str(e)}")
        
        # Strategy B: If A didn't work (or filename was wrong), try CSV (UTF-8)
        if df is None:
            try:
                file_stream.seek(0) # Reset pointer
                df = pd.read_csv(file_stream, skipinitialspace=True)
            except UnicodeDecodeError:
                # It implies the file is actually Binary (Excel), not Text.
                error_log.append("CSV UTF-8 failed (Binary detected)")
            except Exception as e:
                error_log.append(f"CSV read failed: {str(e)}")

        # Strategy C: If still nothing, it might be Excel masquerading as CSV
        if df is None:
            try:
                file_stream.seek(0)
                df = pd.read_excel(file_stream)
            except Exception as e:
                 error_log.append(f"Excel fallback failed: {str(e)}")
                 
        # Strategy D: Last Resort - CSV with 'latin1' encoding (for old files)
        if df is None:
            try:
                file_stream.seek(0)
                df = pd.read_csv(file_stream, encoding='latin1')
            except Exception as e:
                error_log.append(f"CSV Latin1 failed: {str(e)}")

        # 4. Final Check
        if df is None:
             raise Exception(f"Could not read file. Attempts: {'; '.join(error_log)}")

        # INITIALIZE HISTORY STACK 🥞
        file_id = str(uuid.uuid4())
        data_store[file_id] = {
            "original": df.copy(),
            "history": [df.copy()], # Start with initial state
            "filename": filename
        }
        
        # Send 100 rows for scrolling
        preview = df.head(100).replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient='records')        
        
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
        if "openpyxl" in str(e):
             raise HTTPException(status_code=500, detail="Server missing Excel support. Please add 'openpyxl' to requirements.txt")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/undo")
def undo_last_action(request: CommandRequest):
    file_id = request.file_id
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="Session expired.")
    
    history = data_store[file_id]["history"]
    
    # If we have more than 1 state (Original + Changes), pop the last one
    if len(history) > 1:
        history.pop() # Remove the latest action
        
    current_df = history[-1] # Go back to previous
    
    # Handle NaN/Inf for JSON safety
    preview = current_df.head(100).replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient='records')
    
    return {
        "message": "↩️ Undo successful",
        "total_rows": current_df.shape[0],
        "preview": preview,
        "columns": list(current_df.columns)
    }

@app.post("/api/process")
def process_command(request: CommandRequest):
    file_id = request.file_id
    query = request.query.strip().lower()
    
    if file_id not in data_store:
        raise HTTPException(status_code=404, detail="Session expired. Please upload again.")
    
    # RESET LOGIC
    try:
        if query in ["reset", "restart", "restore", "reset data", "restore original", "start over"]:
            # Reset history to just the original
            original = data_store[file_id]["original"].copy()
            data_store[file_id]["history"] = [original]
        
            preview = original.head(100).replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient='records')
            return {
            "message": "🔄 Data reset to original.",
            "generated_code": "# Reset executed",
            "total_rows": original.shape[0],
            "preview": preview,
            "columns": list(original.columns)
            }

        # Get current state
        history = data_store[file_id]["history"]
        df = history[-1] # Always work on the latest version

        buffer = io.StringIO()
        df.info(buf=buffer)
        df_info = buffer.getvalue()
        
        head_rows = df.head(5).to_string()
        tail_rows = df.tail(5).to_string()
        
        try:
            description = df.describe().to_string()
        except:
            description = "No numeric data"
        
        # 2. STRICT SYSTEM PROMPT
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
        Write Python code to process 'df'.

        # 🚦 MODES OF OPERATION:
        
        MODE A: ACTION (Clean, Transform, Edit)
        - If the user wants to CHANGE the data (e.g. "remove duplicates", "fix dates"):
        - Apply changes to 'df' directly in-place.
        - Do NOT create a 'result' variable.
        
        MODE B: INSPECTION (Find, Show, Filter)
        - If the user wants to SEE specific rows (e.g. "show empty rows", "find outliers"):
        - Create a NEW DataFrame named 'result' containing only those rows.
        - Do NOT modify 'df'.
        
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
            "df": df.copy(), # Work on a copy first 
            "pd": pd, 
            "pandas": pd, 
            "np": np, 
            "numpy": np
        } 
        exec(code, {}, local_vars)
        
        # Did the AI create a 'result' variable?
        if "result" in local_vars and isinstance(local_vars["result"], pd.DataFrame):
            # INSPECTION MODE (Don't update history)
            df_display = local_vars["result"]
            message = f"Executed: {code} (Viewing Mode)"
        else:
            # ACTION MODE (Update History)
            df_modified = local_vars["df"]
            df_display = df_modified
            
            # Append to history
            history.append(df_modified)
            
            # MEMORY SAFETY: Limit history to 4 items (Original + 3 Undos)
            if len(history) > 4:
                history.pop(1) # Remove oldest change (keep original at 0)
                
            message = f"Executed: {code}"
        
        # Send 100 rows back so user can scroll
        preview = df_display.head(100).replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient='records')        
        
        return {
            "message": f"Executed: {code}",
            "generated_code": code,
            "total_rows": df_display.shape[0],
            "preview": preview,
            "columns": list(df_display.columns)
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
    
    # Download latest version from history
    df = data_store[file_id]["history"][-1]
    original_filename = data_store[file_id].get("filename", "data.csv")

    if original_filename.lower().endswith(('.xlsx', '.xls')):
        output = io.BytesIO()
        try:
            df.to_excel(output, index=False, engine='openpyxl')
        except:
             df.to_csv(output, index=False)
        output.seek(0)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        clean_name = os.path.splitext(original_filename)[0] + "_clean.xlsx"
    else:
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        output = io.BytesIO()
        output.write(stream.getvalue().encode('utf-8'))
        output.seek(0)
        media_type = "text/csv"
        clean_name = os.path.splitext(original_filename)[0] + "_clean.csv"
    
    return StreamingResponse(output, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={clean_name}"})
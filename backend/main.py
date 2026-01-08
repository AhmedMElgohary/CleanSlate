from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import os
from groq import Groq
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

# Initialize the application
app = FastAPI()

# Security configuration: Allow the Frontend to communicate with this Backend
# TODO: In production, limit this to the specific domain of the React app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Key = Filename, Value = The DataFrame
data_store = {}

class CommandRequest(BaseModel):
    filename: str
    query: str

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY")
)

@app.get("/")
def health_check():
    # Simple endpoint to verify the server is running correctly
    return {"status": "CleanSlate API is active", "version": "1.0.0"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. VALIDATION: Check file extension
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    try:
        # 2. READING: Read the file content into memory
        contents = await file.read()
        
        # 3. PROCESSING: Convert binary bytes -> Pandas DataFrame
        # io.BytesIO makes the raw bytes look like a filepath to Pandas
        df = pd.read_csv(io.BytesIO(contents), skipinitialspace=True)

        # We store the dataframe using the filename as the ID
        data_store[file.filename] = df
        
        # 4. PREVIEW: Get the first 5 rows and handle NaN (empty) values
        # We replace NaN with None because JSON cannot handle NaN
        preview = df.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "filename": file.filename,
            "total_rows": df.shape[0],
            "total_columns": df.shape[1],
            "columns": list(df.columns),
            "preview": preview
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
@app.post("/process")
def process_command(request: CommandRequest):
    filename = request.filename
    query = request.query
    
    if filename not in data_store:
        raise HTTPException(status_code=404, detail="File not found.")
    
    df = data_store[filename]
    
# 1. Prepare the Prompt
    columns = list(df.columns)
    # We show the AI a sample of the data so it sees "Designer" has a capital D
    sample_data = df.head().to_string() 
    
    system_prompt = f"""
    You are a Python Data Assistant. 
    DataFrame Name: 'df'
    Columns: {columns}
    Sample Data:
    {sample_data}
    
    User Request: "{query}"
    
    Task: Write Python code to update 'df'.
    
    CRITICAL RULES:
    1. You MUST use assignment or inplace=True. Example: "df = df[...]"
    2. When filtering strings, use `.str.contains(..., case=False)` if appropriate, or handle capitalization carefully based on the Sample Data.
    3. Return ONLY the code string. No markdown.
    """

    try:
        # 2. Call AI
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a coding assistant. Output only raw code."},
                {"role": "user", "content": system_prompt}
            ],
            model="llama-3.3-70b-versatile",
        )
        
        code_to_run = chat_completion.choices[0].message.content.strip()
        code_to_run = code_to_run.replace("```python", "").replace("```", "").strip()
        
        print(f"🤖 AI Generated Code: {code_to_run}") # Check your terminal to see this!

        # 3. EXECUTE
        local_vars = {"df": df}
        exec(code_to_run, {}, local_vars)
        
        # 4. CAPTURE THE CHANGE
        # We verify if 'df' was actually updated in the local scope
        df_modified = local_vars["df"]
        
        # Save to memory
        data_store[filename] = df_modified
        
        # 5. RETURN
        preview = df_modified.head().replace({float('nan'): None}).to_dict(orient='records')
        
        return {
            "message": f"Executed: {code_to_run}",
            "total_rows": df_modified.shape[0],
            "preview": preview,
            "columns": list(df_modified.columns)
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="The AI failed to generate valid code.")

@app.get("/download/{filename}")
def download_file(filename: str):
    # 1. Check if file exists in memory
    if filename not in data_store:
        raise HTTPException(status_code=404, detail="File not found.")
    
    df = data_store[filename]
    
    # 2. Convert DataFrame to CSV String
    # index=False means "don't include the row numbers (0, 1, 2...)"
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    # 3. Reset cursor to the start of the stream
    response = io.BytesIO()
    response.write(stream.getvalue().encode('utf-8'))
    response.seek(0)
    
    # 4. Stream it back to the user
    return StreamingResponse(
        response, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=clean_{filename}"}
    )
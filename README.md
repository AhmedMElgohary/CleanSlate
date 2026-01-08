# CleanSlate Deployed and Running on Vercel

* Live Link: (https://clean-slate-cgt0yfd5p-ahmedmelgoharys-projects.vercel.app/)

## Overview
CleanSlate is an MVP (Minimum Viable Product) designed to demonstrate how LLMs can bridge the gap between non-technical users and Pandas manipulation. It is currently optimized for lightweight datasets (~5MB) and rapid iteration." It allows users to upload raw CSV files and manipulate them using plain English instructions, eliminating the need to write Python scripts for every new dataset.

I designed the architecture to be secure and stateless. It uses a session-based system to ensure that multiple users can process data simultaneously without any risk of data overlapping. The application is fully deployed and hosted on Vercel.

## Key Features
* Natural Language Processing: I integrated Llama 3.3 (via Groq) to translate user commands into executable Python code instantly.
* Session Isolation: Every upload generates a unique UUID. This ensures strict data privacy between concurrent users.
* In-Memory Processing: Data is processed in RAM for speed and security, then discarded when the session ends.
* Serverless Deployment: The backend and frontend are optimized to run on Vercel's cloud infrastructure.

## Tech Stack
* Frontend: React + Vite
* Backend: Python FastAPI
* Data Engine: Pandas
* AI Model: Llama 3.3-70b
* Deployment: Vercel

## How It Works
1. Upload: The user uploads a CSV. The backend assigns it a random Session ID.
2. Instruction: The user types a command (e.g., "Remove rows where the Job is Designer").
3. Code Generation: The backend sends the command and a small sample of the data to the LLM. The model returns only the specific Python code needed for the transformation.
4. Execution: The system executes the code on the dataframe associated with that specific session.
5. Result: The cleaned file is generated and ready for download.

## Quick Start (Local Development)
To run this project on your own machine:

1. Clone the repository
   ```bash
   git clone [https://github.com/AhmedMElgohary/CleanSlate.git]

2. Install Python dependencies
    ```bash
    pip install -r requirements.txt

3. Install Frontend dependencies
    ```bash
    cd frontend
    npm install

4. Set up Environment Variables Create a .env file in the root folder with your API key:
    GROQ_API_KEY=your_key_here

5. Run the App:
    
    *Backend:
    ```bash
    uvicorn api.index:app --reload

    *Frontend:
    ```bash
    npm run dev
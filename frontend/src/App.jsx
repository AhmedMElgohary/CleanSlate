import { useState } from 'react'
import pako from 'pako' // I use pako to handle GZIP compression in the browser
import './App.css'

function App() {
  // Configuration: Points to the Vercel serverless functions
  const API_BASE_URL = "/api";
  
  const [fileId, setFileId] = useState(null)
  const [file, setFile] = useState(null)
  const [data, setData] = useState(null)
  const [uploading, setUploading] = useState(false)
  
  // AI Interaction State
  const [query, setQuery] = useState("")
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    // Reset state when a new file is selected to avoid UI confusion
    setError("");
    setMessage("");
    setData(null);
    setFileId(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setUploading(true);
    setError("");
    setMessage("");

    try {
      // Step 1: Read the file into memory
      const fileBuffer = await file.arrayBuffer();

      // Step 2: Client-Side Compression
      // I compress the file before sending it to bypass Vercel's 4.5MB payload limit.
      // This allows me to handle files ~10x larger without needing a paid storage bucket.
      const compressed = pako.gzip(new Uint8Array(fileBuffer));

      // Step 3: Prepare the upload
      // I send this as a raw binary Blob with a custom header for the filename,
      // which is more efficient here than standard Multipart FormData.
      const blob = new Blob([compressed], { type: 'application/gzip' });
      
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        headers: {
            "X-Filename": file.name, 
            "Content-Type": "application/gzip"
        },
        body: blob,
      });

      const result = await response.json();

      if (response.ok) {
        setData(result);
        setFileId(result.file_id); // Capture the session ID for subsequent AI operations
      } else {
        setError(result.detail || "Upload failed");
      }
    } catch (err) {
      console.error(err);
      setError("Network error. The file might still be too large for the serverless function.");
    }
    
    setUploading(false);
  };

  const handleProcess = async () => {
    if (!query) return;
    setProcessing(true);
    setMessage("");
    setError("");

    try {
      // I send the query + file_id so the backend knows which dataframe to modify
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId, query: query }),
      });

      const result = await response.json();

      if (response.ok) {
        if (result.error) {
           setError(result.error);
        } else {
           // Update the UI with the new data preview
           setData(prev => ({
             ...prev, 
             preview: result.preview, 
             total_rows: result.total_rows,
             columns: result.columns
           }));
           setMessage(result.message);
           setQuery("");
        }
      } else {
        setError(result.detail || "Processing failed");
      }
    } catch (err) {
      setError("Failed to connect to AI logic.");
    }
    setProcessing(false);
  };

  const handleDownload = () => {
    if (!fileId) return;
    
    // Trigger a direct download from the backend stream
    const url = `${API_BASE_URL}/download/${fileId}`;
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `clean_data.csv`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
  };

  return (
    <div className="container">
      <h1>CleanSlate 🧹</h1>
      
      {/* Upload Section */}
      <div className="upload-box">
        <input type="file" accept=".csv" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? "Compressing & Uploading..." : "Upload CSV"}
        </button>
      </div>

      {error && <p style={{ color: "#ef4444", fontWeight: "bold" }}>{error}</p>}

      {/* Results & AI Interface */}
      {data && (
        <div className="results">
          <h3>File: {data.filename}</h3>
          <p>Rows: <strong>{data.total_rows}</strong> | Columns: <strong>{data.total_columns}</strong></p>
          
          <div className="ai-box" style={{ margin: "20px 0", display: "flex", gap: "10px" }}>
            <input 
              type="text" 
              placeholder="Ask AI: 'Remove empty rows'..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ flex: 1, padding: "10px", borderRadius: "6px", border: "1px solid #334155", color: "#0f172a" }}
            />
            <button onClick={handleProcess} disabled={processing}>
              {processing ? "Processing..." : "✨ Magic Fix"}
            </button>
          </div>
          
          <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end" }}>
            <button 
              onClick={handleDownload}
              style={{ backgroundColor: "#10b981", color: "white" }}
            >
              ⬇️ Download Clean CSV
            </button>
          </div>

          {message && <p style={{ color: "#4ade80", fontWeight: "bold", marginTop: "10px" }}>✅ {message}</p>}

          <h4>Data Preview:</h4>
          <div style={{ overflowX: "auto" }}>
            <table border="1" cellPadding="5" style={{ width: "100%", borderCollapse: "collapse" }}>
               <thead>
                <tr>
                  {data.columns.map((col) => <th key={col}>{col}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.preview.map((row, index) => (
                  <tr key={index}>
                    {data.columns.map((col) => <td key={col}>{row[col]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
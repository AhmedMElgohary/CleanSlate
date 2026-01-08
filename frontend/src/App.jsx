import { useState } from 'react'
import './App.css'

function App() {
  // CONFIGURATION: This points to the backend (relative path for Vercel)
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        setData(result);
        setFileId(result.file_id);
      } else {
        setError(result.detail || "Upload failed");
      }
    } catch (err) {
      setError("Network error. Is the backend running?");
    }
    
    setUploading(false);
  };

  const handleProcess = async () => {
    if (!query) return;
    setProcessing(true);
    setMessage("");
    setError("");

    try {
      // FIX: This now points to /process instead of /upload
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            file_id: fileId, 
            query: query 
        }),
      });

      const result = await response.json();

      if (response.ok) {
        if (result.error) {
           setError(result.error);
        } else {
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
    
    // FIX: Now uses the API_BASE_URL variable
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
      
      {/* Upload Box */}
      <div className="upload-box">
        <input type="file" accept=".csv" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? "Scanning..." : "Upload CSV"}
        </button>
      </div>

      {error && <p style={{ color: "#ef4444", fontWeight: "bold" }}>{error}</p>}

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
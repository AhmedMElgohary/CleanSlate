import { useState } from 'react'
import './App.css'

function App() {
  // I track the fileId to ensure we are editing the correct user session
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
    setFileId(null); // Reset the ticket when a new file is picked
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
      const response = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        setData(result);
        setFileId(result.file_id); // I save the session ticket here!
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
      const response = await fetch("http://127.0.0.1:8000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // I send the file_id so the backend knows which file to fix
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
    
    // I use the fileId to request the specific clean file
    const url = `http://127.0.0.1:8000/download/${fileId}`;
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
import { useState, useEffect } from 'react'
import './App.css'

function App() {
  // State for File Upload
  const [file, setFile] = useState(null)
  const [data, setData] = useState(null)
  const [uploading, setUploading] = useState(false)
  
  // State for AI Processing
  const [query, setQuery] = useState("")
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState("")
  
  // State for Errors
  const [error, setError] = useState("")

  // 1. Handle File Selection
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setError("");
    setMessage(""); // Clear old success messages
    setData(null);  // Clear old data when a new file is picked
  };

  // 2. Handle Upload Button Click
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
      } else {
        setError(result.detail || "Upload failed");
      }
    } catch (err) {
      setError("Network error. Is the backend running?");
    }
    
    setUploading(false);
  };

  // 3. Handle AI Command (The Magic Fix)
  const handleProcess = async () => {
    if (!query) return;
    setProcessing(true);
    setMessage("");
    setError("");

    try {
      const response = await fetch("http://127.0.0.1:8000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, query: query }),
      });

      const result = await response.json();

      if (response.ok) {
        if (result.error) {
           setError(result.error);
        } else {
           // Update the UI with the NEW cleaned data
           setData(prev => ({
             ...prev, 
             preview: result.preview, 
             total_rows: result.total_rows,
             columns: result.columns
           }));
           setMessage(result.message);
           setQuery(""); // Clear the input box
        }
      } else {
        setError(result.detail || "Processing failed");
      }
    } catch (err) {
      setError("Failed to connect to AI logic.");
    }
    setProcessing(false);
  };

  // 4. Handle Download
  const handleDownload = () => {
    if (!data?.filename) return;
    
    // We trigger a browser download by creating a hidden link and clicking it programmatically
    const url = `http://127.0.0.1:8000/download/${data.filename}`;
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `clean_${data.filename}`);
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
          {uploading ? "Scanning..." : "Upload CSV"}
        </button>
      </div>

      {/* Error Message */}
      {error && <p style={{ color: "#ef4444", fontWeight: "bold" }}>{error}</p>}

      {/* Results Section */}
      {data && (
        <div className="results">
          <h3>File Analysis: {data.filename}</h3>
          <p>Rows: <strong>{data.total_rows}</strong> | Columns: <strong>{data.total_columns}</strong></p>
          
          {/* AI Chat Interface */}
          <div className="ai-box" style={{ margin: "20px 0", display: "flex", gap: "10px" }}>
            <input 
              type="text" 
              placeholder="Ask AI: 'Remove empty rows' or 'Remove duplicates'" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ flex: 1, padding: "10px", borderRadius: "6px", border: "1px solid #334155", color: "#0f172a" }}
            />
            <button onClick={handleProcess} disabled={processing}>
              {processing ? "Processing..." : "✨ Magic Fix"}
            </button>
          </div>
          
          {/* Success Message */}
          {message && <p style={{ color: "#4ade80", fontWeight: "bold" }}>✅ {message}</p>}
          
          {/* NEW: Download Section */}
          <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end" }}>
            <button 
              onClick={handleDownload}
              style={{ backgroundColor: "#10b981", color: "white" }} // Green color for 'Success/Download'
            >
              ⬇️ Download Clean CSV
            </button>
          </div>
          
          <h4>Data Preview:</h4>
          {/* Scrollable Table Container */}
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
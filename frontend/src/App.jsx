import React, { useState } from 'react';
import pako from 'pako'; // Keep pako for GZIP compression
import { Upload, Play, Download, AlertCircle, X, Terminal, Wand2, Database } from 'lucide-react';
import './App.css'; // This now imports Tailwind

export default function LivingWorkbench() {
  // 🧠 STATE MANAGEMENT
  const [view, setView] = useState('upload'); // 'upload' | 'workbench'
  const [fileId, setFileId] = useState(null);
  const [data, setData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); 
  const [rowsCount, setRowsCount] = useState(0);
  const [isDragging, setIsDragging] = useState(false); // Visual cue for dragging

  // Configuration
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

  // 🔄 CORE UPLOAD LOGIC (Reused by both Click and Drop)
  const processFile = async (file) => {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      // 1. Read file
      const fileBuffer = await file.arrayBuffer();

      // 2. Compress (Your Pako Logic)
      const compressed = pako.gzip(new Uint8Array(fileBuffer));

      // 3. Create Blob
      const blob = new Blob([compressed], { type: 'application/gzip' });

      // 4. Upload
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        headers: {
          'X-Filename': file.name,
          'Content-Type': 'application/gzip',
        },
        body: blob,
      });

      if (!response.ok) {
        const errResult = await response.json();
        throw new Error(errResult.detail || 'Upload failed');
      }

      const result = await response.json();
      setFileId(result.file_id);
      setData(result.preview);
      setColumns(result.columns);
      setRowsCount(result.total_rows);
      setView('workbench');

    } catch (err) {
      console.error(err);
      setError({ message: err.message || "Failed to upload file." });
    } finally {
      setLoading(false);
      setIsDragging(false);
    }
  };

  // 🖱️ CLICK HANDLER
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  // 🖐️ DRAG & DROP HANDLERS
  const handleDragOver = (e) => {
    e.preventDefault(); // STOP the browser from opening the file
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault(); // STOP the browser from opening the file
    setIsDragging(false);
    
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  // 🤖 PROCESS COMMAND HANDLER
  const handleCommand = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId, query: query }),
      });

      const result = await response.json();

      if (!response.ok) {
        const detail = result.detail || {};
        throw { 
          message: detail.error || result.error || "AI Processing Failed", 
          code: detail.failed_code || result.failed_code
        };
      }

      setData(result.preview);
      setRowsCount(result.total_rows);
      setColumns(result.columns);
      setQuery(''); 
    } catch (err) {
      console.error("Command Error:", err);
      setError({ 
        message: err.message || "Something went wrong", 
        code: err.code || null 
      });
    } finally {
      setLoading(false);
    }
  };

  // 📥 DOWNLOAD HANDLER
  const handleDownload = () => {
    if (!fileId) return;
    window.location.href = `${API_BASE_URL}/download/${fileId}`;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-indigo-100">
      
      {/* 🛑 ERROR TOAST */}
      {error && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl px-4 animate-in slide-in-from-top-4 duration-300">
          <div className="bg-white rounded-xl shadow-2xl border border-red-100 overflow-hidden">
            <div className="p-4 flex items-start gap-3">
              <div className="p-2 bg-red-50 rounded-full text-red-500 flex-shrink-0">
                <AlertCircle size={20} />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-red-600">Action Failed</h3>
                <p className="text-slate-600 text-sm mt-1">{error.message}</p>
                {error.code && (
                  <div className="mt-3 bg-slate-900 rounded-lg p-3 relative group text-left">
                    <div className="absolute top-2 right-2 text-xs text-slate-500 uppercase font-mono">AI Code Attempt</div>
                    <pre className="text-xs text-green-400 font-mono overflow-x-auto whitespace-pre-wrap">
                      {error.code}
                    </pre>
                  </div>
                )}
              </div>
              <button onClick={() => setError(null)} className="p-1 hover:bg-slate-100 rounded-lg text-slate-400">
                <X size={18} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* VIEW: UPLOAD SCREEN */}
      {view === 'upload' && (
        <div className="h-screen flex flex-col items-center justify-center p-4">
          <div className="text-center mb-10 space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600 text-white mb-4 shadow-lg shadow-indigo-200">
              <Wand2 size={24} />
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">CleanSlate</h1>
            <p className="text-slate-500 text-lg">Your AI Data Engineer</p>
          </div>

          <label 
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              group relative flex flex-col items-center justify-center w-full max-w-lg h-64 rounded-3xl border-2 border-dashed 
              transition-all cursor-pointer shadow-sm hover:shadow-xl
              ${isDragging 
                ? 'border-indigo-500 bg-indigo-50 scale-105 shadow-xl ring-4 ring-indigo-500/20' 
                : 'border-slate-300 bg-white hover:border-indigo-500 hover:bg-indigo-50'}
            `}
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6 pointer-events-none">
              <div className={`
                p-4 rounded-full transition-colors mb-4
                ${isDragging ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-50 text-slate-400 group-hover:bg-indigo-100 group-hover:text-indigo-600'}
              `}>
                {loading ? <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div> : <Upload size={32} />}
              </div>
              <p className="mb-2 text-xl font-medium text-slate-700 group-hover:text-indigo-700">
                {isDragging ? 'Drop it like it\'s hot!' : 'Drop your CSV here'}
              </p>
              <p className="text-sm text-slate-400">or click to browse</p>
            </div>
            <input type="file" className="hidden" accept=".csv" onChange={handleFileChange} disabled={loading} />
          </label>
        </div>
      )}

      {/* VIEW: LIVING WORKBENCH */}
      {view === 'workbench' && (
        <div className="relative min-h-screen flex flex-col">
          
          {/* HEADER */}
          <header className="px-6 py-4 flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-30 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
                <Database size={16} />
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">Session Active</h2>
                <p className="text-xs text-slate-500">{rowsCount} rows • {columns.length} columns</p>
              </div>
            </div>
            <button 
              onClick={handleDownload}
              className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-colors shadow-lg shadow-slate-200 cursor-pointer"
            >
              <Download size={16} />
              Export CSV
            </button>
          </header>

          {/* MAIN WORKSPACE */}
          <main className="flex-1 p-6 max-w-7xl mx-auto w-full pb-32">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-100">
                    <tr>
                      {columns.map((col) => (
                        <th key={col} className="px-6 py-4 font-semibold text-slate-700 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.map((row, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        {columns.map((col) => (
                          <td key={`${i}-${col}`} className="px-6 py-4 text-slate-600 whitespace-nowrap">
                            {row[col]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.length === 0 && (
                <div className="p-12 text-center text-slate-400">
                  <p>No data to display</p>
                </div>
              )}
            </div>
          </main>

          {/* FLOATING COMMAND BAR */}
          <div className="fixed bottom-8 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4 z-40">
            <div className={`
              relative bg-white/90 backdrop-blur-xl p-2 rounded-2xl border border-white/20 shadow-2xl shadow-indigo-500/10 
              transition-all duration-300 ring-1 ring-black/5
              ${loading ? 'scale-95 opacity-80' : 'scale-100 opacity-100'}
            `}>
              <form 
                onSubmit={(e) => { e.preventDefault(); handleCommand(); }}
                className="flex items-center gap-2"
              >
                <div className="pl-3 text-indigo-500">
                  {loading ? (
                    <div className="animate-spin w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full" />
                  ) : (
                    <Terminal size={20} />
                  )}
                </div>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask CleanSlate to transform your data..."
                  className="flex-1 bg-transparent border-none text-slate-800 placeholder:text-slate-400 focus:ring-0 text-lg py-3 px-2 font-medium outline-none"
                  autoFocus
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="p-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 transition-colors shadow-md cursor-pointer"
                >
                  <Play size={20} fill="currentColor" />
                </button>
              </form>
            </div>
            <div className="text-center mt-3">
              <p className="text-xs text-slate-400 font-medium tracking-wide">
                PRO TIP: TRY "REMOVE DUPLICATES" OR "FIX DATES"
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
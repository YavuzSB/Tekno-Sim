import { PanelExtensionContext } from "@foxglove/studio-extension-types";
import { useEffect, useState, useRef } from "react";

type Props = {
  context: PanelExtensionContext;
};

interface Project {
  name: string;
  description?: string;
}

export function Panel({ context }: Props): JSX.Element {
  // State definitions
  const [projects, setProjects] = useState<string[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [mode, setMode] = useState<"SITL" | "HITL">("SITL");
  const [isApiOnline, setIsApiOnline] = useState<boolean>(false);
  const [isBuilding, setIsBuilding] = useState<boolean>(false);
  const [isLaunched, setIsLaunched] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [pingCount, setPingCount] = useState<number>(0);
  const [lastPingTime, setLastPingTime] = useState<string>("-");
  const [activeProcessType, setActiveProcessType] = useState<"none" | "build" | "launch">("none");

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const activeReaderRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  // Constants
  const API_BASE = "http://localhost:8000";

  // Auto-scroll logic for terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Check backend health on mount and periodic polling
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE}/projects`, { method: "GET" });
        if (response.ok) {
          setIsApiOnline(true);
        } else {
          setIsApiOnline(false);
        }
      } catch (error) {
        setIsApiOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch projects list
  const fetchProjects = async () => {
    try {
      addLog("[SYSTEM] Fetching projects from backend...");
      const response = await fetch(`${API_BASE}/projects`, { method: "GET" });
      if (!response.ok) {
        throw new Error(`Failed to fetch projects: ${response.statusText}`);
      }
      const data = await response.json();
      
      // Support both string array and object array
      let parsedProjects: string[] = [];
      if (Array.isArray(data)) {
        parsedProjects = data.map((item: any) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && item.name) return item.name;
          return JSON.stringify(item);
        });
      }
      
      setProjects(parsedProjects);
      if (parsedProjects.length > 0 && !selectedProject) {
        setSelectedProject(parsedProjects[0]);
      }
      setIsApiOnline(true);
      addLog(`[SUCCESS] Loaded ${parsedProjects.length} projects successfully.`);
    } catch (error: any) {
      setIsApiOnline(false);
      addLog(`[ERROR] Failed to fetch projects: ${error.message}`);
    }
  };

  // Fetch projects on mount
  useEffect(() => {
    fetchProjects();
  }, []);

  // Helper to add timestamped logs
  const addLog = (message: string) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${time}] ${message}`]);
  };

  // Cancel any active stream reader
  const stopActiveReader = () => {
    if (activeReaderRef.current) {
      try {
        activeReaderRef.current.cancel();
        addLog("[SYSTEM] Active log stream read cancelled.");
      } catch (e) {}
      activeReaderRef.current = null;
    }
  };

  // Heartbeat Ping Mechanism
  const startPingInterval = () => {
    stopPingInterval();
    addLog("[HEARTBEAT] Initializing 5s safety ping interval...");
    
    pingIntervalRef.current = setInterval(async () => {
      try {
        const payload = { project_name: selectedProject, mode: mode.toLowerCase() };
        const response = await fetch(`${API_BASE}/ping`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        if (response.ok) {
          setPingCount((c) => c + 1);
          setLastPingTime(new Date().toLocaleTimeString());
        } else {
          addLog(`[WARNING] Ping failed with status: ${response.status}`);
        }
      } catch (error: any) {
        addLog(`[WARNING] Ping request failed: ${error.message}`);
      }
    }, 5000);
  };

  const stopPingInterval = () => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
      setPingCount(0);
      setLastPingTime("-");
      addLog("[HEARTBEAT] Safety ping interval stopped.");
    }
  };

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      stopPingInterval();
      stopActiveReader();
    };
  }, []);

  // Stream reader for SSE logs
  const readLogStream = async (response: Response) => {
    const reader = response.body?.getReader();
    if (!reader) {
      addLog("[ERROR] Response body stream reader not available.");
      return;
    }
    activeReaderRef.current = reader;

    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("data:")) {
            const dataContent = trimmed.slice(5).trim();
            // Parse event data if it is structured, otherwise print raw
            if (dataContent) {
              setLogs((prev) => [...prev, dataContent]);
            }
          } else if (!trimmed.startsWith("event:") && !trimmed.startsWith(":")) {
            // Support raw text logs that are not formatted as SSE
            setLogs((prev) => [...prev, trimmed]);
          }
        }
      }
      addLog("[SYSTEM] Log stream complete.");
    } catch (error: any) {
      if (error.name !== "AbortError") {
        addLog(`[ERROR] Error reading log stream: ${error.message}`);
      }
    } finally {
      activeReaderRef.current = null;
    }
  };

  // Build project handler
  const handleBuild = async () => {
    if (!selectedProject) {
      addLog("[WARNING] No project selected for build.");
      return;
    }

    setIsBuilding(true);
    setActiveProcessType("build");
    addLog(`[BUILD] Starting compilation for project: "${selectedProject}" [${mode}]...`);

    try {
      const response = await fetch(`${API_BASE}/project/build`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({
          project_name: selectedProject,
          mode: mode.toLowerCase()
        })
      });

      if (response.status === 409) {
        addLog("[ERROR] Build failed: Another process is currently running! (Process Lock active)");
        setIsBuilding(false);
        setActiveProcessType("none");
        return;
      }

      if (!response.ok) {
        throw new Error(`Build request failed with status ${response.status}`);
      }

      await readLogStream(response);
      addLog("[SUCCESS] Project compilation process finished.");
    } catch (error: any) {
      addLog(`[ERROR] Build execution failed: ${error.message}`);
    } finally {
      setIsBuilding(false);
      setActiveProcessType("none");
    }
  };

  // Launch simulation handler
  const handleLaunch = async () => {
    if (!selectedProject) {
      addLog("[WARNING] No project selected for launch.");
      return;
    }

    setActiveProcessType("launch");
    addLog(`[LAUNCH] Initializing simulation launch for project: "${selectedProject}" [${mode}]...`);

    try {
      const response = await fetch(`${API_BASE}/project/launch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({
          project_name: selectedProject,
          mode: mode.toLowerCase()
        })
      });

      if (response.status === 409) {
        addLog("[ERROR] Launch failed: Another process is currently running! (Process Lock active)");
        setActiveProcessType("none");
        return;
      }

      if (!response.ok) {
        throw new Error(`Launch request failed with status ${response.status}`);
      }

      setIsLaunched(true);
      startPingInterval();

      // Read launch logs in the background/stream
      await readLogStream(response);
    } catch (error: any) {
      addLog(`[ERROR] Launch execution failed: ${error.message}`);
      setIsLaunched(false);
      stopPingInterval();
    } finally {
      setActiveProcessType("none");
    }
  };

  // Stop simulation handler
  const handleStop = async () => {
    addLog("[STOP] Sending termination signal to active ROS 2 processes...");
    stopPingInterval();
    stopActiveReader();

    try {
      const response = await fetch(`${API_BASE}/project/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: selectedProject })
      });

      if (response.ok) {
        addLog("[SUCCESS] Active processes stopped successfully.");
      } else {
        addLog(`[WARNING] Stop request returned status: ${response.status}`);
      }
    } catch (error: any) {
      addLog(`[ERROR] Failed to send stop command: ${error.message}`);
    } finally {
      setIsLaunched(false);
      setActiveProcessType("none");
    }
  };

  // Log formatting coloring
  const formatLogLine = (line: string) => {
    let className = "log-normal";
    if (line.includes("[ERROR]") || line.includes("error:") || line.includes("FAILED")) {
      className = "log-error";
    } else if (line.includes("[SUCCESS]") || line.includes("successfully") || line.includes("Finished")) {
      className = "log-success";
    } else if (line.includes("[WARNING]") || line.includes("warning:")) {
      className = "log-warning";
    } else if (line.includes("[SYSTEM]") || line.includes("[BUILD]") || line.includes("[LAUNCH]") || line.includes("[STOP]")) {
      className = "log-system";
    } else if (line.includes("[HEARTBEAT]")) {
      className = "log-heartbeat";
    }
    return <div className={`log-line ${className}`}>{line}</div>;
  };

  return (
    <div className="panel-container">
      {/* Dynamic Glassmorphic Styles */}
      <style>{`
        .panel-container {
          display: flex;
          flex-direction: column;
          height: 100%;
          width: 100%;
          padding: 16px;
          background: radial-gradient(circle at top left, #1e1e24 0%, #121214 100%);
          color: #f5f5f7;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          box-sizing: border-box;
          overflow-y: auto;
        }

        /* Glassmorphic Card Style */
        .glass-card {
          background: rgba(30, 30, 35, 0.45);
          backdrop-filter: blur(20px) saturate(180%);
          -webkit-backdrop-filter: blur(20px) saturate(180%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 14px;
          padding: 20px;
          box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
          margin-bottom: 16px;
        }

        /* Header Style */
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding-bottom: 12px;
          margin-bottom: 16px;
        }

        .title-group {
          display: flex;
          flex-direction: column;
        }

        .title {
          font-size: 16px;
          font-weight: 700;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          background: linear-gradient(135deg, #ffffff 0%, #a1a1a6 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .subtitle {
          font-size: 11px;
          color: #86868b;
          margin-top: 2px;
        }

        /* Status Badge */
        .status-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(255, 255, 255, 0.04);
          padding: 6px 12px;
          border-radius: 20px;
          border: 1px solid rgba(255, 255, 255, 0.06);
          font-size: 11px;
          font-weight: 600;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          box-shadow: 0 0 8px currentColor;
        }

        .online { color: #34c759; }
        .offline { color: #ff3b30; }

        /* Configuration Grid */
        .config-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
          margin-bottom: 16px;
        }

        @media (max-width: 600px) {
          .config-grid {
            grid-template-columns: 1fr;
          }
        }

        .input-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .label {
          font-size: 11px;
          font-weight: 600;
          color: #a1a1a6;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        /* Modern Select & Inputs */
        .select-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .select-input {
          width: 100%;
          padding: 10px 14px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #ffffff;
          font-size: 13px;
          outline: none;
          cursor: pointer;
          transition: all 0.2s ease;
          appearance: none;
        }

        .select-input:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.08);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .select-input:focus {
          border-color: #007aff;
          box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.25);
        }

        .select-wrapper::after {
          content: "▼";
          font-size: 9px;
          color: #86868b;
          position: absolute;
          right: 14px;
          pointer-events: none;
        }

        .refresh-btn {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #ffffff;
          padding: 10px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s ease;
        }

        .refresh-btn:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
        }

        .project-selector-container {
          display: flex;
          gap: 8px;
        }

        /* Apple Segmented Control */
        .segmented-control {
          display: flex;
          background: rgba(0, 0, 0, 0.25);
          padding: 3px;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .segment-btn {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: #86868b;
          font-size: 13px;
          font-weight: 600;
          padding: 8px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .segment-btn.active {
          background: rgba(255, 255, 255, 0.12);
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        /* Action Buttons */
        .action-container {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
          margin-bottom: 16px;
        }

        .btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          border: 1px solid transparent;
          outline: none;
        }

        .btn-build {
          background: linear-gradient(135deg, #303036 0%, #202024 100%);
          border-color: rgba(255, 255, 255, 0.1);
          color: #ffffff;
        }

        .btn-build:hover:not(:disabled) {
          border-color: rgba(255, 255, 255, 0.25);
          background: linear-gradient(135deg, #3d3d45 0%, #27272c 100%);
        }

        .btn-launch {
          background: linear-gradient(135deg, #007aff 0%, #005ecb 100%);
          color: #ffffff;
          box-shadow: 0 4px 16px rgba(0, 122, 255, 0.25);
        }

        .btn-launch:hover:not(:disabled) {
          background: linear-gradient(135deg, #1a88ff 0%, #0066de 100%);
          box-shadow: 0 6px 20px rgba(0, 122, 255, 0.35);
        }

        .btn-stop {
          background: linear-gradient(135deg, #ff3b30 0%, #d32f2f 100%);
          color: #ffffff;
          box-shadow: 0 4px 16px rgba(255, 59, 48, 0.25);
        }

        .btn-stop:hover:not(:disabled) {
          background: linear-gradient(135deg, #ff5247 0%, #e53935 100%);
          box-shadow: 0 6px 20px rgba(255, 59, 48, 0.35);
        }

        .btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
          box-shadow: none !important;
        }

        /* Monospace Live Terminal */
        .terminal-card {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-height: 250px;
          background: rgba(10, 10, 12, 0.8);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 12px;
          overflow: hidden;
          box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.6);
        }

        .terminal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 16px;
          background: rgba(255, 255, 255, 0.02);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .terminal-title {
          font-size: 11px;
          font-weight: 700;
          color: #86868b;
          letter-spacing: 1px;
        }

        .terminal-controls {
          display: flex;
          gap: 8px;
        }

        .term-btn {
          background: rgba(255, 255, 255, 0.05);
          border: none;
          color: #a1a1a6;
          padding: 4px 8px;
          font-size: 11px;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .term-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #ffffff;
        }

        .terminal-body {
          flex: 1;
          padding: 16px;
          overflow-y: auto;
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
          font-size: 12px;
          line-height: 1.6;
          color: #e3e3e6;
        }

        /* Log Line Color Codes */
        .log-line {
          white-space: pre-wrap;
          word-break: break-all;
          margin-bottom: 4px;
        }
        
        .log-normal { color: #e3e3e6; }
        .log-error { color: #ff453a; font-weight: 600; }
        .log-success { color: #30d158; }
        .log-warning { color: #ffd60a; }
        .log-system { color: #0a84ff; font-weight: 600; }
        .log-heartbeat { color: #bf5af2; }

        /* Footer Telemetry Row */
        .footer-telemetry {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          font-size: 11px;
          color: #86868b;
        }

        .telemetry-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .telemetry-value {
          color: #ffffff;
          font-weight: 600;
        }

        /* Spinner for loading state */
        .spinner {
          display: inline-block;
          width: 14px;
          height: 14px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-radius: 50%;
          border-top-color: #ffffff;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      {/* Main Glassmorphic Panel Card */}
      <div className="glass-card flex-grow">
        {/* Header Block */}
        <div className="header">
          <div className="title-group">
            <span className="title">TeknoSim Control Center</span>
            <span className="subtitle">System Orchestrator & Emulation Pilot</span>
          </div>
          <div className="status-badge">
            <span className={`status-dot ${isApiOnline ? 'online' : 'offline'}`} />
            <span>SIDECAR API: {isApiOnline ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
        </div>

        {/* Configurations Grid */}
        <div className="config-grid">
          {/* Project Selector */}
          <div className="input-group">
            <label className="label">Target Emulation Project</label>
            <div className="project-selector-container">
              <div className="select-wrapper" style={{ flex: 1 }}>
                <select
                  className="select-input"
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  disabled={activeProcessType !== "none" || isLaunched}
                >
                  {projects.length === 0 ? (
                    <option value="">No projects available</option>
                  ) : (
                    projects.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <button
                className="refresh-btn"
                onClick={fetchProjects}
                disabled={activeProcessType !== "none" || isLaunched}
                title="Scan projects folder"
              >
                🔄
              </button>
            </div>
          </div>

          {/* Mode Switcher */}
          <div className="input-group">
            <label className="label">Execution Mode</label>
            <div className="segmented-control">
              <button
                className={`segment-btn ${mode === "SITL" ? "active" : ""}`}
                onClick={() => setMode("SITL")}
                disabled={activeProcessType !== "none" || isLaunched}
              >
                SITL (Software-in-the-Loop)
              </button>
              <button
                className={`segment-btn ${mode === "HITL" ? "active" : ""}`}
                onClick={() => setMode("HITL")}
                disabled={activeProcessType !== "none" || isLaunched}
              >
                HITL (Hardware-in-the-Loop)
              </button>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="action-container">
          <button
            className="btn btn-build"
            onClick={handleBuild}
            disabled={activeProcessType !== "none" || isLaunched || !isApiOnline}
          >
            {isBuilding ? (
              <>
                <span className="spinner" />
                <span>Compiling Package...</span>
              </>
            ) : (
              <>
                <span>🛠️</span>
                <span>Build Project</span>
              </>
            )}
          </button>

          {isLaunched ? (
            <button
              className="btn btn-stop"
              onClick={handleStop}
              disabled={!isApiOnline}
            >
              <span>⏹️</span>
              <span>Stop Simulation</span>
            </button>
          ) : (
            <button
              className="btn btn-launch"
              onClick={handleLaunch}
              disabled={activeProcessType !== "none" || !isApiOnline}
            >
              {activeProcessType === "launch" ? (
                <>
                  <span className="spinner" />
                  <span>Launching ROS 2...</span>
                </>
              ) : (
                <>
                  <span>🚀</span>
                  <span>Launch Simulation</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Live Monospace Terminal */}
        <div className="terminal-card">
          <div className="terminal-header">
            <span className="terminal-title">LIVE TELEMETRY LOGS & COMPILER STREAMS</span>
            <div className="terminal-controls">
              <button
                className="term-btn"
                onClick={() => {
                  navigator.clipboard.writeText(logs.join("\n"));
                  addLog("[SYSTEM] Logs copied to clipboard.");
                }}
              >
                📋 Copy
              </button>
              <button
                className="term-btn"
                onClick={() => setLogs([])}
              >
                🗑️ Clear
              </button>
            </div>
          </div>
          <div className="terminal-body">
            {logs.length === 0 ? (
              <div style={{ color: "#86868b", fontStyle: "italic" }}>
                Waiting for processes to start. Logger listening on localhost:8000...
              </div>
            ) : (
              logs.map((line, idx) => (
                <div key={idx} style={{ display: "flex", gap: "8px" }}>
                  <span style={{ color: "#3a3a3c", userSelect: "none" }}>{(idx + 1).toString().padStart(3, "0")}</span>
                  {formatLogLine(line)}
                </div>
              ))
            )}
            <div ref={terminalEndRef} />
          </div>
        </div>

        {/* Footer Telemetry */}
        <div className="footer-telemetry">
          <div className="telemetry-item">
            <span>Active Project:</span>
            <span className="telemetry-value">{selectedProject || "None"}</span>
          </div>
          <div className="telemetry-item">
            <span>Ping Count:</span>
            <span className="telemetry-value">{pingCount}</span>
          </div>
          <div className="telemetry-item">
            <span>Last Active Ping:</span>
            <span className="telemetry-value" style={{ color: pingCount > 0 ? '#34c759' : '#86868b' }}>
              {lastPingTime}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

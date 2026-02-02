import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

function App() {
  const [greetMsg, setGreetMsg] = useState("");
  const [name, setName] = useState("");

  const [pythonMsg, setPythonMsg] = useState("");
  const [pythonResponse, setPythonResponse] = useState("");

  async function greet() {
    setGreetMsg(await invoke("greet", { name }));
  }

  async function sendToPython() {
    try {
      const res = await invoke("send_message", { message: pythonMsg });
      setPythonResponse(res as string);
    } catch (e: any) {
      setPythonResponse("Error: " + e.toString());
    }
  }

  return (
    <main className="container">
      <h1>KogniTerm Desktop</h1>

      <div className="row">
        <a href="https://tauri.app" target="_blank">
          <img src="/tauri.svg" className="logo tauri" alt="Tauri logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>

      <div className="row">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            greet();
          }}
        >
          <input
            id="greet-input"
            onChange={(e) => setName(e.currentTarget.value)}
            placeholder="Enter a name..."
          />
          <button type="submit">Greet Rust</button>
        </form>
      </div>
      <p>{greetMsg}</p>

      <div className="row" style={{ marginTop: '20px', borderTop: '1px solid #333', paddingTop: '20px' }}>
        <h2>Backend Python</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendToPython();
          }}
        >
          <input
            onChange={(e) => setPythonMsg(e.currentTarget.value)}
            placeholder="Message for Python..."
          />
          <button type="submit">Send to Python</button>
        </form>
      </div>
      <p>{pythonResponse}</p>

    </main>
  );
}

export default App;

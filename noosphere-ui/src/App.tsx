import { useState, useEffect } from 'react';
import './App.css';
import { client, CREATE_MISSION_INTENT_MUTATION } from './graphqlClient';
import { connect, NatsConnection } from 'nats.ws';

const NATS_WS_URL = "ws://localhost:8222"; // NATS WebSocket port

function App() {
  const [missionName, setMissionName] = useState('');
  const [missionDescription, setMissionDescription] = useState('');
  const [chronicleEntries, setChronicleEntries] = useState<string[]>([]);

  useEffect(() => {
    let nc: NatsConnection | null = null;

    const setupNats = async () => {
      try {
        nc = await connect({ servers: NATS_WS_URL });
        console.log(`Connected to NATS at ${nc.getServer()}`);

        const sub = nc.subscribe("intents.new");
        (async () => {
          for await (const m of sub) {
            const data = JSON.parse(new TextDecoder().decode(m.data));
            setChronicleEntries((prev) => [
              ...prev,
              `[${new Date().toLocaleTimeString()}] New Mission Intent: ${data.mission_name} (ID: ${data.id})`,
            ]);
          }
        })();

        const subTasksNew = nc.subscribe("tasks.new");
        (async () => {
          for await (const m of subTasksNew) {
            const data = JSON.parse(new TextDecoder().decode(m.data));
            setChronicleEntries((prev) => [
              ...prev,
              `[${new Date().toLocaleTimeString()}] New Task: ${data.description} (ID: ${data.id}) for Intent ${data.mission_intent_id}`,
            ]);
          }
        })();

        const subTasksClaimed = nc.subscribe("tasks.claimed");
        (async () => {
          for await (const m of subTasksClaimed) {
            const data = JSON.parse(new TextDecoder().decode(m.data));
            setChronicleEntries((prev) => [
              ...prev,
              `[${new Date().toLocaleTimeString()}] Task Claimed: ${data.id} by ${data.assigned_to}`,
            ]);
          }
        })();

        const subTasksUpdated = nc.subscribe("tasks.updated");
        (async () => {
          for await (const m of subTasksUpdated) {
            const data = JSON.parse(new TextDecoder().decode(m.data));
            setChronicleEntries((prev) => [
              ...prev,
              `[${new Date().toLocaleTimeString()}] Task Updated: ${data.id} Status: ${data.status} Output: ${data.output || 'N/A'}`,
            ]);
          }
        })();

      } catch (err) {
        console.error('Error connecting to NATS:', err);
        setChronicleEntries((prev) => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ERROR: Could not connect to NATS. Is the NATS server running?`,
        ]);
      }
    };

    setupNats();

    return () => {
      if (nc) {
        console.log('Disconnecting from NATS.');
        nc.close();
      }
    };
  }, []);

  const handleGreenlight = async () => {
    console.log('Greenlight button clicked!');
    console.log('Mission Name:', missionName);
    console.log('Mission Description:', missionDescription);

    try {
      const data = await client.request(CREATE_MISSION_INTENT_MUTATION, {
        missionName,
        description: missionDescription,
      });
      console.log('Mission Intent created:', data.createMissionIntent);
      setChronicleEntries((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Successfully created Mission Intent: ${data.createMissionIntent.missionName}`,
      ]);
      setMissionName('');
      setMissionDescription('');
    } catch (error) {
      console.error('Error creating mission intent:', error);
      setChronicleEntries((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ERROR: Failed to create mission intent. Check console for details.`,
      ]);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Noösphere Nexus</h1>
        <h2>Pitch Room</h2>
      </header>
      <div className="pitch-form">
        <div className="form-group">
          <label htmlFor="missionName">Mission Name:</label>
          <input
            type="text"
            id="missionName"
            value={missionName}
            onChange={(e) => setMissionName(e.target.value)}
            placeholder="e.g., Build a new AI assistant"
          />
        </div>
        <div className="form-group">
          <label htmlFor="missionDescription">Mission Description:</label>
          <textarea
            id="missionDescription"
            value={missionDescription}
            onChange={(e) => setMissionDescription(e.target.value)}
            placeholder="Provide a detailed description of the mission intent..."
            rows={5}
          />
        </div>
        <button className="greenlight-button" onClick={handleGreenlight}>
          Greenlight Project
        </button>
      </div>

      <div className="chronicle">
        <h2>Chronicle</h2>
        <div className="chronicle-log">
          {chronicleEntries.map((entry, index) => (
            <p key={index}>{entry}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;

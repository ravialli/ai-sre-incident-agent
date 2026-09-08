from fastapi import FastAPI
import time

from app.agent.graph import incident_graph
from app.models.incident import IncidentInput

app = FastAPI(
    title="AI SRE Incident Agent",
    version="0.1.0",
)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ai-sre-incident-agent",
    }
    
@app.post("/incidents/investigate")
async def investigate_incident(incident: IncidentInput):
    window_end = int(time.time())
    window_start = window_end - (15 * 60)
    
    initial_state = {
        "alert_name": incident.alert_name,
        "cluster": incident.cluster,
        "service": incident.service,
        "severity": incident.severity,
        "window_start": window_start,
        "telemetry_errors": [],
        "window_end": window_end
    }
    
    result = await incident_graph.ainvoke(initial_state)
    
    return result

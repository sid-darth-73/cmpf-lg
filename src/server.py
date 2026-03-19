import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import TypedDict, List, Literal, Optional
from workflow import graph_runner_app
from cf_api import CodeforcesAPI
from recommendation_engine import problem_recommendations

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = CodeforcesAPI()# Request Model
class ComparisonRequest(BaseModel):
    user1_handle: str
    user2_handle: str

# Response Model
class ComparisonResponse(BaseModel):
    user1: str
    user2: str
    user1_score: float
    user2_score: float
    verdict_log: List[str]

# SERVER ENDPOINTS
@app.get("/api/user/{handle}/info")
async def get_user_info(handle: str):
    res = api.get_user_info(handle)
    if not res:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "OK", "result": [res]}

@app.get("/api/user/{handle}/rating")
async def get_user_rating(handle: str):
    res = api.get_user_rating(handle)
    if res is None:
        raise HTTPException(status_code=404, detail="User not found or no rating history")
    return {"status": "OK", "result": res}

@app.get("/api/user/{handle}/status")
async def get_user_status(handle: str, from_idx: Optional[int] = Query(None, alias="from"), count: Optional[int] = None):
    res = api.get_user_submissions(handle, from_idx=from_idx, count=count)
    if res is None:
        raise HTTPException(status_code=404, detail="User not found or no submissions")
    return {"status": "OK", "result": res}

@app.get("/api/user/{handle}/recommendations")
async def get_user_recommendations(handle: str):
    try:
        recommendations = problem_recommendations(handle)
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compare", response_model=ComparisonResponse)
async def run_comparison(payload: ComparisonRequest):
    """
    Takes two handles, runs the LangGraph workflow, and returns the analysis.
    """
    initial_input = {
        'user1_handle': payload.user1_handle,
        'user2_handle': payload.user2_handle,
        # Initialize default lists to avoid KeyErrors if append happens early
        'llm_messages': [] 
    }
    
    try:
        result = graph_runner_app.invoke(initial_input)
        
        return {
            "user1": result['user1_handle'],
            "user2": result['user2_handle'],
            "user1_score": result.get('user1_score', 0.0),
            "user2_score": result.get('user2_score', 0.0),
            "verdict_log": result.get('llm_messages', ["No analysis generated."])
        }
    
    except Exception as e:
        print(f"Error executing workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/compare/stream")
async def run_comparison_stream(payload: ComparisonRequest):
    """
    Streams analysis updates node-by-node using Server-Sent Events (SSE).
    """
    initial_input = {
        'user1_handle': payload.user1_handle,
        'user2_handle': payload.user2_handle,
        'llm_messages': [] 
    }

    async def event_generator():
        # Nodes that actually generate text we want to show
        content_nodes = {
            "delta_rating", 
            "consistency_contest", 
            "quality_ratio", 
            "total_problems", 
            "unfair_comparison",
            "final_summary"
        }

        # Iterate through the graph execution steps
        async for chunk in graph_runner_app.astream(initial_input):
            for node_name, state_update in chunk.items():
                
                # 1. STREAM INTERMEDIATE UPDATES
                if node_name in content_nodes:
                    messages = state_update.get('llm_messages', [])
                    
                    if messages:
                        # Get the latest message appended by this specific node
                        latest_message = messages[-1]
                        
                        # Construct a JSON payload for the UI
                        update_payload = {
                            "type": "update",
                            "node": node_name,
                            "message": latest_message,
                            # Stream scores real-time for UI progress bars
                            "current_scores": {
                                "user1": state_update.get('user1_score', 0.0),
                                "user2": state_update.get('user2_score', 0.0)
                            }
                        }
                        yield f"data: {json.dumps(update_payload)}\n\n"

                # 2. STREAM FINAL VERDICT
                if node_name in ["final_summary", "unfair_comparison"]:
                    # Terminating node reached, send the full summary object
                    final_payload = {
                        "type": "complete",
                        "user1": state_update.get('user1_handle'),
                        "user2": state_update.get('user2_handle'),
                        "user1_score": state_update.get('user1_score', 0.0),
                        "user2_score": state_update.get('user2_score', 0.0),
                        "verdict_log": state_update.get('llm_messages', [])
                    }
                    yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

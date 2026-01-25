from fastapi import FastAPI
from pydantic import BaseModel
from server import run_comparison_workflow

app = FastAPI()

class ComparisonRequest(BaseModel):
    user1_handle: str
    user2_handle: str

class ComparisonResponse(BaseModel):
    user1_analysis: dict
    user2_analysis: dict
    comparison_result: dict
    llm_messages: list

@app.post("/api/compare", response_model=ComparisonResponse)
async def compare_users(request: ComparisonRequest):
    result = run_comparison_workflow(
        request.user1_handle, 
        request.user2_handle
    )
    return result

@app.get("/api/health")
async def health():
    return {"status": "ok"}
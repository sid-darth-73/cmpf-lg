import os
from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from cf_api import CodeforcesAPI
from analyzer import analyze_user
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# %% ---------------- API SETUP ----------------
app = FastAPI(title="Codeforces Battle API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Model
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

# %% ---------------- WORKFLOW SETUP ----------------

# Setup LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.8)

# %% ---------------- STATE DEFINITION ----------------
class ComparisonState(TypedDict):
    user1_handle: str
    user2_handle: str
    user1_data: dict
    user2_data: dict
    user1_analysis: dict
    user2_analysis: dict
    delta_rating: int
    user1_score: float
    user2_score: float
    llm_messages: List[str]

# %% ---------------- NODES ----------------

def fetch(state: ComparisonState) -> ComparisonState:
    messages = state.get('llm_messages', [])
    api = CodeforcesAPI()
    state['user1_data'] = api.get_user_data(state['user1_handle'])
    state['user2_data'] = api.get_user_data(state['user2_handle'])
    state['user1_analysis'] = analyze_user(state['user1_data'])
    state['user2_analysis'] = analyze_user(state['user2_data'])
    state['user1_score'] = 0.0
    state['user2_score'] = 0.0
    state['llm_messages'] = messages
    return state

def delta_rating_node(state: ComparisonState) -> ComparisonState:
    u1_rating = state['user1_analysis']['rating']
    u2_rating = state['user2_analysis']['rating']
    delta = abs(u1_rating - u2_rating)
    state['delta_rating'] = delta
    
    u1 = state['user1_handle']
    u2 = state['user2_handle']

    # Scoring Logic
    score_log = "Equal footing."
    skip_instruction = ""

    if 100 < delta <= 200:
        if u1_rating > u2_rating: state['user1_score'] += 1
        else: state['user2_score'] += 1
        score_log = "Small Rating Gap (1 pt)."
        
    elif 200 < delta <= 400:
        if u1_rating > u2_rating: state['user1_score'] += 2
        else: state['user2_score'] += 2
        score_log = "Significant Rating Gap (2 pts)."
        
    elif 400 < delta <= 600:
        if u1_rating > u2_rating: state['user1_score'] += 3
        else: state['user2_score'] += 3
        score_log = "Dominating Rating Gap (3 pts)."
        # Explicit instruction to LLM to acknowledge the skip
        skip_instruction = "IMPORTANT: The gap is > 400. You MUST explicitly state: 'The rating gap is so massive we are SKIPPING the consistency and accuracy checks to save time. Jumping straight to problem counts.'"

    # ELABORATE PROMPT
    if delta <= 600:
        leader = u1 if u1_rating > u2_rating else u2
        lagger = u2 if u1_rating > u2_rating else u1
        
        prompt = f"""
        Act as a hype-man for a competitive coding battle.
        Topic: Current ELO Rating.
        User A ({u1}): {u1_rating} ELO.
        User B ({u2}): {u2_rating} ELO.
        Difference: {delta}.
        Status: {score_log}
        {skip_instruction}
        
        Task:
        1. Write a 2-sentence roast comparing their "power levels".
        2. If the gap is small (<100), call it a fierce rivalry. 
        3. If the gap is > 400, follow the IMPORTANT instruction above.
        4. Give one specific tip to {lagger} about how to gain +{delta} rating (e.g., mention specific problem ratings to target).
        """
        response = llm.invoke(prompt).content
        state['llm_messages'].append(f"**Rating Face-off:** {response}")

    return state

def consistency_contest_node(state: ComparisonState) -> ComparisonState:
    u1_trend = state['user1_analysis']['consistency_trend'][0]
    u2_trend = state['user2_analysis']['consistency_trend'][0]
    u1 = state['user1_handle']
    u2 = state['user2_handle']
    
    # Scoring Logic
    update_log = "Trends are similar."
    if (u1_trend == 'upward' and u2_trend == 'downward'):
        state['user1_score'] += 3
        update_log = f"{u1} +3 (Rising vs Falling)."
    elif (u2_trend == 'upward' and u1_trend == 'downward'):
        state['user2_score'] += 3
        update_log = f"{u2} +3 (Rising vs Falling)."
    elif (u1_trend == 'upward' and u2_trend == 'stable'):
        state['user1_score'] += 2
        update_log = f"{u1} +2 (Momentum Advantage)."
    elif (u2_trend == 'upward' and u1_trend == 'stable'):
        state['user2_score'] += 2
        update_log = f"{u2} +2 (Momentum Advantage)."
    elif (u1_trend == 'stable' and u2_trend == 'downward'):
        state['user1_score'] += 2
        update_log = f"{u1} +2 (Discipline Advantage)."
    elif (u2_trend == 'stable' and u1_trend == 'downward'):
        state['user2_score'] += 2
        update_log = f"{u2} +2 (Discipline Advantage)."

    # ELABORATE PROMPT
    prompt = f"""
    Act as a strict discipline coach.
    Topic: Consistency and Contest Frequency.
    {u1} Status: {u1_trend.upper()}.
    {u2} Status: {u2_trend.upper()}.
    
    Task:
    1. If a user is 'downward', roast them for "rusting" or "retiring".
    2. If a user is 'upward', praise their grindset.
    3. If 'stable', call it a plateau.
    4. Provide specific advice to the loser: Mention "virtual contests" or "upsolving" to fix their specific trend issue.
    """
    response = llm.invoke(prompt).content
    state['llm_messages'].append(f"**Momentum Check:** {response}")
    
    return state

def quality_ratio_node(state: ComparisonState) -> ComparisonState:
    q1 = state['user1_analysis']['quality_ratio']
    q2 = state['user2_analysis']['quality_ratio']
    
    # Scoring Logic
    state['user1_score'] += (q1 * 3)
    state['user2_score'] += (q2 * 3)
    
    u1 = state['user1_handle']
    u2 = state['user2_handle']

    # ELABORATE PROMPT
    prompt = f"""
    Act as a Codeforces analyst obsessed with "Wrong Answer" verdicts.
    Topic: Quality Ratio (Accuracy/Efficiency).
    {u1}: {q1:.2f} score.
    {u2}: {q2:.2f} score.
    (Note: Higher is better. A low score implies spamming submissions or brute forcing).
    
    Task:
    1. Compare their precision. Who is the "Sniper" and who is the "Machine Gunner"?
    2. Playfully mock the user with the lower ratio for "polluting the judge queue."
    3. Suggestion: Tell the lower accuracy user to read the problem statement twice or use "assert()" before submitting.
    """
    response = llm.invoke(prompt).content
    state['llm_messages'].append(f"**Accuracy Analysis:** {response}")
    
    return state

def total_problems_node(state: ComparisonState) -> ComparisonState:
    tp1 = state['user1_analysis']['total_problems_solved']
    tp2 = state['user2_analysis']['total_problems_solved']
    
    high_val = max(tp1, tp2)
    low_val = min(tp1, tp2)
    if low_val == 0: low_val = 1 
    
    ratio = high_val / low_val
    higher_is_1 = (tp1 >= tp2)
    
    # Scoring Logic
    points = 0
    if 1.2 < ratio <= 1.5: points = 1
    elif 1.5 < ratio <= 2.0: points = 2
    elif ratio > 2.0: points = 3
    
    if points > 0:
        if higher_is_1: state['user1_score'] += points
        else: state['user2_score'] += points
    
    u1 = state['user1_handle']
    u2 = state['user2_handle']

    # ELABORATE PROMPT
    prompt = f"""
    Act as a veteran programmer who values hard work above talent.
    Topic: Total Problems Solved (The Grind).
    {u1}: {tp1} problems solved.
    {u2}: {tp2} problems solved.
    The ratio is {ratio:.2f}.
    
    Task:
    1. If the ratio > 2.0, state that the leader "lives in the basement" and the trailer needs to "touch less grass".
    2. If the scores are close, call it a "battle of diligence."
    3. Suggestion for the user with fewer problems: Mention specific problem tags (e.g., DP, Graphs) they are likely missing out on due to lack of practice.
    """
    response = llm.invoke(prompt).content
    state['llm_messages'].append(f"**The Grind:** {response}")
    
    return state

def unfair_comparison_node(state: ComparisonState) -> ComparisonState:
    delta = state['delta_rating']
    u1 = state['user1_handle']
    u2 = state['user2_handle']
    
    prompt = f"""
    Write a referee announcement cancelling a boxing match.
    The rating difference between {u1} and {u2} is {delta} points.
    State clearly that this is bullying, not a competition.
    Tell the lower rated user to come back when they are stronger.
    """
    response = llm.invoke(prompt).content
    state['llm_messages'].append(f"**MATCH CANCELLED:** {response}")
    return state

def final_summary_node(state: ComparisonState) -> ComparisonState:
    u1 = state['user1_handle']
    u2 = state['user2_handle']
    s1 = state['user1_score']
    s2 = state['user2_score']
    logs = "\n".join(state['llm_messages'])
    
    winner = "Tie"
    if s1 > s2: winner = u1
    elif s2 > s1: winner = u2
    
    prompt = f"""
    You are the 'Codeforces RoastMaster 3000'. 
    
    Input Data:
    User 1: {u1} (Final Score: {s1:.2f})
    User 2: {u2} (Final Score: {s2:.2f})
    Winner: {winner}
    
    Evaluation Logs:
    {logs}
    
    Task:
    Write a 100-word final summary that includes:
    1. **The Verdict:** Declare the winner with flair.
    2. **The Highlights:** Briefly mention why they won (was it consistency? raw rating? accuracy?).
    3. **The Roast:** A specific, playful insult to the loser based on the metric where they performed worst in the logs.
    4. **The Path Forward:** A genuine, high-level improvement plan for the loser (e.g., "Fix your accuracy and upsolve more Div3 E's").
    """
    
    res = llm.invoke(prompt).content
    state['llm_messages'].append(f"\n--- FINAL VERDICT ---\n{res}")
    return state

# %% ---------------- ROUTING LOGIC ----------------

def route_delta(state: ComparisonState) -> Literal['unfair', 'skip_middle', 'normal']:
    delta = state['delta_rating']
    if delta > 600: return 'unfair'
    elif delta > 400: return 'skip_middle'
    else: return 'normal'

# %% ---------------- GRAPH CONSTRUCTION ----------------

workflow = StateGraph(ComparisonState)

# Nodes
workflow.add_node("fetch", fetch)
workflow.add_node("delta_rating", delta_rating_node)
workflow.add_node("consistency_contest", consistency_contest_node)
workflow.add_node("quality_ratio", quality_ratio_node)
workflow.add_node("total_problems", total_problems_node)
workflow.add_node("unfair_comparison", unfair_comparison_node)
workflow.add_node("final_summary", final_summary_node)

# Edges
workflow.set_entry_point("fetch")
workflow.add_edge("fetch", "delta_rating")

# Branching
workflow.add_conditional_edges("delta_rating", route_delta, {
    "unfair": "unfair_comparison", # skip comparison for delta > 400
    "skip_middle": "total_problems", # Skips Consistency and Quality 
    "normal": "consistency_contest"
})

workflow.add_edge("consistency_contest", "quality_ratio")
workflow.add_edge("quality_ratio", "total_problems")
workflow.add_edge("total_problems", "final_summary")
workflow.add_edge("final_summary", END)
workflow.add_edge("unfair_comparison", END)

# Compile
graph_runner_app = workflow.compile()
#print(graph_runner_app.get_graph().draw_ascii())
# %% ---------------- EXECUTION ----------------

# if __name__ == "__main__":
#     initial_input = {
#         'user1_handle': 'unbit',
#         'user2_handle': 'tourist'
#     }
    
#     print("Running Comparison Workflow...")
#     result = app.invoke(initial_input)
    
#     print("\n\n" + "="*30)
#     for msg in result['llm_messages']:
#         print(msg)
#         print("-" * 20)


# SERVER ENDPOINTS
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

@app.get("/health")
def health_check():
    return {"status": "ok", "model": "gemini-2.5-flash"}

if __name__ == "__main__":
    # Run using: python server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
"""
Analysis functions for comparing Codeforces users.
"""
from typing import Dict, List, Tuple
from collections import defaultdict


def calculate_rating(user_data: Dict) -> int:
    """Extract current rating from user data."""
    if user_data.get("info") and "rating" in user_data["info"]:
        return user_data["info"]["rating"]
    return 0


def calculate_total_problems_solved(user_data: Dict) -> int:
    """Calculate total number of unique problems solved."""
    if not user_data.get("submissions"):
        return 0
    
    solved_problems = set()
    for submission in user_data["submissions"]:
        if submission.get("verdict") == "OK":
            problem = submission.get("problem", {})
            problem_id = f"{problem.get('contestId', '')}{problem.get('index', '')}"
            if problem_id:
                solved_problems.add(problem_id)
    
    return len(solved_problems)


def calculate_consistency_trend(user_data: Dict) -> Tuple[str, float]:
    """
    Calculate consistency/trend from last 10 contests.
    Returns: (trend_direction, trend_score)
    - trend_direction: "upward", "downward", or "stable"
    - trend_score: positive for upward, negative for downward
    """
    rating_history = user_data.get("rating_history", [])
    if not rating_history or len(rating_history) < 2:
        return ("stable", 0.0)
    
    # Get last 10 contests (or all if less than 10)
    recent_contests = rating_history[-10:]
    
    if len(recent_contests) < 2:
        return ("stable", 0.0)
    
    # Calculate rating changes
    rating_changes = []
    for i in range(1, len(recent_contests)):
        old_rating = recent_contests[i-1].get("newRating", 0)
        new_rating = recent_contests[i].get("newRating", 0)
        rating_changes.append(new_rating - old_rating)
    
    # Calculate average change
    avg_change = sum(rating_changes) / len(rating_changes) if rating_changes else 0
    
    # Determine trend
    if avg_change > 10:
        return ("upward", avg_change)
    elif avg_change < -10:
        return ("downward", avg_change)
    else:
        return ("stable", avg_change)


def calculate_quality_ratio(user_data: Dict) -> float:
    """
    Calculate ratio: (problems solved with rating >= 200 + user_rating) / total problems solved
    Higher ratio is better.
    """
    if not user_data.get("submissions"):
        return 0.0
    
    current_rating = calculate_rating(user_data)
    threshold = 200 + current_rating
    
    solved_problems = {}
    for submission in user_data["submissions"]:
        if submission.get("verdict") == "OK":
            problem = submission.get("problem", {})
            problem_id = f"{problem.get('contestId', '')}{problem.get('index', '')}"
            problem_rating = problem.get("rating", 0)
            
            if problem_id:
                # Keep the highest rating if problem appears multiple times
                if problem_id not in solved_problems:
                    solved_problems[problem_id] = problem_rating
                else:
                    solved_problems[problem_id] = max(solved_problems[problem_id], problem_rating)
    
    total_solved = len(solved_problems)
    if total_solved == 0:
        return 0.0
    
    high_rating_problems = sum(1 for rating in solved_problems.values() if rating >= threshold)
    
    return high_rating_problems / total_solved if total_solved > 0 else 0.0


def analyze_user(user_data: Dict) -> Dict:
    """Perform complete analysis of a user."""
    return {
        "handle": user_data["handle"],
        "rating": calculate_rating(user_data),
        "total_problems_solved": calculate_total_problems_solved(user_data),
        "consistency_trend": calculate_consistency_trend(user_data),
        "quality_ratio": calculate_quality_ratio(user_data)
    }

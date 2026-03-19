"""
Codeforces API client for fetching user data.
"""
import requests
from typing import Optional, Dict, List
from collections import defaultdict

class CodeforcesAPI:
    """Client for interacting with Codeforces API."""
    
    BASE_URL = "https://codeforces.com/api"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_user_info(self, handle: str) -> Optional[Dict]:
        """Get user information including rating."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/user.info",
                params={"handles": handle}
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] == "OK" and data["result"]:
                return data["result"][0]
            return None
        except Exception as e:
            print(f"Error fetching user info for {handle}: {e}")
            return None
    
    def get_user_rating(self, handle: str) -> Optional[List[Dict]]:
        """Get user rating history."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/user.rating",
                params={"handle": handle}
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] == "OK":
                return data["result"]
            return None
        except Exception as e:
            print(f"Error fetching rating history for {handle}: {e}")
            return None
    
    def get_user_submissions(self, handle: str, from_idx: Optional[int] = None, count: Optional[int] = None) -> Optional[List[Dict]]:
        """Get user submissions."""
        from typing import Any
        params: Dict[str, Any] = {"handle": handle}
        if from_idx is not None:
            params["from"] = from_idx
        if count is not None:
            params["count"] = count

        try:
            response = self.session.get(
                f"{self.BASE_URL}/user.status",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] == "OK":
                return data["result"]
            return None
        except Exception as e:
            print(f"Error fetching submissions for {handle}: {e}")
            return None

    def get_all_problems(self) -> Optional[List[Dict]]:
        """Get all problems to map contest structures efficiently."""
        try:
            response = self.session.get(f"{self.BASE_URL}/problemset.problems")
            response.raise_for_status()
            data = response.json()
            if data["status"] == "OK":
                return data["result"]["problems"]
            return None
        except Exception as e:
            print(f"Error fetching problemset: {e}")
            return None
    
    def get_user_data(self, handle: str) -> Dict:
        """Get all relevant user data and calculate upsolve list."""
        user_info = self.get_user_info(handle)
        rating_history = self.get_user_rating(handle)
        submissions = self.get_user_submissions(handle)
        all_problems = self.get_all_problems()
        
        upsolve_list = []
        

        if rating_history and submissions and all_problems:
            
            # 1. Get all the contestId for all the participated contests
            participated_contests = {contest["contestId"] for contest in rating_history}
            
            # 2. Group all problems by contestId and sort them alphabetically by index (A, B, C...)
            contest_problems = defaultdict(list)
            for prob in all_problems:
                if "contestId" in prob:
                    contest_problems[prob["contestId"]].append(prob)
            
            for cid in contest_problems:
                # Sort to ensure order is A, B, C, D, etc.
                contest_problems[cid].sort(key=lambda x: x["index"])
                
            # 3. Track which problems the user has successfully solved per contest
            solved_per_contest = defaultdict(set)
            for sub in submissions:
                if sub.get("verdict") == "OK" and "problem" in sub:
                    problem = sub["problem"]
                    if "contestId" in problem and "index" in problem:
                        solved_per_contest[problem["contestId"]].add(problem["index"])
            
            # 4. Determine the next logical problem to upsolve for each participated contest
            for cid in participated_contests:
                if cid not in contest_problems:
                    continue # Skip if contest isn't in standard problemset (e.g., specific Gyms)
                
                c_problems = contest_problems[cid]
                solved_indexes = solved_per_contest.get(cid, set())
                
                # Find the first problem in the sequence that hasn't been solved
                for p in c_problems:
                    if p["index"] not in solved_indexes:
                        upsolve_list.append(p)
                        break # Move on to the next contest once we find one problem
        
        return {
            "handle": handle,
            "info": user_info,
            "rating_history": rating_history or [],
            "submissions": submissions or [],
            "upsolve_list": upsolve_list
        }

if __name__ == "__main__":
    api = CodeforcesAPI()
    user_data = api.get_user_data("unbit")
    
    # Quick printout to verify the upsolve list works
    print(f"\nUpsolve list for {user_data['handle']}:")
    for prob in user_data.get('upsolve_list', [])[:]: # Printing first 5 to keep terminal clean
        print(f"Contest {prob['contestId']} - Problem {prob['index']}: {prob['name']}")
"""
Codeforces API client for fetching user data.
"""
import requests
from typing import Dict, List, Optional, Tuple


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
    
    def get_user_submissions(self, handle: str) -> Optional[List[Dict]]:
        """Get user submissions."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/user.status",
                params={"handle": handle}
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] == "OK":
                return data["result"]
            return None
        except Exception as e:
            print(f"Error fetching submissions for {handle}: {e}")
            return None
    
    def get_user_data(self, handle: str) -> Dict:
        """Get all relevant user data for comparison."""
        user_info = self.get_user_info(handle)
        rating_history = self.get_user_rating(handle)
        submissions = self.get_user_submissions(handle)
        
        return {
            "handle": handle,
            "info": user_info,
            "rating_history": rating_history or [],
            "submissions": submissions or []
        }

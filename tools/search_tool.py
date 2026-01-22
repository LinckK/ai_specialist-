import os
from serpapi import GoogleSearch

def google_search(query: str) -> str:
    """
    Performs a Google search using the SerpApi service and returns formatted results.
    """
    print(f"\n--- Performing Google Search for: '{query}' ---")
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY environment variable not set."
    
    try:
        params = {
            "q": query,
            "engine": "google",
            "api_key": api_key  # Explicitly pass the API key
        }
        client = GoogleSearch(params)
        results = client.get_dict()
        
        # Format the results into a clean string
        output = ""
        if "organic_results" in results:
            for result in results.get("organic_results", [])[:5]: # Get top 5 results
                output += f"Title: {result.get('title', 'N/A')}\n"
                output += f"Link: {result.get('link', 'N/A')}\n"
                output += f"Snippet: {result.get('snippet', 'N/A')}\n---"
        
        return output if output else "No organic results found."
    except Exception as e:
        return f"Error during Google search: {e}"
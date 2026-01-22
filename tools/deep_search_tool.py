import os
from serpapi import GoogleSearch
from typing import Dict, Any

def deep_search(query: str, num_results: int = 10) -> str:
    """
    [OSINT & TECHNICAL RESEARCH]
    Realiza buscas avançadas no Google usando operadores 'Dorks'.

    SINTAXE OBRIGATÓRIA (Use estes operadores na 'query'):
    - site:dominio.com -> Busca dentro de um site (ex: site:github.com, site:reddit.com)
    - filetype:ext -> Busca arquivos específicos (ex: filetype:pdf, filetype:docx)
    - "frase exata" -> Força correspondência exata
    - OR / AND -> Operadores lógicos

    AVISO: NÃO envie queries genéricas. Use esta ferramenta apenas para investigações profundas.
    """
    print(f"\n--- Deep Search (SerpApi): '{query}' ---")
    
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY not set."

    try:
        params = {
            "q": query,
            "engine": "google",
            "api_key": api_key,
            "num": num_results
        }
        client = GoogleSearch(params)
        results = client.get_dict()
        
        output = []
        if "organic_results" in results:
            for result in results.get("organic_results", []):
                title = result.get("title", "No Title")
                link = result.get("link", "#")
                snippet = result.get("snippet", "No snippet available.")
                output.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}")
            
        if not output:
            return "No results found for your query. Try adjusting the Dorks."
            
        return "\n---\n".join(output)
        
    except Exception as e:
        print(f"[Deep Search] Error: {e}")
        return f"Error during Deep Search: {str(e)}"

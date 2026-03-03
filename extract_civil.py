import requests
from bs4 import BeautifulSoup
import re

def fetch_and_process_civil_code():
    """
    Faz o scraping do Código Civil Brasileiro no Planalto, remove artigos 
    revogados (tags <strike>) e formata como Markdown (.md) para que 
    possa ser ingerido diretamente no Corpus RAG do Vertex AI.
    """
    url = "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm"
    print(f"[*] Baixando Lei 10.406/2002 de: {url}")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    response.encoding = 'windows-1252' # Padrão legado do Planalto

    if response.status_code != 200:
        raise Exception(f"Falha ao acessar o Planalto. Status: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove tags desnecessárias (scripts, styles) e o mais importante: <strike> (revogados)
    print(f"[*] Limpando texto e removendo artigos revogados...")
    for tag in soup(['strike', 'script', 'style']):
        tag.decompose()

    raw_text = soup.get_text(separator='\n')

    # Limpeza de espaços em branco e quebras de linha múltiplas
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    clean_text = '\n'.join(lines)

    # Regex para separar em blocos baseados no início do artigo
    article_pattern = re.compile(r'\n(?=Art\.\s*\d+)')
    raw_chunks = article_pattern.split(clean_text)

    # Salvar diretamente em .md pois o upload_tool suporta formato Markdown,
    # O Vertex AI se beneficia das tags ## (Headings) para chunking semântico nativo.
    output_file = "codigo_civil_limpo.md"
    
    artigos_count = 0
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Código Civil Brasileiro (Lei 10.406/2002)\n\n")
        f.write("*Extraído da fonte oficial do planalto e limpo de itens revogados para precisão RAG.*\n\n---\n\n")

        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk.startswith('Art.'):
                continue
                
            artigos_count += 1
            
            # Converte 'Art. 1o' ou 'Art. 1.' para header nível 2 do Markdown
            # Isso ajuda massivamente o Vertex AI no processo de chunking
            chunk_md = re.sub(r'^(Art\.\s*[\d\.]+)[oº]?', r'## \1', chunk)
            
            f.write(chunk_md + '\n\n')

    print(f"[+] Processamento concluído. {artigos_count} artigos identificados.")
    print(f"[+] Arquivo gerado para upload no RAG: {output_file}")
    print(f"    -> Use o CLI do agente (Opção 4) para fazer o upload de {output_file} no Corpus.")

if __name__ == "__main__":
    fetch_and_process_civil_code()

import requests
from bs4 import BeautifulSoup
import re
import json

def fetch_and_process_civil_code_hierarchical():
    """
    Scraping SOTA do Código Civil:
    Rastreia Livro, Título, Capítulo e Seção para embutir no metadado do Artigo 
    (Pilar 1: Hierarchical Chunking / Parent-Child Context).
    Gera um output estruturado (JSONL de Parent Documents) pronto para a 
    arquitetura definitiva (sota_legal_rag.py).
    """
    url = "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm"
    print(f"[*] SOTA Scraper: Baixando Lei 10.406/2002 de: {url}")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    response.encoding = 'windows-1252'

    if response.status_code != 200:
        raise Exception(f"Falha ao acessar o Planalto. Status: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Limpeza vital contra alucinações de modelos (retirar leis revogadas)
    print(f"[*] Limpando texto e descartando itens revogados (tags <strike>)...")
    for tag in soup(['strike', 'script', 'style']):
        tag.decompose()

    # Pega o texto puro mantendo a ordem sequencial das linhas
    raw_text = soup.get_text(separator='\n')
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

    structured_data = []

    # O Estado (Árvore Hierárquica em Tempo Real)
    current_parte = ""
    current_livro = ""
    current_titulo = ""
    current_capitulo = ""
    current_secao = ""

    # Padrões comuns no texto do planalto (Atenção às variações do HTML legado)
    parte_pattern = re.compile(r'^PARTE\s+(GERAL|ESPECIAL)', re.IGNORECASE)
    livro_pattern = re.compile(r'^LIVRO\s+[IVXLCDM]+', re.IGNORECASE)
    titulo_pattern = re.compile(r'^TÍTULO\s+[IVXLCDM]+', re.IGNORECASE)
    capitulo_pattern = re.compile(r'^CAPÍTULO\s+[IVXLCDM]+', re.IGNORECASE)
    secao_pattern = re.compile(r'^Seção\s+[IVXLCDM]+', re.IGNORECASE)
    artigo_start_pattern = re.compile(r'^Art\.\s*([\d\.]+)[oº]?', re.IGNORECASE)

    current_article_num = None
    current_article_text = []

    def save_current_article():
        if current_article_num and current_article_text:
            content = '\n'.join(current_article_text)
            
            # Metadata Enrichment de 'Ferrari' (Pilar 1)
            doc = {
                "metadata": {
                    "source": "Lei 10.406/2002 - Código Civil",
                    "article_number": current_article_num,
                    "parte": current_parte,
                    "livro": current_livro,
                    "titulo": current_titulo,
                    "capitulo": current_capitulo,
                    "secao": current_secao
                },
                "page_content": content
            }
            structured_data.append(doc)

    print("[*] Iniciando Parseamento Hierárquico dos Artigos...")
    
    for line in lines:
        # Tenta identificar mudanças na "Árvore Genealógica"
        if parte_pattern.match(line):
            current_parte = line
            continue
        if livro_pattern.match(line):
            current_livro = line
            # Reset steps below
            current_titulo = ""
            current_capitulo = ""
            current_secao = ""
            continue
        if titulo_pattern.match(line):
            current_titulo = line
            current_capitulo = ""
            current_secao = ""
            continue
        if capitulo_pattern.match(line):
            current_capitulo = line
            current_secao = ""
            continue
        if secao_pattern.match(line):
            current_secao = line
            continue

        # Identificou um Artigo novo?
        art_match = artigo_start_pattern.match(line)
        if art_match:
            # Salva o anterior se existir
            save_current_article()
            
            # Inicia o Novo
            current_article_num = art_match.group(1).replace('.', '') # ex: "1022." ou "1.022" -> "1022"
            current_article_text = [line]
            continue
            
        # Se estamos dentro de um artigo, acumula o texto (parágrafos e incisos atrelados)
        if current_article_num:
            # Pula textos genéricos que o planalto enfia no meio do HTML e não são incisos/paragrafos
            if line.startswith("Vide") or line.startswith("(Revogado"):
                continue
            current_article_text.append(line)

    # Drenagem final
    save_current_article()

    output_file = "codigo_civil_hierarquico.jsonl"
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in structured_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"[+] Chunking Hierárquico Concluído: {len(structured_data)} Parent Documents indexados.")
    print(f"[+] Arquivo gerado para a Pipeline SOTA: {output_file}")
    
    # Validação pequena no log
    if structured_data:
        print("\nExemplo de Metadado da Ferrari (Pilar 1):")
        ex = structured_data[240] # Pegando um artigo no meio
        print(json.dumps(ex['metadata'], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    fetch_and_process_civil_code_hierarchical()

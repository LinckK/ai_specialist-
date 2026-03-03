import json
import os
from typing import List, Dict, Any, Optional

# Dependências do LangChain
from langchain.schema import Document
from langchain_community.vectorstores import Chroma

# Recomendação da etapa 3: Utilizando OpenAI Embeddings.
# Opcional: Se optar pela Cohere, trocar para langchain_cohere.CohereEmbeddings
from langchain_openai import OpenAIEmbeddings

class LegalDataIngestor:
    """
    Etapa 2: PIPELINE DE VETORIZAÇÃO
    Lê o arquivo .jsonl estruturado pelo script de extração e converte para documentos do LangChain.
    """
    @staticmethod
    def load_jsonl_chunks(filepath: str) -> List[Document]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Arquivo {filepath} não encontrado.")
            
        docs = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                data = json.loads(line)
                page_content = data.get("page_content", "")
                metadata = data.get("metadata", {})
                
                # Instancia o documento nativo do LangChain
                docs.append(Document(page_content=page_content, metadata=metadata))
                
        print(f"[+] {len(docs)} documentos carregados do arquivo {filepath}.")
        return docs


class LegalVectorStoreManager:
    """
    Etapa 3 e 4: ESTRATÉGIA DE EMBEDDING & VECTOR STORE
    Configura o Vector Store (neste exemplo, ChromaDB para uso local) com o modelo de embedding adequado.
    """
    def __init__(self, persist_directory: str = "./legal_vector_db", embedding_model_name: str = "text-embedding-3-large"):
        self.persist_directory = persist_directory
        
        # Etapa 3: Instanciar Embeddings com modelo de alto rank semântico (multilateral/legal)
        self.embeddings = OpenAIEmbeddings(model=embedding_model_name)
        self.vector_store = None

    def create_or_update_database(self, documents: List[Document]) -> Chroma:
        """
        Etapa 4: Insere os documentos no Vector DB e indexa os metadados
        (`article_number`, `source`) para futura filtragem no retriever (Metadata Filtering).
        """
        print(f"[*] Gerando embeddings e inserindo no Vector Store: {self.persist_directory} ...")
        
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        print("[+] Documentos vetorizados e base consolidada com sucesso.")
        return self.vector_store

    def load_existing_database(self) -> Chroma:
        """
        Carrega a banco vetorial já persistido, ideal para instanciar apenas o Context Injector.
        """
        if not os.path.exists(self.persist_directory):
            raise Exception("Vector Store não encontrado. É necessário indexar os dados primeiro.")
            
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        return self.vector_store


class LegalContextInjector:
    """
    Etapa 5: CONTEXT INJECTOR (RETRIEVER)
    Recebe queries do 'Query Planner', processa a busca no banco vetorial e forja 
    uma string estrita e enriquecida como conexto (RAG final).
    """
    def __init__(self, vector_store: Chroma):
        self.vector_store = vector_store

    def retrieve_and_format(self, query: str, top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera o resgate semântico (Semantic Search) + filtragem (se demandada pelo Query Planner) 
        formatando no padrão blindado contra alucinação.
        """
        search_kwargs = {}
        if filter_metadata:
            # Metadata filtering (Ex: {'article_number': '422'})
            search_kwargs["filter"] = filter_metadata
            
        # Resgata 'top_k' fragmentos com maior similaridade
        retrieved_docs = self.vector_store.similarity_search(query, k=top_k, **search_kwargs)
        
        formatted_blocks = []
        for doc in retrieved_docs:
            source = doc.metadata.get("source", "Fonte Desconhecida")
            article_number = doc.metadata.get("article_number", "Artigo Desconhecido")
            text = doc.page_content.strip()
            
            # Formatação obrigatória da saída do contexto legal
            block_formatted = f"Fonte: {source} - Artigo: {article_number}\nTexto: {text}"
            formatted_blocks.append(block_formatted)
            
        # O contexto retornado agrupa todos matches com quebra dupla para demarcar limites pro LLM
        return "\n\n".join(formatted_blocks)

# =========================================================================================
# INTEGRAÇÃO & TESTE (Pronto para sua base de código)
# =========================================================================================
def main():
    jsonl_path = "codigo_civil_chunks.jsonl"
    db_path = "./legal_vector_db"
    
    # Valida presença do arquivo para caso alguém chame o teste localmente acidentalmente
    if not os.path.exists(jsonl_path):
        print(f"ATENÇÃO: O arquivo '{jsonl_path}' não foi encontrado. "
              "Certifique-se de executar o scraper (ETAPA 1) primeiro.")
        return

    # Etapa 2: Ler JSONL
    ingestor = LegalDataIngestor()
    docs = ingestor.load_jsonl_chunks(jsonl_path)
    
    # Etapa 3 & 4: Inicializar Embedding & Vector Store (Opcionalmente, pode ser Pinecone/Qdrant)
    # Por praticidade local e testes automáticos, adotamos Chroma.
    db_manager = LegalVectorStoreManager(persist_directory=db_path, embedding_model_name="text-embedding-3-large")
    vector_store = db_manager.create_or_update_database(docs)
    
    # Etapa 5: Preparação do Injetor / Retriever
    injector = LegalContextInjector(vector_store)
    
    # Simulação originada do seu "Query Planner":
    test_query = "Qual o prazo de prescrição para reparação civil?"
    
    print(f"\n[*] Query Planner solicitou: '{test_query}'")
    final_context = injector.retrieve_and_format(query=test_query, top_k=3)
    
    print(f"[*] Contexto Injetado a ser passado ao LLM (com metadados visíveis):\n")
    print(final_context)

if __name__ == "__main__":
    # main() # Descomente para testar isoladamente o fluxo
    pass

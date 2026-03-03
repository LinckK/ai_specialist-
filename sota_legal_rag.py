import os
from typing import List, Dict, Any

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# Necessário para Reranking
# pip install cohere
from langchain_cohere import CohereRerank
from langchain.retrievers import ContextualCompressionRetriever

# Import do Custom Document Retriever (Parent-Child)
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import InMemoryByteStore
import uuid

class StateOfTheArtLegalRAG:
    """
    Arquitetura de 'Ferrari' RAG:
    - Hierarchical Parse (Metadados: Livro/Título/Capítulo/Artigo)
    - Hybrid Search (BM25 + FAISS Vector)
    - Cross-Encoder Re-Ranking (Cohere)
    - Parent-Child Retrieval (Window Retrieval)
    """
    def __init__(self, use_reranker: bool = True):
        # Configurar chaves no .env (OPENAI_API_KEY, COHERE_API_KEY)
        self.use_reranker = use_reranker
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        
        # Armazena os "Parent Documents" (Os artigos inteiros preservando Semântica)
        self.docstore = InMemoryByteStore() 
        self.vectorstore = None
        self.parent_child_retriever = None
        
        # Guardaremos os documentos brutos para o BM25
        self.raw_child_docs = []

    def build_parent_child_index(self, parent_documents: List[Document]):
        """
        Pilar 4: Parent-Child Retrieval (Window Retrieval)
        Indexa pedaços minúsculos (Incisos/Parágrafos), mas atrela eles
        ao Documento Pai (O Artigo Inteiro com seu Cabeçalho / Hierarquia).
        """
        print("[*] Construindo índice Vetorial Small-to-Big...")
        
        # Cria DB Vectorial local
        import faiss
        from langchain_community.docstore.in_memory import InMemoryDocstore
        embedding_size = 3072 # Tamanho do text-embedding-3-large
        index = faiss.IndexFlatL2(embedding_size)
        
        self.vectorstore = FAISS(
            self.embeddings.embed_query,
            index,
            InMemoryDocstore({}),
            {}
        )

        id_key = "doc_id"
        self.parent_child_retriever = MultiVectorRetriever(
            vectorstore=self.vectorstore,
            byte_store=self.docstore,
            id_key=id_key,
        )

        # Quebrador fino (apenas para a busca ser cirúrgica)
        child_text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)

        docs_ids = []
        child_docs = []
        
        for doc in parent_documents:
            # Associa um ID único ao Artigo completo (Parent)
            doc_id = str(uuid.uuid4())
            docs_ids.append(doc_id)
            
            # Quebra o Artigo em parágrafos e incisos (Children)
            sub_docs = child_text_splitter.split_documents([doc])
            for sub_doc in sub_docs:
                sub_doc.metadata[id_key] = doc_id
                child_docs.append(sub_doc)
        
        self.raw_child_docs = child_docs

        # 1. Adiciona os "Children" no VectorDB (A Busca é feita neles)
        self.parent_child_retriever.vectorstore.add_documents(child_docs)
        
        # 2. Adiciona os "Parents" no DocStore (O Retriever puxa eles)
        self.parent_child_retriever.docstore.mset(list(zip(docs_ids, parent_documents)))
        print(f"[+] Índice construído. Textos Pais: {len(parent_documents)} | Textos Filhos (Vetoriais): {len(child_docs)}")


    def _build_hybrid_retriever(self, base_retriever, top_k: int = 20):
        """
        Pilar 2: Busca Híbrida (BM25 + Dense)
        Usado para garantir acertos exatos como 'Usucapião Extraordinária'
        mesmo se o vetor semântico falhar.
        """
        print("[*] Configurando Sparse Retriever (BM25)...")
        # Baseia o BM25 nos textos filhos de busca
        bm25_retriever = BM25Retriever.from_documents(self.raw_child_docs)
        bm25_retriever.k = top_k
        
        # Configura o vetor (baseado no MultiVector) para também puxar top_k limitados
        base_retriever.search_kwargs = {"k": top_k}
        
        # Combina 50/50 o peso semântico vs a palavra exata
        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, base_retriever], weights=[0.5, 0.5]
        )
        return ensemble_retriever


    def _apply_reranker(self, base_retriever, top_k: int = 5):
        """
        Pilar 3: Re-Ranking (Cross-Encoder)
        Reduz os ~40 resultados confusos do Híbrido para os 5 melhores.
        """
        print(f"[*] Aplicando Cohere Re-Ranking (Top {top_k})...")
        
        # Necessita COHERE_API_KEY no .env
        compressor = CohereRerank(top_n=top_k)
        
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever
        )
        return compression_retriever


    def build_legal_pipeline(self, parent_documents: List[Document], final_k: int = 5):
        """
        Monta os 4 pilares: Small-to-Big -> Hybrid Search -> Reranker
        """
        # 1. Constrói o banco Parent-Child (Pilar 4)
        self.build_parent_child_index(parent_documents)
        
        # 2. Adiciona Hybrid Search em cima disso (Pilar 2)
        # O Hybrid vai retornar uns 20 documentos misturados num pool
        hybrid_retriever = self._build_hybrid_retriever(self.parent_child_retriever, top_k=20)
        
        # 3. Adiciona Re-Ranking (Pilar 3)
        if self.use_reranker:
            final_retriever = self._apply_reranker(hybrid_retriever, top_k=final_k)
        else:
            final_retriever = hybrid_retriever
            
        return final_retriever

# Exemplo de uso:
def demo_pipeline():
    # Isso simula o Output do "Hierarchical Chunking" (Pilar 1) onde o parse identificou as ramificações:
    mock_parent_docs = [
        Document(
            page_content="Art. 966. Considera-se empresário quem exerce profissionalmente atividade econômica organizada para a produção ou a circulação de bens ou de serviços.\nParágrafo único. Não se considera empresário quem exerce profissão intelectual, de natureza científica, literária ou artística...",
            metadata={"livro": "Direito de Empresa", "titulo": "Do Empresário", "capitulo": "Caracterização", "artigo": "966"}
        ),
        Document(
            page_content="Art. 1.238. Aquele que, por quinze anos, sem interrupção, nem oposição, possuir como seu um imóvel, adquire-lhe a propriedade, independentemente de título e boa-fé; podendo requerer ao juiz que assim o declare por sentença, a qual servirá de título para o registro no Cartório de Registro de Imóveis.",
            metadata={"livro": "Direito das Coisas", "titulo": "Da Propriedade", "capitulo": "Da Aquisição da Propriedade Imóvel", "secao": "Da Usucapião", "artigo": "1238"}
        )
    ]
    
    rag = StateOfTheArtLegalRAG(use_reranker=True) # Exige Cohere API Key!
    
    # Monto minha Ferrari
    retriever = rag.build_legal_pipeline(mock_parent_docs)
    
    query = "O que caracteriza um empresario?"
    resultados = retriever.invoke(query)
    
    print(f"\nResultados injetados pro LLM (Total: {len(resultados)}):")
    for d in resultados:
        # Note que o LLM recebe as informações ricas em metadados!
        print(f"--> [Metadados: {d.metadata}] \n{d.page_content[:150]}...\n")

if __name__ == "__main__":
    # demo_pipeline()
    pass

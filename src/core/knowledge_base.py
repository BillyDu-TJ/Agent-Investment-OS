# src/core/knowledge_base.py

import os
import glob
import chromadb
import logging

class ExpertKnowledgeBase:
    """基于 ChromaDB 的本地文件向量化知识库 (Zero-LangChain)"""
    
    def __init__(self, docs_dir="data/docs", db_path="data/expert_kb"):
        self.docs_dir = docs_dir
        self.db_path = db_path
        
        # 确保知识库目录存在
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.db_path, exist_ok=True)
        
        # 初始化 ChromaDB 本地持久化客户端
        # 注意: Chroma 会自动使用默认的轻量级 Embedding 模型 (all-MiniLM-L6-v2) 
        # 将文本转化为多维向量，完全在本地运行，不需要耗费 API Token。
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.chroma_client.get_or_create_collection(name="investment_rules")
        
        # 启动时自动扫描并吸收新知识
        self._ingest_local_documents()

    def _chunk_text(self, text, chunk_size=400, overlap=50):
        """原生文本分块器 (Text Splitter)"""
        chunks =[]
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap # 保持上下文重叠
        return chunks

    def _ingest_local_documents(self):
        """扫描 docs_dir 目录，将 md/txt 文件自动向量化入库"""
        files = glob.glob(os.path.join(self.docs_dir, "*.txt")) + glob.glob(os.path.join(self.docs_dir, "*.md"))
        
        if not files:
            logging.info(f"📂 知识库文件夹 [{self.docs_dir}] 为空。请放入您的投资经验文档 (.md, .txt)。")
            return

        doc_count = 0
        for filepath in files:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 如果文件为空，跳过
                if not content.strip(): continue
                
                # 分块
                chunks = self._chunk_text(content)
                
                ids = []
                documents = []
                metadatas =[]
                
                for i, chunk in enumerate(chunks):
                    # 组合 ID，例如: my_rule.md_chunk_0
                    # 使用 upsert，如果文件修改了，再次运行会覆盖更新；如果没改，则等于重写一遍
                    chunk_id = f"{filename}_chunk_{i}"
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append({"source": filename})
                
                # 执行向量化写入 (ChromaDB 底层会自动调用模型计算 Embedding)
                self.collection.upsert(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                doc_count += 1
            except Exception as e:
                logging.error(f"❌ 吸收文件 {filename} 失败: {e}")

        logging.info(f"🧠 知识库同步完毕：成功扫描并向量化了 {doc_count} 个本地文档。")

    def query_rules(self, query_text: str, n_results=2) -> str:
        """根据当前市场情境，检索最相关的专家规则"""
        try:
            # 如果库里啥也没有，就不查了
            if self.collection.count() == 0:
                return "本地知识库暂无内容，请向 data/docs 中添加文档。"

            # 检索向量距离最接近的 N 个块
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            if results and results['documents'] and results['documents'][0]:
                extracted_rules = []
                for i, doc in enumerate(results['documents'][0]):
                    source = results['metadatas'][0][i].get('source', 'Unknown')
                    extracted_rules.append(f"引自 [{source}]:\n{doc}")
                return "\n\n".join(extracted_rules)
                
        except Exception as e:
            logging.warning(f"知识库检索失败: {e}")
            
        return "暂无匹配的专家规则。"
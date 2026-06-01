# =============================================================================
# 脚本名称: rag_text_chunker.py
# 功能描述: 将清洗后的小说文本按固定字符数切分为知识块，
#           用于 RAG（检索增强生成）向量数据库入库前的预处理
# 依赖库:   无（标准库）
# 使用方法: 调用 create_knowledge_base('cleaned_novel.txt', chunk_size=500)
# 流水线:   clean_novel → rag_text_chunker → 向量数据库（如 ChromaDB）
# =============================================================================

def create_knowledge_base(input_file, chunk_size=500):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chunks = []
    current_chunk = ""

    for line in lines:
        current_chunk += line
        if len(current_chunk) > chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = ""

    # 这里通常会配合数据库，比如 ChromaDB
    print(f"📚 剧情解析完毕！一共切成了 {len(chunks)} 个知识点。")
    return chunks
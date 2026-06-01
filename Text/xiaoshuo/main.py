# =============================================================================
# 脚本名称: main.py
# 功能描述: 小说 AI 助手数据处理流水线索引（本文件不执行具体任务）
#
# 项目目标: 基于 Gemma 3 构建个人写作助手（风格模仿 + 剧情问答）
# 详细设计: 见同目录 document.md
#
# 数据处理流水线（按顺序）:
#   1. clean_novel.py          - 清洗原始 txt（去广告、规范化）
#   2. create_sft_dataset.py   - 生成 SFT 微调训练集（JSONL）
#   3. rag_text_chunker.py     - 切分文本块供 RAG 向量检索使用
#
# 使用示例:
#   from clean_novel import clean_novel
#   from create_sft_dataset import create_sft_dataset
#   from rag_text_chunker import create_knowledge_base
#
#   clean_novel('xiaoshuo/1.txt', 'cleaned.txt')
#   create_sft_dataset('cleaned.txt', 'train_data.jsonl')
#   create_knowledge_base('cleaned.txt')
# =============================================================================

if __name__ == '__main__':
    print('请按流水线顺序调用各模块函数，详见上方注释说明。')

# =============================================================================
# 脚本名称: clean_novel.py
# 功能描述: 清洗原始小说 txt 文本
#           - 移除广告、章节提示等无关内容
#           - 规范化换行与空白
# 依赖库:   无（标准库）
# 使用方法: 调用 clean_novel('原始.txt', '清洗后.txt')
# 流水线:   本脚本为数据处理第一步，后续接 create_sft_dataset / rag_text_chunker
# =============================================================================

import re


def clean_novel(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. 过滤掉无意义的符号和广告语 (可以根据实际情况增加正则)
    text = re.sub(r'\(本章完\)|最新章节请前往.*|更多好书.*', '', text)

    # 2. 规范化换行和空格
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_text = '\n'.join(lines)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)
    print(f"✨ 宝，清洗完成！干净的小说已经存到 {output_file} 啦！")

# 使用示例
# clean_novel('my_novel_raw.txt', 'cleaned_novel.txt')
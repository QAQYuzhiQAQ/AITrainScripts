# =============================================================================
# 脚本名称: create_sft_dataset.py
# 功能描述: 从清洗后的小说文本生成 SFT 微调训练数据集（JSONL 格式）
#           - 滑动窗口切分，带重叠上下文
#           - 在句号处智能断句，避免截断句子
#           - 输出 instruction / input / output 三段式结构
# 依赖库:   无（标准库）
# 使用方法: 调用 create_sft_dataset('cleaned_novel.txt', 'train_data.jsonl')
# 流水线:   clean_novel → create_sft_dataset → LoRA/QLoRA 微调
# =============================================================================

import json


def create_sft_dataset(input_file, output_jsonl, chunk_size=800, overlap=200):
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    dataset = []
    start = 0

    # 通过滑动窗口切割文本，保证上下文连贯
    while start < len(text) - chunk_size:
        end = start + chunk_size

        # 寻找最近的句号作为切分点，避免话断在半截
        split_pos = text.find('。', end - 50, end + 50)
        if split_pos != -1:
            end = split_pos + 1

        context = text[max(0, start - overlap):start]  # 上文参考
        target = text[start:end]  # 这一段的精华文笔

        data_point = {
            "instruction": "请模仿该小说的文笔和风格，进行续写或创作。",
            "input": f"参考上文：\n{context}\n\n请继续描写：",
            "output": target
        }
        dataset.append(data_point)
        start = end

    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f"📦 搞定！共生成 {len(dataset)} 条训练数据。拿去喂给 Gemma 3 吧！")

# 使用示例
# create_sft_dataset('cleaned_novel.txt', 'novel_train_data.jsonl')
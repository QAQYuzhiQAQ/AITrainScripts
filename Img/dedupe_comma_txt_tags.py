# =============================================================================
# 脚本名称: dedupe_comma_txt_tags.py
# 功能描述: 处理当前目录下所有 .txt 文件，对逗号分隔的标签/词条进行：
#           - 去重
#           - 按词语重叠度过滤（保留更长或更完整的条目）
# 依赖库:   无（标准库）
# 使用方法: 将 .txt 文件放在脚本同目录，运行本脚本（原地覆盖写入）
# =============================================================================

import os
import glob

def find_txt_files(root_dir='.'):
    # 获取当前目录下所有 .txt 文件
    pattern = os.path.join(root_dir, '*.txt')
    return glob.glob(pattern)


def load_items_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 用逗号分割，并去除首尾空白
    return [item.strip() for item in content.split(',') if item.strip()]


def filter_items(items):
    # 使用集合去重
    unique_items = list(dict.fromkeys(items))
    # B 集合，用列表保持可删除性
    filtered = []

    for a in unique_items:
        a_words = set(a.split())
        overlaps = [b for b in filtered if a_words & set(b.split())]

        if overlaps:
            # 如果 filtered 中有与 a 重叠的元素
            # 若有任何 b 长度大于 a，跳过 a
            if any(len(b) > len(a) for b in overlaps):
                continue
            # 否则，移除所有 overlap 项，再加入 a
            filtered = [b for b in filtered if not (a_words & set(b.split()))]
            filtered.append(a)
        else:
            # 无重叠，直接加入
            filtered.append(a)
    return filtered


def write_items_to_file(items, file_path):
    # 写入逗号分隔的新内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(','.join(items))


def process_all_txt(root_dir='.'):
    txt_files = find_txt_files(root_dir)
    for file_path in txt_files:
        items = load_items_from_file(file_path)
        filtered = filter_items(items)
        write_items_to_file(filtered, file_path)
        print(f"Processed {file_path}: {len(items)} -> {len(filtered)} items")


if __name__ == '__main__':
    process_all_txt()

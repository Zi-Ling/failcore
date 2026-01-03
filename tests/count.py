import os


def count_lines_in_file(file_path):
    """
    统计单个文件的行数，忽略编码错误
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except Exception as e:
        print(f"⚠️  无法读取文件 {file_path}: {e}")
        return 0


def count_python_lines_in_subdirs(root_dir):
    """
    统计指定根目录下所有子文件夹中的Python文件行数
    """
    total_lines = 0
    file_stats = []
    # 新增：存储行数＞800的文件
    large_files = []

    # 遍历目录树，跳过根目录直接处理子目录
    for root, dirs, files in os.walk(root_dir):
        # 只处理子目录（root不等于根目录时）
        if root != root_dir:
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    line_count = count_lines_in_file(file_path)
                    file_stats.append((file_path, line_count))
                    total_lines += line_count
                    # 新增：判断行数是否大于800
                    if line_count > 500:
                        large_files.append((file_path, line_count))

    return file_stats, total_lines, large_files


def main():
    # 固定目标目录
    target_directory = r"../failcore"

    # 验证目录是否存在
    if not os.path.isdir(target_directory):
        print(f"❌ 错误: 目录 '{target_directory}' 不存在或不是有效的目录")
        return

    print(f"🔍 正在统计目录: {target_directory} 下子文件夹中的Python文件...\n")

    # 执行统计（新增接收large_files）
    file_stats, total_lines, large_files = count_python_lines_in_subdirs(target_directory)

    # 输出所有文件统计结果
    if file_stats:
        print("📊 所有Python文件行数统计结果:")
        print("-" * 80)
        for file_path, count in sorted(file_stats):
            # 计算相对路径，使输出更简洁
            rel_path = os.path.relpath(file_path, target_directory)
            print(f"{rel_path:<50} {count:>5} 行")

        print("-" * 80)
        print(f"📈 总计行数: {total_lines} 行\n")

        # 新增：输出行数＞500的文件
        if large_files:
            print("⚠️  行数超过500行的文件（需关注代码复杂度）:")
            print("-" * 80)
            for file_path, count in sorted(large_files):
                rel_path = os.path.relpath(file_path, target_directory)
                print(f"{rel_path:<50} {count:>5} 行")
            print("-" * 80)
            print(f"📌 超过500行的文件总数: {len(large_files)} 个\n")
        else:
            print("✅ 暂无行数超过800行的Python文件\n")
    else:
        print("ℹ️  未找到任何Python文件。")


if __name__ == "__main__":
    main()
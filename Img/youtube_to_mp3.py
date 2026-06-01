# =============================================================================
# 脚本名称: youtube_to_mp3.py
# 功能描述: 批量下载 YouTube 视频并转换为 MP3 音频（192kbps）
#           支持换行分隔的多链接输入，自动跳过已下载文件
# 依赖库:   yt-dlp, FFmpeg（需系统已安装并在 PATH 中）
# 使用方法: 修改底部 YOUTUBE_LINKS 链接列表，运行本脚本
# =============================================================================

import yt_dlp
import os

def download_youtube_to_mp3(links_str, save_dir="./youtube_mp3"):
    """
    批量下载YouTube视频并转换为MP3格式
    :param links_str: 包含多个YouTube链接的字符串（换行符分隔）
    :param save_dir: 音频保存目录（默认当前目录下的youtube_mp3文件夹）
    """
    # 1. 预处理链接：按换行符分割，去除空行和首尾空格
    links = [link.strip() for link in links_str.split('\n') if link.strip()]
    
    if not links:
        print("错误：未找到有效的YouTube链接！")
        return
    
    # 2. 创建保存目录（如果不存在）
    os.makedirs(save_dir, exist_ok=True)
    print(f"音频将保存到：{os.path.abspath(save_dir)}")
    
    # 3. 配置yt-dlp参数（核心配置）
    ydl_opts = {
        # 保存路径和文件名格式：目录/视频标题.mp3
        'outtmpl': os.path.join(save_dir, '%(title)s.%(ext)s'),
        # 仅下载最佳质量音频
        'format': 'bestaudio/best',
        # 音频后处理：转换为MP3
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',       # 目标格式：MP3
            'preferredquality': '192',     # 音频质量：192kbps（平衡音质和文件大小）
        }],
        # 跳过已下载的文件（避免重复下载）
        'download_archive': os.path.join(save_dir, '.downloaded.txt'),
        # 显示下载进度，隐藏无关警告
        'quiet': False,
        'no_warnings': True,
        # 超时设置（防止网络卡顿）
        'timeout': 30,
    }

    # 4. 批量处理每个链接
    success_count = 0
    fail_links = []
    
    print(f"\n开始处理 {len(links)} 个链接...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for idx, link in enumerate(links, 1):
            print(f"\n===== 处理第 {idx}/{len(links)} 个链接 =====")
            print(f"链接：{link}")
            try:
                # 下载并转换当前链接
                ydl.download([link])
                print(f"✅ 第 {idx} 个链接处理成功！")
                success_count += 1
            except Exception as e:
                error_msg = f"❌ 第 {idx} 个链接处理失败：{str(e)}"
                print(error_msg)
                fail_links.append((link, error_msg))

    # 5. 输出最终统计结果
    print("\n" + "-"*50)
    print(f"处理完成！成功：{success_count} 个，失败：{len(fail_links)} 个")
    if fail_links:
        print("\n失败的链接列表：")
        for link, msg in fail_links:
            print(f"- 链接：{link}")
            print(f"  原因：{msg}")
    print(f"\n所有成功的MP3文件已保存至：{os.path.abspath(save_dir)}")

# ===================== 主程序入口 =====================
if __name__ == "__main__":
    # 定义YouTube链接字符串（换行符分隔，可添加任意多个）
    YOUTUBE_LINKS = """
https://www.youtube.com/watch?v=example1
https://www.youtube.com/watch?v=example2
https://www.youtube.com/watch?v=example3
    """
    
    # 调用下载函数
    download_youtube_to_mp3(YOUTUBE_LINKS)
import PyInstaller.__main__
import customtkinter
import os
import platform
import shutil

def build():
    # 根据操作系统确定路径分隔符
    # Windows 使用分号 (;)，Unix/Linux/macOS 使用冒号 (:)
    separator = ";" if platform.system() == "Windows" else ":"
    
    # 图标文件路径
    icon_file = os.path.join("icon", "favicon1.ico")
    
    # 基础参数
    args = [
        "main.py",              # 主程序入口
        "--noconfirm",          # 不询问确认
        "--onedir",             # 生成目录结构 (调试方便，启动快)
        "--windowed",           # 无控制台窗口
        f"--icon={icon_file}",  # 应用程序图标
        "--name=CursorPilot",   # 生成的可执行文件名称
        "--clean",              # 清理缓存
        
        # 收集 customtkinter 的所有资源（代码、数据、二进制）
        "--collect-all=customtkinter",
        
        # 包含我们自己的图标文件夹
        f"--add-data=icon{separator}icon",
    ]
    
    print(f"正在 {platform.system()} 平台上开始打包...")
    print(f"命令参数: {args}")
    
    # 执行打包
    PyInstaller.__main__.run(args)
    
    print("\n打包完成！")
    print(f"可执行文件位于 dist/CursorPilot 目录中。")

if __name__ == "__main__":
    # 确保在脚本所在目录运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 如果存在旧的构建文件夹，尝试清理
    if os.path.exists("build"):
        try: shutil.rmtree("build")
        except: pass
    if os.path.exists("dist"):
        try: shutil.rmtree("dist")
        except: pass
        
    build()

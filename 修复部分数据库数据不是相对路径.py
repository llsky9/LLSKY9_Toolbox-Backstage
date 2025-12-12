import os
import sqlite3
import sys

# =================配置区域=================
# 数据库相对于脚本的路径
DB_REL_PATH = os.path.join(".res", "data.db")
# =========================================

def fix_paths():
    # 1. 获取当前脚本所在的根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_REL_PATH)

    print(f"当前工作目录: {current_dir}")
    print(f"目标数据库:   {db_path}")
    print("-" * 60)

    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print("❌ 错误: 找不到数据库文件！")
        print("请确保将此脚本放在与 ai_studio_code.py 同级的根目录下。")
        input("按回车键退出...")
        return

    # 2. 连接数据库 (不再创建备份)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 查询所有工具的路径
        cursor.execute("SELECT id, name, path FROM tools")
        rows = cursor.fetchall()
        
        modified_count = 0
        
        print("\n正在扫描并计算相对路径...\n")

        for row in rows:
            tool_id, name, old_path = row
            
            if not old_path:
                continue

            new_path = old_path
            
            # --- 核心逻辑：路径转换 ---
            
            # 情况1：如果是绝对路径 (例如 D:\Tools\App.exe)
            if os.path.isabs(old_path):
                # ================= 盘符检测逻辑 =================
                # 获取脚本所在盘符 (例如 C:) 和 数据库记录路径的盘符 (例如 D:)
                curr_drive = os.path.splitdrive(current_dir)[0]
                target_drive = os.path.splitdrive(old_path)[0]

                # 如果两个路径都有盘符，且盘符不一致 (忽略大小写)
                if curr_drive and target_drive and curr_drive.lower() != target_drive.lower():
                    # 保持原样，不提示也不修改，或者可以选择提示一下
                    print(f"⚓ 保持绝对路径 (不同盘符): {name}")
                    continue
                # ===============================================

                try:
                    # 计算从 current_dir 到 old_path 的相对路径
                    rel = os.path.relpath(old_path, current_dir)
                    new_path = rel
                except ValueError:
                    print(f"⚠️ 跳过 (无法计算相对路径): {name}")
                    continue
            
            # 情况2：规范化分隔符 (把 / 变成 \，或去除多余的 ..)
            new_path = os.path.normpath(new_path)

            # --- 对比是否有变化 ---
            if new_path != old_path:
                print(f"🔄 修复 ID:{tool_id} [{name}]")
                print(f"   🔴 原路径: {old_path}")
                print(f"   🟢 新路径: {new_path}")
                print("-" * 30)
                
                # 更新内存中的SQL语句，暂不提交
                cursor.execute("UPDATE tools SET path = ? WHERE id = ?", (new_path, tool_id))
                modified_count += 1
        
        # 3. 确认并保存
        if modified_count > 0:
            print(f"\n共发现 {modified_count} 个路径建议修复。")
            confirm = input("👉 确认写入数据库吗？(输入 y 确认，直接回车取消): ")
            if confirm.lower() == 'y':
                conn.commit()
                print("\n✅ 数据库更新成功！")
            else:
                print("\n🚫 操作已取消，数据库未被修改。")
        else:
            print("\n✅ 完美！没有发现需要修复的路径。")

    except Exception as e:
        print(f"\n❌ 运行时发生错误: {e}")
    finally:
        conn.close()
        input("\n按回车键退出...")

if __name__ == "__main__":
    fix_paths()
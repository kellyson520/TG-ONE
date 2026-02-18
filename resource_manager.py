
import pandas as pd
import os
import shutil
import re
import glob
import sys
from datetime import datetime

# ==========================================
# 配置区域
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_FILE_PATH = os.path.join(BASE_DIR, '咸鱼度盘源.xlsx')  # 完整版 (含链接)
PUBLIC_FILE_PATH = os.path.join(BASE_DIR, '咸鱼度盘.xlsx')   # 公开版 (无链接)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# ==========================================
# 辅助函数: 智能查找无效文件
# ==========================================
def find_invalid_file():
    txt_files = glob.glob(os.path.join(BASE_DIR, '*.txt'))
    if not txt_files:
        return None
    if len(txt_files) == 1:
        return txt_files[0]
    print("\n发现多个 TXT 文件:")
    for i, f in enumerate(txt_files):
        print(f"{i+1}. {os.path.basename(f)}")
    while True:
        choice = input("\n请选择包含无效链接的文件编号 (输入0取消): ").strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(txt_files):
            return txt_files[int(choice)-1]
        print("无效输入，请重新输入")

def normalize_link(text):
    if not isinstance(text, str): return str(text)
    m = re.search(r'(https?://[\w\-\./?=&%]+)', text)
    return m.group(1) if m else text.strip()

def load_invalid_urls(file_path):
    if not file_path: return set()
    encodings = ['utf-8', 'gb18030', 'gbk']
    content = []
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.readlines()
            break
        except UnicodeDecodeError:
            continue
            
    invalid_urls = set()
    for line in content:
        match = re.search(r'(https?://[\w\-\./?=&%]+)', line)
        if match:
            url = match.group(1)
            if '链接' in url: url = url.split('链接')[0]
            invalid_urls.add(url)
    return invalid_urls

# ==========================================
# 功能1: 自动维护 (针对 '咸鱼度盘源.xlsx')
# ==========================================
def clean_source_file():
    print("\n" + "="*40)
    print("      执行自动维护 (仅处理源文件)")
    print("="*40)
    print(f"目标文件: {os.path.basename(SOURCE_FILE_PATH)} (保留完整列)")
    
    invalid_file_path = find_invalid_file()
    if not invalid_file_path:
        print("❌ 错误: 未找到黑名单文件")
        return

    print(f"📄 黑名单: {os.path.basename(invalid_file_path)}")

    
    # 1. Parse Invalid Links
    print("--- 1. 解析无效链接 ---")
    invalid_urls = load_invalid_urls(invalid_file_path)
    print(f"   提取到 {len(invalid_urls)} 条需移除的链接。")

    # 2. Process
    print(f"\n--- 2. 清洗文件: {os.path.basename(SOURCE_FILE_PATH)} ---")
    try:
        # Check if file exists
        if not os.path.exists(SOURCE_FILE_PATH):
             print(f"❌ 源文件不存在: {SOURCE_FILE_PATH}")
             return

        all_sheets = pd.read_excel(SOURCE_FILE_PATH, sheet_name=None)
    except Exception as e:
        print(f"   读取失败: {e}")
        return

    cleaned_sheets = {}
    total_removed = 0
    link_col_name = '链接'

    for sheet_name, df in all_sheets.items():
        if link_col_name not in df.columns:
            cleaned_sheets[sheet_name] = df
            continue
            
        initial_count = len(df)
            
        excel_links = df[link_col_name].apply(normalize_link)
        mask = ~excel_links.isin(invalid_urls)
        
        df_cleaned = df[mask]
        removed = initial_count - len(df_cleaned)
        total_removed += removed
        cleaned_sheets[sheet_name] = df_cleaned

    # Save
    if total_removed > 0:
        print("\n--- 3. 保存更改 ---")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_backup = os.path.join(BASE_DIR, f'咸鱼度盘源_backup_{timestamp}.xlsx')
        try:
            shutil.copy2(SOURCE_FILE_PATH, new_backup)
            print(f"   已备份源文件至: {os.path.basename(new_backup)}")
            
            with pd.ExcelWriter(SOURCE_FILE_PATH, engine='openpyxl') as writer:
                for sheet_name, df in cleaned_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"   ✅ '咸鱼度盘源.xlsx' 已更新 (移除 {total_removed} 行)")
        except Exception as e:
            print(f"   ❌ 保存失败: {e}")
    else:
        print("\n   ✅ 源文件无需修改 (未发现失效链接)")

# ==========================================
# 功能2: 资源查询 (基于 '咸鱼度盘源.xlsx')
# ==========================================
def search_resources():
    print("\n" + "="*40)
    print("      资源查询 (基于完整源文件)")
    print("="*40)
    
    # Pre-check: Load invalid links if any
    invalid_urls = set()
    print("检测到失效链接库文件(.txt):")
    invalid_file = find_invalid_file()
    if invalid_file:
        print(f"正在加载失效库: {os.path.basename(invalid_file)}...")
        invalid_urls = load_invalid_urls(invalid_file)
        print(f"✅ 已加载 {len(invalid_urls)} 条失效链接规则。")
    else:
        print("未加载失效库，跳过有效性检查。")

    try:
        all_sheets = pd.read_excel(SOURCE_FILE_PATH, sheet_name=None)
    except Exception as e:
        print(f"读取源文件失败: {e}")
        return

    data_index = {}
    for sheet_name, df in all_sheets.items():
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            if '链接' in c and 'tg' not in c: col_map['link'] = c
            elif '解压码' in c or ('密码' in c and '提取码' not in c): col_map['unzip'] = c
            elif '备注' in c: col_map['note'] = c
            elif '提取码' in c: col_map['pwd'] = c
            elif '序号' in c: col_map['id'] = c
        
        if 'id' not in col_map: continue
        
        sheet_index = {}
        for idx, row in df.iterrows():
            raw_id = row[col_map['id']]
            if pd.isna(raw_id): continue
            try:
                if isinstance(raw_id, float) and raw_id.is_integer():
                    serial = str(int(raw_id))
                else:
                    serial = str(raw_id).strip()
                    if serial.endswith(".0"): serial = serial[:-2]
            except:
                serial = str(raw_id).strip()

            item = {
                'link': row.get(col_map.get('link'), 'N/A'),
                'pwd': row.get(col_map.get('pwd'), 'NaN'),
                'unzip': row.get(col_map.get('unzip'), '无'),
                'note': row.get(col_map.get('note'), '')
            }
            sheet_index[serial] = item
        data_index[sheet_name] = sheet_index

    print(f"数据加载完毕。可用页号: {list(data_index.keys())}")
    print("输入格式1: 页号 序号 (如: A 1)")
    print("输入格式2: 页号(序号1.序号2...) (如: a(1.2.3)) - 批量导出结果")
    print("输入 q 退出")
    print("-" * 50)

    while True:
        choice = input("\n查询 > ").strip()
        if choice.lower() in ('q', 'quit', 'exit'): break
        if not choice: continue
        
        # Check for batch pattern: e.g. a(1.2.3) or a（1.2.3）
        batch_match = re.match(r'^(.+?)[(（]([\d\.]+)[)）]$', choice)
        if batch_match:
            sheet_input = batch_match.group(1).strip()
            ids_str = batch_match.group(2)
            
            # Find sheet
            found_sheet = next((s for s in data_index if s.lower() == sheet_input.lower()), None)
            if not found_sheet:
                print(f"  [❌] 未找到页号: {sheet_input}")
                continue
                
            # Parse IDs
            id_list = [x.strip() for x in ids_str.split('.') if x.strip()]
            
            results = []
            not_found = []
            
            print(f"\n正在批量查找 {found_sheet} 中的 {len(id_list)} 个条目...")
            
            for sn in id_list:
                item = data_index[found_sheet].get(str(sn))
                if item:
                    full_link = str(item['link'])
                    clean_link = normalize_link(full_link)
                    
                    # Validity Check
                    if invalid_urls and clean_link in invalid_urls:
                        print(f"  ❌ 失效: {sn} [命中黑名单]")
                        not_found.append(f"{sn}(失效)")
                        continue

                    if str(item['pwd']) != 'nan' and str(item['pwd']) not in full_link:
                        full_link += f" (提取码: {item['pwd']})"
                    
                    res_str = f"[ID: {sn}]\n链接: {full_link}\n解压: {item['unzip']}\n备注: {item['note']}\n"
                    results.append(res_str)
                    print(f"  ✅ 找到: {sn}")
                else:
                    not_found.append(sn)
                    print(f"  ❌ 未找到: {sn}")
            
            # Save to file
            if results:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"search_results_{found_sheet}_{timestamp}.txt"
                filepath = os.path.join(BASE_DIR, filename)
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"资源搜索结果: {found_sheet}\n")
                        f.write(f"生成的: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("=" * 30 + "\n\n")
                        f.write("\n".join(results))
                        if not_found:
                            f.write("\n" + "=" * 30 + "\n")
                            f.write(f"未找到/失效序号 ({len(not_found)}个):\n")
                            f.write(", ".join(not_found))
                    
                    print(f"\n📄 结果已保存至: {filename}")
                except Exception as e:
                    print(f"❌ 保存失败: {e}")

                if not_found:
                    print(f"⚠️  未找到/失效 IDs: {', '.join(not_found)}")
            else:
                print("\n⚠️  未找到任何匹配项。")
            
            continue

        parts = choice.replace(',', ' ').replace('-', ' ').replace(':', ' ').split()
        if len(parts) % 2 != 0:
            print("❌ 格式错误。")
            continue
            
        for i in range(0, len(parts), 2):
            pg, sn = parts[i], parts[i+1]
            found_sheet = next((s for s in data_index if s.lower() == pg.lower()), None)
            if not found_sheet:
                print(f"  [❌] 未找到页号 {pg}")
                continue
            item = data_index[found_sheet].get(str(sn))
            if item:
                full_link = str(item['link'])
                if str(item['pwd']) != 'nan' and str(item['pwd']) not in full_link:
                    full_link += f" (提取码: {item['pwd']})"
                print(f"  [✅ {found_sheet}-{sn}]")
                print(f"      链接: {full_link}")
                print(f"      解压: {item['unzip']}")
                print(f"      备注: {item['note']}")
            else:
                print(f"  [❌] {found_sheet}-{sn} 不存在")

# ==========================================
# 功能3: 生成公开版 (咸鱼度盘.xlsx)
# ==========================================
def generate_public_file():
    print("\n" + "="*40)
    print("      生成公开分享版")
    print("="*40)
    
    # 明确展示输入输出
    print(f"1. 读取源文件: {os.path.basename(SOURCE_FILE_PATH)} (保持不变)")
    print(f"2. 输出目标:   {os.path.basename(PUBLIC_FILE_PATH)} (将被覆盖)")
    
    if not os.path.exists(SOURCE_FILE_PATH):
        print(f"❌ 错误: 源文件不存在!")
        return

    print("\n正在处理数据...")
    try:
        all_sheets = pd.read_excel(SOURCE_FILE_PATH, sheet_name=None)
    except Exception as e:
        print(f"读取失败: {e}")
        return

    columns_to_drop = ['tg链接', '链接']
    processed_sheets = {}
    
    for sheet_name, df in all_sheets.items():
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        
        # Identify columns to drop
        drop_list = [c for c in df.columns if c in columns_to_drop]
        
        if drop_list:
            processed_sheets[sheet_name] = df.drop(columns=drop_list)
            print(f"   Sheet '{sheet_name}': 已剔除 {drop_list}")
        else:
            processed_sheets[sheet_name] = df
            print(f"   Sheet '{sheet_name}': 无敏感列，保留原样")

    print(f"\n正在写入文件: {os.path.basename(PUBLIC_FILE_PATH)} ...")
    try:
        with pd.ExcelWriter(PUBLIC_FILE_PATH, engine='openpyxl') as writer:
            for sheet_name, df in processed_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print("✅ 导出成功！")
        print("   该文件已不包含 'tg链接' 和 '百度网盘链接' 列。")
    except Exception as e:
        print(f"❌ 写入失败: {e}")

# ==========================================
# 主程序入口
# ==========================================
def main_menu():
    while True:
        clear_screen()
        print("\n" + "="*40)
        print("      咸鱼度盘源 - 综合管理工具")
        print("="*40)
        print(" 当前源文件: 咸鱼度盘源.xlsx")
        print("-" * 40)
        print("1. 自动清洗维护 (仅更新源文件)")
        print("2. 资源查询 (使用源文件)")
        print("3. 生成公开版 (另存为 '咸鱼度盘.xlsx')")
        print("q. 退出程序")
        print("-" * 40)
        
        choice = input("请选择功能: ").strip().lower()
        
        if choice == '1':
            clean_source_file()
            input("\n按回车键返回主菜单...")
        elif choice == '2':
            search_resources()
        elif choice == '3':
            generate_public_file()
            input("\n按回车键返回主菜单...")
        elif choice in ('q', 'quit', 'exit'):
            print("再见！")
            break
        else:
            print("无效输入")
            input("按回车键继续...")

if __name__ == "__main__":
    main_menu()

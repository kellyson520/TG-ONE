from telethon import events, Button
from version import UPDATE_INFO
import math
from core.helpers.auto_delete import reply_and_delete

ITEMS_PER_PAGE = 5

def parse_changelog():
    lines = UPDATE_INFO.strip().splitlines()
    entries = []
    current_entry = ""
    
    # Skip the first line if it's header like "**更新日志**"
    if lines and "**更新日志**" in lines[0]:
        lines = lines[1:]
        
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("- v"):
            if current_entry:
                entries.append(current_entry)
            current_entry = line
        else:
            # Append continuation lines (if any)
            current_entry += "\n  " + line
    
    if current_entry:
        entries.append(current_entry)
    return entries

async def show_changelog(event, page=1):
    entries = parse_changelog()
    total_items = len(entries)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    
    if total_pages == 0:
        await event.respond("暂无更新日志")
        return

    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    page_entries = entries[start_idx:end_idx]
    
    text = f"**📜 更新日志 (第 {page}/{total_pages} 页)**\n\n"
    text += "\n\n".join(page_entries)
    
    buttons = []
    nav_row = []
    if page > 1:
        nav_row.append(Button.inline("⬅️ 上一页", f"cl_page:{page-1}"))
    else:
        nav_row.append(Button.inline("⬅️", "noop"))
        
    nav_row.append(Button.inline(f"{page}/{total_pages}", "noop"))
    
    if page < total_pages:
        nav_row.append(Button.inline("下一页 ➡️", f"cl_page:{page+1}"))
    else:
        nav_row.append(Button.inline("➡️", "noop"))
        
    buttons.append(nav_row)
    buttons.append([Button.inline("❌ 关闭", "delete")])
    
    # Check if event is Message (command) or CallbackQuery
    if hasattr(event, 'edit'): # CallbackQuery
        await event.edit(text, buttons=buttons)
    else: # Message
        await event.respond(text, buttons=buttons)

async def callback_changelog_page(event):
    """处理更新日志翻页回调"""
    page_str = event.router_params.get('page', '1')
    try:
        page = int(page_str)
    except ValueError:
        page = 1
    await show_changelog(event, page)

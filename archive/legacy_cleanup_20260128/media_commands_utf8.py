from core.logging import get_logger
from core.helpers.auto_delete import reply_and_delete
from services.rule_service import RuleQueryService

logger = get_logger(__name__)

async def _get_current_rule_for_chat(session, event):
    """鏍规嵁褰撳墠鑱婂ぉ鑾峰彇褰撳墠瑙勫垯 - 閫傞厤 RuleQueryService"""
    return await RuleQueryService.get_current_rule_for_chat(event, session)


async def handle_set_duration_command(event, parts):
    """/set_duration <min> [max]"""
    # 浠巆ontainer鑾峰彇鏁版嵁搴撲細璇?
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "鉂?鏈壘鍒板綋鍓嶈亰澶╃殑瑙勫垯锛岃鍏?/switch 閫夋嫨婧愯亰澶?
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "鐢ㄦ硶: /set_duration <鏈€灏忕> [鏈€澶х]\n绀轰緥: /set_duration 30 300 鎴?/set_duration 0 300 鎴?/set_duration 30",
                )
                return
            try:
                min_val = int(parts[1])
                max_val = (
                    int(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_duration", 0)
                )
            except ValueError:
                await reply_and_delete(event, "鉂?鍙傛暟蹇呴』涓烘暣鏁?)
                return
            if min_val < 0 or max_val < 0:
                await reply_and_delete(event, "鉂?鏃堕暱涓嶈兘涓鸿礋鏁?)
                return
            if max_val > 0 and min_val > max_val:
                await reply_and_delete(event, "鉂?鏈€灏忔椂闀夸笉鑳藉ぇ浜庢渶澶ф椂闀?)
                return
            rule.enable_duration_filter = True
            rule.min_duration = min_val
            rule.max_duration = max_val
            await session.commit()
            await reply_and_delete(
                event,
                f"鉁?鏃堕暱鑼冨洿宸茶缃负: {min_val}s - {max_val if max_val>0 else '鈭?}s",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"璁剧疆鏃堕暱鑼冨洿澶辫触: {str(e)}")
            await reply_and_delete(event, "鉂?璁剧疆鏃堕暱鑼冨洿澶辫触锛岃妫€鏌ユ棩蹇?)


async def handle_set_resolution_command(event, parts):
    """/set_resolution <min_w> <min_h> [max_w] [max_h]"""
    # 浠巆ontainer鑾峰彇鏁版嵁搴撲細璇?
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "鉂?鏈壘鍒板綋鍓嶈亰澶╃殑瑙勫垯锛岃鍏?/switch 閫夋嫨婧愯亰澶?
                )
                return
            if len(parts) not in (3, 5):
                await reply_and_delete(
                    event,
                    "鐢ㄦ硶: /set_resolution <鏈€灏忓> <鏈€灏忛珮> [鏈€澶у] [鏈€澶ч珮]\n绀轰緥: /set_resolution 720 480 1920 1080 鎴?/set_resolution 720 480",
                )
                return
            try:
                min_w = int(parts[1])
                min_h = int(parts[2])
                max_w = (
                    int(parts[3]) if len(parts) >= 5 else getattr(rule, "max_width", 0)
                )
                max_h = (
                    int(parts[4]) if len(parts) >= 5 else getattr(rule, "max_height", 0)
                )
            except ValueError:
                await reply_and_delete(event, "鉂?鍙傛暟蹇呴』涓烘暣鏁?)
                return
            if min_w < 0 or min_h < 0 or max_w < 0 or max_h < 0:
                await reply_and_delete(event, "鉂?鍒嗚鲸鐜囦笉鑳戒负璐熸暟")
                return
            if max_w > 0 and min_w > max_w:
                await reply_and_delete(event, "鉂?鏈€灏忓搴︿笉鑳藉ぇ浜庢渶澶у搴?)
                return
            if max_h > 0 and min_h > max_h:
                await reply_and_delete(event, "鉂?鏈€灏忛珮搴︿笉鑳藉ぇ浜庢渶澶ч珮搴?)
                return
            rule.enable_resolution_filter = True
            rule.min_width = min_w
            rule.min_height = min_h
            rule.max_width = max_w
            rule.max_height = max_h
            await session.commit()
            await reply_and_delete(
                event,
                f"鉁?鍒嗚鲸鐜囪寖鍥村凡璁剧疆涓? {min_w}x{min_h} - {max_w if max_w>0 else '鈭?}x{max_h if max_h>0 else '鈭?}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"璁剧疆鍒嗚鲸鐜囪寖鍥村け璐? {str(e)}")
            await reply_and_delete(event, "鉂?璁剧疆鍒嗚鲸鐜囪寖鍥村け璐ワ紝璇锋鏌ユ棩蹇?)


def _parse_size_to_kb(s: str) -> int:
    s = s.strip().upper()
    if s.endswith("G"):
        return int(float(s[:-1]) * 1024 * 1024)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1024)
    if s.endswith("K") or s.endswith("KB"):
        return int(float(s.rstrip("KB")))
    return int(s)


async def handle_set_size_command(event, parts):
    """/set_size <min> [max]锛屾敮鎸並/M/G鍗曚綅"""
    # 浠巆ontainer鑾峰彇鏁版嵁搴撲細璇?
    from core.container import container
    async with container.db.session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "鉂?鏈壘鍒板綋鍓嶈亰澶╃殑瑙勫垯锛岃鍏?/switch 閫夋嫨婧愯亰澶?
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "鐢ㄦ硶: /set_size <鏈€灏忓ぇ灏? [鏈€澶уぇ灏廬\n绀轰緥: /set_size 10M 200M 鎴?/set_size 1024 20480 鎴?/set_size 0 200M",
                )
                return
            try:
                min_kb = _parse_size_to_kb(parts[1])
                max_kb = (
                    _parse_size_to_kb(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_file_size", 0)
                )
            except ValueError:
                await reply_and_delete(event, "鉂?澶у皬鍙傛暟鏍煎紡閿欒锛屾敮鎸並/M/G鍗曚綅")
                return
            if min_kb < 0 or max_kb < 0:
                await reply_and_delete(event, "鉂?鏂囦欢澶у皬涓嶈兘涓鸿礋鏁?)
                return
            if max_kb > 0 and min_kb > max_kb:
                await reply_and_delete(event, "鉂?鏈€灏忓ぇ灏忎笉鑳藉ぇ浜庢渶澶уぇ灏?)
                return
            rule.enable_file_size_range = True
            rule.min_file_size = min_kb
            rule.max_file_size = max_kb
            await session.commit()

            def _fmt(kb: int):
                if kb >= 1024 * 1024:
                    return f"{kb/1024/1024:.1f}GB"
                if kb >= 1024:
                    return f"{kb/1024:.1f}MB"
                return f"{kb}KB"

            await reply_and_delete(
                event,
                f"鉁?鏂囦欢澶у皬鑼冨洿宸茶缃负: {_fmt(min_kb)} - {_fmt(max_kb) if max_kb>0 else '鈭?}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"璁剧疆鏂囦欢澶у皬鑼冨洿澶辫触: {str(e)}")
            await reply_and_delete(event, "鉂?璁剧疆鏂囦欢澶у皬鑼冨洿澶辫触锛岃妫€鏌ユ棩蹇?)

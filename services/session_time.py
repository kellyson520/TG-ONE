import logging
from typing import Dict, Any

from core.helpers.time_range import clamp_time_component, format_time_range_display
from services.forward_settings_service import forward_settings_service

logger = logging.getLogger(__name__)


class SessionTimeMixin:
    """时间范围、延迟设置相关方法"""

    def get_time_range(self, user_id: int) -> Dict[str, int]:
        return self._get_user_session(user_id).get('time_range', {})

    def set_time_range(self, user_id: int, time_range: Dict[str, int]):
        self._get_user_session(user_id)['time_range'] = time_range

    async def set_days(self, user_id: int, days: int) -> Dict[str, Any]:
        days = clamp_time_component(days, "day")
        time_range = self.get_time_range(user_id).copy()
        time_range.update({
            'start_year': 0, 'start_month': 0, 'start_day': days,
            'start_hour': 0, 'start_minute': 0, 'start_second': 0,
            'end_year': 0, 'end_month': 0, 'end_day': 0,
            'end_hour': 0, 'end_minute': 0, 'end_second': 0,
        })
        self.set_time_range(user_id, time_range)
        return {'success': True, 'time_range': time_range}

    async def set_year(self, user_id: int, year: int) -> Dict[str, Any]:
        time_range = self.get_time_range(user_id).copy()
        time_range['start_year'] = clamp_time_component(year, "year")
        self.set_time_range(user_id, time_range)
        return {'success': True, 'time_range': time_range}

    async def set_month(self, user_id: int, month: int) -> Dict[str, Any]:
        time_range = self.get_time_range(user_id).copy()
        time_range['start_month'] = clamp_time_component(month, "month")
        self.set_time_range(user_id, time_range)
        return {'success': True, 'time_range': time_range}

    async def set_day_of_month(self, user_id: int, day: int) -> Dict[str, Any]:
        time_range = self.get_time_range(user_id).copy()
        time_range['start_day'] = clamp_time_component(day, "day")
        self.set_time_range(user_id, time_range)
        return {'success': True, 'time_range': time_range}

    async def get_time_range_config(self, user_id: int) -> Dict[str, Any]:
        try:
            time_range = self.get_time_range(user_id)
            if not time_range:
                time_range = {
                    'start_year': 0, 'start_month': 0, 'start_day': 0,
                    'start_hour': 0, 'start_minute': 0, 'start_second': 0,
                    'end_year': 0, 'end_month': 0, 'end_day': 0,
                    'end_hour': 0, 'end_minute': 0, 'end_second': 0
                }
            is_all_messages = all(time_range.get(key, 0) == 0 for key in time_range.keys())
            try:
                display_text = format_time_range_display(time_range)
            except Exception:
                display_text = "全部时间" if is_all_messages else "自定义"
            return {
                'success': True, 'time_range': time_range,
                'is_all_messages': is_all_messages, 'display_text': display_text
            }
        except Exception as e:
            logger.error(f"获取时间范围配置失败: {e}")
            return {'success': False, 'error': str(e)}

    async def update_time_range(self, user_id: int, **time_params) -> Dict[str, Any]:
        try:
            current = self.get_time_range(user_id) or {}
            updated = {**current, **time_params}
            self.set_time_range(user_id, updated)
            return {'success': True, 'time_range': updated, 'message': '时间范围已更新'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def set_history_message_limit(self, limit: int) -> Dict[str, Any]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return {'success': False, 'error': '请输入有效的数字'}
        if limit < 0 or limit > 1_000_000:
            return {'success': False, 'error': '数量限制必须在 0-1000000 之间'}
        from core.config import settings
        settings.HISTORY_MESSAGE_LIMIT = limit
        try:
            await forward_settings_service.update_global_media_setting(
                "HISTORY_MESSAGE_LIMIT", limit
            )
        except Exception as e:
            logger.warning(f"保存历史消息数量限制到全局配置失败: {e}")
        return {'success': True, 'limit': limit}

    async def save_time_range_settings(self, user_id: int) -> bool:
        try:
            current = self.get_time_range(user_id) or {}
            if current:
                self.set_time_range(user_id, current.copy())
            else:
                await self.get_time_range_config(user_id)
            return True
        except Exception as e:
            logger.error(f"保存时间范围设置失败: {e}")
            return False

    async def get_delay_settings(self, user_id: int) -> Dict[str, Any]:
        try:
            delay = self._get_user_session(user_id).get('delay', 0)
            return {
                'success': True, 'delay_seconds': delay,
                'delay_text': self._format_delay_text(delay)
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'delay_seconds': 0}

    async def update_delay_setting(self, user_id: int, delay_seconds: int) -> Dict[str, Any]:
        try:
            if delay_seconds < 0 or delay_seconds > 3600:
                return {'success': False, 'error': '延迟时间必须在0-3600秒之间'}
            self._get_user_session(user_id)['delay'] = delay_seconds
            return {
                'success': True, 'delay_seconds': delay_seconds,
                'delay_text': self._format_delay_text(delay_seconds),
                'message': f'延迟已设置为 {self._format_delay_text(delay_seconds)}'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _format_delay_text(self, delay: int) -> str:
        if delay == 0: return "无延迟"
        elif delay < 60: return f"{delay}秒"
        else: return f"{delay // 60}分{delay % 60}秒"

    async def adjust_time_component(self, chat_id: int, side: str, field: str, delta: int):
        import calendar
        from datetime import datetime
        tr = self.get_time_range(chat_id)
        now = datetime.now()
        y = tr.get(f"{side}_year") or now.year
        m = tr.get(f"{side}_month") or now.month
        d = tr.get(f"{side}_day") or now.day
        h = tr.get(f"{side}_hour") or 0
        mn = tr.get(f"{side}_minute") or 0
        sc = tr.get(f"{side}_second") or 0
        if field == "year": y += delta
        elif field == "month":
            m += delta
            if m > 12: m = 1
            if m < 1: m = 12
        elif field == "day":
            d += delta
            _, max_d = calendar.monthrange(y, m if m > 0 else 1)
            if d > max_d: d = 1
            if d < 1: d = max_d
        elif field == "hour":
            h += delta
            if h > 23: h = 0
            if h < 0: h = 23
        elif field == "minute":
            mn += delta
            if mn > 59: mn = 0
            if mn < 0: mn = 59
        elif field == "second":
            sc += delta
            if sc > 59: sc = 0
            if sc < 0: sc = 59
        _, last_day = calendar.monthrange(y, m if m > 0 else 1)
        if d > last_day: d = last_day
        tr[f"{side}_year"] = y
        tr[f"{side}_month"] = m
        tr[f"{side}_day"] = d
        tr[f"{side}_hour"] = h
        tr[f"{side}_minute"] = mn
        tr[f"{side}_second"] = sc
        self.set_time_range(chat_id, tr)

    def get_time_picker_context(self, chat_id):
        return self._get_user_session(chat_id).get('picker_context', 'session')

    def set_time_picker_context(self, chat_id, context):
        self._get_user_session(chat_id)['picker_context'] = context

    async def get_time_range_display(self, chat_id):
        tr = self.get_time_range(chat_id)
        return format_time_range_display(tr)

    async def set_time_component(self, chat_id, side, field, value):
        tr = self.get_time_range(chat_id)
        key = f"{side}_{field}"
        tr[key] = int(value)
        self.set_time_range(chat_id, tr)

    async def set_time_field(self, chat_id, side, field, value):
        await self.set_time_component(chat_id, side, field, value)

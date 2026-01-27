"""
转发记录系统
记录所有转发操作的详细信息，方便追溯和分析
"""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import base64
from enum import Enum

from core.logging import get_logger

logger = get_logger(__name__)

class ForwardRecorder:
    """转发记录器"""
    
    def __init__(self, base_dir: str = "./zhuanfaji"):
        # 写入模式：full/summary/off
        self.mode = (os.getenv('FORWARD_RECORDER_MODE', 'summary') or 'summary').lower()
        
        # 允许通过环境变量覆写存储目录
        env_dir = os.getenv("FORWARD_RECORDER_DIR")
        base_dir = env_dir or base_dir

        self.base_dir = Path(base_dir).resolve()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"使用转发记录目录: {self.base_dir}")
        except Exception as e:
            logger.error(f"无法创建目录 {self.base_dir}: {e}")
            # 回退到项目根目录
            fallback_local = Path.cwd() / "zhuanfaji"
            try:
                fallback_local.mkdir(parents=True, exist_ok=True)
                logger.warning(f"目录不可写 {self.base_dir}，回退到 {fallback_local}")
                self.base_dir = fallback_local
            except Exception as e2:
                logger.error(f"回退目录 {fallback_local} 也无法创建: {e2}")
                self.base_dir = Path("data") / "zhuanfaji"
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.warning(f"最终回退到: {self.base_dir}")

        # 最终路径可写性检查
        if not self._is_writable(self.base_dir):
            fallback = Path.cwd() / "zhuanfaji"
            logger.warning(f"目录不可写 {self.base_dir}，再次回退到 {fallback}")
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                if self._is_writable(fallback):
                    self.base_dir = fallback
                else:
                    logger.error(f"回退目录 {fallback} 仍然不可写")
            except Exception as e:
                logger.error(f"创建回退目录 {fallback} 失败: {e}")
        
        # 创建子目录
        self.dirs = {
            'daily': self.base_dir / 'daily',           # 按日期分类
            'rules': self.base_dir / 'rules',           # 按规则分类  
            'chats': self.base_dir / 'chats',           # 按聊天分类
            'types': self.base_dir / 'types',           # 按消息类型分类
            'users': self.base_dir / 'users',           # 按用户分类
            'summary': self.base_dir / 'summary',       # 统计汇总
        }
        
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"ForwardRecorder 初始化完成，模式: {self.mode}")

    def _is_writable(self, directory: Path) -> bool:
        try:
            # 写入模式快速短路
            if self.mode == 'off':
                return True
            directory.mkdir(parents=True, exist_ok=True)
            test_file = directory / ".__wtest__"
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("ok")
            test_file.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.warning(f"目录 {directory} 不可写: {e}")
            return False
    
    async def record_forward(self, 
                           message_obj,                    # Telegram消息对象
                           source_chat_id: int,            # 源聊天ID
                           target_chat_id: int,            # 目标聊天ID  
                           rule_id: Optional[int] = None,  # 规则ID
                           forward_type: str = "auto",     # 转发类型: auto/manual/history
                           operator_id: Optional[int] = None, # 操作者ID
                           session_id: Optional[str] = None,  # 会话ID
                           additional_info: Optional[Dict] = None) -> str:
        """
        记录转发操作
        返回记录ID
        """
        logger.debug(f"record_forward called with mode: {self.mode}")
        try:
            if self.mode == 'off':
                return ""
            
            # 生成记录ID
            timestamp = datetime.now(timezone.utc)
            record_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{message_obj.id}_{target_chat_id}"
            
            # 提取消息详细信息
            message_info = await self._extract_message_info(message_obj)
            
            # 构建完整记录
            record = {
                'record_id': record_id,
                'timestamp': timestamp.isoformat(),
                'forward_info': {
                    'type': forward_type,
                    'rule_id': rule_id,
                    'operator_id': operator_id,
                    'session_id': session_id,
                },
                'message_info': message_info,
                'chat_info': {
                    'source_chat_id': source_chat_id,
                    'target_chat_id': target_chat_id,
                },
                'additional_info': additional_info or {},
                'version': '1.0'
            }
            
            if self.mode == 'full':
                await self._save_record(record, timestamp)
                await self._update_statistics(record, timestamp)
            elif self.mode == 'summary':
                # 仅做统计汇总
                await self._update_statistics(record, timestamp)
            
            logger.info(f"转发记录已保存: {record_id}")
            return record_id
            
        except Exception as e:
            logger.error(f"保存转发记录失败: {e}", exc_info=True)
            return ""

    async def record_forward_batch(self,
                                   messages: List[Any],
                                   source_chat_id: int,
                                   target_chat_id: int,
                                   rule_id: Optional[int] = None,
                                   forward_type: str = "auto",
                                   operator_id: Optional[int] = None,
                                   session_id: Optional[str] = None,
                                   additional_info: Optional[Dict] = None,
                                   summary_only: bool = True) -> int:
        """批量记录转发，降低IOPS。
        返回成功记录的条数。
        """
        try:
            if self.mode == 'off':
                return 0
            
            timestamp = datetime.now(timezone.utc)
            count = 0
            
            for msg in messages:
                try:
                    message_info = await self._extract_message_info(msg)
                    record = {
                        'record_id': f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{getattr(msg, 'id', 0)}_{target_chat_id}",
                        'timestamp': timestamp.isoformat(),
                        'forward_info': {
                            'type': forward_type,
                            'rule_id': rule_id,
                            'operator_id': operator_id,
                            'session_id': session_id,
                        },
                        'message_info': message_info,
                        'chat_info': {
                            'source_chat_id': source_chat_id,
                            'target_chat_id': target_chat_id,
                        },
                        'additional_info': additional_info or {},
                        'version': '1.0'
                    }
                    
                    if summary_only or self.mode == 'summary':
                        await self._update_statistics(record, timestamp)
                    else:
                        await self._save_record(record, timestamp)
                        await self._update_statistics(record, timestamp)
                    count += 1
                except Exception as e:
                    logger.debug(f"Failed to record batch item: {e}")
                    continue
            return count
        except Exception as e:
            logger.error(f"批量记录转发失败: {e}")
            return 0
    
    async def _extract_message_info(self, msg) -> Dict[str, Any]:
        """提取消息详细信息"""
        info = {
            'message_id': getattr(msg, 'id', 0),
            'date': getattr(msg, 'date', datetime.now()).isoformat() if hasattr(msg, 'date') else None,
            'text': getattr(msg, 'message', '')[:500],  # 限制文本长度
            'type': 'text',  # 默认类型
            'size_bytes': 0,
            'duration_seconds': 0,
            'file_info': {},
            'sender_info': {},
            'reply_info': {},
            'forward_info': {},
        }
        
        # 发送者信息
        if hasattr(msg, 'sender') and msg.sender:
            info['sender_info'] = {
                'user_id': getattr(msg.sender, 'id', 0),
                'username': getattr(msg.sender, 'username', ''),
                'first_name': getattr(msg.sender, 'first_name', ''),
                'last_name': getattr(msg.sender, 'last_name', ''),
                'is_bot': getattr(msg.sender, 'bot', False),
            }
        
        # 回复信息
        if hasattr(msg, 'reply_to') and msg.reply_to:
            info['reply_info'] = {
                'reply_to_msg_id': getattr(msg.reply_to, 'reply_to_msg_id', 0),
            }
        
        # 转发信息
        if hasattr(msg, 'forward') and msg.forward:
            fwd = msg.forward
            info['forward_info'] = {
                'from_id': self._normalize_peer(getattr(fwd, 'from_id', 0)),
                'from_name': getattr(fwd, 'from_name', ''),
                'date': fwd.date.isoformat() if hasattr(fwd, 'date') and fwd.date else None,
                'channel_post': getattr(fwd, 'channel_post', 0),
            }
        
        # 媒体信息
        if hasattr(msg, 'media') and msg.media:
            await self._extract_media_info(msg, info)
        
        # 消息链接
        if hasattr(msg, 'chat') and hasattr(msg.chat, 'username') and msg.chat.username:
            info['message_link'] = f"https://t.me/{msg.chat.username}/{msg.id}"
        elif hasattr(msg, 'chat_id'):
            # 私有群组或频道的链接格式
            chat_id_str = str(msg.chat_id).replace('-100', '') if str(msg.chat_id).startswith('-100') else str(msg.chat_id)
            info['message_link'] = f"https://t.me/c/{chat_id_str}/{msg.id}"
        
        return info
    
    async def _extract_media_info(self, msg, info: Dict[str, Any]):
        """提取媒体信息"""
        try:
            media = msg.media
            
            # 照片
            if hasattr(media, 'photo'):
                info['type'] = 'photo'
                photo = media.photo
                if hasattr(photo, 'sizes') and photo.sizes:
                    largest = max(photo.sizes, key=lambda x: getattr(x, 'size', 0) if hasattr(x, 'size') else 0)
                    info['size_bytes'] = getattr(largest, 'size', 0)
                info['file_info'] = {
                    'width': getattr(photo, 'w', 0) if hasattr(photo, 'w') else 0,
                    'height': getattr(photo, 'h', 0) if hasattr(photo, 'h') else 0,
                }
            
            # 文档 (包括视频、音频、文件等)
            elif hasattr(media, 'document'):
                doc = media.document
                info['size_bytes'] = getattr(doc, 'size', 0)
                info['file_info'] = {
                    'file_name': getattr(doc, 'file_name', ''),
                    'mime_type': getattr(doc, 'mime_type', ''),
                }
                
                # 检查文档属性
                if hasattr(doc, 'attributes'):
                    for attr in doc.attributes:
                        attr_type = attr.__class__.__name__
                        
                        if attr_type == 'DocumentAttributeVideo':
                            info['type'] = 'video'
                            info['duration_seconds'] = getattr(attr, 'duration', 0)
                            info['file_info'].update({
                                'width': getattr(attr, 'w', 0),
                                'height': getattr(attr, 'h', 0),
                                'supports_streaming': getattr(attr, 'supports_streaming', False),
                            })
                        
                        elif attr_type == 'DocumentAttributeAudio':
                            info['type'] = 'audio'
                            info['duration_seconds'] = getattr(attr, 'duration', 0)
                            info['file_info'].update({
                                'title': getattr(attr, 'title', ''),
                                'performer': getattr(attr, 'performer', ''),
                                'voice': getattr(attr, 'voice', False),
                            })
                            if getattr(attr, 'voice', False):
                                info['type'] = 'voice'
                        
                        elif attr_type == 'DocumentAttributeAnimated':
                            info['type'] = 'gif'
                        
                        elif attr_type == 'DocumentAttributeSticker':
                            info['type'] = 'sticker'
                            info['file_info'].update({
                                'alt': getattr(attr, 'alt', ''),
                            })
                        
                        elif attr_type == 'DocumentAttributeFilename':
                            info['file_info']['file_name'] = getattr(attr, 'file_name', '')
                
                # 如果没有特殊类型，归类为文档
                if info['type'] == 'text':
                    info['type'] = 'document'
            
            # 其他媒体类型
            elif hasattr(media, 'geo'):
                info['type'] = 'location'
                geo = media.geo
                info['file_info'] = {
                    'latitude': getattr(geo, 'lat', 0),
                    'longitude': getattr(geo, 'long', 0),
                }
            
            elif hasattr(media, 'contact'):
                info['type'] = 'contact'
                contact = media.contact
                info['file_info'] = {
                    'phone_number': getattr(contact, 'phone_number', ''),
                    'first_name': getattr(contact, 'first_name', ''),
                    'last_name': getattr(contact, 'last_name', ''),
                }
            
            elif hasattr(media, 'poll'):
                info['type'] = 'poll'
                poll = media.poll
                info['file_info'] = {
                    'question': getattr(poll, 'question', ''),
                    'total_voters': getattr(poll, 'total_voters', 0),
                    'closed': getattr(poll, 'closed', False),
                }
        
        except Exception as e:
            logger.debug(f"提取媒体信息失败: {e}")
    
    async def _save_record(self, record: Dict[str, Any], timestamp: datetime):
        """保存记录到多个分类目录"""
        record_json = json.dumps(record, ensure_ascii=False, indent=2, default=self._json_default)
        record_id = record['record_id']
        
        # 按日期保存
        daily_file = self.dirs['daily'] / f"{timestamp.strftime('%Y-%m-%d')}.jsonl"
        await self._append_to_file(daily_file, record_json)
        
        # 按规则保存
        if record['forward_info']['rule_id']:
            rule_file = self.dirs['rules'] / f"rule_{record['forward_info']['rule_id']}.jsonl"
            await self._append_to_file(rule_file, record_json)
        
        # 按聊天保存
        target_chat = record['chat_info']['target_chat_id']
        chat_file = self.dirs['chats'] / f"chat_{target_chat}.jsonl"
        await self._append_to_file(chat_file, record_json)
        
        # 按类型保存
        msg_type = record['message_info']['type']
        type_file = self.dirs['types'] / f"{msg_type}.jsonl"
        await self._append_to_file(type_file, record_json)
        
        # 按用户保存
        if record['message_info']['sender_info'].get('user_id'):
            user_id = record['message_info']['sender_info']['user_id']
            user_file = self.dirs['users'] / f"user_{user_id}.jsonl"
            await self._append_to_file(user_file, record_json)

    def _json_default(self, o: Any):
        if isinstance(o, (datetime,)):
            return o.isoformat()
        if isinstance(o, (Path,)):
            return str(o)
        if isinstance(o, bytes):
            try:
                return o.decode('utf-8', 'replace')
            except Exception as e:
                logger.debug(f"JSON base64 fallback failed: {e}")
                return base64.b64encode(o).decode('ascii')
        if isinstance(o, set):
            return list(o)
        if isinstance(o, Enum):
            return getattr(o, 'value', str(o))
        if hasattr(o, 'dict') and callable(getattr(o, 'dict')):
            try:
                return o.dict()
            except Exception:
                pass
        if hasattr(o, '__dict__'):
            try:
                return o.__dict__
            except Exception:
                pass
        return repr(o)

    def _normalize_peer(self, peer: Any):
        if isinstance(peer, (int, str)) or peer is None:
            return peer
        if hasattr(peer, 'channel_id'):
            return {'type': 'channel', 'id': getattr(peer, 'channel_id', None)}
        if hasattr(peer, 'user_id'):
            return {'type': 'user', 'id': getattr(peer, 'user_id', None)}
        if hasattr(peer, 'chat_id'):
            return {'type': 'chat', 'id': getattr(peer, 'chat_id', None)}
        return repr(peer)
    
    async def _append_to_file(self, file_path: Path, content: str):
        """异步追加内容到文件"""
        try:
            def write_file():
                # 确保父目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(content + '\n')
            
            # 在线程池中执行文件写入
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, write_file)
        except Exception as e:
            logger.error(f"写入文件失败 {file_path}: {e}")
    
    async def _update_statistics(self, record: Dict[str, Any], timestamp: datetime):
        """更新统计信息"""
        try:
            stats_file = self.dirs['summary'] / f"{timestamp.strftime('%Y-%m')}_stats.json"
            
            # 读取现有统计
            stats = {}
            if stats_file.exists():
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        stats = json.load(f)
                except Exception as e:
                    logger.debug(f"Failed to read stats file: {e}")
                    stats = {}
            
            # 更新统计
            date_key = timestamp.strftime('%Y-%m-%d')
            if date_key not in stats:
                stats[date_key] = {
                    'total_forwards': 0,
                    'types': {},
                    'rules': {},
                    'chats': {},
                    'users': {},
                    'total_size_bytes': 0,
                    'total_duration_seconds': 0,
                }
            
            day_stats = stats[date_key]
            day_stats['total_forwards'] += 1
            
            # 按类型统计
            msg_type = record['message_info']['type']
            day_stats['types'][msg_type] = day_stats['types'].get(msg_type, 0) + 1
            
            # 按规则统计
            rule_id = record['forward_info'].get('rule_id')
            if rule_id:
                day_stats['rules'][str(rule_id)] = day_stats['rules'].get(str(rule_id), 0) + 1
            
            # 按聊天统计
            target_chat = str(record['chat_info']['target_chat_id'])
            day_stats['chats'][target_chat] = day_stats['chats'].get(target_chat, 0) + 1
            
            # 按用户统计
            user_id = record['message_info']['sender_info'].get('user_id')
            if user_id:
                day_stats['users'][str(user_id)] = day_stats['users'].get(str(user_id), 0) + 1
            
            # 大小和时长统计
            day_stats['total_size_bytes'] += record['message_info'].get('size_bytes', 0)
            day_stats['total_duration_seconds'] += record['message_info'].get('duration_seconds', 0)
            
            # 保存统计
            def write_stats():
                # 原子写入以避免并发/崩溃导致的部分写入
                stats_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = stats_file.with_suffix('.json.tmp')
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, stats_file)
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, write_stats)
            
        except Exception as e:
            logger.error(f"更新统计失败: {e}", exc_info=True)
    
    async def get_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """获取日期统计摘要"""
        if not date:
            local_date = datetime.now().strftime('%Y-%m-%d')
            utc_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        else:
            local_date = date
            utc_date = date
        try:
            lm = local_date[:7]
            lf = self.dirs['summary'] / f"{lm}_stats.json"
            stats = {}
            if lf.exists():
                with open(lf, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            result = stats.get(local_date, {'date': local_date, 'total_forwards': 0})
            if int(result.get('total_forwards', 0)) == 0 and utc_date != local_date:
                um = utc_date[:7]
                uf = self.dirs['summary'] / f"{um}_stats.json"
                if uf.exists():
                    with open(uf, 'r', encoding='utf-8') as f:
                        ustats = json.load(f)
                    ures = ustats.get(utc_date, {'date': utc_date, 'total_forwards': 0})
                    if int(ures.get('total_forwards', 0)) > 0:
                        logger.info(f"本地日期 {local_date} 无数据，使用UTC日期 {utc_date} 的统计")
                        return ures
            logger.debug(f"获取到 {local_date} 的统计数据: {result}")
            return result
        except Exception as e:
            logger.error(f"获取日统计失败: {e}")
            return {'date': local_date, 'total_forwards': 0, 'error': str(e)}

    async def get_hourly_distribution(self, date: str | None = None) -> Dict[str, int]:
        """获取指定日期内按小时的转发分布统计"""
        try:
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')

            # 初始化 24 小时桶
            hourly_counts: Dict[str, int] = {f"{h:02d}": 0 for h in range(24)}

            # 读取当日日志记录（jsonl）
            daily_file = self.dirs['daily'] / f"{date}.jsonl"
            
            if daily_file.exists():
                records = await self._read_jsonl_file(daily_file, limit=200000)
                for rec in records:
                    ts = rec.get('timestamp') or rec.get('message_info', {}).get('date')
                    if not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        hour_key = f"{dt.hour:02d}"
                        if hour_key in hourly_counts:
                            hourly_counts[hour_key] += 1
                    except Exception as e:
                        logger.debug(f"Failed to parse timestamp in distribusi: {e}")
                        continue
            
            return hourly_counts
            
        except Exception as e:
            logger.error(f"获取小时分布失败: {e}")
            return {f"{h:02d}": 0 for h in range(24)}
    
    async def search_records(self, 
                           start_date: str = None,
                           end_date: str = None, 
                           chat_id: int = None,
                           user_id: int = None,
                           message_type: str = None,
                           rule_id: int = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """搜索转发记录"""
        records = []
        
        try:
            # 确定搜索范围
            if chat_id:
                search_file = self.dirs['chats'] / f"chat_{chat_id}.jsonl"
                if search_file.exists():
                    records.extend(await self._read_jsonl_file(search_file, limit))
            
            elif user_id:
                search_file = self.dirs['users'] / f"user_{user_id}.jsonl"
                if search_file.exists():
                    records.extend(await self._read_jsonl_file(search_file, limit))
            
            elif message_type:
                search_file = self.dirs['types'] / f"{message_type}.jsonl"
                if search_file.exists():
                    records.extend(await self._read_jsonl_file(search_file, limit))
            
            elif rule_id:
                search_file = self.dirs['rules'] / f"rule_{rule_id}.jsonl"
                if search_file.exists():
                    records.extend(await self._read_jsonl_file(search_file, limit))
            
            else:
                # 按日期范围搜索
                if not start_date:
                    start_date = datetime.now().strftime('%Y-%m-%d')
                if not end_date:
                    end_date = start_date
                
                current_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                
                while current_date <= end_dt and len(records) < limit:
                    date_str = current_date.strftime('%Y-%m-%d')
                    daily_file = self.dirs['daily'] / f"{date_str}.jsonl"
                    if daily_file.exists():
                        day_records = await self._read_jsonl_file(daily_file, limit - len(records))
                        records.extend(day_records)
                    current_date += timedelta(days=1)
            
            # 排序和限制
            records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return records[:limit]
            
        except Exception as e:
            logger.error(f"搜索记录失败: {e}")
            return []
    
    async def _read_jsonl_file(self, file_path: Path, limit: int = 100) -> List[Dict[str, Any]]:
        """读取JSONL文件"""
        records = []
        try:
            def read_file():
                nonlocal records
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if len(records) >= limit:
                            break
                        try:
                            record = json.loads(line.strip())
                            records.append(record)
                        except json.JSONDecodeError:
                            continue
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, read_file)
            
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
        
        return records

# 全局记录器实例
forward_recorder = ForwardRecorder()

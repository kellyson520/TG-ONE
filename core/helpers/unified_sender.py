
import logging
from typing import Union, List, Optional, Any
# from services.queue_service import send_message_queued, send_file_queued

logger = logging.getLogger(__name__)

class UnifiedSender:
    """
    Unified Sender Interface to handle text and media sending transparently.
    Abstracts differences between send_message and send_file.
    Now integrated with Rate Limit Protection.
    """
    def __init__(self, client):
        self.client = client

    async def send(self, 
                  target_id: int, 
                  text: Optional[str] = None, 
                  media: Union[Any, List[Any]] = None, 
                  **kwargs):
        """
        Send content to target_id with Rate Limiting protection.
        
        Args:
            target_id: Destination Chat ID
            text: Text content (used as message body or media caption)
            media: Media object or list of media objects (for albums)
            **kwargs: Additional arguments (reply_to, buttons, message_thread_id, etc.)
        """
        try:
            send_kwargs = self._prepare_kwargs(kwargs)
            
            # Case 1: Media (Single or Album)
            if media:
                await self._send_media(target_id, media, text, send_kwargs)
            # Case 2: Text Only
            else:
                await self._send_text(target_id, text, send_kwargs)

        except Exception as e:
            logger.error(f"UnifiedSender Error sending to {target_id}: {e}")
            raise e

    def _prepare_kwargs(self, kwargs: dict) -> dict:
        """Filter and prepare safe kwargs for Telethon."""
        valid_keys = [
            'reply_to', 'buttons', 'message_thread_id', 
            'parse_mode', 'link_preview', 'formatting_entities', 
            'schedule', 'silent', 'background'
        ]
        return {k: v for k, v in kwargs.items() if k in valid_keys and v is not None}

    async def _send_media(self, target_id: int, media: Union[Any, List[Any]], text: Optional[str], kwargs: dict):
        """Handle media sending with rate limit."""
        # Use text as caption, pass explicitly to queued function
        caption = text
            
        # Check for Album
        if isinstance(media, list) and len(media) > 0:
            # Telethon albums cannot have buttons attached to the media group itself usually.
            # We must detach buttons.
            buttons = kwargs.pop('buttons', None)
            
            # Send Album
            mod = __import__('services.queue_service', fromlist=['send_file_queued'])
            await mod.send_file_queued(
                self.client,
                target_id,
                media,
                caption=caption,
                extra_keywords={'type': 'album'},
                **kwargs
            )
            
            # Send detached buttons if present
            if buttons:
                send_kwargs = {
                    'reply_to': kwargs.get('reply_to'),
                    'message_thread_id': kwargs.get('message_thread_id'),
                    'buttons': buttons
                }
                mod = __import__('services.queue_service', fromlist=['send_message_queued'])
                await mod.send_message_queued(
                    self.client,
                    target_id,
                    "👇 互动按钮",
                    extra_keywords={'type': 'detached_buttons'},
                    **send_kwargs
                )
        else:
            # Single Media
            mod = __import__('services.queue_service', fromlist=['send_file_queued'])
            await mod.send_file_queued(
                self.client, 
                target_id, 
                media, 
                caption=caption,
                extra_keywords={'type': 'media'},
                **kwargs
            )

    async def _send_text(self, target_id: int, text: Optional[str], kwargs: dict):
        """Handle text sending with rate limit."""
        if not text:
            # Empty text fallback
            if kwargs.get('buttons'):
                text = "👇"
            else:
                logger.warning(f"UnifiedSender: Ignored empty text send request to {target_id}")
                return

        mod = __import__('services.queue_service', fromlist=['send_message_queued'])
        await mod.send_message_queued(
            self.client,
            target_id,
            text,
            extra_keywords={'type': 'text'},
            **kwargs
        )

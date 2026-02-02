
import sys
import os
import asyncio
from telethon import TelegramClient, errors
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

class SessionWizard:
    """会话向导：负责首次启动时的环境检查、会话生成与交互式引导"""
    
    def __init__(self):
        self.session_dir = settings.SESSION_DIR
        self.user_session_path = self.session_dir / "user"
        self.bot_session_path = self.session_dir / "bot"
        
        # 确保目录存在
        os.makedirs(self.session_dir, exist_ok=True)

    async def ensure_session(self):
        """
        核心入口：检查会话并在需要时启动引导
        """
        # 1. 检查环境变量完整性
        if not self._check_env():
            return False

        # 2. 检查用户会话是否存在
        if self._session_exists("user"):
            logger.info("✅ 检测到用户会话文件，准备启动系统...")
            # 可以在这里做一个简单的连通性测试 (可选)
            return True

        # 3. 如果会话不存在，检查是否为交互式环境
        if not sys.stdin.isatty():
            logger.warning(
                "⚠️ [SessionWizard] 未找到用户会话文件 (user.session)，且当前不在交互式终端中。"
            )
            print("\n" + "!"*60)
            print("🛑 首次启动需生成 Session 文件 (Telegram 登录认证)")
            print("!"*60)
            print("\n检测到您正在非交互式环境 (如后台服务/Docker Compose) 运行，")
            print("无法进行手机号验证码输入。请按以下步骤手动生成 Session：\n")
            
            print("🛠️  Docker 用户操作指南:")
            print("1. 保持当前容器运行，打开一个新的终端窗口")
            print("2. 执行以下命令进入容器交互模式:")
            print("   docker exec -it tg_one_app python -m core.session_wizard")
            print("   (注: 将 'tg_one_app' 替换为您的实际容器名称)")
            print("\n3. 按提示输入手机号和验证码完成登录")
            print("4. 登录成功后重启容器即可生效: docker restart tg_one_app\n")
            
            print("🛠️  常规部署用户:")
            print("请在前台直接运行一次: python main.py\n")
            print("!"*60 + "\n")
            
            # 非交互模式下无法生成 session，让后续流程尝试自动处理或报错
            return True 
            
        # 4. 启动交互式向导
        print("\n" + "="*60)
        print("🚀 TG ONE 系统首次启动引导")
        print("="*60)
        print("检测到您是第一次运行 (或 Session 文件已丢失)。")
        print("系统将引导您完成 Telegram 登录配置。\n")
        
        success = await self._interactive_login()
        if success:
            print("\n✅ 配置完成！正在启动系统...\n")
            await asyncio.sleep(1) # 给用户一点反应时间
        return success

    def _check_env(self) -> bool:
        """检查必要的环境变量"""
        missing = []
        if not settings.API_ID: missing.append("API_ID")
        if not settings.API_HASH: missing.append("API_HASH")
        if not settings.PHONE_NUMBER: missing.append("PHONE_NUMBER")
        
        if missing:
            logger.critical(f"❌ 缺少必要配置，无法启动向导: {', '.join(missing)}")
            print(f"\n❌ 错误: .env 文件配置不完整。缺少: {', '.join(missing)}")
            print("请先编辑 .env 文件完善配置。\n")
            return False
        return True

    def _session_exists(self, name: str) -> bool:
        """检查特定会话文件是否存在"""
        # Telethon 默认在路径后加 .session
        return (self.session_dir / f"{name}.session").exists()

    async def _interactive_login(self) -> bool:
        """执行交互式登录流程"""
        print(f"📱 目标手机号: {settings.PHONE_NUMBER} (来自 .env)")
        print("正在连接 Telegram 服务器...\n")

        # 使用临时客户端进行验证，生成的 session 文件将被主程序复用
        temp_client = TelegramClient(
            str(self.user_session_path),
            settings.API_ID,
            settings.API_HASH
        )

        try:
            await temp_client.connect()
            
            # 检查是否已经授权 (有可能文件存在但逻辑判断失误，或者复用了旧文件)
            if not await temp_client.is_user_authorized():
                # 发送验证码
                try:
                    await temp_client.send_code_request(settings.PHONE_NUMBER)
                    print("📩 验证码已发送到您的 Telegram 客户端 (非短信)。")
                except errors.FloodWaitError as e:
                    print(f"\n❌ 触发了 Telegram 频率限制 (FloodWait)。")
                    print(f"请等待 {e.seconds} 秒 ({e.seconds // 60} 分钟) 后再试。")
                    return False
                except errors.PhoneNumberInvalidError:
                    print(f"\n❌ 手机号格式无效: {settings.PHONE_NUMBER}")
                    print("请检查 .env 文件中的 PHONE_NUMBER 格式 (应为 +86138...)")
                    return False
                except Exception as e:
                    print(f"\n❌ 连接或发送验证码失败: {e}")
                    return False

                # 输入验证码循环
                while True:
                    code = input("👉 请输入验证码: ").strip()
                    if not code:
                        continue
                        
                    try:
                        await temp_client.sign_in(settings.PHONE_NUMBER, code)
                        break # 登录成功
                    except errors.SessionPasswordNeededError:
                        print("\n🔐 检测到两步验证 (2FA)。")
                        password = input("👉 请输入您的 2FA 云密码: ").strip()
                        try:
                            await temp_client.sign_in(password=password)
                            break
                        except errors.PasswordHashInvalidError:
                            print("❌ 密码错误，请重试。")
                    except errors.PhoneCodeInvalidError:
                        print("❌ 验证码错误，请重试。")
                    except errors.PhoneCodeExpiredError:
                        print("❌ 验证码已过期，请重新启动程序。")
                        return False

            # 获取用户信息确认登录成功
            me = await temp_client.get_me()
            print(f"\n✅ 用户验证成功: {me.first_name} (@{me.username}) ID: {me.id}")
            
            # 可选: 验证 Bot Token (如果配置了)
            if settings.BOT_TOKEN:
                print("\nchecking Bot configuration...")
                await self._verify_bot()
                
            return True

        except Exception as e:
            logger.error(f"登录引导过程中发生致命错误: {e}", exc_info=True)
            print(f"\n❌ 发生未知错误: {e}")
            return False
        finally:
            await temp_client.disconnect()

    async def _verify_bot(self):
        """验证 Bot Token 有效性"""
        bot_client = TelegramClient(
            str(self.bot_session_path),
            settings.API_ID,
            settings.API_HASH
        )
        try:
            await bot_client.start(bot_token=settings.BOT_TOKEN)
            bot_me = await bot_client.get_me()
            print(f"✅ Bot 验证成功: {bot_me.first_name} (@{bot_me.username})")
        except Exception as e:
            print(f"⚠️ Bot 验证失败 (可能是 Token 错误): {e}")
            print("系统仍可启动，但 Bot 功能将不可用。")
        finally:
            await bot_client.disconnect()


session_wizard = SessionWizard()

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(session_wizard.ensure_session())
    except KeyboardInterrupt:
        print("\n🚫 操作已取消")
    except Exception as e:
        print(f"\n❌ 发生未知错误: {e}")

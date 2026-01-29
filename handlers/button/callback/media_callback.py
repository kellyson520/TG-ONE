import traceback

import logging
from sqlalchemy import select

from models.models import (
    AsyncSessionManager,
    ForwardRule,
    RuleSync,
)
from repositories.db_context import async_db_session
from core.helpers.common import get_db_ops
from handlers.button.settings_manager import get_media_settings_text

from handlers.button.button_helpers import (
    create_media_extensions_buttons,
    create_media_settings_buttons,
    create_media_size_buttons,
    create_media_types_buttons,
)

logger = logging.getLogger(__name__)


async def handle_media_callback(event):
    """处理媒体设置相关回调 (异步版)"""
    data = event.data.decode("utf-8")
    parts = data.split(":")
    action = parts[0]

    # 解析 rule_id
    rule_id = None
    if ":" in data:
        rule_id = parts[1]  # 获取第一个:后面的内容作为rule_id

    # 使用 AsyncSessionManager 获取会话
    async with AsyncSessionManager() as session:
        message = await event.get_message()
        # 获取对应的处理器
        handler = {
            "media_settings": callback_media_settings,
            "set_max_media_size": callback_set_max_media_size,
            "select_max_media_size": callback_select_max_media_size,
            "set_media_types": callback_set_media_types,
            "toggle_media_type": callback_toggle_media_type,
            "set_media_extensions": callback_set_media_extensions,
            "media_extensions_page": callback_media_extensions_page,
            "toggle_media_extension": callback_toggle_media_extension,
            "toggle_media_allow_text": callback_toggle_media_allow_text,
        }.get(action)

        if handler:
            await handler(event, rule_id, session, message, data)


async def _show_rule_media_settings(event, rule_id):
    """显示单规则媒体设置菜单"""
    from telethon import Button

    async with async_db_session() as session:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            await event.answer("规则不存在", alert=True)
            return

        # 构建文本
        text = f"🎬 **媒体设置** (规则 {rule_id})\n配置该规则的媒体过滤选项。"

        # 构建按钮
        buttons = [
            [
                Button.inline(
                    f"类型过滤: {'开启' if rule.enable_media_type_filter else '关闭'}",
                    f"toggle_enable_media_type_filter:{rule_id}",
                )
            ],
            [
                Button.inline(
                    f"大小过滤: {'开启' if rule.enable_media_size_filter else '关闭'}",
                    f"toggle_enable_media_size_filter:{rule_id}",
                )
            ],
            [
                Button.inline(
                    f"扩展名过滤: {'开启' if rule.enable_extension_filter else '关闭'}",
                    f"toggle_enable_media_extension_filter:{rule_id}",
                )
            ],
            [Button.inline("👈 返回规则设置", f"rule_settings:{rule_id}")],
        ]

        await event.edit(text, buttons=buttons, parse_mode="markdown")


async def callback_media_settings(event, rule_id, session, message, data):
    # 显示媒体设置页面
    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if rule:
            await event.edit(
                await get_media_settings_text(),
                buttons=await create_media_settings_buttons(rule),
            )
    finally:
        await session.close()
    return


async def callback_set_max_media_size(event, rule_id, session, message, data):
    await event.edit(
        "请选择最大媒体大小(MB)：",
        buttons=await create_media_size_buttons(rule_id, page=0),
    )
    return


async def callback_select_max_media_size(event, rule_id, session, message, data):
    parts = data.split(":", 2)  # 最多分割2次
    if len(parts) == 3:
        _, rule_id, size = parts
        logger.info(f"设置规则 {rule_id} 的最大媒体大小为: {size}")
        try:
            rule = await session.get(ForwardRule, int(rule_id))
            if rule:
                # 记录旧大小
                old_size = rule.max_media_size

                # 更新最大媒体大小
                rule.max_media_size = int(size)
                await session.commit()
                logger.info(f"数据库更新成功: {old_size} -> {size}")

                # 检查是否启用了同步功能
                if rule.enable_sync:
                    logger.info(
                        f"规则 {rule.id} 启用了同步功能，正在同步媒体大小设置到关联规则"
                    )
                    # 获取需要同步的规则列表
                    sync_rules = (
                        session.query(RuleSync)
                        .filter(RuleSync.rule_id == rule.id)
                        .all()
                    )

                    # 为每个同步规则应用相同的媒体大小设置
                    for sync_rule in sync_rules:
                        sync_rule_id = sync_rule.sync_rule_id
                        logger.info(f"正在同步媒体大小到规则 {sync_rule_id}")

                        # 获取同步目标规则
                        target_rule = session.query(ForwardRule).get(sync_rule_id)
                        if not target_rule:
                            logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                            continue

                        # 更新同步目标规则的媒体大小设置
                        try:
                            # 记录旧大小
                            old_target_size = target_rule.max_media_size

                            # 设置新大小
                            target_rule.max_media_size = int(size)

                            logger.info(
                                f"同步规则 {sync_rule_id} 的媒体大小从 {old_target_size} 到 {size}"
                            )
                        except Exception as e:
                            logger.error(
                                f"同步媒体大小到规则 {sync_rule_id} 时出错: {str(e)}"
                            )
                            continue

                    # 提交所有同步更改
                    await session.commit()
                    logger.info("所有同步媒体大小更改已提交")

                # 获取消息对象
                message = await event.get_message()

                await event.edit(
                    "媒体设置：", buttons=await create_media_settings_buttons(rule)
                )
                await event.answer(f"已设置最大媒体大小为: {size}MB")
                logger.info("界面更新完成")
        except Exception as e:
            logger.error(f"设置最大媒体大小时出错: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
        finally:
            await session.close()
    return


async def callback_set_media_types(event, rule_id, session, message, data):
    """处理查看并设置媒体类型的回调"""
    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 获取或创建媒体类型设置
        db_ops = await get_db_ops()
        success, msg, media_types = await db_ops.get_media_types(session, rule.id)

        if not success:
            await event.answer(f"获取媒体类型设置失败: {msg}")
            return

        # 显示媒体类型选择界面
        await event.edit(
            "请选择要屏蔽的媒体类型",
            buttons=await create_media_types_buttons(rule.id, media_types),
        )

    except Exception as e:
        logger.error(f"设置媒体类型时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"设置媒体类型时出错: {str(e)}")
    finally:
        await session.close()
    return


async def callback_toggle_media_type(event, rule_id, session, message, data):
    """处理切换媒体类型的回调"""
    try:
        # 正确解析数据获取rule_id和媒体类型
        parts = data.split(":")
        if len(parts) < 3:
            await event.answer("数据格式错误")
            return

        # toggle_media_type:31:voice
        action = parts[0]
        rule_id = parts[1]
        media_type = parts[2]
        # 检查媒体类型是否有效
        if media_type not in ["photo", "document", "video", "audio", "voice"]:
            await event.answer(f"无效的媒体类型: {media_type}")
            return

        # 获取规则
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 切换媒体类型状态
        db_ops = await get_db_ops()
        success, msg = await db_ops.toggle_media_type(session, rule.id, media_type)

        if not success:
            await event.answer(f"切换媒体类型失败: {msg}")
            return

        # 检查是否启用了同步功能
        if rule.enable_sync:
            logger.info(
                f"规则 {rule.id} 启用了同步功能，正在同步媒体类型设置到关联规则"
            )

            # 获取该规则的当前媒体类型状态
            success, _, current_media_types = await db_ops.get_media_types(
                session, rule.id
            )
            if not success:
                logger.warning(f"获取媒体类型设置失败，无法同步")
            else:
                # 获取需要同步的规则列表
                sync_rules = (
                    session.query(RuleSync).filter(RuleSync.rule_id == rule.id).all()
                )

                # 为每个同步规则应用相同的媒体类型设置
                for sync_rule in sync_rules:
                    sync_rule_id = sync_rule.sync_rule_id
                    logger.info(f"正在同步媒体类型 {media_type} 到规则 {sync_rule_id}")

                    # 获取同步目标规则
                    target_rule = session.query(ForwardRule).get(sync_rule_id)
                    if not target_rule:
                        logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                        continue

                    # 更新同步目标规则的媒体类型设置
                    try:
                        # 获取目标规则当前媒体类型设置
                        target_success, _, target_media_types = (
                            await db_ops.get_media_types(session, sync_rule_id)
                        )
                        if not target_success:
                            logger.warning(
                                f"获取目标规则 {sync_rule_id} 的媒体类型设置失败，跳过"
                            )
                            continue

                        # 获取当前类型的新状态
                        current_type_status = getattr(current_media_types, media_type)

                        # 如果目标媒体类型状态与主规则不同，则进行更新
                        if (
                            getattr(target_media_types, media_type)
                            != current_type_status
                        ):
                            # 强制设置为与主规则相同的状态
                            if current_type_status:
                                # 当前主规则是开启状态，确保目标规则也开启
                                if not getattr(target_media_types, media_type):
                                    await db_ops.toggle_media_type(
                                        session, sync_rule_id, media_type
                                    )
                                    logger.info(
                                        f"同步规则 {sync_rule_id} 的媒体类型 {media_type} 已开启"
                                    )
                            else:
                                # 当前主规则是关闭状态，确保目标规则也关闭
                                if getattr(target_media_types, media_type):
                                    await db_ops.toggle_media_type(
                                        session, sync_rule_id, media_type
                                    )
                                    logger.info(
                                        f"同步规则 {sync_rule_id} 的媒体类型 {media_type} 已关闭"
                                    )
                        else:
                            logger.info(
                                f"目标规则 {sync_rule_id} 的媒体类型 {media_type} 状态已经是 {current_type_status}，无需更改"
                            )

                    except Exception as e:
                        logger.error(
                            f"同步媒体类型到规则 {sync_rule_id} 时出错: {str(e)}"
                        )
                        continue

        # 重新获取媒体类型设置
        success, _, media_types = await db_ops.get_media_types(session, rule.id)

        if not success:
            await event.answer("获取媒体类型设置失败")
            return

        # 更新界面
        await event.edit(
            "请选择要屏蔽的媒体类型",
            buttons=await create_media_types_buttons(rule.id, media_types),
        )
        await event.answer(msg)

    except Exception as e:
        logger.error(f"切换媒体类型时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"切换媒体类型时出错: {str(e)}")
    finally:
        session.close()
    return


async def callback_set_media_extensions(event, rule_id, session, message, data):
    await event.edit(
        "请选择要过滤的媒体扩展名：",
        buttons=await create_media_extensions_buttons(rule_id, page=0),
    )
    return


async def callback_media_extensions_page(event, rule_id, session, message, data):
    _, rule_id, page = data.split(":")
    page = int(page)
    await event.edit(
        "请选择要过滤的媒体扩展名：",
        buttons=await create_media_extensions_buttons(rule_id, page=page),
    )
    return


async def callback_toggle_media_extension(event, rule_id, session, message, data):
    """处理切换媒体扩展名的回调"""
    try:
        # 解析数据获取rule_id和扩展名
        parts = data.split(":")
        if len(parts) < 3:
            await event.answer("数据格式错误")
            return

        # toggle_media_extension:31:jpg:0
        action = parts[0]
        rule_id = parts[1]
        extension = parts[2]

        # 获取当前页码，如果提供了页码
        current_page = 0
        if len(parts) > 3 and parts[3].isdigit():
            current_page = int(parts[3])

        # 获取规则
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 获取当前规则已选择的扩展名
        db_ops = await get_db_ops()
        selected_extensions = await db_ops.get_media_extensions(session, rule.id)
        selected_extension_list = [ext["extension"] for ext in selected_extensions]

        # 切换扩展名状态
        was_selected = extension in selected_extension_list
        if was_selected:
            # 如果已存在，则删除
            extension_id = next(
                (
                    ext["id"]
                    for ext in selected_extensions
                    if ext["extension"] == extension
                ),
                None,
            )
            if extension_id:
                success, msg = await db_ops.delete_media_extensions(
                    session, rule.id, [extension_id]
                )
                if success:
                    await event.answer(f"已移除扩展名: {extension}")

                    # 检查是否启用了同步功能
                    if rule.enable_sync:
                        logger.info(
                            f"规则 {rule.id} 启用了同步功能，正在同步媒体扩展名移除到关联规则"
                        )

                        # 获取需要同步的规则列表
                        sync_rules = (
                            session.query(RuleSync)
                            .filter(RuleSync.rule_id == rule.id)
                            .all()
                        )

                        # 为每个同步规则应用相同的媒体扩展名设置
                        for sync_rule in sync_rules:
                            sync_rule_id = sync_rule.sync_rule_id
                            logger.info(
                                f"正在同步移除媒体扩展名 {extension} 到规则 {sync_rule_id}"
                            )

                            # 获取同步目标规则
                            target_rule = session.query(ForwardRule).get(sync_rule_id)
                            if not target_rule:
                                logger.warning(
                                    f"同步目标规则 {sync_rule_id} 不存在，跳过"
                                )
                                continue

                            # 更新同步目标规则的媒体扩展名设置
                            try:
                                # 获取目标规则当前扩展名设置
                                target_extensions = await db_ops.get_media_extensions(
                                    session, sync_rule_id
                                )
                                target_extension_list = [
                                    ext["extension"] for ext in target_extensions
                                ]

                                # 如果目标规则中存在该扩展名，则删除
                                if extension in target_extension_list:
                                    target_extension_id = next(
                                        (
                                            ext["id"]
                                            for ext in target_extensions
                                            if ext["extension"] == extension
                                        ),
                                        None,
                                    )
                                    if target_extension_id:
                                        await db_ops.delete_media_extensions(
                                            session, sync_rule_id, [target_extension_id]
                                        )
                                        logger.info(
                                            f"同步规则 {sync_rule_id} 的媒体扩展名 {extension} 已移除"
                                        )
                                    else:
                                        logger.warning(
                                            f"目标规则 {sync_rule_id} 中找不到扩展名 {extension} 的ID"
                                        )
                                else:
                                    logger.info(
                                        f"目标规则 {sync_rule_id} 中不存在扩展名 {extension}，无需删除"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"同步移除媒体扩展名到规则 {sync_rule_id} 时出错: {str(e)}"
                                )
                                continue
                else:
                    await event.answer(f"移除扩展名失败: {msg}")
        else:
            # 如果不存在，则添加
            success, msg = await db_ops.add_media_extensions(
                session, rule.id, [extension]
            )
            if success:
                await event.answer(f"已添加扩展名: {extension}")

                # 检查是否启用了同步功能
                if rule.enable_sync:
                    logger.info(
                        f"规则 {rule.id} 启用了同步功能，正在同步媒体扩展名添加到关联规则"
                    )

                    # 获取需要同步的规则列表
                    result = await session.execute(
                        select(RuleSync).filter(RuleSync.rule_id == rule.id)
                    )
                    sync_rules = result.scalars().all()

                    # 为每个同步规则应用相同的媒体扩展名设置
                    for sync_rule in sync_rules:
                        sync_rule_id = sync_rule.sync_rule_id
                        logger.info(
                            f"正在同步添加媒体扩展名 {extension} 到规则 {sync_rule_id}"
                        )

                        # 获取同步目标规则
                        target_rule = await session.get(ForwardRule, sync_rule_id)
                        if not target_rule:
                            logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                            continue

                        # 更新同步目标规则的媒体扩展名设置
                        try:
                            # 获取目标规则当前扩展名设置
                            target_extensions = await db_ops.get_media_extensions(
                                session, sync_rule_id
                            )
                            target_extension_list = [
                                ext["extension"] for ext in target_extensions
                            ]

                            # 如果目标规则中不存在该扩展名，则添加
                            if extension not in target_extension_list:
                                await db_ops.add_media_extensions(
                                    session, sync_rule_id, [extension]
                                )
                                logger.info(
                                    f"同步规则 {sync_rule_id} 的媒体扩展名 {extension} 已添加"
                                )
                            else:
                                logger.info(
                                    f"目标规则 {sync_rule_id} 中已存在扩展名 {extension}，无需添加"
                                )
                        except Exception as e:
                            logger.error(
                                f"同步添加媒体扩展名到规则 {sync_rule_id} 时出错: {str(e)}"
                            )
                            continue
            else:
                await event.answer(f"添加扩展名失败: {msg}")

        # 更新界面，使用之前获取的页码
        await event.edit(
            "请选择要过滤的媒体扩展名：",
            buttons=await create_media_extensions_buttons(rule_id, page=current_page),
        )

    except Exception as e:
        logger.error(f"切换媒体扩展名时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"切换媒体扩展名时出错: {str(e)}")
    finally:
        session.close()
    return


async def callback_toggle_media_allow_text(event, rule_id, session, message, data):
    """处理切换放行文本的回调"""
    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 切换状态
        rule.media_allow_text = not rule.media_allow_text

        # 检查是否启用了同步功能
        if rule.enable_sync:
            logger.info(
                f"规则 {rule.id} 启用了同步功能，正在同步'放行文本'设置到关联规则"
            )

            # 获取需要同步的规则列表
            result = await session.execute(
                select(RuleSync).filter(RuleSync.rule_id == rule.id)
            )
            sync_rules = result.scalars().all()

            # 为每个同步规则应用相同的设置
            for sync_rule in sync_rules:
                sync_rule_id = sync_rule.sync_rule_id
                logger.info(f"正在同步'放行文本'设置到规则 {sync_rule_id}")

                # 获取同步目标规则
                target_rule = await session.get(ForwardRule, sync_rule_id)
                if not target_rule:
                    logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                    continue

                # 更新同步目标规则的设置
                try:
                    target_rule.media_allow_text = rule.media_allow_text
                    logger.info(
                        f"同步规则 {sync_rule_id} 的'放行文本'设置已更新为 {rule.media_allow_text}"
                    )
                except Exception as e:
                    logger.error(
                        f"同步'放行文本'设置到规则 {sync_rule_id} 时出错: {str(e)}"
                    )
                    continue

        # 提交更改
        await session.commit()

        # 更新界面
        await event.edit(
            await get_media_settings_text(),
            buttons=await create_media_settings_buttons(rule),
        )

        # 向用户显示结果
        status = "开启" if rule.media_allow_text else "关闭"
        await event.answer(f"已{status}放行文本")

    except Exception as e:
        await session.rollback()
        logger.error(f"切换放行文本设置时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"切换放行文本设置时出错: {str(e)}")
    finally:
        session.close()
    return

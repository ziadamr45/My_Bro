"""
WhatsApp Image Generation & Editing
=====================================
Image generation and editing functions for WhatsApp bot.

Extracted from whatsapp/media.py for modularity.
"""

import logging
import base64

from whatsapp.state import _contains_arabic

from whatsapp.api import (
    _send_whatsapp_message,
    _send_interactive_buttons,
    _send_whatsapp_image,
    ThinkingFeedback,
)

logger = logging.getLogger(__name__)

async def _translate_prompt_to_english(prompt: str, user_id: int = None) -> str:
    """Translate Arabic image description to English for image generation models"""
    if not _contains_arabic(prompt):
        return prompt  # Not Arabic — leave as is
    
    try:
        from provider_manager import call_ai
        
        translation_prompt = f"""Translate the following Arabic image description to English. This is for an AI image generation model, so make the translation descriptive and detailed for best image results. Only output the English translation, nothing else.

Arabic: {prompt}

English translation:"""
        
        system = "You are a translator. Translate Arabic image descriptions to English. Make the translation vivid and descriptive for image generation. Output ONLY the English text, no explanations."
        
        translated = await call_ai(
            translation_prompt,
            system_prompt=system,
            task_type="simple",
            temperature=0.3,
            max_tokens=500,
            user_id=user_id,
        )
        
        if translated and translated.strip():
            translated = translated.strip()
            if translated.startswith('"') and translated.endswith('"'):
                translated = translated[1:-1]
            if translated.startswith("'") and translated.endswith("'"):
                translated = translated[1:-1]
            for prefix in ["English translation:", "English:", "Translation:"]:
                if translated.lower().startswith(prefix.lower()):
                    translated = translated[len(prefix):].strip()
            
            logger.info(f"🎨 Translated Arabic prompt: '{prompt[:50]}' → '{translated[:50]}'")
            return translated
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to translate Arabic prompt: {e}")
    
    return prompt



async def _generate_and_send_image(wa_id: str, prompt: str, wa_user_id: int, 
                                     contact_name: str, message_id: str = "", is_admin: bool = False):
    """Generate an image using AI and send it via WhatsApp — like Telegram's /image command
    
    This actually generates an image using the provider_manager (same as Telegram),
    instead of just asking the AI to describe what the image would look like.
    """
    from provider_manager import get_provider_manager
    
    # Start thinking feedback
    feedback = ThinkingFeedback(wa_id, message_id, context_type="image")
    await feedback.start()
    
    try:
        # Translate Arabic prompt to English for better image generation
        original_prompt = prompt
        image_prompt = await _translate_prompt_to_english(prompt, user_id=wa_user_id)
        was_translated = (image_prompt != original_prompt)
        
        # Generate image using provider_manager (same engine as Telegram)
        manager = get_provider_manager()
        result = await manager.generate_image_async(
            prompt=image_prompt,
            size="1024x1024",
            user_id=wa_user_id,
        )
        
        if not result:
            await _send_whatsapp_message(wa_id, "❌ حصل خطأ في إنشاء الصورة. جرب وصف تاني! 🎨")
            await feedback.error()
            return
        
        # Build caption
        if was_translated:
            caption = f"🎨 صورتك جاهزة!\n\n📝 {original_prompt[:150]}"
        else:
            caption = f"🎨 صورتك جاهزة!\n\n📝 {original_prompt[:200]}"
        
        # Send the image
        if result.get("base64"):
            await _send_whatsapp_image(wa_id, result["base64"], caption)
        elif result.get("url"):
            # Download from URL and send
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(result["url"], timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            img_bytes = await resp.read()
                            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                            await _send_whatsapp_image(wa_id, img_b64, caption)
                        else:
                            await _send_whatsapp_message(wa_id, "❌ فشل تحميل الصورة. جرب تاني! 🎨")
            except Exception as e:
                logger.error(f"❌ Error downloading generated image: {e}")
                await _send_whatsapp_message(wa_id, "❌ فشل تحميل الصورة. جرب تاني! 🎨")
        else:
            await _send_whatsapp_message(wa_id, "❌ حصل خطأ في إنشاء الصورة. جرب تاني! 🎨")
        
        # Increment usage
        if not is_admin:
            try:
                from premium import increment_usage
                increment_usage(wa_user_id, "image_generations")
            except Exception:
                pass
        
        # Try track event
        try:
            from dashboard import track_event
            track_event("image_generations", platform="whatsapp")
        except Exception:
            pass
        
        await feedback.complete()
        
        # Quick action buttons
        await _send_interactive_buttons(wa_id, body_text="عايز حاجة تانية؟",
            buttons=[
                {"id": "cmd_image_gen", "title": "🎨 صورة تانية"},
                {"id": "cmd_image_edit", "title": "🖌️ عدّلها"},
                {"id": "cmd_chat", "title": "💬 محادثة"},
            ])
        
        logger.info(f"✅ WA Image generated and sent to {wa_id}")
        
    except Exception as e:
        logger.error(f"❌ Image generation error for WA {wa_id}: {e}", exc_info=True)
        await _send_whatsapp_message(wa_id, "❌ حصل خطأ في إنشاء الصورة. جرب تاني! 🎨")
        await feedback.error()



async def _edit_and_send_image(wa_id: str, prompt: str, image_base64: str, wa_user_id: int,
                                contact_name: str, message_id: str = "", is_admin: bool = False):
    """Edit an image using AI (same as Telegram's /edit command) — REAL image editing
    
    Uses the provider_manager's edit_image_async (NVIDIA Visual GenA) — same engine as Telegram.
    """
    from provider_manager import get_provider_manager
    
    # Start thinking feedback
    feedback = ThinkingFeedback(wa_id, message_id, context_type="image")
    await feedback.start()
    
    try:
        # Translate Arabic prompt to English for better editing results
        original_prompt = prompt
        edit_prompt = await _translate_prompt_to_english(prompt, user_id=wa_user_id)
        was_translated = (edit_prompt != original_prompt)
        
        # Edit the image using provider_manager (same engine as Telegram)
        manager = get_provider_manager()
        result = await manager.edit_image_async(
            prompt=edit_prompt,
            image_base64=image_base64,
            user_id=wa_user_id,
        )
        
        if not result:
            await _send_whatsapp_message(wa_id, "❌ حصل خطأ في تعديل الصورة. جرب وصف تاني! 🖌️")
            await feedback.error()
            return
        
        # Build caption
        if was_translated:
            caption = f"🖌️ الصورة بعد التعديل!\n\n📝 {original_prompt[:150]}"
        else:
            caption = f"🖌️ الصورة بعد التعديل!\n\n📝 {original_prompt[:200]}"
        
        # Send the edited image
        if result.get("base64"):
            await _send_whatsapp_image(wa_id, result["base64"], caption)
        elif result.get("url"):
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(result["url"], timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            img_bytes = await resp.read()
                            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                            await _send_whatsapp_image(wa_id, img_b64, caption)
                        else:
                            await _send_whatsapp_message(wa_id, "❌ فشل تحميل الصورة المعدلة. جرب تاني! 🖌️")
            except Exception as e:
                logger.error(f"❌ Error downloading edited image: {e}")
                await _send_whatsapp_message(wa_id, "❌ فشل تحميل الصورة المعدلة. جرب تاني! 🖌️")
        else:
            await _send_whatsapp_message(wa_id, "❌ حصل خطأ في تعديل الصورة. جرب وصف تاني! 🖌️")
        
        # Increment usage
        if not is_admin:
            try:
                from premium import increment_usage
                increment_usage(wa_user_id, "image_edits")
            except Exception:
                pass
        
        await feedback.complete()
        
        # Quick action buttons
        await _send_interactive_buttons(wa_id, body_text="عايز حاجة تانية؟",
            buttons=[
                {"id": "cmd_image_edit", "title": "🖌️ عدّل تاني"},
                {"id": "cmd_image_gen", "title": "🎨 صورة جديدة"},
                {"id": "cmd_chat", "title": "💬 محادثة"},
            ])
        
        logger.info(f"✅ WA Image edited and sent to {wa_id}")
        
    except Exception as e:
        logger.error(f"❌ Image editing error for WA {wa_id}: {e}", exc_info=True)
        await _send_whatsapp_message(wa_id, "❌ حصل خطأ في تعديل الصورة. جرب تاني! 🖌️")
        await feedback.error()

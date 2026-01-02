import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from asyncio import sleep

# --- Kerakli importlar ---
# Barcha funksiyalar uchun kerak
from database import Database, Movie, RequiredChannel 
from config import config 
from filters import IsAdmin, IsAdminCallback 
from keyboards import (
    get_admin_panel_kb, get_back_to_admin_kb,
    get_cancel_kb, get_confirmation_kb, get_quality_kb,
    get_edit_movie_fields_kb, get_broadcast_kb
)
from utils import format_movie_info, format_number, create_progress_bar 

router = Router()
logger = logging.getLogger(__name__)

# --- Admin States ---
class AdminStates(StatesGroup):
    # 🎬 Kino qo'shish
    AddMovieFile = State()
    AddMovieCode = State()
    AddMovieTitle = State()
    AddMovieGenre = State()
    AddMovieDescription = State()
    AddMovieYear = State()
    AddMovieCountry = State()
    AddMovieDuration = State()
    AddMovieQuality = State()
    AddMovieIMDB = State()
    AddMovieThumbnail = State()
    
    # ✏️ Kino tahrirlash
    EditMovieCode = State()
    EditMovieField = State()
    EditMovieValue = State()
    
    # 🗑 Kino o'chirish
    DeleteMovieCode = State()
    
    # 📢 Rassilka
    BroadcastMessage = State()
    BroadcastConfirm = State()
    
    # 🔐 Majburiy obuna
    AddChannelID = State()
    AddChannelTitle = State()
    DeleteChannelID = State()

# ----------------------------------------------------------------------
## 🏠 Admin Panelga Kirish

@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message, state: FSMContext, db: Database):
    """Admin panel va statistika"""
    await state.clear()
    
    stats = await db.get_global_stats()
    active_users = await db.get_active_users_count(7)
    channels_count = await db.count_required_channels()
    
    text = (
        "🛠 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: {format_number(stats['users_count'])}\n"
        f"🟢 Aktiv (7 kun): {format_number(active_users)}\n"
        f"🎬 Jami kinolar: {format_number(stats['movies_count'])}\n"
        f"👁 Jami ko'rishlar: {format_number(stats['total_views'])}\n"
        f"🔗 Majburiy kanal soni: {channels_count}\n\n"
        f"Quyidagi amallardan birini tanlang:"
    )
    
    await message.answer(text, reply_markup=get_admin_panel_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_panel_back", IsAdminCallback())
async def admin_panel_back(call: CallbackQuery, state: FSMContext, db: Database):
    """Admin panelga qaytish"""
    await state.clear()
    # Edit message agar call orqali kelgan bo'lsa
    await call.message.delete()
    await admin_panel(call.message, state, db)
    await call.answer()

@router.callback_query(F.data == "cancel", IsAdminCallback())
async def cancel_action(call: CallbackQuery, state: FSMContext, db: Database):
    """Amalni bekor qilish"""
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi")
    await admin_panel(call.message, state, db)
    await call.answer()

# ----------------------------------------------------------------------
## 🎬 Kino Qo'shish Funksiyasi (To'liq tiklandi)

@router.callback_query(F.data == "admin_add_movie", IsAdminCallback())
async def add_movie_start(call: CallbackQuery, state: FSMContext):
    """Kino qo'shishni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "📝 <b>Yangi kino qo'shish</b>\n\n"
        "1️⃣/11 Kino faylini (video yoki document) yuboring:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.AddMovieFile)
    await call.answer()
    
@router.message(AdminStates.AddMovieFile, IsAdmin())
async def get_movie_file(message: Message, state: FSMContext):
    """Kino faylini qabul qilish"""
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.answer("❌ Iltimos, faqat video yoki document yuboring!")
        return

    await state.update_data(file_id=file_id)
    await message.answer(
        "2️⃣/11 Kino uchun noyob kodni kiriting:\n\n"
        "Masalan: <code>/code 1234</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.AddMovieCode)
    
@router.message(AdminStates.AddMovieCode, Command("code"), IsAdmin())
async def get_movie_code(message: Message, state: FSMContext, db: Database, command: CommandObject):
    """Kino kodini qabul qilish"""
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n\nMasalan: <code>/code 1234</code>", parse_mode="HTML")
        return
    
    movie_code = int(command.args)
    
    if await db.get_movie_by_code(movie_code):
        await message.answer(f"❌ <code>{movie_code}</code> kodi allaqachon mavjud. Boshqa kod kiriting.", parse_mode="HTML")
        return
    
    await state.update_data(code=movie_code)
    await message.answer("3️⃣/11 Kino nomini kiriting:", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieTitle)

@router.message(AdminStates.AddMovieCode, IsAdmin())
async def get_movie_code_invalid(message: Message):
    """Noto'g'ri kod formati"""
    await message.answer("❌ Noto'g'ri format! Kodni <code>/code 1234</code> formatda kiriting.", parse_mode="HTML")


@router.message(AdminStates.AddMovieTitle, IsAdmin())
async def get_movie_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("4️⃣/11 Kino janrini kiriting (Masalan: Fantastika, Jangari):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieGenre)

@router.message(AdminStates.AddMovieGenre, IsAdmin())
async def get_movie_genre(message: Message, state: FSMContext):
    await state.update_data(genre=message.text)
    await message.answer("5️⃣/11 Kino tavsifini kiriting (O'tkazish uchun: <code>/skip</code>):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieDescription)

@router.message(AdminStates.AddMovieDescription, IsAdmin())
async def get_movie_description(message: Message, state: FSMContext):
    description = None if message.text == "/skip" else message.text
    await state.update_data(description=description)
    await message.answer("6️⃣/11 Kino yilini kiriting (Masalan: <code>2024</code> / <code>/skip</code>):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieYear)

@router.message(AdminStates.AddMovieYear, IsAdmin())
async def get_movie_year(message: Message, state: FSMContext):
    year = None
    if message.text != "/skip":
        try:
            year = int(message.text)
        except ValueError:
            await message.answer("❌ Yil raqamlardan iborat bo'lishi kerak!")
            return
    await state.update_data(year=year)
    await message.answer("7️⃣/11 Mamlakatni kiriting (Masalan: <code>AQSH, Angliya</code> / <code>/skip</code>):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieCountry)

@router.message(AdminStates.AddMovieCountry, IsAdmin())
async def get_movie_country(message: Message, state: FSMContext):
    country = None if message.text == "/skip" else message.text
    await state.update_data(country=country)
    await message.answer("8️⃣/11 Kino davomiyligini kiriting (daqiqalarda, Masalan: <code>120</code> / <code>/skip</code>):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieDuration)

@router.message(AdminStates.AddMovieDuration, IsAdmin())
async def get_movie_duration(message: Message, state: FSMContext):
    duration = None
    if message.text != "/skip":
        try:
            duration = int(message.text)
        except ValueError:
            await message.answer("❌ Davomiylik raqamlardan iborat bo'lishi kerak!")
            return
    await state.update_data(duration=duration)
    await message.answer("9️⃣/11 Sifatni tanlang:", reply_markup=get_quality_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieQuality)

@router.callback_query(AdminStates.AddMovieQuality, F.data.startswith("quality_"), IsAdminCallback())
async def get_movie_quality(call: CallbackQuery, state: FSMContext):
    quality = call.data.split("_")[1]
    await state.update_data(quality=quality)
    await call.message.edit_text(
        "🔟/11 IMDb reytingini kiriting (Masalan: <code>8.5</code> / <code>/skip</code>):",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.AddMovieIMDB)
    await call.answer()

@router.message(AdminStates.AddMovieIMDB, IsAdmin())
async def get_movie_imdb(message: Message, state: FSMContext):
    imdb_rating = None
    if message.text != "/skip":
        try:
            imdb_rating = float(message.text)
        except ValueError:
            await message.answer("❌ Reyting raqam bo'lishi kerak!")
            return
    await state.update_data(imdb_rating=imdb_rating)
    await message.answer("1️⃣1️⃣/11 Thumbnail (rasm) yuboring (O'tkazish uchun: <code>/skip</code>):", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieThumbnail)

@router.message(AdminStates.AddMovieThumbnail, IsAdmin())
async def finalize_movie(message: Message, state: FSMContext, db: Database, bot: Bot):
    """Kinoni yakunlash va saqlash"""
    thumbnail_file_id = None
    
    if message.photo:
        thumbnail_file_id = message.photo[-1].file_id
    elif message.document and 'image' in message.document.mime_type:
        thumbnail_file_id = message.document.file_id
    elif message.text == "/skip":
        pass
    else:
        await message.answer("❌ Rasm yuboring yoki /skip kiriting!")
        return
    
    data = await state.get_data()
    
    try:
        movie: Movie = await db.add_movie(
            code=data['code'],
            file_id=data['file_id'],
            title=data['title'],
            genre=data['genre'],
            description=data.get('description'),
            year=data.get('year'),
            country=data.get('country'),
            duration=data.get('duration'),
            quality=data.get('quality', 'HD'),
            imdb_rating=data.get('imdb_rating'),
            thumbnail_file_id=thumbnail_file_id
        )
        
    except Exception as e:
        logger.error(f"Kino qo'shishda xatolik: {e}")
        await message.answer(f"❌ Kino qo'shishda xatolik yuz berdi: {e}")
        await state.clear()
        return
    
    # Kanalga post yuborish logikasi
    bot_info = await bot.get_me()
    rating = await db.get_movie_rating(movie.id)
    post_text = format_movie_info(movie, rating)
    post_text += f"\n\n👇 Kinoni olish uchun botga o'ting:"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Kinoni olish", url=f"https://t.me/{bot_info.username}?start=code_{movie.code}")
    
    try:
        if thumbnail_file_id:
            await bot.send_photo(
                chat_id=config.CHANNEL_USERNAME,
                photo=thumbnail_file_id,
                caption=post_text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=config.CHANNEL_USERNAME,
                text=post_text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        await message.answer(
            f"✅ Kino muvaffaqiyatli qo'shildi va kanalga joylandi!\n\n"
            f"🎬 Nomi: {movie.title}\n"
            f"🔢 Kod: <code>{movie.code}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"✅ Kino bazaga qo'shildi, lekin kanalga joylashda xatolik!\n\n"
            f"❌ Xatolik: {e}",
            parse_mode="HTML"
        )
    
    await state.clear()
    await admin_panel(message, state, db)

# ----------------------------------------------------------------------
## ✏️ Kino Tahrirlash Funksiyasi (To'liq tiklandi)

@router.callback_query(F.data == "admin_edit_movie", IsAdminCallback())
async def edit_movie_start(call: CallbackQuery, state: FSMContext):
    """Kino tahrirlashni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "✏️ <b>Kinoni tahrirlash</b>\n\n"
        "Tahrirlamoqchi bo'lgan kinoning kodini kiriting:\n"
        "Masalan: <code>/code 1234</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.EditMovieCode)
    await call.answer()

@router.message(AdminStates.EditMovieCode, Command("code"), IsAdmin())
async def edit_movie_code(message: Message, state: FSMContext, db: Database, command: CommandObject):
    """Tahrirlash uchun kino kodini qabul qilish"""
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n\nMasalan: <code>/code 1234</code>", parse_mode="HTML")
        return
    
    movie_code = int(command.args)
    movie: Movie = await db.get_movie_by_code(movie_code)
    
    if not movie:
        await message.answer(f"❌ <code>{movie_code}</code> kodli kino topilmadi. Boshqa kod kiriting.", parse_mode="HTML")
        return
    
    await state.update_data(movie_id=movie.id, movie_code=movie_code)
    
    # Kino ma'lumotlarini ko'rsatish
    rating = await db.get_movie_rating(movie.id)
    info_text = format_movie_info(movie, rating)
    
    await message.answer(
        f"✅ Kino topildi: <b>{movie.title}</b> (Kod: <code>{movie.code}</code>)\n\n"
        f"--- Hozirgi ma'lumotlar ---\n"
        f"{info_text}\n"
        f"--- Tahrirlash uchun maydon tanlang ---",
        reply_markup=get_edit_movie_fields_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.EditMovieField)

@router.message(AdminStates.EditMovieCode, IsAdmin())
async def edit_movie_code_invalid(message: Message):
    await message.answer("❌ Noto'g'ri format! Kodni <code>/code 1234</code> formatda kiriting.", parse_mode="HTML")

@router.callback_query(AdminStates.EditMovieField, F.data.startswith("edit_"), IsAdminCallback())
async def edit_movie_field_select(call: CallbackQuery, state: FSMContext):
    """Tahrirlash maydonini tanlash"""
    field = call.data.split("_")[1]
    
    await state.update_data(edit_field=field)
    
    field_name = field.replace('_', ' ').capitalize()
    prompt = f"<b>'{field_name}'</b> maydoni uchun yangi qiymatni kiriting:"
    
    if field == 'file_id':
        prompt += "\n\n⚠️ Kino faylini (video/document) qayta yuboring."
    elif field == 'thumbnail_file_id':
        prompt += "\n\n⚠️ Yangi thumbnail (rasm) yuboring."
    elif field in ['code']:
        prompt += "\n\n⚠️ Faqat raqam kiriting."
    elif field in ['year', 'duration', 'imdb_rating', 'description', 'country']:
        prompt += "\n\nO'chirish (bo'sh qoldirish) uchun: <code>/clear</code>"

    await call.message.edit_text(
        prompt,
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.EditMovieValue)
    await call.answer()

@router.message(AdminStates.EditMovieValue, IsAdmin())
async def edit_movie_value_input(message: Message, state: FSMContext, db: Database):
    """Tahrirlash qiymatini kiritish va saqlash"""
    data = await state.get_data()
    movie_id = data['movie_id']
    edit_field = data['edit_field']
    new_value = None
    
    # --- Qiymatni tekshirish ---
    if edit_field == 'file_id':
        if message.video:
            new_value = message.video.file_id
        elif message.document:
            new_value = message.document.file_id
        else:
            await message.answer("❌ Iltimos, faqat video yoki document yuboring!")
            return
            
    elif edit_field == 'thumbnail_file_id':
        if message.photo:
            new_value = message.photo[-1].file_id
        elif message.document and 'image' in message.document.mime_type:
             new_value = message.document.file_id
        elif message.text == "/clear":
            new_value = None
        else:
            await message.answer("❌ Iltimos, rasm yuboring yoki /clear kiriting!")
            return
    
    elif edit_field == 'code':
        if not message.text or not message.text.isdigit():
            await message.answer("❌ Kod faqat raqamlardan iborat bo'lishi kerak!")
            return
        new_value = int(message.text)
        existing_movie = await db.get_movie_by_code(new_value)
        if existing_movie and existing_movie.id != movie_id:
            await message.answer(f"❌ <code>{new_value}</code> kodi allaqachon boshqa kino uchun mavjud.", parse_mode="HTML")
            return
            
    elif edit_field == 'year':
        if message.text == "/clear":
            new_value = None
        else:
            try:
                new_value = int(message.text)
            except ValueError:
                await message.answer("❌ Yil raqamlardan iborat bo'lishi kerak!")
                return
                
    elif edit_field == 'duration':
        if message.text == "/clear":
            new_value = None
        else:
            try:
                new_value = int(message.text)
            except ValueError:
                await message.answer("❌ Davomiylik raqamlardan iborat bo'lishi kerak!")
                return
                
    elif edit_field == 'imdb_rating':
        if message.text == "/clear":
            new_value = None
        else:
            try:
                new_value = float(message.text)
            except ValueError:
                await message.answer("❌ Reyting raqam bo'lishi kerak!")
                return
                
    elif edit_field in ['description', 'country']:
        new_value = None if message.text == "/clear" else message.text
        
    elif edit_field in ['title', 'genre', 'quality']:
        if not message.text and message.text != "":
            await message.answer("❌ Qiymat bo'sh bo'lishi mumkin emas!")
            return
        new_value = message.text
    
    # Baza ma'lumotini yangilash
    update_data = {edit_field: new_value}
    await db.update_movie(movie_id, **update_data)
    
    if edit_field == 'code':
        await state.update_data(movie_code=new_value)

    # Natijani ko'rsatish
    updated_movie: Movie = await db.get_movie_by_id(movie_id)
    rating = await db.get_movie_rating(movie_id)
    info_text = format_movie_info(updated_movie, rating)

    await message.answer(
        f"✅ <b>'{edit_field.replace('_', ' ').capitalize()}'</b> maydoni muvaffaqiyatli yangilandi!\n\n"
        f"--- Yangilangan ma'lumotlar ---\n"
        f"{info_text}\n"
        f"--- Davom etish uchun maydon tanlang ---",
        reply_markup=get_edit_movie_fields_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.EditMovieField)

# ----------------------------------------------------------------------
## 🗑 Kino O'chirish Funksiyasi (To'liq tiklandi)

@router.callback_query(F.data == "admin_delete_movie", IsAdminCallback())
async def delete_movie_start(call: CallbackQuery, state: FSMContext):
    """Kino o'chirishni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "🗑 <b>Kinoni o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kinoning kodini kiriting:\n"
        "Masalan: <code>/code 1234</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.DeleteMovieCode)
    await call.answer()

@router.message(AdminStates.DeleteMovieCode, Command("code"), IsAdmin())
async def delete_movie_code(message: Message, state: FSMContext, db: Database, command: CommandObject):
    """O'chirish uchun kino kodini qabul qilish va tasdiqlash"""
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n\nMasalan: <code>/code 1234</code>", parse_mode="HTML")
        return
    
    movie_code = int(command.args)
    movie: Movie = await db.get_movie_by_code(movie_code)
    
    if not movie:
        await message.answer(f"❌ <code>{movie_code}</code> kodli kino topilmadi. Boshqa kod kiriting.", parse_mode="HTML")
        return
    
    await state.update_data(movie_id=movie.id, movie_title=movie.title, movie_code=movie_code)
    
    await message.answer(
        f"⚠️ Siz <b>{movie.title}</b> (Kod: <code>{movie.code}</code>) kinoni o'chirmoqchisiz.\n\n"
        "Rostdan ham o'chirishni tasdiqlaysizmi?",
        reply_markup=get_confirmation_kb("delete_movie"),
        parse_mode="HTML"
    )

@router.message(AdminStates.DeleteMovieCode, IsAdmin())
async def delete_movie_code_invalid(message: Message):
    await message.answer("❌ Noto'g'ri format! Kodni <code>/code 1234</code> formatda kiriting.", parse_mode="HTML")

@router.callback_query(F.data == "confirm_delete_movie", IsAdminCallback())
async def delete_movie_execute(call: CallbackQuery, state: FSMContext, db: Database):
    """Kinoni o'chirishni bajarish"""
    data = await state.get_data()
    movie_id = data['movie_id']
    movie_title = data['movie_title']
    movie_code = data['movie_code']
    
    await db.delete_movie(movie_id) 
    
    await state.clear()
    
    await call.message.edit_text(
        f"✅ <b>{movie_title}</b> (Kod: <code>{movie_code}</code>) muvaffaqiyatli o'chirildi!",
        parse_mode="HTML"
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Admin Panelga qaytish", callback_data="admin_panel_back")
    
    await call.message.edit_reply_markup(reply_markup=kb.as_markup())
    await call.answer()
    
@router.callback_query(F.data == "cancel_delete_movie", IsAdminCallback())
async def delete_movie_cancel(call: CallbackQuery, state: FSMContext, db: Database):
    """Kinoni o'chirishni bekor qilish"""
    await state.clear()
    await call.message.edit_text("❌ Kino o'chirish bekor qilindi")
    await admin_panel(call.message, state, db)
    await call.answer()

# ----------------------------------------------------------------------
## 📊 Statistika Funksiyasi

@router.callback_query(F.data == "admin_stats", IsAdminCallback())
async def get_stats(call: CallbackQuery, db: Database):
    """Umumiy statistika sahifasi"""
    await call.answer()
    
    msg_id = call.message.message_id
    chat_id = call.message.chat.id
    
    await call.message.edit_text("⏳ Statistika yig'ilmoqda...")

    try:
        global_stats = await db.get_global_stats()
        active_users_7 = await db.get_active_users_count(7)
        active_users_30 = await db.get_active_users_count(30)
        channels_count = await db.count_required_channels()

        text = (
            "📈 <b>Bot Statistikasi</b>\n\n"
            "👥 <b>Foydalanuvchilar:</b>\n"
            f"  • Jami: <code>{format_number(global_stats['users_count'])}</code>\n"
            f"  • Aktiv (7 kun): <code>{format_number(active_users_7)}</code>\n"
            f"  • Aktiv (30 kun): <code>{format_number(active_users_30)}</code>\n\n"
            "🎬 <b>Kinolar & Ko'rishlar:</b>\n"
            f"  • Jami kinolar: <code>{format_number(global_stats['movies_count'])}</code>\n"
            f"  • Jami ko'rishlar: <code>{format_number(global_stats['total_views'])}</code>\n\n"
            f"🔗 <b>Kanallar:</b>\n"
            f"  • Majburiy kanal soni: <code>{channels_count}</code>"
        )
        
        await call.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            reply_markup=get_back_to_admin_kb(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Statistika olishda xatolik: {e}")
        await call.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"❌ Xatolik yuz berdi: {e}",
            reply_markup=get_back_to_admin_kb()
        )

# ----------------------------------------------------------------------
## 📢 Rassilka Funksiyasi

@router.callback_query(F.data == "admin_broadcast", IsAdminCallback())
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    """Rassilka xabarini qabul qilishni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "📢 <b>Rassilka yaratish</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring. Xabar matn, rasm, video, tugmalar (inline) bo'lishi mumkin.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.BroadcastMessage)
    await call.answer()

@router.message(AdminStates.BroadcastMessage, IsAdmin())
async def broadcast_preview(message: Message, state: FSMContext):
    """Rassilka xabarini saqlash va ko'rib chiqish"""
    await state.update_data(
        broadcast_text=message.html_text, 
        broadcast_message_id=message.message_id
    )
    
    await message.answer("📢 <b>Rassilka Xabari Ko'rinishi:</b>", parse_mode="HTML")
    try:
        await message.copy_to(
            chat_id=message.chat.id, 
            reply_markup=get_broadcast_kb()
        )
    except Exception as e:
        logger.error(f"Rassilka xabarini ko'chirishda xatolik: {e}")
        await message.answer("❌ Xabarni ko'rib chiqishda xatolik yuz berdi. Yana urinib ko'ring yoki /cancel bosing.")
        return
        
    await state.set_state(AdminStates.BroadcastConfirm)

@router.callback_query(AdminStates.BroadcastConfirm, F.data == "broadcast_send", IsAdminCallback())
async def broadcast_send_confirm(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    """Rassilka yuborishni tasdiqlash va boshlash"""
    await call.message.edit_text("⏳ Rassilka yuborish boshlandi...")
    await call.answer()
    
    data = await state.get_data()
    all_users = await db.get_all_user_ids()
    total_users = len(all_users)
    success_count = 0
    fail_count = 0
    
    start_time = datetime.now()
    status_message = await call.message.answer(f"0 / {total_users} (0%) yuborildi. ✅: 0 | ❌: 0")

    original_message_id = data.get('broadcast_message_id')
    admin_id = call.from_user.id
    
    for i, user_id in enumerate(all_users):
        try:
            await bot.copy_message(
                chat_id=user_id, 
                from_chat_id=admin_id, 
                message_id=original_message_id
            )
            success_count += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            fail_count += 1
        except Exception as e:
            logger.error(f"Rassilka xatoligi {user_id}: {e}")
            fail_count += 1
            
        if (i + 1) % 50 == 0 or (i + 1) == total_users:
            progress = create_progress_bar(i + 1, total_users)
            
            try:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=status_message.message_id,
                    text=(
                        f"📢 <b>Rassilka jarayoni</b>\n"
                        f"Progress: {progress}\n"
                        f"{i + 1} / {total_users} yuborildi.\n"
                        f"✅ Muvaffaqiyatli: {success_count}\n"
                        f"❌ Xatolik: {fail_count}\n"
                        f"Vaqt: {datetime.now() - start_time}"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass 

        await sleep(0.05) 

    end_time = datetime.now()
    final_text = (
        f"✅ <b>Rassilka Yakunlandi!</b>\n\n"
        f"👥 Jami foydalanuvchi: {total_users}\n"
        f"✅ Muvaffaqiyatli: {success_count}\n"
        f"❌ Xatolik (Bot bloklangan): {fail_count}\n"
        f"⏱ Umumiy vaqt: {end_time - start_time}"
    )
    
    await bot.edit_message_text(
        chat_id=admin_id,
        message_id=status_message.message_id,
        text=final_text,
        reply_markup=get_back_to_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(AdminStates.BroadcastConfirm, F.data == "broadcast_preview", IsAdminCallback())
async def broadcast_preview_back(call: CallbackQuery):
    await call.answer("Iltimos, Yuborish yoki Bekor qilish tugmasini bosing.")

# ----------------------------------------------------------------------
## 🔐 Majburiy Obuna Funksiyasi

@router.callback_query(F.data == "admin_fsub", IsAdminCallback())
async def fsub_menu(call: CallbackQuery, db: Database):
    """Majburiy obuna kanallari menyusi"""
    channels = await db.get_required_channels()
    
    if channels:
        channel_list = "\n".join([
            f"  • {i+1}. <b>{ch.title}</b> (ID: <code>{ch.channel_id}</code>)"
            for i, ch in enumerate(channels)
        ])
        text = (
            "🔗 <b>Majburiy Obuna Kanallari</b>\n\n"
            f"Hozirda ro'yxatdagi kanallar ({len(channels)} ta):\n"
            f"{channel_list}\n\n"
            "Quyidagi amallardan birini tanlang:"
        )
    else:
        text = "🔗 <b>Majburiy Obuna Kanallari</b>\n\nRo'yxatda hozircha hech qanday kanal yo'q."
        
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Kanal qo'shish", callback_data="fsub_add_channel")
    if channels:
        kb.button(text="🗑 Kanal o'chirish", callback_data="fsub_delete_channel")
    kb.button(text="⬅️ Ortga", callback_data="admin_panel_back")
    kb.adjust(2, 1)
    
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()

# --- Kanal qo'shish ---
@router.callback_query(F.data == "fsub_add_channel", IsAdminCallback())
async def fsub_add_channel_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "➕ **Yangi Kanal Qo'shish**\n\n"
        "1/2 Kanal ID yoki username'ni kiriting. (Masalan: <code>-10012345678</code> yoki <code>@kanalim</code>)",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.AddChannelID)
    await call.answer()

@router.message(AdminStates.AddChannelID, IsAdmin())
async def fsub_add_channel_title(message: Message, state: FSMContext):
    channel_id_or_username = message.text.strip()
    
    if not channel_id_or_username:
        await message.answer("❌ Kanal ID yoki username noto'g'ri!")
        return

    await state.update_data(channel_id_or_username=channel_id_or_username)
    await message.answer(
        "2/2 Kanalning nomini kiriting (Bu nom foydalanuvchiga ko'rsatiladi):",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminStates.AddChannelTitle)

@router.message(AdminStates.AddChannelTitle, IsAdmin())
async def fsub_add_channel_save(message: Message, state: FSMContext, db: Database, bot: Bot):
    channel_title = message.text.strip()
    data = await state.get_data()
    channel_id_or_username = data['channel_id_or_username']
    
    try:
        chat = await bot.get_chat(channel_id_or_username)
        final_channel_id = chat.id
    except TelegramBadRequest:
        await message.answer("❌ Kanal topilmadi yoki bot u yerda admin emas. Botni kanalga Admin qilib qo'yganingizga ishonch hosil qiling!")
        return
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")
        return

    try:
        await db.add_required_channel(
            channel_id=final_channel_id, 
            title=channel_title
        )
        await message.answer(
            f"✅ Kanal muvaffaqiyatli qo'shildi:\n"
            f"Nomi: <b>{channel_title}</b>\n"
            f"ID: <code>{final_channel_id}</code>",
            reply_markup=get_back_to_admin_kb(),
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Kanalni bazaga qo'shishda xatolik: {e}")
        
# --- Kanal o'chirish ---
@router.callback_query(F.data == "fsub_delete_channel", IsAdminCallback())
async def fsub_delete_channel_start(call: CallbackQuery, state: FSMContext, db: Database):
    channels = await db.get_required_channels()
    if not channels:
        await call.answer("Ro'yxatda o'chirish uchun kanal yo'q.")
        return
    
    channel_list = "\n".join([
        f"  • {i+1}. <b>{ch.title}</b> (ID: <code>{ch.channel_id}</code>)"
        for i, ch in enumerate(channels)
    ])
    
    await state.clear()
    await call.message.edit_text(
        "🗑 **Kanalni O'chirish**\n\n"
        "O'chirmoqchi bo'lgan kanalning **ID raqamini** (<code>-100...</code>) kiriting:\n\n"
        f"Mavjud kanallar:\n{channel_list}",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.DeleteChannelID)
    await call.answer()

@router.message(AdminStates.DeleteChannelID, IsAdmin())
async def fsub_delete_channel_save(message: Message, state: FSMContext, db: Database):
    try:
        channel_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri ID format. ID faqat raqamlardan iborat bo'lishi kerak (masalan, -10012345678).")
        return
    
    await db.delete_required_channel(channel_id)
    
    await message.answer(
        f"✅ Kanal (ID: <code>{channel_id}</code>) ro'yxatdan muvaffaqiyatli o'chirildi!",
        reply_markup=get_back_to_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

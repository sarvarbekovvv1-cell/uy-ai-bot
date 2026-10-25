"""Uzbek localization dictionary."""

MESSAGES: dict[str, str] = {
    # Language & Selection
    "choose_language": "Tilni tanlang / Выберите язык:",
    "btn_uz": "🇺🇿 O‘zbekcha",
    "btn_ru": "🇷🇺 Русский",
    # Consent
    "consent_text": (
        "UyAI xizmatidan foydalanish davomida Telegram profilingiz va siz taqdim "
        "etgan aloqa ma’lumotlari xizmat ko‘rsatish maqsadida qayta ishlanadi.\n\n"
        "Davom etish orqali bunga rozilik bildirasiz."
    ),
    "btn_consent_accept": "✅ Roziman",
    "btn_consent_decline": "❌ Bekor qilish",
    "consent_declined": (
        "Ro‘yxatdan o‘tish bekor qilindi. Xizmatdan foydalanish uchun rozilik talab "
        "etiladi. Qayta boshlash uchun /start buyrug‘ini bosing."
    ),
    # Name & Phone
    "ask_name": "Iltimos, ismingizni kiriting:",
    "invalid_name": (
        "Ism 2 dan 50 tagacha belgidan iborat bo‘lishi kerak. Iltimos, qaytadan kiriting:"
    ),
    "ask_phone": "Iltimos, aloqa uchun telefon raqamingizni pastdagi tugma orqali yuboring:",
    "btn_send_phone": "📱 Telefon raqamni yuborish",
    "invalid_contact_owner": (
        "Xavfsizlik talabi: Faqat o‘zingizning Telegram profilingizga tegishli telefon "
        "raqamni yuborishingiz kerak."
    ),
    "invalid_phone_format": (
        "Noto‘g‘ri telefon raqam formati. Iltimos, pastdagi tugmani bosing yoki raqamingizni "
        "+998XXXXXXXXX formatida yozing:"
    ),
    # Registration & Welcome
    "registration_complete": "Tabriklaymiz! Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi.",
    "welcome_back": "🏢 UyAI tizimiga qayta xush kelibsiz!",
    "main_menu_title": "🏢 UyAI — Asosiy menyu\nQuyidagi xizmatlardan birini tanlang:",
    # Main Menu Buttons
    "btn_buy": "🏠 Uy sotib olish",
    "btn_rent": "🔑 Uy ijaraga olish",
    "btn_sell": "💰 Uyimni sotish",
    "btn_lease": "🏡 Uyimni ijaraga berish",
    "btn_valuation": "📊 Uyimni baholash",
    "btn_map": "📍 Xaritadan uy qidirish",
    "btn_ai_broker": "🤖 AI broker",
    "btn_favorites": "❤️ Saqlangan uylar",
    "btn_appointments": "📅 Uchrashuvlarim",
    "btn_contact_broker": "👨‍💼 Broker bilan bog‘lanish",
    "btn_my_properties": "🏘 Mening e'lonlarim",
    "btn_settings": "⚙️ Sozlamalar",
    # Placeholder
    "feature_in_development": "Bu funksiya keyingi bosqichda ishga tushiriladi.",
    # Property Submission
    "explain_sell_process": (
        "💰 Ko‘chmas mulk sotish bo‘yicha e’lon berish boshlandi.\n"
        "Iltimos, obyekt turini tanlang:"
    ),
    "explain_rent_process": (
        "🏡 Ko‘chmas mulkni ijaraga berish bo‘yicha e’lon berish boshlandi.\n"
        "Iltimos, obyekt turini tanlang:"
    ),
    "ask_region": "Viloyat yoki shaharni kiriting (masalan: Toshkent):",
    "ask_district": "Tuman yoki mahallani kiriting (masalan: Chilonzor):",
    "ask_address": "Aniq manzil yoki ko‘chani kiriting (masalan: 9-mavze, 12-uy):",
    "ask_location": (
        "Obyekt geolokatsiyasini yuborishingiz yoki pastdagi tugma orqali o‘tkazib "
        "yuborishingiz mumkin:"
    ),
    "btn_send_location": "📍 Joylashuvni yuborish",
    "btn_skip": "➡️ O‘tkazib yuborish",
    "ask_rooms": "Xonalar sonini kiriting (faqat musbat son, masalan: 3):",
    "invalid_rooms": "Noto‘g‘ri xonalar soni. Iltimos, musbat butun son kiriting (masalan: 2):",
    "ask_total_area": "Umumiy maydonni m² da kiriting (masalan: 75.5):",
    "invalid_area": "Noto‘g‘ri maydon. Iltimos, noldan katta musbat son kiriting (masalan: 65):",
    "ask_floor": "Obyekt joylashgan qavatni kiriting (masalan: 5):",
    "invalid_floor": "Noto‘g‘ri qavat raqami. Iltimos, butun son kiriting (masalan: 3):",
    "ask_total_floors": "Binoning umumiy qavatlari sonini kiriting (masalan: 9):",
    "invalid_total_floors": (
        "Binoning umumiy qavati xonadon qavatidan kam bo‘lmasligi va musbat son bo‘lishi kerak:"
    ),
    "ask_condition": "Ta’mir holatini tanlang:",
    "ask_furniture": "Mebel va maishiy texnika bormi?",
    "ask_cadastre": "Kadastr hujjatlari holatini tanlang:",
    "ask_price": "Narxni kiriting (faqat musbat son, masalan: 85000):",
    "invalid_price": "Noto‘g‘ri narx. Iltimos, noldan katta musbat son kiriting:",
    "ask_currency": "Valyutani tanlang:",
    "ask_negotiable": "Narx kelishiladimi (savdolashish bormi)?",
    "ask_description": (
        "Obyekt haqida qo‘shimcha tavsif yozing (yoki 'yo‘q' deb yuboring):"
    ),
    "ask_photos": (
        "Obyekt fotosuratlarini yuboring (kamida 1 ta, ko‘pi bilan 15 ta).\n"
        "Yuklab bo‘lgach, pastdagi '✅ Rasmlar tayyor' tugmasini bosing:"
    ),
    "btn_photos_ready": "✅ Rasmlar tayyor",
    "photo_received": "Fotosurat qabul qilindi. Jami rasmlar: {count} ta.",
    "photo_duplicate": "Bu fotosurat allaqachon qo‘shilgan.",
    "photo_max_reached": "Maksimal 15 ta rasm qabul qilindi. '✅ Rasmlar tayyor' tugmasini bosing.",
    "photo_min_error": "Kamida 1 ta rasm yuborishingiz kerak!",
    "preview_title": "🏠 E'lon ma'lumotlari tekshiruvi:",
    "btn_confirm_submit": "✅ Tasdiqlash va yuborish",
    "btn_cancel_submit": "✏️ Bekor qilish",
    "submission_success": (
        "✅ E'loningiz qabul qilindi.\n\n"
        "Broker tekshiruvidan so‘ng e'lon faollashtiriladi."
    ),
    "my_properties_empty": "Sizda hali birorta ham e'lon mavjud emas.",
    "my_properties_title": "🏘 Sizning e'lonlaringiz ro‘yxati:",
    # Review
    "review_no_pending": "Hozirda tasdiqlash uchun navbatda e'lonlar yo‘q.",
    "review_item_title": "📋 Tekshiruvdagi e'lon ID #{id}:",
    "btn_review_approve": "✅ Tasdiqlash",
    "btn_review_reject": "❌ Rad etish",
    "ask_rejection_reason": "Iltimos, rad etish sababini batafsil yozing:",
    "listing_approved_broker": "E'lon #{id} muvaffaqiyatli tasdiqlandi.",
    "listing_rejected_broker": "E'lon #{id} rad etildi.",
    "approved_notification": "✅ Sizning #{id}-raqamli ko‘chmas mulk e'loningiz tasdiqlandi!",
    "rejected_notification": (
        "❌ Sizning #{id}-raqamli ko‘chmas mulk e'loningiz rad etildi.\n\nSabab: {reason}"
    ),
    "unauthorized_review": "Sizda e'lonlarni tekshirish vakolati mavjud emas.",
    # Settings
    "settings_title": "⚙️ Sozlamalar bo‘limi:",
    "btn_change_language": "🌐 Tilni o‘zgartirish",
    "btn_back": "🔙 Orqaga",
    "language_updated": "Til muvaffaqiyatli o‘zgartirildi.",
    # Commands
    "help_text": (
        "🏢 UyAI — Ko‘chmas mulk aqlli Telegram platformasi.\n\n"
        "Bu tizim orqali uylarni sotib olish, sotish, ijaraga berish va bozor narxini "
        "AI orqali baholash imkoniyati yaratiladi.\n\n"
        "Hozirda platforma asosiy poydevor va ro‘yxatga olish bosqichida ishlamoqda. "
        "Yangi xizmatlar bosqichma-bosqich qo‘shiladi.\n\n"
        "Buyruqlar:\n"
        "/start - Tizimni ishga tushirish\n"
        "/help - Yordam va ma’lumot\n"
        "/cancel - Joriy jarayonni bekor qilish"
    ),
    "cancel_text": "Jarayon bekor qilindi.",
    "generic_error": "Xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko‘ring.",
}

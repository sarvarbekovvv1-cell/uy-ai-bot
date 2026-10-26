"""Uzbek localization dictionary."""

MESSAGES: dict[str, str] = {
    # Language & Selection
    "choose_language": "Tilni tanlang / Выберите язык:",
    "btn_uz": "🇺🇿 O‘zbekcha",
    "btn_ru": "🇷🇺 Русский",
    "btn_en": "🇺🇸 English",
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
        "💰 Ko‘chmas mulk sotish bo‘yicha e’lon berish boshlandi.\nIltimos, obyekt turini tanlang:"
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
    "ask_description": ("Obyekt haqida qo‘shimcha tavsif yozing (yoki 'yo‘q' deb yuboring):"),
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
        "✅ E'loningiz qabul qilindi.\n\nBroker tekshiruvidan so‘ng e'lon faollashtiriladi."
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
    # Search & Discovery
    "search_start_sale": (
        "🏠 Uy sotib olish bo‘yicha qidiruv:\nQanday ko‘chmas mulk turini qidiryapsiz?"
    ),
    "search_start_rent": (
        "🔑 Uy ijaraga olish bo‘yicha qidiruv:\nQanday ko‘chmas mulk turini qidiryapsiz?"
    ),
    "btn_type_all": "🌐 Barchasi",
    "type_apartment": "🏢 Kvartira",
    "type_house": "🏡 Hovli / Uy",
    "type_commercial": "🏬 Tijorat",
    "type_land": "🌱 Yer uchastkasi",
    "search_ask_region": "📍 Hudud (viloyat yoki shahar) nomini kiriting (masalan: Toshkent):",
    "search_ask_district": "📍 Tumanni kiriting yoki o‘tkazib yuboring (masalan: Chilonzor):",
    "search_ask_rooms": "🚪 Xonalar sonini tanlang:",
    "btn_rooms_any": "Farqi yo‘q",
    "search_ask_min_price": "💰 Minimal narxni kiriting (raqamda) yoki o‘tkazib yuboring:",
    "search_ask_max_price": "💰 Maksimal narxni kiriting (raqamda) yoki o‘tkazib yuboring:",
    "search_ask_currency": "💵 Qidirilayotgan narx valyutasini tanlang:",
    "search_ask_min_area": "📐 Minimal maydonni kiriting (m² da) yoki o‘tkazib yuboring:",
    "search_searching": "🔎 Mos e'lonlar qidirilmoqda...",
    "search_no_results": "😕 Talablaringizga mos e'lon topilmadi.",
    "search_results_found": "✅ Qidiruvingiz bo‘yicha mos e'lonlar (Sahifa {page}/{total_pages}):",
    "btn_restart_search": "🔄 Qidiruvni o‘zgartirish",
    "btn_details": "👁 Batafsil",
    "btn_fav_add": "❤️ Saqlash",
    "btn_fav_remove": "💔 Saqlanganlardan olib tashlash",
    "fav_added_alert": "✅ E'lon saqlanganlarga qo‘shildi.",
    "fav_removed_alert": "❌ E'lon saqlanganlardan olib tashlandi.",
    "btn_prev": "⬅️ Oldingi",
    "btn_next": "➡️ Keyingi",
    "property_not_found": "Ushbu e'lon mavjud emas yoki faol emas.",
    "saved_properties_title": "❤️ Siz saqlagan uylar ro‘yxati:",
    "saved_properties_empty": "Sizda hali saqlangan e'lonlar yo‘q.",
    "price_invalid_number": "Iltimos, narxni faqat musbat raqamda kiriting.",
    "price_range_error": "Maksimal narx minimal narxdan kam bo‘lishi mumkin emas.",
    "area_invalid_number": "Iltimos, maydonni to‘g‘ri musbat raqamda kiriting.",
    "detail_title": "📋 Ko‘chmas mulk batafsil ma'lumoti (#{id}):",
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
    # Phase 5: Appointments & Broker Contact
    "btn_book_viewing": "📅 Ko‘rishga yozilish",
    "btn_contact_broker_action": "👨‍💼 Broker bilan bog‘lanish",
    "btn_date_today": "📅 Bugun",
    "btn_date_tomorrow": "📅 Ertaga",
    "btn_date_custom": "📅 Boshqa sana",
    "btn_send_request": "✅ So‘rov yuborish",
    "btn_claim_request": "📥 Qabul qilib olish",
    "btn_accept_request": "✅ Qabul qilish",
    "btn_reject_request": "❌ Rad etish",
    "btn_complete_request": "🏁 Yakunlash",
    "btn_cancel_request": "❌ Bekor qilish",
    "btn_confirm_cancel": "✅ Ha, bekor qilish",
    "btn_keep_request": "Ortga",
    "outcome_interested": "👍 Qiziqdi",
    "outcome_not_interested": "👎 Qiziqmadi",
    "outcome_reschedule": "🔁 Qayta rejalashtirish",
    "outcome_no_show": "🚫 Kelmadi",
    "viewing_ask_date": "📅 Uyni ko‘rish uchun qulay sanani tanlang:",
    "viewing_ask_custom_date": (
        "Iltimos, sanani quyidagi formatda kiriting: <b>KK.OO.YYYY</b> (masalan, 28.10.2026):"
    ),
    "viewing_invalid_date": (
        "Noto‘g‘ri sana formati yoki o‘tgan sana. Iltimos, qayta kiriting (KK.OO.YYYY):"
    ),
    "viewing_ask_time": "🕐 Afzal ko‘rgan vaqtingizni tanlang:",
    "viewing_ask_comment": (
        "Qo‘shimcha izoh yoki savolingiz bormi? (Izoh yozing yoki pastdagi tugmani bosing):"
    ),
    "viewing_preview_title": "📋 Ko‘rish so‘rovi tekshiruvi:",
    "viewing_submitted_success": (
        "✅ Ko‘rish so‘rovingiz yuborildi. "
        "Broker ko‘rib chiqqach va tasdiqlagach, uchrashuv belgilangan hisoblanadi."
    ),
    "broker_contact_confirm_prompt": (
        "👨‍💼 Ushbu ko‘chmas mulk bo‘yicha broker bilan bog‘lanish so‘rovini yuborishni "
        "tasdiqlaysizmi?"
    ),
    "broker_contact_submitted_success": (
        "✅ So‘rovingiz yuborildi. Broker tez orada siz bilan bog‘lanadi."
    ),
    "appointments_empty": "Sizda hali uchrashuv yoki broker so‘rovlari mavjud emas.",
    "appointments_title": "📅 <b>Mening uchrashuvlarim va so‘rovlarim:</b>",
    "cancel_confirm_prompt": "Haqiqatan ham ushbu so‘rovni bekor qilmoqchimisiz?",
    "cancel_request_success": "So‘rov bekor qilindi.",
    "broker_requests_empty": "Hozirda yangi so‘rovlar yo‘q.",
    "broker_requests_title": "📋 <b>Ko‘rish va broker so‘rovlari:</b>",
    "broker_claim_success": "So‘rov sizga biriktirildi.",
    "broker_accept_success": "So‘rov tasdiqlandi va mijozga xabar yuborildi.",
    "broker_ask_reject_reason": "Iltimos, so‘rovni rad etish sababini batafsil kiriting:",
    "broker_reject_success": "So‘rov rad etildi va mijozga xabar yuborildi.",
    "broker_select_outcome": "Ko‘rish natijasini tanlang:",
    "broker_complete_success": "Ko‘rish yakunlandi va natija saqlandi.",
    "customer_notify_accepted": (
        "✅ Sizning #{prop_id} bo‘yicha ko‘rish so‘rovingiz broker tomonidan tasdiqlandi!\n"
        "📅 Sana: {date}\n🕐 Vaqt: {time}"
    ),
    "customer_notify_contact_accepted": (
        "✅ Sizning #{prop_id} bo‘yicha broker bilan bog‘lanish so‘rovingiz qabul qilindi. "
        "Tez orada siz bilan bog‘lanishadi."
    ),
    "customer_notify_rejected": (
        "❌ Sizning #{prop_id} bo‘yicha so‘rovingiz rad etildi.\nSabab: {reason}"
    ),
    "customer_notify_completed": (
        "🏁 #{prop_id} bo‘yicha ko‘rish yakunlandi. Tashrifingiz uchun rahmat!"
    ),
    "duplicate_request_error": "Ushbu mulk bo‘yicha faol so‘rovingiz allaqachon mavjud.",
    "property_unavailable_error": "Ko‘chmas mulk hozirda mavjud emas yoki faol emas.",
    "broker_permission_denied": "Sizda so‘rovlarni boshqarish vakolati mavjud emas.",
    # Broker Cabinet & Leads (Phase 6)
    "broker_cabinet_title": "💼 <b>Broker kabineti</b>\n\nQuyidagi bo‘limlardan birini tanlang:",
    "btn_unassigned_leads": "🔥 Yangi leadlar",
    "btn_my_leads": "📋 Mening leadlarim",
    "btn_tasks_today": "📅 Bugungi vazifalar",
    "btn_tasks_overdue": "⏰ Kechikkan vazifalar",
    "btn_lead_stats": "📊 Lead statistikasi",
    "btn_claim_lead": "📥 O‘zimga biriktirish",
    "btn_change_stage": "🔄 Bosqichni o‘zgartirish",
    "btn_add_task": "⏰ Vazifa rejalashtirish",
    "btn_add_note": "📝 Eslatma yozish",
    "btn_lead_history": "📜 Tarix",
    "btn_back_to_cabinet": "💼 Broker kabineti",
    "leads_empty_unassigned": "Hozirda yangi (biriktirilmagan) leadlar mavjud emas.",
    "leads_empty_my": "Sizda hozirda faol leadlar mavjud emas.",
    "tasks_empty_today": "Bugun uchun rejalashtirilgan vazifalar yo‘q.",
    "tasks_empty_overdue": "Kechikkan vazifalar yo‘q, barchasi o‘z vaqtida!",
    "lead_details_title": "📌 <b>Lead #{lead_id} tafsilotlari:</b>",
    "lead_stage_prompt": "Lead uchun yangi bosqichni tanlang:",
    "lead_lost_reason_prompt": "Leadni bekor qilish (Lost) sababini tanlang:",
    "lead_claimed_success": "✅ Lead muvaffaqiyatli o‘zingizga biriktirildi.",
    "lead_stage_updated": "✅ Lead bosqichi o‘zgartirildi: <b>{stage}</b>",
    "lead_ask_note": "📝 Lead bo‘yicha ichki eslatma matnini kiriting:",
    "lead_note_saved": "✅ Eslatma saqlandi.",
    "fu_ask_type": "⏰ Qanday vazifa rejalashtirmoqchisiz?",
    "fu_ask_time": "🕐 Vazifani bajarish vaqtini tanlang:",
    "fu_ask_note": (
        "💬 Vazifa bo‘yicha qo‘shimcha izoh kiriting (yoki o‘tkazib yuborish uchun /skip yozing):"
    ),
    "fu_created_success": "✅ Vazifa muvaffaqiyatli rejalashtirildi: {due_at}",
    "fu_completed_success": "✅ Vazifa bajarildi deb belgilandi.",
    "fu_cancelled_success": "❌ Vazifa bekor qilindi.",
    "stage_new": "Yangi",
    "stage_contacted": "Bog‘lanildi",
    "stage_qualified": "Saralandi",
    "stage_viewing_scheduled": "Ko‘rish belgilandi",
    "stage_negotiation": "Muzokara",
    "stage_won": "Muvaffaqiyatli (Won)",
    "stage_lost": "Bekor qilindi (Lost)",
    "lost_reason_price": "💰 Narx to‘g‘ri kelmadi",
    "lost_reason_not_interested": "🚫 Mijoz qiziqmadi",
    "lost_reason_competitor": "🏢 Boshqa variant topdi",
    "lost_reason_property_unavailable": "🏚 Mulk sotilgan/ijaraga berilgan",
    "lost_reason_no_response": "📵 Aloqaga chiqmadi",
    "lost_reason_other": "💬 Boshqa sabab",
    "task_call": "📞 Qo‘ng‘iroq",
    "task_message": "💬 Xabar",
    "task_meeting": "🤝 Uchrashuv",
    "task_other": "📋 Boshqa",
    "lead_stats_title": "📊 <b>Broker faoliyati statistikasi:</b>",
    # AI Broker
    "btn_ai_exit": "❌ Suhbatni yakunlash",
    "ai_welcome": (
        "🤖 <b>AI Broker ishga tushdi!</b>\n\n"
        "Menga qanday ko‘chmas mulk qidirayotganingizni oddiy so‘zlar bilan yozing.\n\n"
        "<i>Masalan:</i>\n"
        "• «Chilonzordan 2 xonali 100 ming dollargacha kvartira kerak»\n"
        "• «Yunusobodda 3 xonali ijaraga uy bormi?»\n"
        "• «#1 uy nechanchi qavatda?»\n"
        "• «#1 uyni ko‘rishga yozilmoqchiman»\n\n"
        "Suhbatni yakunlash uchun quyidagi tugmani bosing."
    ),
    "ai_exit_confirmation": "🤖 AI broker bilan suhbat yakunlandi. Siz asosiy menyudasiz.",
    "ai_disabled": (
        "🤖 AI Broker xizmati hozircha vaqtincha faol emas. Tez orada ishga tushiriladi!"
    ),
    "ai_fallback_error": (
        "🤖 AI Broker hozircha javob bera olmadi. "
        "Qidiruv menyusidan foydalanishingiz yoki broker bilan bog‘lanishingiz mumkin."
    ),
    "ai_rate_limited": "⏳ Iltimos, xabarlar oralig‘ida biroz kuting.",
    "ai_search_found": "🔍 Talabingizga mos <b>{count}</b> ta e'lon topildi:",
    "ai_search_not_found": (
        "🔍 Talabingizga aynan mos e'lon topilmadi.\n\n"
        "Qidiruv shartlarini (narx oralig‘i, tuman, xonalar soni) o‘zgartirib ko‘rishingiz mumkin."
    ),
    "ai_property_not_found": "Bunday raqamli yoki faol ko‘chmas mulk topilmadi.",
    "ai_clarification_needed": "Iltimos, talabingizni aniqlashtiring: {question}",
    "ai_human_broker_suggest": (
        "Ushbu masala bo‘yicha professional brokerimiz bilan bog‘lanishingizni tavsiya qilamiz."
    ),
    "ai_general_disclaimer": (
        "\n\n⚠️ <i>Eslatma: AI maslahati rasmiy yuridik yoki moliyaviy xulosa hisoblanmaydi. "
        "Muhim bitimlarda mutaxassis bilan maslahatlashing.</i>"
    ),
    # Phase 8: Property Valuation
    "val_welcome": (
        "📊 <b>UyAI — Bozor baholash xizmati</b>\n\n"
        "Ushbu xizmat UyAI bazasidagi tasdiqlangan e'lonlar va sun'iy intellekt tahlili "
        "asosida mulkingizning <b>taxminiy bozor bahosini</b> aniqlab beradi.\n\n"
        "⚠️ <i>Eslatma: Bu rasmiy ekspertiza, bank yoki kadastr baholashi emas, "
        "balki joriy bozor e'lonlariga asoslangan ko‘rsatkichdir.</i>\n\n"
        "Boshlash uchun mulk bo‘yicha operatsiya turini tanlang:"
    ),
    "val_unsupported_type": (
        "ℹ️ <b>Diqqat:</b> Hozirgi bosqichda avtomatik bozor baholash faqat <b>kvartira</b> "
        "va <b>hovli uylar</b> uchun mavjud.\n\n"
        "Tijorat ko‘chmas mulki yoki yer uchastkalari bo‘yicha aniq baho olish uchun "
        "«👨‍💼 Broker bilan bog‘lanish» xizmatidan foydalanishingiz mumkin."
    ),
    "val_choose_listing_type": "Mulk bo‘yicha operatsiya turini tanlang:",
    "val_choose_property_type": "Ko‘chmas mulk turini tanlang:",
    "val_choose_region": "Hududni tanlang yoki nomini yozing (masalan, Toshkent shahri):",
    "val_choose_district": "Tumanni tanlang yoki yozing (masalan, Chilonzor):",
    "val_choose_rooms": "Xonalar sonini tanlang:",
    "val_ask_area": "Mulkning umumiy maydonini m² da kiriting (masalan, 56 yoki 72.5):",
    "val_invalid_area": (
        "Iltimos, maydonni noldan katta musbat son ko‘rinishida kiriting (masalan: 65):"
    ),
    "val_choose_condition": "Mulkning ta'mirlanish holatini tanlang:",
    "val_ask_floor": (
        "Qavat va binoning umumiy qavatlar sonini kiriting (masalan: <b>4/9</b> yoki <b>3</b>).\n"
        "Agar bilmasangiz, o‘tkazib yuborishingiz mumkin:"
    ),
    "val_choose_currency": "Baholash valyutasini tanlang:",
    "val_calculating": "⏳ <i>Bozor ma'lumotlari tahlil qilinmoqda...</i>",
    "val_insufficient_data": (
        "🔍 <b>Taqqoslama ma'lumotlar yetarli emas</b>\n\n"
        "Afsuski, bazada kiritilgan parametrlarga mos keluvchi yetarli tasdiqlangan "
        "e'lonlar topilmadi.\n\n"
        "💡 <i>Maslahat:</i> Ko‘chmas mulk bo‘yicha to‘g‘ri narxni belgilash uchun "
        "professional brokerimiz bilan bog‘lanishingiz mumkin."
    ),
    "val_card_title": "📊 <b>AI BOZOR BAHOSI</b>",
    "val_comps_header": "🏘 <b>Tahlil qilingan o‘xshash tasdiqlangan e'lonlar:</b>\n",
    "val_no_comps": "Taqqoslangan e'lonlar mavjud emas.",
}

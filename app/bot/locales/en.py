"""English localization dictionary."""

MESSAGES: dict[str, str] = {
    # Language & Selection
    "choose_language": "Select language / Tilni tanlang / Выберите язык:",
    "btn_uz": "🇺🇿 O‘zbekcha",
    "btn_ru": "🇷🇺 Русский",
    "btn_en": "🇺🇸 English",
    # Consent
    "consent_text": (
        "While using the UyAI service, your Telegram profile and contact details provided "
        "by you will be processed for service delivery purposes.\n\n"
        "By continuing, you agree to these terms."
    ),
    "btn_consent_accept": "✅ I agree",
    "btn_consent_decline": "❌ Cancel",
    "consent_declined": (
        "Registration cancelled. Consent is required to use the service. "
        "To start again, click /start."
    ),
    # Name & Phone
    "ask_name": "Please enter your name:",
    "invalid_name": "Name must be between 2 and 50 characters long. Please enter again:",
    "ask_phone": "Please send your contact phone number using the button below:",
    "btn_send_phone": "📱 Send phone number",
    "invalid_contact_owner": (
        "Security notice: You must send the phone number belonging to your own Telegram account."
    ),
    "invalid_phone_format": (
        "Invalid phone number format. Please press the button below or type your number "
        "in the +998XXXXXXXXX format:"
    ),
    # Registration & Welcome
    "registration_complete": "Congratulations! Registration successfully completed.",
    "welcome_back": "🏢 Welcome back to UyAI!",
    "main_menu_title": "🏢 UyAI — Main Menu\nSelect one of the services below:",
    # Main Menu Buttons
    "btn_buy": "🏠 Buy property",
    "btn_rent": "🔑 Rent property",
    "btn_sell": "💰 Sell my property",
    "btn_lease": "🏡 Lease my property",
    "btn_valuation": "📊 Estimate property value",
    "btn_map": "📍 Search on map",
    "btn_ai_broker": "🤖 AI broker",
    "btn_favorites": "❤️ Saved properties",
    "btn_appointments": "📅 My viewings",
    "btn_contact_broker": "👨‍💼 Contact broker",
    "btn_my_properties": "🏘 My listings",
    "btn_settings": "⚙️ Settings",
    # Placeholder
    "feature_in_development": "This feature will be available in the next release.",
    # Property Submission
    "explain_sell_process": (
        "💰 Property sale listing wizard started.\nPlease choose property type:"
    ),
    "explain_rent_process": (
        "🏡 Property rental listing wizard started.\nPlease choose property type:"
    ),
    "ask_region": "Enter region or city (e.g., Tashkent):",
    "ask_district": "Enter district or neighborhood (e.g., Chilanzar):",
    "ask_address": "Enter exact address or street (e.g., Block 9, Apt 12):",
    "ask_location": (
        "You can send the property geolocation or skip using the button below:"
    ),
    "btn_send_location": "📍 Send location",
    "btn_skip": "➡️ Skip",
    "ask_rooms": "Enter number of rooms (positive number only, e.g., 3):",
    "invalid_rooms": "Invalid number of rooms. Please enter a positive integer (e.g., 2):",
    "ask_total_area": "Enter total area in m² (e.g., 75.5):",
    "invalid_area": "Invalid area. Please enter a positive number greater than zero (e.g., 65):",
    "ask_floor": "Enter the floor of the property (e.g., 5):",
    "invalid_floor": "Invalid floor number. Please enter an integer (e.g., 3):",
    "ask_total_floors": "Enter total floors of the building (e.g., 9):",
    "invalid_total_floors": (
        "Total building floors must be a positive number and cannot be less than property floor:"
    ),
    "ask_condition": "Select condition / renovation state:",
    "ask_furniture": "Is furniture and appliances included?",
    "ask_cadastre": "Select cadastre documentation status:",
    "ask_price": "Enter price (positive number only, e.g., 85000):",
    "invalid_price": "Invalid price. Please enter a positive number greater than zero:",
    "ask_currency": "Select currency:",
    "ask_negotiable": "Is price negotiable?",
    "ask_description": "Write additional description about property (or type 'none'):",
    "ask_photos": (
        "Send photos of the property (at least 1, up to 15 photos).\n"
        "When finished, click '✅ Photos ready' below:"
    ),
    "btn_photos_ready": "✅ Photos ready",
    "photo_received": "Photo received. Total photos: {count}.",
    "photo_duplicate": "This photo has already been uploaded.",
    "photo_max_reached": "Maximum 15 photos reached. Click '✅ Photos ready'.",
    "photo_min_error": "You must upload at least 1 photo!",
    "preview_title": "🏠 Property listing details check:",
    "btn_confirm_submit": "✅ Confirm and submit",
    "btn_cancel_submit": "✏️ Cancel",
    "submission_success": (
        "✅ Your listing has been submitted.\n\nIt will be activated after broker verification."
    ),
    "my_properties_empty": "You do not have any property listings yet.",
    "my_properties_title": "🏘 Your property listings:",
    # Review
    "review_no_pending": "No listings currently pending moderation.",
    "review_item_title": "📋 Moderation listing ID #{id}:",
    "btn_review_approve": "✅ Approve",
    "btn_review_reject": "❌ Reject",
    "ask_rejection_reason": "Please enter detailed reason for rejection:",
    "listing_approved_broker": "Listing #{id} successfully approved.",
    "listing_rejected_broker": "Listing #{id} rejected.",
    "approved_notification": "✅ Your property listing #{id} has been approved!",
    "rejected_notification": (
        "❌ Your property listing #{id} was rejected.\n\nReason: {reason}"
    ),
    "unauthorized_review": "You are not authorized to moderate listings.",
    # Search & Discovery
    "search_start_sale": (
        "🏠 Property purchase search:\nWhat type of property are you looking for?"
    ),
    "search_start_rent": (
        "🔑 Property rental search:\nWhat type of property are you looking for?"
    ),
    "btn_type_all": "🌐 All types",
    "type_apartment": "🏢 Apartment",
    "type_house": "🏡 House / Villa",
    "type_commercial": "🏬 Commercial",
    "type_land": "🌱 Land plot",
    "search_ask_region": "📍 Enter region or city (e.g., Tashkent):",
    "search_ask_district": "📍 Enter district or skip (e.g., Chilanzar):",
    "search_ask_rooms": "🚪 Select number of rooms:",
    "btn_rooms_any": "Any",
    "search_ask_min_price": "💰 Enter minimum price (number) or skip:",
    "search_ask_max_price": "💰 Enter maximum price (number) or skip:",
    "search_ask_currency": "💵 Select search currency:",
    "search_ask_min_area": "📐 Enter minimum area (m²) or skip:",
    "search_searching": "🔎 Searching matching listings...",
    "search_no_results": "😕 No listings found matching your criteria.",
    "search_results_found": "✅ Matching listings found (Page {page}/{total_pages}):",
    "btn_restart_search": "🔄 Change search criteria",
    "btn_details": "👁 Details",
    "btn_fav_add": "❤️ Save",
    "btn_fav_remove": "💔 Remove from saved",
    "fav_added_alert": "✅ Listing saved to favorites.",
    "fav_removed_alert": "❌ Listing removed from favorites.",
    "btn_prev": "⬅️ Previous",
    "btn_next": "➡️ Next",
    "property_not_found": "This listing is not available or inactive.",
    "saved_properties_title": "❤️ Your saved properties:",
    "saved_properties_empty": "You do not have any saved listings yet.",
    "price_invalid_number": "Please enter price as a positive number only.",
    "price_range_error": "Maximum price cannot be less than minimum price.",
    "area_invalid_number": "Please enter area as a valid positive number.",
    "detail_title": "📋 Property details (#{id}):",
    # Settings
    "settings_title": "⚙️ Settings:",
    "btn_change_language": "🌐 Change language",
    "btn_back": "🔙 Back",
    "language_updated": "Language successfully updated.",
    # Commands
    "help_text": (
        "🏢 UyAI — Smart Real Estate Telegram Platform.\n\n"
        "This platform helps you buy, sell, rent properties and estimate market values "
        "using artificial intelligence.\n\n"
        "Commands:\n"
        "/start - Start the system\n"
        "/help - Help & information\n"
        "/cancel - Cancel current operation"
    ),
    "cancel_text": "Operation cancelled.",
    "generic_error": "An error occurred. Please try again later.",
    # Phase 5: Appointments & Broker Contact
    "btn_book_viewing": "📅 Book a viewing",
    "btn_contact_broker_action": "👨‍💼 Contact broker",
    "btn_date_today": "📅 Today",
    "btn_date_tomorrow": "📅 Tomorrow",
    "btn_date_custom": "📅 Other date",
    "btn_send_request": "✅ Send request",
    "btn_claim_request": "📥 Claim request",
    "btn_accept_request": "✅ Accept",
    "btn_reject_request": "❌ Reject",
    "btn_complete_request": "🏁 Complete",
    "btn_cancel_request": "❌ Cancel request",
    "btn_confirm_cancel": "✅ Yes, cancel",
    "btn_keep_request": "Back",
    "outcome_interested": "👍 Interested",
    "outcome_not_interested": "👎 Not interested",
    "outcome_reschedule": "🔁 Reschedule",
    "outcome_no_show": "🚫 No show",
    "viewing_ask_date": "📅 Select a convenient date to view property:",
    "viewing_ask_custom_date": (
        "Please enter date in format: <b>DD.MM.YYYY</b> (e.g., 28.10.2026):"
    ),
    "viewing_invalid_date": (
        "Invalid date format or date is in the past. Please enter again (DD.MM.YYYY):"
    ),
    "viewing_ask_time": "🕐 Select preferred time:",
    "viewing_ask_comment": (
        "Do you have any comments or questions? (Type comment or press button below):"
    ),
    "viewing_preview_title": "📋 Viewing request check:",
    "viewing_submitted_success": (
        "✅ Your viewing request has been submitted. "
        "The appointment is confirmed once the broker reviews and accepts it."
    ),
    "broker_contact_confirm_prompt": (
        "👨‍💼 Do you confirm sending a contact request for this property to a broker?"
    ),
    "broker_contact_submitted_success": (
        "✅ Your request has been sent. A broker will contact you shortly."
    ),
    "appointments_empty": "You do not have any viewing appointments or broker requests yet.",
    "appointments_title": "📅 <b>My appointments and requests:</b>",
    "cancel_confirm_prompt": "Are you sure you want to cancel this request?",
    "cancel_request_success": "Request has been cancelled.",
    "broker_requests_empty": "No new requests at the moment.",
    "broker_requests_title": "📋 <b>Viewing and broker requests:</b>",
    "broker_claim_success": "Request assigned to you.",
    "broker_accept_success": "Request accepted and client notified.",
    "broker_ask_reject_reason": "Please enter detailed reason for rejection:",
    "broker_reject_success": "Request rejected and client notified.",
    "broker_select_outcome": "Select viewing outcome:",
    "broker_complete_success": "Viewing completed and outcome recorded.",
    "customer_notify_accepted": (
        "✅ Your viewing request for #{prop_id} has been confirmed by broker!\n"
        "📅 Date: {date}\n🕐 Time: {time}"
    ),
    "customer_notify_contact_accepted": (
        "✅ Your broker contact request for #{prop_id} has been accepted. "
        "You will be contacted shortly."
    ),
    "customer_notify_rejected": (
        "❌ Your request for #{prop_id} was rejected.\nReason: {reason}"
    ),
    "customer_notify_completed": (
        "🏁 Viewing for #{prop_id} is completed. Thank you for your visit!"
    ),
    "duplicate_request_error": "You already have an active request for this property.",
    "property_unavailable_error": "Property is currently unavailable or inactive.",
    "broker_permission_denied": "You do not have permission to manage requests.",
    # Broker Cabinet & Leads (Phase 6)
    "broker_cabinet_title": "💼 <b>Broker Cabinet</b>\n\nSelect a section below:",
    "btn_unassigned_leads": "🔥 New leads",
    "btn_my_leads": "📋 My leads",
    "btn_tasks_today": "📅 Today's tasks",
    "btn_tasks_overdue": "⏰ Overdue tasks",
    "btn_lead_stats": "📊 Lead statistics",
    "btn_claim_lead": "📥 Claim lead",
    "btn_change_stage": "🔄 Change stage",
    "btn_add_task": "⏰ Schedule task",
    "btn_add_note": "📝 Add note",
    "btn_lead_history": "📜 History",
    "btn_back_to_cabinet": "💼 Broker cabinet",
    "leads_empty_unassigned": "No new unassigned leads available.",
    "leads_empty_my": "You currently have no active leads.",
    "tasks_empty_today": "No tasks scheduled for today.",
    "tasks_empty_overdue": "No overdue tasks, all on time!",
    "lead_details_title": "📌 <b>Lead #{lead_id} details:</b>",
    "lead_stage_prompt": "Select new stage for lead:",
    "lead_lost_reason_prompt": "Select reason for closing (Lost) lead:",
    "lead_claimed_success": "✅ Lead successfully assigned to you.",
    "lead_stage_updated": "✅ Lead stage updated: <b>{stage}</b>",
    "lead_ask_note": "📝 Enter internal note text for lead:",
    "lead_note_saved": "✅ Note saved.",
    "fu_ask_type": "⏰ What type of task do you want to schedule?",
    "fu_ask_time": "🕐 Select task execution time:",
    "fu_ask_note": (
        "💬 Enter additional note for task (or type /skip to skip):"
    ),
    "fu_created_success": "✅ Task successfully scheduled: {due_at}",
    "fu_completed_success": "✅ Task marked as completed.",
    "fu_cancelled_success": "❌ Task cancelled.",
    "stage_new": "New",
    "stage_contacted": "Contacted",
    "stage_qualified": "Qualified",
    "stage_viewing_scheduled": "Viewing scheduled",
    "stage_negotiation": "Negotiation",
    "stage_won": "Closed Won",
    "stage_lost": "Closed Lost",
    "lost_reason_price": "💰 Price issue",
    "lost_reason_not_interested": "🚫 Client lost interest",
    "lost_reason_competitor": "🏢 Chose competitor / another option",
    "lost_reason_property_unavailable": "🏚 Property sold / leased",
    "lost_reason_no_response": "📵 No response",
    "lost_reason_other": "💬 Other reason",
    "task_call": "📞 Call",
    "task_message": "💬 Message",
    "task_meeting": "🤝 Meeting",
    "task_other": "📋 Other",
    "lead_stats_title": "📊 <b>Broker Activity Statistics:</b>",
    # AI Broker
    "btn_ai_exit": "❌ Exit chat",
    "ai_welcome": (
        "🤖 <b>AI Broker is active!</b>\n\n"
        "Tell me what real estate you are looking for in plain words.\n\n"
        "<i>Examples:</i>\n"
        "• «Looking for a 2-room apartment in Chilanzar up to $100k»\n"
        "• «Are there 3-room apartments for rent in Yunusabad?»\n"
        "• «What floor is property #1 on?»\n"
        "• «I want to book a viewing for property #1»\n\n"
        "Click the button below to end the chat."
    ),
    "ai_exit_confirmation": "🤖 AI broker conversation ended. You are now in the main menu.",
    "ai_disabled": (
        "🤖 AI Broker service is temporarily disabled. It will be available soon!"
    ),
    "ai_fallback_error": (
        "🤖 AI Broker could not answer right now. "
        "You can use the search menu or contact a broker directly."
    ),
    "ai_rate_limited": "⏳ Please wait a moment between messages.",
    "ai_search_found": "🔍 Found <b>{count}</b> matching listings for your request:",
    "ai_search_not_found": (
        "🔍 No exact matching listings found.\n\n"
        "Try adjusting search criteria (price range, district, number of rooms)."
    ),
    "ai_property_not_found": "Property with this ID was not found or is inactive.",
    "ai_clarification_needed": "Please clarify your request: {question}",
    "ai_human_broker_suggest": (
        "We recommend speaking with our professional human broker on this matter."
    ),
    "ai_general_disclaimer": (
        "\n\n⚠️ <i>Note: AI recommendations do not constitute official legal or financial advice. "
        "Consult a specialist for important transactions.</i>"
    ),
    # Phase 8: Property Valuation
    "val_welcome": (
        "📊 <b>UyAI — Market Valuation Service</b>\n\n"
        "This service calculates an <b>estimated market value</b> of your property based on "
        "verified listings in the UyAI database and AI analysis.\n\n"
        "⚠️ <i>Note: This is not an official legal, bank, or cadastral appraisal, "
        "but an indicative metric based on current active market comps.</i>\n\n"
        "Select operation type to begin:"
    ),
    "val_unsupported_type": (
        "ℹ️ <b>Notice:</b> Automated valuation is currently supported for <b>apartments</b> "
        "and <b>houses</b> only.\n\n"
        "For commercial real estate or land plots, please use «👨‍💼 Contact broker»."
    ),
    "val_choose_listing_type": "Select operation type for property:",
    "val_choose_property_type": "Select property type:",
    "val_choose_region": "Select region or type name (e.g., Tashkent):",
    "val_choose_district": "Select district or type name (e.g., Chilanzar):",
    "val_choose_rooms": "Select number of rooms:",
    "val_ask_area": "Enter total property area in m² (e.g., 56 or 72.5):",
    "val_invalid_area": (
        "Please enter area as a positive number greater than zero (e.g., 65):"
    ),
    "val_choose_condition": "Select condition / renovation state of property:",
    "val_ask_floor": (
        "Enter floor and total building floors (e.g., <b>4/9</b> or <b>3</b>).\n"
        "If unknown, you can skip:"
    ),
    "val_choose_currency": "Select valuation currency:",
    "val_calculating": "⏳ <i>Analyzing market data...</i>",
    "val_insufficient_data": (
        "🔍 <b>Insufficient comparable market data</b>\n\n"
        "Unfortunately, not enough verified listings matching these parameters were found.\n\n"
        "💡 <i>Tip:</i> You can contact a professional broker to get an accurate estimate."
    ),
    "val_card_title": "📊 <b>AI MARKET VALUATION</b>",
    "val_comps_header": "🏘 <b>Analyzed comparable verified listings:</b>\n",
    "val_no_comps": "No comparable listings available.",
    "val_payment_service_unconfigured": (
        "📊 <b>AI Property Market Valuation</b>\n\n"
        "This premium service is being integrated with official payment systems. "
        "Payment settings are currently being finalized. Online payment via Click "
        "and Payme will be available shortly."
    ),
    "val_order_summary_title": "📋 <b>Submitted Property Details:</b>",
    "val_price_notice": (
        "💰 <b>Service Fee:</b> {price} UZS\n\n"
        "To receive full AI market analysis and valuation report, "
        "please choose your payment method:"
    ),
    "val_payment_pending": (
        "⏳ <b>Payment not confirmed yet</b> (#{order_id}).\n\n"
        "Please complete payment via Click or Payme. Once verified by the server, "
        "your AI valuation report will appear here automatically."
    ),
    "val_payment_cancelled": "❌ Payment process cancelled.",
}

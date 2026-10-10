# Simple, dependency-free translation system.
#
# Why not Django's built-in i18n (gettext)? Django's standard approach needs
# the GNU gettext toolchain (msgfmt/msguniq) installed on the machine to
# compile .po files into .mo files, which is an extra install on Windows.
# For a project this size, a plain Python dict is easier to maintain: add a
# key here once, use it in every template with `{{ T.key }}`, no compiling.
#
# NOTE: This only covers static UI text (labels, buttons, messages). It does
# NOT translate database content (product names, descriptions, category
# names) since those are user-entered data, not template strings.

from django.utils.functional import lazy

DEFAULT_LANGUAGE = 'mn'

AVAILABLE_LANGUAGES = [
    ('mn', 'МН'),
    ('en', 'EN'),
]

COOKIE_NAME = 'site_lang'

# Category names and employee positions come from the database (a single text
# column), so they can't be swapped via the TRANSLATIONS dict below. These are
# manual lookup tables instead, used in BOTH directions: a value stored in
# English ("Furniture") is shown in Mongolian on the Mongolian site, and one stored
# in Mongolian ("Хувцас") is shown in English on the English site - whichever
# language it was typed in. Add a line any time you add a category / position:
#   (Mongolian name, English name[, extra spellings that also mean the same])
# A name that isn't listed is shown as-is (untranslated), nothing breaks.
CATEGORY_PAIRS = [
    ('Электрон бараа', 'Electronics', 'Electronic'),
    ('Хувцас', 'Clothing', 'Clothes'),
    ('Хүнс', 'Food', 'Хунс'),
    ('Чихэр', 'Sweets', 'Candy'),
    ('Утас', 'Phone', 'Phones'),
    ('Тавилга', 'Furniture'),
    ('Машин', 'Car', 'Mashin', 'Cars'),
]

POSITION_PAIRS = [
    ('Админ', 'Admin'),
    ('Оператор', 'Operator'),
    ('Хүргэгч', 'Driver', 'Courier'),
    ('Ажилтан', 'Employee'),
]


def _build_index(pairs):
    index = {}
    for mn, en, *aliases in pairs:
        for variant in (mn, en, *aliases):
            index[variant.strip().casefold()] = {'mn': mn, 'en': en}
    return index


_CATEGORY_INDEX = _build_index(CATEGORY_PAIRS)
_POSITION_INDEX = _build_index(POSITION_PAIRS)


def _translate_value(index, name, lang):
    if not name:
        return name
    pair = index.get(str(name).strip().casefold())
    return pair['en' if lang == 'en' else 'mn'] if pair else name


def translate_category_name(name, lang):
    """Display name of a category in the given language ('mn' / 'en'), whichever
    language it is stored in. Unknown names are returned unchanged."""
    return _translate_value(_CATEGORY_INDEX, name, lang)


def translate_position(name, lang):
    """Same for an employee's position (Admin / Operator / Хүргэгч ...)."""
    return _translate_value(_POSITION_INDEX, name, lang)

TRANSLATIONS = {
    'mn': {
        # Layout / site-wide
        'site_title': 'Цахим худалдааны веб',
        'footer_text': 'Цахим дэлгүүр',

        # Navbar
        'brand': 'Бараа',
        'nav_home': 'Эхлэл',
        'nav_about': 'Бидний тухай',
        'nav_categories': 'Ангилал',
        'nav_all_products': 'Бүх бүтээгдэхүүн',
        'nav_login': 'Нэвтрэх',
        'nav_register': 'Бүртгүүлэх',
        'nav_logout': 'Гарах',
        'search_placeholder': 'Хайх...',
        'search_button': 'Хайх',
        'search_recent': 'Сүүлийн хайлтууд',
        'search_clear': 'Цэвэрлэх',
        'search_no_recent': 'Сүүлийн хайлт байхгүй',
        'search_remove': 'Устгах',
        'search_recommended': 'Танд санал болгох',
        'search_did_you_mean': 'Та үүнийг хайсан уу?',
        'search_category': 'Ангилал',
        'search_no_exact': 'Яг тохирох үр дүн олдсонгүй. Үүнтэй төстэй үр дүн:',
        'cart_label': 'Сагс',

        # Home page
        'home_title': 'худалдаа',
        'home_subtitle': 'Худалдаа хийхэд зориулсан онлайн платформ',

        # Category page
        'category_subtitle': 'Ангилал дахь бүтээгдэхүүн',
        'add_product_btn': 'Бүтээгдэхүүн нэмэх',
        'empty_products_title': 'Бүтээгдэхүүн байхгүй байна',
        'empty_products_text': 'Энэ ангилалд одоогоор бүтээгдэхүүн нэмэгдээгүй байна.',
        'add_first_product_btn': 'Эхний бүтээгдэхүүн нэмэх',
        'modal_add_product_title': 'Шинэ бүтээгдэхүүн нэмэх',
        'form_name_label': 'Бүтээгдэхүүний нэр',
        'form_category_label': 'Ангилал',
        'form_price_label': 'Үнэ (₮)',
        'form_image_label': 'Зураг',
        'form_description_label': 'Тайлбар',
        'sale_checkbox_label': 'Хямдралтай бүтээгдэхүүн',
        'sale_price_label': 'Хямдрал үнэ (₮)',
        'form_stock_label': 'Үлдэгдэл (ширхэг)',
        'form_rating_label': 'Үнэлгээ (0-5)',
        'cancel_btn': 'Цуцлах',
        'save_btn': 'Хадгалах',

        # Product card / view toggle
        'product_detail_btn': 'Дэлгэрэнгүй',
        'view_grid_title': 'Сүлжээ (box) харагдац',
        'view_list_title': 'Жагсаалт (list) харагдац',

        # Sort / period filter bar
        'sort_label': 'Эрэмбэлэх',
        'sort_name_asc': 'Нэр (А-Я)',
        'sort_name_desc': 'Нэр (Я-А)',
        'sort_price_asc': 'Үнэ: Багаас их',
        'sort_price_desc': 'Үнэ: Ихээс бага',
        'sort_popularity': 'Эрэлттэй',
        'sort_rating': 'Үнэлгээ',
        'period_label': 'Хугацаа',
        'period_all': 'Бүх хугацаа',
        'period_daily': 'Өдрийн',
        'period_monthly': 'Сарын',
        'period_yearly': 'Жилийн',
        'filter_reset_title': 'Шүүлтүүр цэвэрлэх',

        # Search page
        'search_no_results_text': 'Хайлтын үр дүн олдсонгүй.',

        # About page
        'about_title': 'Бидний тухай',
        'about_text': 'Манай цахим худалдааны веб нь хэрэглэгчдэд хамгийн сайн онлайн худалдааны '
                       'туршлагыг санал болгох зорилготой. Бид өргөн хүрээний бүтээгдэхүүн, найдвартай '
                       'үйлчилгээ, хэрэглэгчийн дэмжлэгээрээ алдартай.',

        # Login page
        'login_title': 'Нэвтрэх',
        'login_subtitle': 'Манай дэлгүүрт тавтай морилно уу',
        'username_label': 'Нэвтрэх нэр',
        'password_label': 'Нууц үг',
        'login_btn': 'Нэвтрэх',

        # Register page
        'register_title': 'Бүртгэх хуудас',
        'register_subtitle': 'Манай дэлгүүрт бүртгүүлнэ үү',
        'register_btn': 'Бүртгүүлэх',
        'email_placeholder': 'Имэйл',
        'first_name_placeholder': 'Нэр',
        'last_name_placeholder': 'Овог',
        'username_placeholder': 'Нэвтрэх нэр',
        'password_placeholder': 'Нууц үг',
        'password_confirm_placeholder': 'Нууц үг давтах',
        'username_help_text': 'Нэвтрэх нэр 50 тэмдэгтээс бага байх ёстой.',
        'password_help_text': 'Нууц үг 8 тэмдэгтээс багагүй байх ёстой.',
        'password_confirm_help_text': 'Нууц үгийг дахин оруулна уу.',

        # Product detail page
        'sale_label': 'Хямдралтай',
        'back_btn': 'Буцах',
        'add_to_cart_btn': 'Сагсанд нэмэх',
        'quantity_label': 'Тоо ширхэг',
        'added_to_cart_feedback': 'Сагсанд нэмэгдлээ',
        'in_stock_label': 'ширхэг үлдсэн',
        'low_stock_label': 'Цөөн үлдсэн',
        'out_of_stock_label': 'Дууссан',
        'out_of_stock_btn': 'Дууссан',

        # Cart page
        'cart_page_title': 'Миний сагс',
        'table_product': 'Бүтээгдэхүүн',
        'table_quantity': 'Тоо ширхэг',
        'table_options': 'Сонголт',
        'table_price': 'Үнэ',
        'table_total': 'Нийт',
        'remove_btn': 'Устгах',
        'clear_cart_btn': 'Сагс хоослох',
        'total_amount_label': 'Нийт дүн',
        'empty_cart_text': 'Таны сагс хоосон байна.',

        # Flash messages (views.py)
        'msg_category_not_found': 'Тохирох ангилал олдсонгүй',
        'msg_admin_only_add_product': 'Зөвхөн админ бүтээгдэхүүн нэмэх боломжтой',
        'msg_product_added': 'Бүтээгдэхүүн амжилттай нэмэгдлээ!',
        'msg_form_invalid': 'Мэдээллийг зөв бөглөнө үү.',
        'msg_login_success': 'Амжилттай нэвтэрлээ',
        'msg_login_failed': 'Нэвтрэх нэр эсвэл нууц үг буруу байна',
        'msg_logout_success': 'Амжилттай гарлаа',
        'msg_register_success': 'Бүртгүүлсэнд баярлалаа. Одоо нэвтэрнэ үү.',
        'msg_register_failed': 'Бүртгүүлэхэд алдаа гарлаа. Мэдээллээ шалгаад дахин оролдоно уу.',
        'msg_search_no_results': 'Хайлтын үр дүн олдсонгүй',
                'msg_cart_empty': 'Сагс хоосон байна',
        'msg_order_confirmed': 'Захиалга амжилттай баталгаажлаа!',
        'msg_out_of_stock': 'Уучлаарай, энэ бараа дууссан байна.',
        'msg_insufficient_stock': 'Уучлаарай, зөвхөн {stock} ширхэг үлдсэн байна.',

        # Order confirm page
        'order_confirm_title': 'Захиалга баталгаажуулах',
        'customer_name': 'Нэр',
        'customer_phone': 'Утасны дугаар',
        'customer_address': 'Хаяг',
        'place_order_btn': 'Захиалга өгөх',
        'my_orders_title': 'Миний захиалгууд',
        'order_number_label': 'Захиалга',
        'no_orders_text': 'Танд одоогоор захиалга байхгүй байна.',

        # Employees page
        'employees_title': 'Ажилтнууд',
        'add_employee_btn': 'Ажилтан нэмэх',
        'add_employee_title': 'Шинэ ажилтан нэмэх',
        'add_employee_subtitle': 'Шинэ ажилтны бүртгэл үүсгэх',
        'table_username': 'Нэвтрэх нэр',
        'table_name': 'Нэр',
        'table_email': 'Имэйл',
        'table_role': 'Эрх',
        'role_admin': 'Админ',
        'role_employee': 'Ажилтан',
        'no_employees_text': 'Одоогоор ажилтан байхгүй байна.',
        'msg_employee_added': 'Ажилтан амжилттай нэмэгдлээ!',
        'position_placeholder': 'Албан тушаал',
        'phone_placeholder': 'Утасны дугаар',
        'table_position': 'Албан тушаал',
        'table_phone': 'Утас',

        # Profile page
        'profile_title': 'Миний профайл',
        'profile_subtitle': 'Хувийн мэдээллээ шинэчлэх',
        'nav_profile': 'Миний профайл',
        'nav_admin_panel': 'Админ хуудас',
        'customer_address_label': 'Гэрийн хаяг',
        'customer_address_placeholder': 'Гэрийн хаяг байршил',
        'msg_profile_updated': 'Мэдээлэл амжилттай шинэчлэгдлээ!',

        # ---- Admin panel: branding / chrome ----
        'admin_site_title': 'Bshop Админ',
        'admin_site_header': 'Bshop Админ',
        'admin_index_title': 'Удирдлагын самбар',
        'admin_lang_label': 'Хэл сонгох',
        'admin_theme_light_mode': 'Цагаан горим',
        'admin_theme_dark_mode': 'Харанхуй горим',

        # Admin panel: sidebar
        'admin_nav_stock': 'Агуулах',

        # Admin panel: dashboard (index.html)
        'admin_dashboard': 'Хяналтын самбар',
        'admin_revenue': 'Орлого',
        'admin_products': 'Бүтээгдэхүүн',
        'admin_orders': 'Захиалга',
        'admin_customers': 'Хэрэглэгчид',
        'admin_low_stock': 'Дуусах дөхсөн',
        'admin_overview': 'Тойм',
        'admin_details': 'Дэлгэрэнгүй',
        'admin_chart_soon': 'Захиалгын график удахгүй нэмэгдэнэ',

        # Admin panel: dashboard charts
        'admin_day_title': 'Өдрийн орлого (сүүлийн 14 хоног)',
        'admin_rev_title': 'Сарын орлого (сүүлийн 12 сар)',

        'admin_categories': 'Ангилал',
        'admin_pending_orders': 'Хүлээгдэж буй захиалга',
        'admin_completed_orders': 'Дууссан',
        'admin_low_stock_products': 'Үлдэгдэл багатай бараа',
        'admin_total_customers': 'Нийт хэрэглэгч',
        'admin_view_categories': 'Ангилал харах',
        'admin_recent_actions': 'Сүүлд хийсэн үйлдлүүд',
        'admin_nothing_yet': 'Одоогоор юу ч алга.',
        'admin_unknown': 'Тодорхойгүй',

        # Admin panel: stock page (stock.html)
        'admin_stock_title': 'Агуулах',
        'admin_total_stock_value': 'Нийт барааны үнийн дүн',
        'admin_in_stock': 'Хангалттай',
        'admin_low': 'Бага',
        'admin_out_of_stock': 'Дууссан',
        'admin_low_stock_status': 'Үлдэгдэл бага',
        'admin_total_products': 'Нийт бараа',
        'admin_total_stock_units': 'Нийт үлдэгдэл (ш)',
        'admin_inventory': 'Үлдэгдэл',
        'admin_product_list': 'Барааны жагсаалт',
        'admin_search_inventory': 'Бараа хайх',
        'admin_filters': 'Шүүлтүүр',
        'admin_all': 'Бүгд',
        'admin_add_product': 'Бараа нэмэх',
        'admin_col_name': 'Нэр',
        'admin_col_category': 'Ангилал',
        'admin_col_price': 'Үнэ',
        'admin_col_stock': 'Үлдэгдэл',
        'admin_col_status': 'Төлөв',
        'admin_col_is_active': 'Идэвхтэй эсэх',
        'admin_col_action': 'Үйлдэл',
        'admin_quantity_to_add': 'Нэмэх тоо ширхэг',
        'admin_no_products': 'Бараа олдсонгүй.',

        # Admin panel: model / app names shown in the sidebar
       'admin_app_store': 'Дэлгүүр',
        'admin_app_cart': 'Сагс',
        # Admin panel: "Reports" sidebar group (store/reports.py)
        'admin_app_reports': 'Тайлан',
        'admin_report_inventory': 'Агуулах / Бараа',
        'admin_report_orders': 'Захиалга',
        'admin_report_customers': 'Хэрэглэгч',
        'admin_report_from': 'Эхлэх огноо',
        'admin_report_to': 'Дуусах огноо',
        'admin_report_apply': 'Харах',
        'admin_report_overview': 'Ерөнхий тайлан',
        'admin_cost_price': 'Өртөг (нэгжийн)',
        'admin_margin': 'Нэмэгдэл %',
        'admin_action_reprice': 'Өртөгөөс борлуулах үнийг дахин бодох (+20–30 хувь)',
        'admin_msg_repriced': 'барааны борлуулах үнэ шинэчлэгдлээ',
        'admin_overview_expense': 'Зарлага',
        'admin_overview_profit': 'Ашиг',
        'admin_overview_income_by_cat': 'Ангиллаар орлого',
        'admin_overview_split': 'Орлого ба зарлага',
        'admin_overview_other': 'Бусад',
        'admin_overview_note': 'Зарлага = нөөцөд нэмсэн барааны тоо × худалдан авсан үнэ (одоо байгаа нөөц ч орно). Ашиг = Орлого − Зарлага.',
        'admin_stock_unit_cost': 'Худалдан авсан үнэ (нэгж)',
        'admin_overview_expense_by_cat': 'Ангиллаар зарлага',
        'admin_overview_empty': 'Энэ хугацаанд мэдээлэл алга.',
        'admin_report_date': 'Огноо',
        'admin_report_units_sold': 'Зарагдсан (ш)',
        'admin_report_avg_order': 'Захиалгын дундаж дүн',
        'admin_report_total': 'Нийт',
        'admin_report_no_data': 'Энэ хугацаанд өгөгдөл алга.',
        'rd_product_title': 'Барааны дэлгэрэнгүй',
        'rd_customer_title': 'Хэрэглэгчийн дэлгэрэнгүй',
        'rd_sale_price': 'Хямдралтай үнэ',
        'rd_rating': 'Үнэлгээ',
        'rd_added': 'Нэмэгдсэн огноо',
        'rd_address': 'Хаяг',
        'rd_sales_period': 'Сонгосон хугацааны борлуулалт',
        'rd_order_no': 'Захиалга №',
        'rd_customer': 'Хэрэглэгч',
        'rd_qty': 'Тоо',
        'rd_unit_price': 'Нэгж үнэ',
        'rd_amount': 'Дүн',
        'rd_no_sales': 'Энэ хугацаанд зарагдаагүй.',
        'rd_no_orders': 'Энэ хугацаанд захиалга алга.',
        'rd_items': 'Авсан бараа',
        'rd_receipt': 'Баримт',
        'rd_print': 'Баримт хэвлэх',
        'rd_close': 'Хаах',
        'rd_options': 'Сонголт',
        'rd_thanks': 'Худалдан авалт хийсэнд баярлалаа!',
        'rd_subtotal': 'Дэд дүн',
        'rd_slip': 'Баримтын №',
        'rd_latest': 'Сүүлийн 50 захиалгын мөрийг харуулав.',
        'rd_desc_col': 'Барааны нэр',
        'rd_tax': 'НӨАТ',
        'rd_grand_total': 'Нийт төлөх',
        'rd_period': 'Хугацаа',
        'rd_status_pending': 'Хүлээгдэж буй',
        'rd_status_confirmed': 'Баталгаажсан',
        'rd_status_delivered': 'Хүргэгдсэн',
        'rd_status_cancelled': 'Цуцлагдсан',
        'admin_report_note': 'Цуцлагдсан захиалгыг тооцоогүй.',
        'admin_report_buyers': 'Худалдан авсан',
        'admin_report_spent': 'Худалдан авсан дүн',
        'admin_report_username': 'Нэвтрэх нэр',
        'admin_report_last_sold': 'Сүүлд зарагдсан',
        'admin_report_last_order': 'Сүүлийн захиалга',
        'admin_model_category': 'Ангилал',
        'admin_model_product': 'Бүтээгдэхүүн',
        'hero_model': 'Нүүр слайд',
        'hero_models': 'Нүүр хуудасны слайдер',
        'hero_f_product': 'Бүтээгдэхүүн',
        'hero_f_image': 'Слайдын зураг',
        'hero_f_product_image': 'Зураг',
        'hero_f_button': 'Товчны бичиг',
        'hero_f_button_pos': 'Товчны байрлал',
        'hero_pos_left': 'Зүүн доор',
        'hero_pos_center': 'Дунд доор',
        'hero_pos_right': 'Баруун доор',
        'hero_f_order': 'Дараалал',
        'help_hero_product': 'Нэрээр нь хайж сонгоно. Слайдны товч энэ барааны дэлгэрэнгүй хуудас руу очно.',
        'help_hero_image': 'Заавал 1600x600 px (8:3 харьцаатай) зураг оруулна. Автоматаар 1600x600 болгож, чанарыг тохируулна.',
        'help_hero_button': 'Хоосон бол "Дэлгэрэнгүй" гэж харагдана.',
        'help_hero_order': 'Бага тоо түрүүлж гарна.',
        'help_hero_active': 'Идэвхгүй слайд нүүр хуудсанд харагдахгүй.',
        'hero_err_max': 'Нүүр хуудасны слайдер дээр хамгийн ихдээ {max} слайд байна. Нэгийг нь устгаад эсвэл зургийг нь солиод ашиглана уу.',
        'hero_err_inactive': 'Идэвхгүй бүтээгдэхүүнийг слайдад оруулах боломжгүй.',
        'hero_err_ratio': 'Зургийн харьцаа 8:3 (жишээ нь 1600x600 px) байх ёстой. Таны зураг: {w}x{h} px.',
        'hero_err_small': 'Зураг хэт жижиг байна. Хамгийн багадаа 1200x450 px байх ёстой. Таны зураг: {w}x{h} px.',
        'hero_err_filesize': 'Зургийн хэмжээ {mb} MB-аас их байна. Багасгаад дахин оруулна уу.',
        'hero_full_note': 'Слайд {max}-д хүрсэн тул шинээр нэмэх боломжгүй. Одоо байгаа слайдыг засна уу.',
        'admin_app_customize': 'Тохируулга',
        'admin_model_employee': 'Ажилтан',
        'admin_model_customer': 'Хэрэглэгч',
        'admin_model_order': 'Захиалга',
        'admin_model_orderitem': 'Захиалгын мөр',
        'admin_employees': 'Ажилтнууд',
        'admin_model_customers': 'Худалдан авагчид',
        'admin_order_items': 'Захиалгын мөрүүд',

        'admin_model_category_lower': 'ангилал',
        'admin_model_product_lower': 'бүтээгдэхүүн',
        'admin_model_employee_lower': 'ажилтан',
        'admin_model_customer_lower': 'хэрэглэгч',
        'admin_model_order_lower': 'захиалга',

        # Admin panel: extra column headers defined in admin.py
        'admin_stock_status': 'Үлдэгдлийн төлөв',
        'admin_total': 'Нийт дүн',

        # Admin panel: active / inactive status (soft delete)
        'admin_status': 'Төлөв',
        'admin_active': 'Идэвхтэй',
        'admin_inactive': 'Идэвхгүй',
        'admin_action_activate': 'Сонгосон мөрийг идэвхжүүлэх',
        'admin_action_deactivate': 'Сонгосон мөрийг идэвхгүй болгох',
        'admin_msg_activated': 'мөр идэвхжлээ.',
        'admin_msg_deactivated': 'мөр идэвхгүй боллоо.',

        # ---- Admin panel: model field labels / help texts / misc (added) ----
        'f_price': 'Үнэ',
        'f_description': 'Тайлбар',
        'f_image': 'Зураг',
        'f_is_sale': 'Хямдралтай',
        'f_sale_price': 'Хямдралтай үнэ',
        'f_stock': 'Үлдэгдэл',
        'f_rating': 'Үнэлгээ',
        'f_created_at': 'Үүссэн огноо',
        'f_category': 'Ангилал',
        'f_product': 'Бүтээгдэхүүн',
        'f_user': 'Хэрэглэгч (акаунт)',
        'f_phone': 'Утас',
        'f_address': 'Хаяг',
        'f_position': 'Албан тушаал',
        'f_hired_at': 'Ажилд орсон огноо',
        'f_status': 'Төлөв',
        'f_quantity': 'Тоо ширхэг',
        'f_order': 'Захиалга',
        'f_option_type': 'Сонголтын төрөл',
        'f_option_value': 'Сонголтын утга',
        'f_unit_cost': 'Худалдан авсан үнэ (нэгж)',
        'f_is_opening': 'Эхний үлдэгдэл эсэх',
        'f_query': 'Хайлтын үг',
        'admin_model_productoption': 'Барааны сонголт',
        'admin_productoptions': 'Барааны сонголтууд',
        'admin_model_stockentry': 'Агуулахын бүртгэл',
        'admin_stockentries': 'Агуулахын бүртгэлүүд',
        'status_pending': 'Хүлээгдэж буй',
        'status_confirmed': 'Баталгаажсан',
        'status_delivered': 'Хүргэгдсэн',
        'status_cancelled': 'Цуцлагдсан',
        # Захиалгын жагсаалтын "Төлөв" (захиалга + хүргэлтээс гарган авсан 5 төлөв)
        'ord_st_new': 'Шинэ захиалгууд',
        'ord_st_preparing': 'Бэлтгэгдэж буй',
        'ord_st_on_the_way': 'Хүргэлтэнд гарсан',
        'ord_st_delivered': 'Хүргэгдсэн',
        'ord_st_cancelled': 'Цуцлагдсан',
        'ord_pick_driver': '- Хүргэгч сонгох -',
        'ord_no_driver_online': 'Онлайн хүргэгч алга',
        'ord_assign_failed': 'Хүргэгч оноож чадсангүй',
        'ord_assign_not_new': 'Зөвхөн шинэ захиалгад хүргэгч онооно.',
        'ord_assign_bad_driver': 'Энэ хүргэгчийг оноох боломжгүй (офлайн эсвэл идэвхгүй).',
        'help_category_active': 'Идэвхгүй ангилал дэлгүүрт харагдахгүй.',
        'help_employee_active': 'Идэвхгүй ажилтан нэвтэрч чадахгүй.',
        'help_customer_active': 'Идэвхгүй хэрэглэгч нэвтэрч чадахгүй.',
        'help_product_active': 'Идэвхгүй бүтээгдэхүүн дэлгүүрт харагдахгүй.',
        'help_option_active': 'Идэвхгүй сонголт дэлгүүрт харагдахгүй.',
        'help_order_active': 'Идэвхгүй захиалга архивлагдаж, хэрэглэгчид харагдахгүй.',
        'help_cost_price': 'Нэг ширхэгийн худалдан авсан үнэ. Нөөц нэмэхэд үнийг автоматаар бөглөнө; нөөц нэмэх бүр зарлага болж бүртгэгдэнэ.',
        'help_stock': 'Барааны үлдэгдэл (ширхэг)',
        'help_rating': 'Дундаж үнэлгээ, 0.0-5.0. Дэлгүүрийн "Үнэлгээ" эрэмбэлэлтэд ашиглагдана.',
        'help_created_at': 'Бүтээгдэхүүн нэмэгдсэн огноо. "Шинэ" эрэмбэ болон Өдөр/Сар/Жилийн шүүлтэд ашиглагдана.',
        'help_option_type': 'Худалдан авагчид харагдах сонголтын нэр, жишээ нь "Амт", "Хэмжээ", "Өнгө"',
        'help_option_value': 'Сонголтын утга, жишээ нь "Шоколад", "Том", "Улаан"',
        'help_order_item_options': 'Сонгосон сонголтуудын товч тайлбар, жишээ нь "Амт: Шоколад, Хэмжээ: Том"',
        'err_product_image_required': 'Барааны зураг оруулна уу.',
        'admin_unsaved_changes': 'Хадгалаагүй өөрчлөлт',
        'admin_btn_cancel': 'Болих',
        'admin_btn_cancel_popup': 'Цуцлах',
        'admin_btn_save': 'Хадгалах',
        'admin_btn_edit': 'Засах',
        'admin_btn_add': 'Нэмэх',
        'admin_btn_back': 'Буцах',
        'admin_btn_close': 'Хаах',
        'admin_loading': 'Ачааллаж байна…',
        'admin_current_stock': 'Одоогийн үлдэгдэл',
        'admin_selling_price': 'Борлуулах үнэ',
        'admin_new_stock': 'Шинэ үлдэгдэл',
        'admin_js_form_not_found': 'Django admin form олдсонгүй.',
        'admin_js_form_error': 'Form ачаалахад алдаа гарлаа.',
        'admin_order_label': 'Захиалга',
        'admin_yes': 'Тийм',
        'admin_no': 'Үгүй',
        'admin_empty': '(хоосон)',
        # Delivery app (admin)
        'dl_app': 'Хүргэлт',
        'dl_model_driver': 'Хүргэгч',
        'dl_drivers': 'Хүргэгчид',
        'dl_model_delivery': 'Хүргэлт',
        'dl_deliveries': 'Хүргэлтүүд',
        'dl_model_history': 'Хүргэлтийн түүх',
        'dl_f_user': 'Хэрэглэгч',
        'dl_f_phone': 'Утас',
        'dl_f_active': 'Идэвхтэй эсэх',
        'dl_f_online': 'Онлайн',
        'dl_f_status': 'Төлөв',
        'dl_f_work_status': 'Ажлын төлөв',
        'dl_f_created': 'Үүссэн огноо',
        'dl_f_order': 'Захиалга',
        'dl_f_driver': 'Хүргэгч',
        'dl_f_address': 'Хүргэх хаяг',
        'dl_f_district': 'Дүүрэг',
        'dl_f_assigned': 'Оноосон',
        'dl_f_accepted': 'Хүлээн авсан',
        'dl_f_picked_up': 'Бараа авсан',
        'dl_f_on_the_way': 'Хүргэлтэнд гарсан',
        'dl_f_delivered': 'Хүргэсэн',
        'dl_f_failed_at': 'Амжилтгүй болсон',
        'dl_f_fail_reason': 'Амжилтгүй болсон шалтгаан',
        'dl_f_note': 'Тайлбар',
        'dl_f_delivery': 'Хүргэлт',
        'dl_f_from_status': 'Өмнөх төлөв',
        'dl_f_to_status': 'Шинэ төлөв',
        'dl_f_changed_by': 'Өөрчилсөн',
        'dl_f_date': 'Огноо',
        'dl_ds_online': 'Онлайн',
        'dl_ds_offline': 'Офлайн',
        'dl_ds_busy': 'Завгүй',
        'dl_st_pending': 'Хүргэлт үүссэн',
        'dl_st_assigned': 'Хүргэгч оноогдсон',
        'dl_st_accepted': 'Хүлээн авсан',
        'dl_st_picked_up': 'Бараа авсан',
        'dl_st_on_the_way': 'Хүргэлтэнд явж байна',
        'dl_st_delivered': 'Хүргэсэн',
        'dl_st_failed': 'Амжилтгүй',
        'dl_st_cancelled': 'Цуцлагдсан',
        'dl_fail_unavailable': 'Харилцагч байхгүй',
        'dl_fail_wrong_address': 'Хаяг буруу',
        'dl_fail_refused': 'Харилцагч татгалзсан',
        'dl_fail_phone': 'Утсаар холбогдохгүй',
        'dl_fail_other': 'Бусад',
        'dl_col_name': 'Нэр',
        'dl_col_username': 'Нэвтрэх нэр',
        'dl_col_password': 'Нууц үг',
        'dl_col_customer': 'Харилцагч',
        'dl_col_address': 'Хаяг',
        'dl_err_username_required': 'Нэвтрэх нэрээ оруулна уу.',
        'dl_err_username_taken': 'Энэ нэвтрэх нэр аль хэдийн бүртгэлтэй байна.',
        'dl_err_password_required': 'Нууц үгээ оруулна уу.',
        'dl_action_cancel': 'Сонгосон хүргэлтийг цуцлах',
        'dl_msg_cancelled': 'хүргэлт цуцлагдлаа.',
        'dl_e_no_reassign': 'Бараа авсан хойно хүргэгчийг солих боломжгүй.',
        'dl_e_inactive_driver': 'Идэвхгүй хүргэгчид хүргэлт оноох боломжгүй.',
        'dl_e_no_cancel': 'Энэ хүргэлтийг цуцлах боломжгүй.',
        'dl_e_bad_action': 'Буруу үйлдэл.',
        'dl_e_state_changed': 'Хүргэлтийн төлөв өөрчлөгдсөн байна. Хуудсаа шинэчилнэ үү.',
        'dl_e_reason': 'Амжилтгүй болсон шалтгаанаа сонгоно уу.',

        # Workspaces (admin site / driver site chooser)
        'ws_admin': 'Админ сайт',
        'ws_driver': 'Хүргэгчийн сайт',
        'ws_admin_desc': 'Бараа, захиалга, ажилтан, тайлан удирдах',
        'ws_driver_desc': 'Надад оноогдсон хүргэлтүүд',
        'ws_choose_title': 'Орох сайтаа сонгоно уу',
        'ws_choose_text': 'Танд хэд хэдэн албан тушаал байгаа тул аль сайт руу орохоо сонгоно уу.',
        'ws_open': 'Орох',
        'ws_switch': 'Сайт солих',
        'ws_positions_help': 'Хэд хэдэн албан тушаал сонгож болно. Админ / Оператор нь админ сайтад, Хүргэгч нь хүргэгчийн сайтад орох эрх олгоно.',
        'ws_positions_required': 'Дор хаяж нэг албан тушаал сонгоно уу.',
    },

    'en': {
        # Layout / site-wide
        'site_title': 'E-Commerce Shop',
        'footer_text': 'Online Shop',

        # Navbar
        'brand': 'Shop',
        'nav_home': 'Home',
        'nav_about': 'About Us',
        'nav_categories': 'Categories',
        'nav_all_products': 'All Products',
        'nav_login': 'Login',
        'nav_register': 'Register',
        'nav_logout': 'Logout',
        'search_placeholder': 'Search...',
        'search_button': 'Search',
        'search_recent': 'Recent searches',
        'search_clear': 'Clear',
        'search_no_recent': 'No recent searches',
        'search_remove': 'Remove',
        'search_recommended': 'Recommended for you',
        'search_did_you_mean': 'Did you mean',
        'search_category': 'Category',
        'search_no_exact': 'No exact matches. Showing results for:',
        'cart_label': 'Cart',

        # Home page
        'home_title': 'Shop',
        'home_subtitle': 'An online platform for shopping',

        # Category page
        'category_subtitle': 'Products in this category',
        'add_product_btn': 'Add Product',
        'empty_products_title': 'No products yet',
        'empty_products_text': 'No products have been added to this category yet.',
        'add_first_product_btn': 'Add first product',
        'modal_add_product_title': 'Add New Product',
        'form_name_label': 'Product Name',
        'form_category_label': 'Category',
        'form_price_label': 'Price (₮)',
        'form_image_label': 'Image',
        'form_description_label': 'Description',
        'sale_checkbox_label': 'On sale',
        'sale_price_label': 'Sale Price (₮)',
        'form_stock_label': 'Stock (units)',
        'form_rating_label': 'Rating (0-5)',
        'cancel_btn': 'Cancel',
        'save_btn': 'Save',

        # Product card / view toggle
        'product_detail_btn': 'View Details',
        'view_grid_title': 'Grid view',
        'view_list_title': 'List view',

        # Sort / period filter bar
        'sort_label': 'Sort by',
        'sort_name_asc': 'Name (A-Z)',
        'sort_name_desc': 'Name (Z-A)',
        'sort_price_asc': 'Price: Low to High',
        'sort_price_desc': 'Price: High to Low',
        'sort_popularity': 'Popularity',
        'sort_rating': 'Rating',
        'period_label': 'Period',
        'period_all': 'All time',
        'period_daily': 'Daily',
        'period_monthly': 'Monthly',
        'period_yearly': 'Yearly',
        'filter_reset_title': 'Reset filters',

        # Search page
        'search_no_results_text': 'No search results found.',

        # About page
        'about_title': 'About Us',
        'about_text': 'Our online shop aims to offer customers the best online shopping experience. '
                       'We are known for our wide range of products, reliable service, and customer support.',

        # Login page
        'login_title': 'Login',
        'login_subtitle': 'Welcome to our shop',
        'username_label': 'Username',
        'password_label': 'Password',
        'login_btn': 'Login',

        # Register page
        'register_title': 'Registration',
        'register_subtitle': 'Sign up for our shop',
        'register_btn': 'Register',
        'email_placeholder': 'Email',
        'first_name_placeholder': 'First name',
        'last_name_placeholder': 'Last name',
        'username_placeholder': 'Username',
        'password_placeholder': 'Password',
        'password_confirm_placeholder': 'Confirm password',
        'username_help_text': 'Username must be less than 50 characters.',
        'password_help_text': 'Password must be at least 8 characters.',
        'password_confirm_help_text': 'Enter the same password again.',

        # Product detail page
        'sale_label': 'On Sale',
        'back_btn': 'Back',
        'add_to_cart_btn': 'Add to Cart',
        'quantity_label': 'Quantity',
        'added_to_cart_feedback': 'Added to cart',
        'in_stock_label': 'left in stock',
        'low_stock_label': 'Low stock',
        'out_of_stock_label': 'Out of stock',
        'out_of_stock_btn': 'Out of Stock',

        # Cart page
        'cart_page_title': 'My Cart',
        'table_product': 'Product',
        'table_quantity': 'Quantity',
        'table_options': 'Options',
        'table_price': 'Price',
        'table_total': 'Total',
        'remove_btn': 'Remove',
        'clear_cart_btn': 'Clear Cart',
        'total_amount_label': 'Total',
        'empty_cart_text': 'Your cart is empty.',

        # Flash messages (views.py)
        'msg_category_not_found': 'Matching category not found',
        'msg_admin_only_add_product': 'Only admins can add products',
        'msg_product_added': 'Product added successfully!',
        'msg_form_invalid': 'Please fill in the information correctly.',
        'msg_login_success': 'Successfully logged in',
        'msg_login_failed': 'Incorrect username or password',
        'msg_logout_success': 'Successfully logged out',
        'msg_register_success': 'Thank you for registering. Please log in now.',
        'msg_register_failed': 'Registration failed. Please check your information and try again.',
        'msg_search_no_results': 'No search results found',
        'msg_out_of_stock': 'Sorry, this product is out of stock.',
        'msg_insufficient_stock': 'Sorry, only {stock} units left in stock.',
               'msg_order_confirmed': 'Order confirmed successfully!',
        'msg_cart_empty': 'Your cart is empty',

        # Order confirm page
        'order_confirm_title': 'Confirm Order',
        'customer_name': 'Name',
        'customer_phone': 'Phone number',
        'customer_address': 'Address',
        'place_order_btn': 'Place Order',
           'my_orders_title': 'My Orders',
        'order_number_label': 'Order',
        'no_orders_text': 'You have no orders yet.',

        # Employees page
        'employees_title': 'Employees',
        'add_employee_btn': 'Add Employee',
        'add_employee_title': 'Add New Employee',
        'add_employee_subtitle': 'Create a new employee account',
        'table_username': 'Username',
        'table_name': 'Name',
        'table_email': 'Email',
        'table_role': 'Role',
        'role_admin': 'Admin',
        'role_employee': 'Employee',
        'no_employees_text': 'No employees yet.',
        'msg_employee_added': 'Employee added successfully!',
        'position_placeholder': 'Position',
        'phone_placeholder': 'Phone number',
        'table_position': 'Position',
        'table_phone': 'Phone',

        # Profile page
        'profile_title': 'My Profile',
        'profile_subtitle': 'Update your personal information',
        'nav_profile': 'My Profile',
        'nav_admin_panel': 'Admin Panel',
        'customer_address_label': 'Home address',
        'customer_address_placeholder': 'Home address / location',
        'msg_profile_updated': 'Information updated successfully!',

        # ---- Admin panel: branding / chrome ----
        'admin_site_title': 'Bshop Admin',
        'admin_site_header': 'Bshop Admin',
        'admin_index_title': 'Dashboard',
        'admin_lang_label': 'Choose language',
        'admin_theme_light_mode': 'Light mode',
        'admin_theme_dark_mode': 'Dark mode',

        # Admin panel: sidebar
        'admin_nav_stock': 'Stock',

        # Admin panel: dashboard (index.html)
        'admin_dashboard': 'Dashboard',
        'admin_revenue': 'Revenue',
        'admin_products': 'Products',
        'admin_orders': 'Orders',
        'admin_customers': 'Customers',
        'admin_low_stock': 'Low stock',
        'admin_overview': 'Overview',
        'admin_details': 'Details',
        'admin_chart_soon': 'Order chart coming soon',

        # Admin panel: dashboard charts
        'admin_day_title': 'Daily revenue (last 14 days)',
        'admin_rev_title': 'Monthly revenue (last 12 months)',

        'admin_categories': 'Categories',
        'admin_pending_orders': 'Pending orders',
        'admin_completed_orders': 'Completed',
        'admin_low_stock_products': 'Low-stock products',
        'admin_total_customers': 'Total customers',
        'admin_view_categories': 'View categories',
        'admin_recent_actions': 'Recent actions',
        'admin_nothing_yet': 'Nothing here yet.',
        'admin_unknown': 'Unknown',

        # Admin panel: stock page (stock.html)
        'admin_stock_title': 'Stock',
        'admin_total_stock_value': 'Total stock value',
        'admin_in_stock': 'In stock',
        'admin_low': 'Low',
        'admin_out_of_stock': 'Out of stock',
        'admin_low_stock_status': 'Low stock',
        'admin_total_products': 'Total products',
        'admin_total_stock_units': 'Total stock units',
        'admin_inventory': 'Inventory',
        'admin_product_list': 'Product list',
        'admin_search_inventory': 'Search inventory',
        'admin_filters': 'Filters',
        'admin_all': 'All',
        'admin_add_product': 'Add product',
        'admin_col_name': 'Name',
        'admin_col_category': 'Category',
        'admin_col_price': 'Price',
        'admin_col_stock': 'Stock',
        'admin_col_status': 'Status',
        'admin_col_is_active': 'Is active',
        'admin_col_action': 'Action',
        'admin_quantity_to_add': 'Quantity to add',
        'admin_no_products': 'No products found.',

        # Admin panel: model / app names shown in the sidebar
        'admin_app_store': 'Store',
        'admin_app_cart': 'Cart',
        # Admin panel: "Reports" sidebar group (store/reports.py)
        'admin_app_reports': 'Reports',
        'admin_report_inventory': 'Inventory / Products',
        'admin_report_orders': 'Orders',
        'admin_report_customers': 'Customers',
        'admin_report_from': 'From',
        'admin_report_to': 'To',
        'admin_report_apply': 'Apply',
        'admin_report_overview': 'Overview',
        'admin_cost_price': 'Cost price (per unit)',
        'admin_margin': 'Mark-up %',
        'admin_action_reprice': 'Re-price from cost (+20–30 percent)',
        'admin_msg_repriced': 'product prices updated',
        'admin_overview_expense': 'Expense',
        'admin_overview_profit': 'Profit',
        'admin_overview_income_by_cat': 'Income by category',
        'admin_overview_split': 'Income vs expense',
        'admin_overview_other': 'Other',
        'admin_overview_note': 'Expense = units added to stock x purchase price (stock already on hand counts too). Profit = Income - Expense.',
        'admin_stock_unit_cost': 'Purchase price (per unit)',
        'admin_overview_expense_by_cat': 'Expense by category',
        'admin_overview_empty': 'No data for this period.',
        'admin_report_date': 'Date',
        'admin_report_units_sold': 'Units sold',
        'admin_report_avg_order': 'Average order',
        'admin_report_total': 'Total',
        'admin_report_no_data': 'No data for this period.',
        'rd_product_title': 'Product details',
        'rd_customer_title': 'Customer details',
        'rd_sale_price': 'Sale price',
        'rd_rating': 'Rating',
        'rd_added': 'Added',
        'rd_address': 'Address',
        'rd_sales_period': 'Sales in the selected period',
        'rd_order_no': 'Order #',
        'rd_customer': 'Customer',
        'rd_qty': 'Qty',
        'rd_unit_price': 'Unit price',
        'rd_amount': 'Amount',
        'rd_no_sales': 'Not sold in this period.',
        'rd_no_orders': 'No orders in this period.',
        'rd_items': 'Purchased items',
        'rd_receipt': 'Receipt',
        'rd_print': 'Print receipt',
        'rd_close': 'Close',
        'rd_options': 'Options',
        'rd_thanks': 'Thank you for your purchase!',
        'rd_subtotal': 'Subtotal',
        'rd_slip': 'Slip No',
        'rd_latest': 'Showing the latest 50 order lines.',
        'rd_desc_col': 'Description',
        'rd_tax': 'Tax',
        'rd_grand_total': 'Total',
        'rd_period': 'Period',
        'rd_status_pending': 'Pending',
        'rd_status_confirmed': 'Confirmed',
        'rd_status_delivered': 'Delivered',
        'rd_status_cancelled': 'Cancelled',
        'admin_report_note': 'Cancelled orders are not counted.',
        'admin_report_buyers': 'Customers who ordered',
        'admin_report_spent': 'Total spent',
        'admin_report_username': 'Username',
        'admin_report_last_sold': 'Last sold',
        'admin_report_last_order': 'Last order',
        'admin_model_category': 'Category',
        'admin_model_product': 'Product',
        'hero_model': 'Home slide',
        'hero_models': 'Home page slider',
        'hero_f_product': 'Product',
        'hero_f_image': 'Slide image',
        'hero_f_product_image': 'Picture',
        'hero_f_button': 'Button text',
        'hero_f_button_pos': 'Button position',
        'hero_pos_left': 'Bottom left',
        'hero_pos_center': 'Bottom centre',
        'hero_pos_right': 'Bottom right',
        'hero_f_order': 'Order',
        'help_hero_product': 'Search by name. The slide button opens this product\'s detail page.',
        'help_hero_image': 'Upload a 1600x600 px (8:3) picture. It is resized to 1600x600 and compressed automatically.',
        'help_hero_button': 'Leave empty to show "View Details".',
        'help_hero_order': 'Lower numbers come first.',
        'help_hero_active': 'Inactive slides are hidden from the home page.',
        'hero_err_max': 'The home page slider can hold at most {max} slides. Delete one or replace its picture instead.',
        'hero_err_inactive': 'An inactive product cannot be put in the slider.',
        'hero_err_ratio': 'The picture must be 8:3 (for example 1600x600 px). Yours is {w}x{h} px.',
        'hero_err_small': 'The picture is too small. It must be at least 1200x450 px. Yours is {w}x{h} px.',
        'hero_err_filesize': 'The picture is larger than {mb} MB. Please make it smaller and upload again.',
        'hero_full_note': 'The slider already has {max} slides, so no more can be added. Edit an existing slide instead.',
        'admin_app_customize': 'Customize',
        'admin_model_employee': 'Employee',
        'admin_model_customer': 'Customer',
        'admin_model_order': 'Order',
        'admin_model_orderitem': 'Order item',
        'admin_employees': 'Employees',
        'admin_model_customers': 'Customers',
        'admin_order_items': 'Order items',

        'admin_model_category_lower': 'category',
        'admin_model_product_lower': 'product',
        'admin_model_employee_lower': 'employee',
        'admin_model_customer_lower': 'customer',
        'admin_model_order_lower': 'order',

        # Admin panel: extra column headers defined in admin.py
        'admin_stock_status': 'Stock status',
        'admin_total': 'Total',

        # Admin panel: active / inactive status (soft delete)
        'admin_status': 'Status',
        'admin_active': 'Active',
        'admin_inactive': 'Inactive',
        'admin_action_activate': 'Mark selected rows as active',
        'admin_action_deactivate': 'Mark selected rows as inactive',
        'admin_msg_activated': 'row(s) marked active.',
        'admin_msg_deactivated': 'row(s) marked inactive.',

        # ---- Admin panel: model field labels / help texts / misc (added) ----
        'f_price': 'Price',
        'f_description': 'Description',
        'f_image': 'Image',
        'f_is_sale': 'On sale',
        'f_sale_price': 'Sale price',
        'f_stock': 'Stock',
        'f_rating': 'Rating',
        'f_created_at': 'Created at',
        'f_category': 'Category',
        'f_product': 'Product',
        'f_user': 'User account',
        'f_phone': 'Phone',
        'f_address': 'Address',
        'f_position': 'Position',
        'f_hired_at': 'Hired at',
        'f_status': 'Status',
        'f_quantity': 'Quantity',
        'f_order': 'Order',
        'f_option_type': 'Option type',
        'f_option_value': 'Option value',
        'f_unit_cost': 'Purchase price (per unit)',
        'f_is_opening': 'Is opening stock',
        'f_query': 'Search query',
        'admin_model_productoption': 'Product option',
        'admin_productoptions': 'Product options',
        'admin_model_stockentry': 'Stock entry',
        'admin_stockentries': 'Stock entries',
        'status_pending': 'Pending',
        'status_confirmed': 'Confirmed',
        'status_delivered': 'Delivered',
        'status_cancelled': 'Cancelled',
        'ord_st_new': 'New orders',
        'ord_st_preparing': 'Preparing',
        'ord_st_on_the_way': 'Out for delivery',
        'ord_st_delivered': 'Delivered',
        'ord_st_cancelled': 'Cancelled',
        'ord_pick_driver': '- Choose driver -',
        'ord_no_driver_online': 'No driver online',
        'ord_assign_failed': 'Could not assign the driver',
        'ord_assign_not_new': 'A driver can only be assigned to a new order.',
        'ord_assign_bad_driver': 'This driver cannot be assigned (offline or inactive).',
        'help_category_active': 'Inactive categories are hidden from the storefront.',
        'help_employee_active': 'Inactive employees cannot log in.',
        'help_customer_active': 'Inactive customers cannot log in.',
        'help_product_active': 'Inactive products are hidden from the storefront.',
        'help_option_active': 'Inactive options are hidden from the storefront.',
        'help_order_active': 'Inactive orders are archived and hidden from customers.',
        'help_cost_price': 'Default purchase price of one unit. Pre-fills the price when you add stock; each stock addition is recorded as an expense.',
        'help_stock': 'Product stock quantity (units)',
        'help_rating': "Average customer rating, 0.0-5.0. Powers the 'Rating' sort on the storefront.",
        'help_created_at': "When the product was added. Powers the 'Newest' sort and the Daily/Monthly/Yearly filter.",
        'help_option_type': "Dropdown label shown to customers, e.g. 'Flavor', 'Size', 'Color'",
        'help_option_value': "The choice itself, e.g. 'Chocolate', 'Large', 'Red'",
        'help_order_item_options': "Human-readable summary of the options chosen, e.g. 'Flavor: Chocolate, Size: Large'",
        'err_product_image_required': 'Please upload a product image.',
        'admin_unsaved_changes': 'Unsaved changes',
        'admin_btn_cancel': 'Cancel',
        'admin_btn_cancel_popup': 'Cancel',
        'admin_btn_save': 'Save',
        'admin_btn_edit': 'Edit',
        'admin_btn_add': 'Add',
        'admin_btn_back': 'Back',
        'admin_btn_close': 'Close',
        'admin_loading': 'Loading…',
        'admin_current_stock': 'Current stock',
        'admin_selling_price': 'Selling price',
        'admin_new_stock': 'New stock',
        'admin_js_form_not_found': 'Django admin form not found.',
        'admin_js_form_error': 'Failed to load the form.',
        'admin_order_label': 'Order',
        'admin_yes': 'Yes',
        'admin_no': 'No',
        'admin_empty': '(empty)',
        # Delivery app (admin)
        'dl_app': 'Delivery',
        'dl_model_driver': 'Driver',
        'dl_drivers': 'Drivers',
        'dl_model_delivery': 'Delivery',
        'dl_deliveries': 'Deliveries',
        'dl_model_history': 'Delivery history',
        'dl_f_user': 'User',
        'dl_f_phone': 'Phone',
        'dl_f_active': 'Active',
        'dl_f_online': 'Online',
        'dl_f_status': 'Status',
        'dl_f_work_status': 'Work status',
        'dl_f_created': 'Created',
        'dl_f_order': 'Order',
        'dl_f_driver': 'Driver',
        'dl_f_address': 'Delivery address',
        'dl_f_district': 'District',
        'dl_f_assigned': 'Assigned',
        'dl_f_accepted': 'Accepted',
        'dl_f_picked_up': 'Picked up',
        'dl_f_on_the_way': 'On the way',
        'dl_f_delivered': 'Delivered',
        'dl_f_failed_at': 'Failed',
        'dl_f_fail_reason': 'Failure reason',
        'dl_f_note': 'Note',
        'dl_f_delivery': 'Delivery',
        'dl_f_from_status': 'Previous status',
        'dl_f_to_status': 'New status',
        'dl_f_changed_by': 'Changed by',
        'dl_f_date': 'Date',
        'dl_ds_online': 'Online',
        'dl_ds_offline': 'Offline',
        'dl_ds_busy': 'Busy',
        'dl_st_pending': 'Delivery created',
        'dl_st_assigned': 'Driver assigned',
        'dl_st_accepted': 'Accepted by driver',
        'dl_st_picked_up': 'Goods picked up',
        'dl_st_on_the_way': 'On the way',
        'dl_st_delivered': 'Delivered',
        'dl_st_failed': 'Delivery failed',
        'dl_st_cancelled': 'Cancelled',
        'dl_fail_unavailable': 'Customer unavailable',
        'dl_fail_wrong_address': 'Wrong address',
        'dl_fail_refused': 'Customer refused',
        'dl_fail_phone': 'Phone unreachable',
        'dl_fail_other': 'Other',
        'dl_col_name': 'Name',
        'dl_col_username': 'Username',
        'dl_col_password': 'Password',
        'dl_col_customer': 'Customer',
        'dl_col_address': 'Address',
        'dl_err_username_required': 'Please enter a username.',
        'dl_err_username_taken': 'This username is already taken.',
        'dl_err_password_required': 'Please enter a password.',
        'dl_action_cancel': 'Cancel selected deliveries',
        'dl_msg_cancelled': 'deliveries cancelled.',
        'dl_e_no_reassign': 'The driver cannot be changed after pickup.',
        'dl_e_inactive_driver': 'Cannot assign a delivery to an inactive driver.',
        'dl_e_no_cancel': 'This delivery cannot be cancelled.',
        'dl_e_bad_action': 'Invalid action.',
        'dl_e_state_changed': 'The delivery status has changed. Please refresh the page.',
        'dl_e_reason': 'Please choose a failure reason.',

        # Workspaces (admin site / driver site chooser)
        'ws_admin': 'Admin site',
        'ws_driver': 'Driver site',
        'ws_admin_desc': 'Manage products, orders, staff and reports',
        'ws_driver_desc': 'Deliveries assigned to me',
        'ws_choose_title': 'Choose where to go',
        'ws_choose_text': 'You hold more than one position, so pick which site you want to open.',
        'ws_open': 'Open',
        'ws_switch': 'Switch site',
        'ws_positions_help': 'You can pick several positions. Admin / Operator give access to the admin site, Driver gives access to the driver site.',
        'ws_positions_required': 'Select at least one position.',
    },
}

def get_language(request):
    """Read the visitor's chosen language from a cookie, defaulting to Mongolian."""
    lang = request.COOKIES.get(COOKIE_NAME, DEFAULT_LANGUAGE)
    if lang not in TRANSLATIONS:
        lang = DEFAULT_LANGUAGE
    return lang


def get_translations(request):
    """The full dict of strings for the visitor's current language."""
    return TRANSLATIONS[get_language(request)]


def t(request, key):
    """Look up a single string for use in views.py (e.g. messages.success)."""
    return get_translations(request).get(key, key)


# ---------------------------------------------------------------------------
# Lazy lookup, for places where there is no `request` object
# ---------------------------------------------------------------------------
# Things like admin.py column headers or the admin sidebar's model names are
# built once when Django starts, long before any visitor shows up, so they
# can't use t(request, ...). `lazy_t('key')` returns a placeholder that only
# turns into real text at the moment it is rendered, and it reads the language
# that SiteLanguageMiddleware activated for the current request.


def active_language():
    """The language currently switched on for this request (set by
    store.middleware.SiteLanguageMiddleware), falling back to Mongolian."""
    from django.utils import translation

    lang = translation.get_language() or DEFAULT_LANGUAGE
    lang = lang.split('-')[0]
    return lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE


def _translate_now(key):
    return TRANSLATIONS[active_language()].get(key, key)


lazy_t = lazy(_translate_now, str)


def _category_now(name):
    return translate_category_name(name, active_language())


def _position_now(name):
    return translate_position(name, active_language())


# Translated when the page is drawn, in the language of the current request.
lazy_category = lazy(_category_now, str)
lazy_position = lazy(_position_now, str)

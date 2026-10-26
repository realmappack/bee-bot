import asyncio
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# --- ВЕБСЕРВЕР ДЛЯ RENDER (Щоб сервіс отримував порт і не видавав Exited with status 1) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаємо вебсервер у фоновому потоці одразу при старті
threading.Thread(target=run_web_server, daemon=True).start()


BOT_TOKEN = "8692855173:AAFQc9dsNIlWwT2rOGEs9vz5A4dhiiDSh1w"
ADMIN_ID = 331804153  # Ваш числовий Telegram ID
ADMIN_USERNAME = "mappack"  # Ваша аватара/юзернейм для зв'язку (без @)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- ФУНКЦІЯ ЛІЧИЛЬНИКА ЗАМОВЛЕНЬ ---
COUNTER_FILE = "order_counter.txt"

def get_next_order_id() -> int:
    """Зчитує останній номер замовлення з файлу, збільшує на 1 та зберігає."""
    start_number = 101  # початковий номер замовлення, якщо файлу ще немає
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.isdigit():
                    start_number = int(content) + 1
        except Exception:
            pass
            
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(start_number))
        
    return start_number


# --- СТАНИ (FSM) ---
class OrderProcess(StatesGroup):
    waiting_for_category = State()       
    waiting_for_product = State()        
    waiting_for_zabrus_sub = State()     
    waiting_for_honeycomb_sub = State()  
    waiting_for_nuts_honey_sub = State() 
    waiting_for_creamed_sub = State()    
    waiting_for_amosov_sub = State()     
    waiting_for_bee_prod_sub = State()   
    
    waiting_for_candle_classic_sub = State()
    waiting_for_candle_voshchyna_sub = State()
    waiting_for_candle_shaped_sub = State()
    
    waiting_for_honey_size = State()     
    
    honey_info_view = State()
    honeycomb_info_view = State()
    zabrus_info_view = State()
    nuts_honey_info_view = State()
    creamed_info_view = State()
    amosov_info_view = State()
    bee_prod_info_view = State()
    candle_classic_info_view = State()
    candle_voshchyna_info_view = State()
    candle_shaped_info_view = State()
    
    waiting_for_quantity = State()       
    waiting_for_delivery_type = State()  
    
    waiting_for_fio = State()            
    waiting_for_phone = State()          
    waiting_for_city = State()           
    waiting_for_post_office = State()    
    waiting_for_post_index = State()     
    waiting_for_address = State()        
    waiting_for_delivery_time = State()  
    
    waiting_for_payment_type = State()   
    waiting_for_cod_confirmation = State()     # Крок підтвердження умов післяплати
    waiting_for_payment_confirmation = State() 


# --- БАЗА ТОВАРІВ ТА ЦІН ---
PRODUCTS_DATA = {
    "honey": [
        {"id": "prod_honey_acacia", "name": "🍯 Мед з акації"},
        {"id": "prod_honey_linden", "name": "🍯 Мед з липи"},
        {"id": "prod_honey_buckwheat", "name": "🍯 Мед з гречки"},
        {"id": "prod_honey_mix", "name": "🍯 Мед з різнотрав'я"},
        {"id": "prod_honey_rapeseed", "name": "🍯 Мед з ріпаку"},
        {"id": "prod_honey_sunflower", "name": "🍯 Мед з соняха"},
    ],
    "delicacies": [
        {"id": "prod_honeycomb", "name": "🎁 Мед у стільниках (сотах)"},
        {"id": "prod_zabrus", "name": "🎁 Забрус"},
        {"id": "prod_nuts_honey", "name": "🎁 Акацієвий мед з горішками"},
        {"id": "prod_creamed_honey", "name": "🎁 Крем-мед з добавками"},
        {"id": "prod_amosov_paste", "name": "🎁 Паста Амосова з пилком"},
    ],
    "bee_products": [
        {"id": "prod_pollen", "name": "🐝 Бджолиний пилок (обніжжя)"},
        {"id": "prod_perga", "name": "🐝 Перга бджолина (бджолиний хліб)"},
        {"id": "prod_propolis_tincture", "name": "🐝 Настоянка прополісу"},
        {"id": "prod_propolis_balls", "name": "🐝 Натуральний прополіс (у кульках)"},
        {"id": "prod_wax_ingots", "name": "🐝 Натуральний бджолиний віск (у злитках)"},
    ],
    "candles": [
        {"id": "prod_candle_classic", "name": "🕯 Звичайна воскова свічка"},
        {"id": "prod_candle_voshchyna", "name": "🕯 Свічка з вощини"},
        {"id": "prod_candle_shaped", "name": "🕯 Формова свічка"},
    ],
}

ALL_ITEMS_INFO = {
    "candle_classic_item": {"name": "🕯 Класична свічка (1 шт)", "price": 20},
    "candle_v_xl": {"name": "🕯 Свічка з вощини (XL)", "price": 80},
    "candle_v_l": {"name": "🕯 Свічка з вощини (L)", "price": 80},
    "candle_v_m": {"name": "🕯 Свічка з вощини (M)", "price": 50},
    "candle_v_s": {"name": "🕯 Свічка з вощини (S)", "price": 50},
    "candle_sh_corn": {"name": "🌽 Формова свічка (Кукурузка)", "price": 60},
    "candle_sh_pumpkin": {"name": "🎃 Гарбузик", "price": 50},
    "candle_sh_egg": {"name": "🥚 Яєчко", "price": 50},
    "candle_sh_lotus": {"name": "🌸 Лотос", "price": 40},
    "candle_sh_heart": {"name": "❤️ Сердечко", "price": 40},
    "candle_sh_tree": {"name": "🎄 Ялинка", "price": 40},
    "candle_sh_santa": {"name": "🎅 Санта Клаус", "price": 40},
    "candle_sh_angel": {"name": "👼 Янголятко", "price": 20},
    "item_pollen_100g": {"name": "🌾 Бджолиний пилок (100 г)", "price": 70},
    "item_perga_50g": {"name": "👑 Перга бджолина (50 г)", "price": 140},
    "item_tincture_50ml": {"name": "🧪 Настоянка прополісу (50 мл)", "price": 100},
    "item_propolis_10g": {"name": "🟤 Натуральний прополіс (10 г)", "price": 40},
    "item_wax_ingot": {"name": "🧈 Бджолиний віск у злитку", "price": 25},
    "amosov_033l": {"name": "🍯 Паста Амосова (0.33 л)", "price": 300},
    "amosov_05l": {"name": "🍯 Паста Амосова (0.5 л)", "price": 450},
    "amosov_1l": {"name": "🍯 Паста Амосова (1 л)", "price": 900},
    "cream_classic_025l": {"name": "🍯 Крем-мед класичний (0.25 л)", "price": 150},
    "nuts_walnut_05l": {"name": "🌰 Мед з волоським горіхом (0.5 л)", "price": 340},
    "nuts_mix_025l": {"name": "🌰 Мед з міксом горішків (0.25 л)", "price": 300},
    "zabrus_acacia": {"name": "🐝 Забрус з акації (650 г)", "price": 160},
    "zabrus_linden": {"name": "🐝 Забрус з липи (650 г)", "price": 150},
    "zabrus_mix": {"name": "🐝 Забрус з різнотрав'я (650 г)", "price": 140},
    "honeycomb_acacia": {"name": "🐝 Мед в сотах з акації (200+ г)", "price": 200},
    "size_1l": {"name": "🍯 Мед (1 л / 1.4 кг)", "price": 600},
    "size_05l_plastic": {"name": "🍯 Мед (0.5 л / 0.7 кг — відерце)", "price": 300},
    "size_05l_glass": {"name": "🍯 Мед (0.5 л / 0.7 кг — банка)", "price": 300},
    "size_033l": {"name": "🍯 Мед (0.33 л / 0.45 кг)", "price": 200},
}

HONEY_PRICES_MAP = {
    "prod_honey_acacia": {"size_1l": 600, "size_05l_plastic": 300, "size_05l_glass": 300, "size_033l": 200},
    "prod_honey_linden": {"size_1l": 500, "size_05l_plastic": 250, "size_05l_glass": 250, "size_033l": 170},
    "prod_honey_buckwheat": {"size_1l": 460, "size_05l_plastic": 230, "size_05l_glass": 230, "size_033l": 160},
    "prod_honey_mix": {"size_1l": 360, "size_05l_plastic": 180, "size_05l_glass": 180, "size_033l": 120},
    "prod_honey_rapeseed": {"size_05l_plastic": 150, "size_05l_glass": 150, "size_033l": 100},
    "prod_honey_sunflower": {"size_1l": 280, "size_05l_plastic": 140, "size_05l_glass": 140, "size_033l": 100},
}

HONEY_NAMES_MAP = {
    "prod_honey_acacia": "Мед з акації",
    "prod_honey_linden": "Мед з липи",
    "prod_honey_buckwheat": "Мед з гречки",
    "prod_honey_mix": "Мед з різнотрав'я",
    "prod_honey_rapeseed": "Мед з ріпаку",
    "prod_honey_sunflower": "Мед з соняха",
}

SIZE_NAMES_MAP = {
    "size_1l": "1 л (1.4 кг) — пластикове відерце",
    "size_05l_plastic": "0.5 л (0.7 кг) — пластикове відерце",
    "size_05l_glass": "0.5 л (0.7 кг) — скляна баночка",
    "size_033l": "0.33 л (0.45 кг) — пластикове відерце",
}

CANDLE_CLASSIC_TYPES = [{"id": "candle_classic_item", "name": "🕯 Класична свічка (1 шт)", "price": 20}]
CANDLE_CLASSIC_DESC = "🕯 **Звичайна воскова свічка** зроблена на 100% з натурального бджолиного воску без хімічних домішок."

CANDLE_VOSHCHYNA_TYPES = [
    {"id": "candle_v_xl", "name": "🕯 Розмір XL (26 × 3 см)", "price": 80},
    {"id": "candle_v_l", "name": "🕯 Розмір L (13 × 4.5 см)", "price": 80},
    {"id": "candle_v_m", "name": "🕯 Розмір M (13 × 3 см)", "price": 50},
    {"id": "candle_v_s", "name": "🕯 Розмір S (6.5 × 4.5 см)", "price": 50},
]
CANDLE_VOSHCHYNA_DESC = "🕯 **Свічки з натуральної вощини** мають гарну рифлену текстуру."

CANDLE_SHAPED_TYPES = [
    {"id": "candle_sh_corn", "name": "🌽 Кукурузка", "price": 60},
    {"id": "candle_sh_pumpkin", "name": "🎃 Гарбузик", "price": 50},
    {"id": "candle_sh_egg", "name": "🥚 Яєчко", "price": 50},
    {"id": "candle_sh_lotus", "name": "🌸 Лотос", "price": 40},
    {"id": "candle_sh_heart", "name": "❤️ Сердечко", "price": 40},
    {"id": "candle_sh_tree", "name": "🎄 Ялинка", "price": 40},
    {"id": "candle_sh_santa", "name": "🎅 Санта Клаус", "price": 40},
    {"id": "candle_sh_angel", "name": "👼 Янголятко", "price": 20},
]
CANDLE_SHAPED_DESC = "🕯 **Формові свічки ручної роботи** з чистого бджолиного воску оригінальних форм."

BEE_PRODUCTS_DETAILS = {
    "prod_pollen": {
        "title": "🐝 **Бджолиний пилок (обніжжя)**",
        "text": "Оберіть бажане фасування:",
        "items": [{"id": "item_pollen_100g", "name": "🌾 100 грам", "price": 70}],
        "info": "🌾 **Бджолиний пилок (обніжжя)** — природний мультивітамінний комплекс!"
    },
    "prod_perga": {
        "title": "🐝 **Перга бджолина (бджолиний хліб)**",
        "text": "Оберіть бажане фасування:",
        "items": [{"id": "item_perga_50g", "name": "👑 50 грам", "price": 140}],
        "info": "👑 **Перга** — найпотужніший біостимулятор."
    },
    "prod_propolis_tincture": {
        "title": "🐝 **Настоянка прополісу**",
        "text": "🧪 **Склад:** Настоянка 10% на 70% спирті.\n\nОберіть бажаний об'єм:",
        "items": [{"id": "item_tincture_50ml", "name": "🧪 50 мл", "price": 100}],
        "info": "🧪 **Настоянка прополісу** — потужний природний антибіотик."
    },
    "prod_propolis_balls": {
        "title": "🐝 **Натуральний прополіс (у кульках)**",
        "text": "📦 **Фасування:** Кожна кулька має вагу 10 грамів.\n\nОберіть позицію:",
        "items": [{"id": "item_propolis_10g", "name": "🟤 1 кулька (10 г)", "price": 40}],
        "info": "🟤 **Натуральний очищений прополіс** у зручних кульках."
    },
    "prod_wax_ingots": {
        "title": "🐝 **Натуральний бджолиний віск (у злитках)**",
        "text": "🧈 **Фасування:** Кожен злиток має вагу 45–54 грами.\n\nОберіть позицію:",
        "items": [{"id": "item_wax_ingot", "name": "🧈 1 злиток (45–54 г)", "price": 25}],
        "info": "🧈 **Чистий пасічний віск** без домішок."
    }
}

AMOSOV_PASTE_TYPES = [
    {"id": "amosov_033l", "name": "🍯 0.33 л (400 г) — відерце", "price": 300},
    {"id": "amosov_05l", "name": "🍯 0.5 л (600 г) — відерце", "price": 450},
    {"id": "amosov_1l", "name": "🍯 1 л (1200 г) — відерце", "price": 900},
]
CREAMED_HONEY_TYPES = [{"id": "cream_classic_025l", "name": "🍯 Класичний 0.25 л (320 г)", "price": 150}]
NUTS_HONEY_TYPES = [
    {"id": "nuts_walnut_05l", "name": "🍯 З волоським горіхом 0.5 л", "price": 340},
    {"id": "nuts_mix_025l", "name": "🍯 Мікс горішків 0.25 л", "price": 300},
]
ZABRUS_TYPES = [
    {"id": "zabrus_acacia", "name": "🍯 З акації (650 г — відерце)", "price": 160},
    {"id": "zabrus_linden", "name": "🍯 З липи (650 г — відерце)", "price": 150},
    {"id": "zabrus_mix", "name": "🍯 З різнотрав'я (650 г — відерце)", "price": 140},
]
HONEYCOMB_TYPES = [{"id": "honeycomb_acacia", "name": "🍯 Мед в сотах з акації (200+ г)", "price": 200}]

HONEY_PRICES = {
    "prod_honey_acacia": [
        {"id": "size_1l", "name": "1 л (1.4 кг) — пластикове відерце", "price": 600},
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 300},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 300},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 200},
    ],
    "prod_honey_linden": [
        {"id": "size_1l", "name": "1 л (1.4 кг) — пластикове відерце", "price": 500},
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 250},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 250},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 170},
    ],
    "prod_honey_buckwheat": [
        {"id": "size_1l", "name": "1 л (1.4 кг) — пластикове відерце", "price": 460},
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 230},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 230},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 160},
    ],
    "prod_honey_mix": [
        {"id": "size_1l", "name": "1 л (1.4 кг) — пластикове відерце", "price": 360},
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 180},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 180},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 120},
    ],
    "prod_honey_rapeseed": [
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 150},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 150},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 100},
    ],
    "prod_honey_sunflower": [
        {"id": "size_1l", "name": "1 л (1.4 кг) — пластикове відерце", "price": 280},
        {"id": "size_05l_plastic", "name": "0.5 л (0.7 кг) — пластикове відерце", "price": 140},
        {"id": "size_05l_glass", "name": "0.5 л (0.7 кг) — скляна баночка", "price": 140},
        {"id": "size_033l", "name": "0.33 л (0.45 кг) — пластикове відерце", "price": 100},
    ],
}

HONEY_DESCRIPTIONS = {
    "prod_honey_acacia": "🌿 Акацієвий мед має м'який смак, довго не кристалізується.",
    "prod_honey_linden": "🌸 Липовий мед — визнаний еталон при застудах.",
    "prod_honey_buckwheat": "🌾 Гречаний мед багатий на залізо та мікроелементи.",
    "prod_honey_mix": "🪻 Мед з різнотрав'я тонізує та зміцнює організм.",
    "prod_honey_rapeseed": "🌼 Ріпаковий мед багатий на антиоксиданти.",
    "prod_honey_sunflower": "🌻 Соняшниковий мед — чудове джерело енергії.",
}


# --- УНІВЕРСАЛЬНА ФУНКЦІЯ ДЛЯ СТВОРЕННЯ НАВІГАЦІЙНИХ КНОПОК ---
def get_nav_keyboard(back_callback: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()


# --- ФУНКЦІЇ КЛАВІАТУР МЕНЮ ---

def get_main_categories_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🍯 Мед", callback_data="category_honey"))
    builder.row(InlineKeyboardButton(text="🎁 Делікатеси та смаколики", callback_data="category_delicacies"))
    builder.row(InlineKeyboardButton(text="🐝 Інші продукти бджільництва", callback_data="category_bee_products"))
    builder.row(InlineKeyboardButton(text="🕯 Натуральні воскові свічки", callback_data="category_candles"))
    return builder.as_markup()

def get_products_keyboard(category_key):
    builder = InlineKeyboardBuilder()
    for item in PRODUCTS_DATA.get(category_key, []):
        builder.row(InlineKeyboardButton(text=item["name"], callback_data=item["id"]))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="go_to_start"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_delivery_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚚 Нова Пошта", callback_data="deliv_np"))
    builder.row(InlineKeyboardButton(text="📦 Укрпошта", callback_data="deliv_ukrposhta"))
    builder.row(InlineKeyboardButton(text="🚗 Доставка по м. Ірпінь", callback_data="deliv_irpin"))
    builder.row(InlineKeyboardButton(text="📍 Самовивіз", callback_data="deliv_pickup"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_quantity"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_payment_keyboard(delivery_type: str, back_callback: str):
    builder = InlineKeyboardBuilder()
    if delivery_type in ["Нова Пошта", "Укрпошта"]:
        builder.row(InlineKeyboardButton(text="💵 Післяплата (при отриманні)", callback_data="pay_cod"))
    else:
        builder.row(InlineKeyboardButton(text="💵 Готівкою при отриманні", callback_data="pay_cash"))
        
    builder.row(InlineKeyboardButton(text="💳 Оплата на картку", callback_data="pay_card"))
    builder.row(InlineKeyboardButton(text="📄 За реквізитами (IBAN)", callback_data="pay_iban"))
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_cod_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Згоден з умовами післяплати", callback_data="confirm_cod"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_payment_choice"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_payment_details_keyboard(back_callback: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Я сплатив / сплатила", callback_data="pay_confirmed"))
    builder.row(InlineKeyboardButton(text="💬 З'єднатися з нами (надіслати чек)", url=f"https://t.me/{ADMIN_USERNAME}"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_candle_classic_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in CANDLE_CLASSIC_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="candle_classic_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_candles"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_candle_voshchyna_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in CANDLE_VOSHCHYNA_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="candle_voshchyna_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_candles"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_candle_shaped_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in CANDLE_SHAPED_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="candle_shaped_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_candles"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_bee_product_sub_keyboard(product_id):
    builder = InlineKeyboardBuilder()
    data = BEE_PRODUCTS_DETAILS.get(product_id, {})
    for item in data.get("items", []):
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data=f"bee_info_{product_id}"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_bee_products"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_amosov_paste_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in AMOSOV_PASTE_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="amosov_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delicacies"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_creamed_honey_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in CREAMED_HONEY_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="creamed_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delicacies"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_nuts_honey_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in NUTS_HONEY_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="nuts_honey_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delicacies"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_zabrus_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in ZABRUS_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="zabrus_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delicacies"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_honeycomb_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for item in HONEYCOMB_TYPES:
        builder.row(InlineKeyboardButton(text=f"{item['name']} — {item['price']} грн", callback_data=item["id"]))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="honeycomb_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delicacies"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()

def get_honey_sizes_keyboard(honey_product_id):
    builder = InlineKeyboardBuilder()
    for size in HONEY_PRICES.get(honey_product_id, []):
        builder.row(InlineKeyboardButton(text=f"{size['name']} — {size['price']} грн", callback_data=f"size_h_{size['id']}"))
    builder.row(InlineKeyboardButton(text="ℹ️ Інформація про користь", callback_data="honey_info"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_honey_list"),
        InlineKeyboardButton(text="🏠 На початок", callback_data="go_to_start")
    )
    return builder.as_markup()


async def ask_for_quantity(callback: types.CallbackQuery, state: FSMContext, item_key: str):
    await state.update_data(chosen_variant=item_key)
    await callback.message.edit_text(
        text="🔢 Введіть бажану кількість товару (цифрами, наприклад: `1`, `2`, `3` тощо):",
        reply_markup=get_nav_keyboard("back_to_product_variants"),
        parse_mode="Markdown"
    )
    await state.set_state(OrderProcess.waiting_for_quantity)
    await callback.answer()


# --- ОБРОБНИКИ ПОДІЙ НАВІГАЦІЇ ТА ГОЛОВНОГО МЕНЮ ---

async def reset_to_main_menu(callback_or_message, state: FSMContext):
    await state.clear()
    greeting_text = "Вітаємо вас у Bee | Honey! 🐝\n\nЯ допоможу вам легко та швидко оформити замовлення.\nОберіть, будь ласка, що саме вас цікавить:"
    
    if isinstance(callback_or_message, types.CallbackQuery):
        # Прибираємо кнопки зі старого повідомлення
        try:
            await callback_or_message.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        # Надсилаємо нове головне меню в самий низ чату
        await callback_or_message.message.answer(text=greeting_text, reply_markup=get_main_categories_keyboard())
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(text=greeting_text, reply_markup=get_main_categories_keyboard())
    
    await state.set_state(OrderProcess.waiting_for_category)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await reset_to_main_menu(message, state)

@dp.callback_query(F.data == "go_to_start")
async def go_to_start_handler(callback: types.CallbackQuery, state: FSMContext):
    await reset_to_main_menu(callback, state)

@dp.callback_query(OrderProcess.waiting_for_product, F.data == "back_to_categories")
async def back_to_categories_handler(callback: types.CallbackQuery, state: FSMContext):
    await reset_to_main_menu(callback, state)

@dp.callback_query(OrderProcess.waiting_for_category, F.data.startswith("category_"))
async def process_category_selection(callback: types.CallbackQuery, state: FSMContext):
    category_key = callback.data.split("_", 1)[1]
    await state.update_data(chosen_category=category_key)

    if category_key == "honey":
        text = "Ви обрали категорію **Мед** 🍯\nОберіть бажаний сорт:"
    elif category_key == "delicacies":
        text = "Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:"
    elif category_key == "bee_products":
        text = "Ви обрали **Інші продукти бджільництва** 🐝\nОберіть позицію, що вас цікавить:"
    elif category_key == "candles":
        text = "Ви обрали **Натуральні воскові свічки** 🕯\nОберіть потрібний тип свічки:"
    else:
        text = "Оберіть позицію:"

    await callback.message.edit_text(text=text, reply_markup=get_products_keyboard(category_key), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_product, F.data.startswith("prod_"))
async def process_product_selection(callback: types.CallbackQuery, state: FSMContext):
    product_id = callback.data
    await state.update_data(chosen_product=product_id)

    if product_id == "prod_zabrus":
        await callback.message.edit_text(text="Ви обрали **Забрус** 🎁\nОберіть бажаний різновид:", reply_markup=get_zabrus_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_zabrus_sub)
    elif product_id == "prod_honeycomb":
        await callback.message.edit_text(text="Ви обрали **Мед у стільниках (сотах)** 🎁\nОберіть позицію:", reply_markup=get_honeycomb_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_honeycomb_sub)
    elif product_id == "prod_nuts_honey":
        await callback.message.edit_text(text="Ви обрали **Акацієвий мед з горішками** 🎁\nОберіть бажаний варіант:", reply_markup=get_nuts_honey_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_nuts_honey_sub)
    elif product_id == "prod_creamed_honey":
        await callback.message.edit_text(text="Ви обрали **Крем-мед з добавками** 🎁\nОберіть бажаний варіант:", reply_markup=get_creamed_honey_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_creamed_sub)
    elif product_id == "prod_amosov_paste":
        await callback.message.edit_text(text="Ви обрали **Пасту Амосова з пилком** 🎁\nОберіть бажаний об'єм:", reply_markup=get_amosov_paste_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_amosov_sub)
    elif product_id in BEE_PRODUCTS_DETAILS:
        details = BEE_PRODUCTS_DETAILS[product_id]
        await callback.message.edit_text(text=f"{details['title']}\n\n{details['text']}", reply_markup=get_bee_product_sub_keyboard(product_id), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_bee_prod_sub)
    elif product_id == "prod_candle_classic":
        await callback.message.edit_text(text="Ви обрали **Звичайну воскову свічку** 🕯\nОберіть позицію:", reply_markup=get_candle_classic_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_candle_classic_sub)
    elif product_id == "prod_candle_voshchyna":
        await callback.message.edit_text(text="Ви обрали **Свічки з вощини** 🕯\nОберіть розмір:", reply_markup=get_candle_voshchyna_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_candle_voshchyna_sub)
    elif product_id == "prod_candle_shaped":
        await callback.message.edit_text(text="Ви обрали **Формові свічки** 🕯\nОберіть форму:", reply_markup=get_candle_shaped_sub_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_candle_shaped_sub)
    elif product_id.startswith("prod_honey_"):
        await callback.message.edit_text(text="🍯 Оберіть бажаний об'єм та фасування:", reply_markup=get_honey_sizes_keyboard(product_id), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_honey_size)
        
    await callback.answer()


# Обробники підменю свічок
@dp.callback_query(OrderProcess.waiting_for_candle_classic_sub, F.data == "candle_classic_info")
async def candle_classic_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=f"💡 **Особливості:**\n\n{CANDLE_CLASSIC_DESC}", reply_markup=get_nav_keyboard("back_to_candle_classic_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.candle_classic_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.candle_classic_info_view, F.data == "back_to_candle_classic_sub")
async def back_to_candle_classic_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Звичайну воскову свічку** 🕯\nОберіть позицію:", reply_markup=get_candle_classic_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_candle_classic_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_classic_sub, F.data == "back_to_candles")
async def back_to_candles_from_classic_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Натуральні воскові свічки** 🕯\nОберіть потрібний тип свічки:", reply_markup=get_products_keyboard("candles"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_classic_sub, F.data == "candle_classic_item")
async def process_candle_classic_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Свічки з вощини
@dp.callback_query(OrderProcess.waiting_for_candle_voshchyna_sub, F.data == "candle_voshchyna_info")
async def candle_voshchyna_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=f"💡 **Особливості:**\n\n{CANDLE_VOSHCHYNA_DESC}", reply_markup=get_nav_keyboard("back_to_candle_voshchyna_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.candle_voshchyna_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.candle_voshchyna_info_view, F.data == "back_to_candle_voshchyna_sub")
async def back_to_candle_voshchyna_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Свічки з вощини** 🕯\nОберіть розмір:", reply_markup=get_candle_voshchyna_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_candle_voshchyna_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_voshchyna_sub, F.data == "back_to_candles")
async def back_to_candles_from_voshchyna_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Натуральні воскові свічки** 🕯\nОберіть потрібний тип свічки:", reply_markup=get_products_keyboard("candles"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_voshchyna_sub, F.data.startswith("candle_v_"))
async def process_candle_voshchyna_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Формові свічки
@dp.callback_query(OrderProcess.waiting_for_candle_shaped_sub, F.data == "candle_shaped_info")
async def candle_shaped_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=f"💡 **Особливості:**\n\n{CANDLE_SHAPED_DESC}", reply_markup=get_nav_keyboard("back_to_candle_shaped_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.candle_shaped_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.candle_shaped_info_view, F.data == "back_to_candle_shaped_sub")
async def back_to_candle_shaped_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Формові свічки** 🕯\nОберіть форму:", reply_markup=get_candle_shaped_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_candle_shaped_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_shaped_sub, F.data == "back_to_candles")
async def back_to_candles_from_shaped_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Натуральні воскові свічки** 🕯\nОберіть потрібний тип свічки:", reply_markup=get_products_keyboard("candles"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_candle_shaped_sub, F.data.startswith("candle_sh_"))
async def process_candle_shaped_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Інші продукти бджільництва
@dp.callback_query(OrderProcess.waiting_for_bee_prod_sub, F.data.startswith("bee_info_"))
async def bee_prod_info_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = callback.data.replace("bee_info_", "")
    details = BEE_PRODUCTS_DETAILS.get(product_id, {})
    await callback.message.edit_text(text=f"💡 **Корисні властивості:**\n\n{details.get('info', '')}", reply_markup=get_nav_keyboard(f"back_to_bee_sub_{product_id}"), parse_mode="Markdown")
    await state.set_state(OrderProcess.bee_prod_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.bee_prod_info_view, F.data.startswith("back_to_bee_sub_"))
async def back_to_bee_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = callback.data.replace("back_to_bee_sub_", "")
    details = BEE_PRODUCTS_DETAILS.get(product_id, {})
    await callback.message.edit_text(text=f"{details['title']}\n\n{details['text']}", reply_markup=get_bee_product_sub_keyboard(product_id), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_bee_prod_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_bee_prod_sub, F.data == "back_to_bee_products")
async def back_to_bee_products_list_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Інші продукти бджільництва** 🐝\nОберіть позицію, що вас цікавить:", reply_markup=get_products_keyboard("bee_products"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_bee_prod_sub, F.data.startswith("item_"))
async def process_bee_item_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Паста Амосова
@dp.callback_query(OrderProcess.waiting_for_amosov_sub, F.data == "amosov_info")
async def amosov_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="💡 **Корисні властивості:** Паста Амосова чудово зміцнює серце та імунітет!", reply_markup=get_nav_keyboard("back_to_amosov_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.amosov_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.amosov_info_view, F.data == "back_to_amosov_sub")
async def back_to_amosov_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Пасту Амосова з пилком** 🎁\nОберіть бажаний об'єм:", reply_markup=get_amosov_paste_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_amosov_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_amosov_sub, F.data == "back_to_delicacies")
async def back_to_delicacies_from_amosov_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:", reply_markup=get_products_keyboard("delicacies"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_amosov_sub, F.data.startswith("amosov_"))
async def process_amosov_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Крем-мед
@dp.callback_query(OrderProcess.waiting_for_creamed_sub, F.data == "creamed_info")
async def creamed_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="💡 **Корисні властивості:** Крем-мед зберігає всі вітаміни та має ніжну текстуру.", reply_markup=get_nav_keyboard("back_to_creamed_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.creamed_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.creamed_info_view, F.data == "back_to_creamed_sub")
async def back_to_creamed_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Крем-мед з добавками** 🎁\nОберіть бажаний варіант:", reply_markup=get_creamed_honey_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_creamed_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_creamed_sub, F.data == "back_to_delicacies")
async def back_to_delicacies_from_creamed_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:", reply_markup=get_products_keyboard("delicacies"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_creamed_sub, F.data.startswith("cream_"))
async def process_creamed_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Мед з горішками
@dp.callback_query(OrderProcess.waiting_for_nuts_honey_sub, F.data == "nuts_honey_info")
async def nuts_honey_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="💡 **Корисні властивості:** Мед з горішками ідеально відновлює сили та живить мозок.", reply_markup=get_nav_keyboard("back_to_nuts_honey_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.nuts_honey_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.nuts_honey_info_view, F.data == "back_to_nuts_honey_sub")
async def back_to_nuts_honey_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Акацієвий мед з горішками** 🎁\nОберіть бажаний варіант:", reply_markup=get_nuts_honey_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_nuts_honey_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_nuts_honey_sub, F.data == "back_to_delicacies")
async def back_to_delicacies_from_nuts_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:", reply_markup=get_products_keyboard("delicacies"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_nuts_honey_sub, F.data.startswith("nuts_"))
async def process_nuts_honey_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Забрус
@dp.callback_query(OrderProcess.waiting_for_zabrus_sub, F.data == "zabrus_info")
async def zabrus_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="💡 **Корисні властивості:** Жування забрусу дезінфікує ротову порожнину та зміцнює імунітет.", reply_markup=get_nav_keyboard("back_to_zabrus_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.zabrus_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.zabrus_info_view, F.data == "back_to_zabrus_sub")
async def back_to_zabrus_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Забрус** 🎁\nОберіть бажаний різновид:", reply_markup=get_zabrus_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_zabrus_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_zabrus_sub, F.data == "back_to_delicacies")
async def back_to_delicacies_from_zabrus_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:", reply_markup=get_products_keyboard("delicacies"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_zabrus_sub, F.data.startswith("zabrus_"))
async def process_zabrus_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Сотовий мед
@dp.callback_query(OrderProcess.waiting_for_honeycomb_sub, F.data == "honeycomb_info")
async def honeycomb_info_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="💡 **Корисні властивості:** Мед у сотах — природний антибіотик та джерело вітамінів.", reply_markup=get_nav_keyboard("back_to_honeycomb_sub"), parse_mode="Markdown")
    await state.set_state(OrderProcess.honeycomb_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.honeycomb_info_view, F.data == "back_to_honeycomb_sub")
async def back_to_honeycomb_sub_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Мед у стільниках (сотах)** 🎁\nОберіть позицію:", reply_markup=get_honeycomb_sub_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_honeycomb_sub)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_honeycomb_sub, F.data == "back_to_delicacies")
async def back_to_delicacies_from_honeycomb_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали **Делікатеси та смаколики** 🎁\nОберіть смаколик:", reply_markup=get_products_keyboard("delicacies"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_honeycomb_sub, F.data.startswith("honeycomb_"))
async def process_honeycomb_sel(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# Сорти меду (фасування)
@dp.callback_query(OrderProcess.waiting_for_honey_size, F.data == "honey_info")
async def honey_info_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("chosen_product")
    info_text = HONEY_DESCRIPTIONS.get(product_id, "Корисний натуральний продукт бджільництва!")
    await callback.message.edit_text(text=f"💡 **Корисні властивості:**\n{info_text}", reply_markup=get_nav_keyboard(f"back_to_sizes_{product_id}"), parse_mode="Markdown")
    await state.set_state(OrderProcess.honey_info_view)
    await callback.answer()

@dp.callback_query(OrderProcess.honey_info_view, F.data.startswith("back_to_sizes_"))
async def back_to_sizes_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("chosen_product")
    await callback.message.edit_text(text="🍯 Оберіть бажаний об'єм та фасування:", reply_markup=get_honey_sizes_keyboard(product_id), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_honey_size)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_honey_size, F.data == "back_to_honey_list")
async def back_to_honey_list_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Ви обрали категорію **Мед** 🍯\nОберіть бажаний сорт:", reply_markup=get_products_keyboard("honey"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderProcess.waiting_for_honey_size, F.data.startswith("size_h_"))
async def process_honey_size_selection(callback: types.CallbackQuery, state: FSMContext):
    await ask_for_quantity(callback, state, callback.data)


# --- ОБРОБНИК ВВЕДЕННЯ КІЛЬКОСТІ ➔ ВИБІР ДОСТАВКИ ---
@dp.message(OrderProcess.waiting_for_quantity)
async def process_quantity_input(message: types.Message, state: FSMContext):
    user_input = message.text.strip()
    
    if not user_input.isdigit() or int(user_input) <= 0:
        await message.answer("⚠️ Будь ласка, введіть коректну кількість числом (наприклад: `1`, `2`, `3` тощо).", reply_markup=get_nav_keyboard("back_to_product_variants"))
        return
    
    quantity = int(user_input)
    await state.update_data(quantity=quantity)
    
    await message.answer(
        f"✅ Кількість: **{quantity} шт.**\n\nОберіть зручний спосіб доставки:",
        reply_markup=get_delivery_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderProcess.waiting_for_delivery_type)

@dp.callback_query(OrderProcess.waiting_for_delivery_type, F.data == "back_to_quantity")
async def back_to_quantity_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text="🔢 Введіть бажану кількість товару (цифрами, наприклад: `1`, `2`, `3` тощо):",
        reply_markup=get_nav_keyboard("back_to_product_variants"),
        parse_mode="Markdown"
    )
    await state.set_state(OrderProcess.waiting_for_quantity)
    await callback.answer()

@dp.callback_query(F.data == "back_to_product_variants")
async def back_to_product_variants_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category_key = data.get("chosen_category")
    product_id = data.get("chosen_product")
    
    if category_key == "candles":
        if product_id == "prod_candle_classic":
            await callback.message.edit_text(text="Ви обрали **Звичайну воскову свічку** 🕯\nОберіть позицію:", reply_markup=get_candle_classic_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_candle_classic_sub)
        elif product_id == "prod_candle_voshchyna":
            await callback.message.edit_text(text="Ви обрали **Свічки з вощини** 🕯\nОберіть розмір:", reply_markup=get_candle_voshchyna_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_candle_voshchyna_sub)
        elif product_id == "prod_candle_shaped":
            await callback.message.edit_text(text="Ви обрали **Формові свічки** 🕯\nОберіть форму:", reply_markup=get_candle_shaped_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_candle_shaped_sub)
    elif category_key == "bee_products":
        details = BEE_PRODUCTS_DETAILS.get(product_id, {})
        await callback.message.edit_text(text=f"{details['title']}\n\n{details['text']}", reply_markup=get_bee_product_sub_keyboard(product_id), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_bee_prod_sub)
    elif category_key == "delicacies":
        if product_id == "prod_zabrus":
            await callback.message.edit_text(text="Ви обрали **Забрус** 🎁\nОберіть бажаний різновид:", reply_markup=get_zabrus_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_zabrus_sub)
        elif product_id == "prod_honeycomb":
            await callback.message.edit_text(text="Ви обрали **Мед у стільниках (сотах)** 🎁\nОберіть позицію:", reply_markup=get_honeycomb_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_honeycomb_sub)
        elif product_id == "prod_nuts_honey":
            await callback.message.edit_text(text="Ви обрали **Акацієвий мед з горішками** 🎁\nОберіть бажаний варіант:", reply_markup=get_nuts_honey_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_nuts_honey_sub)
        elif product_id == "prod_creamed_honey":
            await callback.message.edit_text(text="Ви обрали **Крем-мед з добавками** 🎁\nОберіть бажаний варіант:", reply_markup=get_creamed_honey_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_creamed_sub)
        elif product_id == "prod_amosov_paste":
            await callback.message.edit_text(text="Ви обрали **Пасту Амосова з пилком** 🎁\nОберіть бажаний об'єм:", reply_markup=get_amosov_paste_sub_keyboard(), parse_mode="Markdown")
            await state.set_state(OrderProcess.waiting_for_amosov_sub)
    elif category_key == "honey":
        await callback.message.edit_text(text="🍯 Оберіть бажаний об'єм та фасування:", reply_markup=get_honey_sizes_keyboard(product_id), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_honey_size)
    else:
        await reset_to_main_menu(callback, state)
        
    await callback.answer()


# --- ОБРОБКА ВИБОРУ СПОСОБУ ДОСТАВКИ ---
@dp.callback_query(OrderProcess.waiting_for_delivery_type, F.data.startswith("deliv_"))
async def process_delivery_choice(callback: types.CallbackQuery, state: FSMContext):
    delivery_code = callback.data
    
    if delivery_code == "deliv_pickup":
        await state.update_data(delivery_type="Самовивіз")
        pickup_info = (
            "📍 **Самовивіз здійснюється за адресою:**\n"
            "м. Ірпінь, вул. Озерна 17\n"
            "🗓 **Дні та час:** Вівторок та Четвер з 9:00 до 18:00\n\n"
            "👤 Введіть ваше **Ім'я**:"
        )
        await callback.message.edit_text(text=pickup_info, reply_markup=get_nav_keyboard("back_to_delivery_choice"), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_fio)

    elif delivery_code == "deliv_irpin":
        await state.update_data(delivery_type="Доставка по м. Ірпінь")
        await callback.message.edit_text(text="🚗 **Доставка по м. Ірпінь**\n\nВведіть ваше **Прізвище та Ім'я**:", reply_markup=get_nav_keyboard("back_to_delivery_choice"), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_fio)

    elif delivery_code == "deliv_np":
        await state.update_data(delivery_type="Нова Пошта")
        await callback.message.edit_text(text="🚚 **Доставка Новою Поштою**\n\nВведіть ваші **ПІБ (Прізвище, Ім'я, По батькові)**:", reply_markup=get_nav_keyboard("back_to_delivery_choice"), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_fio)

    elif delivery_code == "deliv_ukrposhta":
        await state.update_data(delivery_type="Укрпошта")
        await callback.message.edit_text(text="📦 **Доставка Укрпоштою**\n\nВведіть ваші **ПІБ (Прізвище, Ім'я, По батькові)**:", reply_markup=get_nav_keyboard("back_to_delivery_choice"), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_fio)

    await callback.answer()

@dp.callback_query(F.data == "back_to_delivery_choice")
async def back_to_delivery_choice_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    await callback.message.edit_text(
        text=f"✅ Кількість: **{quantity} шт.**\n\nОберіть зручний спосіб доставки:",
        reply_markup=get_delivery_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderProcess.waiting_for_delivery_type)
    await callback.answer()


# --- ЗБИРАННЯ ДАНИХ КЛІЄНТА ---

@dp.message(OrderProcess.waiting_for_fio)
async def process_fio_input(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text.strip())
    await message.answer("📞 Введіть ваш **номер телефону** для зв'язку:", reply_markup=get_nav_keyboard("back_to_fio_step"))
    await state.set_state(OrderProcess.waiting_for_phone)

@dp.callback_query(F.data == "back_to_fio_step")
async def back_to_fio_step_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deliv_type = data.get("delivery_type")
    
    if deliv_type == "Самовивіз":
        text = "📍 **Самовивіз здійснюється за адресою:**\nм. Ірпінь, вул. Озерна 17\n🗓 **Дні та час:** Вівторок та Четвер з 9:00 до 18:00\n\n👤 Введіть ваше **Ім'я**:"
    else:
        text = "👤 Введіть ваші **ПІБ / Ім'я**:"
        
    await callback.message.edit_text(text=text, reply_markup=get_nav_keyboard("back_to_delivery_choice"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_fio)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_phone)
async def process_phone_input(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    
    data = await state.get_data()
    deliv_type = data.get("delivery_type")

    if deliv_type == "Самовивіз":
        await message.answer("💳 Оберіть зручний **спосіб оплати**:", reply_markup=get_payment_keyboard(deliv_type, "back_to_phone_step"))
        await state.set_state(OrderProcess.waiting_for_payment_type)
    elif deliv_type == "Доставка по м. Ірпінь":
        await message.answer("🏡 Введіть **адресу доставки** у м. Ірпінь (вулиця, будинок, квартира):", reply_markup=get_nav_keyboard("back_to_phone_step"))
        await state.set_state(OrderProcess.waiting_for_address)
    elif deliv_type in ["Нова Пошта", "Укрпошта"]:
        await message.answer("🏙 Введіть **місто або село** для доставки:", reply_markup=get_nav_keyboard("back_to_phone_step"))
        await state.set_state(OrderProcess.waiting_for_city)

@dp.callback_query(F.data == "back_to_phone_step")
async def back_to_phone_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="📞 Введіть ваш **номер телефону** для зв'язку:", reply_markup=get_nav_keyboard("back_to_fio_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_phone)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_city)
async def process_city_input(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    data = await state.get_data()
    deliv_type = data.get("delivery_type")

    if deliv_type == "Нова Пошта":
        await message.answer("🏢 Введіть **номер відділення Нової Пошти** (або поштомату):", reply_markup=get_nav_keyboard("back_to_city_step"))
        await state.set_state(OrderProcess.waiting_for_post_office)
    elif deliv_type == "Укрпошта":
        await message.answer("📮 Введіть **індекс відділення Укрпошти** (5 цифр):", reply_markup=get_nav_keyboard("back_to_city_step"))
        await state.set_state(OrderProcess.waiting_for_post_index)

@dp.callback_query(F.data == "back_to_city_step")
async def back_to_city_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="🏙 Введіть **місто або село** для доставки:", reply_markup=get_nav_keyboard("back_to_phone_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_city)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_post_office)
async def process_post_office_input(message: types.Message, state: FSMContext):
    await state.update_data(post_office=message.text.strip())
    data = await state.get_data()
    deliv_type = data.get("delivery_type")
    
    await message.answer("💳 Оберіть зручний **спосіб оплати**:", reply_markup=get_payment_keyboard(deliv_type, "back_to_post_office_step"))
    await state.set_state(OrderProcess.waiting_for_payment_type)

@dp.callback_query(F.data == "back_to_post_office_step")
async def back_to_post_office_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="🏢 Введіть **номер відділення Нової Пошти** (або поштомату):", reply_markup=get_nav_keyboard("back_to_city_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_post_office)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_post_index)
async def process_post_index_input(message: types.Message, state: FSMContext):
    await state.update_data(post_index=message.text.strip())
    data = await state.get_data()
    deliv_type = data.get("delivery_type")
    
    await message.answer("💳 Оберіть зручний **спосіб оплати**:", reply_markup=get_payment_keyboard(deliv_type, "back_to_post_index_step"))
    await state.set_state(OrderProcess.waiting_for_payment_type)

@dp.callback_query(F.data == "back_to_post_index_step")
async def back_to_post_index_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="📮 Введіть **індекс відділення Укрпошти** (5 цифр):", reply_markup=get_nav_keyboard("back_to_city_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_post_index)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_address)
async def process_address_input(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await message.answer("⏰ Введіть **бажаний час доставки** (наприклад: *сьогодні після 17:00*):", reply_markup=get_nav_keyboard("back_to_address_step"))
    await state.set_state(OrderProcess.waiting_for_delivery_time)

@dp.callback_query(F.data == "back_to_address_step")
async def back_to_address_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="🏡 Введіть **адресу доставки** у м. Ірпінь (вулиця, будинок, квартира):", reply_markup=get_nav_keyboard("back_to_phone_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_address)
    await callback.answer()


@dp.message(OrderProcess.waiting_for_delivery_time)
async def process_delivery_time_input(message: types.Message, state: FSMContext):
    await state.update_data(delivery_time=message.text.strip())
    data = await state.get_data()
    deliv_type = data.get("delivery_type")
    
    await message.answer("💳 Оберіть зручний **спосіб оплати**:", reply_markup=get_payment_keyboard(deliv_type, "back_to_delivery_time_step"))
    await state.set_state(OrderProcess.waiting_for_payment_type)

@dp.callback_query(F.data == "back_to_delivery_time_step")
async def back_to_delivery_time_step_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="⏰ Введіть **бажаний час доставки** (наприклад: *сьогодні після 17:00*):", reply_markup=get_nav_keyboard("back_to_address_step"), parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_delivery_time)
    await callback.answer()


# --- ОБРОБКА ВИБОРУ ОПЛАТИ ---

@dp.callback_query(OrderProcess.waiting_for_payment_type, F.data.startswith("pay_"))
async def process_payment_choice(callback: types.CallbackQuery, state: FSMContext):
    pay_code = callback.data
    payment_map = {
        "pay_cod": "Післяплата (накладений платіж)",
        "pay_cash": "Готівкою при отриманні",
        "pay_card": "Оплата на картку",
        "pay_iban": "Оплата за реквізитами (IBAN)"
    }
    
    payment_title = payment_map.get(pay_code, "Не вказано")
    await state.update_data(payment_type=payment_title)
    
    data = await state.get_data()
    deliv_type = data.get("delivery_type", "")
    quantity = data.get("quantity", 1)
    variant_key = data.get("chosen_variant")
    product_id = data.get("chosen_product")

    # Обчислюємо вартість для підрахунку комісії
    item_price = 0
    if variant_key and variant_key.startswith("size_h_"):
        size_id = variant_key.replace("size_h_", "")
        item_price = HONEY_PRICES_MAP.get(product_id, {}).get(size_id, 0)
    elif variant_key in ALL_ITEMS_INFO:
        item_price = ALL_ITEMS_INFO[variant_key]["price"]
    
    total_amount = item_price * quantity

    # ПІСЛЯПЛАТА ПОШТОЮ: Проміжний крок з інформуванням про комісію
    if pay_code == "pay_cod":
        if deliv_type == "Нова Пошта":
            cod_fee = round(total_amount * 0.02 + 20, 2)
            cod_info = (
                "⚠️ **Умови оплати при отриманні (Нова Пошта):**\n\n"
                "Зверніть увагу, що при виборі післяплати поштова служба стягує додаткову комісію за переказ коштів:\n"
                f"• **Комісія NovaPay:** 2% від суми замовлення + 20 грн (орієнтовно **+{cod_fee} грн**).\n"
                "• **Вартість доставки:** сплачується окремо за тарифами Нової Пошти при отриманні.\n\n"
                "Натисніть кнопку нижче, якщо ви згодні з цими умовами 👇"
            )
        else:  # Укрпошта
            cod_fee = round(total_amount * 0.02 + 15, 2)
            cod_info = (
                "⚠️ **Умови оплати при отриманні (Укрпошта):**\n\n"
                "Зверніть увагу, що при виборі післяплати поштова служба стягує додаткову комісію за переказ коштів:\n"
                f"• **Комісія Укрпошти:** 2% від суми замовлення + 15 грн (орієнтовно **+{cod_fee} грн**).\n"
                "• **Вартість доставки:** сплачується окремо за тарифами Укрпошти при отриманні.\n\n"
                "Натисніть кнопку нижче, якщо ви згодні з цими умовами 👇"
            )

        await callback.message.edit_text(text=cod_info, reply_markup=get_cod_confirm_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderProcess.waiting_for_cod_confirmation)

    elif pay_code == "pay_cash":
        await finalize_order(callback.message, state, callback.from_user.id)

    else:
        # Оплата на картку або IBAN
        temp_order_id = get_next_order_id()
        await state.update_data(temp_order_id=temp_order_id)
        
        if pay_code == "pay_card":
            payment_text = (
                f"🏷 **Номер вашого замовлення: №{temp_order_id}**\n\n"
                f"💳 **Номер картки для оплати:**\n`4441111076765324`\n\n"
                f"⚠️ *Будь ласка, в коментарях до оплати обов'язково вкажіть номер замовлення (№{temp_order_id})!*\n\n"
                f"💬 *Якщо ви хочете пришвидшити процес отримання замовлення, надішліть нам інформацію про оплату, чек або скріншот за допомогою кнопки нижче.*\n\n"
                f"Після здійснення платежу натисніть кнопку «✅ Я сплатив / сплатила» 👇"
            )
        elif pay_code == "pay_iban":
            payment_text = (
                f"🏷 **Номер вашого замовлення: №{temp_order_id}**\n\n"
                f"📄 **Реквізити для оплати (IBAN):**\n"
                f"`UA403220010000026006340063223`\n"
                f"ІПН/ЄДРПОУ: 3347107977\n"
                f"Отримувач: Овдієнко Павло Юрійович\n"
                f"Призначення платежу: За замовлення №{temp_order_id}\n\n"
                f"⚠️ *Обов'язково вказуйте номер замовлення в призначенні платежу!*\n\n"
                f"💬 *Якщо ви хочете пришвидшити процес отримання замовлення, надішліть нам інформацію про оплату, чек або скріншот за допомогою кнопки нижче.*\n\n"
                f"Після здійснення платежу натисніть кнопку «✅ Я сплатив / сплатила» 👇"
            )
            
        await callback.message.edit_text(
            text=payment_text, 
            reply_markup=get_payment_details_keyboard("back_to_payment_choice"), 
            parse_mode="Markdown"
        )
        await state.set_state(OrderProcess.waiting_for_payment_confirmation)
        
    await callback.answer()

# Підтвердження післяплати ("Згоден з умовами")
@dp.callback_query(OrderProcess.waiting_for_cod_confirmation, F.data == "confirm_cod")
async def process_cod_confirmation(callback: types.CallbackQuery, state: FSMContext):
    await finalize_order(callback.message, state, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data == "back_to_payment_choice")
async def back_to_payment_choice_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deliv_type = data.get("delivery_type")
    await callback.message.edit_text(
        text="💳 Оберіть зручний **спосіб оплати**:",
        reply_markup=get_payment_keyboard(deliv_type, "back_to_delivery_time_step"),
        parse_mode="Markdown"
    )
    await state.set_state(OrderProcess.waiting_for_payment_type)
    await callback.answer()


# --- ПІДТВЕРДЖЕННЯ ОПЛАТИ ("Я сплатив") ---
@dp.callback_query(OrderProcess.waiting_for_payment_confirmation, F.data == "pay_confirmed")
async def process_payment_confirmation(callback: types.CallbackQuery, state: FSMContext):
    await finalize_order(callback.message, state, callback.from_user.id)
    await callback.answer()


# --- ФІНАЛІЗАЦІЯ ЗАМОВЛЕННЯ ТА НАДСИЛАННЯ АДМІНІСТРАТОРУ ---
async def finalize_order(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    
    order_id = data.get("temp_order_id")
    if not order_id:
        order_id = get_next_order_id()
    
    deliv_type = data.get("delivery_type", "Не вказано")
    pay_type = data.get("payment_type", "Не вказано")
    quantity = data.get("quantity", 1)
    phone = data.get("phone", "Не вказано")
    fio = data.get("fio", "Не вказано")
    
    variant_key = data.get("chosen_variant")
    product_id = data.get("chosen_product")
    
    item_name = "Обраний товар"
    item_price = 0
    
    if variant_key and variant_key.startswith("size_h_"):
        size_id = variant_key.replace("size_h_", "")
        item_name = f"{HONEY_NAMES_MAP.get(product_id, 'Мед')} ({SIZE_NAMES_MAP.get(size_id, 'фасування')})"
        item_price = HONEY_PRICES_MAP.get(product_id, {}).get(size_id, 0)
    elif variant_key in ALL_ITEMS_INFO:
        item_info = ALL_ITEMS_INFO[variant_key]
        item_name = item_info["name"]
        item_price = item_info["price"]

    total_amount = item_price * quantity
    
    is_prepaid = pay_type in ["Оплата на картку", "Оплата за реквізитами (IBAN)"]
    
    order_summary = f"🎉 **Замовлення №{order_id} успішно прийнято!**\n\n"
    order_summary += f"🛍 **Товар:** {item_name}\n"
    order_summary += f"📦 **Кількість:** {quantity} шт.\n"
    order_summary += f"💵 **Сума замовлення:** **{total_amount} грн**\n"
    order_summary += f"🚚 **Спосіб доставки:** {deliv_type}\n"
    order_summary += f"💳 **Спосіб оплати:** {pay_type}\n\n"
    
    if is_prepaid:
        order_summary += "⏳ **Ми зв'яжемося з вами одразу після надходження коштів на рахунок!**\n\n"
    
    if deliv_type == "Самовивіз":
        order_summary += f"👤 **Ім'я клієнта:** {fio}\n"
        order_summary += f"📞 **Телефон:** {phone}\n"
        order_summary += (
            "\n📍 **Адреса самовивозу:** м. Ірпінь, вул. Озерна 17\n"
            "🗓 **Час роботи:** Вівторок та Четвер з 9:00 до 18:00\n"
        )
    elif deliv_type == "Доставка по м. Ірпінь":
        order_summary += f"👤 **Клієнт:** {fio}\n"
        order_summary += f"📞 **Телефон:** {phone}\n"
        order_summary += f"🏡 **Адреса:** {data.get('address')}\n"
        order_summary += f"⏰ **Час:** {data.get('delivery_time')}\n"
        if not is_prepaid:
            order_summary += "\n📞 **Ми зв'яжемося з вами найближчим часом для уточнення деталей!**\n"
    elif deliv_type == "Нова Пошта":
        order_summary += f"👤 **ПІБ:** {fio}\n"
        order_summary += f"📞 **Телефон:** {phone}\n"
        order_summary += f"🏙 **Населений пункт:** {data.get('city')}\n"
        order_summary += f"🏢 **Відділення НП:** {data.get('post_office')}\n"
    elif deliv_type == "Укрпошта":
        order_summary += f"👤 **ПІБ:** {fio}\n"
        order_summary += f"📞 **Телефон:** {phone}\n"
        order_summary += f"🏙 **Населений пункт:** {data.get('city')}\n"
        order_summary += f"📮 **Індекс:** {data.get('post_index')}\n"

    order_summary += "\nДякуємо за замовлення у **Bee | Honey**! 🐝"

    admin_notification = f"🔔 **НОВЕ ЗАМОВЛЕННЯ №{order_id}!** 🔔\n\n"
    admin_notification += f"🛍 **Товар:** {item_name} ({quantity} шт.)\n"
    admin_notification += f"💵 **Сума:** {total_amount} грн\n"
    admin_notification += f"🚚 **Доставка:** {deliv_type}\n"
    admin_notification += f"💳 **Оплата:** {pay_type}\n"
    admin_notification += f"👤 **Клієнт:** {fio}\n"
    admin_notification += f"📞 **Телефон:** {phone}\n"
    admin_notification += f"🆔 **Telegram ID клієнта:** `{user_id}`\n"

    if deliv_type == "Доставка по м. Ірпінь":
        admin_notification += f"🏡 **Адреса:** {data.get('address')}\n⏰ **Час:** {data.get('delivery_time')}\n"
    elif deliv_type in ["Нова Пошта", "Укрпошта"]:
        admin_notification += f"🏙 **Місто:** {data.get('city')}\n"
        if deliv_type == "Нова Пошта":
            admin_notification += f"🏢 **Відділення:** {data.get('post_office')}\n"
        else:
            admin_notification += f"📮 **Індекс:** {data.get('post_index')}\n"

    if is_prepaid:
        admin_notification += "\n⏳ *Очікується надходження коштів або чек від клієнта.*"

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не вдалося надіслати сповіщення адміну: {e}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Зробити нове замовлення", callback_data="go_to_start"))

    # Надсилаємо фінальний чек новим повідомленням у самий низ чату, а старе очищуємо від кнопок
    if isinstance(message, types.Message):
        await message.answer(order_summary, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await message.bot.send_message(chat_id=message.chat.id, text=order_summary, reply_markup=builder.as_markup(), parse_mode="Markdown")
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        
    await state.clear()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

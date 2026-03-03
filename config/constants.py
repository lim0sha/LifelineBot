ALL_PROFILE_FIELDS = [
    "username",
    "profile_name",
    "Карьерный рост",
    "Текущее направление",
    "Текущий возраст",
    "Текущая роль",
    "Доп. комментарий",
    "Цель. Куда? Зачем?",
    "Как? Понимание, как добраться до цели",
    "Что? Способы достижения цели",
    "Когда и где я буду?",
    "Какой я? Самосовершенствование. Сильные и требующие развития качества и навыки"
]

EDITABLE_FIELDS = [
    "profile_name",
    "Карьерный рост",
    "Текущее направление",
    "Текущий возраст",
    "Текущая роль",
    "Доп. комментарий",
    "Цель. Куда? Зачем?",
    "Как? Понимание, как добраться до цели",
    "Что? Способы достижения цели",
    "Когда и где я буду?",
    "Какой я? Самосовершенствование. Сильные и требующие развития качества и навыки"
]

MENU_ANON_MESSAGE = "📤 Анонимно отправить сообщение"
MENU_GET_ADVICE = "💌 Получить совет / поддержку"
MENU_SIGNUP_MEETING = "📅 Записаться на встречу с руководителем"
MENU_UPDATE_PATH = "✏ Актуализировать свой путь в АРТе"
MENU_VIEW_PROFILE = "📝 Посмотреть свою анкету"

MAIN_MENU_BUTTONS = [
    [MENU_ANON_MESSAGE],
    [MENU_GET_ADVICE],
    [MENU_SIGNUP_MEETING],
    [MENU_UPDATE_PATH],
    [MENU_VIEW_PROFILE],
]

# Perf
MAX_CONCURRENT_UPDATES = 10
REQUESTS_PER_SECOND_LIMIT = 5
DB_CONNECTION_TIMEOUT = 5
API_TIMEOUT = 10
CONNECTION_POOL_SIZE = 10

# Timeouts
DEFAULT_TIMEOUT = 10
LONG_OPERATION_TIMEOUT = 30
WEBHOOK_TIMEOUT = 30

# Limits
MAX_MESSAGE_LENGTH = 4096
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
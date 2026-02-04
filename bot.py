
import logging
import sys
import os
import random
from copy import deepcopy
from dotenv import load_dotenv

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

# Загрузка переменных окружения
load_dotenv()

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TG_TOKEN')
if not TOKEN:
    print("Error: TG_TOKEN environment variable is missing.")
    sys.exit(1)

# Состояния разговора
CONTINUE_GAME = 1
FINISH_GAME = 2

# Константы для игры
FREE_SPACE = '.'
CROSS = 'X'
ZERO = 'O'

# Создаем пустое поле
DEFAULT_STATE = [[FREE_SPACE for _ in range(3)] for _ in range(3)]

def get_default_state():
    """Возвращает копию чистого поля"""
    return deepcopy(DEFAULT_STATE)

def generate_keyboard(state: list[list[str]]) -> list[list[InlineKeyboardButton]]:
    """Генерирует клавиатуру 3x3"""
    return [
        [
            InlineKeyboardButton(state[r][c], callback_data=f'{r}{c}')
            for c in range(3) # Внутренний цикл - это столбцы (строка формируется слева направо)
        ]
        for r in range(3)     # Внешний цикл - это строки
    ]

def won(board: list[list[str]]) -> bool:
    """Проверяет, выиграл ли кто-то (возвращает True/False)"""
    # Проверка строк
    for r in range(3):
        if board[r][0] == board[r][1] == board[r][2] != FREE_SPACE:
            return True
    # Проверка столбцов
    for c in range(3):
        if board[0][c] == board[1][c] == board[2][c] != FREE_SPACE:
            return True
    # Проверка диагоналей
    if board[0][0] == board[1][1] == board[2][2] != FREE_SPACE:
        return True
    if board[0][2] == board[1][1] == board[2][0] != FREE_SPACE:
        return True
        
    return False

def is_draw(board: list[list[str]]) -> bool:
    """Проверка на ничью (нет свободных клеток)"""
    for row in board:
        if FREE_SPACE in row:
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало игры"""
    context.user_data['keyboard_state'] = get_default_state()
    context.user_data['turn'] = CROSS # Первыми ходят крестики
    
    keyboard = generate_keyboard(context.user_data['keyboard_state'])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f'Игра началась! Ход: {CROSS}', 
        reply_markup=reply_markup
    )
    return CONTINUE_GAME

async def game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    # Координаты, куда нажал игрок
    row = int(query.data[0])
    col = int(query.data[1])
    
    board = context.user_data['keyboard_state']

    # --- 1. ХОД ИГРОКА (X) ---
    if board[row][col] != FREE_SPACE:
        await query.answer("Сюда нельзя!", show_alert=True)
        return CONTINUE_GAME

    board[row][col] = CROSS
    await query.answer() 

    # Проверка победы игрока
    if won(board):
        await query.edit_message_text(
            text="Ты победил! \n/start чтобы сыграть снова.",
            reply_markup=InlineKeyboardMarkup(generate_keyboard(board))
        )
        return ConversationHandler.END

    # Проверка ничьей после хода игрока
    if is_draw(board):
        await query.edit_message_text(
            text="Ничья! \n/start чтобы сыграть снова.",
            reply_markup=InlineKeyboardMarkup(generate_keyboard(board))
        )
        return ConversationHandler.END

    # --- 2. ХОД БОТА (O) ---
    # Ищем все свободные клетки
    empty_spots = []
    for r in range(3):
        for c in range(3):
            if board[r][c] == FREE_SPACE:
                empty_spots.append((r, c))
    
    # Бот выбирает случайную свободную клетку
    if empty_spots:
        bot_row, bot_col = random.choice(empty_spots)
        board[bot_row][bot_col] = ZERO
    
    # Проверка победы бота
    if won(board):
        await query.edit_message_text(
            text="Бот выиграл! \n/start чтобы сыграть снова.",
            reply_markup=InlineKeyboardMarkup(generate_keyboard(board))
        )
        return ConversationHandler.END
        
    # Проверка ничьей после хода бота 
    if is_draw(board):
        await query.edit_message_text(
            text="Ничья! \n/start чтобы сыграть снова.",
            reply_markup=InlineKeyboardMarkup(generate_keyboard(board))
        )
        return ConversationHandler.END

    # --- 3. ОБНОВЛЕНИЕ ЭКРАНА ---
    # Если никто не выиграл, просто обновляем поле
    await query.edit_message_text(
        text=f"Твой ход ({CROSS})",
        reply_markup=InlineKeyboardMarkup(generate_keyboard(board))
    )
    
    return CONTINUE_GAME

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Принудительное завершение"""
    await update.message.reply_text("Игра остановлена.")
    return ConversationHandler.END

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CONTINUE_GAME: [
                CallbackQueryHandler(game, pattern=r"^\d{2}$") 
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
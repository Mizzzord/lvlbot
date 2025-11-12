# Конфигурация рангов и опыта
# Этот файл содержит настройки опыта, необходимого для достижения различных рангов

from models import Rank

# Опыт, необходимый для достижения каждого ранга
# Ключ - ранг, значение - минимальный опыт для этого ранга
RANK_EXPERIENCE_REQUIREMENTS = {
    Rank.F: 0,        # Начальный ранг, опыта не требуется
    Rank.E: 500,      # 500 опыта для ранга E
    Rank.D: 1500,     # 1500 опыта для ранга D
    Rank.C: 3000,     # 3000 опыта для ранга C
    Rank.B: 5000,     # 5000 опыта для ранга B
    Rank.A: 7500,     # 7500 опыта для ранга A
    Rank.S: 10000,    # 10000 опыта для ранга S
    Rank.S_PLUS: 15000  # 15000 опыта для ранга S+
}

# Максимальный ранг (последний в списке)
MAX_RANK = Rank.S_PLUS

def get_rank_by_experience(experience: int) -> Rank:
    """
    Получение ранга по количеству опыта

    Args:
        experience: Количество опыта игрока

    Returns:
        Rank: Ранг, соответствующий опыту
    """
    # Проходим по рангам в порядке возрастания требований
    current_rank = Rank.F

    for rank, required_exp in RANK_EXPERIENCE_REQUIREMENTS.items():
        if experience >= required_exp:
            current_rank = rank
        else:
            break

    return current_rank

def get_experience_for_rank(rank: Rank) -> int:
    """
    Получение минимального опыта, необходимого для ранга

    Args:
        rank: Ранг

    Returns:
        int: Минимальный опыт для этого ранга
    """
    return RANK_EXPERIENCE_REQUIREMENTS.get(rank, 0)

def get_next_rank_experience(current_experience: int) -> tuple[Rank, int] | None:
    """
    Получение следующего ранга и опыта, необходимого для его достижения

    Args:
        current_experience: Текущий опыт игрока

    Returns:
        tuple[Rank, int] | None: (следующий ранг, необходимый опыт) или None если максимальный ранг достигнут
    """
    current_rank = get_rank_by_experience(current_experience)

    # Если уже максимальный ранг, возвращаем None
    if current_rank == MAX_RANK:
        return None

    # Получаем все ранги в порядке возрастания
    ranks_in_order = list(RANK_EXPERIENCE_REQUIREMENTS.keys())

    try:
        current_index = ranks_in_order.index(current_rank)
        next_rank = ranks_in_order[current_index + 1]
        next_exp = RANK_EXPERIENCE_REQUIREMENTS[next_rank]
        return (next_rank, next_exp)
    except (IndexError, ValueError):
        return None

def get_experience_to_next_rank(current_experience: int) -> int:
    """
    Получение опыта, необходимого для достижения следующего ранга

    Args:
        current_experience: Текущий опыт игрока

    Returns:
        int: Опыт, необходимый для следующего ранга (0 если максимальный ранг достигнут)
    """
    next_rank_info = get_next_rank_experience(current_experience)

    if next_rank_info is None:
        return 0  # Максимальный ранг достигнут

    next_rank, required_exp = next_rank_info
    return max(0, required_exp - current_experience)

def get_rank_progress(current_experience: int) -> tuple[Rank, int, int, float]:
    """
    Получение детальной информации о прогрессе в текущем ранге

    Args:
        current_experience: Текущий опыт игрока

    Returns:
        tuple[Rank, int, int, float]: (текущий ранг, текущий опыт в ранге, опыт до следующего ранга, процент прогресса)
    """
    current_rank = get_rank_by_experience(current_experience)
    current_rank_exp = get_experience_for_rank(current_rank)

    next_rank_info = get_next_rank_experience(current_experience)

    if next_rank_info is None:
        # Максимальный ранг достигнут
        return (current_rank, current_experience - current_rank_exp, 0, 100.0)

    next_rank, next_rank_exp = next_rank_info
    experience_in_current_rank = current_experience - current_rank_exp
    experience_needed_for_next = next_rank_exp - current_rank_exp

    if experience_needed_for_next > 0:
        progress_percentage = (experience_in_current_rank / experience_needed_for_next) * 100
    else:
        progress_percentage = 100.0

    return (current_rank, experience_in_current_rank, experience_needed_for_next - experience_in_current_rank, progress_percentage)

# Эмодзи для рангов (для отображения в интерфейсе)
RANK_EMOJIS = {
    Rank.F: "⚪",      # Белый круг
    Rank.E: "🟢",      # Зеленый круг
    Rank.D: "🟡",      # Желтый круг
    Rank.C: "🟠",      # Оранжевый круг
    Rank.B: "🔴",      # Красный круг
    Rank.A: "🟣",      # Фиолетовый круг
    Rank.S: "🔵",      # Синий круг
    Rank.S_PLUS: "⭐"   # Звезда
}

# Названия рангов на русском
RANK_NAMES = {
    Rank.F: "Новичок",
    Rank.E: "Ученик",
    Rank.D: "Специалист",
    Rank.C: "Эксперт",
    Rank.B: "Мастер",
    Rank.A: "Профессионал",
    Rank.S: "Чемпион",
    Rank.S_PLUS: "Легенда"
}

# Описания рангов
RANK_DESCRIPTIONS = {
    Rank.F: "Начальный уровень. Только начинаете свой путь к цели.",
    Rank.E: "Первый прогресс. Вы на правильном пути!",
    Rank.D: "Хорошее начало. Продолжайте в том же духе!",
    Rank.C: "Серьезный подход. Вы стали опытнее.",
    Rank.B: "Профессиональный уровень. Отличная работа!",
    Rank.A: "Высокий класс. Вы мастер своего дела!",
    Rank.S: "Элита. Вы достигли высот!",
    Rank.S_PLUS: "Легенда. Вы непобедимы!"
}

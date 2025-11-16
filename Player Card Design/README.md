# Player Card Generator

React-based система для генерации карточек игроков с использованием Puppeteer для создания скриншотов.

## Установка

```bash
cd "Player Card Design"
npm install
```

## Запуск

```bash
npm start
```

Сервер запустится на порту 3000.

## API

### POST /generate-card

Генерирует карточку игрока и возвращает PNG изображение.

**Тело запроса:**
```json
{
  "photoPath": "/path/to/photo.jpg",
  "nickname": "Игрок",
  "experience": 1000,
  "level": 5,
  "rank": "C",
  "ratingPosition": 42,
  "stats": {
    "strength": 75,
    "agility": 60,
    "endurance": 80,
    "intelligence": 50,
    "charisma": 65
  }
}
```

**Ответ:** PNG изображение карточки (800x1200px)

## Структура проекта

- `server.js` - Express сервер с эндпоинтом для генерации карточек
- `src/PlayerCard.jsx` - React компонент карточки игрока
- `package.json` - Зависимости проекта

## Технологии

- React 18 - для создания UI компонента карточки
- Puppeteer - для рендеринга React компонента в изображение
- Express - HTTP сервер


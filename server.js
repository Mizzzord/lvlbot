const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { createPlayerCardImage } = require('./card-generator');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware для обработки JSON
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Настройка multer для загрузки файлов
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const uploadDir = path.join(__dirname, 'temp_uploads');
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir, { recursive: true });
        }
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueName = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}${path.extname(file.originalname)}`;
        cb(null, uniqueName);
    }
});

const upload = multer({
    storage: storage,
    limits: {
        fileSize: 10 * 1024 * 1024 // 10MB limit
    }
});

// Очистка временных файлов (старше 1 часа)
function cleanupTempFiles() {
    const tempDir = path.join(__dirname, 'temp_uploads');
    if (!fs.existsSync(tempDir)) return;

    const files = fs.readdirSync(tempDir);
    const now = Date.now();
    const oneHour = 60 * 60 * 1000;

    files.forEach(file => {
        const filePath = path.join(tempDir, file);
        const stats = fs.statSync(filePath);

        if (now - stats.mtime.getTime() > oneHour) {
            try {
                fs.unlinkSync(filePath);
                console.log(`Удален временный файл: ${file}`);
            } catch (error) {
                console.warn(`Не удалось удалить файл ${file}: ${error.message}`);
            }
        }
    });
}

// Очистка каждый час
setInterval(cleanupTempFiles, 60 * 60 * 1000);

/**
 * POST /generate-card
 * Генерирует карточку игрока
 *
 * Body: JSON
 * {
 *   "photoPath": "путь к фото на сервере",
 *   "nickname": "ник игрока",
 *   "experience": 0,
 *   "stats": {
 *     "strength": 75,
 *     "agility": 60,
 *     "endurance": 80,
 *     "intelligence": 50,
 *     "charisma": 50
 *   }
 * }
 */
app.post('/generate-card', async (req, res) => {
    try {
        const { photoPath, nickname, experience, stats } = req.body;

        // Валидация входных данных
        if (!nickname || typeof experience !== 'number' || !stats) {
            return res.status(400).json({
                error: 'Неверные входные данные',
                message: 'Требуются: nickname, experience, stats'
            });
        }

        console.log(`Генерация карточки для пользователя: ${nickname}`);

        // Генерируем изображение
        const imageBuffer = await createPlayerCardImage(photoPath, nickname, experience, stats);

        // Устанавливаем заголовки для ответа
        res.setHeader('Content-Type', 'image/png');
        res.setHeader('Content-Length', imageBuffer.length);
        res.setHeader('Cache-Control', 'no-cache');

        // Отправляем изображение
        res.send(imageBuffer);

        console.log(`Карточка для ${nickname} успешно сгенерирована и отправлена`);

    } catch (error) {
        console.error('Ошибка генерации карточки:', error);
        res.status(500).json({
            error: 'Ошибка генерации карточки',
            message: error.message
        });
    }
});

/**
 * POST /generate-card-with-upload
 * Альтернативный endpoint для загрузки фото через multipart/form-data
 */
app.post('/generate-card-with-upload', upload.single('photo'), async (req, res) => {
    try {
        const { nickname, experience, stats: statsJson } = req.body;
        let stats;

        try {
            stats = JSON.parse(statsJson);
        } catch (error) {
            return res.status(400).json({
                error: 'Неверный формат stats',
                message: 'stats должен быть валидным JSON'
            });
        }

        // Валидация входных данных
        if (!nickname || typeof parseInt(experience) !== 'number' || !stats) {
            return res.status(400).json({
                error: 'Неверные входные данные',
                message: 'Требуются: nickname, experience, stats'
            });
        }

        const photoPath = req.file ? req.file.path : null;

        console.log(`Генерация карточки с загрузкой для пользователя: ${nickname}`);

        // Генерируем изображение
        const imageBuffer = await createPlayerCardImage(photoPath, nickname, parseInt(experience), stats);

        // Устанавливаем заголовки для ответа
        res.setHeader('Content-Type', 'image/png');
        res.setHeader('Content-Length', imageBuffer.length);

        // Отправляем изображение
        res.send(imageBuffer);

        // Удаляем временный файл после отправки
        if (req.file && fs.existsSync(req.file.path)) {
            try {
                fs.unlinkSync(req.file.path);
            } catch (error) {
                console.warn(`Не удалось удалить временный файл: ${error.message}`);
            }
        }

        console.log(`Карточка для ${nickname} успешно сгенерирована и отправлена`);

    } catch (error) {
        console.error('Ошибка генерации карточки:', error);

        // Удаляем временный файл в случае ошибки
        if (req.file && fs.existsSync(req.file.path)) {
            try {
                fs.unlinkSync(req.file.path);
            } catch (cleanupError) {
                console.warn(`Не удалось удалить временный файл при ошибке: ${cleanupError.message}`);
            }
        }

        res.status(500).json({
            error: 'Ошибка генерации карточки',
            message: error.message
        });
    }
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        service: 'Player Card Generator'
    });
});

// Обработка 404
app.use((req, res) => {
    res.status(404).json({
        error: 'Endpoint not found',
        message: `Путь ${req.path} не найден`
    });
});

// Обработка ошибок
app.use((error, req, res, next) => {
    console.error('Unhandled error:', error);
    res.status(500).json({
        error: 'Internal server error',
        message: error.message
    });
});

// Запуск сервера
app.listen(PORT, () => {
    console.log(`🚀 Player Card Generator сервер запущен на порту ${PORT}`);
    console.log(`📊 Health check: http://localhost:${PORT}/health`);
    console.log(`🎮 Генерация карточек: POST http://localhost:${PORT}/generate-card`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('🛑 Получен сигнал SIGINT, завершение работы...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('🛑 Получен сигнал SIGTERM, завершение работы...');
    process.exit(0);
});

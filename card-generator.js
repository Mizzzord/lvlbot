const { createCanvas, loadImage, registerFont } = require('canvas');
const fs = require('fs');
const path = require('path');

/**
 * Создает изображение карточки игрока с помощью Canvas API
 * @param {string} photoPath - путь к фото пользователя
 * @param {string} nickname - ник игрока
 * @param {number} experience - опыт игрока
 * @param {object} stats - словарь с характеристиками
 * @returns {Promise<Buffer>} - буфер изображения PNG
 */
async function createPlayerCardImage(photoPath, nickname, experience, stats) {
    try {
        console.log(`Создание карточки для ${nickname} с помощью Canvas...`);

        // Размеры карточки
        const width = 800;
        const height = 1200;

        // Создаем Canvas
        const canvas = createCanvas(width, height);
        const ctx = canvas.getContext('2d');

        // Градиентный фон
        const bgGradient = ctx.createLinearGradient(0, 0, 0, height);
        bgGradient.addColorStop(0, '#1a1a2e');
        bgGradient.addColorStop(0.5, '#16213e');
        bgGradient.addColorStop(1, '#0f3460');

        ctx.fillStyle = bgGradient;
        ctx.fillRect(0, 0, width, height);

        // Декоративный круг свечения вверху
        const glowGradient = ctx.createRadialGradient(width/2, 100, 0, width/2, 100, 200);
        glowGradient.addColorStop(0, 'rgba(74, 144, 226, 0.3)');
        glowGradient.addColorStop(1, 'rgba(74, 144, 226, 0)');

        ctx.fillStyle = glowGradient;
        ctx.beginPath();
        ctx.arc(width/2, 100, 200, 0, Math.PI * 2);
        ctx.fill();

        // Внешняя рамка с градиентом
        const goldGradient = ctx.createLinearGradient(0, 0, width, 0);
        goldGradient.addColorStop(0, '#FFD700');
        goldGradient.addColorStop(0.5, '#FFA500');
        goldGradient.addColorStop(1, '#FFD700');

        ctx.strokeStyle = goldGradient;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.roundRect(15, 15, width-30, height-30, 20);
        ctx.stroke();

        // Внутренняя рамка
        ctx.strokeStyle = '#4A90E2';
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.5;
        ctx.beginPath();
        ctx.roundRect(20, 20, width-40, height-40, 18);
        ctx.stroke();
        ctx.globalAlpha = 1;

        // Настройки шрифта
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Заголовок
        ctx.fillStyle = '#FFD700';
        ctx.font = 'bold 42px Arial, sans-serif';
        ctx.fillText('ИГРОВАЯ КАРТОЧКА', width/2, 70);

        // Декоративная линия под заголовком
        ctx.strokeStyle = goldGradient;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(width/2 - 150, 85);
        ctx.lineTo(width/2 + 150, 85);
        ctx.stroke();

        // Ник игрока
        ctx.fillStyle = goldGradient;
        ctx.font = 'bold 32px Arial, sans-serif';
        ctx.fillText(nickname || 'Игрок', width/2, 140);

        // Опыт в рамке
        ctx.fillStyle = '#0f3460';
        ctx.strokeStyle = '#4A90E2';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(width/2 - 80, 155, 160, 35, 17.5);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#FFD700';
        ctx.font = 'bold 16px Arial, sans-serif';
        ctx.fillText(`⭐ Опыт: ${experience || 0}`, width/2, 172.5);

        // Заголовок характеристик
        ctx.fillStyle = '#4A90E2';
        ctx.font = 'bold 24px Arial, sans-serif';
        ctx.fillText('ХАРАКТЕРИСТИКИ', width/2, 440);

        // Линия под заголовком характеристик
        ctx.strokeStyle = '#4A90E2';
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.5;
        ctx.beginPath();
        ctx.moveTo(100, 455);
        ctx.lineTo(width - 100, 455);
        ctx.stroke();
        ctx.globalAlpha = 1;

        // Характеристики
                const statNames = {
            strength: { name: '💪 Сила', color: '#FF6B6B' },
            agility: { name: '⚡ Ловкость', color: '#4ECDC4' },
            endurance: { name: '🛡️ Выносливость', color: '#45B7D1' },
            intelligence: { name: '🧠 Интеллект', color: '#A06CD5' },
            charisma: { name: '✨ Харизма', color: '#FFD93D' }
        };

                let currentY = 490;
        const barWidth = width - 240;
        const barHeight = 12;

                for (const [key, info] of Object.entries(statNames)) {
                    const value = stats[key] || 50;
                    const percentage = Math.min(value, 100);

            // Фон для характеристики
            ctx.fillStyle = 'rgba(15, 52, 96, 0.5)';
            ctx.beginPath();
            ctx.roundRect(60, currentY, width - 120, 55, 10);
            ctx.fill();

            // Название характеристики
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 18px Arial, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(info.name, 120, currentY + 25);

            // Значение характеристики
            ctx.fillStyle = info.color;
            ctx.font = 'bold 18px Arial, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(value.toString(), width - 100, currentY + 25);

            // Полоса прогресса - фон
            ctx.fillStyle = '#1a1a2e';
            ctx.strokeStyle = '#4A90E2';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(120, currentY + 35, barWidth, barHeight, 6);
            ctx.fill();
            ctx.stroke();

            // Полоса прогресса - заполнение
                    const progressWidth = (barWidth * percentage) / 100;
            const gradient = ctx.createLinearGradient(120, 0, 120 + progressWidth, 0);
            gradient.addColorStop(0, info.color + 'CC'); // с прозрачностью
            gradient.addColorStop(1, info.color);

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.roundRect(120 + 1, currentY + 36, progressWidth - 2, barHeight - 2, 5);
            ctx.fill();
                    
                    // Процентная отметка
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 10px Arial, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(`${value}%`, 120 + progressWidth - 5, currentY + 41);

                    currentY += 70;
                }

        // Декоративный элемент внизу
        ctx.strokeStyle = goldGradient;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(100, height - 80);
        ctx.lineTo(width - 100, height - 80);
        ctx.stroke();

        // Нижний текст
        ctx.fillStyle = '#4A90E2';
        ctx.font = 'bold 16px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('🎮 @motivation_lvl_bot', width/2, height - 50);

        ctx.fillStyle = '#AAAAAA';
        ctx.font = '12px Arial, sans-serif';
        ctx.fillText('Твой путь к цели начинается здесь', width/2, height - 25);

        // Добавляем фото, если оно есть
        if (photoPath && fs.existsSync(photoPath)) {
            try {
                const photo = await loadImage(photoPath);

                // Создаем круглое фото
                const avatarSize = 150;
                const avatarX = (width - avatarSize) / 2;
                const avatarY = 235;

                // Сохраняем текущий контекст
                ctx.save();

                // Создаем круглую маску
                ctx.beginPath();
                ctx.arc(avatarX + avatarSize/2, avatarY + avatarSize/2, avatarSize/2, 0, Math.PI * 2);
                ctx.clip();

                // Вычисляем размеры для обрезки
                const scale = Math.max(avatarSize / photo.width, avatarSize / photo.height);
                const scaledWidth = photo.width * scale;
                const scaledHeight = photo.height * scale;
                const offsetX = (avatarSize - scaledWidth) / 2;
                const offsetY = (avatarSize - scaledHeight) / 2;

                // Рисуем фото
                ctx.drawImage(photo, avatarX + offsetX, avatarY + offsetY, scaledWidth, scaledHeight);

                // Восстанавливаем контекст
                ctx.restore();

                // Рисуем рамку вокруг аватара
                ctx.strokeStyle = goldGradient;
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(avatarX + avatarSize/2, avatarY + avatarSize/2, avatarSize/2, 0, Math.PI * 2);
                ctx.stroke();

            } catch (photoError) {
                console.warn(`Не удалось обработать фото: ${photoError.message}`);
                // Рисуем placeholder
                ctx.fillStyle = '#0f3460';
                ctx.strokeStyle = goldGradient;
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(width/2, 310, 75, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                ctx.fillStyle = '#FFD700';
                ctx.font = '60px Arial, sans-serif';
                ctx.fillText('👤', width/2, 310);
            }
        } else {
            // Рисуем placeholder для аватара
            ctx.fillStyle = '#0f3460';
            ctx.strokeStyle = goldGradient;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(width/2, 310, 75, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#FFD700';
            ctx.font = '60px Arial, sans-serif';
            ctx.fillText('👤', width/2, 310);
        }

        // Получаем буфер изображения
        const buffer = canvas.toBuffer('image/png');

        console.log(`Карточка игрока создана для: ${nickname}, размер: ${buffer.length} байт`);
        return buffer;

    } catch (error) {
        console.error(`Ошибка создания карточки игрока: ${error.message}`);
        throw error;
    }
}


module.exports = {
    createPlayerCardImage
};

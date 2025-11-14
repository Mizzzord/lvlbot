const { createCanvas, loadImage, registerFont } = require('canvas');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

/**
 * Создает изображение карточки игрока с помощью Canvas API в новом дизайне из Figma
 * @param {string} photoPath - путь к фото пользователя
 * @param {string} nickname - ник игрока
 * @param {number} experience - опыт игрока
 * @param {number} level - уровень игрока
 * @param {string} rank - ранг игрока (например, "S", "A", "B", и т.д.)
 * @param {number} ratingPosition - позиция в общем рейтинге
 * @param {object} stats - словарь с характеристиками
 * @returns {Promise<Buffer>} - буфер изображения PNG
 */
async function createPlayerCardImage(photoPath, nickname, experience, level, rank, ratingPosition, stats) {
    try {
        console.log(`Создание карточки для ${nickname} с помощью Canvas...`);

        // Размеры карточки (пропорционально дизайну из Figma)
        const width = 1866;
        const height = 1399;

        // Создаем Canvas
        const canvas = createCanvas(width, height);
        const ctx = canvas.getContext('2d');

        // Загружаем фото пользователя как фон
        if (photoPath && fs.existsSync(photoPath)) {
            try {
                // Конвертируем изображение в PNG через sharp для поддержки JPEG и других форматов
                let imageBuffer;
                const ext = path.extname(photoPath).toLowerCase();
                if (ext === '.jpg' || ext === '.jpeg' || ext === '.png' || ext === '.webp') {
                    imageBuffer = await sharp(photoPath).png().toBuffer();
                } else {
                    imageBuffer = await fs.promises.readFile(photoPath);
                }
                
                const photo = await loadImage(imageBuffer);
                // Рисуем фото на весь экран с центрированием
                const scale = Math.max(width / photo.width, height / photo.height);
                const scaledWidth = photo.width * scale;
                const scaledHeight = photo.height * scale;
                const offsetX = (width - scaledWidth) / 2;
                const offsetY = (height - scaledHeight) / 2;
                ctx.drawImage(photo, offsetX, offsetY, scaledWidth, scaledHeight);
            } catch (photoError) {
                console.warn(`Не удалось загрузить фото: ${photoError.message}`);
                // Темный фон если фото не загрузилось
                ctx.fillStyle = '#1e1e1e';
                ctx.fillRect(0, 0, width, height);
            }
        } else {
            // Темный фон если фото нет
            ctx.fillStyle = '#1e1e1e';
            ctx.fillRect(0, 0, width, height);
        }

        // Загружаем логотип (если есть)
        const logoPath = path.join(__dirname, 'изображение', 'logo', 'logo.png');
        if (fs.existsSync(logoPath)) {
            try {
                const logo = await loadImage(logoPath);
                const logoWidth = 251.5;
                const logoHeight = 223;
                ctx.drawImage(logo, 20, 18, logoWidth, logoHeight);
            } catch (logoError) {
                console.warn(`Не удалось загрузить логотип: ${logoError.message}`);
            }
        }

        // Темная панель внизу
        const panelWidth = 1040;
        const panelHeight = 500;
        const panelX = (width - panelWidth) / 2;
        const panelY = 830;
        const borderRadius = 30;

        // Рисуем панель с закругленными углами
        ctx.fillStyle = '#1e1e1e';
        ctx.beginPath();
        ctx.roundRect(panelX, panelY, panelWidth, panelHeight, borderRadius);
        ctx.fill();

        // Внутренний отступ панели
        const padding = 40;
        const contentX = panelX + padding;
        const contentY = panelY + (panelHeight / 2);
        const contentWidth = panelWidth - (padding * 2);

        // Имя игрока (96px)
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 96px Arial, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'bottom';
        ctx.fillText(nickname || 'Игрок', contentX, contentY - 200);

        // Ранг и уровень справа (48px, opacity 60%)
        ctx.globalAlpha = 0.6;
        ctx.font = '48px Arial, sans-serif';
        ctx.textAlign = 'right';
        const rankText = `${rank || 'F'} ранг`;
        const levelText = `Ур. ${level || 1}`;
        const rankWidth = ctx.measureText(rankText).width;
        const levelWidth = ctx.measureText(levelText).width;
        const statsHeaderX = panelX + panelWidth - padding;
        ctx.fillText(rankText, statsHeaderX, contentY - 200);
        ctx.fillText(levelText, statsHeaderX, contentY - 200 + 60);
        ctx.globalAlpha = 1;

        // Статистики в сетке 2x3
        const iconsDir = path.join(__dirname, 'изображение', 'icons');
        const statConfig = [
            { key: 'strength', name: 'Сила', icon: path.join(iconsDir, 'strength.svg'), row: 0, col: 0 },
            { key: 'endurance', name: 'Выносливость', icon: path.join(iconsDir, 'endurance.svg'), row: 0, col: 1 },
            { key: 'charisma', name: 'Харизма', icon: path.join(iconsDir, 'charisma.svg'), row: 0, col: 2 },
            { key: 'agility', name: 'Ловкость', icon: path.join(iconsDir, 'agility.svg'), row: 1, col: 0 },
            { key: 'intelligence', name: 'Интеллект', icon: path.join(iconsDir, 'intelligence.svg'), row: 1, col: 1 },
            { key: 'experience', name: 'Опыт', icon: null, row: 1, col: 2 }
        ];

        const statWidth = 216;
        const statHeight = 120;
        const statGapX = 19;
        const statGapY = 26;
        const statsStartX = contentX;
        const statsStartY = contentY - 100;

        for (const config of statConfig) {
            const statX = statsStartX + config.col * (statWidth + statGapX);
            const statY = statsStartY + config.row * (statHeight + statGapY);

            // Получаем значение статистики
            let value;
            if (config.key === 'experience') {
                value = experience || 0;
            } else {
                value = stats[config.key] || 50;
            }

            // Название статистики (24px, italic)
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'italic 24px Arial, sans-serif';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            
            // Иконка (если есть)
            let iconX = statX;
            if (config.icon) {
                if (fs.existsSync(config.icon)) {
                    try {
                        // Конвертируем SVG в PNG через sharp
                        let iconBuffer;
                        if (config.icon.endsWith('.svg')) {
                            iconBuffer = await sharp(config.icon)
                                .resize(36, 36)
                                .png()
                                .toBuffer();
                        } else {
                            iconBuffer = await fs.promises.readFile(config.icon);
                        }
                        
                        const icon = await loadImage(iconBuffer);
                        const iconSize = 36;
                        ctx.drawImage(icon, iconX, statY, iconSize, iconSize);
                        iconX += iconSize + 9;
                    } catch (iconError) {
                        console.warn(`Не удалось загрузить иконку ${config.icon}: ${iconError.message}`);
                    }
                }
            }

            ctx.fillText(config.name, iconX, statY);

            // Значение статистики (57.73px, bold)
            ctx.font = 'bold 57.73px Arial, sans-serif';
            ctx.textBaseline = 'top';
            ctx.fillText(value.toString(), statX, statY + 31);

            // Прогресс-бар
            const barWidth = statWidth;
            const barHeight = 17.581;
            const barY = statY + 100;

            // Фон прогресс-бара (#2a2a2a)
            ctx.fillStyle = '#2a2a2a';
            ctx.beginPath();
            ctx.roundRect(statX, barY, barWidth, barHeight, 25);
            ctx.fill();

            // Заполнение прогресс-бара (#50ff1b)
            const progressPercentage = Math.min(value, 100) / 100;
            const progressWidth = barWidth * progressPercentage;
            ctx.fillStyle = '#50ff1b';
            ctx.beginPath();
            ctx.roundRect(statX, barY + 0.42, progressWidth, barHeight, 25);
            ctx.fill();
        }

        // Боковая панель с рейтингом (250px ширина)
        const ratingPanelWidth = 250;
        const ratingPanelX = panelX + panelWidth - ratingPanelWidth - padding;
        const ratingPanelY = contentY - 100;
        const ratingPanelHeight = statHeight * 2 + statGapY;

        // Фон боковой панели (#343434)
        ctx.fillStyle = '#343434';
        ctx.beginPath();
        ctx.roundRect(ratingPanelX, ratingPanelY, ratingPanelWidth, ratingPanelHeight, 30);
        ctx.fill();

        // Текст "Место в общем рейтинге"
        ctx.fillStyle = '#FFFFFF';
        ctx.globalAlpha = 0.6;
        ctx.font = '33.231px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const ratingTextY = ratingPanelY + 76;
        ctx.fillText('Место', ratingPanelX + ratingPanelWidth / 2, ratingTextY);
        ctx.font = '22.154px Arial, sans-serif';
        ctx.fillText('в общем рейтинге', ratingPanelX + ratingPanelWidth / 2, ratingTextY + 33);

        // Позиция в рейтинге (64px)
        ctx.globalAlpha = 1;
        ctx.font = 'bold 64px Arial, sans-serif';
        const positionText = `№${String(ratingPosition || 0).padStart(7, '0')}`;
        ctx.fillText(positionText, ratingPanelX + ratingPanelWidth / 2, ratingTextY + 80);

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

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

/**
 * Создает изображение карточки игрока с помощью Sharp
 * @param {string} photoPath - путь к фото пользователя
 * @param {string} nickname - ник игрока
 * @param {number} experience - опыт игрока
 * @param {object} stats - словарь с характеристиками
 * @returns {Promise<Buffer>} - буфер изображения PNG
 */
async function createPlayerCardImage(photoPath, nickname, experience, stats) {
    try {
        console.log(`Создание карточки для ${nickname} с помощью Sharp...`);

        // Размеры карточки
        const width = 800;
        const height = 1200;

        // Создаем большой SVG со всей карточкой
        const svgContent = `
        <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
            <!-- Градиентный фон -->
            <defs>
                <linearGradient id="bgGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#16213e;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#0f3460;stop-opacity:1" />
                </linearGradient>
                
                <linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color:#FFD700;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#FFA500;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#FFD700;stop-opacity:1" />
                </linearGradient>

                <radialGradient id="glowGradient" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" style="stop-color:#4A90E2;stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:#4A90E2;stop-opacity:0" />
                </radialGradient>

                <!-- Фильтр свечения -->
                <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>

            <!-- Фоновый градиент -->
            <rect width="${width}" height="${height}" fill="url(#bgGradient)"/>

            <!-- Декоративный круг свечения вверху -->
            <circle cx="${width/2}" cy="100" r="200" fill="url(#glowGradient)"/>

            <!-- Внешняя рамка с градиентом -->
            <rect x="15" y="15" width="${width-30}" height="${height-30}"
                  fill="none" stroke="url(#goldGradient)" stroke-width="3" rx="20"/>
            
            <!-- Внутренняя рамка -->
            <rect x="20" y="20" width="${width-40}" height="${height-40}"
                  fill="none" stroke="#4A90E2" stroke-width="2" rx="18" opacity="0.5"/>

            <!-- Заголовок с тенью -->
            <text x="${width/2}" y="70" font-family="Arial, sans-serif"
                  font-size="42" font-weight="bold" fill="#FFD700"
                  text-anchor="middle" filter="url(#glow)">ИГРОВАЯ КАРТОЧКА</text>

            <!-- Декоративная линия под заголовком -->
            <line x1="${width/2 - 150}" y1="85" x2="${width/2 + 150}" y2="85" 
                  stroke="url(#goldGradient)" stroke-width="2"/>

            <!-- Ник игрока с подсветкой -->
            <text x="${width/2}" y="140" font-family="Arial, sans-serif"
                  font-size="32" font-weight="bold" fill="url(#goldGradient)"
                  text-anchor="middle" filter="url(#glow)">${nickname || 'Игрок'}</text>

            <!-- Опыт в красивой рамке -->
            <rect x="${width/2 - 80}" y="155" width="160" height="35" 
                  fill="#0f3460" stroke="#4A90E2" stroke-width="2" rx="17.5"/>
            <text x="${width/2}" y="180" font-family="Arial, sans-serif"
                  font-size="16" font-weight="bold" fill="#FFD700"
                  text-anchor="middle">⭐ Опыт: ${experience || 0}</text>

            <!-- Фото placeholder с красивой рамкой -->
            ${!photoPath || !fs.existsSync(photoPath) ? `
            <circle cx="${width/2}" cy="310" r="85" fill="#0f3460" stroke="url(#goldGradient)" stroke-width="3"/>
            <circle cx="${width/2}" cy="310" r="75" fill="#1a1a2e"/>
            <text x="${width/2}" y="325" font-family="Arial, sans-serif"
                  font-size="60" fill="#FFD700" text-anchor="middle">👤</text>
            ` : `
            <circle cx="${width/2}" cy="310" r="85" fill="none" stroke="url(#goldGradient)" stroke-width="3"/>
            `}

            <!-- Заголовок секции характеристик -->
            <text x="${width/2}" y="440" font-family="Arial, sans-serif"
                  font-size="24" font-weight="bold" fill="#4A90E2"
                  text-anchor="middle">ХАРАКТЕРИСТИКИ</text>
            
            <line x1="100" y1="455" x2="${width - 100}" y2="455" 
                  stroke="#4A90E2" stroke-width="1" opacity="0.5"/>

            <!-- Характеристики -->
            ${(() => {
                const statNames = {
                    strength: { name: 'Сила', icon: '💪', color: '#FF6B6B' },
                    agility: { name: 'Ловкость', icon: '⚡', color: '#4ECDC4' },
                    endurance: { name: 'Выносливость', icon: '🛡️', color: '#45B7D1' },
                    intelligence: { name: 'Интеллект', icon: '🧠', color: '#A06CD5' },
                    charisma: { name: 'Харизма', icon: '✨', color: '#FFD93D' }
                };

                let result = '';
                let currentY = 490;

                for (const [key, info] of Object.entries(statNames)) {
                    const value = stats[key] || 50;
                    const percentage = Math.min(value, 100);

                    // Фон для каждой характеристики
                    result += `<rect x="60" y="${currentY}" width="${width - 120}" height="55"
                          fill="#0f3460" rx="10" opacity="0.5"/>`;

                    // Иконка
                    result += `<text x="80" y="${currentY + 33}" font-family="Arial, sans-serif"
                          font-size="24">${info.icon}</text>`;

                    // Название
                    result += `<text x="120" y="${currentY + 25}" font-family="Arial, sans-serif"
                          font-size="18" font-weight="bold" fill="#FFFFFF">${info.name}</text>`;
                    
                    // Значение
                    result += `<text x="${width - 100}" y="${currentY + 25}" font-family="Arial, sans-serif"
                          font-size="18" font-weight="bold" fill="${info.color}">${value}</text>`;

                    // Полоса прогресса с градиентом
                    const barWidth = width - 240;
                    const barHeight = 12;
                    const progressWidth = (barWidth * percentage) / 100;
                    const barX = 120;

                    // Фон полосы
                    result += `<rect x="${barX}" y="${currentY + 35}" width="${barWidth}" height="${barHeight}"
                          fill="#1a1a2e" stroke="#4A90E2" stroke-width="1" rx="6"/>`;
                    
                    // Прогресс
                    result += `<defs>
                        <linearGradient id="statGradient${key}" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" style="stop-color:${info.color};stop-opacity:0.8" />
                            <stop offset="100%" style="stop-color:${info.color};stop-opacity:1" />
                        </linearGradient>
                    </defs>`;
                    
                    result += `<rect x="${barX}" y="${currentY + 35}" width="${progressWidth}" height="${barHeight}"
                          fill="url(#statGradient${key})" rx="6"/>`;
                    
                    // Процентная отметка
                    result += `<text x="${barX + progressWidth - 25}" y="${currentY + 44}" 
                          font-family="Arial, sans-serif"
                          font-size="10" fill="#FFFFFF" font-weight="bold">${value}%</text>`;

                    currentY += 70;
                }

                return result;
            })()}

            <!-- Декоративный элемент внизу -->
            <rect x="100" y="${height - 80}" width="${width - 200}" height="2"
                  fill="url(#goldGradient)"/>
            
            <!-- Нижний текст с иконкой -->
            <text x="${width/2}" y="${height - 50}" font-family="Arial, sans-serif"
                  font-size="16" fill="#4A90E2" font-weight="bold"
                  text-anchor="middle">🎮 @motivation_lvl_bot</text>
            
            <text x="${width/2}" y="${height - 25}" font-family="Arial, sans-serif"
                  font-size="12" fill="#AAAAAA"
                  text-anchor="middle">Твой путь к цели начинается здесь</text>
        </svg>`;

        // Создаем изображение из SVG
        let image = sharp(Buffer.from(svgContent)).png();

        // Добавляем фото, если оно есть
        if (photoPath && fs.existsSync(photoPath)) {
            try {
                const photoBuffer = fs.readFileSync(photoPath);
                
                // Создаем круглое фото с обрезкой
                const resizedPhoto = await sharp(photoBuffer)
                    .resize(150, 150, { fit: 'cover', position: 'center' })
                    .composite([{
                        input: Buffer.from(`
                            <svg width="150" height="150">
                                <circle cx="75" cy="75" r="75" fill="white"/>
                            </svg>
                        `),
                        blend: 'dest-in'
                    }])
                    .png()
                    .toBuffer();

                // Компонуем фото на изображение (центрируем в круге)
                image = image.composite([{
                    input: resizedPhoto,
                    top: 235,  // 310 - 75 (радиус фото)
                    left: (width - 150) / 2
                }]);
            } catch (photoError) {
                console.warn(`Не удалось обработать фото: ${photoError.message}`);
            }
        }

        const result = await image.toBuffer();

        console.log(`Карточка игрока создана для: ${nickname}, размер: ${result.length} байт`);
        return result;

    } catch (error) {
        console.error(`Ошибка создания карточки игрока: ${error.message}`);
        throw error;
    }
}


module.exports = {
    createPlayerCardImage
};

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

/**
 * Создает изображение карточки игрока через Puppeteer, используя React компонент из Player Card Design
 * @param {string} photoPath - путь к фото пользователя
 * @param {string} nickname - ник игрока
 * @param {number} experience - опыт игрока (не используется)
 * @param {number} level - уровень игрока
 * @param {string} rank - ранг игрока (например, "S", "A", "B", и т.д.)
 * @param {number} ratingPosition - позиция в общем рейтинге
 * @param {object} stats - словарь с характеристиками
 * @param {number} daysStreak - количество дней подряд (опционально)
 * @returns {Promise<Buffer>} - буфер изображения PNG
 */
async function createPlayerCardImage(photoPath, nickname, experience, level, rank, ratingPosition, stats, daysStreak = 0) {
    let browser = null;
    
    try {
        console.log(`Создание карточки для ${nickname} через Puppeteer...`);

        // Маппинг статов из старого формата в новый
        const statsMapping = {
            'power': stats.strength || 50,
            'durability': stats.endurance || 50,
            'speed': stats.agility || 50,
            'intelligent': stats.intelligence || 50,
            'charism': stats.charisma || 50
        };

        // Подготавливаем данные для React компонента
        const playerData = {
            name: nickname || 'Игрок',
            level: level || 1,
            rank: rank || 'F',
            rankPlace: ratingPosition || 0,
            photoUrl: photoPath || null,
            stats: {
                power: statsMapping.power,
                durability: statsMapping.durability,
                speed: statsMapping.speed,
                intelligent: statsMapping.intelligent,
                charism: statsMapping.charism
            },
            daysStreak: daysStreak || 0
        };

        // Запускаем браузер
        browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu'
            ]
        });

        const page = await browser.newPage();
        
        // Устанавливаем размер viewport
        await page.setViewport({
            width: 1000,
            height: 1000,
            deviceScaleFactor: 1
        });

        // Загружаем HTML шаблон
        const templatePath = path.join(__dirname, 'card-template.html');
        let htmlContent = fs.readFileSync(templatePath, 'utf8');
        
        // Заменяем путь к логотипу на абсолютный
        const logoPath = path.join(__dirname, 'Player Card Design', 'src', 'assets', '623026b0aee19a3e8aafdbf38ec66e6d38000773.png');
        if (fs.existsSync(logoPath)) {
            try {
                // Конвертируем логотип в base64
                const logoBuffer = fs.readFileSync(logoPath);
                const logoBase64 = logoBuffer.toString('base64');
                const logoExt = path.extname(logoPath).toLowerCase().slice(1);
                const mimeType = logoExt === 'png' ? 'png' : (logoExt === 'jpg' || logoExt === 'jpeg' ? 'jpeg' : 'png');
                const logoDataUrl = `data:image/${mimeType};base64,${logoBase64}`;
                htmlContent = htmlContent.replace('PLAYER_CARD_DESIGN_LOGO_PATH', logoDataUrl);
                console.log(`✅ Логотип загружен: ${logoPath}`);
            } catch (logoError) {
                console.warn(`⚠️ Не удалось загрузить логотип: ${logoError.message}`);
                htmlContent = htmlContent.replace('src="PLAYER_CARD_DESIGN_LOGO_PATH"', 'style="display: none"');
            }
        } else {
            console.warn(`⚠️ Логотип не найден: ${logoPath}`);
            htmlContent = htmlContent.replace('src="PLAYER_CARD_DESIGN_LOGO_PATH"', 'style="display: none"');
        }
        
        // Обрабатываем путь к фото пользователя
        if (photoPath && fs.existsSync(photoPath)) {
            try {
                // Конвертируем фото в base64
                const photoBuffer = fs.readFileSync(photoPath);
                const photoBase64 = photoBuffer.toString('base64');
                const photoExt = path.extname(photoPath).toLowerCase().slice(1);
                const mimeType = photoExt === 'jpg' || photoExt === 'jpeg' ? 'jpeg' : photoExt;
                const photoDataUrl = `data:image/${mimeType};base64,${photoBase64}`;
                playerData.photoUrl = photoDataUrl;
            } catch (photoError) {
                console.warn(`Не удалось загрузить фото: ${photoError.message}`);
                playerData.photoUrl = null;
            }
        } else {
            // Пробуем найти фото по разным путям
            const pathsToTry = [
                photoPath,
                path.isAbsolute(photoPath) ? photoPath : path.join(__dirname, photoPath),
                path.join(process.cwd(), photoPath)
            ];
            
            let photoFound = false;
            for (const tryPath of pathsToTry) {
                if (tryPath && fs.existsSync(tryPath)) {
                    try {
                        const photoBuffer = fs.readFileSync(tryPath);
                        const photoBase64 = photoBuffer.toString('base64');
                        const photoExt = path.extname(tryPath).toLowerCase().slice(1);
                        const mimeType = photoExt === 'jpg' || photoExt === 'jpeg' ? 'jpeg' : photoExt;
                        const photoDataUrl = `data:image/${mimeType};base64,${photoBase64}`;
                        playerData.photoUrl = photoDataUrl;
                        photoFound = true;
                        break;
                    } catch (e) {
                        // Продолжаем поиск
                    }
                }
            }
            
            if (!photoFound) {
                console.warn(`⚠️ Фото не найдено по пути: ${photoPath}`);
                playerData.photoUrl = null;
            }
        }

        // Устанавливаем HTML контент
        await page.setContent(htmlContent, { waitUntil: 'networkidle0' });

        // Передаем данные в React компонент
        await page.evaluate((data) => {
            if (window.renderCard) {
                window.renderCard(data);
            } else {
                window.playerData = data;
            }
        }, playerData);

        // Ждем рендеринга React компонента
        await page.waitForFunction(() => {
            const root = document.getElementById('root');
            return root && root.children.length > 0;
        }, { timeout: 5000 });

        // Дополнительная задержка для полного рендеринга (waitForTimeout удален в новых версиях Puppeteer)
        await new Promise(resolve => setTimeout(resolve, 500));

        // Делаем скриншот карточки
        const screenshot = await page.screenshot({
            type: 'png',
            clip: {
                x: 0,
                y: 0,
                width: 1000,
                height: 1000
            }
        });

        console.log(`✅ Карточка создана для: ${nickname}, размер: ${screenshot.length} байт`);
        return screenshot;

    } catch (error) {
        console.error(`❌ Ошибка создания карточки: ${error.message}`);
        throw error;
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

module.exports = {
    createPlayerCardImage
};

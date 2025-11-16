const express = require('express');
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');
const cors = require('cors');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Функция для рендеринга React компонента в HTML
function renderCard(data) {
  // Конвертируем путь к фото в data URL для браузера
  let photoUrl = '';
  if (data.photoPath) {
    try {
      const absolutePath = path.resolve(data.photoPath);
      
      // Проверка безопасности: путь должен быть внутри разрешенных директорий
      const projectRoot = path.resolve(__dirname, '..');
      const allowedDirs = [
        path.join(projectRoot, 'player_photos'),
        path.join(projectRoot, 'player_cards'),
        path.join(__dirname, 'player_photos'),
        path.join(__dirname, 'player_cards')
      ];
      
      const isAllowed = allowedDirs.some(dir => absolutePath.startsWith(path.resolve(dir)));
      
      if (!isAllowed) {
        console.warn(`Попытка доступа к файлу вне разрешенных директорий: ${absolutePath}`);
        photoUrl = '';
      } else if (fs.existsSync(absolutePath)) {
        // Проверяем, что это действительно изображение
        const imageExtension = path.extname(absolutePath).slice(1).toLowerCase();
        const allowedExtensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
        
        if (allowedExtensions.includes(imageExtension)) {
          // Ограничиваем размер файла (10MB)
          const stats = fs.statSync(absolutePath);
          if (stats.size > 10 * 1024 * 1024) {
            console.warn(`Файл слишком большой: ${absolutePath} (${stats.size} байт)`);
            photoUrl = '';
          } else {
      // Используем data URL для изображения
      const imageBuffer = fs.readFileSync(absolutePath);
      const imageBase64 = imageBuffer.toString('base64');
      photoUrl = `data:image/${imageExtension};base64,${imageBase64}`;
          }
        } else {
          console.warn(`Неподдерживаемый формат изображения: ${imageExtension}`);
          photoUrl = '';
        }
      }
    } catch (error) {
      console.error(`Ошибка при обработке фото: ${error.message}`);
      photoUrl = '';
    }
  }
  
  const cardData = { ...data, photoPath: photoUrl };
  
  return `
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Player Card</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: Arial, sans-serif;
        }
        #root {
            width: 800px;
            height: 1200px;
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script>
        // Встраиваем данные для клиентского рендеринга
        window.cardData = ${JSON.stringify(cardData)};
    </script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script type="text/babel">
        const { useState, useEffect } = React;
        
        function PlayerCard({ data }) {
          const {
            photoPath,
            nickname,
            experience,
            level,
            rank,
            ratingPosition,
            stats
          } = data;

          const statNames = {
            strength: '💪 Сила',
            agility: '🤸 Ловкость',
            endurance: '🏃 Выносливость',
            intelligence: '🧠 Интеллект',
            charisma: '✨ Харизма'
          };

          const getStatColor = (value) => {
            if (value >= 80) return '#4ade80';
            if (value >= 60) return '#60a5fa';
            if (value >= 40) return '#fbbf24';
            return '#f87171';
          };

          const cardStyle = {
            width: '800px',
            height: '1200px',
            position: 'relative',
            overflow: 'hidden',
            fontFamily: 'Arial, sans-serif',
            backgroundImage: photoPath ? \`url(\${photoPath})\` : 'linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat'
          };

          const overlayStyle = {
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(2px)'
          };

          const topPanelStyle = {
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '180px',
            background: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            boxSizing: 'border-box'
          };

          const titleStyle = {
            fontSize: '52px',
            fontWeight: 'bold',
            color: '#ffd700',
            textShadow: '2px 2px 4px rgba(0, 0, 0, 0.8)',
            marginBottom: '10px',
            textAlign: 'center'
          };

          const nicknameStyle = {
            fontSize: '42px',
            fontWeight: 'bold',
            color: '#ffffff',
            textShadow: '2px 2px 4px rgba(0, 0, 0, 0.8)',
            textAlign: 'center'
          };

          const infoPanelStyle = {
            position: 'absolute',
            top: '200px',
            left: '40px',
            width: '720px',
            height: '120px',
            background: 'rgba(0, 0, 0, 0.7)',
            borderRadius: '10px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            boxSizing: 'border-box'
          };

          const infoRowStyle = {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '28px',
            color: '#ffffff'
          };

          const statsPanelStyle = {
            position: 'absolute',
            top: '350px',
            left: '40px',
            width: '720px',
            height: '550px',
            background: 'rgba(0, 0, 0, 0.75)',
            borderRadius: '10px',
            padding: '20px',
            boxSizing: 'border-box'
          };

          const statsTitleStyle = {
            fontSize: '28px',
            fontWeight: 'bold',
            color: '#ffd700',
            textAlign: 'center',
            marginBottom: '30px'
          };

          const statRowStyle = {
            marginBottom: '50px'
          };

          const statLabelStyle = {
            fontSize: '26px',
            color: '#ffffff',
            marginBottom: '10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          };

          const progressBarContainerStyle = {
            width: '100%',
            height: '30px',
            background: '#1e1e1e',
            borderRadius: '15px',
            border: '2px solid #b0c4de',
            overflow: 'hidden',
            position: 'relative'
          };

          const progressBarFillStyle = (value) => ({
            height: '100%',
            width: \`\${value}%\`,
            background: \`linear-gradient(90deg, \${getStatColor(value)} 0%, \${getStatColor(value)}dd 100%)\`,
            borderRadius: '13px',
            transition: 'width 0.3s ease'
          });

          const footerStyle = {
            position: 'absolute',
            bottom: '30px',
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: '18px',
            color: '#999999',
            textAlign: 'center'
          };

          return React.createElement('div', { style: cardStyle },
            React.createElement('div', { style: overlayStyle }),
            React.createElement('div', { style: topPanelStyle },
              React.createElement('div', { style: titleStyle }, 'ИГРОВАЯ КАРТОЧКА'),
              React.createElement('div', { style: nicknameStyle }, nickname)
            ),
            React.createElement('div', { style: infoPanelStyle },
              React.createElement('div', { style: infoRowStyle },
                React.createElement('span', null, \`📊 Уровень: \${level}\`),
                React.createElement('span', { style: { color: '#ff8c00' } }, \`⭐ \${experience} XP\`)
              ),
              React.createElement('div', { style: infoRowStyle },
                React.createElement('span', { style: { color: '#ffd700' } }, \`🏅 Ранг: \${rank}\`),
                ratingPosition && React.createElement('span', { style: { color: '#b0c4de', fontSize: '24px' } }, \`🏆 #\${ratingPosition}\`)
              )
            ),
            React.createElement('div', { style: statsPanelStyle },
              React.createElement('div', { style: statsTitleStyle }, 'ХАРАКТЕРИСТИКИ'),
              Object.entries(statNames).map(([key, label]) => {
                const value = stats[key] || 50;
                return React.createElement('div', { key, style: statRowStyle },
                  React.createElement('div', { style: statLabelStyle },
                    React.createElement('span', null, label),
                    React.createElement('span', { style: { color: '#ffd700' } }, \`\${value}/100\`)
                  ),
                  React.createElement('div', { style: progressBarContainerStyle },
                    React.createElement('div', { style: progressBarFillStyle(value) })
                  )
                );
              })
            ),
            React.createElement('div', { style: footerStyle }, '© Motivation Bot')
          );
        }
        
        ReactDOM.render(
          React.createElement(PlayerCard, { data: window.cardData }),
          document.getElementById('root')
        );
    </script>
</body>
</html>
  `;
}

// Эндпоинт для генерации карточки
app.post('/generate-card', async (req, res) => {
  try {
    const { photoPath, nickname, experience, level, rank, ratingPosition, stats } = req.body;

    console.log('Получен запрос на генерацию карточки:', {
      nickname,
      level,
      rank,
      experience
    });

    // Валидация данных
    if (!nickname || !stats) {
      return res.status(400).json({ error: 'Отсутствуют обязательные поля: nickname, stats' });
    }

    // Валидация типов и значений
    if (typeof nickname !== 'string' || nickname.length > 100) {
      return res.status(400).json({ error: 'Некорректное значение nickname' });
    }

    if (typeof stats !== 'object' || stats === null) {
      return res.status(400).json({ error: 'stats должен быть объектом' });
    }

    // Валидация характеристик (должны быть числа от 0 до 100)
    const statKeys = ['strength', 'agility', 'endurance', 'intelligence', 'charisma'];
    for (const key of statKeys) {
      if (stats[key] !== undefined && (typeof stats[key] !== 'number' || stats[key] < 0 || stats[key] > 100)) {
        return res.status(400).json({ error: `Характеристика ${key} должна быть числом от 0 до 100` });
      }
    }

    // Валидация других полей
    if (level !== undefined && (typeof level !== 'number' || level < 1 || level > 1000)) {
      return res.status(400).json({ error: 'level должен быть числом от 1 до 1000' });
    }

    if (experience !== undefined && (typeof experience !== 'number' || experience < 0)) {
      return res.status(400).json({ error: 'experience должен быть неотрицательным числом' });
    }

    // Подготавливаем данные для карточки
    const cardData = {
      photoPath: photoPath || null,
      nickname: nickname || 'Игрок',
      experience: experience || 0,
      level: level || 1,
      rank: rank || 'F',
      ratingPosition: ratingPosition || null,
      stats: {
        strength: stats.strength || 50,
        agility: stats.agility || 50,
        endurance: stats.endurance || 50,
        intelligence: stats.intelligence || 50,
        charisma: stats.charisma || 50
      }
    };

    // Рендерим HTML
    const html = renderCard(cardData);

    // Запускаем браузер и делаем скриншот
    let browser = null;
    try {
      browser = await puppeteer.launch({
        headless: "new",
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    
    // Устанавливаем размер страницы
    await page.setViewport({
      width: 800,
      height: 1200,
      deviceScaleFactor: 2 // Для лучшего качества
    });

    // Загружаем HTML
    await page.setContent(html, { waitUntil: 'networkidle0' });

      // Ждем загрузки изображения и рендеринга React компонента
      // Используем waitForFunction вместо устаревшего waitForTimeout
      await page.waitForFunction(
        () => {
          const root = document.getElementById('root');
          return root && root.children.length > 0;
        },
        { timeout: 5000 }
      );

      // Дополнительная задержка для завершения анимаций и рендеринга
      await new Promise(resolve => setTimeout(resolve, 500));

    // Делаем скриншот
    const screenshot = await page.screenshot({
      type: 'png',
      clip: {
        x: 0,
        y: 0,
        width: 800,
        height: 1200
      }
    });

    await browser.close();
      browser = null;

    // Отправляем изображение
    res.setHeader('Content-Type', 'image/png');
    res.send(screenshot);
    } catch (browserError) {
      // Гарантируем закрытие браузера при ошибке
      if (browser) {
        try {
          await browser.close();
        } catch (closeError) {
          console.error('Ошибка при закрытии браузера:', closeError);
        }
      }
      throw browserError;
    }

  } catch (error) {
    console.error('Ошибка при генерации карточки:', error);
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.listen(PORT, () => {
  console.log(`🚀 Сервер генерации карточек запущен на порту ${PORT}`);
});


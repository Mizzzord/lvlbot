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
      let absolutePath = path.resolve(data.photoPath);
      
      // Проверка существования по абсолютному пути
      if (!fs.existsSync(absolutePath)) {
          // Попытка найти относительно корня проекта, если путь пришел как 'player_photos/...'
          const projectRoot = path.resolve(__dirname, '..');
          const relativePath = path.join(projectRoot, data.photoPath);
          if (fs.existsSync(relativePath)) {
              absolutePath = relativePath;
          }
      }

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
      } else {
          console.warn(`Файл не найден: ${absolutePath}`);
          photoUrl = '';
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
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Russo+One&display=swap" rel="stylesheet">
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
            font-family: 'Roboto', sans-serif;
            background: #000;
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
        window.cardData = ${JSON.stringify(cardData)};
    </script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script type="text/babel">
        const { useState, useEffect } = React;

        const PlayerCard = ({ data }) => {
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
            strength: { label: 'СИЛА', icon: '💪' },
            agility: { label: 'ЛОВКОСТЬ', icon: '⚡' },
            endurance: { label: 'ВЫНОСЛИВОСТЬ', icon: '🛡️' },
            intelligence: { label: 'ИНТЕЛЛЕКТ', icon: '🧠' },
            charisma: { label: 'ХАРИЗМА', icon: '✨' }
          };

          const formatNumber = (num) => num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, " ");
          
          // Основной цвет акцентов - оранжевый
          const primaryColor = '#ff6600'; // Яркий оранжевый
          const secondaryColor = '#e05500'; // Более темный оранжевый
          const textColor = '#ffffff';
          const dimColor = 'rgba(255,255,255,0.5)';

          const styles = {
            card: {
              width: '800px',
              height: '1200px',
              position: 'relative',
              overflow: 'hidden',
              fontFamily: "'Roboto', sans-serif",
              backgroundColor: '#1a1a2e',
              color: '#fff',
              borderRadius: '40px', // Закругленные углы карточки
            },
            background: {
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              // Используем фото пользователя как основной фон
              backgroundImage: photoPath ? \`url(\${photoPath})\` : 'linear-gradient(135deg, #0f0c29, #302b63, #24243e)',
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              zIndex: 1,
            },
            overlay: {
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              // Более темный градиент снизу для читаемости текста
              background: 'linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.6) 50%, #000000 100%)',
              zIndex: 2,
            },
            borderFrame: {
              position: 'absolute',
              top: '20px',
              left: '20px',
              right: '20px',
              bottom: '20px',
              border: \`2px solid \${primaryColor}\`,
              boxShadow: \`inset 0 0 30px \${primaryColor}40\`,
              borderRadius: '30px', // Закругленные углы рамки
              zIndex: 3,
              pointerEvents: 'none',
            },
            content: {
                position: 'absolute',
                zIndex: 4,
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '60px 40px',
                boxSizing: 'border-box',
            },
            header: {
                textAlign: 'center',
                textShadow: '0 4px 10px rgba(0,0,0,0.8)',
            },
            title: {
                fontFamily: "'Russo One', sans-serif",
                fontSize: '24px',
                letterSpacing: '4px',
                color: primaryColor,
                marginBottom: '10px',
                textTransform: 'uppercase',
            },
            nickname: {
                fontFamily: "'Russo One', sans-serif",
                fontSize: '64px',
                color: '#fff',
                textTransform: 'uppercase',
                letterSpacing: '2px',
                textShadow: '0 0 20px rgba(0, 0, 0, 0.8)',
                marginBottom: '20px',
                lineHeight: '1.1',
            },
            mainStats: {
                display: 'flex',
                justifyContent: 'center',
                gap: '30px',
                marginTop: '30px',
            },
            mainStatBox: {
                background: 'rgba(0,0,0,0.6)',
                backdropFilter: 'blur(10px)',
                padding: '15px 25px',
                borderRadius: '20px', // Более мягкие углы
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                border: '1px solid rgba(255,255,255,0.1)',
                minWidth: '130px',
                boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
            },
            mainStatValue: {
                fontFamily: "'Russo One', sans-serif",
                fontSize: '42px',
                color: primaryColor,
                lineHeight: '1',
                marginBottom: '5px',
            },
            mainStatLabel: {
                fontSize: '14px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                color: 'rgba(255,255,255,0.7)',
                fontWeight: '500',
            },
            xpText: {
                marginTop: '25px', 
                color: '#fff', 
                fontSize: '20px',
                fontFamily: "'Russo One', sans-serif",
                letterSpacing: '1px',
                background: \`rgba(255, 102, 0, 0.8)\`, // Оранжевый фон
                display: 'inline-block',
                padding: '8px 20px',
                borderRadius: '20px',
                backdropFilter: 'blur(5px)',
                boxShadow: '0 0 15px rgba(255, 102, 0, 0.4)',
            },
            statsContainer: {
                background: 'rgba(20, 20, 20, 0.85)', // Темно-серый фон
                backdropFilter: 'blur(15px)',
                borderRadius: '30px', // Более мягкие углы
                padding: '40px',
                border: \`1px solid rgba(255, 255, 255, 0.1)\`,
                borderTop: \`4px solid \${primaryColor}\`, // Оранжевая полоска сверху
                marginTop: 'auto',
                marginBottom: '40px',
                boxShadow: '0 10px 40px rgba(0,0,0,0.6)',
            },
            statsRow: {
                marginBottom: '28px',
            },
            statsHeader: {
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '12px',
                fontFamily: "'Russo One', sans-serif",
                fontSize: '22px',
                color: '#fff',
            },
            progressBarBg: {
                height: '16px',
                background: 'rgba(255, 255, 255, 0.1)',
                borderRadius: '10px', // Более мягкие углы
                overflow: 'hidden',
                boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.3)',
            },
            progressBarFill: (value) => ({
                height: '100%',
                width: \`\${value}%\`,
                background: \`linear-gradient(90deg, \${secondaryColor} 0%, \${primaryColor} 100%)\`, // Оранжевый градиент
                borderRadius: '10px', // Более мягкие углы
                boxShadow: \`0 0 10px \${primaryColor}80\`,
                transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
            }),
            footer: {
                textAlign: 'center',
                color: 'rgba(255,255,255,0.4)',
                fontSize: '16px',
                letterSpacing: '3px',
                textTransform: 'uppercase',
                fontFamily: "'Russo One', sans-serif",
            }
          };

          return (
            <div style={styles.card}>
              <div style={styles.background} />
              <div style={styles.overlay} />
              <div style={styles.borderFrame} />
              
              <div style={styles.content}>
                <div style={styles.header}>
                    <div style={styles.title}>Карточка участника</div>
                    <div style={styles.nickname}>{nickname}</div>
                    
                    <div style={styles.mainStats}>
                         <div style={styles.mainStatBox}>
                            <div style={styles.mainStatValue}>{level}</div>
                            <div style={styles.mainStatLabel}>Уровень</div>
                         </div>
                         <div style={styles.mainStatBox}>
                            <div style={styles.mainStatValue}>{rank}</div>
                            <div style={styles.mainStatLabel}>Ранг</div>
                         </div>
                         {ratingPosition && (
                             <div style={styles.mainStatBox}>
                                <div style={styles.mainStatValue}>#{ratingPosition}</div>
                                <div style={styles.mainStatLabel}>Рейтинг</div>
                             </div>
                         )}
                    </div>
                    
                    <div style={styles.xpText}>
                        ⚡ {formatNumber(experience)} XP
                    </div>
                </div>

                <div style={styles.statsContainer}>
                    {Object.entries(statNames).map(([key, conf]) => {
                        const value = stats[key] || 0;
                        return (
                            <div key={key} style={styles.statsRow}>
                                <div style={styles.statsHeader}>
                                    <span style={{display: 'flex', alignItems: 'center', gap: '15px'}}>
                                        <span style={{fontSize: '28px', filter: 'drop-shadow(0 0 5px rgba(0,0,0,0.5))'}}>{conf.icon}</span>
                                        {conf.label}
                                    </span>
                                    <span style={{color: primaryColor}}>{value}/100</span>
                                </div>
                                <div style={styles.progressBarBg}>
                                    <div style={styles.progressBarFill(value)} />
                                </div>
                            </div>
                        );
                    })}
                </div>
                
                <div style={styles.footer}>
                    Go Prime
                </div>
              </div>
            </div>
          );
        };
        
        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<PlayerCard data={window.cardData} />);
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
      experience,
      photoPath
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

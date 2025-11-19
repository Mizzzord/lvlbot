import React from 'react';

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

  const formatNumber = (num) => num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  
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
      backgroundImage: photoPath ? `url(${photoPath})` : 'linear-gradient(135deg, #0f0c29, #302b63, #24243e)',
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
      border: `2px solid ${primaryColor}`,
      boxShadow: `inset 0 0 30px ${primaryColor}40`,
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
        background: `rgba(255, 102, 0, 0.8)`, // Оранжевый фон
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
        border: `1px solid rgba(255, 255, 255, 0.1)`,
        borderTop: `4px solid ${primaryColor}`, // Оранжевая полоска сверху
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
        width: `${value}%`,
        background: `linear-gradient(90deg, ${secondaryColor} 0%, ${primaryColor} 100%)`, // Оранжевый градиент
        borderRadius: '10px', // Более мягкие углы
        boxShadow: `0 0 10px ${primaryColor}80`,
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

export default PlayerCard;

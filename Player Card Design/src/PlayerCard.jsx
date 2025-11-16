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
    strength: '💪 Сила',
    agility: '🤸 Ловкость',
    endurance: '🏃 Выносливость',
    intelligence: '🧠 Интеллект',
    charisma: '✨ Харизма'
  };

  const getStatColor = (value) => {
    if (value >= 80) return '#4ade80'; // зеленый
    if (value >= 60) return '#60a5fa'; // синий
    if (value >= 40) return '#fbbf24'; // желтый
    return '#f87171'; // красный
  };

  const cardStyle = {
    width: '800px',
    height: '1200px',
    position: 'relative',
    overflow: 'hidden',
    fontFamily: 'Arial, sans-serif',
    backgroundImage: photoPath ? `url(file://${photoPath})` : 'linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%)',
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
    width: `${value}%`,
    background: `linear-gradient(90deg, ${getStatColor(value)} 0%, ${getStatColor(value)}dd 100%)`,
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

  return (
    <div style={cardStyle}>
      <div style={overlayStyle} />
      
      {/* Верхняя панель */}
      <div style={topPanelStyle}>
        <div style={titleStyle}>ИГРОВАЯ КАРТОЧКА</div>
        <div style={nicknameStyle}>{nickname}</div>
      </div>

      {/* Информационная панель */}
      <div style={infoPanelStyle}>
        <div style={infoRowStyle}>
          <span>📊 Уровень: {level}</span>
          <span style={{ color: '#ff8c00' }}>⭐ {experience} XP</span>
        </div>
        <div style={infoRowStyle}>
          <span style={{ color: '#ffd700' }}>🏅 Ранг: {rank}</span>
          {ratingPosition && (
            <span style={{ color: '#b0c4de', fontSize: '24px' }}>🏆 #{ratingPosition}</span>
          )}
        </div>
      </div>

      {/* Панель характеристик */}
      <div style={statsPanelStyle}>
        <div style={statsTitleStyle}>ХАРАКТЕРИСТИКИ</div>
        
        {Object.entries(statNames).map(([key, label]) => {
          const value = stats[key] || 50;
          return (
            <div key={key} style={statRowStyle}>
              <div style={statLabelStyle}>
                <span>{label}</span>
                <span style={{ color: '#ffd700' }}>{value}/100</span>
              </div>
              <div style={progressBarContainerStyle}>
                <div style={progressBarFillStyle(value)} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Футер */}
      <div style={footerStyle}>© Motivation Bot</div>
    </div>
  );
};

export default PlayerCard;


import { PlayerCard } from "./components/PlayerCard";

function App() {
  const playerData = {
    name: "Shadow Wolf",
    level: 47,
    rank: "Diamond I",
    rankPlace: 42,
    photoUrl: "https://images.unsplash.com/photo-1667970573560-6ecf6a143514?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxnYW1lciUyMHBvcnRyYWl0fGVufDF8fHx8MTc2MzE0MjA1MXww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
    stats: {
      power: 850,
      durability: 720,
      speed: 965,
      intelligent: 880,
      charism: 795
    },
    daysStreak: 42
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-black flex items-center justify-center p-8">
      <PlayerCard player={playerData} />
    </div>
  );
}

export default App;

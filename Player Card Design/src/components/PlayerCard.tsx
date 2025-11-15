import { Badge } from "./ui/badge";
import { Card } from "./ui/card";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import { Zap, Shield, Gauge, Brain, Smile, Flame, Award } from "lucide-react";
import goPrimeLogo from "figma:asset/623026b0aee19a3e8aafdbf38ec66e6d38000773.png";

interface PlayerStats {
  name: string;
  level: number;
  rank: string;
  rankPlace: number;
  photoUrl: string;
  stats: {
    power: number;
    durability: number;
    speed: number;
    intelligent: number;
    charism: number;
  };
  daysStreak: number;
}

interface PlayerCardProps {
  player: PlayerStats;
}

export function PlayerCard({ player }: PlayerCardProps) {
  const formattedRankPlace = `#${player.rankPlace.toString().padStart(5, '0')}`;
  
  return (
    <div className="w-full max-w-sm mx-auto">
      <Card className="relative overflow-hidden p-0 border-2 border-orange-500/30">
        {/* Background Image */}
        <div className="absolute inset-0">
          <ImageWithFallback
            src={player.photoUrl}
            alt={player.name}
            className="w-full h-full object-cover"
          />
          {/* Dark overlay for readability */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/50 via-black/60 to-black/75" />
          {/* Orange tint overlay */}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(234,88,12,0.15),rgba(0,0,0,0))]" />
        </div>
        
        {/* Content */}
        <div className="relative flex flex-col p-6">
          {/* Logo */}
          <div className="flex justify-center mb-3">
            <img src={goPrimeLogo} alt="GoPrime" className="h-12 w-auto" />
          </div>

          {/* Rank Place */}
          <div className="text-center mb-3">
            <span className="text-orange-400/60 text-sm tracking-widest">{formattedRankPlace}</span>
          </div>

          {/* Header with Level, Name and Rank */}
          <div className="flex justify-between items-center mb-6 gap-3">
            <Badge variant="secondary" className="bg-gradient-to-r from-orange-600 to-amber-600 text-white border-0 shadow-lg shadow-orange-500/20 shrink-0">
              <Award className="w-3 h-3 mr-1" />
              Level {player.level}
            </Badge>
            <h2 className="text-center text-white flex-1 min-w-0">{player.name}</h2>
            <Badge variant="outline" className="bg-slate-800/50 backdrop-blur-sm border-orange-500/30 text-orange-400 shrink-0">
              {player.rank}
            </Badge>
          </div>

          {/* Stats */}
          <div className="space-y-2.5 bg-slate-900/20 rounded-lg p-4 border border-orange-500/20 backdrop-blur-sm">
            <div className="flex items-center justify-between text-slate-200">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-orange-400" />
                <span className="text-sm">Power</span>
              </div>
              <span className="text-orange-400">{player.stats.power}</span>
            </div>

            <div className="flex items-center justify-between text-slate-200">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-orange-400" />
                <span className="text-sm">Durability</span>
              </div>
              <span className="text-orange-400">{player.stats.durability}</span>
            </div>

            <div className="flex items-center justify-between text-slate-200">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-orange-400" />
                <span className="text-sm">Speed</span>
              </div>
              <span className="text-orange-400">{player.stats.speed}</span>
            </div>

            <div className="flex items-center justify-between text-slate-200">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-orange-400" />
                <span className="text-sm">Intelligent</span>
              </div>
              <span className="text-orange-400">{player.stats.intelligent}</span>
            </div>

            <div className="flex items-center justify-between text-slate-200">
              <div className="flex items-center gap-2">
                <Smile className="w-4 h-4 text-orange-400" />
                <span className="text-sm">Charism</span>
              </div>
              <span className="text-orange-400">{player.stats.charism}</span>
            </div>

            <div className="pt-2 mt-2 border-t border-orange-500/30">
              <div className="flex items-center justify-between text-slate-200">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-500" />
                  <span className="text-sm">Days Streak</span>
                </div>
                <span className="text-orange-400">{player.daysStreak} days</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

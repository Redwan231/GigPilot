interface ScoreChipProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

function bandStyle(score: number) {
  if (score >= 70) return "bg-success/10 text-success border-success/30";
  if (score >= 50) return "bg-warn/10 text-warn border-warn/30";
  return "bg-danger/10 text-danger border-danger/30";
}

function bandLabel(score: number) {
  if (score >= 70) return "High fit";
  if (score >= 50) return "Medium fit";
  return "Low fit";
}

export default function ScoreChip({ score, size = "md" }: ScoreChipProps) {
  const sizeClass = size === "sm" ? "text-xs px-1.5 py-0.5" : size === "lg" ? "text-lg px-3 py-1" : "text-sm px-2 py-1";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border font-medium ${sizeClass} ${bandStyle(score)}`}
      aria-label={`Score ${score} — ${bandLabel(score)}`}
    >
      <span aria-hidden="true">{score}</span>
      <span className="text-xs opacity-70">/100</span>
    </span>
  );
}
